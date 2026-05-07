"""
MCP Request Handler for processing JSON-RPC requests.

Handles routing and processing of MCP protocol requests with validation,
security checks, and proper response formatting.
"""

import json
from typing import Dict, Any, Optional
from fastapi import Request

from src.providers.logger import Logger


class MCPRequestHandler:
    """
    Handles MCP JSON-RPC request processing and routing.
    
    Processes incoming MCP requests, validates them against the protocol,
    applies security checks, and routes them to appropriate tool handlers.
    """
    
    def __init__(self, tool_registry, rbac_validator):
        """
        Initialize MCP request handler.
        
        Args:
            tool_registry: MCP tool registry instance
            rbac_validator: RBAC validator for access control
        """
        self.logger = Logger("MCPRequestHandler")
        self.tool_registry = tool_registry
        self.rbac_validator = rbac_validator
        
        # Supported protocol versions for compatibility (latest specification)
        self.supported_versions = ["2024-11-05", "2025-03-26", "2025-06-18"]
        self.latest_version = "2025-06-18"  # Latest protocol version
        self.fallback_version = "2025-03-26"  # Default per 2025-06-18 spec
    
    async def handle_request(self, request_data: Dict[str, Any], request: Request) -> Dict[str, Any]:
        """
        Handle incoming MCP JSON-RPC request.
        
        Args:
            request_data: JSON-RPC request data
            request: FastAPI request object
            
        Returns:
            JSON-RPC response
        """
        try:
            # Extract request information
            method = request_data.get("method")
            params = request_data.get("params", {})
            request_id = request_data.get("id")
            
            # Check for MCP-Protocol-Version header (required per 2025-06-18 spec)
            protocol_version = self._get_protocol_version(request, method, params)
            
            self.logger.info("Processing MCP request", 
                           method=method, 
                           request_id=request_id,
                           protocol_version=protocol_version)
            
            # Handle different MCP methods
            if method == "initialize":
                return await self._handle_initialize(params, request_id, protocol_version)
            elif method == "notifications/initialized":
                return await self._handle_initialized_notification()
            elif method == "tools/list":
                return await self._handle_tools_list(request_id)
            elif method == "tools/call":
                return await self._handle_tool_call(params, request_id, request)
            elif method == "ping":
                return await self._handle_ping(request_id)
            else:
                return self._create_error_response(
                    -32601, 
                    f"Method not found: {method}", 
                    request_id
                )
                
        except Exception as e:
            self.logger.error("Error handling MCP request", error=str(e))
            return self._create_error_response(
                -32603,
                f"Internal error: {str(e)}",
                request_data.get("id")
            )
    
    def _get_protocol_version(self, request: Request, method: str, params: Dict[str, Any]) -> str:
        """
        Get protocol version from header or initialize params.
        
        Per 2025-06-18 spec:
        - Client MUST include MCP-Protocol-Version header on all requests
        - If no header and no other way to identify version, assume 2025-03-26
        - For initialize, use protocolVersion from params
        
        Args:
            request: FastAPI request object
            method: JSON-RPC method name
            params: Request parameters
            
        Returns:
            Protocol version string
        """
        # For initialize request, use protocolVersion from params
        if method == "initialize":
            return params.get("protocolVersion", self.latest_version)
        
        # Check MCP-Protocol-Version header (required per spec)
        if request and hasattr(request, 'headers'):
            header_version = request.headers.get("mcp-protocol-version")
            if header_version:
                if header_version in self.supported_versions:
                    return header_version
                else:
                    # Invalid version - this should return 400 Bad Request
                    # For now, log warning and use fallback
                    self.logger.warning("Unsupported protocol version in header", 
                                      version=header_version)
        
        # Fallback to 2025-03-26 per specification
        return self.fallback_version
    
    async def _handle_initialize(self, params: Dict[str, Any], request_id: Any, protocol_version: str) -> Dict[str, Any]:
        """Handle MCP initialize request with latest protocol version support."""
        try:
            # Get client information
            client_info = params.get("clientInfo", {})
            capabilities = params.get("capabilities", {})
            
            # Validate and normalize protocol version
            if protocol_version not in self.supported_versions:
                self.logger.warning("Unsupported protocol version", version=protocol_version)
                # Use latest supported version for compatibility
                protocol_version = self.latest_version
            
            self.logger.info("Initializing MCP session", 
                           client_info=client_info, 
                           protocol_version=protocol_version)
            
            # Create response with server capabilities (2025-06-18 format)
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": protocol_version,
                    "serverInfo": {
                        "name": "swe-agent-mcp-server", 
                        "version": "1.0.0",
                        "description": "SWE Agent MCP Server - AI-powered software engineering automation"
                    },
                    "capabilities": {
                        "tools": {
                            "listChanged": False
                        },
                        "resources": {
                            "subscribe": False,
                            "listChanged": False
                        },
                        "prompts": {
                            "listChanged": False
                        },
                        "logging": {}
                    }
                }
            }
            
            return response
            
        except Exception as e:
            self.logger.error("Error in initialize handler", error=str(e))
            return self._create_error_response(-32603, str(e), request_id)
    
    async def _handle_initialized_notification(self) -> Dict[str, Any]:
        """Handle initialized notification (no response needed for notifications)."""
        self.logger.info("Received initialized notification")
        # Notifications don't return responses in JSON-RPC
        return {"status": "accepted"}  # This will be converted to 202 by the router
    
    async def _handle_tools_list(self, request_id: Any) -> Dict[str, Any]:
        """Handle tools/list request."""
        try:
            tools = await self.tool_registry.list_tools()
            
            self.logger.info("Listed MCP tools", tool_count=len(tools))
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": tools
                }
            }
            
        except Exception as e:
            self.logger.error("Error listing tools", error=str(e))
            return self._create_error_response(-32603, str(e), request_id)
    
    async def _handle_tool_call(self, params: Dict[str, Any], request_id: Any, request: Request) -> Dict[str, Any]:
        """Handle tools/call request."""
        try:
            tool_name = params.get("name")
            tool_arguments = params.get("arguments", {})
            
            if not tool_name:
                return self._create_error_response(-32602, "Missing tool name", request_id)
            
            # RBAC validation
            if not self.rbac_validator.validate_tool_access(tool_name, request):
                return self._create_error_response(-32604, f"Access denied: insufficient permissions for tool '{tool_name}'", request_id)
            
            # Execute tool
            result = await self.tool_registry.execute_tool(tool_name, tool_arguments)
            
            self.logger.info("Executed MCP tool", tool_name=tool_name)
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": result.get("content", []),
                    "isError": result.get("isError", False)
                }
            }
            
        except Exception as e:
            self.logger.error("Error executing tool", tool_name=params.get("name"), error=str(e))
            return self._create_error_response(-32603, str(e), request_id)
    
    async def _handle_ping(self, request_id: Any) -> Dict[str, Any]:
        """Handle ping request."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "status": "pong"
            }
        }
    
    def _create_error_response(self, code: int, message: str, request_id: Any) -> Dict[str, Any]:
        """Create JSON-RPC error response."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message
            }
        } 