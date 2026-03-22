"""
Per-IP and per-hotkey rate limiting middleware for DDoS mitigation.

Uses a sliding window counter per source IP and per claimed validator hotkey
to throttle excessive requests before they reach the application logic.

Known validator IPs (provided via an external callback) receive relaxed
limits, while unknown IPs are subject to stricter thresholds.
"""

import asyncio
import time
from typing import Callable, Dict, Optional, Set, Tuple

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp


class _SlidingWindowCounter:
    """
    Fixed-window rate limiter.

    Each key gets a counter that resets when the window expires.
    Thread-safe via an asyncio lock.
    """

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._counters: Dict[str, Tuple[float, int]] = {}
        self._lock = asyncio.Lock()

    async def is_rate_limited(self, key: str) -> Tuple[bool, int]:
        """
        Increment the counter for ``key`` and return whether it exceeds the
        configured limit.

        Returns:
            (is_limited, retry_after_seconds)
        """
        now = time.monotonic()

        async with self._lock:
            window_start, count = self._counters.get(key, (now, 0))

            if now - window_start >= self.window_seconds:
                window_start = now
                count = 0

            count += 1
            self._counters[key] = (window_start, count)

            if count > self.max_requests:
                retry_after = max(1, int(self.window_seconds - (now - window_start)))
                return True, retry_after

            return False, 0

    async def cleanup(self) -> None:
        """Remove expired entries to bound memory usage."""
        now = time.monotonic()
        async with self._lock:
            expired = [
                k for k, (ws, _) in self._counters.items()
                if now - ws >= self.window_seconds * 2
            ]
            for k in expired:
                del self._counters[k]


# ---------------------------------------------------------------------------
# Per-endpoint limits for *unknown* IPs (stricter)
# ---------------------------------------------------------------------------
_ENDPOINT_LIMITS_UNKNOWN: Dict[str, int] = {
    "/availability": 6,
    "/fiber/public-key": 6,
    "/fiber/key-exchange": 10,
    "/fiber/challenge": 30,
    "/inference": 15,
}

# Default per-IP limit for unlisted paths (unknown)
_DEFAULT_IP_LIMIT_UNKNOWN = 15

# ---------------------------------------------------------------------------
# Per-endpoint limits for *known* validator IPs (relaxed)
# ---------------------------------------------------------------------------
_ENDPOINT_LIMITS_KNOWN: Dict[str, int] = {
    "/availability": 20,
    "/fiber/public-key": 20,
    "/fiber/key-exchange": 30,
    "/fiber/challenge": 120,
    "/inference": 60,
}

# Default per-IP limit for unlisted paths (known)
_DEFAULT_IP_LIMIT_KNOWN = 60

# Per-hotkey limit (applies to endpoints that carry a hotkey header)
_DEFAULT_HOTKEY_LIMIT = 60

# Window size (seconds)
_WINDOW_SECONDS = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware that enforces per-IP and per-hotkey rate limits.

    Accepts an optional ``known_ips_provider`` callable that returns the
    current set of known validator IPs.  Requests from known IPs are
    subject to relaxed limits; all other IPs receive stricter thresholds.

    Responds with 429 Too Many Requests when limits are exceeded.
    Runs a periodic cleanup task to bound memory.
    """

    def __init__(
        self,
        app: ASGIApp,
        known_ips_provider: Optional[Callable[[], Set[str]]] = None,
    ):
        super().__init__(app)
        self._known_ips_provider = known_ips_provider

        self._ip_limiters_unknown: Dict[str, _SlidingWindowCounter] = {}
        for path, limit in _ENDPOINT_LIMITS_UNKNOWN.items():
            self._ip_limiters_unknown[path] = _SlidingWindowCounter(limit, _WINDOW_SECONDS)
        self._default_ip_limiter_unknown = _SlidingWindowCounter(
            _DEFAULT_IP_LIMIT_UNKNOWN, _WINDOW_SECONDS
        )

        self._ip_limiters_known: Dict[str, _SlidingWindowCounter] = {}
        for path, limit in _ENDPOINT_LIMITS_KNOWN.items():
            self._ip_limiters_known[path] = _SlidingWindowCounter(limit, _WINDOW_SECONDS)
        self._default_ip_limiter_known = _SlidingWindowCounter(
            _DEFAULT_IP_LIMIT_KNOWN, _WINDOW_SECONDS
        )

        self._hotkey_limiter = _SlidingWindowCounter(_DEFAULT_HOTKEY_LIMIT, _WINDOW_SECONDS)
        self._cleanup_task: Optional[asyncio.Task] = None

    def _get_known_ips(self) -> Set[str]:
        if self._known_ips_provider is not None:
            try:
                return self._known_ips_provider()
            except Exception:
                pass
        return set()

    def _ensure_cleanup(self) -> None:
        if self._cleanup_task is None or self._cleanup_task.done():
            try:
                loop = asyncio.get_running_loop()
                self._cleanup_task = loop.create_task(self._periodic_cleanup())
            except RuntimeError:
                pass

    async def _periodic_cleanup(self) -> None:
        while True:
            await asyncio.sleep(_WINDOW_SECONDS * 2)
            try:
                for limiter in self._ip_limiters_unknown.values():
                    await limiter.cleanup()
                await self._default_ip_limiter_unknown.cleanup()
                for limiter in self._ip_limiters_known.values():
                    await limiter.cleanup()
                await self._default_ip_limiter_known.cleanup()
                await self._hotkey_limiter.cleanup()
            except Exception as e:
                logger.debug(f"Rate limiter cleanup error: {e}")

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        self._ensure_cleanup()

        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path

        known_ips = self._get_known_ips()
        is_known = client_ip in known_ips

        if is_known:
            ip_limiter = self._ip_limiters_known.get(
                path, self._default_ip_limiter_known
            )
        else:
            ip_limiter = self._ip_limiters_unknown.get(
                path, self._default_ip_limiter_unknown
            )

        limited, retry_after = await ip_limiter.is_rate_limited(client_ip)
        if limited:
            logger.warning(
                f"Rate limit exceeded for {'known' if is_known else 'unknown'} "
                f"IP {client_ip} on {path} (retry after {retry_after}s)"
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": str(retry_after)},
            )

        hotkey = (
            request.headers.get("x-fiber-validator-hotkey-ss58")
            or request.headers.get("validator-hotkey")
        )
        if hotkey:
            limited, retry_after = await self._hotkey_limiter.is_rate_limited(hotkey)
            if limited:
                logger.warning(
                    f"Rate limit exceeded for hotkey {hotkey[:8]}... on {path} "
                    f"(retry after {retry_after}s)"
                )
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded for validator"},
                    headers={"Retry-After": str(retry_after)},
                )

        return await call_next(request)
