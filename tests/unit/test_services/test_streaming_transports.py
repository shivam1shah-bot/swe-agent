"""
Unit tests for streaming transports.

Tests for BaseTransport abstract interface and SSETransport implementation.
"""

import pytest
import asyncio
import json
from abc import ABC
from typing import AsyncGenerator, Dict, Any
from unittest.mock import Mock, patch, AsyncMock

from src.services.streaming.transports.base_transport import BaseTransport
from src.services.streaming.transports.sse_transport import SSETransport


class TestTransport(BaseTransport):
    """Test implementation of BaseTransport for testing."""
    
    def __init__(self):
        """Initialize test transport."""
        self.active_sessions = {}
        self.sent_events = []
        self.closed_sessions = []
    
    async def send_event(self, session_id: str, event: Dict[str, Any]) -> bool:
        """Test implementation of send_event."""
        if session_id not in self.active_sessions:
            return False
        
        self.sent_events.append((session_id, event))
        return True
    
    async def create_stream(self, session_id: str) -> AsyncGenerator[str, None]:
        """Test implementation of create_stream."""
        if session_id == "invalid_session":
            raise ValueError("Invalid session")
        
        self.active_sessions[session_id] = True
        
        yield f"event: connection_opened\ndata: {{\"session_id\": \"{session_id}\"}}\n\n"
        yield f"event: test_event\ndata: {{\"message\": \"test\"}}\n\n"
        yield f"event: connection_closed\ndata: {{\"session_id\": \"{session_id}\"}}\n\n"
    
    async def close_session(self, session_id: str) -> None:
        """Test implementation of close_session."""
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
        self.closed_sessions.append(session_id)
    
    def is_session_active(self, session_id: str) -> bool:
        """Test implementation of is_session_active."""
        return session_id in self.active_sessions


@pytest.mark.unit
class TestBaseTransportInterface:
    """Test cases for BaseTransport abstract interface."""
    
    def test_base_transport_is_abstract(self):
        """Test that BaseTransport is an abstract base class."""
        assert issubclass(BaseTransport, ABC)
        
        # Should not be able to instantiate directly
        with pytest.raises(TypeError):
            BaseTransport()
    
    def test_abstract_methods_defined(self):
        """Test that required abstract methods are defined."""
        abstract_methods = BaseTransport.__abstractmethods__
        
        expected_methods = {
            'send_event',
            'create_stream',
            'close_session',
            'is_session_active'
        }
        
        assert abstract_methods == expected_methods
    
    def test_concrete_implementation_works(self):
        """Test that concrete implementation can be instantiated."""
        transport = TestTransport()
        assert isinstance(transport, BaseTransport)
    
    def test_get_transport_type_default(self):
        """Test default transport type implementation."""
        transport = TestTransport()
        transport_type = transport.get_transport_type()
        
        # Should remove 'transport' from class name and lowercase
        assert transport_type == "test"
    
    def test_get_transport_type_sse(self):
        """Test transport type for SSE transport."""
        sse_transport = SSETransport()
        transport_type = sse_transport.get_transport_type()
        
        assert transport_type == "sse"


