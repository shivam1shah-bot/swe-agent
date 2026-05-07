"""
Origin Validator for MCP security.

Validates Origin headers to prevent DNS rebinding attacks as required by
MCP Streamable HTTP specification.
"""

import re
from typing import List, Optional
from urllib.parse import urlparse

from src.providers.logger import Logger
from src.providers.config_loader import get_config


class OriginValidator:
    """
    Validates Origin headers for MCP requests to prevent DNS rebinding attacks.
    
    Implements security measures required by MCP Streamable HTTP specification.
    """
    
    def __init__(self):
        """Initialize origin validator."""
        self.logger = Logger("OriginValidator")
        self.config = get_config()
        self._allowed_origins = self._get_allowed_origins()
        self._localhost_patterns = self._get_localhost_patterns()
        
    def _get_allowed_origins(self) -> List[str]:
        """
        Get allowed origins from configuration.
        
        Returns:
            List of allowed origin URLs
        """
        app_config = self.config.get("app", {})
        env_config = self.config.get("environment", {})
        
        allowed_origins = []
        
        # Add configured UI and API URLs
        ui_base_url = app_config.get("ui_base_url")
        api_base_url = app_config.get("api_base_url")
        
        if ui_base_url:
            allowed_origins.append(ui_base_url)
        if api_base_url:
            allowed_origins.append(api_base_url)
        
        # Development environment: allow common localhost origins
        env_name = env_config.get("name", "")
        if env_name in ["dev", "development", "dev_docker"]:
            allowed_origins.extend([
                "http://localhost:3000",
                "http://localhost:3001", 
                "http://localhost:5173",
                "http://localhost:8000",
                "http://127.0.0.1:3000",
                "http://127.0.0.1:3001",
                "http://127.0.0.1:5173",
                "http://127.0.0.1:8000"
            ])
        
        return allowed_origins
    
    def _get_localhost_patterns(self) -> List[re.Pattern]:
        """
        Get localhost patterns for validation.
        
        Returns:
            List of compiled regex patterns for localhost
        """
        patterns = [
            re.compile(r'^https?://localhost(:\d+)?(/.*)?$'),
            re.compile(r'^https?://127\.0\.0\.1(:\d+)?(/.*)?$'),
            re.compile(r'^https?://\[::1\](:\d+)?(/.*)?$'),  # IPv6 localhost
        ]
        return patterns
    
    def validate_origin(self, origin: Optional[str]) -> bool:
        """
        Validate an Origin header value.
        
        Args:
            origin: Origin header value to validate
            
        Returns:
            True if origin is valid and allowed
        """
        if not origin:
            # In development, allow missing Origin for testing
            env_config = self.config.get("environment", {})
            env_name = env_config.get("name", "")
            if env_name in ["dev", "dev_docker"]:
                self.logger.debug("Allowing missing Origin in development environment")
                return True
            else:
                self.logger.warning("Missing Origin header in production environment")
                return False
        
        # Normalize origin
        origin = origin.strip().lower()
        
        # Check against allowed origins
        if self._is_origin_allowed(origin):
            self.logger.debug("Origin validated successfully", origin=origin)
            return True
        
        # Check if it's a localhost origin in development
        if self._is_development_localhost(origin):
            self.logger.debug("Allowing localhost origin in development", origin=origin)
            return True
        
        self.logger.warning("Origin validation failed", origin=origin, allowed_origins=self._allowed_origins)
        return False
    
    def _is_origin_allowed(self, origin: str) -> bool:
        """
        Check if origin is in the allowed list.
        
        Args:
            origin: Origin to check
            
        Returns:
            True if origin is allowed
        """
        # Exact match
        if origin in [o.lower() for o in self._allowed_origins]:
            return True
        
        # Parse and compare without trailing slashes
        try:
            parsed_origin = urlparse(origin)
            origin_base = f"{parsed_origin.scheme}://{parsed_origin.netloc}"
            
            for allowed in self._allowed_origins:
                parsed_allowed = urlparse(allowed)
                allowed_base = f"{parsed_allowed.scheme}://{parsed_allowed.netloc}"
                
                if origin_base.lower() == allowed_base.lower():
                    return True
        except Exception as e:
            self.logger.debug("Error parsing origin", origin=origin, error=str(e))
        
        return False
    
    def _is_development_localhost(self, origin: str) -> bool:
        """
        Check if origin is a localhost origin in development environment.
        
        Args:
            origin: Origin to check
            
        Returns:
            True if it's a development localhost origin
        """
        env_config = self.config.get("environment", {})
        env_name = env_config.get("name", "")
        
        # Only allow in development environments
        if env_name not in ["dev", "development", "dev_docker"]:
            return False
        
        # Check against localhost patterns
        for pattern in self._localhost_patterns:
            if pattern.match(origin):
                return True
        
        return False
    
    def get_allowed_origins(self) -> List[str]:
        """
        Get list of allowed origins.
        
        Returns:
            List of allowed origin URLs
        """
        return self._allowed_origins.copy()
    
    def add_allowed_origin(self, origin: str):
        """
        Add an allowed origin.
        
        Args:
            origin: Origin URL to add
        """
        if origin not in self._allowed_origins:
            self._allowed_origins.append(origin)
            self.logger.info("Added allowed origin", origin=origin)
    
    def remove_allowed_origin(self, origin: str) -> bool:
        """
        Remove an allowed origin.
        
        Args:
            origin: Origin URL to remove
            
        Returns:
            True if origin was removed
        """
        if origin in self._allowed_origins:
            self._allowed_origins.remove(origin)
            self.logger.info("Removed allowed origin", origin=origin)
            return True
        return False
    
    def validate_and_normalize_origin(self, origin: Optional[str]) -> Optional[str]:
        """
        Validate and normalize an origin.
        
        Args:
            origin: Origin to validate and normalize
            
        Returns:
            Normalized origin if valid, None if invalid
        """
        if not self.validate_origin(origin):
            return None
        
        if not origin:
            return None
        
        # Normalize the origin
        try:
            parsed = urlparse(origin.strip())
            normalized = f"{parsed.scheme}://{parsed.netloc}"
            return normalized.lower()
        except Exception:
            return origin.strip().lower() if origin else None 