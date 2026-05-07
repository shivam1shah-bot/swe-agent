"""
Overall Health MCP Tool.

Provides comprehensive system health status including database, services, and configuration.
"""

from typing import Dict, Any
from ..base_tool import BaseMCPTool


class OverallHealthTool(BaseMCPTool):
    """
    Tool for checking overall system health status.
    
    This tool provides a comprehensive health check of all system components
    including database connectivity, service status, and configuration validation.
    Use this when you need to assess overall system readiness or diagnose
    potential issues across all components.
    """
    
    @property
    def name(self) -> str:
        """Tool name."""
        return "overall_health"
    
    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Check comprehensive system health status including database, services, "
            "and configuration. Use this tool when you need to assess overall system "
            "readiness or diagnose potential issues across all components. Returns "
            "detailed health information with status indicators for each subsystem."
        )
    
    @property
    def domain(self) -> str:
        """Tool domain."""
        return "health"
    
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
            "title": "Overall System Health Check",
            "readOnlyHint": True,
            "openWorldHint": False,
            "domain": "health",
            "use_cases": ["pre_operation_checks", "system_diagnostics", "health_monitoring"]
        }
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute the overall health check.
        
        Returns:
            MCP-formatted tool result with health status information
        """
        try:
            # Validate arguments (none required for this tool)
            validated_args = self.validate_arguments(**kwargs)
            
            self.logger.info("Executing overall health check")
            
            # Call the existing health API endpoint
            health_data = await self.call_api_endpoint("GET", "/api/v1/health")
            
            # Return MCP-formatted response with raw JSON
            import json
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(health_data, indent=2)
                    }
                ],
                "isError": False
            }
            
        except Exception as e:
            self.logger.error("Overall health check failed", error=str(e))
            
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