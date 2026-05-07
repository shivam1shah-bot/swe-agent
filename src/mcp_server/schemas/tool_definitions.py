"""
MCP tool definition models and converters.

This module provides utilities for converting API operations into MCP tool definitions,
including schema transformation, annotation extraction, and tool metadata generation.
"""

from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field
from dataclasses import dataclass
from enum import Enum

from .mcp_protocol import MCPTool, MCPToolInputSchema, MCPToolParameter, MCPToolAnnotations


class ToolDomain(str, Enum):
    """MCP tool domains for organization."""
    HEALTH = "health"
    TASKS = "tasks"
    AGENTS_CATALOGUE = "agents_catalogue"
    ADMIN = "admin"


class ToolCapability(str, Enum):
    """MCP tool capabilities."""
    SYSTEM_MONITORING = "system_monitoring"
    DATABASE_MONITORING = "database_monitoring"
    SERVICE_MONITORING = "service_monitoring"
    PERFORMANCE_MONITORING = "performance_monitoring"
    WORKFLOW_ORCHESTRATION = "workflow_orchestration"
    TASK_INSPECTION = "task_inspection"
    TASK_DISCOVERY = "task_discovery"
    WORKFLOW_STATE_MANAGEMENT = "workflow_state_management"
    EXECUTION_ANALYSIS = "execution_analysis"
    SERVICE_DISCOVERY = "service_discovery"
    SERVICE_EXECUTION = "service_execution"
    DATABASE_ADMINISTRATION = "database_administration"


@dataclass
class ToolMetadata:
    """Metadata for MCP tool definition."""
    name: str
    description: str
    domain: ToolDomain
    capability: ToolCapability
    use_cases: List[str]
    preconditions: List[str]
    output_semantics: str
    is_streaming: bool = False
    is_async: bool = False
    requires_auth: bool = False
    rate_limited: bool = True


