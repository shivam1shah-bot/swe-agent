"""
Get Agents Catalogue Config MCP Tool.

Retrieves agents catalogue configuration and metadata.
"""

from typing import Dict, Any
from ..base_tool import BaseMCPTool


class GetAgentsCatalogueConfigTool(BaseMCPTool):
    """
    Tool for retrieving agents catalogue configuration.
    
    This tool retrieves configuration information for the agents catalogue
    including available types, lifecycles, tags, and default settings. Use
    this when you need to understand catalogue structure, validate item
    configurations, or build catalogue management interfaces.
    """
    
    @property
    def name(self) -> str:
        """Tool name."""
        return "get_agents_catalogue_config"
    
    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Retrieve agents catalogue configuration including available types, lifecycles, "
            "tags, and default settings. Use this tool when you need to understand catalogue "
            "structure, validate item configurations, or build catalogue management interfaces. "
            "Returns comprehensive configuration metadata for the catalogue system."
        )
    
    @property
    def domain(self) -> str:
        """Tool domain."""
        return "agents_catalogue"
    
    @property
    def input_schema(self) -> Dict[str, Any]:
        """Input schema for the tool."""
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    @property
    def annotations(self) -> Dict[str, Any]:
        """Tool annotations."""
        return {
            "title": "Get Agents Catalogue Configuration",
            "readOnlyHint": True,
            "openWorldHint": False,
            "domain": "agents_catalogue"
        }
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute agents catalogue configuration retrieval.
        
        Returns:
            MCP-formatted agents catalogue configuration information
        """
        try:
            # Validate arguments (none required for this tool)
            validated_args = self.validate_arguments(**kwargs)
            
            self.logger.info("Retrieving agents catalogue configuration")
            
            # Call the existing agents catalogue config API endpoint
            config_data = await self.call_api_endpoint("GET", "/api/v1/agents-catalogue/config")
            
            # Return MCP-formatted response with raw JSON
            import json
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(config_data, indent=2)
                    }
                ],
                "isError": False
            }
            
        except Exception as e:
            self.logger.error("Agents catalogue configuration retrieval failed", error=str(e))
            
            # Return MCP-formatted error response
            return {
                "content": [
                    {
                        "type": "text", 
                        "text": f"Error: {str(e)}"
                    }
                ],
                "isError": True
            } 