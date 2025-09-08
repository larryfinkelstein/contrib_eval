"""
Simple SQLite cache and rate-limit-aware fetch helper.
Stores raw JSON responses keyed by service+resource and timestamp.
"""
import sqlite3
import json
import time
from typing import Optional, Any, Dict
import requests
import threading
import random
import email.utils
from datetime import datetime, timezone
import os

# retry/backoff defaults can be driven by environment variables. These are
# intentionally named with a short prefix to be easy to set in CI/containers.
# - CONTRIB_MAX_RETRIES: int
# - CONTRIB_BACKOFF_BASE: float (seconds)
# - CONTRIB_BACKOFF_JITTER: float (seconds) - if not set, jitter defaults to backoff base
# - CONTRIB_MAX_BACKOFF: float (seconds)
DEFAULT_MAX_RETRIES = int(os.getenv("CONTRIB_MAX_RETRIES", "3"))
DEFAULT_BACKOFF_BASE = float(os.getenv("CONTRIB_BACKOFF_BASE", "0.5"))
# allow jitter to be explicitly set; if not set, we fall back to using base as jitter range
_env_jitter = os.getenv("CONTRIB_BACKOFF_JITTER")
DEFAULT_BACKOFF_JITTER = float(_env_jitter) if _env_jitter is not None and _env_jitter != "" else None
DEFAULT_MAX_BACKOFF = float(os.getenv("CONTRIB_MAX_BACKOFF", "120.0"))

# runtime-configurable values (can be set from CLI at startup)
_runtime_max_retries: Optional[int] = None
_runtime_backoff_base: Optional[float] = None
_runtime_backoff_jitter: Optional[float] = None
_runtime_max_backoff: Optional[float] = None


def configure_retry(max_retries: Optional[int] = None, backoff_base: Optional[float] = None, backoff_jitter: Optional[float] = None, max_backoff: Optional[float] = None):
    """Configure retry/backoff defaults at runtime (e.g. from CLI).

    Only values that are not None will override the environment or built-in defaults.
    This function allows the CLI to set global behavior without passing parameters through
    every call site.
    """
    global _runtime_max_retries, _runtime_backoff_base, _runtime_backoff_jitter, _runtime_max_backoff
    if max_retries is not None:
        _runtime_max_retries = int(max_retries)
    if backoff_base is not None:
        _runtime_backoff_base = float(backoff_base)
    if backoff_jitter is not None:
        _runtime_backoff_jitter = float(backoff_jitter)
    if max_backoff is not None:
        _runtime_max_backoff = float(max_backoff)


DB_PATH = None  # can be overridden by caller

# noinspection SqlResolve
SQL_CREATE = """
CREATE TABLE IF NOT EXISTS http_cache (
    key TEXT PRIMARY KEY,
    response TEXT,
    status INTEGER,
    timestamp REAL
);
"""


