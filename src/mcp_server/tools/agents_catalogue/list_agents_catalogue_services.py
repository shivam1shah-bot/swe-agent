"""
List Agents Catalogue Services MCP Tool.

Lists all available agents catalogue services and their capabilities.
"""

from typing import Dict, Any
from ..base_tool import BaseMCPTool


class ListAgentsCatalogueServicesTool(BaseMCPTool):
    """
    Tool for listing available agents catalogue services.
    
    This tool provides a comprehensive list of all registered agents catalogue
    services with their capabilities, health status, performance metrics, and
    API documentation links. Use this when you need to discover available
    automation services or check service operational status.
    """
    
    @property
    def name(self) -> str:
        """Tool name."""
        return "list_agents_catalogue_services"
    
    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "List all dynamically registered services in the agents catalogue including "
            "service capabilities, health status, performance metrics, and API documentation. "
            "Use this tool when you need to discover available automation services or check "
            "service operational status. Returns comprehensive service registry information."
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
            "title": "List Agents Catalogue Services",
            "readOnlyHint": True,
            "openWorldHint": False,
            "domain": "agents_catalogue"
        }
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute agents catalogue services listing.
        
        Returns:
            MCP-formatted agents catalogue services information
        """
        try:
            # Validate arguments (none required for this tool)
            validated_args = self.validate_arguments(**kwargs)
            
            self.logger.info("Listing agents catalogue services")
            
            # Call the existing agents catalogue services API endpoint
            services_data = await self.call_api_endpoint("GET", "/api/v1/agents-catalogue/services")
            
            # Return MCP-formatted response with raw JSON
            import json
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(services_data, indent=2)
                    }
                ],
                "isError": False
            }
            
        except Exception as e:
            self.logger.error("Agents catalogue services listing failed", error=str(e))
            
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