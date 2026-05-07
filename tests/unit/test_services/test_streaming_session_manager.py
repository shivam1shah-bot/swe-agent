"""
Unit tests for SessionManager.

Tests for streaming session management functionality.
"""

import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.services.streaming.session_manager import SessionManager
from src.models.streaming.session import StreamingSession


@pytest.fixture
def mock_streaming_registry():
    """Mock StreamingRegistry for testing."""
    with patch('src.services.streaming.session_manager.StreamingRegistry') as mock_registry:
        # Mock successful agent lookup
        mock_registry.get_agent_by_id.return_value = {
            "id": "test_agent",
            "name": "Test Agent",
            "type": "test_type",
            "framework": "test_framework"
        }
        yield mock_registry


@pytest.fixture
def session_manager():
    """Create a SessionManager instance for testing."""
    return SessionManager(session_timeout=3600)


@pytest.fixture
def sample_agent_config():
    """Sample agent configuration for testing."""
    return {
        "id": "trino_agent",
        "name": "Trino Data Assistant",
        "type": "knowledge_agent",
        "framework": "google_adk",
        "capabilities": ["data_query", "sql_execution"],
        "config": {"timeout": 30}
    }


@pytest.mark.unit
class TestSessionManagerInitialization:
    """Test cases for SessionManager initialization."""
    
    def test_session_manager_creation_default_timeout(self):
        """Test creating SessionManager with default timeout."""
        manager = SessionManager()
        
        assert manager.session_timeout == 3600
        assert manager.sessions == {}
    
    def test_session_manager_creation_custom_timeout(self):
        """Test creating SessionManager with custom timeout."""
        manager = SessionManager(session_timeout=1800)
        
        assert manager.session_timeout == 1800
        assert manager.sessions == {}


@pytest.mark.unit
class TestSessionCreation:
    """Test cases for session creation."""
    
    def test_create_session_success(self, session_manager, mock_streaming_registry, sample_agent_config):
        """Test successful session creation."""
        mock_streaming_registry.get_agent_by_id.return_value = sample_agent_config
        
        with patch('src.services.streaming.session_manager.uuid.uuid4') as mock_uuid:
            mock_uuid.return_value.hex = "test123"
            
            session_id = session_manager.create_session("trino_agent", "sse")
            
            assert session_id == "session_test123"
            assert session_id in session_manager.sessions
            
            session = session_manager.sessions[session_id]
            assert session.session_id == session_id
            assert session.agent_id == "trino_agent"
            assert session.agent_name == "Trino Data Assistant"
            assert session.transport_type == "sse"
            assert session.status == "active"
            assert session.user_context == {}
            assert session.agent_context == {"config": sample_agent_config}
    
    def test_create_session_with_user_context(self, session_manager, mock_streaming_registry, sample_agent_config):
        """Test session creation with user context."""
        mock_streaming_registry.get_agent_by_id.return_value = sample_agent_config
        user_context = {"user_id": "test_user", "role": "admin"}
        
        with patch('src.services.streaming.session_manager.uuid.uuid4') as mock_uuid:
            mock_uuid.return_value.hex = "context123"
            
            session_id = session_manager.create_session(
                "trino_agent", 
                "sse", 
                user_context=user_context
            )
            
            session = session_manager.sessions[session_id]
            assert session.user_context == user_context
    
    def test_create_session_different_transport(self, session_manager, mock_streaming_registry, sample_agent_config):
        """Test session creation with different transport type."""
        mock_streaming_registry.get_agent_by_id.return_value = sample_agent_config
        
        session_id = session_manager.create_session("trino_agent", "websocket")
        
        session = session_manager.sessions[session_id]
        assert session.transport_type == "websocket"
    
    def test_create_session_invalid_agent(self, session_manager, mock_streaming_registry):
        """Test session creation with invalid agent ID."""
        mock_streaming_registry.get_agent_by_id.return_value = None
        
        with pytest.raises(ValueError, match="Unknown agent ID: invalid_agent"):
            session_manager.create_session("invalid_agent")
    
    def test_create_session_logging(self, session_manager, mock_streaming_registry, sample_agent_config):
        """Test that session creation logs appropriately."""
        mock_streaming_registry.get_agent_by_id.return_value = sample_agent_config
        
        with patch('src.services.streaming.session_manager.logger') as mock_logger:
            session_id = session_manager.create_session("trino_agent")
            
            # Check that info log was called
            mock_logger.info.assert_called()
            log_calls = mock_logger.info.call_args_list
            assert len(log_calls) >= 1
            # Should log creation message
            assert any("Created session" in str(call) for call in log_calls)


