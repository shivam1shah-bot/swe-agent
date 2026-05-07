"""
List Tasks MCP Tool.

Retrieves a list of tasks with optional filtering and pagination.
"""

from typing import Dict, Any, Optional
from ..base_tool import BaseMCPTool


class ListTasksTool(BaseMCPTool):
    """
    Tool for listing tasks with filtering and pagination.
    
    This tool retrieves a list of tasks with optional filtering by status,
    pagination support, and sorting capabilities. Use this when you need to
    view multiple tasks, monitor overall workflow progress, or find tasks
    matching specific criteria.
    """
    
    @property
    def name(self) -> str:
        """Tool name."""
        return "list_tasks"
    
    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Retrieve a list of tasks with optional filtering by status, pagination support, "
            "and sorting capabilities. Use this tool when you need to view multiple tasks, "
            "monitor overall workflow progress, or find tasks matching specific criteria. "
            "Returns paginated task list with summary information."
        )
    
    @property
    def domain(self) -> str:
        """Tool domain."""
        return "tasks"
    
    @property
    def input_schema(self) -> Dict[str, Any]:
        """Input schema for the tool."""
        return {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter by task status (optional)",
                    "enum": ["pending", "running", "completed", "failed", "cancelled"]
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of tasks to return (optional, default: 20)",
                    "minimum": 1,
                    "maximum": 1000,
                    "default": 20
                }
            },
            "required": []
        }
    
    @property
    def annotations(self) -> Dict[str, Any]:
        """Tool annotations."""
        return {
            "title": "List Tasks",
            "readOnlyHint": True,
            "openWorldHint": False,
            "domain": "tasks"
        }
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute task listing.
        
        Args:
            status: Optional status filter
            limit: Maximum number of tasks to return
        
        Returns:
            MCP-formatted task list
        """
        try:
            # Validate arguments
            validated_args = self.validate_arguments(**kwargs)
            
            # Extract parameters
            status = validated_args.get("status")
            limit = validated_args.get("limit", 20)
            
            self.logger.info("Listing tasks", status=status, limit=limit)
            
            # Build query parameters
            params = {"limit": limit}
            if status:
                params["status"] = status
            
            # Call the existing task listing API endpoint
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            endpoint = f"/api/v1/tasks?{query_string}"
            
            tasks_data = await self.call_api_endpoint("GET", endpoint)
            
            # Return MCP-formatted response with raw JSON
            import json
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(tasks_data, indent=2)
                    }
                ],
                "isError": False
            }
            
        except Exception as e:
            self.logger.error("Task listing failed", error=str(e))
            
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