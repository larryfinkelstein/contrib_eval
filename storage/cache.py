"""
Simple SQLite cache and rate-limit-aware fetch helper.
Stores raw JSON responses keyed by service+resource and timestamp.
"""

import sqlite3
import json
import time
from typing import Optional, Any, Dict
import threading
import os
import requests  # re-exported for compatibility with tests that patch storage.cache.requests  # noqa: F401

# Delegate retry/backoff logic to storage.retry
from .retry import perform_request_with_retries, configure_retry as _retry_configure

# retry/backoff defaults can be driven by environment variables. These are
# intentionally named with a short prefix to be easy to set in CI/containers.
# - CONTRIB_MAX_RETRIES: int
# - CONTRIB_BACKOFF_BASE: float (seconds)
# - CONTRIB_BACKOFF_JITTER: float (seconds) - if not set, jitter defaults to backoff base
# - CONTRIB_MAX_BACKOFF: float (seconds)
DEFAULT_MAX_RETRIES = int(os.getenv("CONTRIB_MAX_RETRIES", "3"))
DEFAULT_BACKOFF_BASE = float(os.getenv("CONTRIB_BACKOFF_BASE", "0.5"))

# runtime-configurable values (can be set from CLI at startup)
_runtime_max_retries: Optional[int] = None
_runtime_backoff_base: Optional[float] = None
_runtime_backoff_jitter: Optional[float] = None
_runtime_max_backoff: Optional[float] = None


def configure_retry(
    max_retries: Optional[int] = None, backoff_base: Optional[float] = None, backoff_jitter: Optional[float] = None, max_backoff: Optional[float] = None
):
    """Configure retry/backoff defaults at runtime (delegates to storage.retry.configure_retry)."""
    global _runtime_max_retries, _runtime_backoff_base, _runtime_backoff_jitter, _runtime_max_backoff
    if max_retries is not None:
        _runtime_max_retries = int(max_retries)
    if backoff_base is not None:
        _runtime_backoff_base = float(backoff_base)
    if backoff_jitter is not None:
        _runtime_backoff_jitter = float(backoff_jitter)
    if max_backoff is not None:
        _runtime_max_backoff = float(max_backoff)
    # propagate to retry module
    _retry_configure(max_retries=max_retries, backoff_base=backoff_base, backoff_jitter=backoff_jitter, max_backoff=max_backoff)


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
    def __init__(self, path: Optional[str] = None, max_entries: Optional[int] = None, ttl_seconds: Optional[float] = None):
        """Create a cache instance.

        :param path: SQLite file path or None for in-memory.
        :param max_entries: optional maximum number of entries to keep; older entries will be pruned when exceeded.
        :param ttl_seconds: optional TTL in seconds; entries older than TTL will be pruned on set/get.
        """
        self.path = path or DB_PATH or ':memory:'
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self._lock = threading.RLock()
        self.max_entries = int(max_entries) if max_entries is not None else None
        self.ttl_seconds = float(ttl_seconds) if ttl_seconds is not None else None
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
        # TTL-based eviction on access
        if self.ttl_seconds is not None and timestamp is not None:
            age = time.time() - float(timestamp)
            if age > self.ttl_seconds:
                try:
                    self.delete_key(key)
                except Exception:
                    pass
                return None
        return {'response': parsed, 'status': status, 'timestamp': timestamp}

    # noinspection SqlResolve
    def _prune_if_needed(self):
        """Prune cache entries based on TTL and max_entries settings."""
        with self._lock:
            cur = self.conn.cursor()
            # TTL-based pruning
            if self.ttl_seconds is not None:
                cutoff = time.time() - float(self.ttl_seconds)
                cur.execute('DELETE FROM http_cache WHERE timestamp < ?', (cutoff,))
            # size-based pruning: remove oldest entries if count exceeds max_entries
            if self.max_entries is not None:
                cur.execute('SELECT COUNT(1) FROM http_cache')
                count = cur.fetchone()[0] or 0
                if count > self.max_entries:
                    # delete oldest rows until we're at max_entries
                    to_remove = int(count - self.max_entries)
                    # delete by ascending timestamp
                    cur.execute('SELECT key FROM http_cache ORDER BY timestamp ASC LIMIT ?', (to_remove,))
                    rows = cur.fetchall() or []
                    keys = [r[0] for r in rows]
                    if keys:
                        cur.executemany('DELETE FROM http_cache WHERE key = ?', [(k,) for k in keys])
            self.conn.commit()

    # noinspection SqlResolve
    def set(self, key: str, response: Any, status: int = 200):
        with self._lock:
            # ensure we store JSON-serializable content; if not, coerce to string
            try:
                payload = json.dumps(response)
            except Exception:
                payload = json.dumps(str(response))
            cur = self.conn.cursor()
            cur.execute('REPLACE INTO http_cache(key, response, status, timestamp) VALUES (?, ?, ?, ?)', (key, payload, status, time.time()))
            self.conn.commit()
            # prune TTL or size if configured
            try:
                self._prune_if_needed()
            except Exception:
                pass


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


def rate_limited_get(
    url: str,
    headers: Dict[str, str] = None,
    params: Dict[str, Any] = None,
    cache: Cache = None,
    cache_key: str = None,
    min_wait: float = 0.5,
    max_age: Optional[float] = None,
    max_retries: int = 3,
    backoff_base: Optional[float] = None,
    backoff_jitter: Optional[float] = None,
    max_backoff: Optional[float] = None,
) -> Dict[str, Any]:
    """Public API: perform a GET with caching, rate-limit handling, and retries.

    Checks cache first (honoring max_age), otherwise performs the request with retries/backoff via storage.retry.
    """
    cached = _cached_fresh(cache, cache_key, max_age)
    if cached:
        return cached

    # delegate to perform_request_with_retries in storage.retry
    result = perform_request_with_retries(
        url, headers or {}, params or {}, cache, cache_key or '', min_wait, max_retries, backoff_base, backoff_jitter, max_backoff
    )
    return result


__all__ = ["Cache", "rate_limited_get", "configure_retry"]