class Cache:
    def __init__(self, path: Optional[str] = None):
        self.path = path or DB_PATH or ':memory:'
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self):
        with self._lock:
            cur = self.conn.cursor()
            cur.executescript(SQL_CREATE)
            self.conn.commit()

    def close(self):
        try:
            with self._lock:
                if hasattr(self, 'conn') and self.conn:
                    try:
                        self.conn.close()
                    finally:
                        self.conn = None
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    # noinspection SqlResolve
    def stats(self) -> Dict[str, Any]:
        """Return basic statistics about the cache: count, oldest timestamp, newest timestamp."""
        with self._lock:
            cur = self.conn.cursor()
            cur.execute('SELECT COUNT(1) FROM http_cache')
            count = cur.fetchone()[0]
            cur.execute('SELECT MIN(timestamp), MAX(timestamp) FROM http_cache')
            row = cur.fetchone()
            oldest, newest = row if row else (None, None)
        # make explicit conversions to avoid static analyzer type complaints
        try:
            oldest_val = float(oldest) if oldest is not None else None
        except Exception:
            oldest_val = None
        try:
            newest_val = float(newest) if newest is not None else None
        except Exception:
            newest_val = None
        return {'count': int(count or 0), 'oldest': oldest_val, 'newest': newest_val}

    # noinspection SqlResolve
    def list_keys(self, limit: int = 1000) -> list:
        """Return a list of cache keys with basic metadata (key, status, timestamp), newest first."""
        with self._lock:
            cur = self.conn.cursor()
            cur.execute('SELECT key, status, timestamp FROM http_cache ORDER BY timestamp DESC LIMIT ?', (limit,))
            rows = cur.fetchall()
        items = []
        for k, status, ts in rows:
            items.append({'key': k, 'status': int(status or 0), 'timestamp': float(ts or 0)})
        return items

    # noinspection SqlResolve
    # noinspection SqlWithoutWhere
    def clear(self):
        """Clear all entries from the cache."""
        with self._lock:
            cur = self.conn.cursor()
            cur.execute('DELETE FROM http_cache')
            self.conn.commit()

    # noinspection SqlResolve
    def delete_key(self, key: str) -> int:
        """Delete a specific cache key. Returns number of rows deleted."""
        with self._lock:
            cur = self.conn.cursor()
            cur.execute('DELETE FROM http_cache WHERE key = ?', (key,))
            self.conn.commit()
            return cur.rowcount

    # noinspection SqlResolve
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute('SELECT response, status, timestamp FROM http_cache WHERE key = ?', (key,))
            row = cur.fetchone()
        if not row:
            return None
        response, status, timestamp = row
        try:
            parsed = json.loads(response)
        except Exception:
            # fallback: return raw text as response
            parsed = response
        return {'response': parsed, 'status': status, 'timestamp': timestamp}

    # noinspection SqlResolve
    def set(self, key: str, response: Any, status: int = 200):
        with self._lock:
            cur = self.conn.cursor()
            # ensure we store JSON-serializable content; if not, coerce to string
            try:
                payload = json.dumps(response)
            except Exception:
                payload = json.dumps(str(response))
            cur.execute('REPLACE INTO http_cache(key, response, status, timestamp) VALUES (?, ?, ?, ?)',
                        (key, payload, status, time.time()))
            self.conn.commit()


def _cached_fresh(cache: Cache, cache_key: str, max_age: Optional[float]):
    if not cache or not cache_key:
        return None
    cached = cache.get(cache_key)
    if not cached:
        return None
    if max_age is None:
        return cached
    age = time.time() - float(cached.get('timestamp', 0) or 0)
    if age <= float(max_age):
        return cached
    return None


def _parse_retry_after(raw_ra: str):
    """Parse Retry-After header which may be seconds or HTTP-date string.
    Returns float seconds or None.
    """
    if not raw_ra:
        return None
    try:
        return float(raw_ra)
    except Exception:
        try:
            dt = email.utils.parsedate_to_datetime(raw_ra)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            ra = (dt - datetime.now(timezone.utc)).total_seconds()
            return max(0.0, ra)
        except Exception:
            return None


def _safe_int_from_headers(headers: Dict[str, Any], key: str) -> Optional[int]:
    try:
        val = headers.get(key)
        return int(val) if val is not None else None
    except Exception:
        return None


def _safe_float_from_headers(headers: Dict[str, Any], key: str) -> Optional[float]:
    try:
        val = headers.get(key)
        return float(val) if val is not None else None
    except Exception:
        return None


def _parse_rate_headers(resp):
    """Return (retry_after_seconds, rl_remaining, rl_reset_epoch) parsed from response headers.

    retry_after_seconds: float or None
    rl_remaining: int or None
    rl_reset_epoch: float (unix epoch seconds) or None
    """
    try:
        headers = getattr(resp, 'headers', {}) or {}
        raw_ra = headers.get('Retry-After')
        ra = _parse_retry_after(raw_ra)
        rl_remaining = _safe_int_from_headers(headers, 'X-RateLimit-Remaining')
        rl_reset = _safe_float_from_headers(headers, 'X-RateLimit-Reset')
        return ra, rl_remaining, rl_reset
    except Exception:
        return None, None, None


