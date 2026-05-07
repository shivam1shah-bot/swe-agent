"""
Model Context Protocol (MCP) implementation for SWE Agent.

This package provides a complete MCP server implementation using Streamable HTTP transport,
exposing the SWE Agent API as MCP tools organized by functional domains.
"""

from .server.http_server import MCPHttpServer
from .server.session_manager import MCPSessionManager
from .server.error_handler import MCPErrorHandler

__version__ = "1.0.0"
__all__ = ["MCPHttpServer", "MCPSessionManager", "MCPErrorHandler"] 