"""
MCP Session Manager for handling session lifecycle and validation.

Implements session management according to MCP Streamable HTTP specification.
"""

import uuid
import time
from typing import Dict, Optional, Set
from dataclasses import dataclass

from src.providers.logger import Logger


@dataclass
class MCPSession:
    """MCP session information."""
    session_id: str
    created_at: float
    last_accessed: float
    last_activity: float
    client_info: Dict[str, str]
    is_active: bool = True
    
    def __post_init__(self):
        """Initialize last_activity if not provided."""
        if not hasattr(self, 'last_activity') or self.last_activity is None:
            self.last_activity = self.last_accessed


class MCPSessionManager:
    """
    Manages MCP sessions with proper lifecycle and validation.
    
    Handles session creation, validation, and cleanup according to
    MCP Streamable HTTP specification.
    """
    
    def __init__(self, session_timeout: int = 3600):
        """
        Initialize session manager.
        
        Args:
            session_timeout: Session timeout in seconds (default: 1 hour)
        """
        self.logger = Logger("MCPSessionManager")
        self.sessions: Dict[str, MCPSession] = {}
        self.session_timeout = session_timeout
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()
    
    def create_session(self, client_info: Optional[Dict[str, str]] = None) -> str:
        """
        Create a new MCP session.
        
        Args:
            client_info: Optional client information
            
        Returns:
            Globally unique session ID
        """
        session_id = str(uuid.uuid4())
        current_time = time.time()
        
        session = MCPSession(
            session_id=session_id,
            created_at=current_time,
            last_accessed=current_time,
            last_activity=current_time,
            client_info=client_info or {},
            is_active=True
        )
        
        self.sessions[session_id] = session
        
        self.logger.info("Created MCP session", session_id=session_id)
        return session_id
    
    def validate_session(self, session_id: Optional[str]) -> bool:
        """
        Validate if session ID is valid and active.
        
        Args:
            session_id: Session ID to validate
            
        Returns:
            True if session is valid and active
        """
        if not session_id:
            return False
            
        if session_id not in self.sessions:
            return False
            
        session = self.sessions[session_id]
        current_time = time.time()
        
        # Check if session has expired
        if current_time - session.last_accessed > self.session_timeout:
            self.terminate_session(session_id)
            return False
            
        if not session.is_active:
            return False
            
        # Update last accessed time
        session.last_accessed = current_time
        return True
    
    def get_session(self, session_id: str) -> Optional[MCPSession]:
        """
        Get session information.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session information or None if not found
        """
        if not self.validate_session(session_id):
            return None
            
        return self.sessions.get(session_id)
    
    def terminate_session(self, session_id: str) -> bool:
        """
        Terminate a session.
        
        Args:
            session_id: Session ID to terminate
            
        Returns:
            True if session was terminated
        """
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session.is_active = False
            del self.sessions[session_id]
            
            self.logger.info("Terminated MCP session", session_id=session_id)
            return True
            
        return False
    
    def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions.
        
        Returns:
            Number of sessions cleaned up
        """
        current_time = time.time()
        
        # Only run cleanup periodically
        if current_time - self._last_cleanup < self._cleanup_interval:
            return 0
            
        expired_sessions = []
        for session_id, session in self.sessions.items():
            if current_time - session.last_accessed > self.session_timeout:
                expired_sessions.append(session_id)
        
        cleanup_count = 0
        for session_id in expired_sessions:
            if self.terminate_session(session_id):
                cleanup_count += 1
        
        self._last_cleanup = current_time
        
        if cleanup_count > 0:
            self.logger.info("Cleaned up expired sessions", count=cleanup_count)
            
        return cleanup_count
    
    def get_active_session_count(self) -> int:
        """Get count of active sessions."""
        return len([s for s in self.sessions.values() if s.is_active])
    
    def get_session_stats(self) -> Dict[str, int]:
        """
        Get session statistics.
        
        Returns:
            Dictionary with session statistics
        """
        current_time = time.time()
        active_sessions = 0
        expired_sessions = 0
        
        for session in self.sessions.values():
            if session.is_active and (current_time - session.last_accessed <= self.session_timeout):
                active_sessions += 1
            else:
                expired_sessions += 1
        
        return {
            "active_sessions": active_sessions,
            "expired_sessions": expired_sessions,
            "total_sessions": len(self.sessions),
            "total_created": len(self.sessions)  # For backward compatibility
        }
    
    def get_session(self, session_id: str) -> Optional[MCPSession]:
        """
        Get session by ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            MCPSession object if found, None otherwise
        """
        return self.sessions.get(session_id)
    
    def update_activity(self, session_id: str) -> bool:
        """
        Update session activity timestamp.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session was updated, False if not found
        """
        session = self.sessions.get(session_id)
        if session and session.is_active:
            current_time = time.time()
            session.last_activity = current_time
            session.last_accessed = current_time
            return True
        return False 