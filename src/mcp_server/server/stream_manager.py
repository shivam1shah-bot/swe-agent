"""
MCP Stream Manager for handling Server-Sent Events (SSE) streams.

Implements SSE streaming with resumability, event IDs, and proper connection management
according to MCP Streamable HTTP specification.
"""

import asyncio
import time
import uuid
from typing import Dict, List, Optional, AsyncGenerator, Any
from dataclasses import dataclass, field
from collections import deque

from src.providers.logger import Logger


@dataclass
class SSEEvent:
    """Server-Sent Event data structure."""
    id: str
    event: str
    event_type: str
    data: Any  # Store original data object
    data_str: str = None  # JSON serialized data for SSE transmission
    timestamp: float = field(default_factory=time.time)
    
    def __post_init__(self):
        """Initialize event_type and data_str if not provided."""
        if not hasattr(self, 'event_type') or self.event_type is None:
            self.event_type = self.event
        
        # Create JSON string if not provided
        if self.data_str is None:
            import json
            self.data_str = json.dumps(self.data) if not isinstance(self.data, str) else self.data


@dataclass
class MCPStream:
    """MCP SSE stream information."""
    stream_id: str
    session_id: Optional[str]
    created_at: float
    last_activity: float
    is_active: bool = True
    events: deque = field(default_factory=lambda: deque(maxlen=1000))  # Keep last 1000 events
    event_counter: int = 0


