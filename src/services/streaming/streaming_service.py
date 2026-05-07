"""
Main streaming service orchestrator.

Coordinates streaming sessions, agents, and transports to provide
a unified streaming interface.
"""

import asyncio
from typing import AsyncGenerator, Dict, Any, Optional

from .session_manager import SessionManager
from src.providers.streaming.factory import StreamingFactory
from src.services.streaming.agents.base_agent import BaseStreamingAgent
from src.services.streaming.transports.base_transport import BaseTransport

try:
    from src.providers.logger import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class StreamingService:
    """
    Main streaming service orchestrator.
    
    Coordinates all streaming components including sessions, agents, and transports
    to provide a unified streaming interface for the API layer.
    """
    
    def __init__(self, session_timeout: int = 3600):
        """
        Initialize streaming service.
        
        Args:
            session_timeout: Session timeout in seconds
        """
        self.session_manager = SessionManager(session_timeout)
        self.active_agents: Dict[str, BaseStreamingAgent] = {}
        self.transport: BaseTransport = StreamingFactory.create_transport("sse")
        
        # Start background cleanup task
        self._cleanup_task = None
        self._start_cleanup_task()
        
        logger.info("Streaming service initialized")
    
    async def create_session(self, agent_id: str, transport_type: str = "sse",
                           user_context: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a new streaming session.
        
        Args:
            agent_id: Agent identifier
            transport_type: Transport type (default: 'sse')
            user_context: Optional user context
            
        Returns:
            str: Session ID
            
        Raises:
            ValueError: If agent or transport is invalid
            RuntimeError: If session creation fails
        """
        try:
            logger.info(f"Creating streaming session for agent {agent_id}")
            
            # Create session
            session_id = self.session_manager.create_session(
                agent_id, transport_type, user_context
            )
            
            # Initialize agent for this session
            agent = StreamingFactory.create_agent(agent_id)
            await agent.initialize({})
            
            self.active_agents[session_id] = agent
            
            logger.info(f"Created streaming session {session_id} with agent {agent_id}")
            return session_id
            
        except Exception as e:
            logger.error(f"Failed to create streaming session for agent {agent_id}: {e}")
            raise RuntimeError(f"Session creation failed: {e}")
    
    async def process_message(self, session_id: str, message: str) -> None:
        """
        Process user message and stream response events.
        
        Args:
            session_id: Session identifier
            message: User message to process
            
        Raises:
            ValueError: If session is invalid
            RuntimeError: If message processing fails
        """
        try:
            logger.info(f"Processing message for session {session_id}: {message[:100]}...")
            
            # Validate session
            if not self.session_manager.is_session_active(session_id):
                raise ValueError(f"Session {session_id} is not active")
            
            # Get agent for this session
            agent = self.active_agents.get(session_id)
            if not agent:
                raise ValueError(f"No active agent for session {session_id}")
            
            # Update session activity
            self.session_manager.update_session_activity(session_id)
            
            # Get session context
            session_context = self.session_manager.get_session_context(session_id)
            
            # Process message through agent and stream events
            async for event in agent.process_message(message, session_context):
                # Check if session is still active before sending each event
                if not self.session_manager.is_session_active(session_id):
                    logger.warning(f"Session {session_id} became inactive during message processing, stopping")
                    break
                
                # Add session metadata to event
                event["session_id"] = session_id
                
                # Send event through transport
                sent = await self.transport.send_event(session_id, event)
                if not sent:
                    logger.warning(f"Failed to send event to session {session_id}, session may be inactive")
                    break
                
                logger.debug(f"Sent event to session {session_id}: {event.get('event_type')}")
            
            logger.info(f"Completed message processing for session {session_id}")
            
        except Exception as e:
            logger.error(f"Error processing message for session {session_id}: {e}")
            
            # Only try to send error event if session is still active
            if self.session_manager.is_session_active(session_id):
                error_event = {
                    "event_type": "error",
                    "data": {
                        "message": "Message processing failed",
                        "error_type": type(e).__name__,
                        "details": str(e)
                    },
                    "session_id": session_id,
                    "timestamp": self._get_timestamp(),
                    "turn_complete": True
                }
                
                sent = await self.transport.send_event(session_id, error_event)
                if not sent:
                    logger.warning(f"Could not send error event to inactive session {session_id}")
            else:
                logger.info(f"Session {session_id} is inactive, skipping error event")
            
            raise RuntimeError(f"Message processing failed: {e}")
    
    async def get_event_stream(self, session_id: str) -> AsyncGenerator[str, None]:
        """
        Get SSE event stream for a session.
        
        Args:
            session_id: Session identifier
            
        Yields:
            str: SSE-formatted events
            
        Raises:
            ValueError: If session is invalid
        """
        try:
            logger.info(f"Creating event stream for session {session_id}")
            
            # Validate session exists
            if not self.session_manager.get_session(session_id):
                raise ValueError(f"Session {session_id} not found")
            
            # Create transport stream
            async for event in self.transport.create_stream(session_id):
                # Update session activity on each event
                self.session_manager.update_session_activity(session_id)
                yield event
                
        except Exception as e:
            logger.error(f"Error in event stream for session {session_id}: {e}")
            raise
        finally:
            # Clean up when stream ends
            await self.close_session(session_id)
    
    async def close_session(self, session_id: str) -> bool:
        """
        Close a streaming session and clean up resources.
        
        Args:
            session_id: Session identifier
            
        Returns:
            bool: True if session was closed successfully
        """
        try:
            logger.info(f"Closing session {session_id}")
            
            # Clean up agent
            agent = self.active_agents.get(session_id)
            if agent:
                await agent.cleanup()
                del self.active_agents[session_id]
            
            # Close transport session
            await self.transport.close_session(session_id)
            
            # Close session in manager
            success = self.session_manager.close_session(session_id)
            
            if success:
                logger.info(f"Successfully closed session {session_id}")
            else:
                logger.warning(f"Session {session_id} was not found in manager")
            
            return success
            
        except Exception as e:
            logger.error(f"Error closing session {session_id}: {e}")
            return False
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Optional[Dict[str, Any]]: Session information or None if not found
        """
        session = self.session_manager.get_session(session_id)
        if not session:
            return None
        
        # Get transport info
        transport_info = {}
        if hasattr(self.transport, 'get_session_info'):
            transport_info = self.transport.get_session_info(session_id)
        
        # Get agent info
        agent_info = {}
        agent = self.active_agents.get(session_id)
        if agent:
            agent_info = agent.get_agent_info()
        
        return {
            "session": session.dict(),
            "transport": transport_info,
            "agent": agent_info,
            "is_active": self.session_manager.is_session_active(session_id)
        }
    
    def get_service_stats(self) -> Dict[str, Any]:
        """
        Get streaming service statistics.
        
        Returns:
            Dict[str, Any]: Service statistics
        """
        session_stats = self.session_manager.get_session_stats()
        
        # Transport stats
        transport_stats = {}
        if hasattr(self.transport, 'get_active_session_count'):
            transport_stats["active_connections"] = self.transport.get_active_session_count()
        
        return {
            "sessions": session_stats,
            "transport": transport_stats,
            "active_agents": len(self.active_agents),
            "service_status": "running"
        }
    
    def list_available_agents(self) -> list[Dict[str, Any]]:
        """
        List available streaming agents.
        
        Returns:
            list[Dict[str, Any]]: Available agents
        """
        return StreamingFactory.list_available_agents()
    
    def list_knowledge_agents(self) -> list[Dict[str, Any]]:
        """
        List available knowledge agents.
        
        Returns:
            list[Dict[str, Any]]: Available knowledge agents
        """
        return StreamingFactory.list_knowledge_agents()
    
    async def cleanup(self) -> None:
        """Clean up streaming service resources."""
        logger.info("Cleaning up streaming service")
        
        # Stop cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Close all active sessions
        active_sessions = list(self.active_agents.keys())
        for session_id in active_sessions:
            await self.close_session(session_id)
        
        logger.info("Streaming service cleanup completed")
    
    def _start_cleanup_task(self) -> None:
        """Start background cleanup task."""
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(300)  # Run every 5 minutes
                    expired_count = self.session_manager.cleanup_expired_sessions()
                    if expired_count > 0:
                        logger.info(f"Background cleanup removed {expired_count} expired sessions")
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in background cleanup: {e}")
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
    
    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"
