"""
User Rate Limiting Middleware for FastAPI.

Implements a fixed-window rate limiter using Redis, keyed by the authenticated
username (from request.state.current_user set by BasicAuthMiddleware).
Falls back to client TCP peer IP for unauthenticated/excluded paths.
"""

from typing import Callable, Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.providers.logger import Logger


def get_rate_limit_identifier(request: Request) -> str:
    """
    Derive a rate-limit key from the authenticated user identity, falling back
    to the real TCP peer IP (never client-supplied headers to prevent spoofing).

    request.state.current_user is populated by BasicAuthMiddleware and may be
    a dict ({"username": ..., "email": ...}) or an object with those attributes.
    """
    user_info = getattr(request.state, "current_user", None)
    if user_info is not None:
        # Support both dict and object shapes
        if isinstance(user_info, dict):
            username = user_info.get("username") or user_info.get("email")
        else:
            username = getattr(user_info, "username", None) or getattr(user_info, "email", None)
        if username:
            return f"user:{username}"

    # Fallback: use the real TCP connection IP.
    # X-Forwarded-For is NOT used — it is client-controlled and can be trivially
    # spoofed to bypass per-IP rate limits.
    ip = request.client.host if request.client else "unknown"
    return f"ip:{ip}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Per-user rate limiting middleware using a Redis fixed-window counter.

    Key strategy:
    - Authenticated users: keyed by username from request.state.current_user
    - Unauthenticated requests: keyed by real TCP peer IP (not X-Forwarded-For)

    Algorithm (fixed window):
    - Redis key: ``rate_limit:{identifier}:{bucket}``
    - Atomic INCR+EXPIRE via pipeline on first request to prevent key leaks
    - If counter exceeds the limit → 429 Too Many Requests
    - If Redis is unavailable → allow the request (fail-open) + log warning
    """

    _DEFAULT_EXCLUDED_PATHS = [
        # Infrastructure / public endpoints
        "/",
        "/health",
        "/metrics",
        "/metrics/",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
        "/api/v1/health",
        # Auth endpoints that must be reachable before login
        "/api/v1/auth/login",
        "/api/v1/auth/google_oauth/callback",
        "/api/v1/auth/status",
        # External system callbacks — rate-limiting these would block Slack/GitHub/plugins,
        # not users. Each has its own verification (HMAC, webhook secret, etc.)
        "/api/v1/slack",
        "/api/v1/external_metrics/claude_plugins",
        "/api/v1/pr-review/webhook",
    ]

    def __init__(
        self,
        app,
        requests_per_window: int = 100,
        window_seconds: int = 60,
        enabled: bool = True,
        excluded_paths: Optional[list] = None,
        included_paths: Optional[list] = None,
    ) -> None:
        super().__init__(app)
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self.enabled = enabled
        self.excluded_paths = excluded_paths or self._DEFAULT_EXCLUDED_PATHS
        # When set, only requests matching these prefixes are rate-limited.
        # When None, all paths except excluded_paths are rate-limited.
        self.included_paths = included_paths
        self.logger = Logger("RateLimitMiddleware")

        scope = f"paths={included_paths}" if included_paths else "all paths"
        self.logger.info(
            f"Rate limit middleware initialised: enabled={enabled}, "
            f"limit={requests_per_window} req/{window_seconds}s, scope={scope}"
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.enabled:
            return await call_next(request)

        # Only rate-limit write/execution requests (POST, PUT, PATCH).
        # GET/HEAD/OPTIONS are read operations and must never consume the budget.
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)

        # When included_paths is set, only rate-limit matching paths
        if self.included_paths and not self._is_included(request):
            return await call_next(request)

        # Skip excluded paths (infrastructure, external callbacks, etc.)
        if self._is_excluded(request):
            return await call_next(request)

        identifier = get_rate_limit_identifier(request)
        bucket = self._matched_prefix(request) or "global"
        allowed, current_count, retry_after = await self._check_rate_limit(identifier, bucket)

        if not allowed:
            self.logger.warning(
                f"Rate limit exceeded for '{identifier}': "
                f"{current_count}/{self.requests_per_window} in {self.window_seconds}s window "
                f"[path={request.url.path}]"
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests",
                    "error_type": "rate_limit_exceeded",
                    "limit": self.requests_per_window,
                    "window_seconds": self.window_seconds,
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_window)
        response.headers["X-RateLimit-Remaining"] = str(
            max(0, self.requests_per_window - current_count)
        )
        response.headers["X-RateLimit-Window"] = str(self.window_seconds)
        return response

    def _is_included(self, request: Request) -> bool:
        """Return True if this path matches any of the included_paths prefixes."""
        return self._matched_prefix(request) is not None

    def _matched_prefix(self, request: Request) -> Optional[str]:
        """Return the matched included_path prefix, or None if no match."""
        path = request.url.path
        for prefix in (self.included_paths or []):
            if path == prefix or path.startswith(prefix.rstrip("/") + "/"):
                return prefix
        return None

    def _is_excluded(self, request: Request) -> bool:
        path = request.url.path
        if path in self.excluded_paths:
            return True
        for excluded in self.excluded_paths:
            if excluded != "/" and path.startswith(excluded):
                return True
        return False

    async def _check_rate_limit(self, identifier: str, bucket: str = "global") -> tuple[bool, int, int]:
        """
        Increment the Redis counter atomically and return (allowed, current_count, retry_after).

        Redis key format: rate_limit:{identifier}:{bucket}
        All sub-paths under the same included_path share one bucket.

        Uses a Redis pipeline to set INCR and EXPIRE atomically on first request,
        preventing keys with no TTL from accumulating if the process crashes between
        the two calls.

        Fails open if Redis is unavailable so rate-limit issues never take down the API.
        """
        import asyncio

        safe_bucket = bucket.strip("/").replace("/", "_").replace("-", "_") or "global"
        redis_key = f"rate_limit:{identifier}:{safe_bucket}"

        try:
            from src.providers.cache.redis_client import get_redis_client

            client = get_redis_client()
            if not client.is_initialized():
                self.logger.warning("Redis not initialised — skipping rate limit check (fail-open)")
                return True, 0, 0

            # Run blocking Redis calls in a thread to avoid blocking the async event loop
            loop = asyncio.get_event_loop()

            def _redis_op():
                pipe = client.client.pipeline()
                pipe.incr(redis_key)
                # Always set expire — if key already exists with a TTL this is a no-op;
                # if TTL was lost (crash between INCR and EXPIRE), this repairs it.
                # nx=True: only set TTL if the key has no expiry (requires Redis 7.0+)
                pipe.expire(redis_key, self.window_seconds, nx=True)
                pipe.ttl(redis_key)
                results = pipe.execute()
                count = results[0]
                ttl = results[2]
                return count, ttl

            count, ttl = await loop.run_in_executor(None, _redis_op)
            retry_after = max(ttl, 1) if ttl and ttl > 0 else self.window_seconds

            if count > self.requests_per_window:
                return False, count, retry_after

            return True, count, retry_after

        except Exception as exc:
            self.logger.warning(f"Rate limit check failed (fail-open): {exc}")
            return True, 0, 0
