"""Shared POST with one retry on 429/5xx/timeouts (jittered), none on 400/403."""

import logging
import random
import time
from collections.abc import Callable
from typing import Any

import httpx

from kuralcheck.throttle import Throttle
from kuralcheck.clients.errors import (
    ApiAuthError,
    ApiBadRequest,
    ApiError,
    ApiRateLimited,
    ApiServerError,
)

log = logging.getLogger("kuralcheck.http")

RETRYABLE = {429, 500, 502, 503, 504}


def _error_for(status: int, name: str) -> ApiError:
    if status == 400:
        return ApiBadRequest(f"{name}: 400 bad request", status)
    if status in (401, 403):
        return ApiAuthError(f"{name}: {status} (check GNANI_API_KEY and credits)", status)
    if status == 429:
        return ApiRateLimited(f"{name}: 429 rate limited", status)
    if status >= 500:
        return ApiServerError(f"{name}: {status} server error", status)
    return ApiError(f"{name}: unexpected status {status}", status)


def _backoff(response: httpx.Response | None) -> float:
    retry_after = response.headers.get("retry-after") if response is not None else None
    if retry_after and retry_after.isdigit():
        return min(float(retry_after), 10.0)
    if response is not None and response.status_code == 429:
        return random.uniform(2.0, 4.0)  # rate limited: back off longer
    return random.uniform(0.5, 1.5)


def post_with_retry(
    http: httpx.Client,
    url: str,
    *,
    name: str,
    retries: int = 1,
    sleep: Callable[[float], None] = time.sleep,
    throttle: Throttle | None = None,
    **kwargs: Any,
) -> tuple[httpx.Response, float]:
    """Returns (successful response, latency in ms of the attempt that succeeded)."""
    for attempt in range(retries + 1):
        last = attempt == retries
        if throttle is not None:
            throttle.wait()
        start = time.perf_counter()
        try:
            resp = http.post(url, **kwargs)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            log.warning("%s attempt=%d network error=%s", name, attempt + 1, type(exc).__name__)
            if last:
                raise ApiServerError(f"{name}: network error ({type(exc).__name__})") from None
            sleep(_backoff(None))
            continue
        latency_ms = (time.perf_counter() - start) * 1000
        log.info("%s attempt=%d status=%d latency_ms=%.0f", name, attempt + 1, resp.status_code, latency_ms)
        if throttle is not None:
            if resp.status_code == 429:
                throttle.on_rate_limited()
            elif resp.is_success:
                throttle.on_success()
        if resp.is_success:
            return resp, latency_ms
        if resp.status_code not in RETRYABLE or last:
            raise _error_for(resp.status_code, name)
        sleep(_backoff(resp))
    raise AssertionError("unreachable")
