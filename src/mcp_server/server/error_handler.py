"""
MCP Error Handler for converting API errors to MCP JSON-RPC format.

Provides consistent error formatting according to JSON-RPC 2.0 specification
with MCP-specific error codes and user-friendly messages.
"""

import traceback
from typing import Dict, Any, Optional, Union
from fastapi import HTTPException
from pydantic import ValidationError

from src.providers.logger import Logger


class MCPErrorCodes:
    """Standard JSON-RPC and MCP-specific error codes."""
    
    # Standard JSON-RPC errors
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    
    # MCP-specific errors (server error range: -32000 to -32099)
    AUTH_FAILED = -32000
    FORBIDDEN = -32001
    NOT_FOUND = -32002
    TIMEOUT = -32003
    RATE_LIMITED = -32004
    INVALID_SESSION = -32005
    TOOL_EXECUTION_ERROR = -32006
    VALIDATION_ERROR = -32007


class MCPErrorHandler:
    """
    Handles error conversion from API exceptions to MCP JSON-RPC error format.
    
    Provides consistent error formatting with appropriate error codes,
    user-friendly messages, and detailed error information for debugging.
    """
    
    def __init__(self):
        self.logger = Logger("MCPErrorHandler")
    
    def format_mcp_error(
        self, 
        error: Exception, 
        request_id: Optional[Union[str, int]] = None,
        include_traceback: bool = False
    ) -> Dict[str, Any]:
        """
        Convert an exception to MCP JSON-RPC error format.
        
        Args:
            error: Exception to convert
            request_id: Optional request ID for the error response
            include_traceback: Whether to include traceback in error data
            
        Returns:
            MCP JSON-RPC error response
        """
        error_code, message, data = self._extract_error_info(error, include_traceback)
        
        mcp_error = {
            "jsonrpc": "2.0",
            "error": {
                "code": error_code,
                "message": message,
                "data": data
            },
            "id": request_id
        }
        
        # Log the error for monitoring
        self.logger.error(
            "MCP error occurred",
            error_code=error_code,
            message=message,
            request_id=request_id,
            error_type=type(error).__name__
        )
        
        return mcp_error
    
    def _extract_error_info(self, error: Exception, include_traceback: bool) -> tuple[int, str, Dict[str, Any]]:
        """
        Extract error code, message, and data from exception.
        
        Args:
            error: Exception to extract info from
            include_traceback: Whether to include traceback
            
        Returns:
            Tuple of (error_code, message, data)
        """
        data = {
            "error_type": type(error).__name__,
            "timestamp": self._get_timestamp()
        }
        
        if include_traceback:
            data["traceback"] = traceback.format_exc()
        
        # Handle specific exception types
        if isinstance(error, HTTPException):
            return self._handle_http_exception(error, data)
        elif isinstance(error, ValidationError):
            return self._handle_validation_error(error, data)
        elif isinstance(error, ValueError):
            return self._handle_value_error(error, data)
        elif isinstance(error, PermissionError):
            return self._handle_permission_error(error, data)
        elif isinstance(error, FileNotFoundError):
            return self._handle_not_found_error(error, data)
        elif isinstance(error, TimeoutError):
            return self._handle_timeout_error(error, data)
        else:
            return self._handle_generic_error(error, data)
    
    def _handle_http_exception(self, error: HTTPException, data: Dict[str, Any]) -> tuple[int, str, Dict[str, Any]]:
        """Handle FastAPI HTTPException."""
        data.update({
            "http_status": error.status_code,
            "detail": error.detail
        })
        
        # Map HTTP status codes to JSON-RPC error codes
        code_mapping = {
            400: MCPErrorCodes.INVALID_PARAMS,
            401: MCPErrorCodes.AUTH_FAILED,
            403: MCPErrorCodes.FORBIDDEN,
            404: MCPErrorCodes.NOT_FOUND,
            408: MCPErrorCodes.TIMEOUT,
            422: MCPErrorCodes.VALIDATION_ERROR,
            429: MCPErrorCodes.RATE_LIMITED,
            500: MCPErrorCodes.INTERNAL_ERROR,
            503: MCPErrorCodes.INTERNAL_ERROR
        }
        
        error_code = code_mapping.get(error.status_code, MCPErrorCodes.INTERNAL_ERROR)
        message = self._get_user_friendly_message(error.status_code, str(error.detail))
        
        return error_code, message, data
    
    def _handle_validation_error(self, error: ValidationError, data: Dict[str, Any]) -> tuple[int, str, Dict[str, Any]]:
        """Handle Pydantic ValidationError."""
        data["validation_errors"] = error.errors()
        message = f"Validation failed: {len(error.errors())} error(s)"
        return MCPErrorCodes.VALIDATION_ERROR, message, data
    
    def _handle_value_error(self, error: ValueError, data: Dict[str, Any]) -> tuple[int, str, Dict[str, Any]]:
        """Handle ValueError."""
        data["detail"] = str(error)
        message = "Invalid parameter value provided"
        return MCPErrorCodes.INVALID_PARAMS, message, data
    
    def _handle_permission_error(self, error: PermissionError, data: Dict[str, Any]) -> tuple[int, str, Dict[str, Any]]:
        """Handle PermissionError."""
        data["detail"] = str(error)
        message = "Access denied: insufficient permissions"
        return MCPErrorCodes.FORBIDDEN, message, data
    
    def _handle_not_found_error(self, error: FileNotFoundError, data: Dict[str, Any]) -> tuple[int, str, Dict[str, Any]]:
        """Handle FileNotFoundError."""
        data["detail"] = str(error)
        message = "Requested resource not found"
        return MCPErrorCodes.NOT_FOUND, message, data
    
    def _handle_timeout_error(self, error: TimeoutError, data: Dict[str, Any]) -> tuple[int, str, Dict[str, Any]]:
        """Handle TimeoutError."""
        data["detail"] = str(error)
        message = "Operation timed out"
        return MCPErrorCodes.TIMEOUT, message, data
    
    def _handle_generic_error(self, error: Exception, data: Dict[str, Any]) -> tuple[int, str, Dict[str, Any]]:
        """Handle generic exceptions."""
        data["detail"] = str(error)
        message = "An unexpected error occurred"
        return MCPErrorCodes.INTERNAL_ERROR, message, data
    
    def _get_user_friendly_message(self, status_code: int, detail: str) -> str:
        """
        Get user-friendly error message based on HTTP status code.
        
        Args:
            status_code: HTTP status code
            detail: Error detail
            
        Returns:
            User-friendly error message
        """
        friendly_messages = {
            400: "Invalid request parameters",
            401: "Authentication required",
            403: "Access denied",
            404: "Resource not found", 
            408: "Request timeout",
            422: "Request validation failed",
            429: "Too many requests",
            500: "Internal server error",
            503: "Service unavailable"
        }
        
        base_message = friendly_messages.get(status_code, "An error occurred")
        
        # If detail is user-friendly, include it; otherwise use generic message
        if self._is_user_friendly_detail(detail):
            return f"{base_message}: {detail}"
        else:
            return base_message
    
    def _is_user_friendly_detail(self, detail: str) -> bool:
        """
        Check if error detail is user-friendly (safe to expose).
        
        Args:
            detail: Error detail string
            
        Returns:
            True if detail is safe to expose to users
        """
        # Simple heuristic: avoid exposing internal error messages
        sensitive_indicators = [
            "traceback",
            "internal",
            "database",
            "connection",
            "sql",
            "exception",
            "stack"
        ]
        
        detail_lower = detail.lower()
        return not any(indicator in detail_lower for indicator in sensitive_indicators)
    
    def _get_timestamp(self) -> float:
        """Get current timestamp."""
        import time
        return time.time()
    
    def create_tool_not_found_error(self, tool_name: str, request_id: Optional[Union[str, int]] = None) -> Dict[str, Any]:
        """
        Create a tool not found error.
        
        Args:
            tool_name: Name of the tool that was not found
            request_id: Optional request ID
            
        Returns:
            MCP JSON-RPC error response
        """
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": MCPErrorCodes.METHOD_NOT_FOUND,
                "message": f"Tool '{tool_name}' not found",
                "data": {
                    "error_type": "ToolNotFound",
                    "tool_name": tool_name,
                    "timestamp": self._get_timestamp()
                }
            },
            "id": request_id
        }
    
    def create_invalid_session_error(self, session_id: str, request_id: Optional[Union[str, int]] = None) -> Dict[str, Any]:
        """
        Create an invalid session error.
        
        Args:
            session_id: Invalid session ID
            request_id: Optional request ID
            
        Returns:
            MCP JSON-RPC error response
        """
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": MCPErrorCodes.INVALID_SESSION,
                "message": "Invalid or expired session",
                "data": {
                    "error_type": "InvalidSession",
                    "session_id": session_id,
                    "timestamp": self._get_timestamp()
                }
            },
            "id": request_id
        }
    
    def tool_not_found_error(self, tool_name: str, request_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a tool not found error response.
        
        Args:
            tool_name: Name of the tool that was not found
            request_id: Request ID for error response
            
        Returns:
            JSON-RPC error response
        """
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": MCPErrorCodes.METHOD_NOT_FOUND,
                "message": f"Tool '{tool_name}' not found",
                "data": {
                    "error_type": "ToolNotFound",
                    "tool_name": tool_name,
                    "timestamp": self._get_timestamp()
                }
            },
            "id": request_id
        }
    
    def invalid_session_error(self, session_id: str, request_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create an invalid session error response.
        
        Args:
            session_id: Invalid session ID
            request_id: Request ID for error response
            
        Returns:
            JSON-RPC error response
        """
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": MCPErrorCodes.INVALID_SESSION,
                "message": f"Invalid session ID: {session_id}",
                "data": {
                    "error_type": "InvalidSession",
                    "session_id": session_id,
                    "timestamp": self._get_timestamp()
                }
            },
            "id": request_id
        }
    
    def rate_limit_error(self, client_id: str, request_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a rate limit exceeded error response.
        
        Args:
            client_id: Client ID that exceeded rate limit
            request_id: Request ID for error response
            
        Returns:
            JSON-RPC error response
        """
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": MCPErrorCodes.RATE_LIMITED,
                "message": f"Rate limit exceeded for client: {client_id}",
                "data": {
                    "error_type": "RateLimited",
                    "client_id": client_id,
                    "timestamp": self._get_timestamp()
                }
            },
            "id": request_id
        } 