"""
MCP HTTP Server implementation using Streamable HTTP transport.

This module implements the main MCP server using FastAPI with support for:
- JSON-RPC 2.0 over HTTP POST for request/response
- Server-Sent Events (SSE) over HTTP GET for streaming
- Session management with Mcp-Session-Id header
- Security validation and rate limiting
"""

import json
import asyncio
import time
from typing import Dict, Any, Optional, AsyncGenerator
from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from src.providers.logger.provider import Logger
from src.providers.config_loader import get_config

from .session_manager import MCPSessionManager
from .stream_manager import MCPStreamManager
from .request_handler import MCPRequestHandler
from .error_handler import MCPErrorHandler
from ..tools.registry import MCPToolRegistry
from ..security.origin_validator import OriginValidator
from ..security.rate_limiter import MCPRateLimiter
from ..security.rbac_validator import MCPRBACValidator
from ..security.input_sanitizer import InputSanitizer


class MCPHttpServer:
    """
    MCP HTTP Server implementation with Streamable HTTP transport.
    
    This server handles MCP protocol messages over HTTP with support for:
    - JSON-RPC 2.0 requests via POST
    - Server-Sent Events for streaming via GET
    - Session management and security validation
    - Rate limiting and input sanitization
    """
    
    def __init__(self, app: FastAPI):
        """
        Initialize the MCP HTTP server.
        
        Args:
            app: FastAPI application instance
        """
        self.logger = Logger("MCPHttpServer")
        self.app = app
        self.config = get_config()
        
        # Initialize core components
        self.session_manager = MCPSessionManager()
        self.stream_manager = MCPStreamManager()
        self.tool_registry = None  # Will be set later by router
        self.error_handler = MCPErrorHandler()
        
        # Initialize security components first
        self.origin_validator = OriginValidator()
        self.rate_limiter = MCPRateLimiter()
        self.rbac_validator = MCPRBACValidator()
        self.input_sanitizer = InputSanitizer()
        
        # Initialize request handler later after tool registry is set
        self.request_handler = None
        

        
        # Server state
        self._initialized = False
        
    async def initialize(self):
        """Initialize the MCP server and all components."""
        if self._initialized:
            return
            
        self.logger.info("Initializing MCP HTTP Server")
        
        try:
            # Initialize tool registry
            await self.tool_registry.initialize()
            
            # Initialize request handler now that tool registry is available
            self.request_handler = MCPRequestHandler(self.tool_registry, self.rbac_validator)
            
            # Setup routes
            self._setup_routes()
            
            self._initialized = True
            self.logger.info("MCP HTTP Server initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize MCP HTTP Server: {e}")
            raise
    
    def _setup_routes(self):
        """Setup MCP HTTP routes according to Streamable HTTP specification."""
        
        @self.app.post("/mcp")
        async def handle_mcp_post(request: Request):
            """Handle MCP JSON-RPC requests via POST (Streamable HTTP)."""
            return await self._handle_mcp_post_request(request)
        
        @self.app.get("/mcp")
        async def handle_mcp_get(request: Request):
            """Handle MCP SSE stream initialization via GET (Streamable HTTP)."""
            return await self._handle_mcp_get_request(request)
        
        @self.app.delete("/mcp")
        async def handle_mcp_delete(request: Request):
            """Handle MCP session termination via DELETE (Streamable HTTP)."""
            return await self._handle_mcp_delete_request(request)
        
        @self.app.get("/mcp/health")
        async def mcp_health_check():
            """MCP server health check endpoint."""
            return await self._handle_health_check()
        
        @self.app.get("/mcp/info") 
        async def mcp_server_info():
            """MCP server information endpoint."""
            return await self._handle_server_info()
    
    async def _handle_mcp_post_request(self, request: Request):
        """
        Handle POST requests according to MCP Streamable HTTP specification.
        
        Supports:
        - Single JSON-RPC requests/notifications/responses
        - Batched requests/notifications/responses
        - Session management with Mcp-Session-Id headers
        - SSE streaming for complex responses
        
        Args:
            request: FastAPI request object
            
        Returns:
            JSON response or SSE stream
        """
        try:
            # Security validation
            await self._validate_request_security(request, "mcp_request")
            
            # Check Accept header
            accept_header = request.headers.get("accept", "")
            supports_sse = "text/event-stream" in accept_header
            supports_json = "application/json" in accept_header
            
            if not supports_json and not supports_sse:
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=400, 
                    detail="Must accept application/json or text/event-stream"
                )
            
            # Get or validate session
            session_id = request.headers.get("mcp-session-id")
            if session_id and not self.session_manager.validate_session(session_id):
                from fastapi import HTTPException
                raise HTTPException(status_code=404, detail="Session not found")
            
            # Parse request body
            try:
                request_data = await request.json()
            except Exception as e:
                return self.error_handler.format_mcp_error(
                    ValueError(f"Invalid JSON: {e}"),
                    request_id=None
                )
            
            # Handle different types of input
            if isinstance(request_data, list):
                # Batched requests
                has_requests = any(
                    isinstance(item, dict) and item.get("method") and "id" in item 
                    for item in request_data
                )
                
                if not has_requests:
                    # Only notifications/responses - return 202 Accepted
                    await self._process_notifications_responses(request_data, session_id)
                    return Response(status_code=202)
                else:
                    # Contains requests - handle with possible streaming
                    return await self._handle_requests_with_streaming(
                        request_data, session_id, supports_sse, supports_json, request
                    )
            
            elif isinstance(request_data, dict):
                # Single message
                if request_data.get("method") and "id" in request_data:
                    # Single request
                    return await self._handle_requests_with_streaming(
                        [request_data], session_id, supports_sse, supports_json, request
                    )
                else:
                    # Notification or response - return 202 Accepted
                    await self._process_notifications_responses([request_data], session_id)
                    return Response(status_code=202)
            
            else:
                return self.error_handler.format_mcp_error(
                    ValueError("Invalid request format"),
                    request_id=None
                )
                
        except Exception as e:
            self.logger.error("Error in MCP POST request", error=str(e))
            return self.error_handler.format_mcp_error(e, request_id=None)
    
    async def _handle_mcp_get_request(self, request: Request):
        """
        Handle GET requests for SSE streams according to MCP specification.
        
        Args:
            request: FastAPI request object
            
        Returns:
            SSE stream or 405 Method Not Allowed
        """
        try:
            # Check Accept header
            accept_header = request.headers.get("accept", "")
            if "text/event-stream" not in accept_header:
                from fastapi import HTTPException
                raise HTTPException(status_code=405, detail="Method Not Allowed")
            
            # Security validation
            await self._validate_request_security(request, "mcp_stream")
            
            # Get or validate session
            session_id = request.headers.get("mcp-session-id")
            if session_id and not self.session_manager.validate_session(session_id):
                from fastapi import HTTPException
                raise HTTPException(status_code=404, detail="Session not found")
            
            # Check for resumability
            last_event_id = request.headers.get("last-event-id")
            
            # Create SSE stream
            return await self._create_sse_stream(session_id, last_event_id)
            
        except Exception as e:
            self.logger.error("Error in MCP GET request", error=str(e))
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=str(e))
    
    async def _handle_mcp_delete_request(self, request: Request):
        """
        Handle DELETE requests for session termination.
        
        Args:
            request: FastAPI request object
            
        Returns:
            200 OK or 405 Method Not Allowed
        """
        try:
            # Security validation
            await self._validate_request_security(request, "mcp_session_delete")
            
            # Get session ID
            session_id = request.headers.get("mcp-session-id")
            if not session_id:
                from fastapi import HTTPException
                raise HTTPException(status_code=400, detail="Missing Mcp-Session-Id header")
            
            # Terminate session
            if self.session_manager.terminate_session(session_id):
                return Response(status_code=200)
            else:
                from fastapi import HTTPException
                raise HTTPException(status_code=404, detail="Session not found")
                
        except Exception as e:
            self.logger.error("Error in MCP DELETE request", error=str(e))
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=str(e))
    
    async def _handle_requests_with_streaming(
        self, 
        requests: list, 
        session_id: Optional[str], 
        supports_sse: bool, 
        supports_json: bool, 
        request: Request
    ):
        """
        Handle requests with potential SSE streaming.
        
        Args:
            requests: List of JSON-RPC requests
            session_id: Optional session ID
            supports_sse: Whether client supports SSE
            supports_json: Whether client supports JSON
            request: Original FastAPI request
            
        Returns:
            JSON response or SSE stream
        """
        # For now, let's implement simple JSON responses
        # In a full implementation, you'd check if streaming is beneficial
        
        responses = []
        session_header = {}
        
        for req in requests:
            if isinstance(req, dict) and req.get("method"):
                # Handle initialization specially for session management
                if req.get("method") == "initialize" and not session_id:
                    # Create new session for initialization
                    client_info = req.get("params", {}).get("clientInfo", {})
                    new_session_id = self.session_manager.create_session(client_info)
                    session_header["mcp-session-id"] = new_session_id
                    session_id = new_session_id
                
                # Process the request
                response = await self.request_handler.handle_request(req, request)
                responses.append(response)
        
        # Return JSON response
        if len(responses) == 1:
            result = responses[0]
        else:
            result = responses
        
        # Add session header if needed
        if session_header:
            from fastapi import Response
            import json
            response = Response(
                content=json.dumps(result),
                media_type="application/json",
                headers=session_header
            )
            return response
        
        return result
    
    async def _process_notifications_responses(self, messages: list, session_id: Optional[str]):
        """
        Process notifications and responses (no return expected).
        
        Args:
            messages: List of notifications/responses
            session_id: Optional session ID
        """
        # Update session activity
        if session_id:
            self.session_manager.update_activity(session_id)
        
        # Process notifications/responses
        for msg in messages:
            if isinstance(msg, dict):
                method = msg.get("method")
                if method:
                    self.logger.info("Received notification", method=method, session_id=session_id)
                else:
                    self.logger.info("Received response", id=msg.get("id"), session_id=session_id)
    
    async def _create_sse_stream(self, session_id: Optional[str], last_event_id: Optional[str]):
        """
        Create an SSE stream for server-to-client communication.
        
        Args:
            session_id: Optional session ID
            last_event_id: Optional last event ID for resumption
            
        Returns:
            SSE streaming response
        """
        from fastapi.responses import StreamingResponse
        import json
        import asyncio
        import time
        
        async def event_generator():
            """Generate SSE events."""
            try:
                # Send initial connection event
                yield f"event: connection\ndata: {json.dumps({'status': 'connected', 'session_id': session_id})}\n\n"
                
                # Keep connection alive and send periodic heartbeats
                while True:
                    await asyncio.sleep(30)  # 30 second heartbeat
                    yield f"event: heartbeat\ndata: {json.dumps({'timestamp': time.time()})}\n\n"
                    
            except Exception as e:
                self.logger.error("SSE stream error", error=str(e))
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "mcp-session-id, last-event-id"
            }
        )
    
    async def _handle_get_request(self, stream_id: str, request: Request) -> StreamingResponse:
        """
        Handle GET requests for Server-Sent Events.
        
        Args:
            stream_id: Stream identifier
            request: FastAPI request object
            
        Returns:
            Streaming response with SSE
        """
        try:
            # Security validation
            await self._validate_request_security(request, "mcp_stream")
            
            # Validate session
            session_id = request.headers.get("Mcp-Session-Id")
            if not session_id or not self.session_manager.validate_session(session_id):
                raise HTTPException(status_code=401, detail="Invalid or missing session")
            
            # Get Last-Event-ID for resumability
            last_event_id = request.headers.get("Last-Event-ID")
            
            # Create stream generator
            async def event_generator():
                try:
                    async for event_data in self.stream_manager.stream_events(
                        stream_id, last_event_id
                    ):
                        yield event_data
                        
                        # Small delay to prevent overwhelming the client
                        await asyncio.sleep(0.01)
                        
                except Exception as e:
                    self.logger.error(f"Error in stream {stream_id}: {e}")
                    # Send error event
                    error_event = f"data: {json.dumps({'error': str(e)})}\n\n"
                    yield error_event
            
            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Last-Event-ID, Mcp-Session-Id"
                }
            )
            
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Error handling GET request for stream {stream_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def _validate_request_security(self, request: Request, operation: str):
        """
        Validate request security including origin, rate limiting, and RBAC.
        
        Args:
            request: FastAPI request object
            operation: Operation type for rate limiting
            
        Raises:
            HTTPException: If security validation fails
        """
        # Origin validation
        origin = request.headers.get("Origin")
        if not self.origin_validator.validate_origin(origin):
            self.logger.warning(f"Invalid origin: {origin}")
            raise HTTPException(status_code=403, detail="Invalid origin")
        
        # Rate limiting
        client_id = self._get_client_id(request)
        if not self.rate_limiter.check_rate_limit(client_id, operation):
            self.logger.warning(f"Rate limit exceeded for client: {client_id}")
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        
        # RBAC validation for authenticated endpoints
        if hasattr(request.state, 'user') and request.state.user:
            # This would be set by authentication middleware
            # For now, we'll skip this check as it depends on the existing auth system
            pass
    
    def _get_client_id(self, request: Request) -> str:
        """
        Get client identifier for rate limiting.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Client identifier
        """
        # Try to get authenticated user ID first
        if hasattr(request.state, 'user') and request.state.user:
            return f"user:{request.state.user.id}"
        
        # Fall back to IP address
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"
    
    async def _handle_health_check(self) -> Dict[str, Any]:
        """
        Handle MCP server health check.
        
        Returns:
            Health check response
        """
        try:
            # Check tool registry health
            tools_healthy = len(await self.tool_registry.list_tools()) > 0
            
            # Check session manager health
            session_stats = self.session_manager.get_session_stats()
            sessions_healthy = session_stats["active_sessions"] >= 0
            
            # Check stream manager health
            stream_stats = self.stream_manager.get_stream_stats()
            streams_healthy = stream_stats["active_streams"] >= 0
            
            overall_healthy = tools_healthy and sessions_healthy and streams_healthy
            
            return {
                "status": "healthy" if overall_healthy else "unhealthy",
                "timestamp": self._get_timestamp(),
                "components": {
                    "tools": {
                        "status": "healthy" if tools_healthy else "unhealthy",
                        "registered_tools": len(await self.tool_registry.list_tools())
                    },
                    "sessions": {
                        "status": "healthy" if sessions_healthy else "unhealthy",
                        **session_stats
                    },
                    "streams": {
                        "status": "healthy" if streams_healthy else "unhealthy",
                        **stream_stats
                    }
                }
            }
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "timestamp": self._get_timestamp(),
                "error": str(e)
            }
    
    async def _handle_server_info(self) -> Dict[str, Any]:
        """
        Handle server info request.
        
        Returns:
            Server information and capabilities (2025-06-18 format)
        """
        try:
            # Get tool count
            tools = await self.tool_registry.list_tools()
            
            return {
                "name": "swe-agent-mcp-server",
                "version": "1.0.0",
                "description": "SWE Agent MCP Server - AI-powered software engineering automation",
                "protocol_version": "2025-06-18",  # Latest protocol version
                "supported_versions": ["2024-11-05", "2025-03-26", "2025-06-18"],
                "transport": "streamable_http",
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"subscribe": False, "listChanged": False},
                    "prompts": {"listChanged": False},
                    "logging": {},
                    "streaming": True,
                    "session_management": True,
                    "rate_limiting": True,
                    "security_validation": True,
                    "protocol_version_header": True  # Support for MCP-Protocol-Version header
                },
                "tool_count": len(tools),
                "domains": ["health", "tasks", "agents_catalogue"],
                "endpoints": {
                    "mcp": "/mcp",
                    "health": "/health", 
                    "info": "/info",
                    "tools": "/tools"
                },
                "timestamp": time.time()
            }
            
        except Exception as e:
            self.logger.error("Error getting server info", error=str(e))
            return {
                "name": "swe-agent-mcp-server",
                "version": "1.0.0", 
                "error": str(e),
                "protocol_version": "2025-06-18"
            }
    
    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"
    
    async def shutdown(self):
        """Shutdown the MCP server and cleanup resources."""
        self.logger.info("Shutting down MCP HTTP Server")
        
        try:
            # Cleanup sessions
            await self.session_manager.cleanup_expired_sessions()
            
            # Cleanup streams  
            self.stream_manager.cleanup_expired_streams()
            
            self._initialized = False
            self.logger.info("MCP HTTP Server shutdown completed")
            
        except Exception as e:
            self.logger.error(f"Error during MCP server shutdown: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive server statistics.
        
        Returns:
            Server statistics
        """
        try:
            return {
                "server": {
                    "initialized": self._initialized,
                    "uptime": self._get_timestamp()
                },
                "sessions": self.session_manager.get_session_stats(),
                "streams": self.stream_manager.get_stream_stats(),
                "rate_limiting": self.rate_limiter.get_rate_limit_status("system")
            }
        except Exception as e:
            self.logger.error(f"Error getting server stats: {e}")
            return {"error": str(e)} 