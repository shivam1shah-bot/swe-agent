"""
Unit tests for Discover service-to-service authentication.

Tests the HTTP Basic Authentication pattern for Vyom <> Discover communication.
"""

from typing import Any, Dict
from unittest.mock import MagicMock, Mock, patch

import jwt
import pytest
from fastapi import Request

pytest.importorskip("pytest_asyncio")


class TestGetServiceCredentials:
    """Tests for _get_service_credentials function."""

    def test_get_credentials_from_config(self):
        """Should extract service credentials from config."""
        from src.api.routers.discover import _get_service_credentials
        
        mock_request = MagicMock()
        mock_request.app.state.config = {
            "auth": {
                "users": {
                    "discover_service": "service_password_123"
                }
            }
        }
        
        username, password = _get_service_credentials(mock_request)
        
        assert username == "discover_service"
        assert password == "service_password_123"

    def test_get_credentials_missing_password(self):
        """Should return empty password when not configured."""
        from src.api.routers.discover import _get_service_credentials
        
        mock_request = MagicMock()
        mock_request.app.state.config = {
            "auth": {
                "users": {}
            }
        }
        
        username, password = _get_service_credentials(mock_request)
        
        assert username == "discover_service"
        assert password == ""

    def test_get_credentials_missing_auth_section(self):
        """Should handle missing auth section gracefully."""
        from src.api.routers.discover import _get_service_credentials
        
        mock_request = MagicMock()
        mock_request.app.state.config = {}
        
        username, password = _get_service_credentials(mock_request)
        
        assert username == "discover_service"
        assert password == ""


class TestCreateBasicAuthHeader:
    """Tests for _create_basic_auth_header function."""

    def test_create_basic_auth_header(self):
        """Should create valid Basic Auth header."""
        from src.api.routers.discover import _create_basic_auth_header
        
        header = _create_basic_auth_header("discover_service", "password123")
        
        assert header.startswith("Basic ")
        # Decode and verify
        encoded = header.split(" ")[1]
        decoded = __import__("base64").b64decode(encoded).decode()
        assert decoded == "discover_service:password123"

    def test_create_basic_auth_header_special_chars(self):
        """Should handle special characters in credentials."""
        from src.api.routers.discover import _create_basic_auth_header
        
        header = _create_basic_auth_header("user", "pass:word@123!")
        
        encoded = header.split(" ")[1]
        decoded = __import__("base64").b64decode(encoded).decode()
        assert decoded == "user:pass:word@123!"


class TestVerifyVyomToken:
    """Tests for _verify_vyom_token function."""

    def test_verify_valid_token(self):
        """Successfully verify a valid JWT token."""
        import time
        from src.api.routers.discover import _verify_vyom_token
        
        secret = "test_secret"
        payload = {"email": "test@example.com", "sub": "user123", "exp": time.time() + 3600}
        token = jwt.encode(payload, secret, algorithm="HS256")
        
        result = _verify_vyom_token(token, secret)
        
        assert result is not None
        assert result["email"] == "test@example.com"
        assert result["sub"] == "user123"

    def test_verify_expired_token(self):
        """Expired token should return None."""
        import time
        from src.api.routers.discover import _verify_vyom_token
        
        secret = "test_secret"
        payload = {"email": "test@example.com", "exp": time.time() - 3600}  # Expired
        token = jwt.encode(payload, secret, algorithm="HS256")
        
        result = _verify_vyom_token(token, secret)
        
        assert result is None

    def test_verify_invalid_signature(self):
        """Token with wrong signature should return None."""
        import time
        from src.api.routers.discover import _verify_vyom_token
        
        secret = "test_secret"
        wrong_secret = "wrong_secret"
        payload = {"email": "test@example.com", "exp": time.time() + 3600}
        token = jwt.encode(payload, wrong_secret, algorithm="HS256")
        
        result = _verify_vyom_token(token, secret)
        
        assert result is None

    def test_verify_malformed_token(self):
        """Malformed token should return None."""
        from src.api.routers.discover import _verify_vyom_token
        
        result = _verify_vyom_token("not_a_valid_token", "secret")
        
        assert result is None


