"""
Unit tests for StreamingService.

Tests for main streaming service orchestrator functionality.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from src.services.streaming.streaming_service import StreamingService


@pytest.fixture
def mock_session_manager():
    """Mock SessionManager for testing."""
    manager = Mock()
    manager.create_session.return_value = "session_123"
    manager.is_session_active.return_value = True
    manager.get_session.return_value = Mock(session_id="session_123")
    manager.update_session_activity.return_value = True
    manager.get_session_context.return_value = {
        "session_id": "session_123",
        "agent_id": "test_agent",
        "user_context": {}
    }
    manager.close_session.return_value = True
    manager.cleanup_expired_sessions.return_value = 0
    manager.get_session_stats.return_value = {
        "total_active_sessions": 1,
        "sessions_by_agent": {"test_agent": 1},
        "sessions_by_transport": {"sse": 1}
    }
    return manager


@pytest.fixture
def mock_streaming_agent():
    """Mock BaseStreamingAgent for testing."""
    agent = AsyncMock()
    # Make synchronous methods return values directly (not coroutines)
    agent.get_agent_info = Mock(return_value={
        "id": "test_agent",
        "name": "Test Agent",
        "framework": "test"
    })
    
    # Mock async generator for process_message
    async def mock_process_message(message, context):
        yield {"event_type": "agent_message", "data": {"content": "test response"}}
        yield {"event_type": "turn_complete", "data": {}, "turn_complete": True}
    
    agent.process_message = mock_process_message
    return agent


@pytest.fixture
def mock_transport():
    """Mock BaseTransport for testing."""
    transport = AsyncMock()
    transport.send_event.return_value = True
    # Make synchronous methods return values directly (not coroutines)
    transport.get_session_info = Mock(return_value={"transport": "sse", "active": True})
    transport.get_active_session_count = Mock(return_value=1)
    
    # Mock async generator for create_stream
    async def mock_create_stream(session_id):
        yield f"data: {{\"event_type\": \"connection_opened\"}}\n\n"
        yield f"data: {{\"event_type\": \"agent_message\"}}\n\n"
    
    transport.create_stream = mock_create_stream
    return transport


@pytest.fixture
def mock_streaming_factory(mock_streaming_agent, mock_transport):
    """Mock StreamingFactory for testing."""
    with patch('src.services.streaming.streaming_service.StreamingFactory') as mock_factory:
        mock_factory.create_agent.return_value = mock_streaming_agent
        mock_factory.create_transport.return_value = mock_transport
        mock_factory.list_available_agents.return_value = [
            {"id": "agent1", "name": "Agent 1"},
            {"id": "agent2", "name": "Agent 2"}
        ]
        mock_factory.list_knowledge_agents.return_value = [
            {"id": "knowledge_agent", "name": "Knowledge Agent"}
        ]
        yield mock_factory


@pytest.fixture
def streaming_service(mock_session_manager, mock_streaming_factory):
    """Create StreamingService instance with mocked dependencies."""
    with patch('src.services.streaming.streaming_service.SessionManager', return_value=mock_session_manager):
        with patch('src.services.streaming.streaming_service.asyncio.create_task') as mock_create_task:
            # Mock the cleanup task
            mock_create_task.return_value = Mock()
            
            service = StreamingService(session_timeout=3600)
            service.session_manager = mock_session_manager  # Ensure our mock is used
            return service


@pytest.mark.unit
class TestStreamingServiceInitialization:
    """Test cases for StreamingService initialization."""
    
    @patch('src.services.streaming.streaming_service.SessionManager')
    @patch('src.services.streaming.streaming_service.StreamingFactory')
    @patch('src.services.streaming.streaming_service.asyncio.create_task')
    def test_streaming_service_creation_default_timeout(self, mock_create_task, mock_factory, mock_session_manager_class):
        """Test creating StreamingService with default timeout."""
        mock_transport = Mock()
        mock_factory.create_transport.return_value = mock_transport
        mock_session_manager = Mock()
        mock_session_manager_class.return_value = mock_session_manager
        
        service = StreamingService()
        
        # Verify initialization
        mock_session_manager_class.assert_called_once_with(3600)
        mock_factory.create_transport.assert_called_once_with("sse")
        assert service.session_manager == mock_session_manager
        assert service.active_agents == {}
        assert service.transport == mock_transport
        mock_create_task.assert_called_once()  # Background cleanup task started
    
    @patch('src.services.streaming.streaming_service.SessionManager')
    @patch('src.services.streaming.streaming_service.StreamingFactory')
    @patch('src.services.streaming.streaming_service.asyncio.create_task')
    def test_streaming_service_creation_custom_timeout(self, mock_create_task, mock_factory, mock_session_manager_class):
        """Test creating StreamingService with custom timeout."""
        mock_session_manager_class.return_value = Mock()
        mock_factory.create_transport.return_value = Mock()
        
        service = StreamingService(session_timeout=1800)
        
        mock_session_manager_class.assert_called_once_with(1800)
    
    @patch('src.services.streaming.streaming_service.logger')
    @patch('src.services.streaming.streaming_service.SessionManager')
    @patch('src.services.streaming.streaming_service.StreamingFactory')
    @patch('src.services.streaming.streaming_service.asyncio.create_task')
    def test_streaming_service_initialization_logging(self, mock_create_task, mock_factory, mock_session_manager, mock_logger):
        """Test that initialization logs appropriately."""
        mock_session_manager.return_value = Mock()
        mock_factory.create_transport.return_value = Mock()
        
        service = StreamingService()
        
        mock_logger.info.assert_called_with("Streaming service initialized")


@pytest.mark.unit
@pytest.mark.asyncio
class TestSessionCreation:
    """Test cases for session creation."""
    
    async def test_create_session_success(self, streaming_service, mock_streaming_factory, mock_streaming_agent):
        """Test successful session creation."""
        session_id = await streaming_service.create_session("test_agent", "sse")
        
        # Verify session creation
        assert session_id == "session_123"
        streaming_service.session_manager.create_session.assert_called_once_with(
            "test_agent", "sse", None
        )
        
        # Verify agent creation and initialization
        mock_streaming_factory.create_agent.assert_called_once_with("test_agent")
        mock_streaming_agent.initialize.assert_called_once_with({})
        
        # Verify agent is stored
        assert session_id in streaming_service.active_agents
        assert streaming_service.active_agents[session_id] == mock_streaming_agent
    
    async def test_create_session_with_user_context(self, streaming_service):
        """Test session creation with user context."""
        user_context = {"user_id": "test_user", "role": "admin"}
        
        session_id = await streaming_service.create_session(
            "test_agent", 
            "websocket", 
            user_context=user_context
        )
        
        streaming_service.session_manager.create_session.assert_called_once_with(
            "test_agent", "websocket", user_context
        )
    
    async def test_create_session_session_manager_error(self, streaming_service):
        """Test session creation when SessionManager raises error."""
        streaming_service.session_manager.create_session.side_effect = ValueError("Invalid agent")
        
        with pytest.raises(RuntimeError, match="Session creation failed: Invalid agent"):
            await streaming_service.create_session("invalid_agent")
    
    async def test_create_session_agent_initialization_error(self, streaming_service, mock_streaming_factory, mock_streaming_agent):
        """Test session creation when agent initialization fails."""
        mock_streaming_agent.initialize.side_effect = RuntimeError("Agent init failed")
        
        with pytest.raises(RuntimeError, match="Session creation failed: Agent init failed"):
            await streaming_service.create_session("test_agent")
    
    async def test_create_session_logging(self, streaming_service):
        """Test that session creation logs appropriately."""
        with patch('src.services.streaming.streaming_service.logger') as mock_logger:
            session_id = await streaming_service.create_session("test_agent")
            
            # Should log creation start and success
            mock_logger.info.assert_any_call("Creating streaming session for agent test_agent")
            mock_logger.info.assert_any_call(f"Created streaming session {session_id} with agent test_agent")


@pytest.mark.unit
@pytest.mark.asyncio
class TestMessageProcessing:
    """Test cases for message processing."""
    
    async def test_process_message_success(self, streaming_service, mock_streaming_agent):
        """Test successful message processing."""
        session_id = "session_123"
        streaming_service.active_agents[session_id] = mock_streaming_agent
        
        await streaming_service.process_message(session_id, "Hello, agent!")
        
        # Verify session validation and activity update
        streaming_service.session_manager.is_session_active.assert_called_with(session_id)
        streaming_service.session_manager.update_session_activity.assert_called_with(session_id)
        streaming_service.session_manager.get_session_context.assert_called_with(session_id)
        
        # Verify transport events were sent
        streaming_service.transport.send_event.assert_called()
        assert streaming_service.transport.send_event.call_count >= 1
    
    async def test_process_message_inactive_session(self, streaming_service):
        """Test message processing with inactive session."""
        streaming_service.session_manager.is_session_active.return_value = False
        
        with pytest.raises(RuntimeError, match="Message processing failed: Session session_123 is not active"):
            await streaming_service.process_message("session_123", "Hello!")
    
    async def test_process_message_no_agent(self, streaming_service):
        """Test message processing when no agent is found."""
        session_id = "session_123"
        # Don't add agent to active_agents
        
        with pytest.raises(RuntimeError, match="Message processing failed: No active agent for session session_123"):
            await streaming_service.process_message(session_id, "Hello!")
    
    async def test_process_message_transport_send_failure(self, streaming_service, mock_streaming_agent):
        """Test message processing when transport fails to send events."""
        session_id = "session_123"
        streaming_service.active_agents[session_id] = mock_streaming_agent
        streaming_service.transport.send_event.return_value = False
        
        await streaming_service.process_message(session_id, "Hello!")
        
        # Should still complete without raising an exception
        # but log warnings about failed sends
    
    async def test_process_message_session_becomes_inactive(self, streaming_service, mock_streaming_agent):
        """Test message processing when session becomes inactive during processing."""
        session_id = "session_123" 
        streaming_service.active_agents[session_id] = mock_streaming_agent
        
        # Mock session becoming inactive during processing
        streaming_service.session_manager.is_session_active.side_effect = [True, True, False]
        
        await streaming_service.process_message(session_id, "Hello!")
        
        # Should stop processing when session becomes inactive
    
    async def test_process_message_agent_error_handling(self, streaming_service, mock_streaming_agent):
        """Test error handling during message processing."""
        session_id = "session_123"
        streaming_service.active_agents[session_id] = mock_streaming_agent
        
        # Mock agent raising error during processing
        async def failing_process_message(message, context):
            raise RuntimeError("Agent processing failed")
            yield  # This makes it an async generator (unreachable but required for type)
        
        mock_streaming_agent.process_message = failing_process_message
        
        with pytest.raises(RuntimeError, match="Message processing failed: Agent processing failed"):
            await streaming_service.process_message(session_id, "Hello!")
        
        # Should attempt to send error event
        streaming_service.transport.send_event.assert_called()
        error_call = streaming_service.transport.send_event.call_args_list[-1]
        error_event = error_call[0][1]
        assert error_event["event_type"] == "error"
        assert "Agent processing failed" in error_event["data"]["details"]
    
    async def test_process_message_error_with_inactive_session(self, streaming_service, mock_streaming_agent):
        """Test error handling when session becomes inactive before error event."""
        session_id = "session_123"
        streaming_service.active_agents[session_id] = mock_streaming_agent
        
        # Mock agent raising error and session becoming inactive
        async def failing_process_message(message, context):
            raise RuntimeError("Agent processing failed")
            yield  # This makes it an async generator (unreachable but required for type)
        
        mock_streaming_agent.process_message = failing_process_message
        streaming_service.session_manager.is_session_active.side_effect = [True, True, False]  # Inactive during error handling
        
        with pytest.raises(RuntimeError, match="Message processing failed"):
            await streaming_service.process_message(session_id, "Hello!")
        
        # Should not try to send error event to inactive session
    
    async def test_process_message_logging(self, streaming_service, mock_streaming_agent):
        """Test that message processing logs appropriately."""
        session_id = "session_123"
        streaming_service.active_agents[session_id] = mock_streaming_agent
        
        with patch('src.services.streaming.streaming_service.logger') as mock_logger:
            await streaming_service.process_message(session_id, "Hello, agent!")
            
            # Should log processing start and completion
            mock_logger.info.assert_any_call("Processing message for session session_123: Hello, agent!...")
            mock_logger.info.assert_any_call("Completed message processing for session session_123")


@pytest.mark.unit
@pytest.mark.asyncio
class TestEventStreaming:
    """Test cases for event streaming."""
    
    async def test_get_event_stream_success(self, streaming_service):
        """Test successful event stream creation."""
        session_id = "session_123"
        
        events = []
        async for event in streaming_service.get_event_stream(session_id):
            events.append(event)
        
        # Verify session validation
        streaming_service.session_manager.get_session.assert_called_with(session_id)
        
        # Verify events were received
        assert len(events) >= 1
        
        # Verify session activity was updated
        assert streaming_service.session_manager.update_session_activity.call_count >= 1
    
    async def test_get_event_stream_session_not_found(self, streaming_service):
        """Test event stream creation when session is not found."""
        streaming_service.session_manager.get_session.return_value = None
        
        with pytest.raises(ValueError, match="Session session_123 not found"):
            async for event in streaming_service.get_event_stream("session_123"):
                pass
    
    async def test_get_event_stream_transport_error(self, streaming_service):
        """Test event stream when transport raises error."""
        async def failing_create_stream(session_id):
            raise RuntimeError("Transport error")
            yield  # This makes it an async generator
        
        streaming_service.transport.create_stream = failing_create_stream
        
        with pytest.raises(RuntimeError, match="Transport error"):
            async for event in streaming_service.get_event_stream("session_123"):
                pass
    
    async def test_get_event_stream_cleanup_on_completion(self, streaming_service):
        """Test that session is cleaned up when event stream completes."""
        session_id = "session_123"
        
        with patch.object(streaming_service, 'close_session', new_callable=AsyncMock) as mock_close:
            events = []
            stream = streaming_service.get_event_stream(session_id)
            async for event in stream:
                events.append(event)
                if len(events) >= 2:  # Stop after receiving some events
                    break
            
            # Explicitly close the async generator to trigger finally block
            await stream.aclose()
        
        # Should clean up session
        mock_close.assert_called_once_with(session_id)
    
    async def test_get_event_stream_cleanup_on_error(self, streaming_service):
        """Test that session is cleaned up when event stream has error."""
        session_id = "session_123"
        
        async def error_stream(session_id):
            yield "event1"
            raise RuntimeError("Stream error")
        
        streaming_service.transport.create_stream = error_stream
        
        with patch.object(streaming_service, 'close_session', new_callable=AsyncMock) as mock_close:
            with pytest.raises(RuntimeError, match="Stream error"):
                async for event in streaming_service.get_event_stream(session_id):
                    pass
        
        # Should still clean up session
        mock_close.assert_called_once_with(session_id)


@pytest.mark.unit
@pytest.mark.asyncio
class TestSessionClosure:
    """Test cases for session closure."""
    
    async def test_close_session_success(self, streaming_service, mock_streaming_agent):
        """Test successful session closure."""
        session_id = "session_123"
        streaming_service.active_agents[session_id] = mock_streaming_agent
        
        result = await streaming_service.close_session(session_id)
        
        assert result is True
        
        # Verify agent cleanup
        mock_streaming_agent.cleanup.assert_called_once()
        assert session_id not in streaming_service.active_agents
        
        # Verify transport closure
        streaming_service.transport.close_session.assert_called_once_with(session_id)
        
        # Verify session manager closure
        streaming_service.session_manager.close_session.assert_called_once_with(session_id)
    
    async def test_close_session_no_agent(self, streaming_service):
        """Test session closure when no agent exists."""
        session_id = "session_123"
        # Don't add agent to active_agents
        
        result = await streaming_service.close_session(session_id)
        
        assert result is True  # Should still succeed
        
        # Should still close transport and session manager
        streaming_service.transport.close_session.assert_called_once_with(session_id)
        streaming_service.session_manager.close_session.assert_called_once_with(session_id)
    
    async def test_close_session_agent_cleanup_error(self, streaming_service, mock_streaming_agent):
        """Test session closure when agent cleanup raises error."""
        session_id = "session_123"
        streaming_service.active_agents[session_id] = mock_streaming_agent
        mock_streaming_agent.cleanup.side_effect = RuntimeError("Cleanup failed")
        
        result = await streaming_service.close_session(session_id)
        
        # Should return False due to error
        assert result is False
        
        # Agent cleanup failure causes entire operation to fail, so transport and session manager are not called
        streaming_service.transport.close_session.assert_not_called()
        streaming_service.session_manager.close_session.assert_not_called()
    
    async def test_close_session_session_manager_failure(self, streaming_service, mock_streaming_agent):
        """Test session closure when session manager returns False."""
        session_id = "session_123"
        streaming_service.active_agents[session_id] = mock_streaming_agent
        streaming_service.session_manager.close_session.return_value = False
        
        result = await streaming_service.close_session(session_id)
        
        assert result is False
        
        # Should still clean up agent and transport
        mock_streaming_agent.cleanup.assert_called_once()
        streaming_service.transport.close_session.assert_called_once_with(session_id)
    
    async def test_close_session_logging(self, streaming_service, mock_streaming_agent):
        """Test that session closure logs appropriately."""
        session_id = "session_123"
        streaming_service.active_agents[session_id] = mock_streaming_agent
        
        with patch('src.services.streaming.streaming_service.logger') as mock_logger:
            await streaming_service.close_session(session_id)
            
            # Should log closure start and success
            mock_logger.info.assert_any_call("Closing session session_123")
            mock_logger.info.assert_any_call("Successfully closed session session_123")


@pytest.mark.unit
class TestSessionInformation:
    """Test cases for session information retrieval."""
    
    def test_get_session_info_success(self, streaming_service, mock_streaming_agent):
        """Test getting session info for existing session."""
        session_id = "session_123"
        streaming_service.active_agents[session_id] = mock_streaming_agent
        
        mock_session = Mock()
        mock_session.dict.return_value = {"session_id": session_id, "agent_id": "test_agent"}
        streaming_service.session_manager.get_session.return_value = mock_session
        
        # Setup transport mock properly
        streaming_service.transport.get_session_info.return_value = {"transport": "sse", "active": True}
        
        info = streaming_service.get_session_info(session_id)
        
        assert info is not None
        assert "session" in info
        assert "transport" in info
        assert "agent" in info
        assert "is_active" in info
        
        assert info["session"] == {"session_id": session_id, "agent_id": "test_agent"}
        assert info["transport"] == {"transport": "sse", "active": True}
        assert info["agent"] == {
            "id": "test_agent",
            "name": "Test Agent", 
            "framework": "test"
        }
        assert info["is_active"] is True
    
    def test_get_session_info_not_found(self, streaming_service):
        """Test getting session info for non-existent session."""
        streaming_service.session_manager.get_session.return_value = None
        
        info = streaming_service.get_session_info("non_existent")
        
        assert info is None
    
    def test_get_session_info_no_agent(self, streaming_service):
        """Test getting session info when no agent exists."""
        session_id = "session_123"
        # Don't add agent to active_agents
        
        mock_session = Mock()
        mock_session.dict.return_value = {"session_id": session_id}
        streaming_service.session_manager.get_session.return_value = mock_session
        
        info = streaming_service.get_session_info(session_id)
        
        assert info is not None
        assert info["agent"] == {}
    
    def test_get_session_info_transport_without_method(self, streaming_service):
        """Test getting session info when transport doesn't have get_session_info."""
        session_id = "session_123"
        
        mock_session = Mock()
        mock_session.dict.return_value = {"session_id": session_id}
        streaming_service.session_manager.get_session.return_value = mock_session
        
        # Remove get_session_info method from transport mock
        delattr(streaming_service.transport, 'get_session_info')
        
        info = streaming_service.get_session_info(session_id)
        
        assert info is not None
        assert info["transport"] == {}


