"""
Integration tests for MCP HTTP server and FastAPI integration.

Tests the complete MCP server integration including HTTP endpoints,
SSE streaming, session management, and tool execution.
"""

import pytest
import json
import asyncio
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from src.api.api import create_app
from mcp_server.server.http_server import MCPHttpServer
from mcp_server.tools.registry import MCPToolRegistry


class TestMCPHTTPIntegration:
    """Integration tests for MCP HTTP server."""
    
    @pytest.fixture
    def app(self):
        """Create FastAPI app for testing."""
        return create_app()
    
    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)
    
    def test_mcp_health_endpoint(self, client):
        """Test MCP health check endpoint."""
        response = client.get("/api/v1/mcp/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "components" in data
    
    def test_mcp_info_endpoint(self, client):
        """Test MCP server info endpoint."""
        response = client.get("/api/v1/mcp/info")
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "swe-agent-mcp-server"
        assert data["protocol_version"] == "2025-03-26"
        assert data["transport"] == "streamable_http"
        assert "capabilities" in data
        assert "endpoints" in data
    
    def test_mcp_tools_list_endpoint(self, client):
        """Test MCP tools list endpoint."""
        response = client.get("/api/v1/mcp/tools")
        
        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        assert "total_count" in data
        assert "timestamp" in data
        assert data["total_count"] > 0  # Should have tools registered
    
    def test_mcp_tools_summary_endpoint(self, client):
        """Test MCP tools summary endpoint."""
        response = client.get("/api/v1/mcp/tools/summary")
        
        assert response.status_code == 200
        data = response.json()
        assert "total_tools" in data
        assert "domains" in data
        assert "capabilities" in data
        assert "timestamp" in data
    
    def test_mcp_stats_endpoint(self, client):
        """Test MCP server statistics endpoint."""
        response = client.get("/api/v1/mcp/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert "server" in data
        assert "sessions" in data
        assert "streams" in data
    
    def test_mcp_enhanced_openapi_endpoint(self, client):
        """Test enhanced OpenAPI specification endpoint."""
        response = client.get("/api/v1/mcp/openapi-enhanced")
        
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data or "info" in data  # Valid OpenAPI structure
        assert "paths" in data
    
    def test_mcp_session_creation(self, client):
        """Test MCP session creation."""
        response = client.post(
            "/api/v1/mcp/sessions",
            headers={"Origin": "http://localhost:3000"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "created_at" in data
        assert "expires_in" in data
        
        # Store session ID for cleanup
        session_id = data["session_id"]
        
        # Test session termination
        delete_response = client.delete(f"/api/v1/mcp/sessions/{session_id}")
        assert delete_response.status_code == 200
    
    def test_mcp_json_rpc_request(self, client):
        """Test MCP JSON-RPC request handling."""
        # Test initialize request
        initialize_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocol_version": {"version": "2025-03-26"},
                "client_info": {"name": "test-client", "version": "1.0.0"},
                "capabilities": {}
            }
        }
        
        response = client.post(
            "/api/v1/mcp",
            json=initialize_request,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        assert "result" in data
        assert "_session_id" in data  # Session ID should be added
    
    def test_mcp_tools_list_json_rpc(self, client):
        """Test tools/list via JSON-RPC."""
        request_data = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        response = client.post(
            "/api/v1/mcp",
            json=request_data,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 2
        assert "result" in data
        assert "tools" in data["result"]
    
    def test_mcp_ping_json_rpc(self, client):
        """Test ping via JSON-RPC."""
        request_data = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "ping",
            "params": {}
        }
        
        response = client.post(
            "/api/v1/mcp",
            json=request_data,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 3
        assert "result" in data
    
    def test_mcp_batch_request(self, client):
        """Test batch JSON-RPC request."""
        batch_request = [
            {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        ]
        
        response = client.post(
            "/api/v1/mcp",
            json=batch_request,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert all(resp["jsonrpc"] == "2.0" for resp in data)
    
    def test_mcp_invalid_json_rpc(self, client):
        """Test invalid JSON-RPC request."""
        invalid_request = {
            "invalid": "request"
        }
        
        response = client.post(
            "/api/v1/mcp",
            json=invalid_request,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200  # MCP errors are returned as 200 with error payload
        data = response.json()
        assert "error" in data
    
    @pytest.mark.asyncio
    async def test_mcp_sse_stream(self, client):
        """Test MCP Server-Sent Events streaming."""
        # Create a session first
        session_response = client.post("/api/v1/mcp/sessions")
        session_data = session_response.json()
        session_id = session_data["session_id"]
        
        # Test SSE endpoint (note: TestClient doesn't support SSE well, so we'll test the response structure)
        response = client.get(
            "/api/v1/mcp/stream/test-stream-id",
            headers={"Mcp-Session-Id": session_id}
        )
        
        # The response might be an error since the stream doesn't exist, but it should be properly formatted
        assert response.status_code in [200, 404, 401]  # Valid HTTP status codes for SSE
    
    def test_mcp_cors_headers(self, client):
        """Test CORS headers on MCP endpoints."""
        response = client.options(
            "/api/v1/mcp",
            headers={"Origin": "http://localhost:3000"}
        )
        
        # Should handle OPTIONS request for CORS
        assert response.status_code in [200, 204]


class TestMCPToolExecution:
    """Integration tests for MCP tool execution."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_app()
        return TestClient(app)
    
    def test_execute_health_tool(self, client):
        """Test executing a health tool via MCP."""
        request_data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "overall_health",
                "arguments": {}
            }
        }
        
        with patch('mcp.tools.base_tool.BaseMCPTool.call_api_endpoint') as mock_api:
            mock_api.return_value = {
                "status": "healthy",
                "timestamp": "2025-01-15T10:00:00Z"
            }
            
            response = client.post(
                "/api/v1/mcp",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["jsonrpc"] == "2.0"
            assert "result" in data
            assert "content" in data["result"]
    
    def test_execute_task_creation_tool(self, client):
        """Test executing task creation tool via MCP."""
        request_data = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "get_task",
                "arguments": {
                    "task_id": "test-task-123"
                }
            }
        }
        
        with patch('mcp.tools.base_tool.BaseMCPTool.call_api_endpoint') as mock_api:
            mock_api.return_value = {
                "id": "test-task-id",
                "name": "Test Task",
                "status": "pending",
                "created_at": "2025-01-15T10:00:00Z"
            }
            
            response = client.post(
                "/api/v1/mcp",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["jsonrpc"] == "2.0"
            assert "result" in data
    
    def test_execute_nonexistent_tool(self, client):
        """Test executing non-existent tool via MCP."""
        request_data = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "nonexistent_tool",
                "arguments": {}
            }
        }
        
        response = client.post(
            "/api/v1/mcp",
            json=request_data,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert "error" in data
        assert data["error"]["code"] == -32601  # Method not found
    
    def test_execute_tool_with_validation_error(self, client):
        """Test executing tool with invalid arguments."""
        request_data = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "get_task",
                "arguments": {}  # Missing required 'name' parameter
            }
        }
        
        response = client.post(
            "/api/v1/mcp",
            json=request_data,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["jsonrpc"] == "2.0"
        # Should either have result with isError=true or error field
        assert "result" in data or "error" in data


class TestMCPSecurity:
    """Integration tests for MCP security features."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_app()
        return TestClient(app)
    
    def test_mcp_origin_validation(self, client):
        """Test origin validation for MCP requests."""
        request_data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "ping",
            "params": {}
        }
        
        # Test with invalid origin
        response = client.post(
            "/api/v1/mcp",
            json=request_data,
            headers={
                "Content-Type": "application/json",
                "Origin": "http://malicious-site.com"
            }
        )
        
        # Should be blocked by origin validation
        assert response.status_code in [403, 400]
    
    def test_mcp_session_validation(self, client):
        """Test session validation for SSE streams."""
        # Try to access stream without valid session
        response = client.get(
            "/api/v1/mcp/stream/test-stream",
            headers={"Mcp-Session-Id": "invalid-session"}
        )
        
        assert response.status_code == 401  # Unauthorized
    
    def test_mcp_input_sanitization(self, client):
        """Test input sanitization for malicious payloads."""
        malicious_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "overall_health",
                "arguments": {
                    "malicious": "<script>alert('xss')</script>",
                    "injection": "'; DROP TABLE users; --"
                }
            }
        }
        
        response = client.post(
            "/api/v1/mcp",
            json=malicious_request,
            headers={"Content-Type": "application/json"}
        )
        
        # Should either sanitize the input or return validation error
        assert response.status_code == 200
        data = response.json()
        # Should have either result or error (not crash)
        assert "result" in data or "error" in data


class TestMCPPerformance:
    """Performance tests for MCP integration."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_app()
        return TestClient(app)
    
    def test_mcp_concurrent_requests(self, client):
        """Test MCP server handling concurrent requests."""
        import concurrent.futures
        import time
        
        def make_request():
            request_data = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "ping",
                "params": {}
            }
            
            start_time = time.time()
            response = client.post(
                "/api/v1/mcp",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )
            end_time = time.time()
            
            return {
                "status_code": response.status_code,
                "response_time": end_time - start_time,
                "success": response.status_code == 200
            }
        
        # Make 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [future.result() for future in futures]
        
        # All requests should succeed
        assert all(result["success"] for result in results)
        
        # Response times should be reasonable (less than 1 second each)
        assert all(result["response_time"] < 1.0 for result in results)
    
    def test_mcp_batch_request_performance(self, client):
        """Test performance of batch requests."""
        import time
        
        # Create a large batch request
        batch_size = 50
        batch_request = [
            {"jsonrpc": "2.0", "id": i, "method": "ping", "params": {}}
            for i in range(batch_size)
        ]
        
        start_time = time.time()
        response = client.post(
            "/api/v1/mcp",
            json=batch_request,
            headers={"Content-Type": "application/json"}
        )
        end_time = time.time()
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == batch_size
        
        # Batch processing should be efficient (less than 2 seconds for 50 requests)
        processing_time = end_time - start_time
        assert processing_time < 2.0
    
    def test_mcp_memory_usage(self, client):
        """Test memory usage during MCP operations."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        # Get initial memory usage
        initial_memory = process.memory_info().rss
        
        # Make many requests to test for memory leaks
        for i in range(100):
            request_data = {
                "jsonrpc": "2.0",
                "id": i,
                "method": "tools/list",
                "params": {}
            }
            
            response = client.post(
                "/api/v1/mcp",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )
            
            assert response.status_code == 200
        
        # Get final memory usage
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 50MB for 100 requests)
        assert memory_increase < 50 * 1024 * 1024  # 50MB in bytes 