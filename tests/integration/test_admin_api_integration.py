"""
Integration tests for admin API endpoints.

Tests the admin migration endpoints through actual HTTP requests.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from fastapi.testclient import TestClient
import json

from src.api.api import create_app
from src.providers.database.provider import DatabaseProvider


@pytest.fixture
def mock_migration_manager():
    """Mock migration manager for integration tests."""
    manager = MagicMock()
    
    # Default migration status
    manager.get_migration_status.return_value = {
        "current_version": 2,
        "latest_version": 2,
        "applied_count": 2,
        "available_count": 2,
        "pending_count": 0,
        "up_to_date": True,
        "applied_migrations": [1, 2],
        "pending_migrations": []
    }
    
    manager.get_pending_migrations.return_value = []
    manager.get_applied_migrations.return_value = [1, 2]
    manager.run_migrations.return_value = True
    manager.rollback_to_version.return_value = True
    
    return manager


@pytest.fixture
def mock_database_provider(mock_migration_manager):
    """Mock database provider for integration tests."""
    provider = MagicMock(spec=DatabaseProvider)
    provider.get_migration_manager.return_value = mock_migration_manager
    provider.health_check.return_value = {
        "status": "healthy",
        "message": "Database connection successful"
    }
    return provider


@pytest.fixture
def app_with_mocked_db(mock_database_provider):
    """Create FastAPI app with mocked database provider."""
    app = create_app()
    
    # Mock the app state
    mock_state = MagicMock()
    mock_state.database_provider = mock_database_provider
    mock_state.cache_provider = MagicMock()
    mock_state.task_service = MagicMock()
    mock_state.agents_catalogue_service = MagicMock()
    mock_state.config = {"app": {"name": "test"}}
    
    app.state = mock_state
    
    return app


@pytest.fixture
def test_client(app_with_mocked_db):
    """Create test client with mocked dependencies."""
    return TestClient(app_with_mocked_db)


@pytest.mark.integration
class TestAdminAPIIntegration:
    """Integration tests for admin API endpoints."""
    
    def test_get_migration_status_endpoint(self, test_client, mock_migration_manager):
        """Test GET /api/v1/admin/migrations/status endpoint."""
        # Act
        response = test_client.get("/api/v1/admin/migrations/status")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        
        assert data["current_version"] == 2
        assert data["latest_version"] == 2
        assert data["up_to_date"] is True
        assert data["applied_migrations"] == [1, 2]
        assert data["pending_migrations"] == []
        
        mock_migration_manager.get_migration_status.assert_called_once()
    
    def test_run_migrations_endpoint_no_pending(self, test_client, mock_migration_manager):
        """Test POST /api/v1/admin/migrations/run with no pending migrations."""
        # Arrange
        mock_migration_manager.get_pending_migrations.return_value = []
        
        # Act
        response = test_client.post("/api/v1/admin/migrations/run")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["migrations_applied"] == 0
        assert data["total_migrations"] == 0
        assert "No pending migrations" in data["message"]
        assert "duration_ms" in data
        assert "timestamp" in data
        
        mock_migration_manager.get_pending_migrations.assert_called_once()
        mock_migration_manager.run_migrations.assert_not_called()
    
    def test_run_migrations_endpoint_with_pending(self, test_client, mock_migration_manager):
        """Test POST /api/v1/admin/migrations/run with pending migrations."""
        # Arrange
        mock_pending = [MagicMock(), MagicMock(), MagicMock()]  # 3 pending migrations
        mock_migration_manager.get_pending_migrations.return_value = mock_pending
        mock_migration_manager.run_migrations.return_value = True
        
        # Act
        response = test_client.post("/api/v1/admin/migrations/run")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["migrations_applied"] == 3
        assert data["total_migrations"] == 3
        assert "Successfully applied 3 migrations" in data["message"]
        
        mock_migration_manager.get_pending_migrations.assert_called_once()
        mock_migration_manager.run_migrations.assert_called_once()
    
    def test_run_migrations_endpoint_failure(self, test_client, mock_migration_manager):
        """Test POST /api/v1/admin/migrations/run with migration failure."""
        # Arrange
        mock_migration_manager.get_pending_migrations.return_value = [MagicMock()]
        mock_migration_manager.run_migrations.return_value = False  # Migration failed
        
        # Act
        response = test_client.post("/api/v1/admin/migrations/run")
        
        # Assert
        assert response.status_code == 500
        data = response.json()
        assert "Migration run failed" in data["detail"]
    
    def test_rollback_migrations_endpoint_success(self, test_client, mock_migration_manager):
        """Test POST /api/v1/admin/migrations/rollback/{target_version} success."""
        # Arrange
        mock_migration_manager.get_applied_migrations.return_value = [1, 2, 3, 4]
        mock_migration_manager.rollback_to_version.return_value = True
        
        target_version = 2
        
        # Act
        response = test_client.post(f"/api/v1/admin/migrations/rollback/{target_version}")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["rollback_to_version"] == 2
        assert data["migrations_rolled_back"] == 2  # Rolled back migrations 3 and 4
        assert "Successfully rolled back 2 migrations to version 2" in data["message"]
        
        mock_migration_manager.rollback_to_version.assert_called_once_with(2)
    
    def test_rollback_migrations_endpoint_no_rollback_needed(self, test_client, mock_migration_manager):
        """Test rollback when already at target version."""
        # Arrange
        mock_migration_manager.get_applied_migrations.return_value = [1, 2]
        
        target_version = 2  # Already at version 2
        
        # Act
        response = test_client.post(f"/api/v1/admin/migrations/rollback/{target_version}")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["migrations_rolled_back"] == 0
        assert "Already at or below target version 2" in data["message"]
        
        mock_migration_manager.rollback_to_version.assert_not_called()
    
    def test_rollback_migrations_endpoint_failure(self, test_client, mock_migration_manager):
        """Test rollback failure."""
        # Arrange
        mock_migration_manager.get_applied_migrations.return_value = [1, 2, 3]
        mock_migration_manager.rollback_to_version.return_value = False  # Rollback failed
        
        target_version = 1
        
        # Act
        response = test_client.post(f"/api/v1/admin/migrations/rollback/{target_version}")
        
        # Assert
        assert response.status_code == 500
        data = response.json()
        assert "Migration rollback failed" in data["detail"]
    

    
    def test_get_admin_info_endpoint(self, test_client):
        """Test GET /api/v1/admin/info endpoint."""
        # Act
        response = test_client.get("/api/v1/admin/info")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        
        assert "admin_endpoints" in data
        assert "timestamp" in data
        
        endpoints = data["admin_endpoints"]
        expected_endpoints = [
            "migration_status",
            "run_migrations", 
            "rollback_migrations"
        ]
        
        for endpoint in expected_endpoints:
            assert endpoint in endpoints
            assert "method" in endpoints[endpoint]
            assert "path" in endpoints[endpoint]
            assert "description" in endpoints[endpoint]
    
    def test_database_provider_not_available_error(self, test_client):
        """Test error when database provider is not available."""
        # Arrange - Remove database provider from app state
        test_client.app.state.database_provider = None
        
        # Act
        response = test_client.get("/api/v1/admin/migrations/status")
        
        # Assert
        assert response.status_code == 503
        data = response.json()
        assert "Database provider not initialized" in data["detail"]
    
    def test_migration_manager_error(self, test_client, mock_database_provider):
        """Test error when migration manager fails."""
        # Arrange
        mock_database_provider.get_migration_manager.side_effect = Exception("Migration manager error")
        
        # Act
        response = test_client.get("/api/v1/admin/migrations/status")
        
        # Assert
        assert response.status_code == 500
        data = response.json()
        assert "Failed to get migration status" in data["detail"]
    
    def test_admin_endpoints_content_type(self, test_client):
        """Test that admin endpoints return JSON content type."""
        endpoints_to_test = [
            "/api/v1/admin/migrations/status",
            "/api/v1/admin/info"
        ]
        
        for endpoint in endpoints_to_test:
            response = test_client.get(endpoint)
            assert response.headers["content-type"] == "application/json"
            assert response.status_code == 200
    
    def test_rollback_migrations_invalid_version(self, test_client):
        """Test rollback with invalid version parameter."""
        # Act - Test with invalid version (non-integer)
        response = test_client.post("/api/v1/admin/migrations/rollback/invalid")
        
        # Assert
        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "detail" in data
    
    def test_admin_endpoint_documentation_in_openapi(self, test_client):
        """Test that admin endpoints are properly documented in OpenAPI schema."""
        # Act
        response = test_client.get("/openapi.json")
        
        # Assert
        assert response.status_code == 200
        openapi_schema = response.json()
        
        # Check that admin endpoints are documented
        paths = openapi_schema["paths"]
        admin_paths = [path for path in paths.keys() if "/api/v1/admin/" in path]
        
        assert len(admin_paths) >= 4  # Should have at least 4 admin endpoints
        
        # Check specific endpoints
        expected_admin_paths = [
            "/api/v1/admin/migrations/status",
            "/api/v1/admin/migrations/run",
            "/api/v1/admin/migrations/rollback/{target_version}",
            "/api/v1/admin/info"
        ]
        
        for expected_path in expected_admin_paths:
            assert expected_path in paths
    
    def test_admin_endpoints_have_proper_tags(self, test_client):
        """Test that admin endpoints are tagged correctly in OpenAPI schema."""
        # Act
        response = test_client.get("/openapi.json")
        
        # Assert
        assert response.status_code == 200
        openapi_schema = response.json()
        
        # Check admin endpoints have "admin" tag
        paths = openapi_schema["paths"]
        for path, methods in paths.items():
            if "/api/v1/admin/" in path:
                for method, spec in methods.items():
                    if method != "parameters":  # Skip parameter definitions
                        assert "admin" in spec.get("tags", [])


@pytest.mark.integration
class TestAdminAPIErrorHandling:
    """Test error handling in admin API endpoints."""
    
    def test_database_connection_error(self, test_client, mock_database_provider):
        """Test handling of database connection errors."""
        # Arrange
        mock_database_provider.get_migration_manager.side_effect = Exception("Connection failed")
        
        # Act
        response = test_client.get("/api/v1/admin/migrations/status")
        
        # Assert
        assert response.status_code == 500
        data = response.json()
        assert "Failed to get migration status" in data["detail"]
    
    def test_migration_operation_timeout(self, test_client, mock_migration_manager):
        """Test handling of migration operation timeouts."""
        # Arrange
        mock_migration_manager.run_migrations.side_effect = TimeoutError("Operation timed out")
        mock_migration_manager.get_pending_migrations.return_value = [MagicMock()]
        
        # Act
        response = test_client.post("/api/v1/admin/migrations/run")
        
        # Assert
        assert response.status_code == 500
        data = response.json()
        assert "Failed to run migrations" in data["detail"] 