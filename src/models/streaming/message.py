"""
Streaming message model.

Represents messages exchanged between clients and agents in streaming sessions.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class StreamingMessage(BaseModel):
    """Model for streaming messages."""
    
    message_id: str = Field(..., description="Unique message identifier")
    session_id: str = Field(..., description="Session this message belongs to")
    sender: str = Field(..., description="Message sender: user, agent, system")
    content: str = Field(..., description="Message content")
    content_type: str = Field(default="text", description="Content type: text, json, html")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional message metadata")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class MessageRequest(BaseModel):
    """Request model for sending a message."""
    
    message: str = Field(..., description="Message content to send")
    content_type: str = Field(default="text", description="Content type")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional message metadata")


class MessageResponse(BaseModel):
    """Response model for message operations."""
    
    status: str = Field(..., description="Operation status")
    message_id: Optional[str] = Field(default=None, description="Message ID if applicable")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
