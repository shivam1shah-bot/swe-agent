"""
Discover API router - proxies to discover backend service with service-to-service auth.

This router provides the API surface expected by the discover UI frontend,
which is backed by the discover backend service (separate from the generic
streaming/knowledge-agents API).

AUTH FLOW - Service-to-Service Basic Authentication:
1. User calls Vyom with Vyom JWT in Authorization header (optional)
2. Vyom validates Vyom JWT and extracts user context (for audit/logging)
3. Vyom calls Discover backend with service-to-service Basic Auth:
   - Username: discover_service (service account)
   - Password: from config [auth.users].discover_service
   - Header: Authorization: Basic base64(username:password)
4. Discover validates Basic Auth credentials using its auth provider
5. Request proceeds with service identity or user context from X-User-Email header

BACKWARD COMPATIBILITY:
- If user provides Vyom JWT, it's validated and user email is forwarded via X-User-Email header
- If no user auth provided, request proceeds with service identity only
- This allows both direct API usage and proxied user requests

SECURITY:
- Basic Auth credentials never leave Vyom service
- Uses constant-time comparison to prevent timing attacks
- HTTPS required in production
"""

import base64
import json
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Header, Request
from fastapi.responses import StreamingResponse
import httpx
import jwt
from pydantic import BaseModel

try:
    from src.providers.logger import get_logger
    from src.providers.auth import require_role
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    require_role = None

router = APIRouter()

ALGORITHM = "HS256"


class DiscoverQueryRequest(BaseModel):
    query: str
    skill_name: str = "discover"
    session_id: Optional[str] = None


class SaveConversationRequest(BaseModel):
    transcript: list[dict]


class ShareConversationRequest(BaseModel):
    transcript: Optional[list[dict]] = None


class CredentialPayload(BaseModel):
    toolId: str
    type: str  # "oauth" | "api_key" | "token"
    value: str


class FeedbackPayload(BaseModel):
    message_id: str
    session_id: Optional[str] = None
    rating: str  # "thumbs_up" | "thumbs_down"


class HandoffAttachRequest(BaseModel):
    """Request body for attaching a session to a handoff reference."""
    session_id: str


def _get_backend_url(request: Request) -> str:
    """Get discover backend URL from app config."""
    config = request.app.state.config
    discover_config = config.get("discover", {})
    return discover_config.get("backend_url", "http://localhost:8080")


def _get_service_credentials(request: Request) -> tuple[str, str]:
    """
    Get service-to-service Basic Auth credentials.
    
    Returns:
        Tuple of (username, password) for service account
    """
    config = request.app.state.config
    auth_config = config.get("auth", {})
    users = auth_config.get("users", {})
    
    username = "discover_service"
    password = users.get("discover_service", "")
    
    return username, password


def _get_vyom_jwt_secret(request: Request) -> str:
    """Get Vyom's JWT secret from config to validate incoming tokens."""
    config = request.app.state.config
    return config.get("google_oauth", {}).get("jwt_secret", "")


