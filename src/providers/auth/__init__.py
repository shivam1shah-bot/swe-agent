"""
Authentication providers package.

Contains authentication-related providers for the SWE Agent.
"""

from .basic_auth import BasicAuthProvider
from .rbac import (
    require_role,
    require_admin_role,
    require_dashboard_or_admin_role,
    get_current_user_role,
    require_role_dependency,
    AdminRole,
    DashboardOrAdminRole,
    RBACError
)

__all__ = [
    "BasicAuthProvider",
    "require_role",
    "require_admin_role",
    "require_dashboard_or_admin_role",
    "get_current_user_role",
    "require_role_dependency",
    "AdminRole",
    "DashboardOrAdminRole",
    "RBACError"
] 