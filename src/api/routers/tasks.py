"""
Tasks router for FastAPI.

This module provides REST API endpoints for task management using the service layer.
"""

from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, status, Depends, Query, Request
from pydantic import BaseModel, Field, ConfigDict

from src.models import TaskStatus
from src.providers.auth import require_role
from src.providers.logger import Logger
from src.services import TaskService
from src.services.exceptions import (
    TaskNotFoundError, ValidationError,
    InvalidStatusTransitionError, BusinessLogicError
)
from src.utils.prompt_guard import validate_prompt_or_raise, PromptInjectionError, scan_for_injection, ThreatLevel
from ..dependencies import get_task_service, get_logger, get_cache_service

# Create router
router = APIRouter()


# Pydantic models for request/response
class TaskCreateRequest(BaseModel):
    """Request model for creating a task."""
    name: str = Field(..., min_length=1, max_length=255, description="Task name")
    description: Optional[str] = Field(None, description="Task description")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Task parameters")


class TaskUpdateStatusRequest(BaseModel):
    """Request model for updating task status."""
    status: str = Field(..., description="New task status")
    progress: Optional[int] = Field(None, ge=0, le=100, description="Task progress (0-100)")


class TaskTerminationRequest(BaseModel):
    """Request model for terminating a task."""
    reason: Optional[str] = Field(None, description="Reason for termination")
    force: bool = Field(False, description="Force termination even if task is not running")