@pytest.mark.unit
@pytest.mark.asyncio
class TestTestTransportImplementation:
    """Test cases for the test transport implementation."""
    
    async def test_send_event_success(self):
        """Test successful event sending."""
        transport = TestTransport()
        transport.active_sessions["session_123"] = True
        
        event = {"event_type": "test", "data": {"message": "hello"}}
        result = await transport.send_event("session_123", event)
        
        assert result is True
        assert len(transport.sent_events) == 1
        assert transport.sent_events[0] == ("session_123", event)
    
    async def test_send_event_inactive_session(self):
        """Test sending event to inactive session."""
        transport = TestTransport()
        
        event = {"event_type": "test", "data": {"message": "hello"}}
        result = await transport.send_event("inactive_session", event)
        
        assert result is False
        assert len(transport.sent_events) == 0
    
    async def test_create_stream_success(self):
        """Test successful stream creation."""
        transport = TestTransport()
        
        events = []
        async for event in transport.create_stream("session_123"):
            events.append(event)
        
        assert len(events) == 3
        assert "connection_opened" in events[0]
        assert "test_event" in events[1]
        assert "connection_closed" in events[2]
        assert "session_123" in transport.active_sessions
    
    async def test_create_stream_invalid_session(self):
        """Test stream creation with invalid session."""
        transport = TestTransport()
        
        with pytest.raises(ValueError, match="Invalid session"):
            async for event in transport.create_stream("invalid_session"):
                pass
    
    async def test_close_session_active(self):
        """Test closing active session."""
        transport = TestTransport()
        transport.active_sessions["session_123"] = True
        
        await transport.close_session("session_123")
        
        assert "session_123" not in transport.active_sessions
        assert "session_123" in transport.closed_sessions
    
    async def test_close_session_inactive(self):
        """Test closing inactive session."""
        transport = TestTransport()
        
        await transport.close_session("inactive_session")
        
        assert "inactive_session" in transport.closed_sessions
    
    def test_is_session_active_true(self):
        """Test checking active session."""
        transport = TestTransport()
        transport.active_sessions["session_123"] = True
        
        assert transport.is_session_active("session_123") is True
    
    def test_is_session_active_false(self):
        """Test checking inactive session."""
        transport = TestTransport()
        
        assert transport.is_session_active("session_123") is False


@pytest.mark.unit
class TestSSETransportInitialization:
    """Test cases for SSETransport initialization."""
    
    def test_sse_transport_creation(self):
        """Test creating SSETransport instance."""
        with patch('src.services.streaming.transports.sse_transport.logger') as mock_logger:
            transport = SSETransport()
            
            assert transport.active_sessions == {}
            assert transport.session_metadata == {}
            mock_logger.info.assert_called_with("SSE transport initialized")
    
    def test_sse_transport_type(self):
        """Test SSE transport type."""
        transport = SSETransport()
        assert transport.get_transport_type() == "sse"


@pytest.mark.unit
@pytest.mark.asyncio
class TestSSETransportSendEvent:
    """Test cases for SSE transport event sending."""
    
    async def test_send_event_success(self):
        """Test successful event sending."""
        transport = SSETransport()
        
        # Create a session with queue
        session_id = "session_123"
        queue = asyncio.Queue()
        transport.active_sessions[session_id] = queue
        
        event = {"event_type": "agent_message", "data": {"content": "Hello"}}
        
        with patch.object(transport, '_format_sse_event', return_value="formatted_event") as mock_format:
            result = await transport.send_event(session_id, event)
            
            assert result is True
            mock_format.assert_called_once_with(event)
            
            # Check that event was queued
            queued_event = await asyncio.wait_for(queue.get(), timeout=1.0)
            assert queued_event == "formatted_event"
    
    async def test_send_event_inactive_session(self):
        """Test sending event to inactive session."""
        transport = SSETransport()
        
        event = {"event_type": "test", "data": {}}
        
        with patch('src.services.streaming.transports.sse_transport.logger') as mock_logger:
            result = await transport.send_event("inactive_session", event)
            
            assert result is False
            mock_logger.warning.assert_called_with(
                "Attempted to send event to inactive session: inactive_session"
            )
    
    async def test_send_event_queue_error(self):
        """Test event sending when queue operations fail."""
        transport = SSETransport()
        
        # Create a mock queue that raises an exception
        mock_queue = AsyncMock()
        mock_queue.put.side_effect = Exception("Queue error")
        
        session_id = "session_123"
        transport.active_sessions[session_id] = mock_queue
        
        event = {"event_type": "test", "data": {}}
        
        with patch('src.services.streaming.transports.sse_transport.logger') as mock_logger:
            with patch.object(transport, 'close_session', new_callable=AsyncMock) as mock_close:
                result = await transport.send_event(session_id, event)
                
                assert result is False
                mock_logger.error.assert_called()
                mock_close.assert_called_once_with(session_id)