class MCPStreamManager:
    """
    Manages Server-Sent Event streams for MCP communication.
    
    Handles stream creation, event delivery, resumability, and cleanup
    according to MCP Streamable HTTP specification.
    """
    
    def __init__(self, stream_timeout: int = 3600, max_events_per_stream: int = 1000):
        """
        Initialize stream manager.
        
        Args:
            stream_timeout: Stream timeout in seconds (default: 1 hour)
            max_events_per_stream: Maximum events to keep per stream for resumability
        """
        self.logger = Logger("MCPStreamManager")
        self.streams: Dict[str, MCPStream] = {}
        self.stream_timeout = stream_timeout
        self.max_events_per_stream = max_events_per_stream
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()
    
    def create_stream(self, session_id: Optional[str] = None) -> str:
        """
        Create a new SSE stream.
        
        Args:
            session_id: Optional session ID to associate with stream
            
        Returns:
            Unique stream ID
        """
        stream_id = str(uuid.uuid4())
        current_time = time.time()
        
        stream = MCPStream(
            stream_id=stream_id,
            session_id=session_id,
            created_at=current_time,
            last_activity=current_time,
            is_active=True,
            events=deque(maxlen=self.max_events_per_stream),
            event_counter=0
        )
        
        self.streams[stream_id] = stream
        
        self.logger.info("Created MCP stream", stream_id=stream_id, session_id=session_id)
        return stream_id
    
    def get_stream(self, stream_id: str) -> Optional[MCPStream]:
        """
        Get stream by ID.
        
        Args:
            stream_id: Stream ID
            
        Returns:
            Stream object or None if not found
        """
        return self.streams.get(stream_id)
    
    def is_stream_active(self, stream_id: str) -> bool:
        """
        Check if stream is active.
        
        Args:
            stream_id: Stream ID
            
        Returns:
            True if stream is active
        """
        stream = self.get_stream(stream_id)
        if not stream:
            return False
        
        current_time = time.time()
        
        # Check if stream has expired
        if current_time - stream.last_activity > self.stream_timeout:
            self.close_stream(stream_id)
            return False
        
        return stream.is_active
    
    def add_event(
        self,
        stream_id: str,
        event_type: str,
        data: Any,
        event_id: Optional[str] = None
    ) -> Optional[SSEEvent]:
        """
        Add an event to a stream.
        
        Args:
            stream_id: Stream ID
            event_type: SSE event type
            data: Event data (will be JSON serialized)
            event_id: Optional custom event ID
            
        Returns:
            SSEEvent object or None if stream not found
        """
        stream = self.get_stream(stream_id)
        if not stream or not stream.is_active:
            return None
        
        # Generate event ID if not provided
        if event_id is None:
            stream.event_counter += 1
            event_id = f"{stream_id}_{stream.event_counter}"
        
        # Create event
        event = SSEEvent(
            id=event_id,
            event=event_type,
            event_type=event_type,
            data=data
        )
        
        # Add to stream
        stream.events.append(event)
        stream.last_activity = time.time()
        
        self.logger.debug("Added event to stream", stream_id=stream_id, event_id=event_id, event_type=event_type)
        return event
    
    def get_events_after(self, stream_id: str, last_event_id: Optional[str] = None) -> List[SSEEvent]:
        """
        Get events after a specific event ID for resumability.
        
        Args:
            stream_id: Stream ID
            last_event_id: Last event ID received by client
            
        Returns:
            List of events after the specified event ID
        """
        stream = self.get_stream(stream_id)
        if not stream:
            return []
        
        if last_event_id is None:
            return list(stream.events)
        
        # Find events after the last event ID
        events_after = []
        found_last_event = False
        
        for event in stream.events:
            if found_last_event:
                events_after.append(event)
            elif event.id == last_event_id:
                found_last_event = True
        
        return events_after
    
    async def stream_events(
        self,
        stream_id: str,
        last_event_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Generate SSE-formatted events for a stream.
        
        Args:
            stream_id: Stream ID
            last_event_id: Optional last event ID for resumability
            
        Yields:
            SSE-formatted event strings
        """
        stream = self.get_stream(stream_id)
        if not stream:
            self.logger.warning("Attempted to stream from non-existent stream", stream_id=stream_id)
            return
        
        # Send existing events if resuming
        if last_event_id:
            existing_events = self.get_events_after(stream_id, last_event_id)
            for event in existing_events:
                yield self._format_sse_event(event)
        
        # Monitor for new events
        last_event_count = len(stream.events)
        
        while self.is_stream_active(stream_id):
            current_event_count = len(stream.events)
            
            # Check for new events
            if current_event_count > last_event_count:
                # Get new events
                new_events = list(stream.events)[last_event_count:]
                for event in new_events:
                    yield self._format_sse_event(event)
                
                last_event_count = current_event_count
            
            # Small delay to prevent tight loop
            await asyncio.sleep(0.1)
        
        self.logger.info("Stream ended", stream_id=stream_id)
    
    def _format_sse_event(self, event: SSEEvent) -> str:
        """
        Format an event as SSE string.
        
        Args:
            event: SSEEvent to format
            
        Returns:
            SSE-formatted string
        """
        lines = []
        
        if event.id:
            lines.append(f"id: {event.id}")
        
        if event.event:
            lines.append(f"event: {event.event}")
        
        # Handle multi-line data
        data_lines = event.data_str.split('\n')
        for line in data_lines:
            lines.append(f"data: {line}")
        
        # Add empty line to signal end of event
        lines.append("")
        
        return "\n".join(lines)
    
    def close_stream(self, stream_id: str) -> bool:
        """
        Close a stream.
        
        Args:
            stream_id: Stream ID to close
            
        Returns:
            True if stream was closed
        """
        if stream_id in self.streams:
            stream = self.streams[stream_id]
            stream.is_active = False
            
            # Keep stream for a while for resumability
            # It will be cleaned up by cleanup_expired_streams
            
            self.logger.info("Closed MCP stream", stream_id=stream_id)
            return True
        
        return False
    
    def cleanup_expired_streams(self) -> int:
        """
        Clean up expired streams.
        
        Returns:
            Number of streams cleaned up
        """
        current_time = time.time()
        
        # Only run cleanup periodically
        if current_time - self._last_cleanup < self._cleanup_interval:
            return 0
        
        expired_streams = []
        for stream_id, stream in self.streams.items():
            if current_time - stream.last_activity > self.stream_timeout:
                expired_streams.append(stream_id)
        
        cleanup_count = 0
        for stream_id in expired_streams:
            if stream_id in self.streams:
                del self.streams[stream_id]
                cleanup_count += 1
        
        self._last_cleanup = current_time
        
        if cleanup_count > 0:
            self.logger.info("Cleaned up expired streams", count=cleanup_count)
        
        return cleanup_count
    
    def get_stream_stats(self) -> Dict[str, int]:
        """
        Get stream statistics.
        
        Returns:
            Dictionary with stream statistics
        """
        current_time = time.time()
        active_streams = 0
        inactive_streams = 0
        
        for stream in self.streams.values():
            if stream.is_active and (current_time - stream.last_activity <= self.stream_timeout):
                active_streams += 1
            else:
                inactive_streams += 1
        
        return {
            "active_streams": active_streams,
            "inactive_streams": inactive_streams,
            "total_streams": len(self.streams)
        } 