class TaskResponse(BaseModel):
    """Response model for task data."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str] = None
    status: str
    created_at: str
    updated_at: str
    progress: Optional[int] = None
    parameters: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None


class TaskListResponse(BaseModel):
    """Response model for task list."""
    tasks: List[TaskResponse]
    total: int
    limit: int
    offset: int


class BatchTaskCreateRequest(BaseModel):
    """Request model for batch task creation."""
    tasks: List[TaskCreateRequest] = Field(..., min_items=1, max_items=100)


class BatchTaskCreateResponse(BaseModel):
    """Response model for batch task creation."""
    total_created: int
    total_errors: int
    created_tasks: List[TaskResponse]
    errors: List[Dict[str, Any]]


class TaskStatsResponse(BaseModel):
    """Response model for task statistics."""
    total_tasks: int
    by_status: Dict[str, int]


class TaskTerminationResponse(BaseModel):
    """Response model for task termination."""
    task_id: str
    previous_status: str
    new_status: str
    reason: Optional[str] = None
    terminated_at: str
    message: str


class ExecutionLogEntry(BaseModel):
    """Model for a single execution log entry."""
    log_index: int = Field(..., description="Index of this log entry")
    timestamp: Optional[str] = Field(None, description="Timestamp of the log entry")
    content: str = Field(..., description="Content of the log entry")
    status: str = Field(..., description="Status of this log entry (active/completed)")


class TaskExecutionLogsResponse(BaseModel):
    """Response model for task execution logs."""
    task_id: str = Field(..., description="ID of the task")
    total_logs: int = Field(..., description="Total number of logs for this task")
    last_logs: List[ExecutionLogEntry] = Field(..., description="Last N execution logs")
    file_status: str = Field(..., description="Status of the log file (active/not_found/read_error)")
    last_updated: Optional[str] = Field(None, description="Last time the log file was updated")


def _validate_task_parameters(parameters: Optional[Dict[str, Any]], logger: Logger) -> None:
    """
    Validate task parameters for potential prompt injection.
    
    Args:
        parameters: Task parameters dictionary
        logger: Logger instance
        
    Raises:
        HTTPException: If prompt injection is detected
    """
    if not parameters:
        return
    
    # Fields that may contain user-provided prompts
    prompt_fields = ["user_prompt", "prompt", "input_prompt", "message", "query", "instruction"]
    
    for field in prompt_fields:
        if field in parameters and parameters[field]:
            value = str(parameters[field])
            result = scan_for_injection(value)
            
            if result.threat_level == ThreatLevel.MALICIOUS:
                logger.warning(
                    "Prompt injection detected in task creation",
                    extra={
                        "field": field,
                        "matched_patterns": result.matched_patterns[:3]
                    }
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "invalid_prompt",
                        "message": "The request contains potentially harmful patterns and has been blocked for security. If this is a legitimate development request, please rephrase your prompt.",
                        "field": field,
                        "matched_patterns": result.matched_patterns[:3] if result.matched_patterns else []
                    }
                )
    
    # Also check nested input_parameters if present
    if "input_parameters" in parameters and isinstance(parameters["input_parameters"], dict):
        _validate_task_parameters(parameters["input_parameters"], logger)


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
@require_role(["dashboard", "admin"])
async def create_task(
        request: Request,
        task_data: TaskCreateRequest,
        task_service: TaskService = Depends(get_task_service),
        logger: Logger = Depends(get_logger)
):
    """Create a new task."""
    try:
        # Validate task parameters for prompt injection
        _validate_task_parameters(task_data.parameters, logger)
        
        task = task_service.create_task(
            name=task_data.name,
            description=task_data.description,
            parameters=task_data.parameters
        )

        # Auto-sanitized logging - no manual sanitization needed
        logger.info("Created task via API", task_id=task['id'])
        return TaskResponse(**task)

    except HTTPException:
        raise
    except TaskNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except InvalidStatusTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BusinessLogicError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        # Auto-sanitized error logging with exception info
        logger.exception("Unhandled error in create_task", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/stats", response_model=TaskStatsResponse)
@require_role(["dashboard", "admin", "devops"])
async def get_task_statistics(
        request: Request,
        task_service: TaskService = Depends(get_task_service),
        cache_service=Depends(get_cache_service),
        logger: Logger = Depends(get_logger)
):
    """Get task statistics."""
    try:
        # Use cache service to get task statistics with 2-minute TTL
        def fetch_task_stats():
            return task_service.get_task_statistics()

        stats = cache_service.get_task_stats(fetch_task_stats)

        logger.debug("Retrieved task statistics via API")
        return TaskStatsResponse(**stats)

    except Exception as e:
        # Auto-sanitized error logging
        logger.exception("Unhandled error in get_task_statistics", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/users", response_model=List[dict])
@require_role(["dashboard", "admin", "mcp_read_user", "devops"])
async def list_task_users(
        request: Request,
        task_service: TaskService = Depends(get_task_service),
        logger: Logger = Depends(get_logger),
):
    """List unique users who have triggered tasks, with task counts."""
    try:
        from src.providers.database.connection import get_engine
        from sqlalchemy import text
        engine = get_engine()
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT
                    JSON_UNQUOTE(JSON_EXTRACT(task_metadata, '$.connector.user_email')) AS user_email,
                    COUNT(*) AS task_count
                FROM tasks
                WHERE JSON_EXTRACT(task_metadata, '$.connector.user_email') IS NOT NULL
                  AND JSON_UNQUOTE(JSON_EXTRACT(task_metadata, '$.connector.user_email')) != 'null'
                  AND JSON_UNQUOTE(JSON_EXTRACT(task_metadata, '$.connector.user_email')) != ''
                GROUP BY user_email
                ORDER BY task_count DESC
                LIMIT 100
            """)).fetchall()
        return [{"email": r[0], "task_count": r[1]} for r in rows if r[0]]
    except Exception as e:
        logger.exception("Error listing task users", error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.get("/{task_id}", response_model=TaskResponse)
@require_role(["dashboard", "admin", "mcp_read_user", "splitz", "devops"])
async def get_task(
        request: Request,
        task_id: str,
        task_service: TaskService = Depends(get_task_service),
        logger: Logger = Depends(get_logger)
):
    """Get a task by ID."""
    try:
        task = task_service.get_task(task_id)

        # Auto-sanitized logging
        logger.debug(f"Retrieved task {task_id} via API", task_id=task_id)
        return TaskResponse(**task)

    except TaskNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        # Auto-sanitized error logging
        logger.exception(f"Unhandled error in get_task for task {task_id}", task_id=task_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("", response_model=List[TaskResponse])
@require_role(["dashboard", "admin", "mcp_read_user", "devops"])
async def list_tasks(
        request: Request,
        status_filter: Optional[str] = Query(None, alias="status",
                                             description="Filter by status (comma-separated for multiple)"),
        user_email: Optional[str] = Query(None, description="Filter by user email from task metadata"),
        connector: Optional[str] = Query(None, description="Filter by connector: slack | dashboard | devrev"),
        page: int = Query(1, ge=1, description="Page number (1-based)"),
        page_size: int = Query(20, ge=1, le=100, description="Number of tasks per page"),
        task_service: TaskService = Depends(get_task_service),
        logger: Logger = Depends(get_logger)
):
    """List tasks with optional filters and pagination."""
    try:
        # Convert page-based pagination to limit/offset
        limit = page_size
        offset = (page - 1) * page_size

        # Parse comma-separated status values
        status_values = []
        if status_filter:
            status_list = [s.strip() for s in status_filter.split(',')]
            for status_str in status_list:
                try:
                    status_values.append(TaskStatus(status_str))
                except ValueError:
                    valid_statuses = [s.value for s in TaskStatus]
                    # Auto-sanitized warning logging
                    logger.warning(f"Invalid status filter provided: {status_str}", invalid_status=status_str,
                                   valid_statuses=valid_statuses)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "error": "Invalid status",
                            "message": f"Status '{status_str}' is invalid. Must be one of: {valid_statuses}"
                        }
                    )

        # Get tasks with pagination
        if user_email or connector:
            # User/connector filter — supports optional status alongside
            status_val = status_values[0] if len(status_values) == 1 else None
            result = task_service.list_tasks_by_user(
                user_email=user_email,
                connector=connector,
                status=status_val,
                limit=limit,
                offset=offset,
            )
        elif len(status_values) == 1:
            result = task_service.list_tasks(status=status_values[0], limit=limit, offset=offset)
        elif len(status_values) > 1:
            result = task_service.list_tasks_by_statuses(status_values, limit=limit, offset=offset)
        else:
            result = task_service.list_tasks(status=None, limit=limit, offset=offset)

        # No need to filter in memory anymore - server handles it
        tasks = result['tasks']

        logger.debug(f"Listed {len(tasks)} tasks via API", task_count=len(tasks), page=page, page_size=page_size)
        return [TaskResponse(**task) for task in tasks]

    except HTTPException:
        raise
    except Exception as e:
        # Auto-sanitized error logging
        logger.exception("Unhandled error in list_tasks", error=str(e), page=page, page_size=page_size)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.put("/{task_id}/status", response_model=TaskResponse)