@pytest.mark.unit
class TestSessionRetrieval:
    """Test cases for session retrieval."""
    
    def test_get_session_exists(self, session_manager, mock_streaming_registry, sample_agent_config):
        """Test getting an existing session."""
        mock_streaming_registry.get_agent_by_id.return_value = sample_agent_config
        
        session_id = session_manager.create_session("trino_agent")
        session = session_manager.get_session(session_id)
        
        assert session is not None
        assert session.session_id == session_id
        assert session.agent_id == "trino_agent"
    
    def test_get_session_not_exists(self, session_manager):
        """Test getting a non-existent session."""
        session = session_manager.get_session("non_existent_session")
        assert session is None
    
    def test_get_session_expired(self, session_manager, mock_streaming_registry, sample_agent_config):
        """Test getting an expired session."""
        mock_streaming_registry.get_agent_by_id.return_value = sample_agent_config
        session_manager.session_timeout = 1  # Very short timeout
        
        session_id = session_manager.create_session("trino_agent")
        
        # Mock time passing beyond timeout
        with patch('src.services.streaming.session_manager.datetime') as mock_datetime:
            # Set current time to be beyond timeout
            expired_time = datetime.utcnow() + timedelta(seconds=2)
            mock_datetime.utcnow.return_value = expired_time
            
            session = session_manager.get_session(session_id)
            
            # Should return None and remove expired session
            assert session is None
            assert session_id not in session_manager.sessions


@pytest.mark.unit
class TestSessionActivity:
    """Test cases for session activity management."""
    
    def test_update_session_activity_success(self, session_manager, mock_streaming_registry, sample_agent_config):
        """Test successful session activity update."""
        mock_streaming_registry.get_agent_by_id.return_value = sample_agent_config
        
        session_id = session_manager.create_session("trino_agent")
        original_activity = session_manager.sessions[session_id].last_activity
        
        with patch('src.models.streaming.session.datetime') as mock_datetime:
            new_time = original_activity + timedelta(minutes=1)
            mock_datetime.utcnow.return_value = new_time
            
            result = session_manager.update_session_activity(session_id)
            
            assert result is True
            assert session_manager.sessions[session_id].last_activity == new_time
    
    def test_update_session_activity_not_found(self, session_manager):
        """Test updating activity for non-existent session."""
        result = session_manager.update_session_activity("non_existent")
        assert result is False
    
    def test_is_session_active(self, session_manager, mock_streaming_registry, sample_agent_config):
        """Test checking if session is active."""
        mock_streaming_registry.get_agent_by_id.return_value = sample_agent_config
        
        session_id = session_manager.create_session("trino_agent")
        
        # Should be active
        assert session_manager.is_session_active(session_id) is True
        
        # Should be False for non-existent session
        assert session_manager.is_session_active("non_existent") is False


@pytest.mark.unit
class TestSessionClosure:
    """Test cases for session closure."""
    
    def test_close_session_success(self, session_manager, mock_streaming_registry, sample_agent_config):
        """Test successful session closure."""
        mock_streaming_registry.get_agent_by_id.return_value = sample_agent_config
        
        session_id = session_manager.create_session("trino_agent")
        assert session_id in session_manager.sessions
        
        result = session_manager.close_session(session_id)
        
        assert result is True
        assert session_id not in session_manager.sessions
    
    def test_close_session_not_found(self, session_manager):
        """Test closing non-existent session."""
        result = session_manager.close_session("non_existent")
        assert result is False
    
    def test_close_session_logging(self, session_manager, mock_streaming_registry, sample_agent_config):
        """Test that session closure logs appropriately."""
        mock_streaming_registry.get_agent_by_id.return_value = sample_agent_config
        
        session_id = session_manager.create_session("trino_agent")
        
        with patch('src.services.streaming.session_manager.logger') as mock_logger:
            session_manager.close_session(session_id)
            
            # Should log closure
            mock_logger.info.assert_called()
            log_calls = mock_logger.info.call_args_list
            assert any("Closed session" in str(call) for call in log_calls)
    
    def test_close_session_warning_for_non_existent(self, session_manager):
        """Test warning log for closing non-existent session."""
        with patch('src.services.streaming.session_manager.logger') as mock_logger:
            session_manager.close_session("non_existent")
            
            # Should log warning
            mock_logger.warning.assert_called_once()
            warning_call = mock_logger.warning.call_args_list[0]
            assert "non-existent session" in str(warning_call)


