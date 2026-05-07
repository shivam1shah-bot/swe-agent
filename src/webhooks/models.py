"""
Webhook event models - normalized representations of events from any source.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WebhookEvent(BaseModel):
    """Normalized webhook event that works across all sources."""

    event_id: str = Field(..., description="Unique event identifier for deduplication")
    source: str = Field(..., description="Source name (e.g., 'devrev', 'github')")
    event_type: str = Field(..., description="Event type (e.g., 'work_created')")
    applies_to_part: str = Field(
        default="",
        description="Part/enhancement DON ID this event relates to (e.g., 'don:core:...:enhancement/11966')",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Event timestamp",
    )
    raw_payload: Dict[str, Any] = Field(
        default_factory=dict, description="Original unmodified payload from source"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Source-specific metadata"
    )


class EventFilter(BaseModel):
    """Declarative filter for which events a handler processes.
    Empty list = match all values for that field."""

    sources: List[str] = Field(default_factory=list)
    event_types: List[str] = Field(default_factory=list)
    parts: List[str] = Field(default_factory=list, description="DON IDs for applies_to_part")


class HandlerResult(BaseModel):
    """Result of a single handler processing an event."""

    handler_name: str
    success: bool
    message: str = ""


class WebhookVerificationResponse(BaseModel):
    """Response for webhook verification/challenge handshakes."""

    challenge: Optional[str] = None
