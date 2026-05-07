"""
RBAC Validator for MCP tool access control.

Integrates with the existing RBAC system to validate tool access permissions.
"""

from typing import Dict, List, Optional, Any
from fastapi import Request

from src.providers.logger import Logger
from src.providers.auth.rbac import get_user_roles, check_role_permission


class MCPRBACValidator:
    """
    RBAC validator for MCP tool access control.
    
    Integrates with the existing authentication and authorization system
    to validate tool access permissions.
    """
    
    def __init__(self):
        """Initialize RBAC validator."""
        self.logger = Logger("MCPRBACValidator")
        
        # Load configuration to check environment
        from src.providers.config_loader import get_config
        self.config = get_config()
        
        # Tool to role mapping
        self.tool_permissions = self._get_tool_permissions()
    
    def _get_tool_permissions(self) -> Dict[str, List[str]]:
        """
        Get tool permission mapping.
        
        Returns:
            Dictionary mapping tool names to required roles
        """
        # Check if we're in development environment
        env_config = self.config.get("environment", {})
        env_name = env_config.get("name", "")
        
        # In development environments, allow open access to all tools
        if env_name in ["dev", "development", "dev_docker"]:
            self.logger.info("Development environment detected - allowing open access to all MCP tools")
            return {
                # All tools accessible without authentication in development
                "overall_health": [],
                "get_task": [],
                "list_tasks": [],
                "get_task_execution_logs": [],
                "list_agents_catalogue_services": [],
                "get_agents_catalogue_items": [],
                "get_agents_catalogue_config": [],
            }
        
        # Production environment - require mcp_read_user access
        return {
            # Health tools - accessible by mcp_read_user and admin users
            "overall_health": ["mcp_read_user", "admin"],
            
            # Task tools - accessible by mcp_read_user and admin users
            "get_task": ["mcp_read_user", "admin"],
            "list_tasks": ["mcp_read_user", "admin"],
            "get_task_execution_logs": ["mcp_read_user", "admin"],
            
            # Agents catalogue tools - accessible by mcp_read_user and admin users
            "list_agents_catalogue_services": ["mcp_read_user", "admin"],
            "get_agents_catalogue_items": ["mcp_read_user", "admin"],
            "get_agents_catalogue_config": ["mcp_read_user", "admin"],
        }
    
    def validate_tool_access(self, tool_name: str, request: Request) -> bool:
        """
        Validate if the current user has access to a tool.
        
        Args:
            tool_name: Name of the tool to validate access for
            request: FastAPI request object containing user context
            
        Returns:
            True if user has access to the tool
        """
        try:
            # Get required roles for the tool
            required_roles = self.tool_permissions.get(tool_name)
            if required_roles is None:
                # If tool is not in permission mapping, deny access by default
                self.logger.warning("Unknown tool access denied - not in permission mapping", tool_name=tool_name)
                return False
            
            # If no roles required, allow access (development mode)
            if not required_roles:
                self.logger.debug("Tool access granted - no authentication required", tool_name=tool_name)
                return True
            
            # Get user from request context (set by BasicAuthMiddleware)
            user = getattr(request.state, 'current_user', None)
            if not user:
                self.logger.warning("No user found in request context for tool access", tool_name=tool_name)
                return False
            
            # Get user roles
            user_roles = get_user_roles(user)
            if not user_roles:
                self.logger.warning("No roles found for user", tool_name=tool_name, user=user)
                return False
            
            # Check if user has any of the required roles
            for role in required_roles:
                if role in user_roles:
                    self.logger.debug("Tool access granted", tool_name=tool_name, user_role=role, user=user)
                    return True
            
            self.logger.warning(
                "Tool access denied - insufficient permissions",
                tool_name=tool_name,
                required_roles=required_roles,
                user_roles=user_roles,
                user=user
            )
            return False
            
        except Exception as e:
            self.logger.error("Error validating tool access", tool_name=tool_name, error=str(e))
            return False
    
    def get_accessible_tools(self, request: Request) -> List[str]:
        """
        Get list of tools accessible to the current user.
        
        Args:
            request: FastAPI request object containing user context
            
        Returns:
            List of tool names the user can access
        """
        try:
            accessible_tools = []
            
            # Get user from request context
            user = getattr(request.state, 'user', None)
            if not user:
                return accessible_tools
            
            # Get user roles
            user_roles = get_user_roles(user)
            if not user_roles:
                return accessible_tools
            
            # Check each tool
            for tool_name, required_roles in self.tool_permissions.items():
                if not required_roles:
                    # No specific roles required
                    accessible_tools.append(tool_name)
                    continue
                
                # Check if user has any required role
                if any(role in user_roles for role in required_roles):
                    accessible_tools.append(tool_name)
            
            self.logger.debug("Retrieved accessible tools", user=user, tool_count=len(accessible_tools))
            return accessible_tools
            
        except Exception as e:
            self.logger.error("Error getting accessible tools", error=str(e))
            return []
    
    def get_tool_permissions_info(self, tool_name: str) -> Dict[str, Any]:
        """
        Get permission information for a tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Dictionary with permission information
        """
        required_roles = self.tool_permissions.get(tool_name, [])
        
        return {
            "tool_name": tool_name,
            "required_roles": required_roles,
            "access_level": self._get_access_level(required_roles),
            "description": self._get_permission_description(required_roles)
        }
    
    def _get_access_level(self, required_roles: List[str]) -> str:
        """
        Get access level based on required roles.
        
        Args:
            required_roles: List of required roles
            
        Returns:
            Access level string
        """
        if not required_roles:
            return "public"
        elif "admin" in required_roles and len(required_roles) == 1:
            return "admin_only"
        elif "admin" in required_roles and "dashboard" in required_roles:
            return "authenticated"
        else:
            return "restricted"
    
    def _get_permission_description(self, required_roles: List[str]) -> str:
        """
        Get human-readable permission description.
        
        Args:
            required_roles: List of required roles
            
        Returns:
            Permission description
        """
        if not required_roles:
            return "Available to all users"
        elif len(required_roles) == 1:
            return f"Requires {required_roles[0]} role"
        else:
            return f"Requires one of: {', '.join(required_roles)}"
    
    def add_tool_permission(self, tool_name: str, required_roles: List[str]):
        """
        Add permission mapping for a tool.
        
        Args:
            tool_name: Name of the tool
            required_roles: List of required roles
        """
        self.tool_permissions[tool_name] = required_roles
        self.logger.info("Added tool permission", tool_name=tool_name, required_roles=required_roles)
    
    def remove_tool_permission(self, tool_name: str) -> bool:
        """
        Remove permission mapping for a tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            True if permission was removed
        """
        if tool_name in self.tool_permissions:
            del self.tool_permissions[tool_name]
            self.logger.info("Removed tool permission", tool_name=tool_name)
            return True
        return False
    
    def get_all_tool_permissions(self) -> Dict[str, List[str]]:
        """
        Get all tool permission mappings.
        
        Returns:
            Dictionary of all tool permissions
        """
        return self.tool_permissions.copy()
    
    def validate_session_permissions(self, session_id: str, tool_name: str) -> bool:
        """
        Validate tool access for a specific session.
        
        Args:
            session_id: MCP session ID
            tool_name: Name of the tool
            
        Returns:
            True if session has access to the tool
        """
        # For now, we don't have session-specific permissions
        # This could be extended to support session-based access control
        
        # Get required roles for the tool
        required_roles = self.tool_permissions.get(tool_name, [])
        
        # If no specific roles required, allow access
        if not required_roles:
            return True
        
        # For session-based validation, we would need to:
        # 1. Look up session information
        # 2. Get associated user/roles
        # 3. Validate against tool requirements
        
        # For now, log and return False for restricted tools
        self.logger.warning(
            "Session-based tool access not fully implemented",
            session_id=session_id,
            tool_name=tool_name,
            required_roles=required_roles
        )
        
        return len(required_roles) == 0 