"""
Shared fixtures for Discover service-to-service auth tests.
"""

import time
from unittest.mock import MagicMock

import jwt
import pytest


@pytest.fixture
def valid_vyom_token():
    """Generate a valid Vyom JWT token for testing."""
    secret = "test_vyom_secret"
    payload = {
        "email": "test@example.com",
        "sub": "user123",
        "picture": "https://example.com/pic.jpg",
        "exp": time.time() + 3600
    }
    return jwt.encode(payload, secret, algorithm="HS256"), secret


@pytest.fixture
def expired_vyom_token():
    """Generate an expired Vyom JWT token for testing."""
    secret = "test_vyom_secret"
    payload = {
        "email": "test@example.com",
        "sub": "user123",
        "exp": time.time() - 3600  # Expired 1 hour ago
    }
    return jwt.encode(payload, secret, algorithm="HS256"), secret


@pytest.fixture
def mock_request_with_service_auth():
    """Create a mock FastAPI request with service-to-service auth configured."""
    mock_request = MagicMock()
    mock_request.app.state.config = {
        "discover": {
            "backend_url": "http://discover-backend:8080",
        },
        "auth": {
            "users": {
                "discover_service": "test_service_password"
            }
        },
        "google_oauth": {
            "jwt_secret": "test_vyom_secret",
        },
    }
    return mock_request


@pytest.fixture
def mock_request_no_service_auth():
    """Create a mock request without service auth configured."""
    mock_request = MagicMock()
    mock_request.app.state.config = {
        "discover": {
            "backend_url": "http://discover-backend:8080",
        },
        "auth": {
            "users": {}
        },
        "google_oauth": {
            "jwt_secret": "test_vyom_secret",
        },
    }
    return mock_request


@pytest.fixture
def mock_request_with_user_context():
    """Create a mock request with both service auth and user JWT validation."""
    mock_request = MagicMock()
    mock_request.app.state.config = {
        "discover": {
            "backend_url": "http://discover-backend:8080",
        },
        "auth": {
            "users": {
                "discover_service": "test_service_password"
            }
        },
        "google_oauth": {
            "jwt_secret": "test_vyom_secret",
        },
    }
    return mock_request


# Clean up any remaining global state from old implementation
@pytest.fixture(autouse=True)
def cleanup_globals():
    """Clean up any global state before and after each test."""
    # Try to clear old globals if they exist (for backward compatibility)
    try:
        from src.api.routers.discover import _memory_token_cache, _rate_limit_store
        _memory_token_cache.clear()
        _rate_limit_store.clear()
    except ImportError:
        pass  # Old globals don't exist in new implementation
    
    yield
    
    # Clean up after test
    try:
        from src.api.routers.discover import _memory_token_cache, _rate_limit_store
        _memory_token_cache.clear()
        _rate_limit_store.clear()
    except ImportError:
        pass