def _resolve_backoff_params(min_wait_local: float, backoff_base_local: Optional[float], backoff_jitter_local: Optional[float], max_backoff_local: Optional[float]):
    """Resolve base, jitter and max_backoff honoring explicit args, runtime overrides, env, and defaults."""
    if backoff_base_local is not None:
        base_local = float(backoff_base_local)
    else:
        # prefer explicit min_wait, then runtime override, then default
        if min_wait_local:
            base_local = float(min_wait_local)
        elif _runtime_backoff_base is not None:
            base_local = float(_runtime_backoff_base)
        else:
            base_local = float(DEFAULT_BACKOFF_BASE)

    if backoff_jitter_local is not None:
        jitter_local = float(backoff_jitter_local)
    elif _runtime_backoff_jitter is not None:
        jitter_local = float(_runtime_backoff_jitter)
    elif DEFAULT_BACKOFF_JITTER is not None:
        jitter_local = float(DEFAULT_BACKOFF_JITTER)
    else:
        jitter_local = base_local

    if max_backoff_local is not None:
        max_backoff_resolved = float(max_backoff_local)
    elif _runtime_max_backoff is not None:
        max_backoff_resolved = float(_runtime_max_backoff)
    else:
        max_backoff_resolved = float(DEFAULT_MAX_BACKOFF)

    return base_local, jitter_local, max_backoff_resolved


def _parse_success_body(resp_local):
    try:
        return resp_local.json()
    except Exception:
        return getattr(resp_local, 'text', None)


def _should_retry_response(status_code: int, ra_local: Optional[float], rl_remaining_local: Optional[int]) -> bool:
    if status_code in (429, 503):
        return True
    if ra_local is not None:
        return True
    if rl_remaining_local is not None and rl_remaining_local <= 0:
        return True
    return False


def _compute_wait_seconds(ra_local: Optional[float], rl_reset_local: Optional[float], backoff_local: float, jitter_local: float) -> float:
    # prefer explicit retry-after seconds
    if ra_local is not None:
        try:
            return min(float(ra_local) + random.uniform(0, jitter_local), 300.0)
        except Exception:
            pass
    # if reset epoch provided, compute remaining seconds
    if rl_reset_local:
        try:
            now = time.time()
            wait = max(0.0, float(rl_reset_local) - now)
            return min(wait + random.uniform(0, jitter_local), 300.0)
        except Exception:
            pass
    # fallback to backoff with jitter
    return min(backoff_local + random.uniform(0, jitter_local), 300.0)


def _attempt_request_once(url: str, headers: Dict[str, str], params: Dict[str, Any]):
    """Perform a single HTTP GET and classify the outcome.

    Returns a tuple: (outcome, data) where outcome is one of:
    - 'error' : network/exception occurred, data={'exception': str}
    - 'success' : status 200, data={'body': parsed_body, 'status': status}
    - 'retry' : transient rate-limited condition, data={'status': status, 'ra': ra, 'rl_reset': rl_reset, 'text': resp_text}
    - 'fail' : non-retryable non-200 response, data={'body': body, 'status': status}
    """
    try:
        resp = requests.get(url, headers=headers or {}, params=params or {})
    except Exception as ex:
        return 'error', {'exception': str(ex)}

    status = getattr(resp, 'status_code', 0)
    ra, rl_remaining, rl_reset = _parse_rate_headers(resp)

    if status == 200:
        body = _parse_success_body(resp)
        return 'success', {'body': body, 'status': status}

    # transient / rate-limit conditions
    if _should_retry_response(status, ra, rl_remaining):
        return 'retry', {'status': status, 'ra': ra, 'rl_reset': rl_reset, 'text': getattr(resp, 'text', None)}

    # non-retryable non-200: return body
    try:
        body = resp.json()
    except Exception:
        body = resp.text
    return 'fail', {'body': body, 'status': status}


