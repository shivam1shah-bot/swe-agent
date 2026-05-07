"""
Unit tests for MCP health domain tools.

Tests the health monitoring tools including overall health, database health,
services health, and health metrics.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from typing import Dict, Any

from src.mcp_server.tools.health.overall_health import OverallHealthTool
# Other health tools removed


class TestOverallHealthTool:
    """Test cases for OverallHealthTool."""
    
    @pytest.fixture
    def tool(self):
        """Create OverallHealthTool instance."""
        return OverallHealthTool()
    
    def test_tool_properties(self, tool):
        """Test tool basic properties."""
        assert tool.name == "overall_health"
        assert tool.domain == "health"
        assert "comprehensive system health" in tool.description.lower()
        assert tool.input_schema["type"] == "object"
        assert tool.annotations is not None
    
    @pytest.mark.asyncio
    async def test_execute_success(self, tool):
        """Test successful tool execution."""
        mock_response = {"status": "healthy", "components": {"database": "ok"}}
        
        with patch.object(tool, 'call_api_endpoint', return_value=mock_response) as mock_call:
            result = await tool.execute()
            
            mock_call.assert_called_once_with("GET", "/api/v1/health")
            assert result["isError"] is False
            assert "content" in result
            assert len(result["content"]) == 1
            assert result["content"][0]["type"] == "text"
            # The text should contain the JSON response
            import json
            text_content = result["content"][0]["text"]
            parsed_content = json.loads(text_content)
            assert parsed_content == mock_response
    
    @pytest.mark.asyncio
    async def test_execute_failure(self, tool):
        """Test tool execution with API failure."""
        with patch.object(tool, 'call_api_endpoint', side_effect=Exception("API Error")):
            result = await tool.execute()
            
            assert result["isError"] is True
            assert "content" in result
            assert len(result["content"]) == 1
            assert result["content"][0]["type"] == "text"
            assert "API Error" in result["content"][0]["text"]
    
    def test_annotations(self, tool):
        """Test tool annotations."""
        annotations = tool.annotations
        assert annotations["domain"] == "health"
        assert annotations["readOnlyHint"] is True
        assert "pre_operation_checks" in annotations["use_cases"]


# Test classes for deleted health tools removed


# Integration test for all health tools
class TestHealthToolsIntegration:
    """Integration tests for health domain tools."""
    
    @pytest.mark.asyncio
    async def test_overall_health_tool_execution(self):
        """Test execution of overall health tool."""
        tool = OverallHealthTool()
        
        # Mock successful response
        mock_response = {"status": "healthy", "timestamp": "2025-01-15T10:00:00Z"}
        
        with patch('src.mcp_server.tools.base_tool.BaseMCPTool.call_api_endpoint') as mock_call:
            mock_call.return_value = mock_response
            
            result = await tool.execute()
            
            # Verify tool executed successfully
            assert result["isError"] is False
            assert "content" in result
            assert mock_call.call_count == 1
    
    def test_health_tool_properties_consistency(self):
        """Test consistency of health tool properties."""
        tool = OverallHealthTool()
        
        # Health tool should have proper domain
        assert tool.domain == "health"
        
        # Should have proper annotations
        assert tool.annotations is not None
        assert tool.annotations["domain"] == "health"
        assert tool.annotations["readOnlyHint"] is True
        
        # Should have proper input schema
        assert tool.input_schema["type"] == "object"
        assert "properties" in tool.input_schema
        assert "required" in tool.input_schema 