class TestPrepareDiscoverHeaders:
    """Tests for _prepare_discover_headers function."""

    @pytest.mark.asyncio
    async def test_basic_auth_header_added(self):
        """Should add Basic Auth header with service credentials."""
        from src.api.routers.discover import _prepare_discover_headers
        
        mock_request = MagicMock()
        mock_request.app.state.config = {
            "auth": {
                "users": {
                    "discover_service": "service_pass"
                }
            },
            "google_oauth": {
                "jwt_secret": ""
            }
        }
        
        result = await _prepare_discover_headers(None, mock_request)
        
        assert "Authorization" in result
        assert result["Authorization"].startswith("Basic ")
        assert result["Accept"] == "application/json"
        assert result["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_user_context_forwarded(self):
        """Should forward user email via X-User-Email header when valid token provided."""
        import time
        from src.api.routers.discover import _prepare_discover_headers
        
        secret = "vyom_secret"
        payload = {"email": "user@razorpay.com", "exp": time.time() + 3600}
        vyom_token = jwt.encode(payload, secret, algorithm="HS256")
        
        mock_request = MagicMock()
        mock_request.app.state.config = {
            "auth": {
                "users": {
                    "discover_service": "service_pass"
                }
            },
            "google_oauth": {
                "jwt_secret": secret
            }
        }
        
        result = await _prepare_discover_headers(f"Bearer {vyom_token}", mock_request)
        
        assert "X-User-Email" in result
        assert result["X-User-Email"] == "user@razorpay.com"
        assert result["Authorization"].startswith("Basic ")

    @pytest.mark.asyncio
    async def test_invalid_user_token_no_context(self):
        """Should not add X-User-Email when user token is invalid."""
        from src.api.routers.discover import _prepare_discover_headers
        
        mock_request = MagicMock()
        mock_request.app.state.config = {
            "auth": {
                "users": {
                    "discover_service": "service_pass"
                }
            },
            "google_oauth": {
                "jwt_secret": "vyom_secret"
            }
        }
        
        result = await _prepare_discover_headers("Bearer invalid_token", mock_request)
        
        # Should have Basic Auth but no user context
        assert "Authorization" in result
        assert "X-User-Email" not in result

    @pytest.mark.asyncio
    async def test_no_credentials_warning(self):
        """Should still work but log warning when service credentials not configured."""
        from src.api.routers.discover import _prepare_discover_headers
        
        mock_request = MagicMock()
        mock_request.app.state.config = {
            "auth": {
                "users": {}
            },
            "google_oauth": {
                "jwt_secret": ""
            }
        }
        
        result = await _prepare_discover_headers(None, mock_request)
        
        # Should still return headers but without Authorization
        assert "Authorization" not in result
        assert result["Accept"] == "application/json"


class TestGetBackendUrl:
    """Tests for _get_backend_url function."""

    def test_get_backend_url(self):
        """Should extract backend URL from config."""
        from src.api.routers.discover import _get_backend_url
        
        mock_request = MagicMock()
        mock_request.app.state.config = {
            "discover": {"backend_url": "https://discover-api.example.com"}
        }
        
        result = _get_backend_url(mock_request)
        
        assert result == "https://discover-api.example.com"

    def test_get_backend_url_default(self):
        """Should return default when not configured."""
        from src.api.routers.discover import _get_backend_url
        
        mock_request = MagicMock()
        mock_request.app.state.config = {"discover": {}}
        
        result = _get_backend_url(mock_request)
        
        assert result == "http://localhost:8080"


class TestGetVyomJwtSecret:
    """Tests for _get_vyom_jwt_secret function."""

    def test_get_secret_from_config(self):
        """Should extract JWT secret from config."""
        from src.api.routers.discover import _get_vyom_jwt_secret
        
        mock_request = MagicMock()
        mock_request.app.state.config = {
            "google_oauth": {"jwt_secret": "vyom_secret_key"}
        }
        
        result = _get_vyom_jwt_secret(mock_request)
        
        assert result == "vyom_secret_key"

    def test_get_secret_missing_config(self):
        """Should return empty string when not configured."""
        from src.api.routers.discover import _get_vyom_jwt_secret
        
        mock_request = MagicMock()
        mock_request.app.state.config = {}
        
        result = _get_vyom_jwt_secret(mock_request)
        
        assert result == ""


class TestErrorHandlers:
    """Tests for error handling functions."""

    def test_handle_http_error_401(self):
        """Should raise HTTPException with 401 status."""
        import httpx
        from src.api.routers.discover import _handle_discover_http_error
        
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        
        mock_error = httpx.HTTPStatusError(
            "401 Unauthorized",
            request=MagicMock(),
            response=mock_response
        )
        
        with pytest.raises(Exception) as exc_info:
            _handle_discover_http_error(mock_error, "test operation")
        
        assert exc_info.value.status_code == 401
        assert "Authentication failed" in exc_info.value.detail

    def test_handle_http_error_other(self):
        """Should raise HTTPException with original status code."""
        import httpx
        from src.api.routers.discover import _handle_discover_http_error
        
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server Error"
        
        mock_error = httpx.HTTPStatusError(
            "500 Server Error",
            request=MagicMock(),
            response=mock_response
        )
        
        with pytest.raises(Exception) as exc_info:
            _handle_discover_http_error(mock_error, "test operation")
        
        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Server Error"

    def test_handle_backend_error(self):
        """Should raise HTTPException with 503 status."""
        from src.api.routers.discover import _handle_discover_backend_error
        
        with pytest.raises(Exception) as exc_info:
            _handle_discover_backend_error(Exception("Connection failed"), "test operation")
        
        assert exc_info.value.status_code == 503
        assert "Discover backend unavailable" in exc_info.value.detail


class TestIntegrationPatterns:
    """Integration pattern tests for the service-to-service auth flow."""

    @pytest.mark.asyncio
    async def test_full_auth_flow_with_user_context(self):
        """Complete flow: service auth + user context forwarding."""
        import time
        from src.api.routers.discover import (
            _get_service_credentials,
            _create_basic_auth_header,
            _verify_vyom_token,
            _prepare_discover_headers
        )
        
        # Setup
        vyom_secret = "vyom_secret_key"
        service_pass = "discover_service_pass"
        
        mock_request = MagicMock()
        mock_request.app.state.config = {
            "auth": {
                "users": {
                    "discover_service": service_pass
                }
            },
            "google_oauth": {
                "jwt_secret": vyom_secret
            }
        }
        
        # Create user token
        user_payload = {"email": "developer@razorpay.com", "exp": time.time() + 3600}
        user_token = jwt.encode(user_payload, vyom_secret, algorithm="HS256")
        
        # Execute flow
        username, password = _get_service_credentials(mock_request)
        basic_auth = _create_basic_auth_header(username, password)
        user_info = _verify_vyom_token(user_token, vyom_secret)
        headers = await _prepare_discover_headers(f"Bearer {user_token}", mock_request)
        
        # Verify
        assert basic_auth.startswith("Basic ")
        assert user_info["email"] == "developer@razorpay.com"
        assert headers["Authorization"] == basic_auth
        assert headers["X-User-Email"] == "developer@razorpay.com"

    @pytest.mark.asyncio
    async def test_service_only_auth_flow(self):
        """Service-to-service only without user context."""
        from src.api.routers.discover import (
            _get_service_credentials,
            _create_basic_auth_header,
            _prepare_discover_headers
        )
        
        mock_request = MagicMock()
        mock_request.app.state.config = {
            "auth": {
                "users": {
                    "discover_service": "service_password"
                }
            },
            "google_oauth": {
                "jwt_secret": ""
            }
        }
        
        # Execute flow without user auth
        username, password = _get_service_credentials(mock_request)
        basic_auth = _create_basic_auth_header(username, password)
        headers = await _prepare_discover_headers(None, mock_request)
        
        # Verify
        assert basic_auth.startswith("Basic ")
        assert headers["Authorization"] == basic_auth
        assert "X-User-Email" not in headers


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
