"""
Unit tests for tasks API pagination and ordering functionality.

Tests the new pagination parameters, ordering, and multi-status filtering
introduced to improve performance and user experience.
"""

import pytest
import base64
from unittest.mock import Mock, patch, AsyncMock
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
import json

from src.services.task_service import TaskService
from src.models.base import TaskStatus
from src.providers.logger import Logger


# Patch auth config at module level to ensure BasicAuthProvider gets it
@pytest.fixture(autouse=True, scope="module")
def mock_auth_config():
    """Mock auth config at module level to fix BasicAuthProvider initialization."""
    with patch('src.providers.auth.basic_auth.get_config') as mock_config:
        mock_config.return_value = {
            'auth': {
                'enabled': True,
                'users': {
                    'dashboard': 'dashboard123',
                    'admin': 'admin123',
                    'mcp_read_user': 'mcp_secure_dev_2024'
                }
            }
        }
        yield


class TestTasksPagination:
    """Test cases for tasks API pagination functionality."""

    @pytest.fixture
    def mock_task_service(self):
        """Create mock task service."""
        service = Mock(spec=TaskService)
        # Return complete task data with all required fields for TaskResponse
        service.list_tasks.return_value = {
            'tasks': [
                {
                    'id': '1',
                    'name': 'Test Task 1',
                    'description': 'Test description 1',
                    'status': 'running',
                    'created_at': '2025-01-31T12:00:00Z',
                    'updated_at': '2025-01-31T12:01:00Z',
                    'progress': 50,
                    'parameters': {},
                    'metadata': {},
                    'result': None
                },
                {
                    'id': '2',
                    'name': 'Test Task 2', 
                    'description': 'Test description 2',
                    'status': 'pending',
                    'created_at': '2025-01-31T11:00:00Z',
                    'updated_at': '2025-01-31T11:01:00Z',
                    'progress': 0,
                    'parameters': {},
                    'metadata': {},
                    'result': None
                }
            ],
            'count': 2
        }
        service.list_tasks_by_statuses.return_value = {
            'tasks': [
                {
                    'id': '1',
                    'name': 'Test Task 1',
                    'description': 'Test description 1',
                    'status': 'running',
                    'created_at': '2025-01-31T12:00:00Z',
                    'updated_at': '2025-01-31T12:01:00Z',
                    'progress': 50,
                    'parameters': {},
                    'metadata': {},
                    'result': None
                },
                {
                    'id': '2',
                    'name': 'Test Task 2',
                    'description': 'Test description 2', 
                    'status': 'pending',
                    'created_at': '2025-01-31T11:00:00Z',
                    'updated_at': '2025-01-31T11:01:00Z',
                    'progress': 0,
                    'parameters': {},
                    'metadata': {},
                    'result': None
                }
            ],
            'count': 2
        }
        return service

    @pytest.fixture
    def auth_headers(self):
        """Create proper authentication headers using admin credentials from default config."""
        # Using admin:admin123 from environments/env.default.toml
        credentials = base64.b64encode(b"admin:admin123").decode('ascii')
        return {"Authorization": f"Basic {credentials}"}

    def _setup_dependencies(self, authenticated_api_client, mock_task_service):
        """Helper method to set up FastAPI dependency overrides."""
        from src.api.dependencies import get_task_service, get_logger
        
        mock_logger = Mock()
        authenticated_api_client.app.dependency_overrides[get_task_service] = lambda: mock_task_service
        authenticated_api_client.app.dependency_overrides[get_logger] = lambda: mock_logger
        
        return mock_logger

    def _cleanup_dependencies(self, authenticated_api_client):
        """Helper method to clean up FastAPI dependency overrides."""
        from src.api.dependencies import get_task_service, get_logger
        
        if get_task_service in authenticated_api_client.app.dependency_overrides:
            del authenticated_api_client.app.dependency_overrides[get_task_service]
        if get_logger in authenticated_api_client.app.dependency_overrides:
            del authenticated_api_client.app.dependency_overrides[get_logger]

    def test_pagination_parameters_conversion(self, authenticated_api_client, mock_task_service, auth_headers):
        """Test that page and page_size are correctly converted to limit and offset."""
        self._setup_dependencies(authenticated_api_client, mock_task_service)
        
        try:
            response = authenticated_api_client.get("/tasks?page=2&page_size=5", headers=auth_headers)
            
            assert response.status_code == 200
            # Verify service was called with correct limit and offset
            mock_task_service.list_tasks.assert_called_once_with(
                status=None, limit=5, offset=5  # page 2, size 5 = offset 5
            )
        finally:
            self._cleanup_dependencies(authenticated_api_client)

    def test_default_pagination_values(self, authenticated_api_client, mock_task_service, auth_headers):
        """Test default pagination values when not specified."""
        self._setup_dependencies(authenticated_api_client, mock_task_service)
        
        try:
            response = authenticated_api_client.get("/tasks", headers=auth_headers)
            
            assert response.status_code == 200
            # Should use defaults: page=1, page_size=20
            mock_task_service.list_tasks.assert_called_once_with(
                status=None, limit=20, offset=0
            )
        finally:
            self._cleanup_dependencies(authenticated_api_client)

    def test_single_status_filtering(self, authenticated_api_client, mock_task_service, auth_headers):
        """Test filtering by a single status."""
        self._setup_dependencies(authenticated_api_client, mock_task_service)
        
        try:
            response = authenticated_api_client.get("/tasks?status=running&page=1&page_size=10", headers=auth_headers)
            
            assert response.status_code == 200
            # Should call list_tasks with single status
            mock_task_service.list_tasks.assert_called_once_with(
                status=TaskStatus.RUNNING, limit=10, offset=0
            )
        finally:
            self._cleanup_dependencies(authenticated_api_client)

    def test_multi_status_filtering(self, authenticated_api_client, mock_task_service, auth_headers):
        """Test filtering by multiple statuses uses efficient method."""
        self._setup_dependencies(authenticated_api_client, mock_task_service)
        
        try:
            response = authenticated_api_client.get("/tasks?status=running,pending&page=1&page_size=10", headers=auth_headers)
            
            assert response.status_code == 200
            # Should call list_tasks_by_statuses for multiple statuses
            mock_task_service.list_tasks_by_statuses.assert_called_once_with(
                [TaskStatus.RUNNING, TaskStatus.PENDING], limit=10, offset=0
            )
        finally:
            self._cleanup_dependencies(authenticated_api_client)

    def test_invalid_status_error(self, authenticated_api_client, mock_task_service, auth_headers):
        """Test error handling for invalid status values."""
        self._setup_dependencies(authenticated_api_client, mock_task_service)
        
        try:
            response = authenticated_api_client.get("/tasks?status=invalid_status", headers=auth_headers)
            
            assert response.status_code == 400
            assert "invalid_status" in response.json()["detail"]["message"]
        finally:
            self._cleanup_dependencies(authenticated_api_client)

    def test_empty_tasks_response(self, authenticated_api_client, mock_task_service, auth_headers):
        """Test handling of empty task results."""
        # Override the mock to return empty results
        mock_task_service.list_tasks.return_value = {'tasks': [], 'count': 0}
        self._setup_dependencies(authenticated_api_client, mock_task_service)
        
        try:
            response = authenticated_api_client.get("/tasks", headers=auth_headers)
            
            assert response.status_code == 200
            assert response.json() == []
        finally:
            self._cleanup_dependencies(authenticated_api_client)

    def test_service_error_propagation(self, authenticated_api_client, mock_task_service, auth_headers):
        """Test that service errors are properly propagated."""
        from src.services.exceptions import BusinessLogicError
        mock_task_service.list_tasks.side_effect = BusinessLogicError("Database error")
        self._setup_dependencies(authenticated_api_client, mock_task_service)
        
        try:
            response = authenticated_api_client.get("/tasks", headers=auth_headers)
            
            assert response.status_code == 500
        finally:
            self._cleanup_dependencies(authenticated_api_client)

    def test_pagination_edge_cases(self, authenticated_api_client, mock_task_service, auth_headers):
        """Test edge cases for pagination parameters."""
        self._setup_dependencies(authenticated_api_client, mock_task_service)
        
        try:
            # Test page_size limit
            response = authenticated_api_client.get("/tasks?page_size=200", headers=auth_headers)
            assert response.status_code == 422  # Validation error for exceeding limit
            
            # Test minimum page number
            response = authenticated_api_client.get("/tasks?page=0", headers=auth_headers)
            assert response.status_code == 422  # Validation error for page < 1
        finally:
            self._cleanup_dependencies(authenticated_api_client) 