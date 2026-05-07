"""
Unit tests for devops role in BasicAuthProvider and RoleChecker.

Validates that:
- devops user credentials are accepted
- devops username maps to devops role (username-as-role convention)
- RoleChecker grants/denies access to the correct endpoints
"""

import pytest
from unittest.mock import patch

from src.providers.auth.basic_auth import BasicAuthProvider
from src.providers.auth.rbac import RoleChecker


# ---------------------------------------------------------------------------
# Shared config fixture
# ---------------------------------------------------------------------------

MOCK_CONFIG = {
    "auth": {
        "enabled": True,
        "users": {
            "admin": "admin123",
            "dashboard": "dashboard123",
            "mcp_read_user": "mcp123",
            "splitz": "splitz123",
            "devops": "devops123",
        }
    }
}


# ---------------------------------------------------------------------------
# BasicAuthProvider tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDevopsBasicAuth:
    """Test devops user credential and role resolution in BasicAuthProvider."""

    @pytest.fixture
    def provider(self):
        with patch('src.providers.auth.basic_auth.get_config', return_value=MOCK_CONFIG):
            with patch('src.providers.auth.basic_auth.Logger'):
                yield BasicAuthProvider()

    def test_devops_user_loaded(self, provider):
        """devops must be present in the loaded users dict."""
        assert "devops" in provider.users

    def test_devops_credentials_valid(self, provider):
        """devops:devops123 must authenticate successfully."""
        assert provider.validate_credentials("devops", "devops123") is True

    def test_devops_wrong_password_rejected(self, provider):
        """devops with a wrong password must be rejected."""
        assert provider.validate_credentials("devops", "wrong") is False

    def test_devops_role_matches_username(self, provider):
        """get_user_role must return 'devops' for username 'devops' (convention)."""
        assert provider.get_user_role("devops") == "devops"

    def test_devops_full_auth_header_returns_role(self, provider):
        """validate_auth_header must return username=devops and role=devops."""
        import base64
        encoded = base64.b64encode(b"devops:devops123").decode("ascii")
        user_info = provider.validate_auth_header(f"Basic {encoded}")

        assert user_info is not None
        assert user_info["username"] == "devops"
        assert user_info["role"] == "devops"

    def test_existing_roles_unaffected(self, provider):
        """Adding devops must not change role resolution for other users."""
        assert provider.get_user_role("admin") == "admin"
        assert provider.get_user_role("dashboard") == "dashboard"
        assert provider.get_user_role("mcp_read_user") == "mcp_read_user"
        assert provider.get_user_role("splitz") == "splitz"


# ---------------------------------------------------------------------------
# RoleChecker tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDevopsRoleChecker:
    """Test devops role access control via RoleChecker."""

    @pytest.fixture
    def checker(self):
        return RoleChecker()

    # -- role resolution --

    def test_role_resolved_from_role_field(self, checker):
        """When role field is present (JWT path), it is returned directly."""
        user_info = {"username": "devops", "role": "devops"}
        assert checker.get_user_role(user_info) == "devops"

    def test_role_resolved_from_username(self, checker):
        """When role field is absent (Basic Auth path), username is used as role."""
        user_info = {"username": "devops"}
        assert checker.get_user_role(user_info) == "devops"

    # -- allowed endpoints --

    def test_devops_allowed_on_agents_run(self, checker):
        allowed = ["dashboard", "admin", "splitz", "devops"]
        assert checker.check_role_access("devops", allowed) is True

    def test_devops_allowed_on_agents_batch(self, checker):
        allowed = ["dashboard", "admin", "splitz", "devops"]
        assert checker.check_role_access("devops", allowed) is True

    def test_devops_allowed_on_agents_multi_repo(self, checker):
        allowed = ["dashboard", "admin", "splitz", "devops"]
        assert checker.check_role_access("devops", allowed) is True

    def test_devops_allowed_on_tasks_list(self, checker):
        allowed = ["dashboard", "admin", "mcp_read_user", "devops"]
        assert checker.check_role_access("devops", allowed) is True

    def test_devops_allowed_on_tasks_get(self, checker):
        allowed = ["dashboard", "admin", "mcp_read_user", "splitz", "devops"]
        assert checker.check_role_access("devops", allowed) is True

    def test_devops_allowed_on_tasks_stats(self, checker):
        allowed = ["dashboard", "admin", "devops"]
        assert checker.check_role_access("devops", allowed) is True

    def test_devops_allowed_on_tasks_execution_logs(self, checker):
        allowed = ["dashboard", "admin", "mcp_read_user", "devops"]
        assert checker.check_role_access("devops", allowed) is True

    # -- denied endpoints --

    def test_devops_denied_on_tasks_create(self, checker):
        """POST /tasks is dashboard+admin only — devops must be denied."""
        allowed = ["dashboard", "admin"]
        assert checker.check_role_access("devops", allowed) is False

    def test_devops_denied_on_tasks_batch_create(self, checker):
        """POST /tasks/batch is admin-only — devops must be denied."""
        allowed = ["admin"]
        assert checker.check_role_access("devops", allowed) is False

    def test_devops_denied_on_tasks_status_update(self, checker):
        """PUT /tasks/{id}/status is dashboard+admin only — devops must be denied."""
        allowed = ["dashboard", "admin"]
        assert checker.check_role_access("devops", allowed) is False

    # -- other roles unaffected --

    def test_admin_still_has_full_access(self, checker):
        assert checker.check_role_access("admin", ["admin"]) is True
        assert checker.check_role_access("admin", ["dashboard", "admin"]) is True

    def test_mcp_read_user_unaffected(self, checker):
        assert checker.check_role_access("mcp_read_user", ["dashboard", "admin", "mcp_read_user"]) is True
        assert checker.check_role_access("mcp_read_user", ["admin"]) is False
