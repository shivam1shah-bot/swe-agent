"""
Get Task MCP Tool.

Retrieves detailed information about a specific task.
"""

from typing import Dict, Any
from ..base_tool import BaseMCPTool


class GetTaskTool(BaseMCPTool):
    """
    Tool for retrieving detailed task information.
    
    This tool retrieves comprehensive information about a specific task including
    its current status, execution progress, metadata, and history. Use this when
    you need to check the status of a running or completed task, or to get
    detailed information for debugging or monitoring purposes.
    """
    
    @property
    def name(self) -> str:
        """Tool name."""
        return "get_task"
    
    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Retrieve detailed information about a specific task including current status, "
            "execution progress, metadata, and history. Use this tool when you need to check "
            "the status of a running or completed task, or to get detailed information for "
            "debugging or monitoring purposes. Returns comprehensive task details."
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
                "task_id": {
                    "type": "string",
                    "description": "Unique task identifier (required)",
                    "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
                }
            },
            "required": ["task_id"]
        }
    
    @property
    def annotations(self) -> Dict[str, Any]:
        """Tool annotations."""
        return {
            "title": "Get Task Details",
            "readOnlyHint": True,
            "openWorldHint": False,
            "domain": "tasks"
        }
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute task retrieval.
        
        Args:
            task_id: Unique task identifier
        
        Returns:
            MCP-formatted detailed task information
        """
        try:
            # Validate arguments
            validated_args = self.validate_arguments(**kwargs)
            
            task_id = validated_args["task_id"]
            
            self.logger.info("Retrieving task details", task_id=task_id)
            
            # Call the existing task retrieval API endpoint
            task_data = await self.call_api_endpoint("GET", f"/api/v1/tasks/{task_id}")
            
            # Return MCP-formatted response with raw JSON
            import json
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(task_data, indent=2)
                    }
                ],
                "isError": False
            }
            
        except Exception as e:
            self.logger.error("Task retrieval failed", error=str(e))
            
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