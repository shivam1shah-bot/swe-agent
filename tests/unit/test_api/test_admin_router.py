"""
Unit tests for admin router endpoints.

Tests the FastAPI admin router functions and dependencies.
"""

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi import HTTPException, status, Request
import time

# Test imports
from src.api.routers.admin import (
    router,
    get_database_provider
)
from src.providers.database.provider import DatabaseProvider


@pytest.fixture
def mock_database_provider():
    """Mock database provider for testing."""
    provider = MagicMock(spec=DatabaseProvider)
    return provider


@pytest.fixture
def mock_app_state(mock_database_provider):
    """Mock FastAPI app state."""
    mock_state = MagicMock()
    mock_state.database_provider = mock_database_provider
    return mock_state


@pytest.fixture
def mock_request(mock_app_state):
    """Mock FastAPI request with app state."""
    mock_request = MagicMock()
    mock_request.app.state = mock_app_state
    return mock_request


@pytest.fixture
def authenticated_mock_request():
    """Create a proper FastAPI Request mock with authentication."""
    mock_request = MagicMock(spec=Request)
    
    # Mock the request state with authenticated user
    mock_request.state = MagicMock()
    mock_request.state.current_user = {
        'username': 'admin',  # Must be exactly 'admin' for admin role
        'roles': ['admin'],
        'authenticated': True
    }
    
    return mock_request


class TestAdminRouterDependencies:
    """Test admin router dependencies."""
    
    def test_get_database_provider_success(self, mock_request, mock_app_state):
        """Test successful database provider retrieval."""
        # Arrange
        expected_provider = mock_app_state.database_provider
        
        # Act
        result = get_database_provider(mock_request)
        
        # Assert
        assert result == expected_provider
    
    def test_get_database_provider_not_initialized(self, mock_request):
        """Test database provider not initialized error."""
        # Arrange
        mock_request.app.state.database_provider = None
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            get_database_provider(mock_request)
        
        assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "Database provider not initialized" in str(exc_info.value.detail)
    
    def test_get_database_provider_attribute_error(self, mock_request):
        """Test database provider attribute error."""
        # Arrange
        del mock_request.app.state.database_provider
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            get_database_provider(mock_request)
        
        assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "Database provider not available" in str(exc_info.value.detail)


class TestAdminInfoEndpoint:
    """Test admin info endpoint function."""
    
    @pytest.mark.asyncio
    async def test_get_admin_info_response_structure(self, authenticated_mock_request):
        """Test admin info endpoint response structure."""
        # Arrange
        from src.api.routers.admin import get_admin_info
        
        # Act
        result = await get_admin_info(authenticated_mock_request)
        
        # Assert
        assert "admin_endpoints" in result
        assert "timestamp" in result
        assert isinstance(result["timestamp"], float)
        
        endpoints = result["admin_endpoints"]
        assert isinstance(endpoints, dict)
        
        # Verify that endpoints have proper structure
        for endpoint_name, endpoint_info in endpoints.items():
            assert "method" in endpoint_info
            assert "path" in endpoint_info  
            assert "description" in endpoint_info
            assert isinstance(endpoint_info["method"], str)
            assert isinstance(endpoint_info["path"], str)
            assert isinstance(endpoint_info["description"], str) 