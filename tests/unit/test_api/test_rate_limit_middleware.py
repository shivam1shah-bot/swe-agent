"""
Unit tests for RateLimitMiddleware.

Tests per-user rate limiting, Redis counter logic, identifier resolution,
excluded paths, fail-open behaviour, and response headers.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.api.middleware.rate_limit import RateLimitMiddleware, get_rate_limit_identifier


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app(
    requests_per_window: int = 5,
    window_seconds: int = 60,
    enabled: bool = True,
) -> FastAPI:
    """Create a minimal FastAPI app wrapped with RateLimitMiddleware."""
    app = FastAPI()

    @app.post("/api/v1/agents/run")
    async def run_agent():
        return {"ok": True}

    @app.get("/api/v1/health")
    async def health():
        return {"status": "healthy"}

    app.add_middleware(
        RateLimitMiddleware,
        requests_per_window=requests_per_window,
        window_seconds=window_seconds,
        enabled=enabled,
        included_paths=["/api/v1/agents"],
    )
    return app


def _make_redis_mock(count: int = 1, ttl: int = 55) -> MagicMock:
    """Return a mock RedisClient whose .client supports pipeline / INCR / EXPIRE / TTL."""
    mock_redis_client = MagicMock()
    mock_redis_client.is_initialized.return_value = True
    mock_redis_client.client = MagicMock()

    # Pipeline mock: pipeline().incr().expire().ttl().execute() → [count, True, ttl]
    mock_pipe = MagicMock()
    mock_pipe.execute.return_value = [count, True, ttl]
    mock_redis_client.client.pipeline.return_value = mock_pipe

    # Direct calls kept for backward compatibility with tests that patch them
    mock_redis_client.client.incr.return_value = count
    mock_redis_client.client.expire.return_value = True
    mock_redis_client.client.ttl.return_value = ttl
    return mock_redis_client


# ---------------------------------------------------------------------------
# _get_identifier
# ---------------------------------------------------------------------------

class TestGetIdentifier:
    """Tests for identifier resolution (user vs IP fallback)."""

    def _middleware(self) -> RateLimitMiddleware:
        app = FastAPI()
        mw = RateLimitMiddleware(app)
        return mw

    def _make_request(self, user_info=None, ip="1.2.3.4", forwarded_for=None):
        req = MagicMock(spec=Request)
        req.state = MagicMock()
        req.state.current_user = user_info
        req.client = MagicMock()
        req.client.host = ip
        headers = {}
        if forwarded_for:
            headers["X-Forwarded-For"] = forwarded_for
        req.headers = headers
        return req

    def test_uses_username_for_basic_auth_user(self):
        mw = self._middleware()
        req = self._make_request(user_info={"username": "admin", "role": "admin"})
        assert get_rate_limit_identifier(req) == "user:admin"

    def test_uses_email_for_jwt_user(self):
        mw = self._middleware()
        req = self._make_request(user_info={"email": "dev@example.com", "role": "user"})
        assert get_rate_limit_identifier(req) == "user:dev@example.com"

    def test_prefers_username_over_email(self):
        mw = self._middleware()
        req = self._make_request(
            user_info={"username": "admin", "email": "admin@example.com"}
        )
        assert get_rate_limit_identifier(req) == "user:admin"

    def test_falls_back_to_ip_when_no_user(self):
        mw = self._middleware()
        req = self._make_request(user_info=None, ip="10.0.0.1")
        assert get_rate_limit_identifier(req) == "ip:10.0.0.1"

    def test_falls_back_to_ip_when_user_has_no_identity(self):
        mw = self._middleware()
        req = self._make_request(user_info={"role": "user"}, ip="10.0.0.2")
        assert get_rate_limit_identifier(req) == "ip:10.0.0.2"

    def test_ignores_x_forwarded_for_uses_tcp_peer_ip(self):
        """X-Forwarded-For must be ignored to prevent rate-limit bypass via spoofing."""
        req = self._make_request(
            user_info=None,
            ip="10.0.0.1",
            forwarded_for="203.0.113.5, 10.0.0.1, 192.168.1.1",
        )
        # Must use TCP peer IP (10.0.0.1), not the X-Forwarded-For value
        assert get_rate_limit_identifier(req) == "ip:10.0.0.1"


# ---------------------------------------------------------------------------
# _is_excluded
# ---------------------------------------------------------------------------

class TestIsExcluded:
    def _middleware(self) -> RateLimitMiddleware:
        return RateLimitMiddleware(FastAPI())

    def _req(self, path: str, method: str = "GET") -> MagicMock:
        req = MagicMock(spec=Request)
        req.url = MagicMock()
        req.url.path = path
        req.method = method
        return req

    def test_health_path_excluded(self):
        assert self._middleware()._is_excluded(self._req("/api/v1/health")) is True

    def test_health_subpath_excluded(self):
        assert self._middleware()._is_excluded(self._req("/api/v1/health/detailed")) is True

    def test_docs_excluded(self):
        assert self._middleware()._is_excluded(self._req("/docs")) is True

    def test_metrics_excluded(self):
        assert self._middleware()._is_excluded(self._req("/metrics")) is True

    def test_api_tasks_not_excluded(self):
        assert self._middleware()._is_excluded(self._req("/api/v1/tasks")) is False

    def test_root_path_excluded(self):
        assert self._middleware()._is_excluded(self._req("/")) is True

    def test_auth_login_excluded(self):
        assert self._middleware()._is_excluded(self._req("/api/v1/auth/login")) is True

    def test_slack_excluded(self):
        # Note: _is_excluded is only reached when included_paths is None or path matches.
        # With included_paths set (agent-only mode), slack is never even checked.
        assert self._middleware()._is_excluded(self._req("/api/v1/slack")) is True

    def test_slack_subpath_excluded(self):
        assert self._middleware()._is_excluded(self._req("/api/v1/slack/events")) is True

    def test_claude_plugins_metrics_excluded(self):
        assert self._middleware()._is_excluded(self._req("/api/v1/external_metrics/claude_plugins")) is True

    def test_pr_review_webhook_excluded(self):
        assert self._middleware()._is_excluded(self._req("/api/v1/pr-review/webhook")) is True

    def test_pr_review_non_webhook_not_excluded(self):
        # /api/v1/pr-review (non-webhook) is user-facing and should be rate-limited
        assert self._middleware()._is_excluded(self._req("/api/v1/pr-review")) is False


# ---------------------------------------------------------------------------
# _is_included — agent-only scope
# ---------------------------------------------------------------------------

class TestIsIncluded:
    AGENT_PATHS = [
        "/api/v1/agents",
        "/api/v1/agents-catalogue",
        "/api/v1/agent-skills",
        "/api/v1/knowledge-agents",
    ]

    def _middleware(self):
        app = FastAPI()
        return RateLimitMiddleware(app, included_paths=self.AGENT_PATHS)

    def _req(self, path):
        req = MagicMock(spec=Request)
        req.url = MagicMock()
        req.url.path = path
        return req

    def test_agent_root_included(self):
        assert self._middleware()._is_included(self._req("/api/v1/agents")) is True

    def test_agent_subpath_included(self):
        assert self._middleware()._is_included(self._req("/api/v1/agents/list")) is True

    def test_agents_catalogue_included(self):
        assert self._middleware()._is_included(self._req("/api/v1/agents-catalogue/items")) is True

    def test_agent_skills_included(self):
        assert self._middleware()._is_included(self._req("/api/v1/agent-skills")) is True

    def test_knowledge_agents_included(self):
        assert self._middleware()._is_included(self._req("/api/v1/knowledge-agents/query")) is True

    def test_tasks_not_included(self):
        assert self._middleware()._is_included(self._req("/api/v1/tasks")) is False

    def test_health_not_included(self):
        assert self._middleware()._is_included(self._req("/api/v1/health")) is False

    def test_slack_not_included(self):
        assert self._middleware()._is_included(self._req("/api/v1/slack")) is False

    def test_non_agent_path_not_rate_limited_in_dispatch(self):
        """When included_paths is set, paths outside the list pass through with no rate-limit headers.
        GET requests are always exempt; POST to a non-included path is also never rate-limited.
        """
        agent_app = FastAPI()

        @agent_app.post("/api/v1/tasks")
        async def tasks():
            return {"ok": True}

        agent_app.add_middleware(
            RateLimitMiddleware,
            requests_per_window=5,
            included_paths=["/api/v1/agents"],  # /api/v1/tasks is NOT in scope
        )
        mock_redis = _make_redis_mock(count=1)
        with patch("src.providers.cache.redis_client.get_redis_client", return_value=mock_redis):
            from fastapi.testclient import TestClient
            client = TestClient(agent_app)
            resp = client.post("/api/v1/tasks")  # non-agent POST → not rate-limited

        assert resp.status_code == 200
        assert "X-RateLimit-Limit" not in resp.headers
        mock_redis.client.incr.assert_not_called()


# ---------------------------------------------------------------------------
# dispatch — allowed requests
# ---------------------------------------------------------------------------

class TestDispatchAllowed:
    """Requests under the limit should pass through with rate-limit headers."""

    def test_request_under_limit_gets_200(self):
        app = _make_app(requests_per_window=5)
        mock_redis = _make_redis_mock(count=1)

        with patch(
            "src.providers.cache.redis_client.get_redis_client",
            return_value=mock_redis,
        ):
            client = TestClient(app)
            resp = client.post(
                "/api/v1/agents/run",
                headers={"Authorization": "Bearer fake"},
            )

        assert resp.status_code == 200

    def test_rate_limit_headers_present(self):
        app = _make_app(requests_per_window=10)
        mock_redis = _make_redis_mock(count=3, ttl=45)

        with patch(
            "src.providers.cache.redis_client.get_redis_client",
            return_value=mock_redis,
        ):
            client = TestClient(app)
            resp = client.post("/api/v1/agents/run")

        assert resp.headers["X-RateLimit-Limit"] == "10"
        assert resp.headers["X-RateLimit-Remaining"] == "7"  # 10 - 3
        assert resp.headers["X-RateLimit-Window"] == "60"

    def test_excluded_path_has_no_rate_limit_headers(self):
        app = _make_app()
        mock_redis = _make_redis_mock()

        with patch(
            "src.providers.cache.redis_client.get_redis_client",
            return_value=mock_redis,
        ):
            client = TestClient(app)
            resp = client.get("/api/v1/health")

        assert resp.status_code == 200
        assert "X-RateLimit-Limit" not in resp.headers

    def test_options_request_skipped(self):
        app = _make_app()
        mock_redis = _make_redis_mock()

        with patch(
            "src.providers.cache.redis_client.get_redis_client",
            return_value=mock_redis,
        ):
            client = TestClient(app)
            resp = client.options("/api/v1/tasks")

        # OPTIONS should never be rate-limited; Redis INCR must not be called
        mock_redis.client.incr.assert_not_called()


# ---------------------------------------------------------------------------
# dispatch — limit exceeded
# ---------------------------------------------------------------------------

class TestDispatchLimitExceeded:
    def test_returns_429_when_limit_exceeded(self):
        app = _make_app(requests_per_window=5)
        mock_redis = _make_redis_mock(count=6, ttl=30)  # count > limit

        with patch(
            "src.providers.cache.redis_client.get_redis_client",
            return_value=mock_redis,
        ):
            client = TestClient(app)
            resp = client.post("/api/v1/agents/run")

        assert resp.status_code == 429
        body = resp.json()
        assert body["error_type"] == "rate_limit_exceeded"
        assert body["limit"] == 5
        assert body["retry_after"] == 30

    def test_retry_after_header_set(self):
        app = _make_app(requests_per_window=5)
        mock_redis = _make_redis_mock(count=6, ttl=20)

        with patch(
            "src.providers.cache.redis_client.get_redis_client",
            return_value=mock_redis,
        ):
            client = TestClient(app)
            resp = client.post("/api/v1/agents/run")

        assert resp.headers["Retry-After"] == "20"

    def test_redis_expire_uses_nx_flag_for_first_request_only(self):
        """EXPIRE is always queued in the pipeline, but nx=True delegates
        'only set on first request' semantics to Redis itself (requires Redis 7.0+)."""
        app = _make_app(requests_per_window=10)
        mock_redis = _make_redis_mock(count=2)  # existing key

        with patch(
            "src.providers.cache.redis_client.get_redis_client",
            return_value=mock_redis,
        ):
            client = TestClient(app)
            client.post("/api/v1/agents/run")

        pipe = mock_redis.client.pipeline.return_value
        pipe.expire.assert_called_once()
        assert pipe.expire.call_args[1].get("nx") is True

    def test_redis_expire_set_on_first_request(self):
        app = _make_app(requests_per_window=10)
        mock_redis = _make_redis_mock(count=1)  # new key

        with patch(
            "src.providers.cache.redis_client.get_redis_client",
            return_value=mock_redis,
        ):
            client = TestClient(app)
            client.post("/api/v1/agents/run")

        # With pipeline, expire is called on the pipe, not client directly
        pipe = mock_redis.client.pipeline.return_value
        pipe.expire.assert_called_once()
        assert pipe.expire.call_args[0][1] == 60


# ---------------------------------------------------------------------------
# dispatch — disabled middleware
# ---------------------------------------------------------------------------

class TestDispatchDisabled:
    def test_disabled_middleware_allows_all(self):
        app = _make_app(enabled=False)
        mock_redis = _make_redis_mock()

        with patch(
            "src.providers.cache.redis_client.get_redis_client",
            return_value=mock_redis,
        ):
            client = TestClient(app)
            resp = client.post("/api/v1/agents/run")

        assert resp.status_code == 200
        mock_redis.client.incr.assert_not_called()


# ---------------------------------------------------------------------------
# dispatch — Redis unavailable (fail-open)
# ---------------------------------------------------------------------------

class TestFailOpen:
    def test_passes_request_when_redis_not_initialised(self):
        app = _make_app(requests_per_window=5)
        mock_redis = MagicMock()
        mock_redis.is_initialized.return_value = False

        with patch(
            "src.providers.cache.redis_client.get_redis_client",
            return_value=mock_redis,
        ):
            client = TestClient(app)
            resp = client.post("/api/v1/agents/run")

        assert resp.status_code == 200

    def test_passes_request_when_redis_raises(self):
        app = _make_app(requests_per_window=5)

        with patch(
            "src.providers.cache.redis_client.get_redis_client",
            side_effect=Exception("Redis connection refused"),
        ):
            client = TestClient(app)
            resp = client.post("/api/v1/agents/run")

        assert resp.status_code == 200

    def test_passes_request_when_incr_raises(self):
        app = _make_app(requests_per_window=5)
        mock_redis = MagicMock()
        mock_redis.is_initialized.return_value = True
        mock_redis.client.incr.side_effect = Exception("INCR failed")

        with patch(
            "src.providers.cache.redis_client.get_redis_client",
            return_value=mock_redis,
        ):
            client = TestClient(app)
            resp = client.post("/api/v1/agents/run")

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Redis key format
# ---------------------------------------------------------------------------

class TestRedisKeyFormat:
    def test_redis_key_uses_username(self):
        """Ensure the Redis key includes the resolved identifier."""
        from starlette.middleware.base import BaseHTTPMiddleware

        app = FastAPI()

        @app.post("/api/v1/agents/run")
        async def run_agent():
            return {"ok": True}

        # RateLimitMiddleware must be added first (innermost) so it runs AFTER auth
        app.add_middleware(RateLimitMiddleware, requests_per_window=10,
                           included_paths=["/api/v1/agents"])

        # User injection added second → becomes outermost → runs first, setting user info
        class InjectUserMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next):
                request.state.current_user = {"username": "dashboard", "role": "user"}
                return await call_next(request)

        app.add_middleware(InjectUserMiddleware)

        mock_redis = _make_redis_mock(count=1)
        with patch(
            "src.providers.cache.redis_client.get_redis_client",
            return_value=mock_redis,
        ):
            client = TestClient(app)
            client.post("/api/v1/agents/run")

        # With pipeline, the key is passed to pipe.incr(), not client.incr()
        # The bucket for included_path="/api/v1/agents" → "api_v1_agents"
        pipe = mock_redis.client.pipeline.return_value
        incr_key = pipe.incr.call_args[0][0]
        assert incr_key == "rate_limit:user:dashboard:api_v1_agents"

    def test_redis_key_uses_ip_fallback(self):
        app = _make_app(requests_per_window=10)
        mock_redis = _make_redis_mock(count=1)

        with patch(
            "src.providers.cache.redis_client.get_redis_client",
            return_value=mock_redis,
        ):
            client = TestClient(app)
            client.post("/api/v1/agents/run")

        pipe = mock_redis.client.pipeline.return_value
        incr_key = pipe.incr.call_args[0][0]
        assert incr_key.startswith("rate_limit:ip:")
