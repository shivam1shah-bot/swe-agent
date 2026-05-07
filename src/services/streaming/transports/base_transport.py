"""
Base transport interface.

Defines the interface for streaming transport implementations.
This allows for future extensibility to support WebSockets and other protocols.
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Any


class BaseTransport(ABC):
    """
    Base interface for streaming transports.
    
    This abstract class defines the contract that all transport implementations
    must follow, enabling pluggable transport layers for different protocols.
    """
    
    @abstractmethod
    async def send_event(self, session_id: str, event: Dict[str, Any]) -> bool:
        """
        Send an event to a specific session.
        
        Args:
            session_id: Unique identifier for the session
            event: Event data to send to the client
            
        Returns:
            bool: True if event was sent successfully, False if session is inactive
        """
        pass
    
    @abstractmethod
    async def create_stream(self, session_id: str) -> AsyncGenerator[str, None]:
        """
        Create a streaming connection for a session.
        
        Args:
            session_id: Unique identifier for the session
            
        Yields:
            str: Formatted event data for the transport protocol
            
        Raises:
            ValueError: If session_id is invalid
            ConnectionError: If unable to establish stream
        """
        pass
    
    @abstractmethod
    async def close_session(self, session_id: str) -> None:
        """
        Close a streaming session and clean up resources.
        
        Args:
            session_id: Unique identifier for the session to close
        """
        pass
    
    @abstractmethod
    def is_session_active(self, session_id: str) -> bool:
        """
        Check if a session is currently active.
        
        Args:
            session_id: Session identifier to check
            
        Returns:
            bool: True if session is active, False otherwise
        """
        pass
    
    def get_transport_type(self) -> str:
        """
        Get the transport type identifier.
        
        Returns:
            str: Transport type (e.g., 'sse', 'websocket')
        """
        return self.__class__.__name__.lower().replace('transport', '')
