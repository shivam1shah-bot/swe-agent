"""
Unit tests for MCP server components.

Tests the core server components including session management, stream management,
error handling, and request processing.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import time
import json
import asyncio
from typing import Dict, Any

from src.mcp_server.server.session_manager import MCPSessionManager, MCPSession
from src.mcp_server.server.stream_manager import MCPStreamManager, MCPStream, SSEEvent
from src.mcp_server.server.error_handler import MCPErrorHandler, MCPErrorCodes
from src.mcp_server.server.request_handler import MCPRequestHandler
from src.mcp_server.config.settings import MCPSettings, get_mcp_settings


@pytest.mark.unit
class TestMCPSettings:
    """Test cases for MCPSettings."""
    
    @patch('src.mcp_server.config.settings.get_config')
    def test_mcp_settings_authentication_properties(self, mock_get_config):
        """Test MCPSettings authentication properties."""
        # Mock configuration with auth enabled
        mock_config = {
            "auth": {
                "enabled": True,
                "users": {
                    "dashboard": "dashboard123",
                    "admin": "admin123",
                    "mcp_read_user": "mcp_secure_dev_2024"
                }
            },
            "app": {
                "host": "localhost",
                "mcp_port": 8003,
                "api_base_url": "http://localhost:8002",
                "debug": False
            },
            "environment": {
                "name": "dev"
            },
            "logging": {
                "level": "INFO"
            }
        }
        mock_get_config.return_value = mock_config
        
        settings = MCPSettings()
        
        # Test authentication properties
        assert settings.auth_enabled is True
        assert settings.auth_username == "mcp_read_user"
        assert settings.auth_password == "mcp_secure_dev_2024"
    
    @patch('src.mcp_server.config.settings.get_config')
    def test_mcp_settings_authentication_disabled(self, mock_get_config):
        """Test MCPSettings when authentication is disabled."""
        mock_config = {
            "auth": {
                "enabled": False,
                "users": {}
            },
            "app": {},
            "environment": {"name": "dev"},
            "logging": {}
        }
        mock_get_config.return_value = mock_config
        
        settings = MCPSettings()
        
        # Test authentication properties
        assert settings.auth_enabled is False
        assert settings.auth_username == "mcp_read_user"  # Username is always fixed
        assert settings.auth_password == ""  # Password should be empty
    
    @patch('src.mcp_server.config.settings.get_config')
    def test_mcp_settings_no_mcp_read_user(self, mock_get_config):
        """Test MCPSettings when mcp_read_user is not configured."""
        mock_config = {
            "auth": {
                "enabled": True,
                "users": {
                    "dashboard": "dashboard123",
                    "admin": "admin123"
                    # mcp_read_user is missing
                }
            },
            "app": {},
            "environment": {"name": "dev"},
            "logging": {}
        }
        mock_get_config.return_value = mock_config
        
        settings = MCPSettings()
        
        # Test authentication properties
        assert settings.auth_enabled is True
        assert settings.auth_username == "mcp_read_user"
        assert settings.auth_password == ""  # Should be empty when user not configured


class TestMCPSessionManager:
    """Test cases for MCPSessionManager."""
    
    @pytest.fixture
    def session_manager(self):
        """Create MCPSessionManager instance."""
        return MCPSessionManager(session_timeout=3600)
    
    def test_create_session(self, session_manager):
        """Test session creation."""
        client_info = {"origin": "http://localhost", "user_agent": "TestAgent"}
        session_id = session_manager.create_session(client_info)
        
        assert session_id is not None
        assert len(session_id) == 36  # UUID length
        assert session_manager.validate_session(session_id)
        
        # Check session data
        session = session_manager.get_session(session_id)
        assert session is not None
        assert session.client_info == client_info
    
    def test_create_session_without_client_info(self, session_manager):
        """Test session creation without client info."""
        session_id = session_manager.create_session()
        
        assert session_id is not None
        assert session_manager.validate_session(session_id)
    
    def test_validate_session_invalid(self, session_manager):
        """Test validation of invalid session."""
        assert not session_manager.validate_session("invalid-session-id")
        assert not session_manager.validate_session(None)
    
    def test_terminate_session(self, session_manager):
        """Test session termination."""
        session_id = session_manager.create_session()
        assert session_manager.validate_session(session_id)
        
        success = session_manager.terminate_session(session_id)
        assert success
        assert not session_manager.validate_session(session_id)
    
    def test_terminate_nonexistent_session(self, session_manager):
        """Test termination of non-existent session."""
        success = session_manager.terminate_session("nonexistent-session")
        assert not success
    
    def test_session_expiry(self):
        """Test session expiry functionality."""
        # Create manager with very short timeout
        session_manager = MCPSessionManager(session_timeout=1)
        session_id = session_manager.create_session()
        
        # Session should be valid initially
        assert session_manager.validate_session(session_id)
        
        # Wait for expiry and force cleanup
        time.sleep(1.1)
        session_manager.cleanup_expired_sessions()
        
        # Session should be expired now
        assert not session_manager.validate_session(session_id)
    
    def test_update_activity(self, session_manager):
        """Test session activity update."""
        session_id = session_manager.create_session()
        
        # Get initial last activity
        session = session_manager.get_session(session_id)
        initial_activity = session.last_activity
        
        # Update activity
        time.sleep(0.1)  # Ensure time difference
        session_manager.update_activity(session_id)
        
        # Check activity was updated
        updated_session = session_manager.get_session(session_id)
        assert updated_session.last_activity > initial_activity
    
    def test_get_session_stats(self, session_manager):
        """Test session statistics."""
        # Create multiple sessions
        session_ids = [session_manager.create_session() for _ in range(3)]
        
        stats = session_manager.get_session_stats()
        assert stats["active_sessions"] == 3
        assert stats["total_created"] == 3
        
        # Terminate one session
        session_manager.terminate_session(session_ids[0])
        
        updated_stats = session_manager.get_session_stats()
        assert updated_stats["active_sessions"] == 2


class TestMCPStreamManager:
    """Test cases for MCPStreamManager."""
    
    @pytest.fixture
    def stream_manager(self):
        """Create MCPStreamManager instance."""
        return MCPStreamManager(stream_timeout=3600, max_events_per_stream=100)
    
    def test_create_stream(self, stream_manager):
        """Test stream creation."""
        session_id = "test-session"
        stream_id = stream_manager.create_stream(session_id)
        
        assert stream_id is not None
        assert len(stream_id) == 36  # UUID length
        
        # Check stream exists
        stream = stream_manager.streams.get(stream_id)
        assert stream is not None
        assert stream.session_id == session_id
    
    def test_add_event(self, stream_manager):
        """Test adding events to stream."""
        stream_id = stream_manager.create_stream("test-session")
        
        # Add event
        event_data = {"type": "test", "message": "Hello"}
        stream_manager.add_event(stream_id, "test_event", event_data, "event-1")
        
        # Check event was added
        stream = stream_manager.streams[stream_id]
        assert len(stream.events) == 1
        assert stream.events[0].event_type == "test_event"
        assert stream.events[0].data == event_data
    
    def test_add_event_to_nonexistent_stream(self, stream_manager):
        """Test adding event to non-existent stream."""
        # Should not raise exception
        stream_manager.add_event("nonexistent", "test", {}, "event-1")
    
    def test_get_events_after(self, stream_manager):
        """Test retrieving events after specific event ID."""
        stream_id = stream_manager.create_stream("test-session")
        
        # Add multiple events
        stream_manager.add_event(stream_id, "event", {"msg": "1"}, "event-1")
        stream_manager.add_event(stream_id, "event", {"msg": "2"}, "event-2") 
        stream_manager.add_event(stream_id, "event", {"msg": "3"}, "event-3")
        
        # Get events after event-1
        events = stream_manager.get_events_after(stream_id, "event-1")
        assert len(events) == 2
        assert events[0].id == "event-2"
        assert events[1].id == "event-3"
    
    def test_get_events_after_invalid_id(self, stream_manager):
        """Test retrieving events with invalid last event ID."""
        stream_id = stream_manager.create_stream("test-session")
        stream_manager.add_event(stream_id, "event", {"msg": "1"}, "event-1")
        
        # Invalid last event ID returns empty list (no events found after the invalid ID)
        events = stream_manager.get_events_after(stream_id, "invalid-id")
        assert len(events) == 0
        
        # With no last_event_id, should return all events
        events = stream_manager.get_events_after(stream_id, None)
        assert len(events) == 1
    
    def test_stream_events_format(self, stream_manager):
        """Test streaming events formatting (non-hanging version)."""
        stream_id = stream_manager.create_stream("test-session")
        
        # Add events
        event1 = stream_manager.add_event(stream_id, "event", {"msg": "1"}, "event-1")
        event2 = stream_manager.add_event(stream_id, "event", {"msg": "2"}, "event-2")
        
        # Test event formatting directly
        formatted1 = stream_manager._format_sse_event(event1)
        formatted2 = stream_manager._format_sse_event(event2)
        
        assert "data:" in formatted1
        assert "id:" in formatted1
        assert "event-1" in formatted1
        assert "data:" in formatted2
        assert "id:" in formatted2
        assert "event-2" in formatted2
        
        # Test getting existing events
        existing_events = stream_manager.get_events_after(stream_id, None)
        assert len(existing_events) == 2
        assert existing_events[0].id == "event-1"
        assert existing_events[1].id == "event-2"
    
    def test_close_stream(self, stream_manager):
        """Test stream closure."""
        stream_id = stream_manager.create_stream("test-session")
        assert stream_id in stream_manager.streams
        
        stream_manager.close_stream(stream_id)
        # Stream should still exist but be marked as inactive
        assert stream_id in stream_manager.streams
        stream = stream_manager.streams[stream_id]
        assert stream.is_active is False
    
    def test_max_events_limit(self, stream_manager):
        """Test maximum events per stream limit."""
        stream_id = stream_manager.create_stream("test-session")
        
        # Add events beyond limit
        for i in range(150):  # Limit is 100
            stream_manager.add_event(stream_id, "event", {"msg": str(i)}, f"event-{i}")
        
        # Should only keep max events
        stream = stream_manager.streams[stream_id]
        assert len(stream.events) == 100
        
        # Should keep most recent events
        assert stream.events[-1].id == "event-149"


class TestMCPErrorHandler:
    """Test cases for MCPErrorHandler."""
    
    @pytest.fixture
    def error_handler(self):
        """Create MCPErrorHandler instance."""
        return MCPErrorHandler()
    
    def test_format_mcp_error_generic_exception(self, error_handler):
        """Test formatting generic exception."""
        error = Exception("Generic error")
        request_id = "test-request-1"
        
        result = error_handler.format_mcp_error(error, request_id)
        
        assert result["jsonrpc"] == "2.0"
        assert result["id"] == request_id
        assert "error" in result
        assert result["error"]["code"] == MCPErrorCodes.INTERNAL_ERROR
        # Generic exceptions get sanitized message for security
        assert result["error"]["message"] == "An unexpected error occurred"
        # But the actual error is in the data field
        assert result["error"]["data"]["detail"] == "Generic error"
    
    def test_format_mcp_error_validation_error(self, error_handler):
        """Test formatting validation error."""
        error = ValueError("Invalid input")
        request_id = "test-request-2"
        
        result = error_handler.format_mcp_error(error, request_id)
        
        assert result["jsonrpc"] == "2.0"
        assert result["id"] == request_id
        assert "error" in result
        # ValueError is handled as INVALID_PARAMS, not VALIDATION_ERROR
        assert result["error"]["code"] == MCPErrorCodes.INVALID_PARAMS
        assert "Invalid parameter value provided" in result["error"]["message"]
    
    def test_format_mcp_error_with_traceback(self, error_handler):
        """Test formatting error with traceback."""
        error = RuntimeError("Runtime error")
        
        result = error_handler.format_mcp_error(error, include_traceback=True)
        
        assert "data" in result["error"]
        assert "traceback" in result["error"]["data"]
    
    def test_tool_not_found_error(self, error_handler):
        """Test tool not found error creation."""
        result = error_handler.tool_not_found_error("nonexistent_tool", "req-1")
        
        assert result["error"]["code"] == MCPErrorCodes.METHOD_NOT_FOUND
        assert "nonexistent_tool" in result["error"]["message"]
        assert result["id"] == "req-1"
    
    def test_invalid_session_error(self, error_handler):
        """Test invalid session error creation."""
        result = error_handler.invalid_session_error("invalid-session", "req-2")
        
        assert result["error"]["code"] == MCPErrorCodes.INVALID_SESSION
        assert "invalid-session" in result["error"]["message"]
        assert result["id"] == "req-2"
    
    def test_rate_limit_error(self, error_handler):
        """Test rate limit error creation."""
        result = error_handler.rate_limit_error("client-123", "req-3")
        
        assert result["error"]["code"] == MCPErrorCodes.RATE_LIMITED
        assert "client-123" in result["error"]["message"]
        assert result["id"] == "req-3"


class TestMCPRequestHandler:
    """Test cases for MCPRequestHandler."""
    
    @pytest.fixture
    def mock_tool_registry(self):
        """Create mock tool registry."""
        from unittest.mock import AsyncMock
        registry = Mock()
        registry.get_tool.return_value = None
        registry.list_tools = AsyncMock(return_value=[])
        registry.execute_tool = AsyncMock(return_value={"success": True, "data": "test"})
        return registry
    
    @pytest.fixture
    def mock_rbac_validator(self):
        """Create mock RBAC validator."""
        return Mock()
    
    @pytest.fixture
    def mock_request(self):
        """Create mock FastAPI request."""
        request = Mock()
        request.state = Mock()
        request.state.current_user = Mock()
        request.state.current_user.roles = ["mcp_read_user"]
        return request
    
    @pytest.fixture
    def request_handler(self, mock_tool_registry, mock_rbac_validator):
        """Create MCPRequestHandler instance."""
        return MCPRequestHandler(mock_tool_registry, mock_rbac_validator)

    @pytest.mark.asyncio
    async def test_handle_initialize_request(self, request_handler, mock_request):
        """Test handling initialize request."""
        request_data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocol_version": {"version": "2025-03-26"},
                "client_info": {"name": "test-client", "version": "1.0.0"},
                "capabilities": {}
            }
        }
        
        response = await request_handler.handle_request(request_data, mock_request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        assert response["result"]["serverInfo"]["name"] == "swe-agent-mcp-server"
        assert response["result"]["protocolVersion"] in request_handler.supported_versions
        assert "capabilities" in response["result"]

    @pytest.mark.asyncio
    async def test_handle_tools_list_request(self, request_handler, mock_tool_registry, mock_request):
        """Test handling tools/list request."""
        mock_tools = [
            {"name": "test_tool", "description": "Test tool", "inputSchema": {}}
        ]
        mock_tool_registry.list_tools.return_value = mock_tools
        
        request_data = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        response = await request_handler.handle_request(request_data, mock_request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 2
        assert "result" in response
        assert response["result"]["tools"] == mock_tools
    
    @pytest.mark.asyncio
    async def test_handle_tools_call_request(self, request_handler, mock_tool_registry, mock_request):
        """Test handling tools/call request."""
        mock_tool_registry.execute_tool.return_value = {"success": True, "data": "executed"}
        
        request_data = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "test_tool",
                "arguments": {"param": "value"}
            }
        }
        
        response = await request_handler.handle_request(request_data, mock_request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 3
        assert "result" in response
        
        # Verify tool was called
        mock_tool_registry.execute_tool.assert_called_once_with(
            "test_tool", {"param": "value"}
        )

    @pytest.mark.asyncio
    async def test_handle_ping_request(self, request_handler, mock_request):
        """Test handling ping request."""
        request_data = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "ping",
            "params": {}
        }
        
        response = await request_handler.handle_request(request_data, mock_request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 4
        assert "result" in response
    
    @pytest.mark.asyncio
    async def test_handle_invalid_method(self, request_handler, mock_request):
        """Test handling request with invalid method."""
        request_data = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "invalid/method",
            "params": {}
        }
        
        response = await request_handler.handle_request(request_data, mock_request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 5
        assert "error" in response
        assert response["error"]["code"] == MCPErrorCodes.METHOD_NOT_FOUND
    
    @pytest.mark.asyncio
    async def test_handle_batch_request(self, request_handler, mock_tool_registry, mock_request):
        """Test handling batch request - process multiple requests individually."""
        mock_tool_registry.list_tools.return_value = []
        
        # Process individual requests from batch
        request1 = {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}}
        request2 = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        
        response1 = await request_handler.handle_request(request1, mock_request)
        response2 = await request_handler.handle_request(request2, mock_request)
        
        assert response1["jsonrpc"] == "2.0"
        assert response1["id"] == 1
        assert response2["jsonrpc"] == "2.0"  
        assert response2["id"] == 2

    @pytest.mark.asyncio
    async def test_handle_malformed_request(self, request_handler, mock_request):
        """Test handling malformed request."""
        request_data = {
            "invalid": "request"
        }
        
        response = await request_handler.handle_request(request_data, mock_request)
        
        assert "error" in response
        assert response["error"]["code"] == MCPErrorCodes.METHOD_NOT_FOUND


# Integration tests for server components
class TestServerComponentsIntegration:
    """Integration tests for MCP server components."""
    
    @pytest.mark.asyncio
    async def test_session_and_stream_integration(self):
        """Test session and stream managers working together."""
        session_manager = MCPSessionManager()
        stream_manager = MCPStreamManager()
        
        # Create session
        session_id = session_manager.create_session()
        assert session_manager.validate_session(session_id)
        
        # Create stream for session
        stream_id = stream_manager.create_stream(session_id)
        
        # Add events to stream
        stream_manager.add_event(stream_id, "session_event", {"session": session_id}, "evt-1")
        
        # Verify stream has events
        events = stream_manager.get_events_after(stream_id, None)
        assert len(events) == 1
        assert events[0].data["session"] == session_id
        
        # Cleanup
        session_manager.terminate_session(session_id)
        stream_manager.close_stream(stream_id)
    
    def test_error_handler_with_request_handler(self):
        """Test error handler integration with request handler."""
        from src.mcp_server.tools.registry import MCPToolRegistry
        from unittest.mock import Mock
        
        # Create mock API client
        mock_api_client = Mock()
        
        # Create mock RBAC validator
        mock_rbac_validator = Mock()
        
        tool_registry = MCPToolRegistry(mock_api_client)
        request_handler = MCPRequestHandler(tool_registry, mock_rbac_validator)
        
        # Test that request handler was created successfully
        assert request_handler is not None
        
        # Verify required attributes exist
        assert hasattr(request_handler, 'logger')
        assert hasattr(request_handler, 'tool_registry')
        assert hasattr(request_handler, 'rbac_validator')
        assert hasattr(request_handler, 'supported_versions')
        
        # Verify the tool registry and RBAC validator are properly assigned
        assert request_handler.tool_registry is tool_registry
        assert request_handler.rbac_validator is mock_rbac_validator 