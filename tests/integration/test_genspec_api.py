import pytest
from unittest.mock import Mock, patch
from fastapi import status
from fastapi.testclient import TestClient
from src.api.api import app

client = TestClient(app)

@pytest.fixture
async def setup_genspec_environment():
    # Setup any necessary environment or configuration for GenSpec
    yield
    # Teardown or cleanup after tests

class TestGenSpecAPI:
    """Test class for GenSpec API endpoints."""

    @patch('src.api.routers.genspec.genspec_service')
    def test_execute_genspec_success(self, mock_genspec_service, authenticated_api_client):
        """Test successful execution of GenSpec task with valid parameters."""
        # Mock the service execution
        mock_genspec_service.execute.return_value = {
            "status": "success",
            "message": "GenSpec executed successfully"
        }

        headers = {"Authorization": "Bearer YOUR_ACCESS_TOKEN"}  # Replace with actual token
        response = authenticated_api_client.post(
            "/api/genspec/execute",
            json={"param1": "value1"},
            headers=headers
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "success"

    @patch('src.api.routers.genspec.genspec_service')
    def test_execute_genspec_service_error(self, mock_genspec_service, authenticated_api_client):
        """Test execution of GenSpec task with service error."""
        # Mock the service execution to raise an exception
        mock_genspec_service.execute.side_effect = Exception("Service error")

        headers = {"Authorization": "Bearer YOUR_ACCESS_TOKEN"}  # Replace with actual token
        response = authenticated_api_client.post(
            "/api/genspec/execute",
            json={"param1": "value1"},
            headers=headers
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Service error" in response.json()["detail"] 