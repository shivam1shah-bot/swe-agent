"""
Unit tests for auth provider.
"""
import pytest
from unittest.mock import Mock, patch
from src.providers.auth.basic_auth import BasicAuthProvider
from src.providers.auth.rbac import RoleChecker


@pytest.mark.unit
class TestBasicAuthProvider:
    """Test cases for BasicAuthProvider."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Mock configuration
        self.mock_config = {
            "auth": {
                "enabled": True,
                "users": {
                    "dashboard": "dashboard123",
                    "admin": "admin123",
                    "mcp_read_user": "mcp_secure_dev_2024"
                }
            }
        }
    
    @patch('src.providers.auth.basic_auth.get_config')
    def test_get_user_role_mcp_read_user(self, mock_get_config):
        """Test get_user_role returns correct role for mcp_read_user."""
        mock_get_config.return_value = self.mock_config
        
        provider = BasicAuthProvider()
        
        # Test mcp_read_user role
        assert provider.get_user_role("mcp_read_user") == "mcp_read_user"
        
        # Test existing roles still work
        assert provider.get_user_role("admin") == "admin"
        assert provider.get_user_role("dashboard") == "dashboard"
        
        # Test unknown user
        assert provider.get_user_role("unknown") is None
    
    @patch('src.providers.auth.basic_auth.get_config')
    def test_validate_credentials_mcp_read_user(self, mock_get_config):
        """Test validate_credentials works for mcp_read_user."""
        mock_get_config.return_value = self.mock_config
        
        provider = BasicAuthProvider()
        
        # Test valid mcp_read_user credentials
        assert provider.validate_credentials("mcp_read_user", "mcp_secure_dev_2024") is True
        
        # Test invalid password
        assert provider.validate_credentials("mcp_read_user", "wrong_password") is False
        
        # Test existing users still work
        assert provider.validate_credentials("admin", "admin123") is True
        assert provider.validate_credentials("dashboard", "dashboard123") is True


@pytest.mark.unit
class TestRoleChecker:
    """Test cases for RoleChecker."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.role_checker = RoleChecker()
    
    def test_get_user_role_mcp_read_user(self):
        """Test get_user_role recognizes mcp_read_user."""
        # Test mcp_read_user
        user_info = {"username": "mcp_read_user", "role": "mcp_read_user"}
        assert self.role_checker.get_user_role(user_info) == "mcp_read_user"
        
        # Test existing roles
        admin_info = {"username": "admin", "role": "admin"}
        assert self.role_checker.get_user_role(admin_info) == "admin"
        
        dashboard_info = {"username": "dashboard", "role": "dashboard"}
        assert self.role_checker.get_user_role(dashboard_info) == "dashboard"
        
        # Test unknown user
        unknown_info = {"username": "unknown", "role": "unknown"}
        assert self.role_checker.get_user_role(unknown_info) == "unknown"
    
    def test_check_role_access_mcp_read_user(self):
        """Test check_role_access allows mcp_read_user for appropriate endpoints."""
        # Test mcp_read_user access to MCP tools
        assert self.role_checker.check_role_access("mcp_read_user", ["mcp_read_user", "admin"]) is True
        assert self.role_checker.check_role_access("mcp_read_user", ["dashboard", "admin", "mcp_read_user"]) is True
        
        # Test mcp_read_user denied for admin-only endpoints
        assert self.role_checker.check_role_access("mcp_read_user", ["admin"]) is False
        
        # Test admin still has access to everything
        assert self.role_checker.check_role_access("admin", ["mcp_read_user", "admin"]) is True
        assert self.role_checker.check_role_access("admin", ["admin"]) is True 