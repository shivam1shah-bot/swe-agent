"""
Basic Authentication Middleware for FastAPI.

Validates HTTP Basic Authentication for API requests.
"""

from typing import Callable, Dict, Any, Optional
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.providers.auth import BasicAuthProvider
from src.providers.logger import Logger
from src.utils.jwt import verify_token


class BasicAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle HTTP Authentication (Basic Auth and Bearer Token).

    Validates authorization header and sets user info in request state.
    Supports both Basic Auth (legacy) and Bearer JWT (new).
    """

    def __init__(self, app, excluded_paths: Optional[list] = None):
        """
        Initialize the auth middleware.
        
        Args:
            app: FastAPI application instance
            excluded_paths: List of paths to exclude from authentication
        """
        super().__init__(app)
        self.auth_provider = BasicAuthProvider()
        self.logger = Logger("AuthMiddleware")
        
        # Default excluded paths - health checks, docs, metrics, and auth endpoints
        self.excluded_paths = excluded_paths or [
            "/",
            "/api/v1/health",
            "/api/v1/auth/login",                    # Allow login without auth
            "/api/v1/auth/google_oauth/callback",    # Allow OAuth callback without auth
            "/api/v1/auth/status",                   # Allow auth status checks without auth
            "/api/v1/external_metrics/claude_plugins",  # Allow plugin metrics from external clients (Claude Code plugins)
            "/docs",
            "/redoc",
            "/openapi.json",
            "/favicon.ico",
            "/metrics",  # Prometheus metrics endpoint - should be publicly accessible
            "/metrics/",  # Support both with and without trailing slash
            "/api/v1/slack",  # Slack webhooks - verified via HMAC signature, not Basic Auth
            "/api/v1/pulse/ingest",  # Pulse CLI clients send data without user tokens
            "/api/v1/pulse/health",  # Pulse health check — public like /api/v1/health
        ]
        
        self.logger.info(f"Auth middleware initialized with {len(self.excluded_paths)} excluded paths")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request through auth middleware.
        
        Args:
            request: FastAPI request object
            call_next: Next middleware/handler in chain
            
        Returns:
            Response from downstream or auth error response
        """
        # Skip authentication for excluded paths
        if self._should_skip_auth(request):
            return await call_next(request)
        
        # Skip authentication if disabled in config
        if not self.auth_provider.is_auth_enabled():
            self.logger.debug("Authentication disabled in config - skipping auth check")
            return await call_next(request)
        
        # Get authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return self._create_auth_error_response("Missing Authorization header")
        
        # Check for Bearer token (JWT)
        scheme_token = auth_header.strip().split(None, 1)
        if scheme_token and len(scheme_token) == 2 and scheme_token[0].lower() == "bearer":
            token = scheme_token[1].strip()
            if not token:
                return self._create_auth_error_response("Missing bearer token")

            payload = verify_token(token)
            
            if payload:
                # Valid JWT token (email-based authentication)
                user_info = {
                    "username": payload.get("sub"),
                    "email": payload.get("sub"),
                    "role": payload.get("role", "user")
                }
                request.state.current_user = user_info
                self.logger.debug(f"Request authenticated with JWT for user: {user_info['email']}")
                return await call_next(request)
            else:
                self.logger.warning("Bearer token verification failed (invalid or expired)")
                return self._create_auth_error_response("Invalid or expired token")
        
        # Fallback to Basic Auth (legacy - only for admin and mcp_read_user)
        user_info = self.auth_provider.validate_auth_header(auth_header)
        if not user_info:
            return self._create_auth_error_response("Invalid credentials")
        
        # Block Basic Auth for dashboard users - they must use SSO
        if user_info.get("username") == "dashboard":
            self.logger.debug("Basic Auth rejected for dashboard user - SSO required")
            return self._create_sso_required_response()
        
        # Set user info in request state for downstream handlers
        request.state.current_user = user_info
        
        # Log successful authentication
        self.logger.debug(f"Request authenticated with Basic Auth for user: {user_info['username']} ({user_info['role']})")
        
        # Continue to next middleware/handler
        response = await call_next(request)
        return response

    
    def _should_skip_auth(self, request: Request) -> bool:
        """
        Check if authentication should be skipped for this request.
        
        Args:
            request: FastAPI request object
            
        Returns:
            True if auth should be skipped, False otherwise
        """
        # Always skip authentication for OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return True
            
        path = request.url.path
        
        # Check exact matches first
        if path in self.excluded_paths:
            return True
        
        # For prefix matching, avoid the root path "/" issue
        # Only do prefix matching for paths that are not "/"
        for excluded_path in self.excluded_paths:
            if excluded_path != "/" and path.startswith(excluded_path):
                return True
        
        return False
    
    def _create_auth_error_response(self, message: str) -> JSONResponse:
        """
        Create a standardized authentication error response.
        
        Args:
            message: Error message to include
            
        Returns:
            JSON response with 401 status
        """
        self.logger.warning(f"Authentication failed: {message}")
        
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "detail": "Authentication required",
                "message": message,
                "error_type": "authentication_error"
            },
            headers={"WWW-Authenticate": "Basic"}
        )
    
    def _create_sso_required_response(self) -> JSONResponse:
        """
        Create a response indicating SSO login is required.
        
        Returns:
            JSON response with 401 status indicating SSO is required
        """
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "detail": "SSO login required",
                "message": "Dashboard access requires SSO. Please login via the web UI at /login",
                "error_type": "sso_required"
            },
            headers={"WWW-Authenticate": "Bearer"}
        ) 