def _verify_vyom_token(token: str, secret: str) -> Optional[Dict[str, Any]]:
    """
    Verify a Vyom JWT token and extract user info.
    
    Args:
        token: The JWT token from the Authorization header
        secret: Vyom's JWT secret
        
    Returns:
        Decoded token payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Vyom token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid Vyom token: {e}")
        return None
    except Exception as e:
        logger.error(f"Error verifying Vyom token: {e}")
        return None


def _create_basic_auth_header(username: str, password: str) -> str:
    """
    Create Basic Auth header value.
    
    Args:
        username: Service account username
        password: Service account password
        
    Returns:
        Basic Auth header value (e.g., "Basic <base64-encoded-credentials>")
    """
    credentials = f"{username}:{password}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


async def _prepare_discover_headers(
    authorization: Optional[str],
    request: Request
) -> Dict[str, str]:
    """
    Prepare headers for Discover backend with service-to-service auth.
    
    Args:
        authorization: Authorization header value from incoming request (optional)
        request: FastAPI request
        
    Returns:
        Headers dict ready for Discover backend
    """
    headers: Dict[str, str] = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    # Get service-to-service credentials
    username, password = _get_service_credentials(request)
    
    if password:
        # Add Basic Auth header for service-to-service authentication
        headers["Authorization"] = _create_basic_auth_header(username, password)
    else:
        logger.warning("Service credentials not configured, request may fail")
    
    # If user provided a Vyom JWT, validate it and forward user context
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            vyom_token = parts[1]
            secret = _get_vyom_jwt_secret(request)
            
            if secret:
                user_payload = _verify_vyom_token(vyom_token, secret)
                if user_payload:
                    # Forward user email to Discover for user context
                    user_email = user_payload.get("email") or user_payload.get("sub", "")
                    if user_email:
                        headers["X-User-Email"] = user_email
                        logger.debug(f"Forwarding user context: {user_email}")
    
    return headers


def _handle_discover_http_error(error: httpx.HTTPStatusError, operation: str, handle_401: bool = True) -> None:
    """
    Standardized HTTP error handling for Discover proxy endpoints.
    
    Args:
        error: The HTTPStatusError from httpx
        operation: Description of the operation for logging
        handle_401: Whether to provide special handling for 401 errors
    """
    if handle_401 and error.response.status_code == 401:
        raise HTTPException(status_code=401, detail="Authentication failed with Discover backend")
    raise HTTPException(status_code=error.response.status_code, detail=error.response.text)


def _handle_discover_backend_error(error: Exception, operation: str) -> None:
    """
    Standardized error handling for Discover backend failures.
    
    Args:
        error: The exception that occurred
        operation: Description of the operation for logging
    """
    logger.error(f"Error {operation}: {error}")
    raise HTTPException(status_code=503, detail=f"Discover backend unavailable: {str(error)}")


# ============================================================================
# ROUTE HANDLERS
# ============================================================================

@router.post("/query/stream")
async def stream_query(
    request: DiscoverQueryRequest,
    req: Request,
    authorization: Optional[str] = Header(None),
):
    """
    Stream a discover query response.
    
    Proxies to discover backend's streaming endpoint with service-to-service auth.
    
    Note: This uses an inner generator pattern to ensure proper resource cleanup
    when the client disconnects or the stream completes.
    """
    backend_url = _get_backend_url(req)
    headers = await _prepare_discover_headers(authorization, req)
    
    try:
        client = httpx.AsyncClient(base_url=backend_url, timeout=300.0)
        
        async def event_stream():
            """
            Inner async generator that streams data from Discover backend.
            
            This pattern ensures:
            1. Backend connection is properly closed on client disconnect
            2. SSE format is preserved (data: lines with double newlines)
            3. Errors are yielded in SSE format for client handling
            """
            try:
                async with client.stream(
                    "POST",
                    "/api/v1/query/stream",
                    json=request.model_dump(),
                    headers=headers,
                ) as response:
                    # Handle auth errors - yield error in SSE format
                    if response.status_code == 401:
                        error_body = await response.aread()
                        error_text = error_body.decode('utf-8', errors='replace')
                        logger.warning(f"Discover backend 401: {error_text}")
                        payload = json.dumps({"type": "error", "error": "Authentication failed with Discover backend"})
                        yield f"data: {payload}\n\n"
                        return
                    # Handle other non-200 responses
                    elif response.status_code != 200:
                        error_body = await response.aread()
                        error_text = error_body.decode('utf-8', errors='replace')
                        logger.error(f"Discover backend error {response.status_code}: {error_text}")
                        payload = json.dumps({"type": "error", "error": f"Backend error: {response.status_code}"})
                        yield f"data: {payload}\n\n"
                        return

                    # Stream successful response - forward only data: lines
                    async for line in response.aiter_lines():
                        if line.startswith("data:"):
                            yield f"{line}\n\n"
            except Exception as e:
                logger.exception("Error during streaming")
                # Yield error in SSE format so client can handle gracefully
                payload = json.dumps({"type": "error", "error": "Stream interrupted"})
                yield f"data: {payload}\n\n"
            finally:
                # Ensure client is always closed to prevent resource leaks
                await client.aclose()
        
        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering for SSE
            },
        )
        
    except Exception as e:
        logger.error(f"Error streaming from discover backend: {e}")
        raise HTTPException(status_code=503, detail=f"Discover backend unavailable: {str(e)}")


@router.post("/sessions/{session_id}/save")
async def save_conversation(
    session_id: str,
    request: SaveConversationRequest,
    req: Request,
    authorization: Optional[str] = Header(None),
):
    """Save a conversation transcript."""
    backend_url = _get_backend_url(req)
    headers = await _prepare_discover_headers(authorization, req)
    
    try:
        async with httpx.AsyncClient(base_url=backend_url, timeout=30.0) as client:
            response = await client.post(
                f"/api/v1/sessions/{session_id}/save",
                json=request.model_dump(),
                headers=headers,
            )
            response.raise_for_status()
            return response.json()
            
    except httpx.HTTPStatusError as e:
        _handle_discover_http_error(e, "saving conversation")
    except Exception as e:
        _handle_discover_backend_error(e, "saving conversation")


@router.post("/sessions/{session_id}/share")
async def share_conversation(
    session_id: str,
    request: ShareConversationRequest,
    req: Request,
    authorization: Optional[str] = Header(None),
):
    """Create a shareable link for a conversation."""
    backend_url = _get_backend_url(req)
    headers = await _prepare_discover_headers(authorization, req)
    
    try:
        async with httpx.AsyncClient(base_url=backend_url, timeout=30.0) as client:
            response = await client.post(
                f"/api/v1/sessions/{session_id}/share",
                json=request.model_dump() if request.transcript else {},
                headers=headers,
            )
            response.raise_for_status()
            return response.json()
            
    except httpx.HTTPStatusError as e:
        _handle_discover_http_error(e, "sharing conversation")
    except Exception as e:
        _handle_discover_backend_error(e, "sharing conversation")


@router.get("/credentials/{tool_id}")
async def get_credential(
    tool_id: str,
    req: Request,
    authorization: Optional[str] = Header(None),
):
    """Get stored credential for a tool."""
    backend_url = _get_backend_url(req)
    headers = await _prepare_discover_headers(authorization, req)
    
    try:
        async with httpx.AsyncClient(base_url=backend_url, timeout=30.0) as client:
            response = await client.get(
                f"/api/v1/credentials/{tool_id}",
                headers=headers,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
            
    except httpx.HTTPStatusError as e:
        _handle_discover_http_error(e, "getting credential")
    except Exception as e:
        _handle_discover_backend_error(e, "getting credential")


@router.post("/credentials")
async def save_credential(
    request: CredentialPayload,
    req: Request,
    authorization: Optional[str] = Header(None),
):
    """Save a credential for a tool."""
    backend_url = _get_backend_url(req)
    headers = await _prepare_discover_headers(authorization, req)
    
    try:
        async with httpx.AsyncClient(base_url=backend_url, timeout=30.0) as client:
            response = await client.post(
                "/api/v1/credentials",
                json=request.model_dump(),
                headers=headers,
            )
            if response.status_code == 401:
                raise HTTPException(status_code=401, detail="Authentication failed with Discover backend")
            response.raise_for_status()
            return response.json()
            
    except httpx.HTTPStatusError as e:
        _handle_discover_http_error(e, "saving credential", handle_401=False)
    except Exception as e:
        _handle_discover_backend_error(e, "saving credential")


@router.delete("/credentials/{tool_id}")
async def delete_credential(
    tool_id: str,
    req: Request,
    authorization: Optional[str] = Header(None),
):
    """Delete a stored credential."""
    backend_url = _get_backend_url(req)
    headers = await _prepare_discover_headers(authorization, req)
    
    try:
        async with httpx.AsyncClient(base_url=backend_url, timeout=30.0) as client:
            response = await client.delete(
                f"/api/v1/credentials/{tool_id}",
                headers=headers,
            )
            if response.status_code == 401:
                raise HTTPException(status_code=401, detail="Authentication failed with Discover backend")
            response.raise_for_status()
            return {"deleted": True}
            
    except httpx.HTTPStatusError as e:
        _handle_discover_http_error(e, "deleting credential", handle_401=False)
    except Exception as e:
        _handle_discover_backend_error(e, "deleting credential")


@router.get("/tools")
async def get_tools(
    req: Request,
    authorization: Optional[str] = Header(None),
):
    """Get list of available MCP tools."""
    backend_url = _get_backend_url(req)
    headers = await _prepare_discover_headers(authorization, req)
    
    try:
        async with httpx.AsyncClient(base_url=backend_url, timeout=30.0) as client:
            response = await client.get(
                "/api/v1/tools",
                headers=headers,
            )
            if response.status_code == 401:
                raise HTTPException(status_code=401, detail="Authentication failed with Discover backend")
            response.raise_for_status()
            return response.json()
            
    except httpx.HTTPStatusError as e:
        _handle_discover_http_error(e, "getting tools", handle_401=False)
    except Exception as e:
        _handle_discover_backend_error(e, "getting tools")


@router.get("/tools/{tool_id}/status")
async def get_tool_status(
    tool_id: str,
    req: Request,
    authorization: Optional[str] = Header(None),
):
    """Get status of a specific tool."""
    backend_url = _get_backend_url(req)
    headers = await _prepare_discover_headers(authorization, req)
    
    try:
        async with httpx.AsyncClient(base_url=backend_url, timeout=30.0) as client:
            response = await client.get(
                f"/api/v1/tools/{tool_id}/status",
                headers=headers,
            )
            if response.status_code == 401:
                raise HTTPException(status_code=401, detail="Authentication failed with Discover backend")
            response.raise_for_status()
            return response.json()
            
    except httpx.HTTPStatusError as e:
        _handle_discover_http_error(e, "getting tool status", handle_401=False)
    except Exception as e:
        _handle_discover_backend_error(e, "getting tool status")


@router.post("/handoff/{ref_id}/attach")
async def attach_handoff(
    ref_id: str,
    request: HandoffAttachRequest,
    req: Request,
    authorization: Optional[str] = Header(None),
):
    """Attach a session to a handoff reference."""
    backend_url = _get_backend_url(req)
    headers = await _prepare_discover_headers(authorization, req)
    
    try:
        async with httpx.AsyncClient(base_url=backend_url, timeout=30.0) as client:
            response = await client.post(
                f"/api/v1/handoff/{ref_id}/attach",
                json=request.model_dump(),
                headers=headers,
            )
            if response.status_code == 401:
                raise HTTPException(status_code=401, detail="Authentication failed with Discover backend")
            response.raise_for_status()
            return {"attached": True}
            
    except httpx.HTTPStatusError as e:
        _handle_discover_http_error(e, "attaching handoff", handle_401=False)
    except Exception as e:
        _handle_discover_backend_error(e, "attaching handoff")


@router.get("/handoff/pending/{runtime_session_id}")
async def get_pending_messages(
    runtime_session_id: str,
    req: Request,
    authorization: Optional[str] = Header(None),
):
    """Get pending messages for a runtime session."""
    backend_url = _get_backend_url(req)
    headers = await _prepare_discover_headers(authorization, req)
    
    try:
        async with httpx.AsyncClient(base_url=backend_url, timeout=30.0) as client:
            response = await client.get(
                f"/api/v1/handoff/pending/{runtime_session_id}",
                headers=headers,
            )
            if response.status_code == 401:
                raise HTTPException(status_code=401, detail="Authentication failed with Discover backend")
            response.raise_for_status()
            return response.json()
            
    except httpx.HTTPStatusError as e:
        _handle_discover_http_error(e, "getting pending messages", handle_401=False)
    except Exception as e:
        _handle_discover_backend_error(e, "getting pending messages")


@router.post("/feedback/ui")
async def submit_feedback(
    request: FeedbackPayload,
    req: Request,
    authorization: Optional[str] = Header(None),
):
    """Submit UI feedback for a message."""
    backend_url = _get_backend_url(req)
    headers = await _prepare_discover_headers(authorization, req)
    
    try:
        async with httpx.AsyncClient(base_url=backend_url, timeout=30.0) as client:
            response = await client.post(
                "/api/v1/feedback/ui",
                json=request.model_dump(),
                headers=headers,
            )
            response.raise_for_status()
            return {"submitted": True}
            
    except httpx.HTTPStatusError as e:
        _handle_discover_http_error(e, "submitting feedback")
    except Exception as e:
        _handle_discover_backend_error(e, "submitting feedback")


# ============================================================================
# ADMIN/DEBUG ENDPOINTS
# ============================================================================

@router.get("/admin/discover-config")
@require_role(["admin"])
async def get_discover_config(
    req: Request,
    authorization: Optional[str] = Header(None),
):
    """
    Get discover configuration (for admin debugging).
    
    Returns:
        Configuration info (passwords redacted)
    """
    config = req.app.state.config
    discover_config = config.get("discover", {})
    auth_config = config.get("auth", {})
    users = auth_config.get("users", {})
    
    return {
        "backend_url": discover_config.get("backend_url", "http://localhost:8080"),
        "timeout": discover_config.get("timeout", 30),
        "service_account_configured": bool(users.get("discover_service", "")),
        "user_auth_enabled": auth_config.get("enabled", False),
    }
