"""
Role-Based Access Control (RBAC) for FastAPI routes.

Provides decorators and dependencies for protecting API endpoints based on user roles.
"""

from typing import List, Dict, Any, Optional, Callable
from functools import wraps
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from src.providers.config_loader import get_config
from ..logger import Logger


class RBACError(Exception):
    """Custom exception for RBAC-related errors."""
    pass


class RoleChecker:
    """
    Role-based access control checker.
    
    Validates user roles against required permissions for route access.
    """
    
    def __init__(self):
        """Initialize the role checker."""
        self.logger = Logger("RBAC")
    
    def check_role_access(
        self, 
        user_role: str, 
        allowed_roles: List[str], 
        method: Optional[str] = None,
        endpoint: Optional[str] = None
    ) -> bool:
        """
        Check if user role has access to the endpoint.
        
        Args:
            user_role: User's role (e.g., 'dashboard', 'admin')
            allowed_roles: List of roles allowed for this operation
            method: HTTP method (for logging)
            endpoint: Endpoint path (for logging)
            
        Returns:
            True if access is allowed, False otherwise
        """
        access_granted = user_role in allowed_roles
        
        if access_granted:
            self.logger.debug(
                f"Access granted to user with role '{user_role}' for {method} {endpoint}",
                user_role=user_role,
                allowed_roles=allowed_roles,
                method=method,
                endpoint=endpoint
            )
        else:
            self.logger.warning(
                f"Access denied to user with role '{user_role}' for {method} {endpoint}",
                user_role=user_role,
                allowed_roles=allowed_roles,
                method=method,
                endpoint=endpoint
            )
        
        return access_granted
    
    def get_user_role(self, user_info: Dict[str, Any]) -> str:
        """
        Extract user role from user info.
        
        Args:
            user_info: User information dict containing username and role
            
        Returns:
            User's role as string
        """
        # If auth is disabled, default to dashboard role for local use
        if not _is_auth_enabled():
            return "dashboard"

        # First check if role is explicitly set (JWT auth)
        role = user_info.get("role", "")
        if role:
            return role
        
        # Fallback: determine role based on username (Basic Auth legacy)
        username = user_info.get("username", "")

        # Role name matches username by convention (e.g. admin -> admin, devops -> devops)
        return username


# Global role checker instance
role_checker = RoleChecker()


def require_role(
    allowed_roles: List[str], 
    method_specific: Optional[Dict[str, List[str]]] = None
):
    """
    Decorator to require specific roles for route access.
    
    Args:
        allowed_roles: List of roles allowed to access this route
        method_specific: Optional dict mapping HTTP methods to specific role requirements
        
    Usage:
        @require_role(["admin"])  # Admin only
        @require_role(["dashboard", "admin"])  # Both dashboard and admin
        @require_role(["admin"], method_specific={"POST": ["admin"], "GET": ["dashboard", "admin"]})
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Short-circuit all checks when auth is disabled
            if not _is_auth_enabled():
                return await func(*args, **kwargs)

            # Extract request from function arguments
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            # If no request found in args, check kwargs
            if request is None:
                request = kwargs.get('request')
            
            if request is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal error: Request object not found in route handler"
                )
            
            # Get user info from request state (set by BasicAuthMiddleware)
            user_info = getattr(request.state, 'current_user', None)
            if user_info is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            # Determine required roles for this method
            method = request.method
            required_roles = allowed_roles
            
            if method_specific and method in method_specific:
                required_roles = method_specific[method]
            
            # Check role access
            user_role = role_checker.get_user_role(user_info)
            
            if not role_checker.check_role_access(
                user_role=user_role,
                allowed_roles=required_roles,
                method=method,
                endpoint=str(request.url.path)
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "Access denied",
                        "message": f"Role '{user_role}' does not have access to {method} {request.url.path}",
                        "required_roles": required_roles,
                        "user_role": user_role
                    }
                )
            
            # Role check passed, proceed with the route handler
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


# Predefined role dependency functions
def require_admin_role():
    """Dependency function that requires admin role."""
    return require_role(["admin"])


def require_dashboard_or_admin_role():
    """Dependency function that requires dashboard or admin role."""
    return require_role(["dashboard", "admin"])


def get_current_user_role(request: Request) -> str:
    """
    FastAPI dependency to get current user's role.
    
    Args:
        request: FastAPI request object
        
    Returns:
        User's role as string
        
    Raises:
        HTTPException: If user is not authenticated
    """
    # If auth is disabled, return dashboard role
    if not _is_auth_enabled():
        return "dashboard"

    user_info = getattr(request.state, 'current_user', None)
    if user_info is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    return role_checker.get_user_role(user_info)


def require_role_dependency(allowed_roles: List[str]):
    """
    Create a FastAPI dependency that requires specific roles.
    
    Args:
        allowed_roles: List of roles allowed
        
    Returns:
        FastAPI dependency function
    """
    def role_dependency(request: Request):
        # If auth is disabled, allow and return dashboard role
        if not _is_auth_enabled():
            return "dashboard"

        user_info = getattr(request.state, 'current_user', None)
        if user_info is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        
        user_role = role_checker.get_user_role(user_info)
        
        if not role_checker.check_role_access(
            user_role=user_role,
            allowed_roles=allowed_roles,
            method=request.method,
            endpoint=str(request.url.path)
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "Access denied",
                    "message": f"Role '{user_role}' does not have access to {request.method} {request.url.path}",
                    "required_roles": allowed_roles,
                    "user_role": user_role
                }
            )
        
        return user_role
    
    return role_dependency


# Common role dependencies
AdminRole = Depends(require_role_dependency(["admin"]))
DashboardOrAdminRole = Depends(require_role_dependency(["dashboard", "admin"]))
MCPReadUserRole = Depends(require_role_dependency(["mcp_read_user"]))
DashboardAdminOrMCPRole = Depends(require_role_dependency(["dashboard", "admin", "mcp_read_user"]))


# Helper functions for MCP integration
def get_user_roles(user: Dict[str, Any]) -> List[str]:
    """
    Get user roles as a list for MCP integration.
    
    Args:
        user: User information dictionary or object with roles attribute
        
    Returns:
        List of user roles
    """
    # Handle mock objects with roles attribute (for testing)
    if hasattr(user, 'roles') and isinstance(user.roles, list):
        return user.roles
    
    # Handle dictionary with roles key
    if isinstance(user, dict) and 'roles' in user:
        return user['roles']
    
    # Fallback to role checker for legacy behavior
    role_checker = RoleChecker()
    user_role = role_checker.get_user_role(user)
    return [user_role] if user_role else []


def _is_auth_enabled() -> bool:
    """
    Helper to read auth.enabled from config.
    Defaults to True if missing.
    """
    config = get_config()
    return config.get("auth", {}).get("enabled", True)


def check_role_permission(user_role: str, tool_name: str, required_roles: List[str]) -> bool:
    """
    Check if user role has permission for a specific tool.
    
    Args:
        user_role: User's role
        tool_name: Name of the tool being accessed
        required_roles: List of roles required for the tool
        
    Returns:
        True if permission granted, False otherwise
    """
    role_checker = RoleChecker()
    return role_checker.check_role_access(user_role, required_roles, endpoint=tool_name) 