"""
Unit tests for MCP API client.
"""

import pytest
import base64
from unittest.mock import Mock, patch
from src.mcp_server.clients.api_client import SWEAgentAPIClient
from src.mcp_server.config.settings import MCPSettings


@pytest.mark.unit
class TestSWEAgentAPIClient:
    """Test cases for SWEAgentAPIClient."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Mock settings for testing
        self.mock_settings = Mock(spec=MCPSettings)
        self.mock_settings.api_base_url = "http://localhost:8002"
        self.mock_settings.api_timeout = 30.0
        self.mock_settings.auth_enabled = True
        self.mock_settings.auth_username = "mcp_read_user"
        self.mock_settings.auth_password = "test_password_123"
    
    def test_api_client_initialization_with_auth(self):
        """Test API client initialization includes authentication headers when auth is enabled."""
        client = SWEAgentAPIClient(self.mock_settings)
        
        # Verify client is created
        assert client is not None
        assert client.base_url == "http://localhost:8002"
        
        # Verify authentication header is added
        headers = client.client.headers
        assert "Authorization" in headers
        
        # Verify Basic Auth format
        auth_header = headers["Authorization"]
        assert auth_header.startswith("Basic ")
        
        # Decode and verify credentials
        encoded_credentials = auth_header[6:]  # Remove "Basic "
        decoded_credentials = base64.b64decode(encoded_credentials).decode('utf-8')
        expected_credentials = "mcp_read_user:test_password_123"
        assert decoded_credentials == expected_credentials
    
    def test_api_client_initialization_without_auth(self):
        """Test API client initialization without authentication when auth is disabled."""
        self.mock_settings.auth_enabled = False
        
        client = SWEAgentAPIClient(self.mock_settings)
        
        # Verify client is created
        assert client is not None
        
        # Verify no authentication header is added
        headers = client.client.headers
        assert "Authorization" not in headers
    
    def test_api_client_initialization_no_password(self):
        """Test API client initialization when auth is enabled but no password configured."""
        self.mock_settings.auth_enabled = True
        self.mock_settings.auth_password = ""
        
        client = SWEAgentAPIClient(self.mock_settings)
        
        # Verify client is created
        assert client is not None
        
        # Verify no authentication header is added when password is empty
        headers = client.client.headers
        assert "Authorization" not in headers
    
    def test_api_client_headers_include_required_headers(self):
        """Test that API client includes all required headers."""
        client = SWEAgentAPIClient(self.mock_settings)
        
        headers = client.client.headers
        
        # Verify required headers
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"
        assert headers["User-Agent"] == "SWE-Agent-MCP/1.0.0"
        assert headers["Origin"] == "http://localhost:28003"
        assert "Authorization" in headers  # Auth header should be present
    
    @patch('src.mcp_server.clients.api_client.get_mcp_settings')
    def test_api_client_uses_global_settings(self, mock_get_settings):
        """Test that API client uses global settings when none provided."""
        mock_get_settings.return_value = self.mock_settings
        
        client = SWEAgentAPIClient()
        
        # Verify global settings were called
        mock_get_settings.assert_called_once()
        
        # Verify client uses settings
        assert client.base_url == "http://localhost:8002" 