@pytest.mark.unit
class TestSessionContext:
    """Test cases for session context retrieval."""
    
    def test_get_session_context_success(self, session_manager, mock_streaming_registry, sample_agent_config):
        """Test getting session context for existing session."""
        mock_streaming_registry.get_agent_by_id.return_value = sample_agent_config
        user_context = {"user_id": "test_user"}
        
        session_id = session_manager.create_session(
            "trino_agent",
            "sse", 
            user_context=user_context
        )
        
        context = session_manager.get_session_context(session_id)
        
        assert context["session_id"] == session_id
        assert context["agent_id"] == "trino_agent"
        assert context["agent_name"] == "Trino Data Assistant"
        assert context["transport_type"] == "sse"
        assert context["user_context"] == user_context
        assert context["agent_context"] == {"config": sample_agent_config}
        assert "created_at" in context
        assert "last_activity" in context
    
    def test_get_session_context_not_found(self, session_manager):
        """Test getting context for non-existent session."""
        context = session_manager.get_session_context("non_existent")
        assert context == {}


@pytest.mark.unit
class TestActiveSessionsManagement:
    """Test cases for active sessions management."""
    
    def test_get_active_sessions_empty(self, session_manager):
        """Test getting active sessions when none exist."""
        active_sessions = session_manager.get_active_sessions()
        assert active_sessions == []
    
    def test_get_active_sessions_with_sessions(self, session_manager, mock_streaming_registry, sample_agent_config):
        """Test getting active sessions with existing sessions."""
        mock_streaming_registry.get_agent_by_id.return_value = sample_agent_config
        
        session_id1 = session_manager.create_session("trino_agent")
        session_id2 = session_manager.create_session("trino_agent")
        
        active_sessions = session_manager.get_active_sessions()
        
        assert len(active_sessions) == 2
        session_ids = [s.session_id for s in active_sessions]
        assert session_id1 in session_ids
        assert session_id2 in session_ids
    
    def test_get_active_sessions_filters_expired(self, session_manager, mock_streaming_registry, sample_agent_config):
        """Test that get_active_sessions filters out expired sessions."""
        mock_streaming_registry.get_agent_by_id.return_value = sample_agent_config
        session_manager.session_timeout = 1  # Very short timeout
        
        session_id = session_manager.create_session("trino_agent")
        
        # Mock time passing beyond timeout
        with patch('src.services.streaming.session_manager.datetime') as mock_datetime:
            expired_time = datetime.utcnow() + timedelta(seconds=2)
            mock_datetime.utcnow.return_value = expired_time
            
            active_sessions = session_manager.get_active_sessions()
            
            # Should be empty and session should be removed
            assert active_sessions == []
            assert session_id not in session_manager.sessions
    
    def test_get_session_count(self, session_manager, mock_streaming_registry, sample_agent_config):
        """Test getting session count."""
        mock_streaming_registry.get_agent_by_id.return_value = sample_agent_config
        
        assert session_manager.get_session_count() == 0
        
        session_manager.create_session("trino_agent")
        session_manager.create_session("trino_agent")
        
        assert session_manager.get_session_count() == 2
    
    def test_get_sessions_by_agent(self, session_manager, mock_streaming_registry):
        """Test getting sessions filtered by agent."""
        agent1_config = {"id": "agent1", "name": "Agent 1"}
        agent2_config = {"id": "agent2", "name": "Agent 2"}
        
        mock_streaming_registry.get_agent_by_id.side_effect = lambda agent_id: (
            agent1_config if agent_id == "agent1" else agent2_config
        )
        
        session_id1 = session_manager.create_session("agent1")
        session_id2 = session_manager.create_session("agent1")
        session_id3 = session_manager.create_session("agent2")
        
        agent1_sessions = session_manager.get_sessions_by_agent("agent1")
        agent2_sessions = session_manager.get_sessions_by_agent("agent2")
        
        assert len(agent1_sessions) == 2
        assert len(agent2_sessions) == 1
        
        agent1_session_ids = [s.session_id for s in agent1_sessions]
        assert session_id1 in agent1_session_ids
        assert session_id2 in agent1_session_ids
        
        assert agent2_sessions[0].session_id == session_id3


