"""
MCP Service Configuration Settings.

This module provides configuration management for the standalone MCP service
that communicates with the SWE Agent API via HTTP.
"""

from typing import Dict, Any
from src.providers.config_loader import get_config


class MCPSettings:
    """Configuration settings for the MCP service using config loader."""
    
    def __init__(self):
        """Initialize MCP settings from config loader."""
        self.config = get_config()
    
    @property
    def host(self) -> str:
        """Get MCP service host."""
        return self.config.get("app", {}).get("host", "0.0.0.0")
    
    @property
    def port(self) -> int:
        """Get MCP service port."""
        return self.config.get("app", {}).get("mcp_port", 8003)
    
    @property
    def api_base_url(self) -> str:
        """Get base URL for SWE Agent API service."""
        return self.config.get("app", {}).get("api_base_url", "http://localhost:28002")
    
    @property
    def mcp_base_url(self) -> str:
        """Get base URL for MCP service."""
        return self.config.get("app", {}).get("mcp_base_url", "http://localhost:28003")
    
    @property
    def debug(self) -> bool:
        """Get debug mode setting."""
        return self.config.get("app", {}).get("debug", False)
    
    @property
    def log_level(self) -> str:
        """Get logging level."""
        return self.config.get("logging", {}).get("level", "INFO")
    
    @property
    def api_timeout(self) -> float:
        """Get API request timeout in seconds."""
        return 30.0
    
    @property
    def api_retries(self) -> int:
        """Get number of API request retries."""
        return 3
    
    @property
    def environment_name(self) -> str:
        """Get environment name."""
        return self.config.get("environment", {}).get("name", "dev")
    
    def is_development_mode(self) -> bool:
        """Check if running in development mode."""
        return self.environment_name in ["dev", "dev_docker"]
    
    @property
    def auth_username(self) -> str:
        """Get authentication username for API calls."""
        return "mcp_read_user"
    
    @property
    def auth_password(self) -> str:
        """Get authentication password for API calls."""
        auth_config = self.config.get("auth", {})
        users = auth_config.get("users", {})
        return users.get("mcp_read_user", "")
    
    @property
    def auth_enabled(self) -> bool:
        """Check if authentication is enabled."""
        auth_config = self.config.get("auth", {})
        return auth_config.get("enabled", False)
    
    def get_all_settings(self) -> Dict[str, Any]:
        """
        Get all MCP settings as a dictionary.
        
        Returns:
            Dictionary containing all configuration settings
        """
        return {
            "host": self.host,
            "port": self.port,
            "api_base_url": self.api_base_url,
            "mcp_base_url": self.mcp_base_url,
            "debug": self.debug,
            "log_level": self.log_level,
            "api_timeout": self.api_timeout,
            "api_retries": self.api_retries,
            "environment_name": self.environment_name,
            "is_development_mode": self.is_development_mode(),
            "auth_username": self.auth_username,
            "auth_enabled": self.auth_enabled
        }


# Global settings instance
_settings = None


def get_mcp_settings() -> MCPSettings:
    """Get global MCP settings instance."""
    global _settings
    if _settings is None:
        _settings = MCPSettings()
    return _settings 