@pytest.mark.unit
@pytest.mark.asyncio
class TestSSETransportCreateStream:
    """Test cases for SSE transport stream creation."""
    
    async def test_create_stream_success(self):
        """Test successful stream creation."""
        transport = SSETransport()
        session_id = "session_123"
        
        with patch('src.services.streaming.transports.sse_transport.logger') as mock_logger:
            with patch.object(transport, '_get_timestamp', return_value="2023-01-01T12:00:00Z"):
                # Start stream and collect some events
                events = []
                count = 0
                async for event in transport.create_stream(session_id):
                    events.append(event)
                    count += 1
                    if count >= 2:  # Get connection event + one more
                        break
                
                # Verify stream creation was logged
                mock_logger.info.assert_any_call(f"Creating SSE stream for session: {session_id}")
                
                # Verify we received some events
                assert len(events) >= 1
    
    async def test_create_stream_with_events(self):
        """Test stream creation and event delivery."""
        transport = SSETransport()
        session_id = "session_123"
        
        # Start stream in background
        events = []
        stream_task = asyncio.create_task(self._collect_stream_events(transport, session_id, events, max_events=2))
        
        # Wait for stream to initialize
        await asyncio.sleep(0.1)
        
        # Send test event
        test_event = {"event_type": "agent_message", "data": {"content": "Hello"}}
        await transport.send_event(session_id, test_event)
        
        # Wait for processing
        await asyncio.sleep(0.1)
        
        # Close session to end stream
        await transport.close_session(session_id)
        
        # Wait for stream to complete
        try:
            await asyncio.wait_for(stream_task, timeout=2.0)
        except asyncio.TimeoutError:
            stream_task.cancel()
            try:
                await stream_task
            except asyncio.CancelledError:
                pass
        
        # Should have received events
        assert len(events) >= 1
    
    async def test_create_stream_timeout_ping(self):
        """Test stream timeout handling with ping events."""
        transport = SSETransport()
        session_id = "session_123"
        
        # Mock asyncio.wait_for to simulate timeout
        original_wait_for = asyncio.wait_for
        call_count = 0
        
        async def mock_wait_for(coro, timeout):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call - connection event
                return await original_wait_for(coro, timeout=0.1)
            else:
                # Subsequent calls - simulate timeout
                raise asyncio.TimeoutError()
        
        events = []
        with patch('asyncio.wait_for', side_effect=mock_wait_for):
            with patch.object(transport, '_get_timestamp', return_value="2023-01-01T12:00:00Z"):
                stream_task = asyncio.create_task(self._collect_stream_events(transport, session_id, events, max_events=2))
                
                # Wait for ping event generation
                await asyncio.sleep(0.2)
                
                # Cancel stream
                stream_task.cancel()
                try:
                    await stream_task
                except asyncio.CancelledError:
                    pass
        
        # Should have generated ping events
        ping_events = [event for event in events if "ping" in event]
        assert len(ping_events) >= 1
    
    async def test_create_stream_error_handling(self):
        """Test stream error handling."""
        transport = SSETransport()
        session_id = "session_123"
        
        # Mock queue.get to raise an error after first event
        call_count = 0
        
        async def mock_queue_get():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return transport._format_sse_event({"event_type": "connection_opened", "data": {"session_id": session_id}})
            else:
                raise RuntimeError("Queue error")
        
        with patch('asyncio.Queue') as mock_queue_class:
            mock_queue = AsyncMock()
            mock_queue.get = mock_queue_get
            mock_queue.put = AsyncMock()
            mock_queue_class.return_value = mock_queue
            
            with patch('src.services.streaming.transports.sse_transport.logger') as mock_logger:
                events = []
                try:
                    async for event in transport.create_stream(session_id):
                        events.append(event)
                except Exception:
                    pass
                
                # Should log error
                mock_logger.error.assert_called()
    
    async def _collect_stream_events(self, transport, session_id, events_list, max_events=10):
        """Helper method to collect stream events."""
        count = 0
        async for event in transport.create_stream(session_id):
            events_list.append(event)
            count += 1
            if count >= max_events:
                break


