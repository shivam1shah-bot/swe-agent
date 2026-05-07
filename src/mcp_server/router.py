"""
MCP Router.

This module provides the FastAPI router for MCP protocol endpoints.
All endpoints proxy requests to the SWE Agent API service via HTTP.
"""

import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, Depends, HTTPException, Response
from fastapi.responses import JSONResponse, StreamingResponse

from .dependencies import get_api_client
from .clients.api_client import SWEAgentAPIClient, APIConnectionError, APIAuthenticationError, APIClientError
from .server.http_server import MCPHttpServer
from .tools.registry import MCPToolRegistry

# Create router
router = APIRouter()

# Global MCP server instance
_mcp_server: Optional[MCPHttpServer] = None


async def get_mcp_server(
    request: Request,
    api_client: SWEAgentAPIClient = Depends(get_api_client)
) -> MCPHttpServer:
    """
    Get or create MCP server instance with API client.
    
    Args:
        request: FastAPI request object to get app instance
        api_client: API client dependency
        
    Returns:
        MCPHttpServer instance
    """
    global _mcp_server
    if _mcp_server is None:
        # Create tool registry with API client
        tool_registry = MCPToolRegistry(api_client)
        
        # Create MCP server with FastAPI app instance
        _mcp_server = MCPHttpServer(request.app)
        _mcp_server.tool_registry = tool_registry
        await _mcp_server.initialize()
    
    return _mcp_server


@router.post("/mcp")
async def handle_mcp_post(
    request: Request,
    mcp_server: MCPHttpServer = Depends(get_mcp_server)
) -> Dict[str, Any]:
    """
    Handle MCP JSON-RPC requests via POST according to Streamable HTTP specification.
    
    Implements 2025-06-18 protocol version with MCP-Protocol-Version header support.
    
    This endpoint processes JSON-RPC requests and returns either:
    - 202 Accepted for notifications/responses
    - JSON response for single requests 
    - SSE stream for complex requests (when client supports it)
    
    Args:
        request: FastAPI request object
        mcp_server: MCP server dependency
        
    Returns:
        JSON response, 202 status, or SSE stream
    """
    try:
        # Validate MCP-Protocol-Version header (required per 2025-06-18 spec)
        protocol_version = request.headers.get("mcp-protocol-version")
        if protocol_version and protocol_version not in ["2024-11-05", "2025-03-26", "2025-06-18"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported MCP protocol version: {protocol_version}"
            )
        
        # Validate Accept header
        accept_header = request.headers.get("accept", "")
        supports_sse = "text/event-stream" in accept_header
        supports_json = "application/json" in accept_header
        
        if not supports_json and not supports_sse:
            raise HTTPException(
                status_code=400,
                detail="Must accept application/json or text/event-stream"
            )
        
        # Get session ID from header
        session_id = request.headers.get("mcp-session-id")
        
        # Validate session if provided
        if session_id and not mcp_server.session_manager.validate_session(session_id):
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Parse request body
        try:
            request_data = await request.json()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
        
        # Handle different message types according to MCP spec
        if isinstance(request_data, list):
            # Batched messages - not supported in 2025-06-18 for single requests
            # Each message must be a separate POST per the spec
            raise HTTPException(
                status_code=400, 
                detail="Batched requests not supported - send each as separate POST"
            )
        
        elif isinstance(request_data, dict):
            # Single message
            method = request_data.get("method")
            has_id = "id" in request_data
            
            if method and has_id:
                # Request with ID - return response
                return await _handle_requests([request_data], session_id, supports_sse, mcp_server, request)
            elif method and not has_id:
                # Notification (no ID) - return 202
                await _process_notifications([request_data], session_id, mcp_server)
                return Response(status_code=202)
            else:
                # Response - return 202
                await _process_notifications([request_data], session_id, mcp_server)
                return Response(status_code=202)
        
        else:
            raise HTTPException(status_code=400, detail="Invalid request format")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mcp")
async def handle_mcp_get(
    request: Request,
    mcp_server: MCPHttpServer = Depends(get_mcp_server)
) -> StreamingResponse:
    """
    Handle MCP SSE stream requests via GET according to Streamable HTTP specification.
    
    Opens a Server-Sent Events stream for server-to-client communication.
    
    Args:
        request: FastAPI request object
        mcp_server: MCP server dependency
        
    Returns:
        SSE streaming response or 405 Method Not Allowed
    """
    try:
        # Validate Accept header
        accept_header = request.headers.get("accept", "")
        if "text/event-stream" not in accept_header:
            raise HTTPException(status_code=405, detail="Method Not Allowed")
        
        # Get session ID
        session_id = request.headers.get("mcp-session-id")
        
        # Validate session if provided
        if session_id and not mcp_server.session_manager.validate_session(session_id):
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get resumption info
        last_event_id = request.headers.get("last-event-id")
        
        # Create SSE stream
        return await _create_sse_stream(session_id, last_event_id, mcp_server)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/mcp")
