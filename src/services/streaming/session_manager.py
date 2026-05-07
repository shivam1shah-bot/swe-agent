"""
Session manager for streaming functionality.

Manages the lifecycle of streaming sessions including creation, tracking, and cleanup.
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from src.models.streaming.session import StreamingSession
from src.providers.streaming.registry import StreamingRegistry

try:
    from src.providers.logger import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class SessionManager:
    """
    Manages streaming sessions.
    
    Handles session creation, tracking, timeout management, and cleanup.
    """
    
    def __init__(self, session_timeout: int = 3600):
        """
        Initialize session manager.
        
        Args:
            session_timeout: Session timeout in seconds (default: 1 hour)
        """
        self.sessions: Dict[str, StreamingSession] = {}
        self.session_timeout = session_timeout
        logger.info(f"Session manager initialized with timeout: {session_timeout}s")
    
    def create_session(self, agent_id: str, transport_type: str = "sse", 
                      user_context: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a new streaming session.
        
        Args:
            agent_id: Agent identifier
            transport_type: Transport type (default: 'sse')
            user_context: Optional user context data
            
        Returns:
            str: Session ID
            
        Raises:
            ValueError: If agent ID is invalid
        """
        # Validate agent exists
        agent_config = StreamingRegistry.get_agent_by_id(agent_id)
        if not agent_config:
            raise ValueError(f"Unknown agent ID: {agent_id}")
        
        # Generate session ID
        session_id = f"session_{uuid.uuid4().hex}"
        
        # Create session
        session = StreamingSession(
            session_id=session_id,
            agent_id=agent_id,
            agent_name=agent_config["name"],
            transport_type=transport_type,
            user_context=user_context or {},
            agent_context={"config": agent_config}
        )
        
        # Store session
        self.sessions[session_id] = session
        
        logger.info(f"Created session {session_id} for agent {agent_id} with transport {transport_type}")
        return session_id
    
    def get_session(self, session_id: str) -> Optional[StreamingSession]:
        """
        Get a session by ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Optional[StreamingSession]: Session if found, None otherwise
        """
        session = self.sessions.get(session_id)
        if session and self._is_session_expired(session):
            logger.info(f"Session {session_id} has expired, removing")
            self.close_session(session_id)
            return None
        
        return session
    
    def update_session_activity(self, session_id: str) -> bool:
        """
        Update session activity timestamp.
        
        Args:
            session_id: Session identifier
            
        Returns:
            bool: True if session was updated, False if not found
        """
        session = self.get_session(session_id)
        if session:
            session.update_activity()
            logger.debug(f"Updated activity for session {session_id}")
            return True
        return False
    
    def close_session(self, session_id: str) -> bool:
        """
        Close a session and clean up.
        
        Args:
            session_id: Session identifier
            
        Returns:
            bool: True if session was closed, False if not found
        """
        session = self.sessions.get(session_id)
        if session:
            session.close()
            del self.sessions[session_id]
            logger.info(f"Closed session {session_id}")
            return True
        
        logger.warning(f"Attempted to close non-existent session: {session_id}")
        return False
    
    def get_session_context(self, session_id: str) -> Dict[str, Any]:
        """
        Get session context for agent processing.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dict[str, Any]: Combined session context
        """
        session = self.get_session(session_id)
        if not session:
            return {}
        
        return {
            "session_id": session_id,
            "agent_id": session.agent_id,
            "agent_name": session.agent_name,
            "transport_type": session.transport_type,
            "user_context": session.user_context,
            "agent_context": session.agent_context,
            "created_at": session.created_at,
            "last_activity": session.last_activity
        }
    
    def get_active_sessions(self) -> List[StreamingSession]:
        """
        Get all active sessions.
        
        Returns:
            List[StreamingSession]: List of active sessions
        """
        active_sessions = []
        expired_sessions = []
        
        for session_id, session in self.sessions.items():
            if self._is_session_expired(session):
                expired_sessions.append(session_id)
            elif session.is_active():
                active_sessions.append(session)
        
        # Clean up expired sessions
        for session_id in expired_sessions:
            self.close_session(session_id)
        
        return active_sessions
    
    def get_session_count(self) -> int:
        """
        Get total number of active sessions.
        
        Returns:
            int: Number of active sessions
        """
        return len(self.get_active_sessions())
    
    def get_sessions_by_agent(self, agent_id: str) -> List[StreamingSession]:
        """
        Get all active sessions for a specific agent.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            List[StreamingSession]: Sessions for the agent
        """
        active_sessions = self.get_active_sessions()
        return [session for session in active_sessions if session.agent_id == agent_id]
    
    def cleanup_expired_sessions(self) -> int:
        """
        Clean up all expired sessions.
        
        Returns:
            int: Number of sessions cleaned up
        """
        expired_sessions = []
        
        for session_id, session in self.sessions.items():
            if self._is_session_expired(session):
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            self.close_session(session_id)
        
        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
        
        return len(expired_sessions)
    
    def get_session_stats(self) -> Dict[str, Any]:
        """
        Get session statistics.
        
        Returns:
            Dict[str, Any]: Session statistics
        """
        active_sessions = self.get_active_sessions()
        
        # Count by agent
        agent_counts = {}
        transport_counts = {}
        
        for session in active_sessions:
            agent_counts[session.agent_id] = agent_counts.get(session.agent_id, 0) + 1
            transport_counts[session.transport_type] = transport_counts.get(session.transport_type, 0) + 1
        
        return {
            "total_active_sessions": len(active_sessions),
            "sessions_by_agent": agent_counts,
            "sessions_by_transport": transport_counts,
            "session_timeout": self.session_timeout
        }
    
    def is_session_active(self, session_id: str) -> bool:
        """
        Check if a session is active.
        
        Args:
            session_id: Session identifier
            
        Returns:
            bool: True if session is active
        """
        session = self.get_session(session_id)
        return session is not None and session.is_active()
    
    def _is_session_expired(self, session: StreamingSession) -> bool:
        """
        Check if a session has expired.
        
        Args:
            session: Session to check
            
        Returns:
            bool: True if session has expired
        """
        if session.status == "closed":
            return True
        
        timeout_delta = timedelta(seconds=self.session_timeout)
        return datetime.utcnow() - session.last_activity > timeout_delta