@pytest.mark.unit
@pytest.mark.asyncio
class TestSSETransportCloseSession:
    """Test cases for SSE transport session closure."""
    
    async def test_close_session_active(self):
        """Test closing active session."""
        transport = SSETransport()
        session_id = "session_123"
        
        # Create active session
        queue = asyncio.Queue()
        transport.active_sessions[session_id] = queue
        transport.session_metadata[session_id] = {"event_count": 5}
        
        with patch('src.services.streaming.transports.sse_transport.logger') as mock_logger:
            with patch.object(transport, '_get_timestamp', return_value="2023-01-01T12:00:00Z"):
                await transport.close_session(session_id)
                
                # Session should be removed
                assert session_id not in transport.active_sessions
                assert session_id not in transport.session_metadata
                
                # Should log closure with event count
                mock_logger.info.assert_any_call(f"Closing SSE session: {session_id}")
                mock_logger.info.assert_any_call(f"Session {session_id} closed. Events sent: 5")
    
    async def test_close_session_inactive(self):
        """Test closing inactive session."""
        transport = SSETransport()
        session_id = "inactive_session"
        
        with patch('src.services.streaming.transports.sse_transport.logger') as mock_logger:
            await transport.close_session(session_id)
            
            # Should log that session was already closed
            mock_logger.debug.assert_called_with(f"Session {session_id} was already closed or did not exist")
    
    async def test_close_session_send_event_error(self):
        """Test closing session when sending close event fails."""
        transport = SSETransport()
        session_id = "session_123"
        
        # Create active session with queue that will fail
        mock_queue = AsyncMock()
        mock_queue.put.side_effect = Exception("Queue error")
        transport.active_sessions[session_id] = mock_queue
        
        with patch('src.services.streaming.transports.sse_transport.logger') as mock_logger:
            with patch.object(transport, '_get_timestamp', return_value="2023-01-01T12:00:00Z"):
                await transport.close_session(session_id)
                
                # Should log warning about close event error
                mock_logger.warning.assert_called()
                
                # Session should still be cleaned up
                assert session_id not in transport.active_sessions
    
    async def test_close_session_cleanup_metadata_only(self):
        """Test closing session that has metadata but no active session."""
        transport = SSETransport()
        session_id = "session_123"
        
        # Add only metadata, no active session
        transport.session_metadata[session_id] = {"event_count": 3}
        
        await transport.close_session(session_id)
        
        # Metadata should be cleaned up
        assert session_id not in transport.session_metadata


