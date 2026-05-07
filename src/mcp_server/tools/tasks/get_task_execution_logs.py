"""
Get Task Execution Logs MCP Tool.

Retrieves execution logs for a specific task.
"""

from typing import Dict, Any
from ..base_tool import BaseMCPTool


class GetTaskExecutionLogsTool(BaseMCPTool):
    """
    Tool for retrieving task execution logs and history.
    
    This tool retrieves detailed execution logs for a specific task including
    progress updates, error messages, and operational history. Use this when
    you need to debug task failures, monitor execution progress, or audit
    task operations for compliance or troubleshooting purposes.
    """
    
    @property
    def name(self) -> str:
        """Tool name."""
        return "get_task_execution_logs"
    
    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Retrieve detailed execution logs for a specific task including progress updates, "
            "error messages, and operational history. Use this tool when you need to debug "
            "task failures, monitor execution progress, or audit task operations for compliance "
            "or troubleshooting purposes. Returns chronological log entries with timestamps."
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
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of log entries to return (optional, default: 50)",
                    "minimum": 1,
                    "maximum": 1000,
                    "default": 50
                }
            },
            "required": ["task_id"]
        }
    
    @property
    def annotations(self) -> Dict[str, Any]:
        """Tool annotations."""
        return {
            "title": "Get Task Execution Logs",
            "readOnlyHint": True,
            "openWorldHint": False,
            "domain": "tasks"
        }
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute task execution logs retrieval.
        
        Args:
            task_id: Unique task identifier
            limit: Maximum number of log entries to return
        
        Returns:
            MCP-formatted task execution logs
        """
        try:
            # Validate arguments
            validated_args = self.validate_arguments(**kwargs)
            
            task_id = validated_args["task_id"]
            limit = validated_args.get("limit", 50)
            
            self.logger.info("Retrieving task execution logs", task_id=task_id, limit=limit)
            
            # Build query parameters  
            params = {"limit": limit}
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            endpoint = f"/api/v1/tasks/{task_id}/execution-logs?{query_string}"
            
            # Call the existing task logs API endpoint
            logs_data = await self.call_api_endpoint("GET", endpoint)
            
            # Return MCP-formatted response with raw JSON
            import json
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(logs_data, indent=2)
                    }
                ],
                "isError": False
            }
            
        except Exception as e:
            self.logger.error("Task execution logs retrieval failed", error=str(e))
            
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