@require_role(["dashboard", "admin"])
async def update_task_status(
        request: Request,
        task_id: str,
        status_data: TaskUpdateStatusRequest,
        task_service: TaskService = Depends(get_task_service),
        logger: Logger = Depends(get_logger)
):
    """Update task status."""
    try:
        # Validate status
        try:
            task_status = TaskStatus(status_data.status)
        except ValueError:
            # Auto-sanitized warning logging
            logger.warning(f"Invalid status update attempted: {status_data.status}",
                           task_id=task_id, attempted_status=status_data.status)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Invalid status",
                    "message": f"Status must be one of: {[s.value for s in TaskStatus]}"
                }
            )

        # Update task using service
        task = task_service.update_task_status(
            task_id=task_id,
            status=task_status,
            progress=status_data.progress
        )

        # Auto-sanitized info logging with structured data
        logger.info(f"Updated task {task_id} status to {task_status.value} via API",
                    task_id=task_id, new_status=task_status.value, progress=status_data.progress)
        return TaskResponse(**task)

    except HTTPException:
        raise
    except TaskNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except InvalidStatusTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        # Auto-sanitized error logging
        logger.exception(f"Unhandled error in update_task_status for task {task_id}",
                         task_id=task_id, attempted_status=status_data.status, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/batch", response_model=BatchTaskCreateResponse, status_code=status.HTTP_201_CREATED)
@require_role(["admin"])
async def create_batch_tasks(
        request: Request,
        batch_data: BatchTaskCreateRequest,
        task_service: TaskService = Depends(get_task_service),
        logger: Logger = Depends(get_logger)
):
    """Create multiple tasks in a batch operation."""
    created_tasks = []
    errors = []

    for i, task_data in enumerate(batch_data.tasks):
        try:
            task = task_service.create_task(
                name=task_data.name,
                description=task_data.description,
                parameters=task_data.parameters
            )
            created_tasks.append(TaskResponse(**task))

        except Exception as e:
            errors.append({
                "index": i,
                "task_name": task_data.name,
                "error": str(e)
            })
            # Auto-sanitized warning logging
            logger.warning(f"Failed to create batch task {i} ({task_data.name})",
                           batch_index=i, task_name=task_data.name, error=str(e))

    # Auto-sanitized info logging with batch summary
    logger.info(f"Batch created {len(created_tasks)} tasks with {len(errors)} errors via API",
                total_created=len(created_tasks), total_errors=len(errors), batch_size=len(batch_data.tasks))
    return BatchTaskCreateResponse(
        total_created=len(created_tasks),
        total_errors=len(errors),
        created_tasks=created_tasks,
        errors=errors
    )


@router.post("/{task_id}/terminate", response_model=TaskTerminationResponse)
async def terminate_task(
        task_id: str,
        termination_data: TaskTerminationRequest,
        task_service: TaskService = Depends(get_task_service),
        logger: Logger = Depends(get_logger)
):
    """
    Terminate a running task.
    
    This endpoint allows manual termination of tasks that are currently running or pending.
    Once terminated, the task status will be set to 'cancelled' and it will not be processed further.
    """
    try:
        # Terminate the task using service
        result = task_service.terminate_task(
            task_id=task_id,
            reason=termination_data.reason,
            force=termination_data.force
        )

        # Auto-sanitized info logging
        logger.info(f"Terminated task {task_id} via API",
                    task_id=task_id,
                    previous_status=result['previous_status'],
                    reason=termination_data.reason,
                    force=termination_data.force)

        return TaskTerminationResponse(**result)

    except TaskNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except InvalidStatusTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BusinessLogicError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        # Auto-sanitized error logging
        logger.exception(f"Unhandled error in terminate_task for task {task_id}",
                         task_id=task_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{task_id}/execution-logs", response_model=TaskExecutionLogsResponse)
@require_role(["dashboard", "admin", "mcp_read_user", "devops"])
async def get_task_execution_logs(
        request: Request,
        task_id: str,
        limit: int = Query(1000, ge=1, le=1000, description="Number of logs to return (1-1000)"),
        task_service: TaskService = Depends(get_task_service),
        logger: Logger = Depends(get_logger)
):
    """
    Get the last N execution logs for a task.
    
    This endpoint provides real-time access to task execution logs,
    including Claude's responses and agent behavior. Useful for monitoring
    task progress and debugging.
    """
    try:
        logger.info(f"Getting execution logs for task {task_id} (limit: {limit})",
                    task_id=task_id, limit=limit)

        # Get execution logs from service
        logs_data = task_service.get_task_execution_logs(task_id, limit)

        # Convert to response model
        response = TaskExecutionLogsResponse(
            task_id=logs_data['task_id'],
            total_logs=logs_data['total_logs'],
            last_logs=[
                ExecutionLogEntry(
                    log_index=log['log_index'],
                    timestamp=log['timestamp'],
                    content=log['content'],
                    status=log['status']
                ) for log in logs_data['last_logs']
            ],
            file_status=logs_data['file_status'],
            last_updated=logs_data['last_updated']
        )

        logger.info(f"Retrieved {len(response.last_logs)} execution logs for task {task_id}",
                    task_id=task_id,
                    total_logs=response.total_logs,
                    file_status=response.file_status)

        return response

    except TaskNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessLogicError as e:
        logger.error(f"Business logic error in get_task_execution_logs for task {task_id}: {e}",
                     task_id=task_id, error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        logger.exception(f"Unhandled error in get_task_execution_logs for task {task_id}",
                         task_id=task_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
