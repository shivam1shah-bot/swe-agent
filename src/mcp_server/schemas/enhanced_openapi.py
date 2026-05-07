"""
Enhanced OpenAPI generation with MCP-focused semantic descriptions.

This module extends the standard FastAPI OpenAPI generation to include rich semantic
meaning and MCP tool capability descriptions, following the blog post guidance on
describing APIs in terms of capabilities rather than just contract structure.
"""

from typing import Dict, Any, Optional, List
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from src.providers.logger.provider import Logger


class EnhancedOpenAPIGenerator:
    """
    Generates enhanced OpenAPI specifications with MCP-focused semantic descriptions.
    
    This class extends the standard FastAPI OpenAPI generation to include:
    - Rich semantic descriptions for capabilities
    - MCP tool annotations using x-mcp extensions
    - JSON-LD linked data context for semantic meaning
    - Tool-oriented operation descriptions
    """
    
    def __init__(self, app: FastAPI):
        """
        Initialize the enhanced OpenAPI generator.
        
        Args:
            app: FastAPI application instance
        """
        self.logger = Logger("EnhancedOpenAPIGenerator")
        self.app = app
        
    def generate_enhanced_spec(self) -> Dict[str, Any]:
        """
        Generate enhanced OpenAPI specification with MCP semantic descriptions.
        
        Returns:
            Enhanced OpenAPI specification with MCP-focused descriptions
        """
        self.logger.info("Generating enhanced OpenAPI specification for MCP")
        
        # Get base OpenAPI spec from FastAPI
        openapi_spec = get_openapi(
            title="SWE Agent API",
            version="1.0.0",
            description="AI-powered software engineering automation platform",
            routes=self.app.routes,
        )
        
        # Enhance with MCP-focused semantic descriptions
        enhanced_spec = self._enhance_info_section(openapi_spec)
        enhanced_spec = self._add_linked_data_context(enhanced_spec)
        enhanced_spec = self._enhance_paths_with_mcp_descriptions(enhanced_spec)
        enhanced_spec = self._add_mcp_tool_annotations(enhanced_spec)
        enhanced_spec = self._enhance_schemas_with_semantics(enhanced_spec)
        
        self.logger.info("Enhanced OpenAPI specification generated successfully")
        return enhanced_spec
    
    def _enhance_info_section(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance the info section with rich capability descriptions.
        
        Args:
            spec: Base OpenAPI specification
            
        Returns:
            Specification with enhanced info section
        """
        spec["info"].update({
            "title": "SWE Agent API - AI-Powered Engineering Platform",
            "description": """
This API exposes comprehensive software engineering automation capabilities designed 
for AI agents and models. It provides tools for task management, health monitoring, 
agents catalogue execution, and administrative operations.

Key capabilities include:
- **Health Monitoring**: Real-time system health checks and metrics
- **Task Management**: Workflow tracking, execution, and progress monitoring  
- **Agents Catalogue**: Dynamic service discovery and execution
- **Administrative Operations**: Database migrations and GitHub integration

Ideal for AI agents performing software engineering tasks, workflow automation, 
system monitoring, and development operations. The API is designed with semantic 
richness to enable intelligent tool selection and contextual decision-making.
            """.strip(),
            "termsOfService": "https://swe-agent.com/terms",
            "contact": {
                "name": "SWE Agent Team",
                "url": "https://swe-agent.com/support",
                "email": "support@swe-agent.com"
            },
            "license": {
                "name": "MIT",
                "url": "https://opensource.org/licenses/MIT"
            }
        })
        
        # Add external documentation
        spec["externalDocs"] = {
            "description": "Complete documentation and usage examples for SWE Agent API capabilities",
            "url": "https://docs.swe-agent.com"
        }
        
        return spec
    
    def _add_linked_data_context(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add JSON-LD context for semantic meaning.
        
        Args:
            spec: OpenAPI specification
            
        Returns:
            Specification with JSON-LD context
        """
        spec["x-linkedData"] = {
            "@context": {
                "schema": "https://schema.org/",
                "hydra": "http://www.w3.org/ns/hydra/core#",
                "swe": "https://swe-agent.com/vocab#"
            },
            "@type": "schema:WebAPI",
            "@id": "https://api.swe-agent.com/v1",
            "schema:name": "SWE Agent API",
            "schema:description": "AI-powered software engineering automation platform",
            "schema:provider": {
                "@type": "schema:Organization",
                "schema:name": "SWE Agent",
                "schema:url": "https://swe-agent.com"
            },
            "schema:dateModified": "2025-01-15"
        }
        
        return spec
    
    def _enhance_paths_with_mcp_descriptions(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance path descriptions with MCP capability focus.
        
        Args:
            spec: OpenAPI specification
            
        Returns:
            Specification with enhanced path descriptions
        """
        path_enhancements = self._get_path_enhancements()
        
        for path, methods in spec.get("paths", {}).items():
            for method, operation in methods.items():
                if isinstance(operation, dict) and "operationId" in operation:
                    operation_id = operation["operationId"]
                    
                    if operation_id in path_enhancements:
                        enhancement = path_enhancements[operation_id]
                        operation.update({
                            "summary": enhancement["summary"],
                            "description": enhancement["description"],
                            "x-mcp": enhancement["mcp"]
                        })
        
        return spec
    
    def _get_path_enhancements(self) -> Dict[str, Dict[str, Any]]:
        """
        Get MCP-focused enhancements for each API operation.
        
        Returns:
            Dictionary mapping operation IDs to enhancements
        """
        return {
            # Health endpoints
            "get_health": {
                "summary": "Check comprehensive system health status",
                "description": """
Provides real-time assessment of overall system health including database connectivity,
service availability, and system metrics. Essential for AI agents monitoring system
state before executing operations or diagnosing issues. Returns structured health
data with status indicators and detailed component information.
                """.strip(),
                "mcp": {
                    "capability": "system_monitoring",
                    "use_cases": ["pre_operation_checks", "system_diagnostics", "health_monitoring"],
                    "preconditions": ["none"],
                    "output_semantics": "structured_health_status"
                }
            },

            # Task endpoints

            "get_task": {
                "summary": "Retrieve detailed information about a specific task",
                "description": """
Fetches complete task information including status, metadata, and execution details.
Essential for AI agents monitoring task progress, making workflow decisions, or
retrieving results from completed tasks.
                """.strip(),
                "mcp": {
                    "capability": "task_inspection",
                    "use_cases": ["progress_monitoring", "result_retrieval", "workflow_coordination"],
                    "preconditions": ["valid_task_id"],
                    "output_semantics": "complete_task_details"
                }
            },
            "list_tasks": {
                "summary": "Retrieve a list of tasks with optional filtering by status",
                "description": """
Lists tasks with optional status filtering and pagination. AI agents use this
for workflow overview, identifying pending work, or coordinating task execution
across multiple workflows and processes.
                """.strip(),
                "mcp": {
                    "capability": "task_discovery",
                    "use_cases": ["workflow_overview", "task_coordination", "workload_analysis"],
                    "preconditions": ["none"],
                    "output_semantics": "paginated_task_list"
                }
            },

            "get_task_execution_logs": {
                "summary": "Retrieve detailed execution logs for a specific task",
                "description": """
Fetches execution logs and diagnostic information for task debugging and analysis.
AI agents use this for error diagnosis, performance analysis, or understanding
task execution patterns for optimization.
                """.strip(),
                "mcp": {
                    "capability": "execution_analysis",
                    "use_cases": ["error_diagnosis", "performance_analysis", "execution_debugging"],
                    "preconditions": ["valid_task_id"],
                    "output_semantics": "structured_execution_logs"
                }
            },
            # Agents catalogue endpoints  
            "list_agents_catalogue_services": {
                "summary": "List all dynamically registered services in the agents catalogue",
                "description": """
Discovers available agents catalogue services for dynamic service execution.
AI agents use this for capability discovery, service selection, and understanding
available automation tools in the system.
                """.strip(),
                "mcp": {
                    "capability": "service_discovery",
                    "use_cases": ["capability_discovery", "service_selection", "automation_planning"],
                    "preconditions": ["none"],
                    "output_semantics": "service_registry_list"
                }
            },


        }
    
    def _add_mcp_tool_annotations(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add MCP-specific tool annotations to operations.
        
        Args:
            spec: OpenAPI specification
            
        Returns:
            Specification with MCP tool annotations
        """
        for path, methods in spec.get("paths", {}).items():
            for method, operation in methods.items():
                if isinstance(operation, dict) and "operationId" in operation:
                    # Add MCP tool metadata
                    if "x-mcp" not in operation:
                        operation["x-mcp"] = {}
                    
                    operation["x-mcp"].update({
                        "tool_name": operation["operationId"],
                        "transport": "streamable_http",
                        "async_capable": method.lower() == "post" and "migrations" in path,
                        "rate_limited": True,
                        "auth_required": "admin" in path
                    })
        
        return spec
    
    def _enhance_schemas_with_semantics(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance schema definitions with semantic annotations.
        
        Args:
            spec: OpenAPI specification
            
        Returns:
            Specification with enhanced schemas
        """
        if "components" in spec and "schemas" in spec["components"]:
            for schema_name, schema_def in spec["components"]["schemas"].items():
                if isinstance(schema_def, dict):
                    # Add semantic context based on schema name
                    schema_def["x-semantic"] = self._get_schema_semantics(schema_name)
        
        return spec
    
    def _get_schema_semantics(self, schema_name: str) -> Dict[str, Any]:
        """
        Get semantic annotations for a schema.
        
        Args:
            schema_name: Name of the schema
            
        Returns:
            Semantic annotations for the schema
        """
        semantic_mappings = {
            "Task": {
                "@type": "schema:Action",
                "domain": "workflow_management",
                "purpose": "Represents a unit of work in automated workflows"
            },
            "HealthStatus": {
                "@type": "schema:HealthCheckResult", 
                "domain": "system_monitoring",
                "purpose": "Represents system health and operational status"
            },
            "AgentsCatalogueItem": {
                "@type": "swe:AutomationCapability",
                "domain": "service_discovery",
                "purpose": "Represents available automation capabilities"
            }
        }
        
        return semantic_mappings.get(schema_name, {
            "@type": "schema:Thing",
            "domain": "general",
            "purpose": f"Schema definition for {schema_name}"
        }) 