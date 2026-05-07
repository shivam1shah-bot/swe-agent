"""
Streaming session model.

Represents an active streaming session between a client and an agent.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class StreamingSession(BaseModel):
    """Model for streaming session data."""
    
    session_id: str = Field(..., description="Unique session identifier")
    agent_id: str = Field(..., description="ID of the agent handling this session")
    agent_name: str = Field(..., description="Human-readable name of the agent")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Session creation timestamp")
    last_activity: datetime = Field(default_factory=datetime.utcnow, description="Last activity timestamp")
    status: str = Field(default="active", description="Session status: active, inactive, closed")
    transport_type: str = Field(default="sse", description="Transport type: sse, websocket")
    user_context: Dict[str, Any] = Field(default_factory=dict, description="User-specific context data")
    agent_context: Dict[str, Any] = Field(default_factory=dict, description="Agent-specific context data")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional session metadata")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.utcnow()
    
    def close(self) -> None:
        """Mark session as closed."""
        self.status = "closed"
        self.update_activity()
    
    def is_active(self) -> bool:
        """Check if session is active."""
        return self.status == "active"


class CreateSessionRequest(BaseModel):
    """Request model for creating a new streaming session."""
    
    agent_id: str = Field(..., description="ID of the agent to create session for")
    transport_type: str = Field(default="sse", description="Preferred transport type")
    user_context: Optional[Dict[str, Any]] = Field(default=None, description="Initial user context")


class SessionResponse(BaseModel):
    """Response model for session operations."""
    
    session_id: str = Field(..., description="Session identifier")
    agent_id: str = Field(..., description="Agent identifier")
    agent_name: str = Field(..., description="Agent name")
    status: str = Field(..., description="Session status")
    created_at: datetime = Field(..., description="Session creation time")
    transport_type: str = Field(..., description="Transport type")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
