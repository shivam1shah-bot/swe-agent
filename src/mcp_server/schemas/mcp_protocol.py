"""
MCP Protocol schema definitions for JSON-RPC 2.0 message structures.

This module defines Pydantic models for all MCP protocol messages including
requests, responses, notifications, and data structures used in the 
Model Context Protocol over Streamable HTTP transport.
"""

from typing import Dict, Any, List, Optional, Union, Literal
from pydantic import BaseModel, Field, field_validator, ValidationInfo
from enum import Enum


class MCPCapability(str, Enum):
    """MCP server capabilities."""
    TOOLS = "tools"
    RESOURCES = "resources"
    PROMPTS = "prompts"
    LOGGING = "logging"


class MCPClientInfo(BaseModel):
    """MCP client information."""
    name: str = Field(..., description="Client name")
    version: str = Field(..., description="Client version") 
    
    
class MCPServerInfo(BaseModel):
    """MCP server information."""
    name: str = Field(..., description="Server name")
    version: str = Field(..., description="Server version")
    description: Optional[str] = Field(None, description="Server description")
    
    
class MCPProtocolVersion(BaseModel):
    """MCP protocol version information."""
    version: str = Field("2025-03-26", description="MCP protocol version")


class MCPInitializeParams(BaseModel):
    """Parameters for the initialize request."""
    protocol_version: MCPProtocolVersion = Field(..., description="Protocol version")
    capabilities: Dict[str, Any] = Field(default_factory=dict, description="Client capabilities")
    client_info: MCPClientInfo = Field(..., description="Client information")


class MCPInitializeResult(BaseModel):
    """Result of the initialize request."""
    protocol_version: MCPProtocolVersion = Field(..., description="Protocol version")
    capabilities: Dict[str, Any] = Field(default_factory=dict, description="Server capabilities")
    server_info: MCPServerInfo = Field(..., description="Server information")


class MCPToolParameter(BaseModel):
    """MCP tool parameter definition."""
    type: str = Field(..., description="Parameter type")
    description: Optional[str] = Field(None, description="Parameter description")
    enum: Optional[List[str]] = Field(None, description="Allowed values for enum types")
    default: Optional[Any] = Field(None, description="Default value")
    minimum: Optional[Union[int, float]] = Field(None, description="Minimum value for numeric types")
    maximum: Optional[Union[int, float]] = Field(None, description="Maximum value for numeric types")
    pattern: Optional[str] = Field(None, description="Regex pattern for string validation")
    minLength: Optional[int] = Field(None, description="Minimum string length")
    maxLength: Optional[int] = Field(None, description="Maximum string length")


class MCPToolInputSchema(BaseModel):
    """MCP tool input schema definition."""
    type: Literal["object"] = Field("object", description="Schema type")
    properties: Dict[str, MCPToolParameter] = Field(default_factory=dict, description="Tool parameters")
    required: List[str] = Field(default_factory=list, description="Required parameters")
    additionalProperties: bool = Field(False, description="Allow additional properties")


class MCPToolAnnotations(BaseModel):
    """MCP tool annotations for additional metadata."""
    title: Optional[str] = Field(None, description="Tool title")
    readOnlyHint: Optional[bool] = Field(None, description="Read-only operation hint")
    openWorldHint: Optional[bool] = Field(None, description="Open world assumption hint")
    domain: Optional[str] = Field(None, description="Tool domain")
    capability: Optional[str] = Field(None, description="Tool capability")
    use_cases: Optional[List[str]] = Field(None, description="Tool use cases")
    preconditions: Optional[List[str]] = Field(None, description="Tool preconditions")


class MCPTool(BaseModel):
    """MCP tool definition."""
    name: str = Field(..., description="Unique tool name")
    description: str = Field(..., description="Tool description")
    inputSchema: MCPToolInputSchema = Field(..., description="Tool input schema")
    annotations: Optional[MCPToolAnnotations] = Field(None, description="Tool annotations")


class MCPToolsListResult(BaseModel):
    """Result of the tools/list request."""
    tools: List[MCPTool] = Field(..., description="List of available tools")


class MCPToolCallParams(BaseModel):
    """Parameters for the tools/call request."""
    name: str = Field(..., description="Tool name to execute")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")


class MCPToolResult(BaseModel):
    """Result of a tool execution."""
    content: List[Dict[str, Any]] = Field(..., description="Tool execution results")
    isError: bool = Field(False, description="Whether the result represents an error")


class MCPNotificationParams(BaseModel):
    """Parameters for MCP notifications."""
    level: Literal["debug", "info", "notice", "warning", "error", "critical", "alert", "emergency"] = Field(
        ..., description="Log level"
    )
    data: Optional[Any] = Field(None, description="Notification data")
    logger: Optional[str] = Field(None, description="Logger name")


class MCPRequest(BaseModel):
    """MCP JSON-RPC 2.0 request."""
    jsonrpc: Literal["2.0"] = Field("2.0", description="JSON-RPC version")
    id: Optional[Union[str, int]] = Field(None, description="Request ID")
    method: str = Field(..., description="Method name")
    params: Optional[Dict[str, Any]] = Field(None, description="Method parameters")


