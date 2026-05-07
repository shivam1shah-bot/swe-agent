"""
Basic Authentication Provider.

Handles HTTP Basic Authentication using credentials from configuration.
"""

import base64
import hashlib
import hmac
from typing import Dict, Any, Optional, Tuple

from ..config_loader import get_config
from ..logger import Logger


class BasicAuthProvider:
    """
    Basic Authentication provider that validates credentials against configuration.
    
    Supports two hardcoded users: dashboard and admin.
    """
    
    def __init__(self):
        """Initialize the basic auth provider."""
        self.config = get_config()
        self.logger = Logger("BasicAuth")
        self._load_users()
    
    def _load_users(self) -> None:
        """Load user credentials from configuration."""
        auth_config = self.config.get("auth", {})
        self.users = auth_config.get("users", {})
        
        if not self.users:
            self.logger.warning("No auth users configured - authentication will fail")
        else:
            self.logger.debug(f"Loaded {len(self.users)} auth users")
    
    def validate_credentials(self, username: str, password: str) -> bool:
        """
        Validate username and password against configuration.
        
        Args:
            username: Username to validate
            password: Password to validate
            
        Returns:
            True if credentials are valid, False otherwise
        """
        if not username or not password:
            return False
        
        # Get expected password from config
        expected_password = self.users.get(username)
        if not expected_password:
            self.logger.debug(f"Authentication failed: unknown user '{username}'")
            return False
        
        # Use constant-time comparison to prevent timing attacks
        is_valid = hmac.compare_digest(password, expected_password)
        
        if is_valid:
            self.logger.debug(f"Authentication successful for user '{username}'")
        else:
            self.logger.warning(f"Authentication failed: invalid password for user '{username}'")
        
        return is_valid
    
    def get_user_role(self, username: str) -> Optional[str]:
        """
        Get the role for a given username.

        Args:
            username: Username to get role for

        Returns:
            User role ("dashboard", "admin", "mcp_read_user", or "splitz") or None if user doesn't exist
        """
        if username not in self.users:
            return None

        # Role name matches username by convention (e.g. admin -> admin, devops -> devops)
        return username
    
    def parse_auth_header(self, auth_header: str) -> Optional[Tuple[str, str]]:
        """
        Parse HTTP Basic Auth header.
        
        Args:
            auth_header: Authorization header value
            
        Returns:
            Tuple of (username, password) or None if invalid
        """
        if not auth_header:
            return None
        
        try:
            # Remove "Basic " prefix
            if not auth_header.startswith("Basic "):
                self.logger.warning("Invalid auth header format - missing 'Basic ' prefix")
                return None
            
            encoded_credentials = auth_header[6:]  # Remove "Basic "
            
            # Decode base64
            try:
                decoded_bytes = base64.b64decode(encoded_credentials)
                decoded_str = decoded_bytes.decode('utf-8')
            except Exception:
                self.logger.debug("Failed to decode auth header")
                return None
            
            # Split username:password
            if ':' not in decoded_str:
                self.logger.warning("Invalid auth header format - missing ':' separator")
                return None
            
            username, password = decoded_str.split(':', 1)
            return username, password
            
        except Exception:
            self.logger.debug("Error parsing auth header")
            return None
    
    def validate_auth_header(self, auth_header: str) -> Optional[Dict[str, Any]]:
        """
        Validate complete auth header and return user info.
        
        Args:
            auth_header: Authorization header value
            
        Returns:
            Dict with user info (username, role) or None if invalid
        """
        credentials = self.parse_auth_header(auth_header)
        if not credentials:
            return None
        
        username, password = credentials
        
        if not self.validate_credentials(username, password):
            return None
        
        role = self.get_user_role(username)
        return {
            "username": username,
            "role": role
        }
    
    def is_auth_enabled(self) -> bool:
        """
        Check if authentication is enabled in configuration.
        
        Returns:
            True if auth is enabled, False otherwise
        """
        auth_config = self.config.get("auth", {})
        return auth_config.get("enabled", False)
    
    def get_available_users(self) -> list:
        """
        Get list of available usernames (for debugging/admin purposes).
        
        Returns:
            List of configured usernames
        """
        return list(self.users.keys()) 