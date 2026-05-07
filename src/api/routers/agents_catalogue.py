"""
Agents Catalogue router for FastAPI.

This module provides REST API endpoints for agents catalogue functionality.
"""

import time
import asyncio
import logging
import os
import uuid
import json
import base64
import subprocess
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field, field_validator
from pathlib import Path

from src.services import AgentsCatalogueService
from src.services.agents_catalogue import get_service_for_usecase, service_registry

from src.services.exceptions import ValidationError, BusinessLogicError
from src.providers.logger import Logger
from src.providers.auth import require_role
from src.providers.config_loader import get_config
from ..dependencies import get_agents_catalogue_service, get_logger
from src.services.agents_catalogue import validator_discovery

# Initialize router
router = APIRouter()

# Configuration
EXECUTION_TIMEOUT = 1800  # 30 minutes
MAX_RETRIES = 2
RETRY_DELAY = 30  # seconds

# Enhanced Input Models
class AgentsCatalogueExecutionRequest(BaseModel):
    """Generic request model for agents catalogue execution."""

    parameters: Dict[str, Any] = Field(
        ...,
        description="Parameters specific to the use case"
    )

    timeout: Optional[int] = Field(
        EXECUTION_TIMEOUT,
        description="Execution timeout in seconds (max 1800)",
        ge=60,
        le=1800
    )

    priority: Optional[str] = Field(
        "normal",
        description="Task priority level"
    )

    tags: Optional[List[str]] = Field(
        [],
        description="Optional tags for task categorization"
    )

    @field_validator('priority')
    def validate_priority(cls, v):
        if v not in ['low', 'normal', 'high', 'urgent']:
            raise ValueError('Priority must be one of: low, normal, high, urgent')
        return v


class AgentsCatalogueExecutionResponse(BaseModel):
    """Response model for agents catalogue execution."""

    status: str = Field(..., description="Execution status")
    message: str = Field(..., description="Human-readable message")
    task_id: Optional[str] = Field(None, description="Task identifier (if queued asynchronously)")
    execution_time: Optional[float] = Field(None, description="Execution time in seconds")
    files: Optional[List[Dict[str, str]]] = Field(None, description="Generated files")
    pr_url: Optional[str] = Field(None, description="Pull request URL if applicable")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional execution metadata")
    agent_result: Optional[Dict[str, Any]] = Field(None, description="Raw agent execution result")


class AgentsCatalogueErrorResponse(BaseModel):
    """Error response model for agents catalogue."""

    error: str = Field(..., description="Error message")
    error_type: str = Field(..., description="Type of error")
    error_code: str = Field(..., description="Machine-readable error code")
    task_id: Optional[str] = Field(None, description="Task ID if available")
    retry_after: Optional[int] = Field(None, description="Retry delay in seconds")
    suggestions: Optional[List[str]] = Field(None, description="Suggested actions")