async def handle_mcp_delete(
    request: Request,
    mcp_server: MCPHttpServer = Depends(get_mcp_server)
) -> Response:
    """
    Handle MCP session termination via DELETE.
    
    Args:
        request: FastAPI request object
        mcp_server: MCP server dependency
        
    Returns:
        200 OK or error response
    """
    try:
        # Get session ID
        session_id = request.headers.get("mcp-session-id")
        if not session_id:
            raise HTTPException(status_code=400, detail="Missing Mcp-Session-Id header")
        
        # Terminate session
        if mcp_server.session_manager.terminate_session(session_id):
            return Response(status_code=200)
        else:
            raise HTTPException(status_code=404, detail="Session not found")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_requests(
    requests: list, 
    session_id: Optional[str], 
    supports_sse: bool, 
    mcp_server: MCPHttpServer, 
    request: Request
) -> Any:
    """Handle JSON-RPC requests with session management."""
    responses = []
    new_session_id = session_id
    session_headers = {}
    
    for req in requests:
        if isinstance(req, dict) and req.get("method"):
            # Handle initialization specially
            if req.get("method") == "initialize" and not session_id:
                client_info = req.get("params", {}).get("clientInfo", {})
                new_session_id = mcp_server.session_manager.create_session(client_info)
                session_headers["mcp-session-id"] = new_session_id
            
            # Process request through handler
            response = await mcp_server.request_handler.handle_request(req, request)
            responses.append(response)
    
    # Return response with session header if needed
    if len(responses) == 1:
        result = responses[0]
    else:
        result = responses
    
    if session_headers:
        return Response(
            content=json.dumps(result),
            media_type="application/json",
            headers=session_headers
        )
    
    return result


async def _process_notifications(
    messages: list, 
    session_id: Optional[str], 
    mcp_server: MCPHttpServer
):
    """Process notifications and responses."""
    if session_id:
        mcp_server.session_manager.update_activity(session_id)
    
    # Process each notification/response
    for msg in messages:
        if isinstance(msg, dict):
            method = msg.get("method")
            if method:
                # It's a notification - handle through request handler
                await mcp_server.request_handler.handle_request(msg, None)
            else:
                # It's a response
                pass  # Handle response logic here


async def _create_sse_stream(
    session_id: Optional[str], 
    last_event_id: Optional[str], 
    mcp_server: MCPHttpServer
) -> StreamingResponse:
    """Create SSE stream for server-to-client communication."""
    
    async def event_generator():
        """Generate SSE events."""
        try:
            # Send connection event
            connection_data = {
                "status": "connected",
                "session_id": session_id,
                "timestamp": time.time()
            }
            yield f"event: connection\ndata: {json.dumps(connection_data)}\n\n"
            
            # Send periodic heartbeats
            import asyncio
            while True:
                await asyncio.sleep(30)  # 30 second heartbeat
                heartbeat_data = {"timestamp": time.time()}
                yield f"event: heartbeat\ndata: {json.dumps(heartbeat_data)}\n\n"
                
        except Exception as e:
            error_data = {"error": str(e)}
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
    
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


@router.get("/health")
async def mcp_health(
    api_client: SWEAgentAPIClient = Depends(get_api_client)
) -> Dict[str, Any]:
    """
    MCP service health check.
    
    Tests connectivity to the API service and returns overall health status.
    
    Args:
        api_client: API client dependency
        
    Returns:
        Health status response
    """
    try:
        # Test API service connectivity
        api_health = await api_client.get_health()
        
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mcp_service": "running",
            "api_service": "connected",
            "api_health": api_health,
            "components": {
                "http_client": "healthy",
                "tool_registry": "healthy"
            }
        }
        
    except APIConnectionError as e:
        return {
            "status": "unhealthy",
            "error": "API service unreachable",
            "detail": str(e),
            "mcp_service": "running",
            "api_service": "disconnected"
        }
    except APIAuthenticationError as e:
        return {
            "status": "unhealthy", 
            "error": "API authentication failed",
            "detail": str(e),
            "mcp_service": "running",
            "api_service": "auth_failed"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": "Unexpected error",
            "detail": str(e)
        }


@router.get("/info")
async def mcp_info(
    mcp_server: MCPHttpServer = Depends(get_mcp_server)
) -> Dict[str, Any]:
    """
    Get MCP server information and capabilities.
    
    Provides metadata about the MCP server including supported capabilities,
    protocol version, and available tools summary.
    
    Args:
        mcp_server: MCP server dependency
        
    Returns:
        Server information response
    """
    try:
        if hasattr(mcp_server, '_handle_server_info'):
            return await mcp_server._handle_server_info()
        else:
            # Fallback server info with latest protocol version
            tools = await mcp_server.tool_registry.list_tools()
            return {
                "name": "swe-agent-mcp-server",
                "version": "1.0.0",
                "protocol_version": "2025-06-18",  # Latest protocol version
                "supported_versions": ["2024-11-05", "2025-03-26", "2025-06-18"],
                "description": "SWE Agent MCP Server - HTTP proxy to SWE Agent API",
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"subscribe": False, "listChanged": False},
                    "prompts": {"listChanged": False},
                    "logging": {}
                },
                "tool_count": len(tools),
                "transport": "streamable_http",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools")
async def list_mcp_tools(
    mcp_server: MCPHttpServer = Depends(get_mcp_server)
) -> Dict[str, Any]:
    """
    List all available MCP tools.
    
    Returns a complete list of MCP tools with their schemas and descriptions.
    
    Args:
        mcp_server: MCP server dependency
        
    Returns:
        Tools list in MCP format
    """
    try:
        tools = await mcp_server.tool_registry.list_tools()
        return {
            "tools": tools,
            "total_count": len(tools),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 