@pytest.mark.unit
class TestServiceStatistics:
    """Test cases for service statistics."""
    
    def test_get_service_stats(self, streaming_service):
        """Test getting service statistics."""
        # Setup transport mock properly
        streaming_service.transport.get_active_session_count.return_value = 1
        
        stats = streaming_service.get_service_stats()
        
        assert "sessions" in stats
        assert "transport" in stats
        assert "active_agents" in stats
        assert "service_status" in stats
        
        assert stats["sessions"]["total_active_sessions"] == 1
        assert stats["transport"]["active_connections"] == 1
        assert stats["active_agents"] == 0  # No agents added in this test
        assert stats["service_status"] == "running"
    
    def test_get_service_stats_with_agents(self, streaming_service, mock_streaming_agent):
        """Test service stats with active agents."""
        streaming_service.active_agents["session1"] = mock_streaming_agent
        streaming_service.active_agents["session2"] = mock_streaming_agent
        
        stats = streaming_service.get_service_stats()
        
        assert stats["active_agents"] == 2
    
    def test_get_service_stats_transport_without_method(self, streaming_service):
        """Test service stats when transport doesn't have get_active_session_count."""
        # Remove method from transport mock
        delattr(streaming_service.transport, 'get_active_session_count')
        
        stats = streaming_service.get_service_stats()
        
        assert stats["transport"] == {}