# Validation Functions
def validate_service_parameters(service_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate service parameters using the validator discovery system.

    Args:
        service_name: Name of the service
        parameters: Parameters to validate

    Returns:
        Validated parameters

    Raises:
        ValueError: If validation fails
    """
    try:
        return validator_discovery.validate_parameters(service_name, parameters)
    except Exception as e:
        raise ValueError(f"Parameter validation failed: {str(e)}")


def validate_usecase_name(usecase_name: str) -> str:
    """
    Validate and sanitize use case name.

    Args:
        usecase_name: Use case name to validate

    Returns:
        Validated use case name

    Raises:
        ValueError: If use case name is invalid
    """
    import re

    if not usecase_name:
        raise ValueError("Use case name cannot be empty")

    # Convert to lowercase and replace underscores with hyphens
    normalized = usecase_name.lower().replace('_', '-')

    # Validate forma
    if not re.match(r'^[a-z0-9-]+$', normalized):
        raise ValueError("Use case name must contain only lowercase letters, numbers, and hyphens")

    if normalized.startswith('-') or normalized.endswith('-'):
        raise ValueError("Use case name cannot start or end with hyphen")

    return normalized


def validate_item_type(item_type: str) -> str:
    """
    Validate and sanitize item type.

    Args:
        item_type: Item type to validate

    Returns:
        Validated item type

    Raises:
        ValueError: If item type is invalid
    """
    if not item_type:
        raise ValueError("Item type cannot be empty")

    valid_types = ['micro-frontend', 'workflow', 'api', 'tool']

    normalized = item_type.lower()
    if normalized not in valid_types:
        raise ValueError(f"Invalid item type: {normalized}. Valid types: {valid_types}")

    return normalized


def sanitize_parameter_value(value: Any) -> Any:
    """
    Sanitize parameter values for security.

    Args:
        value: Value to sanitize

    Returns:
        Sanitized value
    """
    if isinstance(value, str):
        # Remove potentially dangerous characters
        import re
        # Basic sanitization - remove control characters and script tags
        value = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', value)
        value = re.sub(r'<script[^>]*>.*?</script>', '', value, flags=re.IGNORECASE | re.DOTALL)

    return value


async def execute_service_with_timeout(service, parameters: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    """
    Execute service with timeout handling.

    Args:
        service: Service instance to execute
        parameters: Parameters for execution
        timeout: Timeout in seconds

    Returns:
        Service execution resul

    Raises:
        asyncio.TimeoutError: If execution times ou
        Exception: If service execution fails
    """
    try:
        # API router always uses synchronous execute method in thread pool
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(service.execute, parameters)
            return await asyncio.wait_for(
                asyncio.wrap_future(future),
                timeout=timeout
            )
    except asyncio.TimeoutError:
        raise
    except Exception as e:
        raise Exception(f"Service execution failed: {str(e)}")


def format_success_response(result: Dict[str, Any], task_id: Optional[str], usecase_name: str) -> AgentsCatalogueExecutionResponse:
    """
    Format successful execution result into standardized response.

    Args:
        result: Raw service execution resul
        task_id: Task identifier (None if no task created)
        usecase_name: Name of the executed use case

    Returns:
        Formatted response
    """
    # Extract common fields with defaults
    status = result.get("status", "completed")
    message = result.get("message", f"Successfully executed {usecase_name}")
    execution_time = result.get("execution_time")
    files = result.get("files", [])
    pr_url = result.get("pr_url")
    metadata = result.get("metadata", {})
    agent_result = result.get("agent_result")

    # Ensure files is a list of dictionaries
    if files and not isinstance(files, list):
        files = []

    # Build response data
    response_data = {
        "status": status,
        "message": message,
        "task_id": task_id,
        "execution_time": execution_time,
        "files": files,
        "pr_url": pr_url,
        "metadata": metadata,
        "agent_result": agent_result
    }

    return AgentsCatalogueExecutionResponse(**response_data)


# Main Execution Endpoint
@router.post("/{item_type}/{usecase_name}",
             response_model=AgentsCatalogueExecutionResponse,
             responses={
                 400: {"model": AgentsCatalogueErrorResponse, "description": "Validation error"},
                 404: {"model": AgentsCatalogueErrorResponse, "description": "Service not found"},
                 408: {"model": AgentsCatalogueErrorResponse, "description": "Request timeout"},
                 500: {"model": AgentsCatalogueErrorResponse, "description": "Internal server error"}
             })
@require_role(["dashboard", "admin", "splitz"])
async def execute_agents_catalogue_agent(
    request: Request,
    item_type: str,
    usecase_name: str,
    execution_request: AgentsCatalogueExecutionRequest,
    background_tasks: BackgroundTasks,
    logger: Logger = Depends(get_logger)
):
    """
    Dynamic endpoint for executing agents catalogue functionality.

    This endpoint provides a unified interface for all agents catalogue agents including:
    - E2E Onboarding (workflow/e2e-onboarding)
    - Spinnaker V3 Pipeline Generator
    - Auto Documentation Generator
    - Service Onboarding Assistant
    - And other agents catalogue services

    Args:
        item_type: Type of agents catalogue item (e.g., 'micro-frontend', 'workflow')
        usecase_name: Name of the specific use case (e.g., 'spinnaker-v3-pipeline-generator')
        request: Request parameters specific to the use case
        background_tasks: FastAPI background tasks for cleanup

    Returns:
        AgentsCatalogueExecutionResponse with execution results

    Raises:
        HTTPException: For various error conditions with appropriate status codes
    """
    execution_start = time.time()

    try:
        logger.info("Starting agents catalogue agent execution",
                   item_type=item_type,
                   usecase_name=usecase_name,
                   parameters_count=len(execution_request.parameters))

        # Validate and sanitize inputs
        validated_item_type = validate_item_type(item_type)
        validated_usecase_name = validate_usecase_name(usecase_name)

        # Autonomous agent variants have moved to /api/v1/agents/*
        _MOVED_SERVICES = {
            "autonomous-agent": "/api/v1/agents/run",
            "autonomous-agent-clean-slate": "/api/v1/agents/run",
            "autonomous-agent-batch": "/api/v1/agents/batch",
            "autonomous-agent-multi-repo": "/api/v1/agents/multi-repo",
        }
        if validated_usecase_name in _MOVED_SERVICES:
            new_url = _MOVED_SERVICES[validated_usecase_name]
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail={
                    "error": f"'{validated_usecase_name}' has moved. Use {new_url} instead.",
                    "error_code": "ENDPOINT_MOVED",
                    "new_endpoint": new_url,
                }
            )

        # Sanitize parameters
        sanitized_parameters = {
            key: sanitize_parameter_value(value)
            for key, value in execution_request.parameters.items()
        }

        # Validate service-specific parameters
        try:
            validated_parameters = validate_service_parameters(validated_usecase_name, sanitized_parameters)
        except ValueError as e:
            logger.warning("Parameter validation failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": str(e),
                    "error_type": "validation_error",
                    "error_code": "INVALID_PARAMETERS"
                }
            )

        # Get service instance
        service = get_service_for_usecase(validated_usecase_name)

        if not service:
            logger.warning("Service not found", usecase_name=validated_usecase_name)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": f"Service '{validated_usecase_name}' not found",
                    "error_type": "service_not_found",
                    "error_code": "SERVICE_NOT_REGISTERED",
                    "suggestions": [
                        "Check the usecase name spelling",
                        "Verify the service is registered",
                        "See /services endpoint for available services"
                    ]
                }
            )

        # Execute service directly
        logger.info("Executing service directly",
                   usecase_name=validated_usecase_name)

        result = await execute_service_with_timeout(
            service,
            validated_parameters,
            execution_request.timeout
        )

        execution_time = time.time() - execution_start

        # Extract task_id from service result if available
        task_id = result.get("task_id") if isinstance(result, dict) else None

        response = format_success_response(result, task_id, validated_usecase_name)
        response.execution_time = execution_time
        return response

    except HTTPException:
        # Re-raise HTTP exceptions
        raise

    except Exception as e:
        # Handle any unexpected errors
        execution_time = time.time() - execution_start

        logger.exception("Unhandled error in execute_agents_catalogue_agent", error=str(e))

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": f"Internal server error: {str(e)}",
                "error_type": "internal_error",
                "error_code": "INTERNAL_SERVER_ERROR",
                "execution_time": execution_time,
            }
        )
    finally:
        # No cleanup required here.
        pass


# Service Discovery and Management Endpoints
@router.get("/services",
           summary="List Available Services",
           description="Get a list of all registered agents catalogue services with their capabilities")
@require_role(["dashboard", "admin", "mcp_read_user"])
async def list_agents_catalogue_services(
    request: Request,
    logger: Logger = Depends(get_logger)
):
    """
    List all dynamically registered services in the agents catalogue.

    Returns comprehensive information about each service including:
    - Service name and description
    - Capabilities and supported operations
    - Current health status
    - Performance metrics
    - API documentation links
    """
    try:
        # Get all services from registry
        services_info = service_registry.get_all_services_info()

        # Format response
        services_list = []
        for service_name, info in services_info.items():
            service_data = {
                "name": service_name,
                "description": info.get("description", "No description available"),
                "capabilities": info.get("capabilities", []),
                "version": info.get("version", "unknown"),
                "health_status": info.get("health_status", "unknown"),
                "metrics": {
                    "total_executions": info.get("metrics", {}).get("total_executions", 0),
                    "success_rate": (
                        (info.get("metrics", {}).get("successful_executions", 0) /
                         max(info.get("metrics", {}).get("total_executions", 1), 1)) * 100
                    ),
                    "average_execution_time": info.get("metrics", {}).get("average_execution_time", 0.0)
                },
                "endpoints": {
                    "execute": f"/api/v1/agents-catalogue/micro-frontend/{service_name}",
                    "health": f"/api/v1/agents-catalogue/services/{service_name}/health"
                }
            }
            services_list.append(service_data)

        response = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_services": len(services_list),
            "services": services_list,
            "registry_health": service_registry.get_registry_health(),
            "documentation": "/docs#/agents-catalogue"
        }

        logger.info("Listed agents catalogue services", total_services=len(services_list))
        return response

    except Exception as e:
        logger.error("Error listing services", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve service list"
        )


@router.get("/health",
           summary="Health Check",
           description="Check the health of the agents catalogue system")
@require_role(["dashboard", "admin"])
async def agents_catalogue_health_check(
    request: Request,
    logger: Logger = Depends(get_logger)
):
    """
    Comprehensive health check for the agents catalogue system.

    Returns:
        Detailed health status including service registry, individual services,
        and overall system metrics.
    """
    try:
        # Get registry health
        registry_health = service_registry.get_registry_health()

        # Get system metrics
        metrics = service_registry.get_registry_metrics()

        # Determine overall health
        overall_status = "healthy"
        if registry_health.get("unhealthy_services", 0) > 0:
            overall_status = "unhealthy"
        elif registry_health.get("degraded_services", 0) > 0:
            overall_status = "degraded"

        health_response = {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "system": {
                "agents_catalogue_api": "healthy",
                "service_registry": registry_health.get("status", "unknown"),
                "total_services": registry_health.get("total_services", 0)
            },
            "services": registry_health.get("service_details", {}),
            "metrics": {
                "total_executions": metrics.get("overall", {}).get("total_executions", 0),
                "success_rate": (
                    100 - metrics.get("overall", {}).get("overall_error_rate", 0)
                ),
                "average_response_time": metrics.get("overall", {}).get("overall_avg_execution_time", 0.0)
            },
            "uptime": "N/A"  # Would be calculated from service start time
        }

        logger.info("Agents catalogue health check completed", status=overall_status)
        return health_response

    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


# Agents Catalogue CRUD Models
class AgentsCatalogueItemCreate(BaseModel):
    """Model for creating agents catalogue items."""
    name: str = Field(..., description="Item name")
    description: str = Field(..., description="Item description")
    type: str = Field(..., description="Item type")
    lifecycle: str = Field(..., description="Item lifecycle")
    owners: List[str] = Field(..., description="List of owner emails")
    tags: List[str] = Field(default=[], description="List of tags")

class AgentsCatalogueItemUpdate(BaseModel):
    """Model for updating agents catalogue items."""
    name: Optional[str] = Field(None, description="Item name")
    description: Optional[str] = Field(None, description="Item description")
    type: Optional[str] = Field(None, description="Item type")
    lifecycle: Optional[str] = Field(None, description="Item lifecycle")
    owners: Optional[List[str]] = Field(None, description="List of owner emails")
    tags: Optional[List[str]] = Field(None, description="List of tags")

class AgentsCatalogueItem(BaseModel):
    """Model for agents catalogue item response."""
    id: str
    name: str
    description: str
    type: str
    type_display: str
    lifecycle: str
    owners: List[str]
    tags: List[str]
    created_at: int
    updated_at: int

class AgentsCataloguePagination(BaseModel):
    """Pagination model."""
    page: int
    per_page: int
    total_pages: int
    total_items: int
    has_next: bool
    has_prev: bool

class AgentsCatalogueResponse(BaseModel):
    """Response model for agents catalogue items list."""
    items: List[AgentsCatalogueItem]
    pagination: AgentsCataloguePagination
    filters: Dict[str, Optional[str]] = {}

class AgentsCatalogueConfig(BaseModel):
    """Configuration model for agents catalogue."""
    available_types: List[Dict[str, str]]
    available_lifecycles: List[str]
    available_tags: List[str]
    default_owner: str

@router.get("/metrics",
           summary="System Metrics",
           description="Get usage metrics and performance statistics")
async def get_agents_catalogue_metrics(logger: Logger = Depends(get_logger)):
    """
    Get metrics and statistics for the agents catalogue.

    Returns:
        Usage statistics and performance metrics
    """
    try:
        # This would typically come from a metrics store
        # For now, return basic information

        registered_services = service_registry.list_services()

        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "total_registered": len(registered_services),
                "active_services": registered_services
            },
            "usage": {
                "total_executions": "N/A",  # Would track in real implementation
                "successful_executions": "N/A",
                "failed_executions": "N/A",
                "average_execution_time": "N/A"
            },
            "performance": {
                "avg_response_time": "N/A",
                "p95_response_time": "N/A",
                "error_rate": "N/A"
            }
        }

        logger.info("Retrieved agents catalogue metrics")
        return metrics

    except Exception as e:
        logger.error("Error retrieving metrics", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to retrieve system metrics",
                "error_type": "metrics_error",
                "error_code": "METRICS_ACCESS_FAILED"
            }
        )

# Workflow Diagram Endpoint
@router.get("/workflow-diagram/{service_type}",
           summary="Get Workflow Diagram",
           description="Get Mermaid diagram syntax for a specific agents catalogue workflow")
@require_role(["dashboard", "admin", "mcp_read_user"])
async def get_workflow_diagram(
    request: Request,
    service_type: str,
    logger: Logger = Depends(get_logger)
):
    """
    Get the LangGraph workflow diagram for a specific agents catalogue service.
    
    Args:
        service_type: Type of service (e.g., 'gateway-integrations-common')
        
    Returns:
        JSON response with Mermaid diagram syntax
        
    Raises:
        HTTPException: For various error conditions
    """
    try:
        logger.info(f"Fetching workflow diagram for service type: {service_type}")
        
        # List of supported service types
        supported_services = ["gateway-integrations-common"]
        
        if service_type not in supported_services:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": f"Workflow diagram not available for service type: {service_type}",
                    "error_type": "service_not_found",
                    "error_code": "WORKFLOW_DIAGRAM_NOT_FOUND",
                    "supported_services": supported_services
                }
            )
        
        # Get the service instance
        try:
            service_instance = get_service_for_usecase(service_type)
            if not service_instance:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": f"Service implementation not found for: {service_type}",
                        "error_type": "service_implementation_not_found",
                        "error_code": "SERVICE_IMPLEMENTATION_NOT_FOUND"
                    }
                )
            
            # Check if the service has workflow diagram support
            if not hasattr(service_instance, 'get_workflow_diagram'):
                raise HTTPException(
                    status_code=status.HTTP_501_NOT_IMPLEMENTED,
                    detail={
                        "error": f"Workflow diagram not implemented for service: {service_type}",
                        "error_type": "feature_not_implemented",
                        "error_code": "WORKFLOW_DIAGRAM_NOT_IMPLEMENTED"
                    }
                )
            
            # Generate the diagram
            diagram_syntax = service_instance.get_workflow_diagram()
            
            logger.info(f"Successfully generated workflow diagram for {service_type}")
            
            return {
                "success": True,
                "service_type": service_type,
                "diagram_syntax": diagram_syntax,
                "diagram_type": "mermaid",
                "generated_at": time.time()
            }
            
        except Exception as service_error:
            logger.error(f"Error getting service for {service_type}: {str(service_error)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": f"Failed to generate workflow diagram for {service_type}",
                    "error_type": "diagram_generation_error",
                    "error_code": "WORKFLOW_DIAGRAM_GENERATION_FAILED",
                    "details": str(service_error)
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in workflow diagram endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error while fetching workflow diagram",
                "error_type": "internal_error",
                "error_code": "INTERNAL_SERVER_ERROR"
            }
        )

# Agents Catalogue CRUD Endpoints
@router.get("/items", response_model=AgentsCatalogueResponse)
@require_role(["dashboard", "admin", "mcp_read_user"])
async def get_agents_catalogue_items(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    lifecycle: Optional[str] = Query(None),
    agents_catalogue_service: AgentsCatalogueService = Depends(get_agents_catalogue_service),
    logger: Logger = Depends(get_logger)
):
    """Get agents catalogue items with pagination and filtering."""
    try:
        result = agents_catalogue_service.list_items(
            page=page,
            per_page=per_page,
            search=search,
            item_type=type,
            lifecycle=lifecycle
        )

        # Convert to expected forma
        items = []
        for item in result.get('items', []):
            items.append(AgentsCatalogueItem(
                id=item['id'],
                name=item['name'],
                description=item['description'],
                type=item['type'],
                type_display=item.get('type_display', item['type']),
                lifecycle=item['lifecycle'],
                owners=item['owners'],
                tags=item['tags'],
                created_at=int(item['created_at']),
                updated_at=int(item['updated_at'])
            ))

        pagination_data = result.get('pagination', {})
        pagination = AgentsCataloguePagination(
            page=pagination_data.get('page', page),
            per_page=pagination_data.get('per_page', per_page),
            total_pages=pagination_data.get('total_pages', 1),
            total_items=pagination_data.get('total_items', len(items)),
            has_next=pagination_data.get('has_next', False),
            has_prev=pagination_data.get('has_prev', False)
        )

        return AgentsCatalogueResponse(
            items=items,
            pagination=pagination,
            filters=result.get('filters', {})
        )

    except Exception as e:
        logger.error("Error getting agents catalogue items", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve agents catalogue items"
        )

@router.post("/items", response_model=AgentsCatalogueItem, status_code=status.HTTP_201_CREATED)
@require_role(["dashboard", "admin"])
async def create_agents_catalogue_item(
    request: Request,
    item_data: AgentsCatalogueItemCreate,
    agents_catalogue_service: AgentsCatalogueService = Depends(get_agents_catalogue_service),
    logger: Logger = Depends(get_logger)
):
    """Create a new agents catalogue item."""
    try:
        item_id = agents_catalogue_service.create_item(
            name=item_data.name,
            description=item_data.description,
            item_type=item_data.type,
            lifecycle=item_data.lifecycle,
            owners=item_data.owners,
            tags=item_data.tags
        )

        # Get the created item
        item = agents_catalogue_service.get_item(item_id)

        return AgentsCatalogueItem(
            id=item['id'],
            name=item['name'],
            description=item['description'],
            type=item['type'],
            type_display=item.get('type_display', item['type']),
            lifecycle=item['lifecycle'],
            owners=item['owners'],
            tags=item['tags'],
            created_at=int(item['created_at']),
            updated_at=int(item['updated_at'])
        )

    except (ValidationError, ValueError) as e:
        logger.error("Validation error creating agents catalogue item", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except BusinessLogicError as e:
        logger.error("Business logic error creating agents catalogue item", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Error creating agents catalogue item", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create agents catalogue item"
        )

@router.get("/items/{item_id}", response_model=AgentsCatalogueItem)
async def get_agents_catalogue_item(
    item_id: str,
    agents_catalogue_service: AgentsCatalogueService = Depends(get_agents_catalogue_service),
    logger: Logger = Depends(get_logger)
):
    """Get a specific agents catalogue item."""
    try:
        item = agents_catalogue_service.get_item(item_id)

        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agents catalogue item not found"
            )

        return AgentsCatalogueItem(
            id=item['id'],
            name=item['name'],
            description=item['description'],
            type=item['type'],
            type_display=item.get('type_display', item['type']),
            lifecycle=item['lifecycle'],
            owners=item['owners'],
            tags=item['tags'],
            created_at=int(item['created_at']),
            updated_at=int(item['updated_at'])
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting agents catalogue item", item_id=item_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve agents catalogue item"
        )

@router.put("/items/{item_id}", response_model=AgentsCatalogueItem)
async def update_agents_catalogue_item(
    item_id: str,
    item_data: AgentsCatalogueItemUpdate,
    agents_catalogue_service: AgentsCatalogueService = Depends(get_agents_catalogue_service),
    logger: Logger = Depends(get_logger)
):
    """Update an agents catalogue item."""
    try:
        # Filter out None values and map field names
        update_data = {}
        for k, v in item_data.model_dump().items():
            if v is not None:
                # Map API field names to service method parameter names
                if k == "type":
                    update_data["item_type"] = v
                else:
                    update_data[k] = v

        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No update data provided"
            )

        item = agents_catalogue_service.update_item(item_id, **update_data)

        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agents catalogue item not found"
            )

        return AgentsCatalogueItem(
            id=item['id'],
            name=item['name'],
            description=item['description'],
            type=item['type'],
            type_display=item.get('type_display', item['type']),
            lifecycle=item['lifecycle'],
            owners=item['owners'],
            tags=item['tags'],
            created_at=int(item['created_at']),
            updated_at=int(item['updated_at'])
        )

    except HTTPException:
        raise
    except (ValidationError, ValueError) as e:
        logger.error("Validation error updating agents catalogue item", item_id=item_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except BusinessLogicError as e:
        logger.error("Business logic error updating agents catalogue item", item_id=item_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Error updating agents catalogue item", item_id=item_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update agents catalogue item"
        )

@router.delete("/items/{item_id}")
async def delete_agents_catalogue_item(
    item_id: str,
    agents_catalogue_service: AgentsCatalogueService = Depends(get_agents_catalogue_service),
    logger: Logger = Depends(get_logger)
):
    """Delete an agents catalogue item."""
    try:
        success = agents_catalogue_service.delete_item(item_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agents catalogue item not found"
            )

        return {"message": "Agents catalogue item deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error deleting agents catalogue item", item_id=item_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete agents catalogue item"
        )

@router.get("/config", response_model=AgentsCatalogueConfig)
@require_role(["dashboard", "admin", "mcp_read_user"])
async def get_agents_catalogue_config(
    request: Request,
    agents_catalogue_service: AgentsCatalogueService = Depends(get_agents_catalogue_service),
    logger: Logger = Depends(get_logger)
):
    """Get agents catalogue configuration."""
    try:
        # Create config from service methods
        config = {
            "available_types": [
                {"value": t, "label": t.replace('-', ' ').title()}
                for t in agents_catalogue_service.get_available_types()
            ],
            "available_lifecycles": agents_catalogue_service.get_available_lifecycles(),
            "available_tags": agents_catalogue_service.get_available_tags(),
            "default_owner": "user@razorpay.com"  # Default fallback
        }

        return AgentsCatalogueConfig(
            available_types=config.get('available_types', []),
            available_lifecycles=config.get('available_lifecycles', []),
            available_tags=config.get('available_tags', []),
            default_owner=config.get('default_owner', '')
        )

    except Exception as e:
        logger.error("Error getting agents catalogue config", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve agents catalogue configuration"
        )

# Generic download endpoint for all agents
@router.get("/{item_type}/{usecase_name}/download/{task_id}/{file_type}")
@require_role(["dashboard", "admin"])
async def download_agent_file(
    request: Request,
    item_type: str,
    usecase_name: str,
    task_id: str,
    file_type: str,
    logger: Logger = Depends(get_logger)
):
    """
    Generic download endpoint for agent-generated files.

    Args:
        item_type: Type of agent (micro-frontend, workflow, etc.)
        usecase_name: Name of the specific agent (bank-uat-agent, api-doc-generator, etc.)
        task_id: Task identifier
        file_type: Type of file to download

    Returns:
        File download response
    """
    try:
        # Validate inputs
        item_type = validate_item_type(item_type)
        usecase_name = validate_usecase_name(usecase_name)

        logger.info(f"Download request for {usecase_name} file",
                   task_id=task_id, file_type=file_type, item_type=item_type)

        # Use file download service to get file
        from src.services.files import get_file_download_service
        download_service = get_file_download_service(logger)

        file_path, filename = download_service.get_file_for_download(
            usecase_name=usecase_name,
            task_id=task_id,
            file_type=file_type
        )

        if not file_path:
            # Get supported file types for better error message
            supported_types = download_service.get_supported_file_types(usecase_name)

            logger.error(f"File not found for download",
                       task_id=task_id, file_type=file_type, usecase_name=usecase_name,
                       supported_types=supported_types)

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "File not found",
                    "message": f"The requested file for task {task_id} was not found.",
                    "task_id": task_id,
                    "file_type": file_type,
                    "usecase_name": usecase_name,
                    "supported_file_types": supported_types
                }
            )

        logger.info(f"Serving file for download",
                   task_id=task_id, file_type=file_type, usecase_name=usecase_name,
                   file_path=str(file_path), filename=filename)

        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type="application/octet-stream"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error downloading {usecase_name} file",
                        task_id=task_id, file_type=file_type, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during file download"
        )










