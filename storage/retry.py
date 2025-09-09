"""
Retry/backoff and rate-limit-aware HTTP GET helper.
This module centralizes request retry logic so callers (e.g. storage.cache) can use it.
"""

import os
import time
import random
import email.utils
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import requests

# retry/backoff defaults from environment
DEFAULT_MAX_RETRIES = int(os.getenv("CONTRIB_MAX_RETRIES", "3"))
DEFAULT_BACKOFF_BASE = float(os.getenv("CONTRIB_BACKOFF_BASE", "0.5"))
_env_jitter = os.getenv("CONTRIB_BACKOFF_JITTER")
DEFAULT_BACKOFF_JITTER = float(_env_jitter) if _env_jitter is not None and _env_jitter != "" else None
DEFAULT_MAX_BACKOFF = float(os.getenv("CONTRIB_MAX_BACKOFF", "120.0"))

# runtime-overrides
_runtime_max_retries: Optional[int] = None
_runtime_backoff_base: Optional[float] = None
_runtime_backoff_jitter: Optional[float] = None
_runtime_max_backoff: Optional[float] = None


def configure_retry(
    max_retries: Optional[int] = None, backoff_base: Optional[float] = None, backoff_jitter: Optional[float] = None, max_backoff: Optional[float] = None
):
    """Configure retry/backoff defaults at runtime (e.g. from CLI)."""
    global _runtime_max_retries, _runtime_backoff_base, _runtime_backoff_jitter, _runtime_max_backoff
    if max_retries is not None:
        _runtime_max_retries = int(max_retries)
    if backoff_base is not None:
        _runtime_backoff_base = float(backoff_base)
    if backoff_jitter is not None:
        _runtime_backoff_jitter = float(backoff_jitter)
    if max_backoff is not None:
        _runtime_max_backoff = float(max_backoff)


def _parse_retry_after(raw_ra: str):
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
    try:
        headers = getattr(resp, 'headers', {}) or {}
        raw_ra = headers.get('Retry-After')
        ra = _parse_retry_after(raw_ra)
        rl_remaining = _safe_int_from_headers(headers, 'X-RateLimit-Remaining')
        rl_reset = _safe_float_from_headers(headers, 'X-RateLimit-Reset')
        return ra, rl_remaining, rl_reset
    except Exception:
        return None, None, None


def _resolve_backoff_params(
    min_wait_local: float, backoff_base_local: Optional[float], backoff_jitter_local: Optional[float], max_backoff_local: Optional[float]
):
    if backoff_base_local is not None:
        base_local = float(backoff_base_local)
    else:
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
    if ra_local is not None:
        try:
            return min(float(ra_local) + random.uniform(0, jitter_local), 300.0)
        except Exception:
            pass
    if rl_reset_local:
        try:
            now = time.time()
            wait = max(0.0, float(rl_reset_local) - now)
            return min(wait + random.uniform(0, jitter_local), 300.0)
        except Exception:
            pass
    return min(backoff_local + random.uniform(0, jitter_local), 300.0)


def _attempt_request_once(url: str, headers: Dict[str, str], params: Dict[str, Any]):
    try:
        resp = requests.get(url, headers=headers or {}, params=params or {})
    except Exception as ex:
        return 'error', {'exception': str(ex)}

    status = getattr(resp, 'status_code', 0)
    ra, rl_remaining, rl_reset = _parse_rate_headers(resp)

    if status == 200:
        body = _parse_success_body(resp)
        return 'success', {'body': body, 'status': status}

    if _should_retry_response(status, ra, rl_remaining):
        return 'retry', {'status': status, 'ra': ra, 'rl_reset': rl_reset, 'text': getattr(resp, 'text', None)}

    try:
        body = resp.json()
    except Exception:
        body = resp.text
    return 'fail', {'body': body, 'status': status}


def _handle_attempt_outcome(outcome: str, data: Dict[str, Any], cache, cache_key: str, backoff: float, max_backoff_resolved: float, jitter_val: float):
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
        backoff = min(backoff * 2, max_backoff_resolved)
        time.sleep(wait_seconds)
        last_result = {'response': data.get('text'), 'status': data.get('status', 0), 'timestamp': time.time()}
        return 'continue', last_result, backoff

    result = {'response': data.get('body'), 'status': data.get('status', 0), 'timestamp': time.time()}
    return 'return', result, backoff


def _request_with_retries_core(
    url: str,
    headers: Dict[str, str],
    params: Dict[str, Any],
    cache,
    cache_key: str,
    base: float,
    jitter_val: float,
    max_backoff_resolved: float,
    effective_max_retries: int,
) -> Dict[str, Any]:
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
        return payload

    return last_result


def perform_request_with_retries(
    url: str,
    headers: Dict[str, str],
    params: Dict[str, Any],
    cache,
    cache_key: str,
    min_wait: float,
    max_retries: int,
    backoff_base: Optional[float] = None,
    backoff_jitter: Optional[float] = None,
    max_backoff: Optional[float] = None,
) -> Dict[str, Any]:
    base, jitter_val, max_backoff_resolved = _resolve_backoff_params(min_wait, backoff_base, backoff_jitter, max_backoff)
    effective_max_retries = int(_runtime_max_retries) if _runtime_max_retries is not None else int(max_retries or DEFAULT_MAX_RETRIES)
    return _request_with_retries_core(url, headers, params, cache, cache_key, base, jitter_val, max_backoff_resolved, effective_max_retries)


__all__ = ["configure_retry", "perform_request_with_retries"]
