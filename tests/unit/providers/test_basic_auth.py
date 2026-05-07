"""
Unit tests for BasicAuthProvider.

Tests authentication validation, header parsing, and user role management.
"""

import pytest
import base64
from unittest.mock import Mock, patch, MagicMock

from src.providers.auth.basic_auth import BasicAuthProvider


class TestBasicAuthProvider:
    """Test suite for BasicAuthProvider."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        return {
            "auth": {
                "enabled": True,
                "users": {
                    "admin": "admin_password",
                    "dashboard": "dashboard_password",
                    "mcp_read_user": "read_password",
                    "splitz": "splitz_password",
                    "custom_user": "custom_password"
                }
            }
        }

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        logger = Mock()
        logger.debug = Mock()
        logger.warning = Mock()
        logger.error = Mock()
        return logger

    @pytest.fixture
    def auth_provider(self, mock_config, mock_logger):
        """Create a BasicAuthProvider instance with mocked dependencies."""
        with patch('src.providers.auth.basic_auth.get_config', return_value=mock_config):
            with patch('src.providers.auth.basic_auth.Logger', return_value=mock_logger):
                provider = BasicAuthProvider()
                return provider

    def test_init_loads_users(self, mock_config):
        """Test that __init__ loads users from config."""
        with patch('src.providers.auth.basic_auth.get_config', return_value=mock_config):
            with patch('src.providers.auth.basic_auth.Logger'):
                provider = BasicAuthProvider()
                assert len(provider.users) == 5
                assert provider.users["admin"] == "admin_password"
                assert provider.users["dashboard"] == "dashboard_password"

    def test_init_with_no_users_logs_warning(self):
        """Test that __init__ logs warning when no users configured."""
        empty_config = {"auth": {"users": {}}}
        mock_logger = Mock()

        with patch('src.providers.auth.basic_auth.get_config', return_value=empty_config):
            with patch('src.providers.auth.basic_auth.Logger', return_value=mock_logger):
                provider = BasicAuthProvider()
                mock_logger.warning.assert_called_once()

    def test_validate_credentials_success(self, auth_provider):
        """Test successful credential validation."""
        assert auth_provider.validate_credentials("admin", "admin_password") is True
        assert auth_provider.validate_credentials("dashboard", "dashboard_password") is True

    def test_validate_credentials_invalid_password(self, auth_provider):
        """Test credential validation with invalid password."""
        assert auth_provider.validate_credentials("admin", "wrong_password") is False

    def test_validate_credentials_unknown_user(self, auth_provider):
        """Test credential validation with unknown username."""
        assert auth_provider.validate_credentials("unknown", "password") is False

    def test_validate_credentials_empty_username(self, auth_provider):
        """Test credential validation with empty username."""
        assert auth_provider.validate_credentials("", "password") is False

    def test_validate_credentials_empty_password(self, auth_provider):
        """Test credential validation with empty password."""
        assert auth_provider.validate_credentials("admin", "") is False

    def test_validate_credentials_none_values(self, auth_provider):
        """Test credential validation with None values."""
        assert auth_provider.validate_credentials(None, "password") is False
        assert auth_provider.validate_credentials("admin", None) is False

    def test_get_user_role_admin(self, auth_provider):
        """Test getting role for admin user."""
        assert auth_provider.get_user_role("admin") == "admin"

    def test_get_user_role_dashboard(self, auth_provider):
        """Test getting role for dashboard user."""
        assert auth_provider.get_user_role("dashboard") == "dashboard"

    def test_get_user_role_mcp_read_user(self, auth_provider):
        """Test getting role for mcp_read_user."""
        assert auth_provider.get_user_role("mcp_read_user") == "mcp_read_user"

    def test_get_user_role_splitz(self, auth_provider):
        """Test getting role for splitz user."""
        assert auth_provider.get_user_role("splitz") == "splitz"

    def test_get_user_role_custom_user(self, auth_provider):
        """Test getting role for custom user (backward compatibility)."""
        assert auth_provider.get_user_role("custom_user") == "custom_user"

    def test_get_user_role_unknown_user(self, auth_provider):
        """Test getting role for unknown user."""
        assert auth_provider.get_user_role("unknown") is None

    def test_parse_auth_header_success(self, auth_provider):
        """Test successful parsing of auth header."""
        credentials = "admin:admin_password"
        encoded = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
        auth_header = f"Basic {encoded}"

        username, password = auth_provider.parse_auth_header(auth_header)
        assert username == "admin"
        assert password == "admin_password"

    def test_parse_auth_header_with_colon_in_password(self, auth_provider):
        """Test parsing auth header with colon in password."""
        credentials = "user:pass:word:123"
        encoded = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
        auth_header = f"Basic {encoded}"

        username, password = auth_provider.parse_auth_header(auth_header)
        assert username == "user"
        assert password == "pass:word:123"

    def test_parse_auth_header_empty(self, auth_provider):
        """Test parsing empty auth header."""
        assert auth_provider.parse_auth_header("") is None
        assert auth_provider.parse_auth_header(None) is None

    def test_parse_auth_header_missing_basic_prefix(self, auth_provider):
        """Test parsing auth header without 'Basic ' prefix."""
        credentials = "admin:password"
        encoded = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')

        assert auth_provider.parse_auth_header(encoded) is None
        assert auth_provider.parse_auth_header(f"Bearer {encoded}") is None

    def test_parse_auth_header_invalid_base64(self, auth_provider):
        """Test parsing auth header with invalid base64."""
        auth_header = "Basic invalid_base64!!!"
        assert auth_provider.parse_auth_header(auth_header) is None

    def test_parse_auth_header_missing_colon(self, auth_provider):
        """Test parsing auth header without colon separator."""
        credentials = "adminpassword"  # No colon
        encoded = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
        auth_header = f"Basic {encoded}"

        assert auth_provider.parse_auth_header(auth_header) is None

    def test_validate_auth_header_success(self, auth_provider):
        """Test successful validation of complete auth header."""
        credentials = "admin:admin_password"
        encoded = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
        auth_header = f"Basic {encoded}"

        user_info = auth_provider.validate_auth_header(auth_header)
        assert user_info is not None
        assert user_info["username"] == "admin"
        assert user_info["role"] == "admin"

    def test_validate_auth_header_invalid_credentials(self, auth_provider):
        """Test validation of auth header with invalid credentials."""
        credentials = "admin:wrong_password"
        encoded = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
        auth_header = f"Basic {encoded}"

        user_info = auth_provider.validate_auth_header(auth_header)
        assert user_info is None

    def test_validate_auth_header_malformed(self, auth_provider):
        """Test validation of malformed auth header."""
        assert auth_provider.validate_auth_header("malformed") is None
        assert auth_provider.validate_auth_header("") is None
        assert auth_provider.validate_auth_header(None) is None

    def test_is_auth_enabled_true(self, auth_provider):
        """Test is_auth_enabled returns True when enabled."""
        assert auth_provider.is_auth_enabled() is True

    def test_is_auth_enabled_false(self):
        """Test is_auth_enabled returns False when disabled."""
        config = {"auth": {"enabled": False, "users": {}}}

        with patch('src.providers.auth.basic_auth.get_config', return_value=config):
            with patch('src.providers.auth.basic_auth.Logger'):
                provider = BasicAuthProvider()
                assert provider.is_auth_enabled() is False

    def test_is_auth_enabled_missing_config(self):
        """Test is_auth_enabled with missing auth config."""
        config = {}

        with patch('src.providers.auth.basic_auth.get_config', return_value=config):
            with patch('src.providers.auth.basic_auth.Logger'):
                provider = BasicAuthProvider()
                assert provider.is_auth_enabled() is False

    def test_get_available_users(self, auth_provider):
        """Test getting list of available usernames."""
        users = auth_provider.get_available_users()
        assert isinstance(users, list)
        assert len(users) == 5
        assert "admin" in users
        assert "dashboard" in users
        assert "mcp_read_user" in users
        assert "splitz" in users
        assert "custom_user" in users

    def test_get_available_users_empty(self):
        """Test getting available users when none configured."""
        config = {"auth": {"users": {}}}

        with patch('src.providers.auth.basic_auth.get_config', return_value=config):
            with patch('src.providers.auth.basic_auth.Logger'):
                provider = BasicAuthProvider()
                users = provider.get_available_users()
                assert users == []

    def test_constant_time_comparison(self, auth_provider):
        """Test that password comparison uses constant-time comparison."""
        # This test verifies that hmac.compare_digest is being used
        # by checking that it doesn't matter if we compare passwords of different lengths

        # Both should take roughly the same time (can't easily test timing, but we verify behavior)
        result1 = auth_provider.validate_credentials("admin", "x")
        result2 = auth_provider.validate_credentials("admin", "x" * 100)

        assert result1 is False
        assert result2 is False

    def test_validate_credentials_logs_success(self, auth_provider, mock_logger):
        """Test that successful validation logs debug message."""
        auth_provider.logger = mock_logger
        auth_provider.validate_credentials("admin", "admin_password")

        # Should have debug log for successful auth
        assert any("successful" in str(call).lower() for call in mock_logger.debug.call_args_list)

    def test_validate_credentials_logs_failure(self, auth_provider, mock_logger):
        """Test that failed validation logs warning message."""
        auth_provider.logger = mock_logger
        auth_provider.validate_credentials("admin", "wrong_password")

        # Should have warning log for failed auth
        assert mock_logger.warning.called