class MCPToolDefinitions:
    """
    Collection of MCP tool definitions and utilities for tool management.
    
    This class provides methods for creating, converting, and managing MCP tool
    definitions from API operations and custom tool specifications.
    """
    
    def __init__(self):
        """Initialize tool definitions manager."""
        self.tool_metadata = self._get_tool_metadata()
    
    def _get_tool_metadata(self) -> Dict[str, ToolMetadata]:
        """
        Get predefined metadata for all MCP tools.
        
        Returns:
            Dictionary mapping tool names to metadata
        """
        return {
            # Health domain tools
            "overall_health": ToolMetadata(
                name="overall_health",
                description="Check comprehensive system health status including database connectivity, service availability, and system metrics. Essential for AI agents monitoring system state before executing operations or diagnosing issues.",
                domain=ToolDomain.HEALTH,
                capability=ToolCapability.SYSTEM_MONITORING,
                use_cases=["pre_operation_checks", "system_diagnostics", "health_monitoring"],
                preconditions=["none"],
                output_semantics="structured_health_status"
            ),

            
            # Task domain tools

            "get_task": ToolMetadata(
                name="get_task",
                description="Retrieve detailed information about a specific task including status, metadata, and execution details. Essential for AI agents monitoring task progress.",
                domain=ToolDomain.TASKS,
                capability=ToolCapability.TASK_INSPECTION,
                use_cases=["progress_monitoring", "result_retrieval", "workflow_coordination"],
                preconditions=["valid_task_id"],
                output_semantics="complete_task_details"
            ),
            "list_tasks": ToolMetadata(
                name="list_tasks",
                description="Retrieve a list of tasks with optional filtering by status. AI agents use this for workflow overview and task coordination.",
                domain=ToolDomain.TASKS,
                capability=ToolCapability.TASK_DISCOVERY,
                use_cases=["workflow_overview", "task_coordination", "workload_analysis"],
                preconditions=["none"],
                output_semantics="paginated_task_list"
            ),

            "get_task_execution_logs": ToolMetadata(
                name="get_task_execution_logs",
                description="Retrieve detailed execution logs for a specific task for debugging and analysis. AI agents use this for error diagnosis and performance analysis.",
                domain=ToolDomain.TASKS,
                capability=ToolCapability.EXECUTION_ANALYSIS,
                use_cases=["error_diagnosis", "performance_analysis", "execution_debugging"],
                preconditions=["valid_task_id"],
                output_semantics="structured_execution_logs"
            ),
            
            # Agents catalogue domain tools

            "list_agents_catalogue_services": ToolMetadata(
                name="list_agents_catalogue_services",
                description="List all dynamically registered services in the agents catalogue for capability discovery and service selection.",
                domain=ToolDomain.AGENTS_CATALOGUE,
                capability=ToolCapability.SERVICE_DISCOVERY,
                use_cases=["capability_discovery", "service_selection", "automation_planning"],
                preconditions=["none"],
                output_semantics="service_registry_list"
            ),
            "get_agents_catalogue_items": ToolMetadata(
                name="get_agents_catalogue_items",
                description="Retrieve agents catalogue items with pagination and filtering by type, lifecycle, and search terms.",
                domain=ToolDomain.AGENTS_CATALOGUE,
                capability=ToolCapability.SERVICE_DISCOVERY,
                use_cases=["capability_discovery", "service_browsing", "automation_planning"],
                preconditions=["none"],
                output_semantics="paginated_catalogue_items"
            ),
            "get_agents_catalogue_config": ToolMetadata(
                name="get_agents_catalogue_config",
                description="Retrieve agents catalogue configuration and settings for understanding system capabilities and constraints.",
                domain=ToolDomain.AGENTS_CATALOGUE,
                capability=ToolCapability.SERVICE_DISCOVERY,
                use_cases=["configuration_discovery", "capability_assessment", "system_understanding"],
                preconditions=["none"],
                output_semantics="catalogue_configuration"
            ),

        }
    
    def get_tool_definition(self, tool_name: str) -> Optional[ToolMetadata]:
        """
        Get tool metadata by name.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Tool metadata if found, None otherwise
        """
        return self.tool_metadata.get(tool_name)
    
    def list_tools_by_domain(self, domain: ToolDomain) -> List[ToolMetadata]:
        """
        List all tools in a specific domain.
        
        Args:
            domain: Tool domain to filter by
            
        Returns:
            List of tool metadata for the domain
        """
        return [
            metadata for metadata in self.tool_metadata.values()
            if metadata.domain == domain
        ]
    
    def list_tools_by_capability(self, capability: ToolCapability) -> List[ToolMetadata]:
        """
        List all tools with a specific capability.
        
        Args:
            capability: Tool capability to filter by
            
        Returns:
            List of tool metadata with the capability
        """
        return [
            metadata for metadata in self.tool_metadata.values()
            if metadata.capability == capability
        ]
    
    def convert_to_mcp_tool(self, tool_name: str, input_schema: Dict[str, Any]) -> Optional[MCPTool]:
        """
        Convert tool metadata and input schema to MCP tool definition.
        
        Args:
            tool_name: Name of the tool
            input_schema: JSON schema for tool input
            
        Returns:
            MCP tool definition if metadata found, None otherwise
        """
        metadata = self.get_tool_definition(tool_name)
        if not metadata:
            return None
        
        # Convert input schema to MCP format
        mcp_input_schema = self._convert_input_schema(input_schema)
        
        # Create annotations
        annotations = MCPToolAnnotations(
            title=metadata.name.replace("_", " ").title(),
            readOnlyHint=metadata.capability in [
                ToolCapability.SYSTEM_MONITORING,
                ToolCapability.DATABASE_MONITORING,
                ToolCapability.SERVICE_MONITORING,
                ToolCapability.PERFORMANCE_MONITORING,
                ToolCapability.TASK_INSPECTION,
                ToolCapability.TASK_DISCOVERY,
                ToolCapability.SERVICE_DISCOVERY,
                ToolCapability.EXECUTION_ANALYSIS
            ],
            openWorldHint=False,
            domain=metadata.domain.value,
            capability=metadata.capability.value,
            use_cases=metadata.use_cases,
            preconditions=metadata.preconditions
        )
        
        return MCPTool(
            name=metadata.name,
            description=metadata.description,
            inputSchema=mcp_input_schema,
            annotations=annotations
        )
    
    def _convert_input_schema(self, schema: Dict[str, Any]) -> MCPToolInputSchema:
        """
        Convert JSON schema to MCP tool input schema.
        
        Args:
            schema: JSON schema definition
            
        Returns:
            MCP tool input schema
        """
        properties = {}
        
        for prop_name, prop_def in schema.get("properties", {}).items():
            properties[prop_name] = MCPToolParameter(
                type=prop_def.get("type", "string"),
                description=prop_def.get("description"),
                enum=prop_def.get("enum"),
                default=prop_def.get("default"),
                minimum=prop_def.get("minimum"),
                maximum=prop_def.get("maximum"),
                pattern=prop_def.get("pattern"),
                minLength=prop_def.get("minLength"),
                maxLength=prop_def.get("maxLength")
            )
        
        return MCPToolInputSchema(
            type="object",
            properties=properties,
            required=schema.get("required", []),
            additionalProperties=schema.get("additionalProperties", False)
        )
    
    def get_tool_summary(self) -> Dict[str, Any]:
        """
        Get summary of all available tools organized by domain.
        
        Returns:
            Dictionary with tool summary statistics
        """
        summary = {
            "total_tools": len(self.tool_metadata),
            "domains": {},
            "capabilities": {},
            "streaming_tools": [],
            "auth_required_tools": []
        }
        
        for metadata in self.tool_metadata.values():
            # Count by domain
            domain = metadata.domain.value
            if domain not in summary["domains"]:
                summary["domains"][domain] = 0
            summary["domains"][domain] += 1
            
            # Count by capability
            capability = metadata.capability.value
            if capability not in summary["capabilities"]:
                summary["capabilities"][capability] = 0
            summary["capabilities"][capability] += 1
            
            # Track special tool types
            if metadata.is_streaming:
                summary["streaming_tools"].append(metadata.name)
            if metadata.requires_auth:
                summary["auth_required_tools"].append(metadata.name)
        
        return summary
    
    def validate_tool_arguments(self, tool_name: str, arguments: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate tool arguments against tool definition.
        
        Args:
            tool_name: Name of the tool
            arguments: Arguments to validate
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        metadata = self.get_tool_definition(tool_name)
        if not metadata:
            return False, [f"Unknown tool: {tool_name}"]
        
        errors = []
        
        # Basic validation - can be extended with more sophisticated checks
        if not isinstance(arguments, dict):
            errors.append("Arguments must be a dictionary")
        
        return len(errors) == 0, errors 