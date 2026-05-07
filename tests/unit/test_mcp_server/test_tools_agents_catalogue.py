"""
Unit tests for MCP agents catalogue domain tools.

Tests the agents catalogue tools including service execution, service discovery,
catalogue browsing, and configuration access.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from typing import Dict, Any

# ExecuteAgentsCatalogueAgentTool removed
from src.mcp_server.tools.agents_catalogue.list_agents_catalogue_services import ListAgentsCatalogueServicesTool
from src.mcp_server.tools.agents_catalogue.get_agents_catalogue_items import GetAgentsCatalogueItemsTool
from src.mcp_server.tools.agents_catalogue.get_agents_catalogue_config import GetAgentsCatalogueConfigTool


# ExecuteAgentsCatalogueAgentTool tests removed - tool was deleted


class TestListAgentsCatalogueServicesTool:
    """Test cases for ListAgentsCatalogueServicesTool."""
    
    @pytest.fixture
    def tool(self):
        """Create ListAgentsCatalogueServicesTool instance."""
        return ListAgentsCatalogueServicesTool()
    
    def test_tool_properties(self, tool):
        """Test tool basic properties."""
        assert tool.name == "list_agents_catalogue_services"
        assert tool.domain == "agents_catalogue"
        assert "list" in tool.description.lower()
        assert "services" in tool.description.lower()
    
    def test_input_schema(self, tool):
        """Test input schema validation."""
        schema = tool.input_schema
        assert schema["type"] == "object"
        assert schema["properties"] == {}  # No parameters required
        assert schema["required"] == []
    
    @pytest.mark.asyncio
    async def test_execute_success(self, tool):
        """Test successful service listing."""
        mock_response = {
            "services": [
                {"name": "service1", "type": "workflow", "status": "active"},
                {"name": "service2", "type": "micro-frontend", "status": "active"},
                {"name": "service3", "type": "gateway-integration", "status": "active"}
            ],
            "total_services": 3,
            "active_services": 3
        }
        
        with patch.object(tool, 'call_api_endpoint', return_value=mock_response) as mock_call:
            result = await tool.execute()
            
            mock_call.assert_called_once_with("GET", "/api/v1/agents-catalogue/services")
            assert result["isError"] is False
            assert "content" in result
            assert len(result["content"]) == 1
            assert result["content"][0]["type"] == "text"
            # Check that the JSON contains the services
            import json
            text_content = result["content"][0]["text"]
            parsed_content = json.loads(text_content)
            assert parsed_content["total_services"] == 3
            assert len(parsed_content["services"]) == 3

    @pytest.mark.asyncio
    async def test_execute_empty_services(self, tool):
        """Test execution with no services."""
        mock_response = {
            "services": [],
            "total_services": 0,
            "active_services": 0,
            "timestamp": "2025-01-15T10:00:00Z"
        }
        
        with patch.object(tool, 'call_api_endpoint', return_value=mock_response):
            result = await tool.execute()
            
            assert result["isError"] is False
            assert "content" in result
            # Check that the response contains empty services
            import json
            text_content = result["content"][0]["text"]
            parsed_content = json.loads(text_content)
            assert parsed_content["total_services"] == 0


class TestGetAgentsCatalogueItemsTool:
    """Test cases for GetAgentsCatalogueItemsTool."""
    
    @pytest.fixture
    def tool(self):
        """Create GetAgentsCatalogueItemsTool instance."""
        return GetAgentsCatalogueItemsTool()
    
    def test_tool_properties(self, tool):
        """Test tool basic properties."""
        assert tool.name == "get_agents_catalogue_items"
        assert tool.domain == "agents_catalogue"
        assert "catalogue items" in tool.description.lower()
    
    def test_input_schema(self, tool):
        """Test input schema validation."""
        schema = tool.input_schema
        assert schema["type"] == "object"
        assert "page" in schema["properties"]
        assert "per_page" in schema["properties"]
        assert "search" in schema["properties"]
        assert "type" in schema["properties"]
        assert "lifecycle" in schema["properties"]
        
        # Check defaults
        assert schema["properties"]["page"]["default"] == 1
        assert schema["properties"]["per_page"]["default"] == 20
        
        # Check lifecycle enum
        lifecycle_enum = schema["properties"]["lifecycle"]["enum"]
        assert "active" in lifecycle_enum
        assert "deprecated" in lifecycle_enum
        assert "experimental" in lifecycle_enum
        
        # No required parameters
        assert schema["required"] == []
    
    @pytest.mark.asyncio
    async def test_execute_default_parameters(self, tool):
        """Test execution with default parameters."""
        mock_response = {
            "items": [
                {"id": "item-1", "name": "Test Item 1", "type": "workflow"},
                {"id": "item-2", "name": "Test Item 2", "type": "micro-frontend"}
            ],
            "pagination": {
                "page": 1,
                "per_page": 20,
                "total_items": 2,
                "total_pages": 1
            }
        }
        
        with patch.object(tool, 'call_api_endpoint', return_value=mock_response) as mock_call:
            result = await tool.execute()
            
            mock_call.assert_called_once_with("GET", "/api/v1/agents-catalogue/items?page=1&per_page=20")
            assert result["isError"] is False
            assert "content" in result
            assert len(result["content"]) == 1
            assert result["content"][0]["type"] == "text"
            # Check that the JSON contains the items
            import json
            text_content = result["content"][0]["text"]
            parsed_content = json.loads(text_content)
            assert len(parsed_content["items"]) == 2

    @pytest.mark.asyncio
    async def test_execute_with_pagination(self, tool):
        """Test execution with pagination parameters."""
        mock_response = {
            "items": [{"id": "item-1", "name": "Test Item"}],
            "pagination": {"page": 2, "per_page": 5, "total_items": 10, "total_pages": 2}
        }
        
        with patch.object(tool, 'call_api_endpoint', return_value=mock_response) as mock_call:
            result = await tool.execute(page=2, per_page=5)
            
            mock_call.assert_called_once_with("GET", "/api/v1/agents-catalogue/items?page=2&per_page=5")
            assert result["isError"] is False
            assert "content" in result

    @pytest.mark.asyncio
    async def test_execute_with_filters(self, tool):
        """Test execution with search and filter parameters."""
        mock_response = {
            "items": [
                {
                    "id": "item-1",
                    "name": "Pipeline Generator",
                    "type": "workflow",
                    "lifecycle": "active"
                }
            ],
            "pagination": {"page": 1, "per_page": 20, "total_items": 1, "total_pages": 1}
        }
        
        with patch.object(tool, 'call_api_endpoint', return_value=mock_response) as mock_call:
            result = await tool.execute(
                search="pipeline",
                type="workflow",
                lifecycle="active"
            )
            
            expected_url = "/api/v1/agents-catalogue/items?page=1&per_page=20&search=pipeline&type=workflow&lifecycle=active"
            mock_call.assert_called_once_with("GET", expected_url)
            assert result["isError"] is False
            assert "content" in result
            # Check that the JSON contains the filtered items
            import json
            text_content = result["content"][0]["text"]
            parsed_content = json.loads(text_content)
            assert len(parsed_content["items"]) == 1


class TestGetAgentsCatalogueConfigTool:
    """Test cases for GetAgentsCatalogueConfigTool."""
    
    @pytest.fixture
    def tool(self):
        """Create GetAgentsCatalogueConfigTool instance."""
        return GetAgentsCatalogueConfigTool()
    
    def test_tool_properties(self, tool):
        """Test tool basic properties."""
        assert tool.name == "get_agents_catalogue_config"
        assert tool.domain == "agents_catalogue"
        assert "configuration" in tool.description.lower()
    
    def test_input_schema(self, tool):
        """Test input schema validation."""
        schema = tool.input_schema
        assert schema["type"] == "object"
        assert schema["properties"] == {}  # No parameters required
        assert schema["required"] == []
    
    @pytest.mark.asyncio
    async def test_execute_success(self, tool):
        """Test successful configuration retrieval."""
        mock_response = {
            "version": "2.0.0",
            "supported_types": ["workflow", "micro-frontend", "gateway-integration"],
            "supported_lifecycles": ["experimental", "active", "deprecated"],
            "features": {
                "auto_discovery": True,
                "validation": True,
                "version_control": True
            }
        }
        
        with patch.object(tool, 'call_api_endpoint', return_value=mock_response) as mock_call:
            result = await tool.execute()
            
            mock_call.assert_called_once_with("GET", "/api/v1/agents-catalogue/config")
            assert result["isError"] is False
            assert "content" in result
            assert len(result["content"]) == 1
            assert result["content"][0]["type"] == "text"
            # Check that the JSON contains the config
            import json
            text_content = result["content"][0]["text"]
            parsed_content = json.loads(text_content)
            assert parsed_content["version"] == "2.0.0"
            assert "workflow" in parsed_content["supported_types"]
            assert "features" in parsed_content

    @pytest.mark.asyncio
    async def test_execute_config_error(self, tool):
        """Test configuration retrieval with error."""
        with patch.object(tool, 'call_api_endpoint', side_effect=Exception("Config service unavailable")):
            result = await tool.execute()
            
            assert result["isError"] is True
            assert "content" in result
            assert len(result["content"]) == 1
            assert result["content"][0]["type"] == "text"
            assert "Config service unavailable" in result["content"][0]["text"]


# Integration tests for agents catalogue tools
class TestAgentsCatalogueToolsIntegration:
    """Integration tests for agents catalogue domain tools."""
    
    @pytest.mark.asyncio
    async def test_service_discovery_workflow(self):
        """Test complete service discovery workflow."""
        list_tool = ListAgentsCatalogueServicesTool()
        items_tool = GetAgentsCatalogueItemsTool()
        config_tool = GetAgentsCatalogueConfigTool()
        # execute_tool removed
        
        # Mock responses for workflow
        mock_responses = [
            # List services response
            {
                "services": [
                    {"name": "spinnaker-v3-pipeline-generator", "type": "workflow", "status": "active"}
                ],
                "total_services": 1
            },
            # Get items response
            {
                "items": [
                    {"id": "item-1", "name": "Pipeline Generator", "type": "workflow"}
                ],
                "pagination": {"total_items": 1}
            },
            # Get config response
            {
                "version": "2.0.0",
                "supported_types": ["workflow"],
                "features": {"pipeline_generation": True}
            },

        ]
        
        with patch('src.mcp_server.tools.base_tool.BaseMCPTool.call_api_endpoint') as mock_call:
            mock_call.side_effect = mock_responses
            
            # Discovery workflow
            services_result = await list_tool.execute()
            items_result = await items_tool.execute()
            config_result = await config_tool.execute()
            
            # Verify all operations succeeded (MCP format)
            assert all(result["isError"] is False for result in [services_result, items_result, config_result])
            assert all("content" in result for result in [services_result, items_result, config_result])
            assert mock_call.call_count == 3
    
    def test_agents_catalogue_tools_consistency(self):
        """Test consistency across all agents catalogue tools."""
        tools = [
            ListAgentsCatalogueServicesTool(),
            GetAgentsCatalogueItemsTool(),
            GetAgentsCatalogueConfigTool()
        ]
        
        for tool in tools:
            # All tools should have same domain
            assert tool.domain == "agents_catalogue"
            
            # All should have proper annotations
            assert tool.annotations is not None
            assert tool.annotations["domain"] == "agents_catalogue"
            
            # All should have proper input schema
            assert tool.input_schema["type"] == "object" 