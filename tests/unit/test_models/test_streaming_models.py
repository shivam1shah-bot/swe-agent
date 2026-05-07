"""
Unit tests for streaming models.

Tests for StreamingSession, StreamingMessage, and StreamingEvent models.
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import patch
from pydantic import ValidationError

from src.models.streaming.session import (
    StreamingSession, 
    CreateSessionRequest, 
    SessionResponse
)
from src.models.streaming.message import (
    StreamingMessage,
    MessageRequest,
    MessageResponse
)
from src.models.streaming.event import (
    StreamingEvent,
    ToolExecutionStartEvent,
    ToolExecutionCompleteEvent,
    AgentMessageEvent,
    TurnCompleteEvent,
    SystemEvent,
    EventTypes
)


@pytest.mark.unit
class TestStreamingSession:
    """Test cases for StreamingSession model."""
    
    def test_streaming_session_creation(self):
        """Test creating a streaming session with required fields."""
        session = StreamingSession(
            session_id="session_123",
            agent_id="trino_agent",
            agent_name="Trino Assistant"
        )
        
        assert session.session_id == "session_123"
        assert session.agent_id == "trino_agent"
        assert session.agent_name == "Trino Assistant"
        assert session.status == "active"
        assert session.transport_type == "sse"
        assert session.user_context == {}
        assert session.agent_context == {}
        assert session.metadata == {}
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.last_activity, datetime)
    
    def test_streaming_session_with_optional_fields(self):
        """Test creating a streaming session with all optional fields."""
        user_context = {"user_id": "test_user", "preferences": {"theme": "dark"}}
        agent_context = {"config": {"timeout": 30}}
        metadata = {"source": "api", "version": "1.0"}
        
        session = StreamingSession(
            session_id="session_456",
            agent_id="code_agent", 
            agent_name="Code Assistant",
            status="inactive",
            transport_type="websocket",
            user_context=user_context,
            agent_context=agent_context,
            metadata=metadata
        )
        
        assert session.session_id == "session_456"
        assert session.agent_id == "code_agent"
        assert session.agent_name == "Code Assistant"
        assert session.status == "inactive"
        assert session.transport_type == "websocket"
        assert session.user_context == user_context
        assert session.agent_context == agent_context
        assert session.metadata == metadata
    
    def test_update_activity(self):
        """Test updating session activity timestamp."""
        session = StreamingSession(
            session_id="session_789",
            agent_id="test_agent",
            agent_name="Test Agent"
        )
        
        original_activity = session.last_activity
        
        # Mock datetime to ensure we can detect the change
        with patch('src.models.streaming.session.datetime') as mock_datetime:
            new_time = original_activity + timedelta(minutes=1)
            mock_datetime.utcnow.return_value = new_time
            
            session.update_activity()
            
            assert session.last_activity == new_time
            assert session.last_activity != original_activity
    
    def test_close_session(self):
        """Test closing a session."""
        session = StreamingSession(
            session_id="session_close",
            agent_id="test_agent",
            agent_name="Test Agent"
        )
        
        assert session.status == "active"
        assert session.is_active() is True
        
        with patch('src.models.streaming.session.datetime') as mock_datetime:
            close_time = session.last_activity + timedelta(minutes=1)
            mock_datetime.utcnow.return_value = close_time
            
            session.close()
            
            assert session.status == "closed"
            assert session.is_active() is False
            assert session.last_activity == close_time
    
    def test_is_active(self):
        """Test session active status check."""
        # Active session
        active_session = StreamingSession(
            session_id="active_session",
            agent_id="test_agent",
            agent_name="Test Agent",
            status="active"
        )
        assert active_session.is_active() is True
        
        # Inactive session
        inactive_session = StreamingSession(
            session_id="inactive_session",
            agent_id="test_agent", 
            agent_name="Test Agent",
            status="inactive"
        )
        assert inactive_session.is_active() is False
        
        # Closed session
        closed_session = StreamingSession(
            session_id="closed_session",
            agent_id="test_agent",
            agent_name="Test Agent", 
            status="closed"
        )
        assert closed_session.is_active() is False
    
    def test_json_serialization(self):
        """Test JSON serialization of streaming session."""
        session = StreamingSession(
            session_id="json_test",
            agent_id="test_agent",
            agent_name="Test Agent"
        )
        
        # Should be able to serialize to JSON
        json_data = session.model_dump_json()
        parsed_data = json.loads(json_data)
        
        assert parsed_data["session_id"] == "json_test"
        assert parsed_data["agent_id"] == "test_agent"
        assert parsed_data["agent_name"] == "Test Agent"
        assert "created_at" in parsed_data
        assert "last_activity" in parsed_data
    
    def test_validation_errors(self):
        """Test validation errors for required fields."""
        # Missing required fields
        with pytest.raises(ValidationError):
            StreamingSession()
        
        with pytest.raises(ValidationError):
            StreamingSession(session_id="test")
        
        with pytest.raises(ValidationError):
            StreamingSession(
                session_id="test",
                agent_id="agent"
            )


@pytest.mark.unit
class TestCreateSessionRequest:
    """Test cases for CreateSessionRequest model."""
    
    def test_create_session_request_minimal(self):
        """Test creating session request with minimal fields."""
        request = CreateSessionRequest(agent_id="test_agent")
        
        assert request.agent_id == "test_agent"
        assert request.transport_type == "sse"
        assert request.user_context is None
    
    def test_create_session_request_full(self):
        """Test creating session request with all fields."""
        user_context = {"user_id": "123", "role": "admin"}
        
        request = CreateSessionRequest(
            agent_id="full_agent",
            transport_type="websocket",
            user_context=user_context
        )
        
        assert request.agent_id == "full_agent"
        assert request.transport_type == "websocket"
        assert request.user_context == user_context


@pytest.mark.unit
class TestSessionResponse:
    """Test cases for SessionResponse model."""
    
    def test_session_response_creation(self):
        """Test creating session response."""
        created_at = datetime.utcnow()
        
        response = SessionResponse(
            session_id="resp_123",
            agent_id="test_agent",
            agent_name="Test Agent",
            status="active",
            created_at=created_at,
            transport_type="sse"
        )
        
        assert response.session_id == "resp_123"
        assert response.agent_id == "test_agent"
        assert response.agent_name == "Test Agent"
        assert response.status == "active"
        assert response.created_at == created_at
        assert response.transport_type == "sse"


@pytest.mark.unit
class TestStreamingMessage:
    """Test cases for StreamingMessage model."""
    
    def test_streaming_message_creation(self):
        """Test creating a streaming message with required fields."""
        message = StreamingMessage(
            message_id="msg_123",
            session_id="session_123",
            sender="user",
            content="Hello, agent!"
        )
        
        assert message.message_id == "msg_123"
        assert message.session_id == "session_123"
        assert message.sender == "user"
        assert message.content == "Hello, agent!"
        assert message.content_type == "text"
        assert message.metadata == {}
        assert isinstance(message.timestamp, datetime)
    
    def test_streaming_message_with_optional_fields(self):
        """Test creating streaming message with all optional fields."""
        metadata = {"priority": "high", "source": "web"}
        
        message = StreamingMessage(
            message_id="msg_456", 
            session_id="session_456",
            sender="agent",
            content="<p>HTML content</p>",
            content_type="html",
            metadata=metadata
        )
        
        assert message.message_id == "msg_456"
        assert message.session_id == "session_456"
        assert message.sender == "agent"
        assert message.content == "<p>HTML content</p>"
        assert message.content_type == "html"
        assert message.metadata == metadata
    
    def test_json_serialization(self):
        """Test JSON serialization of streaming message."""
        message = StreamingMessage(
            message_id="json_msg",
            session_id="json_session",
            sender="system",
            content="System message"
        )
        
        json_data = message.model_dump_json()
        parsed_data = json.loads(json_data)
        
        assert parsed_data["message_id"] == "json_msg"
        assert parsed_data["session_id"] == "json_session"
        assert parsed_data["sender"] == "system"
        assert parsed_data["content"] == "System message"
        assert "timestamp" in parsed_data
    
    def test_validation_errors(self):
        """Test validation errors for required fields."""
        with pytest.raises(ValidationError):
            StreamingMessage()
        
        with pytest.raises(ValidationError):
            StreamingMessage(message_id="test")


@pytest.mark.unit
class TestMessageRequest:
    """Test cases for MessageRequest model."""
    
    def test_message_request_minimal(self):
        """Test creating message request with minimal fields."""
        request = MessageRequest(message="Hello")
        
        assert request.message == "Hello"
        assert request.content_type == "text"
        assert request.metadata is None
    
    def test_message_request_full(self):
        """Test creating message request with all fields."""
        metadata = {"urgent": True}
        
        request = MessageRequest(
            message="Important message",
            content_type="json",
            metadata=metadata
        )
        
        assert request.message == "Important message"
        assert request.content_type == "json"
        assert request.metadata == metadata


@pytest.mark.unit
class TestMessageResponse:
    """Test cases for MessageResponse model."""
    
    def test_message_response_creation(self):
        """Test creating message response."""
        response = MessageResponse(
            status="sent",
            message_id="msg_response_123"
        )
        
        assert response.status == "sent"
        assert response.message_id == "msg_response_123"
        assert isinstance(response.timestamp, datetime)


@pytest.mark.unit
class TestStreamingEvent:
    """Test cases for StreamingEvent model."""
    
    def test_streaming_event_creation(self):
        """Test creating a streaming event with required fields."""
        event_data = {"tool_name": "search", "query": "test"}
        
        event = StreamingEvent(
            event_id="event_123",
            session_id="session_123",
            event_type="tool_execution_start",
            data=event_data
        )
        
        assert event.event_id == "event_123"
        assert event.session_id == "session_123"
        assert event.event_type == "tool_execution_start"
        assert event.data == event_data
        assert event.turn_complete is False
        assert event.metadata == {}
        assert isinstance(event.timestamp, datetime)
    
    def test_streaming_event_with_optional_fields(self):
        """Test creating streaming event with all optional fields."""
        event_data = {"result": "success"}
        metadata = {"duration_ms": 150}
        
        event = StreamingEvent(
            event_id="event_456",
            session_id="session_456", 
            event_type="tool_execution_complete",
            data=event_data,
            turn_complete=True,
            metadata=metadata
        )
        
        assert event.event_id == "event_456"
        assert event.session_id == "session_456"
        assert event.event_type == "tool_execution_complete"
        assert event.data == event_data
        assert event.turn_complete is True
        assert event.metadata == metadata
    
    def test_json_serialization(self):
        """Test JSON serialization of streaming event."""
        event = StreamingEvent(
            event_id="json_event",
            session_id="json_session",
            event_type="agent_message",
            data={"content": "Hello"}
        )
        
        json_data = event.model_dump_json()
        parsed_data = json.loads(json_data)
        
        assert parsed_data["event_id"] == "json_event"
        assert parsed_data["session_id"] == "json_session"
        assert parsed_data["event_type"] == "agent_message"
        assert parsed_data["data"] == {"content": "Hello"}
        assert "timestamp" in parsed_data


@pytest.mark.unit
class TestToolExecutionEvents:
    """Test cases for tool execution event models."""
    
    def test_tool_execution_start_event(self):
        """Test creating tool execution start event."""
        tool_args = {"query": "SELECT * FROM users", "limit": 10}
        
        event = ToolExecutionStartEvent(
            tool_name="sql_query",
            tool_args=tool_args
        )
        
        assert event.tool_name == "sql_query"
        assert event.tool_args == tool_args
        assert isinstance(event.timestamp, datetime)
    
    def test_tool_execution_complete_event(self):
        """Test creating tool execution complete event."""
        tool_result = {"rows": [{"id": 1, "name": "test"}]}
        
        event = ToolExecutionCompleteEvent(
            tool_name="sql_query",
            tool_result=tool_result,
            execution_time=1.5
        )
        
        assert event.tool_name == "sql_query"
        assert event.tool_result == tool_result
        assert event.execution_time == 1.5
        assert isinstance(event.timestamp, datetime)
    
    def test_tool_execution_complete_without_timing(self):
        """Test creating tool execution complete event without timing."""
        event = ToolExecutionCompleteEvent(
            tool_name="test_tool",
            tool_result={"status": "ok"}
        )
        
        assert event.tool_name == "test_tool"
        assert event.tool_result == {"status": "ok"}
        assert event.execution_time is None


@pytest.mark.unit
class TestAgentMessageEvent:
    """Test cases for AgentMessageEvent model."""
    
    def test_agent_message_event_creation(self):
        """Test creating agent message event."""
        event = AgentMessageEvent(
            content="Hello, how can I help you?",
            content_type="text",
            partial=False
        )
        
        assert event.content == "Hello, how can I help you?"
        assert event.content_type == "text"
        assert event.partial is False
        assert isinstance(event.timestamp, datetime)
    
    def test_agent_message_event_partial(self):
        """Test creating partial agent message event."""
        event = AgentMessageEvent(
            content="I'm thinking...",
            partial=True
        )
        
        assert event.content == "I'm thinking..."
        assert event.content_type == "text"  # default
        assert event.partial is True


@pytest.mark.unit
class TestTurnCompleteEvent:
    """Test cases for TurnCompleteEvent model."""
    
    def test_turn_complete_event_minimal(self):
        """Test creating turn complete event with minimal fields."""
        event = TurnCompleteEvent()
        
        assert event.turn_id is None
        assert event.total_tokens is None
        assert event.execution_time is None
        assert isinstance(event.timestamp, datetime)
    
    def test_turn_complete_event_full(self):
        """Test creating turn complete event with all fields."""
        event = TurnCompleteEvent(
            turn_id="turn_123",
            total_tokens=150,
            execution_time=3.2
        )
        
        assert event.turn_id == "turn_123"
        assert event.total_tokens == 150
        assert event.execution_time == 3.2


@pytest.mark.unit
class TestSystemEvent:
    """Test cases for SystemEvent model."""
    
    def test_system_event_creation(self):
        """Test creating system event."""
        event = SystemEvent(
            message="System is ready",
            severity="info"
        )
        
        assert event.message == "System is ready"
        assert event.severity == "info"
        assert isinstance(event.timestamp, datetime)
    
    def test_system_event_different_severities(self):
        """Test creating system events with different severities."""
        # Info event
        info_event = SystemEvent(message="Info message")
        assert info_event.severity == "info"  # default
        
        # Warning event
        warning_event = SystemEvent(
            message="Warning message",
            severity="warning"
        )
        assert warning_event.severity == "warning"
        
        # Error event
        error_event = SystemEvent(
            message="Error occurred",
            severity="error"
        )
        assert error_event.severity == "error"
    
    def test_invalid_severity(self):
        """Test validation error for invalid severity."""
        with pytest.raises(ValidationError):
            SystemEvent(
                message="Test",
                severity="invalid"
            )


@pytest.mark.unit
class TestEventTypes:
    """Test cases for EventTypes constants."""
    
    def test_event_type_constants(self):
        """Test that all event type constants are defined correctly."""
        assert EventTypes.TOOL_EXECUTION_START == "tool_execution_start"
        assert EventTypes.TOOL_EXECUTION_COMPLETE == "tool_execution_complete"
        assert EventTypes.AGENT_MESSAGE == "agent_message"
        assert EventTypes.TURN_COMPLETE == "turn_complete"
        assert EventTypes.SYSTEM_MESSAGE == "system_message"
        assert EventTypes.CONNECTION_OPENED == "connection_opened"
        assert EventTypes.CONNECTION_CLOSED == "connection_closed"
        assert EventTypes.ERROR == "error"
    
    def test_event_types_uniqueness(self):
        """Test that all event type constants are unique."""
        event_types = [
            EventTypes.TOOL_EXECUTION_START,
            EventTypes.TOOL_EXECUTION_COMPLETE,
            EventTypes.AGENT_MESSAGE,
            EventTypes.TURN_COMPLETE,
            EventTypes.SYSTEM_MESSAGE,
            EventTypes.CONNECTION_OPENED,
            EventTypes.CONNECTION_CLOSED,
            EventTypes.ERROR
        ]
        
        # All values should be unique
        assert len(event_types) == len(set(event_types))