class MCPResponse(BaseModel):
    """MCP JSON-RPC 2.0 response."""
    jsonrpc: Literal["2.0"] = Field("2.0", description="JSON-RPC version")
    id: Optional[Union[str, int]] = Field(None, description="Request ID")
    result: Optional[Any] = Field(None, description="Response result")
    error: Optional[Dict[str, Any]] = Field(None, description="Error information")

    @field_validator('error')
    @classmethod
    def result_or_error(cls, v, info: ValidationInfo):
        """Ensure either result or error is present, but not both."""
        if info.data.get('result') is not None and v is not None:
            raise ValueError('Cannot have both result and error')
        return v


class MCPBatchRequest(BaseModel):
    """MCP JSON-RPC 2.0 batch request."""
    requests: List[MCPRequest] = Field(..., description="Batch of requests")


class MCPBatchResponse(BaseModel):
    """MCP JSON-RPC 2.0 batch response."""
    responses: List[MCPResponse] = Field(..., description="Batch of responses")


class MCPNotification(BaseModel):
    """MCP JSON-RPC 2.0 notification."""
    jsonrpc: Literal["2.0"] = Field("2.0", description="JSON-RPC version")
    method: str = Field(..., description="Notification method")
    params: Optional[Dict[str, Any]] = Field(None, description="Notification parameters")


class MCPPingParams(BaseModel):
    """Parameters for ping request."""
    # Ping typically has no parameters
    pass


class MCPPingResult(BaseModel):
    """Result of ping request."""
    # Ping result is typically empty
    pass


class MCPErrorInfo(BaseModel):
    """MCP error information structure."""
    code: int = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional error data")


class MCPStreamEvent(BaseModel):
    """Server-Sent Event for MCP streaming."""
    id: Optional[str] = Field(None, description="Event ID for resumability")
    event: Optional[str] = Field(None, description="Event type")
    data: str = Field(..., description="Event data (JSON string)")
    retry: Optional[int] = Field(None, description="Retry interval in milliseconds")


class MCPTransportHeaders(BaseModel):
    """HTTP headers specific to MCP Streamable HTTP transport."""
    mcp_session_id: Optional[str] = Field(None, alias="Mcp-Session-Id", description="MCP session identifier")
    last_event_id: Optional[str] = Field(None, alias="Last-Event-ID", description="Last received event ID for resumability")
    content_type: str = Field("application/json", alias="Content-Type", description="Content type")
    accept: Optional[str] = Field(None, alias="Accept", description="Accepted content types")
    origin: Optional[str] = Field(None, alias="Origin", description="Request origin")
    user_agent: Optional[str] = Field(None, alias="User-Agent", description="User agent")


class MCPSessionInfo(BaseModel):
    """MCP session information."""
    session_id: str = Field(..., description="Session identifier")
    created_at: str = Field(..., description="Session creation timestamp")
    last_activity: str = Field(..., description="Last activity timestamp")
    client_info: Optional[MCPClientInfo] = Field(None, description="Client information")
    capabilities: Dict[str, Any] = Field(default_factory=dict, description="Session capabilities")


class MCPServerCapabilities(BaseModel):
    """MCP server capabilities structure."""
    tools: Optional[Dict[str, Any]] = Field(None, description="Tools capability configuration")
    resources: Optional[Dict[str, Any]] = Field(None, description="Resources capability configuration")
    prompts: Optional[Dict[str, Any]] = Field(None, description="Prompts capability configuration")
    logging: Optional[Dict[str, Any]] = Field(None, description="Logging capability configuration")


class MCPProtocolSchemas:
    """
    Collection of MCP protocol schemas.
    
    This class provides easy access to all MCP protocol schema definitions
    for validation and serialization of protocol messages.
    """
    
    # Request/Response schemas
    Request = MCPRequest
    Response = MCPResponse
    BatchRequest = MCPBatchRequest
    BatchResponse = MCPBatchResponse
    Notification = MCPNotification
    
    # Protocol schemas
    InitializeParams = MCPInitializeParams
    InitializeResult = MCPInitializeResult
    ProtocolVersion = MCPProtocolVersion
    ClientInfo = MCPClientInfo
    ServerInfo = MCPServerInfo
    
    # Tool schemas
    Tool = MCPTool
    ToolParameter = MCPToolParameter
    ToolInputSchema = MCPToolInputSchema
    ToolAnnotations = MCPToolAnnotations
    ToolsListResult = MCPToolsListResult
    ToolCallParams = MCPToolCallParams
    ToolResult = MCPToolResult
    
    # Utility schemas
    PingParams = MCPPingParams
    PingResult = MCPPingResult
    ErrorInfo = MCPErrorInfo
    NotificationParams = MCPNotificationParams
    
    # Transport schemas
    StreamEvent = MCPStreamEvent
    TransportHeaders = MCPTransportHeaders
    SessionInfo = MCPSessionInfo
    ServerCapabilities = MCPServerCapabilities 