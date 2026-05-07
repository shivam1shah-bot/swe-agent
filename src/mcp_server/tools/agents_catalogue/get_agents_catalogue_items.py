"""
Get Agents Catalogue Items MCP Tool.

Retrieves agents catalogue items with pagination and filtering.
"""

from typing import Dict, Any, Optional
from ..base_tool import BaseMCPTool


class GetAgentsCatalogueItemsTool(BaseMCPTool):
    """
    Tool for retrieving agents catalogue items.
    
    This tool retrieves agents catalogue items with pagination and filtering
    capabilities. Use this when you need to browse available automation
    templates, search for specific functionality, or manage catalogue content.
    Supports filtering by type, lifecycle, and search terms.
    """
    
    @property
    def name(self) -> str:
        """Tool name."""
        return "get_agents_catalogue_items"
    
    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Retrieve agents catalogue items with pagination and filtering by type, lifecycle, "
            "and search terms. Use this tool when you need to browse available automation "
            "templates, search for specific functionality, or manage catalogue content. "
            "Returns paginated results with detailed item information and metadata."
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
            "properties": {
                "page": {
                    "type": "integer",
                    "description": "Page number for pagination (optional, default: 1)",
                    "minimum": 1,
                    "default": 1
                },
                "per_page": {
                    "type": "integer",
                    "description": "Items per page (optional, default: 20)",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 20
                },
                "search": {
                    "type": "string",
                    "description": "Search term for filtering items (optional)",
                    "maxLength": 255
                },
                "type": {
                    "type": "string",
                    "description": "Filter by item type (optional)"
                },
                "lifecycle": {
                    "type": "string",
                    "description": "Filter by lifecycle stage (optional)",
                    "enum": ["active", "deprecated", "experimental"]
                }
            },
            "required": []
        }
    
    @property
    def annotations(self) -> Dict[str, Any]:
        """Tool annotations."""
        return {
            "title": "Get Agents Catalogue Items",
            "readOnlyHint": True,
            "openWorldHint": False,
            "domain": "agents_catalogue"
        }
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute agents catalogue items retrieval.
        
        Args:
            page: Page number for pagination (optional)
            per_page: Items per page (optional)
            search: Search term for filtering (optional)
            type: Filter by item type (optional)
            lifecycle: Filter by lifecycle stage (optional)
        
        Returns:
            MCP-formatted agents catalogue items information
        """
        try:
            # Validate arguments
            validated_args = self.validate_arguments(**kwargs)
            
            # Extract parameters
            page = validated_args.get("page", 1)
            per_page = validated_args.get("per_page", 20)
            search = validated_args.get("search")
            item_type = validated_args.get("type")
            lifecycle = validated_args.get("lifecycle")
            
            self.logger.info("Retrieving agents catalogue items", 
                           page=page, per_page=per_page, search=search, 
                           type=item_type, lifecycle=lifecycle)
            
            # Build query parameters
            params = {"page": page, "per_page": per_page}
            if search:
                params["search"] = search
            if item_type:
                params["type"] = item_type
            if lifecycle:
                params["lifecycle"] = lifecycle
            
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            endpoint = f"/api/v1/agents-catalogue/items?{query_string}"
            
            # Call the existing agents catalogue items API endpoint
            items_data = await self.call_api_endpoint("GET", endpoint)
            
            # Return MCP-formatted response with raw JSON
            import json
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(items_data, indent=2)
                    }
                ],
                "isError": False
            }
            
        except Exception as e:
            self.logger.error("Agents catalogue items retrieval failed", error=str(e))
            
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