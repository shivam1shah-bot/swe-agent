"""
Streaming event model.

Represents events emitted during streaming sessions, including tool calls,
agent responses, and system events.
"""

from datetime import datetime
from typing import Dict, Any, Optional, Literal
from pydantic import BaseModel, Field


class StreamingEvent(BaseModel):
    """Model for streaming events."""
    
    event_id: str = Field(..., description="Unique event identifier")
    session_id: str = Field(..., description="Session this event belongs to")
    event_type: str = Field(..., description="Type of event")
    data: Dict[str, Any] = Field(..., description="Event data payload")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    turn_complete: bool = Field(default=False, description="Whether this completes a conversation turn")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional event metadata")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ToolExecutionStartEvent(BaseModel):
    """Event for tool execution start."""
    
    tool_name: str = Field(..., description="Name of the tool being executed")
    tool_args: Dict[str, Any] = Field(..., description="Arguments passed to the tool")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Execution start time")


class ToolExecutionCompleteEvent(BaseModel):
    """Event for tool execution completion."""
    
    tool_name: str = Field(..., description="Name of the tool that completed")
    tool_result: Any = Field(..., description="Result returned by the tool")
    execution_time: Optional[float] = Field(default=None, description="Execution time in seconds")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Completion time")


class AgentMessageEvent(BaseModel):
    """Event for agent message content."""
    
    content: str = Field(..., description="Message content from the agent")
    content_type: str = Field(default="text", description="Type of content: text, markdown, html")
    partial: bool = Field(default=False, description="Whether this is a partial message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message timestamp")


class TurnCompleteEvent(BaseModel):
    """Event indicating completion of a conversation turn."""
    
    turn_id: Optional[str] = Field(default=None, description="Turn identifier if applicable")
    total_tokens: Optional[int] = Field(default=None, description="Total tokens used in turn")
    execution_time: Optional[float] = Field(default=None, description="Total turn execution time")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Completion timestamp")


class SystemEvent(BaseModel):
    """Event for system-level messages."""
    
    message: str = Field(..., description="System message")
    severity: Literal["info", "warning", "error"] = Field(default="info", description="Message severity")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")


# Event type constants
class EventTypes:
    """Constants for event types."""
    
    TOOL_EXECUTION_START = "tool_execution_start"
    TOOL_EXECUTION_COMPLETE = "tool_execution_complete"
    AGENT_MESSAGE = "agent_message"
    TURN_COMPLETE = "turn_complete"
    SYSTEM_MESSAGE = "system_message"
    CONNECTION_OPENED = "connection_opened"
    CONNECTION_CLOSED = "connection_closed"
    ERROR = "error"
