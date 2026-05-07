"""
MCP Transport Configuration.

This module provides configuration for MCP transport mechanisms including
HTTP, Server-Sent Events (SSE), and streaming parameters.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class TransportType(str, Enum):
    """MCP transport types."""
    HTTP = "http"
    SSE = "sse"
    STREAMABLE_HTTP = "streamable_http"


class CompressionType(str, Enum):
    """Compression types for transport."""
    NONE = "none"
    GZIP = "gzip"
    DEFLATE = "deflate"


class TransportConfig(BaseModel):
    """
    Configuration for MCP transport mechanisms.
    
    This class defines settings for HTTP transport, Server-Sent Events,
    and streaming parameters used by the MCP server.
    """
    
    # HTTP Transport Settings
    transport_type: TransportType = Field(
        TransportType.STREAMABLE_HTTP,
        description="Primary transport mechanism"
    )
    
    http_enabled: bool = Field(True, description="Enable HTTP transport")
    http_timeout: int = Field(30, description="HTTP request timeout in seconds")
    http_max_request_size: int = Field(10 * 1024 * 1024, description="Maximum HTTP request size in bytes")
    http_compression: CompressionType = Field(CompressionType.GZIP, description="HTTP compression type")
    
    # Server-Sent Events Settings
    sse_enabled: bool = Field(True, description="Enable Server-Sent Events")
    sse_keepalive_interval: int = Field(30, description="SSE keepalive interval in seconds")
    sse_reconnect_interval: int = Field(3, description="SSE reconnect interval in seconds")
    sse_max_reconnect_attempts: int = Field(10, description="Maximum SSE reconnect attempts")
    
    # Streaming Settings
    stream_enabled: bool = Field(True, description="Enable streaming support")
    stream_timeout: int = Field(3600, description="Stream timeout in seconds")
    stream_buffer_size: int = Field(8192, description="Stream buffer size in bytes")
    max_events_per_stream: int = Field(1000, description="Maximum events per stream")
    stream_cleanup_interval: int = Field(300, description="Stream cleanup interval in seconds")
    
    # Session Settings
    session_enabled: bool = Field(True, description="Enable session management")
    session_timeout: int = Field(3600, description="Session timeout in seconds")
    session_cleanup_interval: int = Field(300, description="Session cleanup interval in seconds")
    max_concurrent_sessions: int = Field(1000, description="Maximum concurrent sessions")
    
    # Performance Settings
    max_concurrent_requests: int = Field(100, description="Maximum concurrent requests")
    request_queue_size: int = Field(1000, description="Request queue size")
    response_cache_enabled: bool = Field(False, description="Enable response caching")
    response_cache_ttl: int = Field(300, description="Response cache TTL in seconds")
    
    # Security Settings
    cors_enabled: bool = Field(True, description="Enable CORS support")
    cors_max_age: int = Field(3600, description="CORS preflight max age in seconds")
    request_id_header: str = Field("X-Request-ID", description="Request ID header name")
    session_id_header: str = Field("Mcp-Session-Id", description="Session ID header name")
    
    @field_validator('http_max_request_size')
    @classmethod
    def validate_max_request_size(cls, v):
        """Validate maximum request size."""
        if v < 1024:  # Minimum 1KB
            raise ValueError("Maximum request size must be at least 1KB")
        if v > 100 * 1024 * 1024:  # Maximum 100MB
            raise ValueError("Maximum request size cannot exceed 100MB")
        return v
    
    @field_validator('max_events_per_stream')
    @classmethod
    def validate_max_events_per_stream(cls, v):
        """Validate maximum events per stream."""
        if v < 10:
            raise ValueError("Maximum events per stream must be at least 10")
        if v > 10000:
            raise ValueError("Maximum events per stream cannot exceed 10,000")
        return v
    
    @field_validator('max_concurrent_sessions')
    @classmethod
    def validate_max_concurrent_sessions(cls, v):
        """Validate maximum concurrent sessions."""
        if v < 1:
            raise ValueError("Maximum concurrent sessions must be at least 1")
        if v > 100000:
            raise ValueError("Maximum concurrent sessions cannot exceed 100,000")
        return v
    
    def get_http_headers(self) -> Dict[str, str]:
        """
        Get default HTTP headers for transport.
        
        Returns:
            Dictionary of HTTP headers
        """
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block"
        }
        
        if self.http_compression != CompressionType.NONE:
            headers["Accept-Encoding"] = self.http_compression.value
        
        return headers
    
    def get_sse_headers(self) -> Dict[str, str]:
        """
        Get default SSE headers for transport.
        
        Returns:
            Dictionary of SSE headers
        """
        headers = {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable proxy buffering
        }
        
        if self.cors_enabled:
            headers.update({
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": f"Last-Event-ID, {self.session_id_header}",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Max-Age": str(self.cors_max_age)
            })
        
        return headers
    
    def get_cors_headers(self, origin: Optional[str] = None) -> Dict[str, str]:
        """
        Get CORS headers for transport.
        
        Args:
            origin: Request origin
            
        Returns:
            Dictionary of CORS headers
        """
        if not self.cors_enabled:
            return {}
        
        headers = {
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": f"Content-Type, Authorization, {self.session_id_header}, {self.request_id_header}",
            "Access-Control-Max-Age": str(self.cors_max_age),
            "Access-Control-Allow-Credentials": "true"
        }
        
        if origin:
            headers["Access-Control-Allow-Origin"] = origin
        else:
            headers["Access-Control-Allow-Origin"] = "*"
        
        return headers
    
    def get_stream_config(self) -> Dict[str, Any]:
        """
        Get streaming configuration parameters.
        
        Returns:
            Dictionary of streaming configuration
        """
        return {
            "timeout": self.stream_timeout,
            "buffer_size": self.stream_buffer_size,
            "max_events": self.max_events_per_stream,
            "cleanup_interval": self.stream_cleanup_interval,
            "keepalive_interval": self.sse_keepalive_interval,
            "reconnect_interval": self.sse_reconnect_interval,
            "max_reconnect_attempts": self.sse_max_reconnect_attempts
        }
    
    def get_session_config(self) -> Dict[str, Any]:
        """
        Get session management configuration parameters.
        
        Returns:
            Dictionary of session configuration
        """
        return {
            "enabled": self.session_enabled,
            "timeout": self.session_timeout,
            "cleanup_interval": self.session_cleanup_interval,
            "max_concurrent": self.max_concurrent_sessions,
            "header_name": self.session_id_header
        }
    
    def get_performance_config(self) -> Dict[str, Any]:
        """
        Get performance configuration parameters.
        
        Returns:
            Dictionary of performance configuration
        """
        return {
            "max_concurrent_requests": self.max_concurrent_requests,
            "request_queue_size": self.request_queue_size,
            "http_timeout": self.http_timeout,
            "max_request_size": self.http_max_request_size,
            "compression": self.http_compression.value,
            "response_cache_enabled": self.response_cache_enabled,
            "response_cache_ttl": self.response_cache_ttl
        }
    
    def is_streamable_transport(self) -> bool:
        """
        Check if transport supports streaming.
        
        Returns:
            True if transport supports streaming
        """
        return self.transport_type == TransportType.STREAMABLE_HTTP and self.sse_enabled
    
    def is_session_management_enabled(self) -> bool:
        """
        Check if session management is enabled.
        
        Returns:
            True if session management is enabled
        """
        return self.session_enabled
    
    def validate_configuration(self) -> tuple[bool, list[str]]:
        """
        Validate the transport configuration.
        
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        # Check transport consistency
        if self.transport_type == TransportType.STREAMABLE_HTTP and not self.sse_enabled:
            errors.append("Streamable HTTP transport requires SSE to be enabled")
        
        if not self.http_enabled and not self.sse_enabled:
            errors.append("At least one transport mechanism must be enabled")
        
        # Check timeout consistency
        if self.session_timeout < self.stream_timeout:
            errors.append("Session timeout should be >= stream timeout")
        
        # Check cleanup intervals
        if self.session_cleanup_interval > self.session_timeout:
            errors.append("Session cleanup interval should be <= session timeout")
        
        if self.stream_cleanup_interval > self.stream_timeout:
            errors.append("Stream cleanup interval should be <= stream timeout")
        
        return len(errors) == 0, errors 