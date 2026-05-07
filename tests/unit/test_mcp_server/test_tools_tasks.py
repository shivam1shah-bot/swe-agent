"""
Unit tests for MCP task domain tools.

Tests the task management tools including create, get, list, update, and logs.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from typing import Dict, Any
import uuid

from src.mcp_server.tools.tasks.get_task import GetTaskTool
from src.mcp_server.tools.tasks.list_tasks import ListTasksTool
from src.mcp_server.tools.tasks.get_task_execution_logs import GetTaskExecutionLogsTool
# Removed: CreateTaskTool, UpdateTaskStatusTool


# TestCreateTaskTool removed - tool was deleted


class TestGetTaskTool:
    """Test cases for GetTaskTool."""
    
    @pytest.fixture
    def tool(self):
        """Create GetTaskTool instance."""
        return GetTaskTool()
    
    def test_tool_properties(self, tool):
        """Test tool basic properties."""
        assert tool.name == "get_task"
        assert tool.domain == "tasks"
        assert "retrieve" in tool.description.lower()
    
    def test_input_schema(self, tool):
        """Test input schema validation."""
        schema = tool.input_schema
        assert schema["type"] == "object"
        assert "task_id" in schema["properties"]
        assert "task_id" in schema["required"]
        assert "pattern" in schema["properties"]["task_id"]  # UUID pattern
    
    @pytest.mark.asyncio
    async def test_execute_success(self, tool):
        """Test successful task retrieval."""
        task_id = str(uuid.uuid4())
        mock_response = {
            "id": task_id,
            "status": "running",
            "name": "Test Task",
            "created_at": "2025-01-15T10:00:00Z"
        }
        
        with patch.object(tool, 'call_api_endpoint', return_value=mock_response) as mock_call:
            result = await tool.execute(task_id=task_id)
            
            mock_call.assert_called_once_with("GET", f"/api/v1/tasks/{task_id}")
            assert result["isError"] is False
            assert "content" in result
            assert len(result["content"]) == 1
            assert result["content"][0]["type"] == "text"
            # The text should contain the JSON response
            import json
            text_content = result["content"][0]["text"]
            parsed_content = json.loads(text_content)
            assert parsed_content["id"] == task_id
            assert parsed_content["status"] == "running"

    @pytest.mark.asyncio
    async def test_execute_task_not_found(self, tool):
        """Test task retrieval with non-existent task."""
        task_id = str(uuid.uuid4())
        
        with patch.object(tool, 'call_api_endpoint', side_effect=Exception("Task not found")):
            result = await tool.execute(task_id=task_id)
            
            assert result["isError"] is True
            assert "content" in result
            assert len(result["content"]) == 1
            assert result["content"][0]["type"] == "text"
            assert "Task not found" in result["content"][0]["text"]


class TestListTasksTool:
    """Test cases for ListTasksTool."""
    
    @pytest.fixture
    def tool(self):
        """Create ListTasksTool instance."""
        return ListTasksTool()
    
    def test_tool_properties(self, tool):
        """Test tool basic properties."""
        assert tool.name == "list_tasks"
        assert tool.domain == "tasks"
        assert "list" in tool.description.lower()
    
    def test_input_schema(self, tool):
        """Test input schema validation."""
        schema = tool.input_schema
        assert schema["type"] == "object"
        assert "status" in schema["properties"]
        assert "limit" in schema["properties"]
        assert schema["required"] == []  # No required parameters
        
        # Check status enum values
        status_enum = schema["properties"]["status"]["enum"]
        assert "pending" in status_enum
        assert "running" in status_enum
        assert "completed" in status_enum
    
    @pytest.mark.asyncio
    async def test_execute_no_filters(self, tool):
        """Test task listing without filters."""
        mock_response = [
            {"id": str(uuid.uuid4()), "name": "Task 1", "status": "pending"},
            {"id": str(uuid.uuid4()), "name": "Task 2", "status": "running"},
            {"id": str(uuid.uuid4()), "name": "Task 3", "status": "completed"}
        ]
        
        with patch.object(tool, 'call_api_endpoint', return_value=mock_response) as mock_call:
            result = await tool.execute()
            
            mock_call.assert_called_once_with("GET", "/api/v1/tasks?limit=20")
            assert result["isError"] is False
            assert "content" in result
            assert len(result["content"]) == 1
            assert result["content"][0]["type"] == "text"
            # The text should contain the JSON response
            import json
            text_content = result["content"][0]["text"]
            parsed_content = json.loads(text_content)
            assert len(parsed_content) == 3

    @pytest.mark.asyncio
    async def test_execute_with_status_filter(self, tool):
        """Test task listing with status filter."""
        mock_response = [
            {"id": str(uuid.uuid4()), "name": "Running Task 1", "status": "running"},
            {"id": str(uuid.uuid4()), "name": "Running Task 2", "status": "running"}
        ]
        
        with patch.object(tool, 'call_api_endpoint', return_value=mock_response) as mock_call:
            result = await tool.execute(status="running")
            
            mock_call.assert_called_once_with("GET", "/api/v1/tasks?limit=20&status=running")
            assert result["isError"] is False
            assert "content" in result
    
    @pytest.mark.asyncio
    async def test_execute_with_limit(self, tool):
        """Test task listing with limit."""
        mock_response = [
            {"id": str(uuid.uuid4()), "name": "Task 1", "status": "pending"}
        ]
        
        with patch.object(tool, 'call_api_endpoint', return_value=mock_response) as mock_call:
            result = await tool.execute(limit=1)
            
            mock_call.assert_called_once_with("GET", "/api/v1/tasks?limit=1")
            assert result["isError"] is False
            assert "content" in result
            assert len(result["content"]) == 1
            assert result["content"][0]["type"] == "text"


# TestUpdateTaskStatusTool removed - tool was deleted


class TestGetTaskExecutionLogsTool:
    """Test cases for GetTaskExecutionLogsTool."""
    
    @pytest.fixture
    def tool(self):
        """Create GetTaskExecutionLogsTool instance."""
        return GetTaskExecutionLogsTool()
    
    def test_tool_properties(self, tool):
        """Test tool basic properties."""
        assert tool.name == "get_task_execution_logs"
        assert tool.domain == "tasks"
        assert "logs" in tool.description.lower()
        assert "execution" in tool.description.lower()
    
    def test_input_schema(self, tool):
        """Test input schema validation."""
        schema = tool.input_schema
        assert schema["type"] == "object"
        assert "task_id" in schema["properties"]
        assert "limit" in schema["properties"]
        assert "task_id" in schema["required"]
        assert schema["properties"]["limit"]["default"] == 50
    
    @pytest.mark.asyncio
    async def test_execute_success(self, tool):
        """Test successful log retrieval."""
        task_id = str(uuid.uuid4())
        
        mock_response = {
            "logs": [
                {"timestamp": "2025-01-15T10:00:00Z", "level": "INFO", "message": "Task started"},
                {"timestamp": "2025-01-15T10:01:00Z", "level": "INFO", "message": "Processing..."},
                {"timestamp": "2025-01-15T10:02:00Z", "level": "INFO", "message": "Task completed"}
            ],
            "total_count": 3,
            "task_id": task_id
        }
        
        with patch.object(tool, 'call_api_endpoint', return_value=mock_response) as mock_call:
            result = await tool.execute(task_id=task_id)
            
            expected_url = f"/api/v1/tasks/{task_id}/execution-logs?limit=50"
            mock_call.assert_called_once_with("GET", expected_url)
            assert result["isError"] is False
            assert "content" in result
            assert len(result["content"]) == 1
            assert result["content"][0]["type"] == "text"
            # Check that the JSON contains the logs
            import json
            text_content = result["content"][0]["text"]
            parsed_content = json.loads(text_content)
            assert len(parsed_content["logs"]) == 3

    @pytest.mark.asyncio
    async def test_execute_with_custom_limit(self, tool):
        """Test log retrieval with custom limit."""
        task_id = str(uuid.uuid4())
        
        mock_response = {
            "logs": [
                {"timestamp": "2025-01-15T10:00:00Z", "level": "INFO", "message": "Task started"}
            ],
            "total_count": 1,
            "task_id": task_id
        }
        
        with patch.object(tool, 'call_api_endpoint', return_value=mock_response) as mock_call:
            result = await tool.execute(task_id=task_id, limit=1)
            
            expected_url = f"/api/v1/tasks/{task_id}/execution-logs?limit=1"
            mock_call.assert_called_once_with("GET", expected_url)
            assert result["isError"] is False
            assert "content" in result 


# Integration tests for task tools
class TestTaskToolsIntegration:
    """Integration tests for task domain tools."""
    
    @pytest.mark.asyncio
    async def test_task_tools_workflow(self):
        """Test remaining task tools workflow."""
        task_id = str(uuid.uuid4())
        
        # Get task
        get_tool = GetTaskTool()
        get_response = {"id": task_id, "name": "Workflow Test", "status": "running"}
        
        # Get logs
        logs_tool = GetTaskExecutionLogsTool()
        logs_response = {"logs": [{"message": "Task started"}], "task_id": task_id}
        
        with patch('src.mcp_server.tools.base_tool.BaseMCPTool.call_api_endpoint') as mock_call:
            mock_call.side_effect = [get_response, logs_response]
            
            # Execute workflow
            get_result = await get_tool.execute(task_id=task_id)
            logs_result = await logs_tool.execute(task_id=task_id)
            
            # Verify all operations succeeded (MCP format)
            assert all(result["isError"] is False for result in [get_result, logs_result])
            assert all("content" in result for result in [get_result, logs_result])
            assert mock_call.call_count == 2
    
    def test_task_tools_consistency(self):
        """Test consistency across remaining task tools."""
        tools = [
            GetTaskTool(),
            ListTasksTool(),
            GetTaskExecutionLogsTool()
        ]
        
        for tool in tools:
            # All task tools should have same domain
            assert tool.domain == "tasks"
            
            # All should have proper annotations
            assert tool.annotations is not None
            assert tool.annotations["domain"] == "tasks"
            
            # All should have proper input schema
            assert tool.input_schema["type"] == "object" 