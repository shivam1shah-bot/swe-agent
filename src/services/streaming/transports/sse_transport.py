"""
Server-Sent Events (SSE) transport implementation.

Provides SSE-based streaming communication between server and clients.
"""

import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, Any

from .base_transport import BaseTransport

try:
    from src.providers.logger import get_logger
    logger = get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)


class SSETransport(BaseTransport):
    """
    Server-Sent Events transport implementation.
    
    Handles SSE-specific formatting and connection management for streaming
    communication with web clients.
    """
    
    def __init__(self):
        """Initialize SSE transport."""
        self.active_sessions: Dict[str, asyncio.Queue] = {}
        self.session_metadata: Dict[str, Dict[str, Any]] = {}
        logger.info("SSE transport initialized")
    
    async def send_event(self, session_id: str, event: Dict[str, Any]) -> bool:
        """
        Send an event to a specific SSE session.
        
        Args:
            session_id: Session identifier
            event: Event data to send
            
        Returns:
            bool: True if event was sent successfully, False if session is inactive
        """
        if session_id not in self.active_sessions:
            logger.warning(f"Attempted to send event to inactive session: {session_id}")
            return False
        
        try:
            # Format event for SSE
            sse_data = self._format_sse_event(event)
            
            # Send to session queue
            queue = self.active_sessions[session_id]
            await queue.put(sse_data)
            
            logger.debug(f"Event sent to session {session_id}: {event.get('event_type', 'unknown')}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send event to session {session_id}: {e}")
            # Remove session from active sessions if queue is broken
            if session_id in self.active_sessions:
                logger.info(f"Removing broken session {session_id} from active sessions")
                await self.close_session(session_id)
            return False
    
    async def create_stream(self, session_id: str) -> AsyncGenerator[str, None]:
        """
        Create an SSE stream for a session.
        
        Args:
            session_id: Session identifier
            
        Yields:
            str: SSE-formatted event data
        """
        logger.info(f"Creating SSE stream for session: {session_id}")
        
        # Create queue for this session
        queue = asyncio.Queue()
        self.active_sessions[session_id] = queue
        self.session_metadata[session_id] = {
            "created_at": asyncio.get_event_loop().time(),
            "event_count": 0
        }
        
        try:
            # Send initial connection event
            connection_event = {
                "event_type": "connection_opened",
                "data": {
                    "session_id": session_id,
                    "transport": "sse",
                    "timestamp": self._get_timestamp()
                }
            }
            await queue.put(self._format_sse_event(connection_event))
            
            # Stream events from queue
            while session_id in self.active_sessions:
                try:
                    # Wait for next event with timeout
                    event_data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    
                    # Update event count
                    if session_id in self.session_metadata:
                        self.session_metadata[session_id]["event_count"] += 1
                    
                    yield event_data
                    
                except asyncio.TimeoutError:
                    # Send keep-alive ping
                    ping_event = self._format_sse_event({
                        "event_type": "ping",
                        "data": {
                            "timestamp": self._get_timestamp(),
                            "session_id": session_id
                        }
                    })
                    yield ping_event
                    
                except Exception as e:
                    logger.error(f"Error in SSE stream for session {session_id}: {e}")
                    break
                    
        finally:
            # Clean up session
            await self.close_session(session_id)
            logger.info(f"SSE stream closed for session: {session_id}")
    
    async def close_session(self, session_id: str) -> None:
        """
        Close an SSE session and clean up resources.
        
        Args:
            session_id: Session to close
        """
        if session_id in self.active_sessions:
            logger.info(f"Closing SSE session: {session_id}")
            
            # Send closing event
            try:
                close_event = {
                    "event_type": "connection_closed",
                    "data": {
                        "session_id": session_id,
                        "timestamp": self._get_timestamp()
                    }
                }
                queue = self.active_sessions[session_id]
                await queue.put(self._format_sse_event(close_event))
            except Exception as e:
                logger.warning(f"Error sending close event for session {session_id}: {e}")
            
            # Remove from active sessions
            self.active_sessions.pop(session_id, None)
            
            # Log session statistics
            metadata = self.session_metadata.pop(session_id, {})
            event_count = metadata.get("event_count", 0)
            logger.info(f"Session {session_id} closed. Events sent: {event_count}")
        else:
            # Session was already closed or never existed
            logger.debug(f"Session {session_id} was already closed or did not exist")
            # Still clean up metadata if it exists
            self.session_metadata.pop(session_id, None)
    
    def is_session_active(self, session_id: str) -> bool:
        """
        Check if an SSE session is active.
        
        Args:
            session_id: Session to check
            
        Returns:
            bool: True if session is active
        """
        return session_id in self.active_sessions
    
    def get_active_session_count(self) -> int:
        """
        Get the number of active SSE sessions.
        
        Returns:
            int: Number of active sessions
        """
        return len(self.active_sessions)
    
    def get_session_info(self, session_id: str) -> Dict[str, Any]:
        """
        Get information about a specific session.
        
        Args:
            session_id: Session to get info for
            
        Returns:
            dict: Session information
        """
        if session_id not in self.session_metadata:
            return {}
        
        metadata = self.session_metadata[session_id]
        return {
            "session_id": session_id,
            "transport": "sse",
            "active": self.is_session_active(session_id),
            "created_at": metadata.get("created_at"),
            "event_count": metadata.get("event_count", 0)
        }
    
    def _format_sse_event(self, event: Dict[str, Any]) -> str:
        """
        Format an event for SSE transmission.
        
        Args:
            event: Event data to format
            
        Returns:
            str: SSE-formatted event string
        """
        try:
            # Convert event to JSON
            event_json = json.dumps(event, default=str)
            
            # Format as SSE event
            sse_event = f"data: {event_json}\n\n"
            
            return sse_event
            
        except Exception as e:
            logger.error(f"Failed to format SSE event: {e}")
            # Return error event
            error_event = {
                "event_type": "error",
                "data": {"message": "Failed to format event"}
            }
            return f"data: {json.dumps(error_event)}\n\n"
    
    def _get_timestamp(self) -> str:
        """
        Get current timestamp in ISO format.
        
        Returns:
            str: ISO formatted timestamp
        """
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"