@pytest.mark.unit
class TestSSETransportUtilityMethods:
    """Test cases for SSE transport utility methods."""
    
    def test_is_session_active_true(self):
        """Test checking active session."""
        transport = SSETransport()
        session_id = "session_123"
        transport.active_sessions[session_id] = asyncio.Queue()
        
        assert transport.is_session_active(session_id) is True
    
    def test_is_session_active_false(self):
        """Test checking inactive session."""
        transport = SSETransport()
        
        assert transport.is_session_active("inactive_session") is False
    
    def test_get_active_session_count(self):
        """Test getting active session count."""
        transport = SSETransport()
        
        assert transport.get_active_session_count() == 0
        
        # Add some sessions
        transport.active_sessions["session1"] = asyncio.Queue()
        transport.active_sessions["session2"] = asyncio.Queue()
        
        assert transport.get_active_session_count() == 2
    
    def test_get_session_info_exists(self):
        """Test getting info for existing session."""
        transport = SSETransport()
        session_id = "session_123"
        
        transport.active_sessions[session_id] = asyncio.Queue()
        transport.session_metadata[session_id] = {
            "created_at": 1234567890,
            "event_count": 10
        }
        
        info = transport.get_session_info(session_id)
        
        assert info["session_id"] == session_id
        assert info["transport"] == "sse"
        assert info["active"] is True
        assert info["created_at"] == 1234567890
        assert info["event_count"] == 10
    
    def test_get_session_info_not_exists(self):
        """Test getting info for non-existent session."""
        transport = SSETransport()
        
        info = transport.get_session_info("non_existent")
        
        assert info == {}
    
    def test_format_sse_event_success(self):
        """Test successful SSE event formatting."""
        transport = SSETransport()
        
        event = {
            "event_type": "agent_message",
            "data": {"content": "Hello world"},
            "timestamp": "2023-01-01T12:00:00Z"
        }
        
        formatted = transport._format_sse_event(event)
        
        expected_json = json.dumps(event, default=str)
        expected = f"data: {expected_json}\n\n"
        
        assert formatted == expected
    
    def test_format_sse_event_json_error(self):
        """Test SSE event formatting with JSON serialization error."""
        transport = SSETransport()
        
        # Create event that will cause JSON serialization to fail
        event = {
            "event_type": "error_test",
            "data": {"message": "test"}
        }
        
        # Save original json.dumps before patching
        import json
        original_dumps = json.dumps
        
        # Mock json.dumps to fail on first call but succeed on error event
        call_count = 0
        def mock_dumps(obj, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TypeError("Not serializable")
            # Use original dumps for error event
            return original_dumps(obj, **kwargs)
        
        with patch('src.services.streaming.transports.sse_transport.json.dumps', side_effect=mock_dumps):
            with patch('src.services.streaming.transports.sse_transport.logger') as mock_logger:
                formatted = transport._format_sse_event(event)
                
                # Should return error event
                assert "error" in formatted
                assert "Failed to format event" in formatted
                mock_logger.error.assert_called()
    
    def test_get_timestamp(self):
        """Test timestamp generation."""
        transport = SSETransport()
        
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value.isoformat.return_value = "2023-01-01T12:00:00"
            
            timestamp = transport._get_timestamp()
            
            assert timestamp == "2023-01-01T12:00:00Z"
            mock_datetime.utcnow.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
class TestSSETransportIntegration:
    """Integration tests for SSE transport functionality."""
    
    async def test_full_session_lifecycle(self):
        """Test complete session lifecycle."""
        transport = SSETransport()
        session_id = "integration_test_session"
        
        # 1. Check initial state
        assert not transport.is_session_active(session_id)
        assert transport.get_active_session_count() == 0
        
        # 2. Create stream (this creates the session)
        events = []
        stream_task = asyncio.create_task(self._collect_events_with_limit(transport, session_id, events, 3))
        
        # Wait for stream initialization
        await asyncio.sleep(0.1)
        
        # 3. Verify session is active
        assert transport.is_session_active(session_id)
        assert transport.get_active_session_count() == 1
        
        # 4. Send events
        await transport.send_event(session_id, {"event_type": "test1", "data": {"msg": "first"}})
        await transport.send_event(session_id, {"event_type": "test2", "data": {"msg": "second"}})
        
        # Wait for event processing
        await asyncio.sleep(0.1)
        
        # 5. Close session
        await transport.close_session(session_id)
        
        # Wait for stream to complete
        try:
            await asyncio.wait_for(stream_task, timeout=2.0)
        except asyncio.TimeoutError:
            stream_task.cancel()
            try:
                await stream_task
            except asyncio.CancelledError:
                pass
        
        # 6. Verify final state
        assert not transport.is_session_active(session_id)
        assert transport.get_active_session_count() == 0
        assert len(events) >= 2  # At least connection and test events
    
    async def test_multiple_sessions(self):
        """Test handling multiple simultaneous sessions."""
        transport = SSETransport()
        
        session_ids = ["session_1", "session_2", "session_3"]
        tasks = []
        all_events = {}
        
        # Start streams for multiple sessions
        for session_id in session_ids:
            events = []
            all_events[session_id] = events
            task = asyncio.create_task(self._collect_events_with_limit(transport, session_id, events, 2))
            tasks.append(task)
        
        # Wait for initialization
        await asyncio.sleep(0.1)
        
        # Verify all sessions are active
        for session_id in session_ids:
            assert transport.is_session_active(session_id)
        assert transport.get_active_session_count() == 3
        
        # Send events to different sessions
        await transport.send_event("session_1", {"event_type": "msg", "data": {"to": "session_1"}})
        await transport.send_event("session_2", {"event_type": "msg", "data": {"to": "session_2"}})
        await transport.send_event("session_3", {"event_type": "msg", "data": {"to": "session_3"}})
        
        # Wait for processing
        await asyncio.sleep(0.1)
        
        # Close all sessions
        for session_id in session_ids:
            await transport.close_session(session_id)
        
        # Wait for all streams to complete
        for task in tasks:
            try:
                await asyncio.wait_for(task, timeout=1.0)
            except asyncio.TimeoutError:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Verify all sessions are closed
        for session_id in session_ids:
            assert not transport.is_session_active(session_id)
        assert transport.get_active_session_count() == 0
    
    async def _collect_events_with_limit(self, transport, session_id, events_list, max_events):
        """Helper to collect events with a limit."""
        count = 0
        async for event in transport.create_stream(session_id):
            events_list.append(event)
            count += 1
            if count >= max_events:
                break