def _handle_attempt_outcome(outcome: str, data: Dict[str, Any], cache: Cache, cache_key: str, backoff: float, max_backoff_resolved: float, jitter_val: float):
    """Handle the result of a single attempt. Returns a tuple (action, payload, backoff).
    action: 'continue' to continue loop, 'return' to return payload immediately.
    payload: for 'continue' it's last_result dict; for 'return' it's the result to return.
    backoff: updated backoff value.
    """
    if outcome == 'error':
        last_result = {'response': data.get('exception'), 'status': 0, 'timestamp': time.time()}
        backoff = min(backoff * 2, max_backoff_resolved)
        return 'continue', last_result, backoff

    if outcome == 'success':
        result = {'response': data.get('body'), 'status': data.get('status', 200), 'timestamp': time.time()}
        if cache and cache_key:
            try:
                cache.set(cache_key, data.get('body'), data.get('status', 200))
            except Exception:
                pass
        return 'return', result, backoff

    if outcome == 'retry':
        wait_seconds = _compute_wait_seconds(data.get('ra'), data.get('rl_reset'), backoff, jitter_val)
        # increase backoff for next loop
        backoff = min(backoff * 2, max_backoff_resolved)
        # sleep now
        time.sleep(wait_seconds)
        last_result = {'response': data.get('text'), 'status': data.get('status', 0), 'timestamp': time.time()}
        return 'continue', last_result, backoff

    # outcome == 'fail'
    result = {'response': data.get('body'), 'status': data.get('status', 0), 'timestamp': time.time()}
    return 'return', result, backoff


def _request_with_retries_core(url: str, headers: Dict[str, str], params: Dict[str, Any], cache: Cache, cache_key: str, base: float, jitter_val: float, max_backoff_resolved: float, effective_max_retries: int) -> Dict[str, Any]:
    """Core retry loop extracted to reduce complexity of the public wrapper."""
    attempt = 0
    backoff = base
    last_result: Dict[str, Any] = {'response': None, 'status': 0, 'timestamp': time.time()}

    while attempt < effective_max_retries:
        if attempt > 0:
            sleep_for = min(backoff + random.uniform(0, jitter_val), max_backoff_resolved)
            time.sleep(sleep_for)

        outcome, data = _attempt_request_once(url, headers, params)

        action, payload, backoff = _handle_attempt_outcome(outcome, data, cache, cache_key, backoff, max_backoff_resolved, jitter_val)

        if action == 'continue':
            last_result = payload
            attempt += 1
            continue
        # action == 'return'
        return payload

    return last_result


def _perform_request_with_retries(url: str, headers: Dict[str, str], params: Dict[str, Any], cache: Cache, cache_key: str, min_wait: float, max_retries: int, backoff_base: Optional[float] = None, backoff_jitter: Optional[float] = None, max_backoff: Optional[float] = None) -> Dict[str, Any]:
    # resolve backoff params
    base, jitter_val, max_backoff_resolved = _resolve_backoff_params(min_wait, backoff_base, backoff_jitter, max_backoff)
    effective_max_retries = int(_runtime_max_retries) if _runtime_max_retries is not None else int(max_retries or DEFAULT_MAX_RETRIES)

    return _request_with_retries_core(url, headers, params, cache, cache_key, base, jitter_val, max_backoff_resolved, effective_max_retries)


def rate_limited_get(url: str, headers: Dict[str, str] = None, params: Dict[str, Any] = None, cache: Cache = None, cache_key: str = None, min_wait: float = 0.5, max_age: Optional[float] = None, max_retries: int = 3, backoff_base: Optional[float] = None, backoff_jitter: Optional[float] = None, max_backoff: Optional[float] = None) -> Dict[str, Any]:
    """Public API: perform a GET with caching, rate-limit handling, and retries.

    Checks cache first (honoring max_age), otherwise performs the request with retries/backoff.
    """
    cached = _cached_fresh(cache, cache_key, max_age)
    if cached:
        return cached
    return _perform_request_with_retries(url, headers, params, cache, cache_key, min_wait, max_retries, backoff_base=backoff_base, backoff_jitter=backoff_jitter, max_backoff=max_backoff)


__all__ = ["Cache", "rate_limited_get", "configure_retry"]
