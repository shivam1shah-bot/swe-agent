"""
Pytest configuration for MCP unit tests.

Provides fixtures and test setup for MCP unit test modules.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, Generator

from src.mcp_server.tools.registry import MCPToolRegistry
from src.mcp_server.server.session_manager import MCPSessionManager
from src.mcp_server.server.stream_manager import MCPStreamManager
from src.mcp_server.server.error_handler import MCPErrorHandler
from src.mcp_server.server.request_handler import MCPRequestHandler
from src.mcp_server.security.rate_limiter import MCPRateLimiter
from src.mcp_server.security.input_sanitizer import InputSanitizer
from src.mcp_server.security.origin_validator import OriginValidator
from src.mcp_server.security.rbac_validator import MCPRBACValidator


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_tool_registry():
    """Create a mock MCP tool registry."""
    registry = Mock(spec=MCPToolRegistry)
    registry.get_tool.return_value = None
    registry.list_tools.return_value = []
    registry.execute_tool.return_value = {"success": True, "data": "test"}
    registry.get_tool_summary.return_value = {
        "total_tools": 17,
        "domains": {"health": 4, "tasks": 5, "agents_catalogue": 4, "admin": 4}
    }
    return registry


@pytest.fixture
def mock_session_manager():
    """Create a mock session manager."""
    manager = Mock(spec=MCPSessionManager)
    manager.create_session.return_value = "test-session-id"
    manager.validate_session.return_value = True
    manager.terminate_session.return_value = True
    manager.get_session_stats.return_value = {
        "active_sessions": 1,
        "total_created": 5,
        "expired_sessions": 2
    }
    return manager


@pytest.fixture
def mock_stream_manager():
    """Create a mock stream manager."""
    manager = Mock(spec=MCPStreamManager)
    manager.create_stream.return_value = "test-stream-id"
    manager.add_event.return_value = None
    manager.close_stream.return_value = None
    manager.get_events_after.return_value = []
    manager.get_stream_stats.return_value = {
        "active_streams": 1,
        "total_created": 3,
        "expired_streams": 1
    }
    return manager


@pytest.fixture
def mock_error_handler():
    """Create a mock error handler."""
    handler = Mock(spec=MCPErrorHandler)
    handler.format_mcp_error.return_value = {
        "jsonrpc": "2.0",
        "id": "test-id",
        "error": {"code": -32603, "message": "Internal error"}
    }
    handler.tool_not_found_error.return_value = {
        "jsonrpc": "2.0",
        "id": "test-id",
        "error": {"code": -32601, "message": "Method not found"}
    }
    return handler


@pytest.fixture
def mock_request_handler(mock_tool_registry, mock_rbac_validator):
    """Create a mock request handler."""
    handler = Mock(spec=MCPRequestHandler)
    handler.handle_request.return_value = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"status": "ok"}
    }
    handler.handle_batch_request.return_value = [
        {"jsonrpc": "2.0", "id": 1, "result": {"status": "ok"}}
    ]
    return handler


@pytest.fixture
def mock_rate_limiter():
    """Create a mock rate limiter."""
    limiter = Mock(spec=MCPRateLimiter)
    limiter.check_rate_limit.return_value = True
    limiter.get_rate_limit_status.return_value = {
        "requests_made": 5,
        "requests_remaining": 55,
        "window_resets_in": 45
    }
    return limiter


@pytest.fixture
def mock_input_sanitizer():
    """Create a mock input sanitizer."""
    sanitizer = Mock(spec=InputSanitizer)
    sanitizer.sanitize_input.side_effect = lambda x, field: x  # Pass through by default
    sanitizer.sanitize_tool_arguments.side_effect = lambda tool, args: args
    return sanitizer


@pytest.fixture
def mock_origin_validator():
    """Create a mock origin validator."""
    validator = Mock(spec=OriginValidator)
    validator.validate_origin.return_value = True  # Allow all origins by default
    return validator


@pytest.fixture
def mock_rbac_validator():
    """Create a mock RBAC validator."""
    validator = Mock(spec=MCPRBACValidator)
    validator.validate_tool_access.return_value = True  # Allow all access by default
    return validator


@pytest.fixture
def sample_health_response():
    """Sample health check response data."""
    return {
        "status": "healthy",
        "timestamp": "2025-01-15T10:00:00Z",
        "components": {
            "database": {"status": "healthy", "response_time": "2ms"},
            "cache": {"status": "healthy", "hit_rate": 0.95},
            "services": {"status": "healthy", "active_services": 3}
        },
        "metrics": {
            "cpu_usage": 45.2,
            "memory_usage": 62.8,
            "disk_usage": 78.3,
            "requests_per_second": 12.5
        }
    }


@pytest.fixture
def sample_task_data():
    """Sample task data for testing."""
    return {
        "id": "test-task-123",
        "name": "Test Task",
        "description": "A test task for unit testing",
        "status": "pending",
        "created_at": "2025-01-15T10:00:00Z",
        "updated_at": "2025-01-15T10:00:00Z",
        "parameters": {
            "environment": "test",
            "timeout": 300
        }
    }


@pytest.fixture
def sample_agents_catalogue_data():
    """Sample agents catalogue data for testing."""
    return {
        "services": [
            {
                "name": "spinnaker-v3-pipeline-generator",
                "type": "workflow",
                "description": "Generate Spinnaker V3 pipelines",
                "version": "1.0.0",
                "status": "active"
            },
            {
                "name": "repo-context-generator",
                "type": "micro-frontend",
                "description": "Generate repository context",
                "version": "2.1.0",
                "status": "active"
            }
        ],
        "total_services": 2,
        "active_services": 2
    }


@pytest.fixture
def sample_mcp_request():
    """Sample MCP JSON-RPC request."""
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "overall_health",
            "arguments": {}
        }
    }


@pytest.fixture
def sample_mcp_response():
    """Sample MCP JSON-RPC response."""
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": "Health check completed successfully"
                }
            ],
            "isError": False
        }
    }


@pytest.fixture
def sample_sse_events():
    """Sample SSE events for testing."""
    return [
        {
            "id": "event-1",
            "event": "tool_execution",
            "data": {"tool": "overall_health", "status": "started"},
            "timestamp": "2025-01-15T10:00:00Z"
        },
        {
            "id": "event-2",
            "event": "tool_execution",
            "data": {"tool": "overall_health", "status": "completed", "result": "healthy"},
            "timestamp": "2025-01-15T10:00:01Z"
        }
    ]


@pytest.fixture
def mock_api_endpoint():
    """Mock API endpoint responses."""
    with patch('src.mcp_server.tools.base_tool.BaseMCPTool.call_api_endpoint') as mock:
        mock.return_value = {"status": "success", "data": "test"}
        yield mock


@pytest.fixture
def mock_stream_api_endpoint():
    """Mock streaming API endpoint."""
    async def mock_stream():
        yield {"type": "progress", "data": {"step": 1, "total": 3}}
        yield {"type": "progress", "data": {"step": 2, "total": 3}}
        yield {"type": "complete", "data": {"result": "success"}}
    
    with patch('src.mcp_server.tools.base_tool.BaseMCPTool.stream_api_endpoint') as mock:
        mock.return_value = mock_stream()
        yield mock


@pytest.fixture
def clean_environment():
    """Ensure clean test environment."""
    # Clean up any global state before test
    yield
    # Clean up any global state after test


class MockRequest:
    """Mock FastAPI request object for testing."""
    
    def __init__(self, origin=None, session_id=None, user_roles=None):
        self.headers = {}
        if origin:
            self.headers["Origin"] = origin
        if session_id:
            self.headers["Mcp-Session-Id"] = session_id
        
        self.state = Mock()
        if user_roles:
            self.state.user = Mock()
            self.state.user.roles = user_roles
        else:
            self.state.user = None
        
        self.client = Mock()
        self.client.host = "127.0.0.1"


@pytest.fixture
def mock_authenticated_request():
    """Mock authenticated request with user."""
    return MockRequest(
        origin="http://localhost:3000",
        session_id="test-session",
        user_roles=["user", "developer"]
    )


@pytest.fixture
def mock_admin_request():
    """Mock request with admin user."""
    return MockRequest(
        origin="http://localhost:3000",
        session_id="admin-session",
        user_roles=["user", "admin"]
    )


@pytest.fixture
def mock_unauthenticated_request():
    """Mock unauthenticated request."""
    return MockRequest(origin="http://localhost:3000")


# Pytest markers for organizing tests

def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "security: mark test as a security test"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as a performance test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


# Test utilities
class TestHelpers:
    """Helper utilities for MCP tests."""
    
    @staticmethod
    def assert_mcp_response_format(response: Dict[str, Any]):
        """Assert that response follows MCP JSON-RPC format."""
        assert "jsonrpc" in response
        assert response["jsonrpc"] == "2.0"
        assert "id" in response
        # Should have either result or error, but not both
        has_result = "result" in response
        has_error = "error" in response
        assert has_result or has_error
        assert not (has_result and has_error)
    
    @staticmethod
    def assert_tool_response_format(response: Dict[str, Any]):
        """Assert that response follows MCP tool response format."""
        assert "success" in response
        assert isinstance(response["success"], bool)
        
        if response["success"]:
            assert "data" in response
            assert "message" in response
        else:
            assert "error" in response
    
    @staticmethod
    def create_mock_tool_result(success: bool = True, data: Any = None, error: str = None):
        """Create a mock tool execution result."""
        if success:
            return {
                "success": True,
                "data": data or {"status": "completed"},
                "message": "Operation completed successfully"
            }
        else:
            return {
                "success": False,
                "error": error or "Mock error",
                "message": "Operation failed"
            }


@pytest.fixture
def test_helpers():
    """Provide test helper utilities."""
    return TestHelpers 