@pytest.mark.unit
class TestSessionCleanup:
    """Test cases for session cleanup functionality."""
    
    def test_cleanup_expired_sessions_none_expired(self, session_manager, mock_streaming_registry, sample_agent_config):
        """Test cleanup when no sessions are expired."""
        mock_streaming_registry.get_agent_by_id.return_value = sample_agent_config
        
        session_manager.create_session("trino_agent")
        session_manager.create_session("trino_agent")
        
        cleaned_count = session_manager.cleanup_expired_sessions()
        
        assert cleaned_count == 0
        assert len(session_manager.sessions) == 2
    
    def test_cleanup_expired_sessions_some_expired(self, session_manager, mock_streaming_registry, sample_agent_config):
        """Test cleanup when some sessions are expired."""
        mock_streaming_registry.get_agent_by_id.return_value = sample_agent_config
        session_manager.session_timeout = 1  # Very short timeout
        
        session_id1 = session_manager.create_session("trino_agent")
        session_id2 = session_manager.create_session("trino_agent")
        
        # Expire one session by manipulating its last_activity
        session1 = session_manager.sessions[session_id1]
        session1.last_activity = datetime.utcnow() - timedelta(seconds=2)
        
        cleaned_count = session_manager.cleanup_expired_sessions()
        
        assert cleaned_count == 1
        assert len(session_manager.sessions) == 1
        assert session_id1 not in session_manager.sessions
        assert session_id2 in session_manager.sessions
    
    def test_cleanup_expired_sessions_logging(self, session_manager, mock_streaming_registry, sample_agent_config):
        """Test that cleanup logs appropriately."""
        mock_streaming_registry.get_agent_by_id.return_value = sample_agent_config
        session_manager.session_timeout = 1
        
        session_id = session_manager.create_session("trino_agent")
        session = session_manager.sessions[session_id]
        session.last_activity = datetime.utcnow() - timedelta(seconds=2)
        
        with patch('src.services.streaming.session_manager.logger') as mock_logger:
            cleaned_count = session_manager.cleanup_expired_sessions()
            
            assert cleaned_count == 1
            # Should log cleanup info
            mock_logger.info.assert_called()
            log_calls = mock_logger.info.call_args_list
            assert any("Cleaned up" in str(call) for call in log_calls)


@pytest.mark.unit
class TestSessionStatistics:
    """Test cases for session statistics."""
    
    def test_get_session_stats_empty(self, session_manager):
        """Test getting statistics with no sessions."""
        stats = session_manager.get_session_stats()
        
        assert stats["total_active_sessions"] == 0
        assert stats["sessions_by_agent"] == {}
        assert stats["sessions_by_transport"] == {}
        assert stats["session_timeout"] == 3600
    
    def test_get_session_stats_with_sessions(self, session_manager, mock_streaming_registry):
        """Test getting statistics with multiple sessions."""
        agent1_config = {"id": "agent1", "name": "Agent 1"}
        agent2_config = {"id": "agent2", "name": "Agent 2"}
        
        mock_streaming_registry.get_agent_by_id.side_effect = lambda agent_id: (
            agent1_config if agent_id == "agent1" else agent2_config
        )
        
        # Create sessions with different agents and transports
        session_manager.create_session("agent1", "sse")
        session_manager.create_session("agent1", "sse")
        session_manager.create_session("agent2", "websocket")
        
        stats = session_manager.get_session_stats()
        
        assert stats["total_active_sessions"] == 3
        assert stats["sessions_by_agent"] == {"agent1": 2, "agent2": 1}
        assert stats["sessions_by_transport"] == {"sse": 2, "websocket": 1}
        assert stats["session_timeout"] == 3600


@pytest.mark.unit
class TestPrivateMethods:
    """Test cases for private methods."""
    
    def test_is_session_expired_active_session(self, session_manager):
        """Test expiry check for active session."""
        session = StreamingSession(
            session_id="test_session",
            agent_id="test_agent",
            agent_name="Test Agent"
        )
        
        # Session should not be expired
        result = session_manager._is_session_expired(session)
        assert result is False
    
    def test_is_session_expired_closed_session(self, session_manager):
        """Test expiry check for closed session."""
        session = StreamingSession(
            session_id="test_session",
            agent_id="test_agent",
            agent_name="Test Agent",
            status="closed"
        )
        
        # Closed session should be considered expired
        result = session_manager._is_session_expired(session)
        assert result is True
    
    def test_is_session_expired_timeout_exceeded(self, session_manager):
        """Test expiry check for session that exceeded timeout."""
        session_manager.session_timeout = 1  # 1 second timeout
        
        session = StreamingSession(
            session_id="test_session",
            agent_id="test_agent",
            agent_name="Test Agent"
        )
        
        # Set last_activity to be beyond timeout
        session.last_activity = datetime.utcnow() - timedelta(seconds=2)
        
        result = session_manager._is_session_expired(session)
        assert result is True
    
    def test_is_session_expired_within_timeout(self, session_manager):
        """Test expiry check for session within timeout."""
        session_manager.session_timeout = 3600  # 1 hour timeout
        
        session = StreamingSession(
            session_id="test_session",
            agent_id="test_agent", 
            agent_name="Test Agent"
        )
        
        # Set last_activity to be recent
        session.last_activity = datetime.utcnow() - timedelta(seconds=10)
        
        result = session_manager._is_session_expired(session)
        assert result is False
