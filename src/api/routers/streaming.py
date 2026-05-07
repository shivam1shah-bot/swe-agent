"""
Streaming API endpoints.

Provides generic streaming endpoints for all agents and transports.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from typing import Dict, Any

from src.models.streaming.session import CreateSessionRequest, SessionResponse
from src.models.streaming.message import MessageRequest, MessageResponse
from src.services.streaming.streaming_service import StreamingService

try:
    from src.providers.logger import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

router = APIRouter()

# Global streaming service instance
_streaming_service: StreamingService = None


def get_streaming_service() -> StreamingService:
    """Get or create streaming service instance."""
    global _streaming_service
    if _streaming_service is None:
        _streaming_service = StreamingService()
    return _streaming_service


@router.get("/agents")
async def get_available_agents():
    """
    Get list of available streaming agents.
    
    Returns all agents that can be used for streaming sessions.
    """
    try:
        streaming_service = get_streaming_service()
        agents = streaming_service.list_available_agents()
        
        return {
            "agents": agents,
            "count": len(agents)
        }
        
    except Exception as e:
        logger.error(f"Error getting available agents: {e}")
        raise HTTPException(status_code=500, detail="Failed to get available agents")


@router.post("/sessions", response_model=SessionResponse)
async def create_session(request: CreateSessionRequest):
    """
    Create a new streaming session.
    
    Creates a session for the specified agent with the chosen transport.
    """
    try:
        logger.info(f"Creating session for agent {request.agent_id}")
        
        streaming_service = get_streaming_service()
        session_id = await streaming_service.create_session(
            agent_id=request.agent_id,
            transport_type=request.transport_type,
            user_context=request.user_context
        )
        
        # Get session info for response
        session_info = streaming_service.get_session_info(session_id)
        if not session_info:
            raise HTTPException(status_code=500, detail="Session created but info not available")
        
        session_data = session_info["session"]
        
        return SessionResponse(
            session_id=session_data["session_id"],
            agent_id=session_data["agent_id"],
            agent_name=session_data["agent_name"],
            status=session_data["status"],
            created_at=session_data["created_at"],
            transport_type=session_data["transport_type"]
        )
        
    except ValueError as e:
        logger.warning(f"Invalid session creation request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create session")


@router.get("/sessions/{session_id}/events")
async def stream_events(session_id: str):
    """
    Stream events for a session via Server-Sent Events.
    
    Establishes an SSE connection to receive real-time events from the agent.
    """
    try:
        logger.info(f"Creating event stream for session {session_id}")
        
        streaming_service = get_streaming_service()
        
        # Validate session exists
        session_info = streaming_service.get_session_info(session_id)
        if not session_info:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
        async def event_generator():
            try:
                async for event in streaming_service.get_event_stream(session_id):
                    yield event
            except Exception as e:
                logger.error(f"Error in event stream for session {session_id}: {e}")
                # Send error event and close stream
                error_event = f"data: {{\"event_type\": \"error\", \"data\": {{\"message\": \"Stream error: {str(e)}\"}}}}\n\n"
                yield error_event
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Disable nginx buffering
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting up event stream for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create event stream")


@router.post("/sessions/{session_id}/messages", response_model=MessageResponse)
async def send_message(session_id: str, request: MessageRequest):
    """
    Send a message to an agent in a streaming session.
    
    The agent will process the message and stream response events.
    """
    try:
        logger.info(f"Sending message to session {session_id}: {request.message[:100]}...")
        
        streaming_service = get_streaming_service()
        
        # Validate session exists and is active
        session_info = streaming_service.get_session_info(session_id)
        if not session_info:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
        if not session_info["is_active"]:
            raise HTTPException(status_code=410, detail=f"Session {session_id} is not active")
        
        # Process message (this will stream events through the transport)
        await streaming_service.process_message(session_id, request.message)
        
        return MessageResponse(
            status="sent",
            message_id=f"msg_{session_id}_{int(time.time() * 1000)}"
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Invalid message request for session {session_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing message for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to process message")


@router.get("/sessions/{session_id}")
async def get_session_info(session_id: str):
    """
    Get information about a specific session.
    
    Returns session details, agent info, and transport status.
    """
    try:
        streaming_service = get_streaming_service()
        session_info = streaming_service.get_session_info(session_id)
        
        if not session_info:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
        return session_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session info for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get session info")


@router.delete("/sessions/{session_id}")
async def close_session(session_id: str):
    """
    Close a streaming session and clean up resources.
    
    Terminates the session and releases associated resources.
    """
    try:
        logger.info(f"Closing session {session_id}")
        
        streaming_service = get_streaming_service()
        success = await streaming_service.close_session(session_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
        return {"status": "closed", "session_id": session_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error closing session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to close session")


@router.get("/stats")
async def get_streaming_stats():
    """
    Get streaming service statistics.
    
    Returns information about active sessions, agents, and performance metrics.
    """
    try:
        streaming_service = get_streaming_service()
        stats = streaming_service.get_service_stats()
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting streaming stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get streaming stats")


# Import time for message IDs
import time