@pytest.mark.unit
class TestAgentListing:
    """Test cases for agent listing functionality."""
    
    def test_list_available_agents(self, streaming_service, mock_streaming_factory):
        """Test listing available agents."""
        agents = streaming_service.list_available_agents()
        
        mock_streaming_factory.list_available_agents.assert_called_once()
        assert agents == [
            {"id": "agent1", "name": "Agent 1"},
            {"id": "agent2", "name": "Agent 2"}
        ]
    
    def test_list_knowledge_agents(self, streaming_service, mock_streaming_factory):
        """Test listing knowledge agents."""
        agents = streaming_service.list_knowledge_agents()
        
        mock_streaming_factory.list_knowledge_agents.assert_called_once()
        assert agents == [
            {"id": "knowledge_agent", "name": "Knowledge Agent"}
        ]


@pytest.mark.unit
@pytest.mark.asyncio
class TestServiceCleanup:
    """Test cases for service cleanup."""
    
    async def test_cleanup_success(self, streaming_service, mock_streaming_agent):
        """Test successful service cleanup."""
        # Add some active agents
        streaming_service.active_agents["session1"] = mock_streaming_agent
        streaming_service.active_agents["session2"] = mock_streaming_agent
        
        # Create a proper asyncio Task mock that can be awaited
        async def dummy_task():
            return None
        
        mock_task = asyncio.create_task(dummy_task())
        streaming_service._cleanup_task = mock_task
        
        with patch.object(streaming_service, 'close_session', new_callable=AsyncMock) as mock_close:
            await streaming_service.cleanup()
            
            # Should cancel cleanup task (real task, so just verify it was cancelled)
            assert mock_task.cancelled() or mock_task.done()
            
            # Should close all active sessions
            assert mock_close.call_count == 2
            mock_close.assert_any_call("session1")
            mock_close.assert_any_call("session2")
    
    async def test_cleanup_no_cleanup_task(self, streaming_service):
        """Test cleanup when no cleanup task exists."""
        streaming_service._cleanup_task = None
        
        # Should not raise error
        await streaming_service.cleanup()
    
    async def test_cleanup_task_cancellation_error(self, streaming_service):
        """Test cleanup when task cancellation raises CancelledError."""
        # Create a task that will raise CancelledError when awaited
        async def cancellable_task():
            await asyncio.sleep(10)  # This will be cancelled
        
        mock_task = asyncio.create_task(cancellable_task())
        streaming_service._cleanup_task = mock_task
        
        # Should handle CancelledError gracefully
        await streaming_service.cleanup()
        
        # Task should be cancelled
        assert mock_task.cancelled() or mock_task.done()
    
    async def test_cleanup_logging(self, streaming_service):
        """Test that cleanup logs appropriately."""
        # Set cleanup task to None to avoid await issues
        streaming_service._cleanup_task = None
        
        with patch('src.services.streaming.streaming_service.logger') as mock_logger:
            await streaming_service.cleanup()
            
            # Should log cleanup start and completion
            mock_logger.info.assert_any_call("Cleaning up streaming service")
            mock_logger.info.assert_any_call("Streaming service cleanup completed")


@pytest.mark.unit
class TestBackgroundCleanup:
    """Test cases for background cleanup functionality."""
    
    @patch('src.services.streaming.streaming_service.asyncio.create_task')
    def test_start_cleanup_task_creation(self, mock_create_task):
        """Test that cleanup task is created correctly."""
        with patch('src.services.streaming.streaming_service.SessionManager'):
            with patch('src.services.streaming.streaming_service.StreamingFactory'):
                service = StreamingService()
                
                # Should create background task
                mock_create_task.assert_called_once()
                # Store task reference
                assert service._cleanup_task == mock_create_task.return_value


@pytest.mark.unit
class TestPrivateMethods:
    """Test cases for private methods."""
    
    def test_get_timestamp(self, streaming_service):
        """Test timestamp generation."""
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value.isoformat.return_value = "2023-01-01T12:00:00"
            
            timestamp = streaming_service._get_timestamp()
            
            assert timestamp == "2023-01-01T12:00:00Z"
            mock_datetime.utcnow.assert_called_once()
            mock_datetime.utcnow.return_value.isoformat.assert_called_once()
