"""
MCP Service Dependencies.

This module provides dependency injection for the MCP service including
API client instances, configuration, and other shared resources.
"""

from typing import Optional
from fastapi import Depends

from .clients.api_client import SWEAgentAPIClient
from .config.settings import MCPSettings, get_mcp_settings

# Global instances
_api_client: Optional[SWEAgentAPIClient] = None


def get_settings() -> MCPSettings:
    """
    Get MCP settings dependency.
    
    Returns:
        MCPSettings instance
    """
    return get_mcp_settings()


async def get_api_client(
    settings: MCPSettings = Depends(get_settings)
) -> SWEAgentAPIClient:
    """
    Get API client dependency for calling SWE Agent API.
    
    This creates a singleton API client instance that can be shared
    across all MCP requests.
    
    Args:
        settings: MCP settings dependency
        
    Returns:
        SWEAgentAPIClient instance
    """
    global _api_client
    if _api_client is None:
        _api_client = SWEAgentAPIClient(settings)
    return _api_client


async def cleanup_dependencies():
    """
    Cleanup function to be called on service shutdown.
    
    This ensures proper cleanup of HTTP clients and other resources.
    """
    global _api_client
    if _api_client:
        await _api_client.close()
        _api_client = None 