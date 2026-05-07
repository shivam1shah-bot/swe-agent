"""
Task service for the SWE Agent.

Provides business logic for task management operations.
"""

import json
import os
import shutil
import time
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any, Union, Tuple

from src.models import Task, TaskStatus
from src.providers.database.session import get_session, get_readonly_session
from src.repositories import SQLAlchemyTaskRepository
from src.repositories.exceptions import EntityNotFoundError, RepositoryError
from .base import BaseService
from .exceptions import (
    TaskNotFoundError, ValidationError, InvalidStatusTransitionError, BusinessLogicError
)


class TaskService(BaseService):
    """Task service for managing tasks."""

    def __init__(self, config, database_provider):
        """Initialize the task service."""
        super().__init__("TaskService")
        self._db_provider = database_provider

        # Database provider should already be initialized by the FastAPI lifespan
        # No need for redundant initialization checks here

        self.initialize(config)

    def _get_task_repo(self, session):
        """Get the task repository with a given session."""
        return SQLAlchemyTaskRepository(session)

    def _validate_status_transition(self, current_status, new_status):
        """Validate that a status transition is allowed."""
        # Allow any transition for now
        # This can be expanded to implement state machine rules
        pass

    def _validate_task_data(self, name: str, description: str = None):
        """
        Validate task data before creation.

        Args:
            name: Task name
            description: Task description

        Raises:
            ValidationError: If validation fails
        """
        # Validate name
        if not name or not name.strip():
            raise ValidationError("name", "Task name is required")

        if len(name.strip()) > 255:
            raise ValidationError("name", "Task name cannot exceed 255 characters")

        # Validate description length if provided
        if description and len(description.strip()) > 1000:
            raise ValidationError("description", "Task description cannot exceed 1000 characters")

    def _serialize_datetime(self, dt: Union[datetime, int, None]) -> Optional[str]:
        """
        Serialize a datetime object to ISO format string.

        Args:
            dt: Datetime object, timestamp, or None

        Returns:
            ISO format string or None
        """
        if dt is None:
            return None

        if isinstance(dt, datetime):
            return dt.isoformat()

        if isinstance(dt, int):
            # Convert timestamp to datetime and then to ISO format
            try:
                return datetime.fromtimestamp(dt).isoformat()
            except (ValueError, OverflowError):
                self._log_warning(f"Invalid timestamp: {dt}")
                return str(dt)

        # If it's already a string, return as is
        if isinstance(dt, str):
            return dt

        # For any other type, convert to string
        return str(dt)

    def _task_to_dict(self, task: Task) -> Dict[str, Any]:
        """
        Convert Task entity to dictionary.
        
        Args:
            task: Task entity
            
        Returns:
            Dictionary representation of task
        """
        # Safe JSON parsing helper
        def safe_json_parse(json_str, fallback=None):
            """Safely parse JSON string, returning fallback on error."""
            if fallback is None:
                fallback = {}
            
            if not json_str or (isinstance(json_str, str) and json_str.strip() == ''):
                return fallback
            
            try:
                return json.loads(json_str)
            except (json.JSONDecodeError, TypeError, ValueError) as e:
                self.logger.warning(
                    f"Failed to parse JSON field",
                    extra={"error": str(e), "json_str_preview": str(json_str)[:100]}
                )
                return fallback
        
        result = {
            "id": task.id,
            "name": task.name,
            "description": task.description,
            "status": task.status,
            "progress": task.progress or 0,
            "parameters": safe_json_parse(task.parameters, {}),
            "created_at": self._serialize_datetime(task.created_at),
            "updated_at": self._serialize_datetime(task.updated_at),
        }

        # Add result if available - ensure it's always a dict or None
        if task.result:
            parsed_result = safe_json_parse(task.result, None)
            if parsed_result is not None:
                # Ensure the result is a dictionary
                if isinstance(parsed_result, dict):
                    result["result"] = parsed_result
                else:
                    # Convert non-dict results to a dict format
                    result["result"] = {"message": str(parsed_result)}
            else:
                # If parsing failed, wrap the raw value in a dict
                result["result"] = {"message": str(task.result)}
        else:
            result["result"] = None

        # Add metadata if available using task_metadata field (not the SQLAlchemy metadata)
        if task.task_metadata:
            parsed_metadata = safe_json_parse(task.task_metadata, None)
            if parsed_metadata is not None:
                result["metadata"] = parsed_metadata
            else:
                result["metadata"] = {"raw": str(task.task_metadata)}
        else:
            result["metadata"] = None

        return result

    def create_task(
            self,
            name: str,
            description: str = None,
            parameters: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Create a new task.

        Args:
            name: Task name
            description: Task description
            parameters: Task parameters

        Returns:
            Dictionary representation of created task

        Raises:
            ValidationError: If input validation fails
        """
        self._validate_initialized()
        self._log_operation("create_task", task_name=name)

        try:
            # Validate input data
            self._validate_task_data(name, description)

            # Create task entity
            task = Task(
                id=str(uuid.uuid4()),
                name=name.strip(),
                description=description.strip() if description else None,
                parameters=json.dumps(parameters) if parameters else None,
                status=TaskStatus.CREATED.value,
                progress=0
            )

            # Set initial performance metadata
            task.set_performance_start()

            # Save task using repository
            with get_session() as session:
                task_repo = self._get_task_repo(session)
                created_task = task_repo.create(task)

                # Convert to dictionary for return
                result = self._task_to_dict(created_task)

                self._log_success("create_task", task_id=created_task.id)
                return result

        except ValidationError as e:
            self._log_error("create_task", e, task_name=name)
            raise
        except RepositoryError as e:
            self._log_error("create_task", e, task_name=name)
            raise BusinessLogicError(f"Failed to create task: {e}")
        except Exception as e:
            self._log_error("create_task", e, task_name=name)
            raise BusinessLogicError(f"Unexpected error creating task: {e}")

    def get_task(self, task_id: str) -> Dict[str, Any]:
        """
        Get a task by ID.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Dictionary representation of task
            
        Raises:
            TaskNotFoundError: If task does not exist
        """
        self._validate_initialized()
        self._log_operation("get_task", task_id=task_id)

        try:
            # Use read-only session to avoid conflicts with write operations during task execution

            with get_readonly_session() as session:
                task_repo = self._get_task_repo(session)
                task = task_repo.get_by_id(task_id)

                if not task:
                    raise TaskNotFoundError(task_id)

                result = self._task_to_dict(task)

                # Check if this is a batch parent task and update child status
                result = self._update_batch_parent_status(result, session)

                self._log_success("get_task", task_id=task_id)
                return result

        except TaskNotFoundError:
            raise
        except RepositoryError as e:
            self._log_error("get_task", e, task_id=task_id)
            raise BusinessLogicError(f"Failed to get task: {e}")
        except Exception as e:
            self._log_error("get_task", e, task_id=task_id)
            raise BusinessLogicError(f"Unexpected error getting task: {e}")

    def list_tasks(self, status: Optional[TaskStatus] = None, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """
        List tasks with optional filtering and pagination.
        
        Args:
            status: Optional status filter
            limit: Maximum number of tasks to return
            offset: Number of tasks to skip for pagination
            
        Returns:
            Dictionary with list of tasks
        """
        self._validate_initialized()
        status_value = status.value if hasattr(status, 'value') else status if status else None
        self._log_operation("list_tasks", status=status_value, limit=limit, offset=offset)

        try:
            # Use read-only session for list operations to avoid connection conflicts
            with get_readonly_session() as session:
                task_repo = self._get_task_repo(session)

                # Get tasks based on status filter
                if status:
                    tasks = task_repo.get_by_status(status, limit, offset)
                else:
                    tasks = task_repo.get_all(limit=limit, offset=offset)

                # Convert tasks to dictionaries (skip expensive batch status updates for list operations)
                task_dicts = []
                for task in tasks:
                    if task:  # Safety check for task
                        task_dict = self._task_to_dict(task)
                        # Skip batch parent status update for performance - only update when viewing individual tasks
                        if task_dict:  # Safety check for task_dict
                            task_dicts.append(task_dict)

                result = {
                    "tasks": task_dicts,
                    "count": len(task_dicts),
                }

                self._log_success("list_tasks", count=len(task_dicts), status=status_value, offset=offset)
                return result

        except Exception as e:
            self._log_error("list_tasks", e, status=status_value, limit=limit, offset=offset)
            # Log more detailed error information
            import traceback
            self.logger.error(f"Detailed error in list_tasks: {traceback.format_exc()}")
            raise BusinessLogicError(f"Unexpected error listing tasks: {e}")

    def list_tasks_by_user(
        self,
        user_email: Optional[str] = None,
        connector: Optional[str] = None,
        status: Optional[TaskStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List tasks filtered by user_email and/or connector from task_metadata."""
        self._validate_initialized()
        try:
            with get_readonly_session() as session:
                task_repo = self._get_task_repo(session)
                tasks = task_repo.get_by_connector_filter(
                    user_email=user_email,
                    connector=connector,
                    status=status,
                    limit=limit,
                    offset=offset,
                )
                task_dicts = [self._task_to_dict(t) for t in tasks if t]
                return {"tasks": task_dicts, "count": len(task_dicts)}
        except Exception as e:
            self._log_error("list_tasks_by_user", e)
            raise BusinessLogicError(f"Unexpected error listing tasks by user: {e}")

    def list_tasks_by_statuses(self, statuses: List[TaskStatus], limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """
        List tasks by multiple statuses with pagination.
        
        Args:
            statuses: List of status filters
            limit: Maximum number of tasks to return
            offset: Number of tasks to skip for pagination
            
        Returns:
            Dictionary with list of tasks
        """
        self._validate_initialized()
        status_values = [s.value for s in statuses]
        self._log_operation("list_tasks_by_statuses", statuses=status_values, limit=limit, offset=offset)

        try:
            # Use read-only session for list operations to avoid connection conflicts
            with get_readonly_session() as session:
                task_repo = self._get_task_repo(session)

                # Get tasks by multiple statuses
                tasks = task_repo.get_by_statuses(statuses, limit, offset)

                # Convert tasks to dictionaries (skip expensive batch status updates for list operations)
                task_dicts = []
                for task in tasks:
                    if task:  # Safety check for task
                        task_dict = self._task_to_dict(task)
                        # Skip batch parent status update for performance - only update when viewing individual tasks
                        if task_dict:  # Safety check for task_dict
                            task_dicts.append(task_dict)

                result = {
                    "tasks": task_dicts,
                    "count": len(task_dicts),
                }

                self._log_success("list_tasks_by_statuses", count=len(task_dicts), statuses=status_values,
                                  offset=offset)
                return result

        except Exception as e:
            # Log more detailed error information with context
            import traceback
            self.logger.error(f"Detailed error in list_tasks_by_statuses: {traceback.format_exc()}", extra={
                "statuses": status_values if 'status_values' in locals() else "not_defined",
                "limit": limit,
                "offset": offset,
                "error_type": type(e).__name__,
                "error_message": str(e)
            })
            self._log_error("list_tasks_by_statuses", e, statuses=status_values if 'status_values' in locals() else [],
                            limit=limit, offset=offset)
            raise BusinessLogicError(f"Unexpected error listing tasks by statuses: {e}")

    def update_task_status(
            self,
            task_id: str,
            status: TaskStatus,
            progress: int = None,
            queue_wait_time_ms: int = None
    ) -> Dict[str, Any]:
        """
        Update task status with validation and performance tracking.

        Args:
            task_id: Task identifier
            status: New status
            progress: Optional progress update
            queue_wait_time_ms: Optional queue wait time for performance tracking

        Returns:
            Dictionary representation of updated task

        Raises:
            TaskNotFoundError: If task does not exist
            InvalidStatusTransitionError: If status transition is invalid
        """
        self._validate_initialized()
        self._log_operation("update_task_status", task_id=task_id, status=status.value)

        try:
            # Use session context manager properly
            with get_session() as session:
                task_repo = self._get_task_repo(session)

                # Get current task
                task = task_repo.get_by_id(task_id)
                if not task:
                    raise TaskNotFoundError(task_id)

                current_status = TaskStatus(task.status)

                # Validate status transition
                if current_status != status:
                    self._validate_status_transition(current_status, status)

                # Update performance tracking based on status
                if status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                    task.set_performance_end(queue_wait_time_ms)

                # Update status
                updated_task = task_repo.update_status(task_id, status)

                # Update progress if provided
                if progress is not None:
                    if not 0 <= progress <= 100:
                        raise ValidationError("progress", "Progress must be between 0 and 100")
                    updated_task = task_repo.update_progress(task_id, progress)

                result = self._task_to_dict(updated_task)
                self._log_success("update_task_status", task_id=task_id, status=status.value)
                return result

        except (TaskNotFoundError, InvalidStatusTransitionError, ValidationError):
            raise
        except EntityNotFoundError:
            raise TaskNotFoundError(task_id)
        except RepositoryError as e:
            self._log_error("update_task_status", e, task_id=task_id, status=status.value)
            raise BusinessLogicError(f"Failed to update task status: {e}")
        except Exception as e:
            self._log_error("update_task_status", e, task_id=task_id, status=status.value)
            raise BusinessLogicError(f"Unexpected error updating task status: {e}")

    def update_task_progress(self, task_id: str, progress: int) -> Task:
        """
        Update task progress.

        Args:
            task_id: Task identifier
            progress: Progress value (0-100)

        Returns:
            Updated task entity

        Raises:
            TaskNotFoundError: If task does not exist
            ValidationError: If progress is invalid
        """
        self._validate_initialized()
        self._log_operation("update_task_progress", task_id=task_id, progress=progress)

        try:
            if not 0 <= progress <= 100:
                raise ValidationError("progress", "Progress must be between 0 and 100")

            # Use session context manager properly
            with get_session() as session:
                task_repo = self._get_task_repo(session)
                updated_task = task_repo.update_progress(task_id, progress)

                self._log_success("update_task_progress", task_id=task_id, progress=progress)
                return updated_task

        except ValidationError:
            raise
        except EntityNotFoundError:
            raise TaskNotFoundError(task_id)
        except RepositoryError as e:
            self._log_error("update_task_progress", e, task_id=task_id, progress=progress)
            raise BusinessLogicError(f"Failed to update task progress: {e}")
        except Exception as e:
            self._log_error("update_task_progress", e, task_id=task_id, progress=progress)
            raise BusinessLogicError(f"Unexpected error updating task progress: {e}")

    def update_task_result(self, task_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update task result.

        Args:
            task_id: Task identifier
            result: Task result data

        Returns:
            Dictionary representation of updated task

        Raises:
            TaskNotFoundError: If task does not exist
        """
        self._validate_initialized()
        self._log_operation("update_task_result", task_id=task_id)

        try:
            # Use session context manager properly
            with get_session() as session:
                task_repo = self._get_task_repo(session)
                updated_task = task_repo.update_result(task_id, result)

                result_dict = self._task_to_dict(updated_task)
                self._log_success("update_task_result", task_id=task_id, result_size=len(str(result)))
                return result_dict

        except EntityNotFoundError:
            raise TaskNotFoundError(task_id)
        except RepositoryError as e:
            self._log_error("update_task_result", e, task_id=task_id)
            raise BusinessLogicError(f"Failed to update task result: {e}")
        except Exception as e:
            self._log_error("update_task_result", e, task_id=task_id)
            raise BusinessLogicError(f"Unexpected error updating task result: {e}")

    def get_available_workflows(self) -> Dict[str, Dict[str, Any]]:
        """
        Get available workflows from registry.

        Returns:
            Dictionary of available workflows with descriptions
        """
        self._validate_initialized()
        # Workflow registry removed - return empty dict, use agents catalogue instead
        return {}

    def get_workflow_by_name(self, workflow_name: str) -> Dict[str, Any]:
        """
        Get workflow information by name.

        Args:
            workflow_name: Workflow name

        Returns:
            Workflow information dictionary

        Raises:
            WorkflowValidationError: If workflow does not exist
        """
        self._validate_initialized()
        # Workflow registry removed - return legacy workflow info
        return {
            "name": workflow_name,
            "description": f"Legacy workflow: {workflow_name}",
            "status": "deprecated"
        }

    def get_task_statistics(self) -> Dict[str, Any]:
        """
        Get task statistics with caching.

        Returns:
            Dictionary with task statistics (cached for 1 minute)
        """
        self._validate_initialized()
        self._log_operation("get_task_statistics")

        def fetch_task_stats():
            try:
                # Use read-only session to avoid conflicts with write operations during task execution

                with get_readonly_session() as session:
                    task_repo = self._get_task_repo(session)

                    # Get all tasks for statistics
                    all_tasks = task_repo.get_all(limit=None, offset=0)

                    # Calculate statistics
                    total_tasks = len(all_tasks)
                    by_status = {}

                    for task in all_tasks:
                        # Count by status
                        status = task.status
                        # Ensure status is a string value, not enum
                        if hasattr(status, 'value'):
                            status = status.value
                        elif isinstance(status, TaskStatus):
                            status = status.value
                        by_status[status] = by_status.get(status, 0) + 1

                    result = {
                        "total_tasks": total_tasks,
                        "by_status": by_status
                    }

                    self._log_success("get_task_statistics", total_tasks=total_tasks)
                    return result

            except RepositoryError as e:
                self._log_error("get_task_statistics", e)
                raise BusinessLogicError(f"Failed to get task statistics: {e}")
            except Exception as e:
                self._log_error("get_task_statistics", e)
                raise BusinessLogicError(f"Unexpected error getting task statistics: {e}")

        # Use cache service with fallback to direct fetch
        try:
            from src.services.cache_service import cache_service
            cached_stats = cache_service.get_task_stats(fetch_task_stats)
            return cached_stats if cached_stats is not None else fetch_task_stats()
        except Exception as e:
            # If cache service fails, fall back to direct fetch
            self._log_error("get_task_statistics", e, message="Cache service failed, falling back to direct fetch")
            return fetch_task_stats()

    def get_workflow_statistics(self, workflow_name: str) -> Dict[str, Any]:
        """
        Get statistics for a specific workflow - deprecated.

        Args:
            workflow_name: Workflow name

        Returns:
            Empty statistics since workflow_name field was removed
        """
        self._validate_initialized()
        self._log_operation("get_workflow_statistics", workflow_name=workflow_name)

        self.logger.warning("get_workflow_statistics is deprecated - workflow_name field removed from Task model")

        # Return empty statistics since workflow concept is deprecated
        return {
            "total_tasks": 0,
            "by_status": {},
            "recent_tasks": 0,
            "deprecated": True,
            "message": "Workflow statistics are no longer available. Use task statistics or agents catalogue instead."
        }

    def terminate_task(
            self,
            task_id: str,
            reason: str = None,
            force: bool = False
    ) -> Dict[str, Any]:
        """
        Terminate a task by setting its status to CANCELLED.

        Args:
            task_id: Task identifier
            reason: Reason for termination
            force: Force termination even if task is not in terminable state

        Returns:
            Dictionary with termination result information

        Raises:
            TaskNotFoundError: If task does not exist
            InvalidStatusTransitionError: If task cannot be terminated
            BusinessLogicError: If termination fails
        """
        self._validate_initialized()
        self._log_operation("terminate_task", task_id=task_id, reason=reason, force=force)

        try:
            with get_session() as session:
                task_repo = self._get_task_repo(session)

                # Get current task
                current_task = task_repo.get_by_id(task_id)
                if not current_task:
                    raise TaskNotFoundError(task_id)

                previous_status = current_task.status

                # Validate termination is allowed
                if not force:
                    terminable_statuses = [
                        TaskStatus.CREATED.value,
                        TaskStatus.PENDING.value,
                        TaskStatus.RUNNING.value
                    ]

                    if previous_status not in terminable_statuses:
                        raise InvalidStatusTransitionError(
                            previous_status,
                            TaskStatus.CANCELLED.value
                        )

                # Update task status to CANCELLED
                updated_task = task_repo.update_status(
                    task_id,
                    TaskStatus.CANCELLED
                )

                # Handle batch parent task cancellation
                self._handle_batch_parent_cancellation(task_id, current_task, session)

                # Update task metadata with termination information
                termination_metadata = {
                    "termination": {
                        "terminated_at": int(time.time()),
                        "reason": reason or "Task terminated manually",
                        "force": force,
                        "previous_status": previous_status
                    }
                }
                updated_task.update_metadata(**termination_metadata)

                # Save metadata changes
                task_repo.update_metadata(task_id, updated_task.metadata_dict)

                # Prepare response
                result = {
                    "task_id": task_id,
                    "previous_status": previous_status,
                    "new_status": TaskStatus.CANCELLED.value,
                    "reason": reason or "Task terminated manually",
                    "terminated_at": self._serialize_datetime(termination_metadata["termination"]["terminated_at"]),
                    "message": f"Task {task_id} terminated successfully"
                }

                self._log_success("terminate_task", task_id=task_id,
                                  previous_status=previous_status, force=force)

                return result

        except TaskNotFoundError:
            raise
        except InvalidStatusTransitionError:
            raise
        except EntityNotFoundError:
            raise TaskNotFoundError(task_id)
        except RepositoryError as e:
            self._log_error("terminate_task", e, task_id=task_id)
            raise BusinessLogicError(f"Failed to terminate task: {e}")
        except Exception as e:
            self._log_error("terminate_task", e, task_id=task_id)
            raise BusinessLogicError(f"Unexpected error terminating task: {e}")

    def get_task_execution_logs(self, task_id: str, limit: int = 5) -> Dict[str, Any]:
        """
        Get the last N execution logs for a task.

        Args:
            task_id: The ID of the task
            limit: Number of logs to return (default 5)

        Returns:
            Dictionary containing execution logs and metadata
        """
        try:
            # Validate task exists
            with get_session() as session:
                task_repo = self._get_task_repo(session)
                task = task_repo.get_by_id(task_id)
                if not task:
                    raise TaskNotFoundError(task_id)

            # Read execution logs
            logs_dir = os.path.join("tmp", "logs", "agent-logs")
            log_file_path = os.path.join(logs_dir, f"claude_code_{task_id}.json")

            if not os.path.exists(log_file_path):
                return {
                    "task_id": task_id,
                    "total_logs": 0,
                    "last_logs": [],
                    "file_status": "not_found",
                    "last_updated": None
                }

            # Get file metadata
            file_stat = os.stat(log_file_path)
            last_modified = datetime.fromtimestamp(file_stat.st_mtime).isoformat()

            # Safely read the log file
            logs_data = self._safely_read_log_file(log_file_path)

            if logs_data is None:
                return {
                    "task_id": task_id,
                    "total_logs": 0,
                    "last_logs": [],
                    "file_status": "read_error",
                    "last_updated": last_modified
                }

            # Normalize to list format
            if isinstance(logs_data, dict):
                logs_list = [logs_data]
            elif isinstance(logs_data, list):
                logs_list = logs_data
            else:
                logs_list = []

            # Get the last N logs
            last_logs = logs_list[-limit:] if len(logs_list) > limit else logs_list

            # Format logs with metadata
            formatted_logs = []
            for i, log_entry in enumerate(last_logs):
                formatted_log = {
                    "log_index": len(logs_list) - len(last_logs) + i + 1,
                    "timestamp": self._extract_timestamp_from_log(log_entry),
                    "content": self._extract_content_from_log(log_entry),
                    "status": "active" if i == len(last_logs) - 1 else "completed"
                }
                formatted_logs.append(formatted_log)

            return {
                "task_id": task_id,
                "total_logs": len(logs_list),
                "last_logs": formatted_logs,
                "file_status": "active",
                "last_updated": last_modified
            }

        except TaskNotFoundError:
            raise
        except Exception as e:
            self._log_error("get_task_execution_logs", e, task_id=task_id)
            raise BusinessLogicError(f"Failed to get execution logs: {e}")

    def _safely_read_log_file(self, file_path: str, max_retries: int = 3) -> Optional[Any]:
        """
        Safely read a log file that might be actively written to.

        Args:
            file_path: Path to the log file
            max_retries: Maximum number of retry attempts

        Returns:
            Parsed JSON data or None if failed
        """
        for attempt in range(max_retries):
            try:
                # Create a temporary copy to avoid reading while writing
                temp_file_path = f"{file_path}.tmp_read_{int(time.time())}"

                try:
                    # Copy file to temporary location
                    shutil.copy2(file_path, temp_file_path)

                    # Read from temporary file
                    with open(temp_file_path, 'r', encoding='utf-8') as f:
                        content = f.read().strip()

                    # Clean up temporary file
                    os.remove(temp_file_path)

                    if not content:
                        return None

                    # Try to parse as JSON
                    return json.loads(content)

                except json.JSONDecodeError:
                    # If JSON parsing fails, try line-by-line parsing
                    return self._parse_partial_json(content)

                except Exception as e:
                    # Clean up temporary file on error
                    if os.path.exists(temp_file_path):
                        try:
                            os.remove(temp_file_path)
                        except:
                            pass

                    if attempt == max_retries - 1:
                        self.logger.warning(f"Failed to read log file after {max_retries} attempts: {e}")
                        return None

                    # Wait before retry
                    time.sleep(0.1 * (attempt + 1))

            except Exception as e:
                self.logger.warning(f"Error in attempt {attempt + 1} to read log file: {e}")
                if attempt == max_retries - 1:
                    return None
                time.sleep(0.1 * (attempt + 1))

        return None

    def _parse_partial_json(self, content: str) -> Optional[Any]:
        """
        Parse potentially partial JSON content.

        Args:
            content: Raw file content

        Returns:
            Parsed data or None if failed
        """
        try:
            # Try to parse as complete JSON first
            return json.loads(content)
        except json.JSONDecodeError:
            try:
                # If that fails, try to find complete JSON objects line by line
                lines = content.strip().split('\n')
                parsed_objects = []

                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        parsed_objects.append(obj)
                    except json.JSONDecodeError:
                        continue

                if parsed_objects:
                    return parsed_objects if len(parsed_objects) > 1 else parsed_objects[0]

                # Last resort: try to fix incomplete JSON
                if content.strip().endswith(','):
                    # Remove trailing comma and try again
                    fixed_content = content.strip().rstrip(',')
                    return json.loads(fixed_content)

            except Exception:
                pass

        return None

    def _extract_timestamp_from_log(self, log_entry: Any) -> Optional[str]:
        """Extract timestamp from a log entry."""
        if isinstance(log_entry, dict):
            # Look for common timestamp fields
            for field in ['timestamp', 'created_at', 'time', 'date']:
                if field in log_entry:
                    return str(log_entry[field])

        # Return current time as fallback
        return datetime.now().isoformat()

    def _extract_content_from_log(self, log_entry: Any) -> str:
        """Extract readable content from a log entry."""
        if isinstance(log_entry, dict):
            # Look for content in various formats
            if 'result' in log_entry and isinstance(log_entry['result'], dict):
                if 'content' in log_entry['result']:
                    content = log_entry['result']['content']
                    return str(content)

            if 'message' in log_entry and isinstance(log_entry['message'], dict):
                if 'content' in log_entry['message']:
                    content = log_entry['message']['content']
                    if isinstance(content, list) and len(content) > 0:
                        # Extract text from Claude message format
                        for item in content:
                            if isinstance(item, dict) and 'text' in item:
                                text = item['text']
                                return text
                    return str(content)

            # Fallback to raw content - return full JSON for better debugging
            import json
            try:
                return json.dumps(log_entry, indent=2)
            except (TypeError, ValueError):
                return str(log_entry)

        # For non-dict entries
        return str(log_entry)

    def _update_batch_parent_status(self, task_dict: Dict[str, Any], session) -> Dict[str, Any]:
        """
        Update batch parent task with current status of child tasks.
        
        Args:
            task_dict: Task dictionary from _task_to_dict
            session: Database session
            
        Returns:
            Updated task dictionary with batch status
        """
        # Safety check - ensure task_dict is not None
        if not task_dict:
            self.logger.warning("task_dict is None in _update_batch_parent_status")
            return task_dict or {}

        metadata = task_dict.get("metadata", {}) or {}
        batch_info = metadata.get("batch", {}) if metadata else {}

        # Only process if this is a batch parent task
        if not batch_info.get("is_parent", False):
            return task_dict

        child_task_ids = batch_info.get("child_task_ids", [])
        if not child_task_ids:
            return task_dict

        try:
            task_repo = self._get_task_repo(session)

            # Get child task details and statuses
            repositories_status, child_statuses = self._get_child_task_details(child_task_ids, task_repo)

            # Determine what the parent status should be
            current_status = task_dict.get("status") if task_dict else None
            new_parent_status = self._determine_batch_parent_status(child_statuses, current_status)

            # Update parent task status if needed
            self._update_parent_task_status(task_dict, new_parent_status, task_repo, child_statuses)

            # Create and persist batch result data
            result_data = self._create_batch_result_data(repositories_status, child_statuses, child_task_ids,
                                                         new_parent_status)
            task_dict["result"] = result_data
            self._persist_batch_result(task_dict["id"], result_data, task_repo)

            self.logger.debug(f"Updated batch parent status for task {task_dict['id']}",
                              extra={
                                  "task_id": task_dict["id"],
                                  "child_count": len(child_task_ids),
                                  "repositories_count": len(repositories_status),
                                  "parent_status": new_parent_status
                              })

        except Exception as e:
            self.logger.warning(f"Failed to update batch parent status for task {task_dict['id']}: {e}",
                                extra={"task_id": task_dict["id"], "error": str(e)})

        return task_dict

    # =====================================
    # Batch Task Management Methods
    # =====================================

    def _get_child_task_details(self, child_task_ids: List[str], task_repo) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Fetch and extract details from child tasks.
        
        Args:
            child_task_ids: List of child task IDs
            task_repo: Task repository instance
            
        Returns:
            Tuple of (repositories_status, child_statuses)
        """
        repositories_status = []
        child_statuses = []

        for child_task_id in child_task_ids:
            child_task = task_repo.get_by_id(child_task_id)
            if child_task:
                repo_info = self._extract_child_task_info(child_task, child_task_id)
                repositories_status.append(repo_info)
                child_statuses.append(child_task.status)
            else:
                # Child task not found - include with error status
                repositories_status.append({
                    "repository_url": "unknown",
                    "task_id": child_task_id,
                    "status": "not_found"
                })
                child_statuses.append("not_found")

        return repositories_status, child_statuses

    def _extract_child_task_info(self, child_task, child_task_id: str) -> Dict[str, Any]:
        """
        Extract repository information from a child task.
        
        Args:
            child_task: Child task entity
            child_task_id: Child task ID
            
        Returns:
            Dictionary with repository information
        """
        # Safety check for child_task
        if not child_task:
            return {
                "repository_url": "unknown",
                "task_id": child_task_id,
                "status": "not_found",
                "branch": None
            }

        child_metadata = child_task.metadata_dict or {}
        child_batch_info = child_metadata.get("batch", {})

        # Parse child task parameters from JSON
        child_parameters = {}
        if child_task.parameters:
            try:
                child_parameters = json.loads(child_task.parameters)
            except (json.JSONDecodeError, TypeError):
                child_parameters = {}

        # Get repository URL from multiple sources (parameters first, then metadata)
        repository_url = (
                child_parameters.get("repository_url") or
                child_batch_info.get("repository_url") or
                "unknown"
        )

        return {
            "repository_url": repository_url,
            "task_id": child_task_id,
            "status": child_task.status,
            "branch": child_parameters.get("branch") or child_batch_info.get("branch")
        }

    def _determine_batch_parent_status(self, child_statuses: List[str], current_status: str) -> str:
        """
        Determine what the parent batch task status should be based on child statuses.
        
        Args:
            child_statuses: List of child task statuses
            current_status: Current parent task status
            
        Returns:
            New parent task status
        """
        pending_statuses = ["queued", "in_progress", "pending"]
        failed_statuses = ["failed", "cancelled", "not_found"]

        has_pending = any(status in pending_statuses for status in child_statuses)
        has_failed = any(status in failed_statuses for status in child_statuses)
        all_completed = all(status == "completed" for status in child_statuses)
        all_cancelled = all(status == "cancelled" for status in child_statuses)

        # Determine new status based on child states
        if has_pending:
            return "in_progress"
        elif all_completed:
            return "completed"
        elif all_cancelled:
            return "cancelled"
        elif has_failed and not has_pending:
            return "failed"
        else:
            return current_status or "in_progress"

    def _update_parent_task_status(self, task_dict: Dict[str, Any], new_parent_status: str,
                                   task_repo, child_statuses: List[str]) -> None:
        """
        Update parent task status if it needs to change.
        
        Args:
            task_dict: Parent task dictionary
            new_parent_status: New status to set
            task_repo: Task repository instance
            child_statuses: List of child task statuses for logging
        """
        if not task_dict:
            self.logger.warning("task_dict is None in _update_parent_task_status")
            return

        current_status = task_dict.get("status")

        if current_status != new_parent_status and current_status != "cancelled":
            # Don't override cancelled status
            task_dict["status"] = new_parent_status

            # Update the actual task entity in database
            parent_task = task_repo.get_by_id(task_dict["id"])
            if parent_task:
                status_enum = self._convert_status_to_enum(new_parent_status)
                task_repo.update_status(task_dict["id"], status_enum)

            self._log_parent_status_change(task_dict["id"], current_status, new_parent_status, child_statuses)

    def _convert_status_to_enum(self, status_string: str):
        """
        Convert string status to TaskStatus enum.
        
        Args:
            status_string: Status as string
            
        Returns:
            TaskStatus enum value
        """
        from src.models.base import TaskStatus
        status_enum_map = {
            "created": TaskStatus.CREATED,
            "pending": TaskStatus.PENDING,
            "in_progress": TaskStatus.RUNNING,
            "completed": TaskStatus.COMPLETED,
            "failed": TaskStatus.FAILED,
            "cancelled": TaskStatus.CANCELLED
        }
        return status_enum_map.get(status_string, TaskStatus.RUNNING)

    def _log_parent_status_change(self, task_id: str, old_status: str, new_status: str,
                                  child_statuses: List[str]) -> None:
        """
        Log parent task status changes.
        
        Args:
            task_id: Parent task ID
            old_status: Previous status
            new_status: New status
            child_statuses: Child task statuses for context
        """
        pending_statuses = ["queued", "in_progress", "pending"]
        failed_statuses = ["failed", "cancelled", "not_found"]

        self.logger.info(f"Updated batch parent task status",
                         extra={
                             "task_id": task_id,
                             "old_status": old_status,
                             "new_status": new_status,
                             "child_statuses": child_statuses,
                             "has_pending": any(status in pending_statuses for status in child_statuses),
                             "has_failed": any(status in failed_statuses for status in child_statuses),
                             "all_completed": all(status == "completed" for status in child_statuses)
                         })

    def _create_batch_result_data(self, repositories_status: List[Dict[str, Any]], child_statuses: List[str],
                                  child_task_ids: List[str], parent_status: str) -> Dict[str, Any]:
        """
        Create batch result data structure.
        
        Args:
            repositories_status: Repository status information
            child_statuses: Child task statuses
            child_task_ids: Child task IDs
            parent_status: Parent task status
            
        Returns:
            Batch result data dictionary
        """
        pending_statuses = ["queued", "in_progress", "pending"]
        failed_statuses = ["failed", "cancelled", "not_found"]

        return {
            "repositories": repositories_status,
            "last_updated": self._get_current_timestamp(),
            "batch_summary": {
                "total_repositories": len(child_task_ids),
                "completed": sum(1 for status in child_statuses if status == "completed"),
                "pending": sum(1 for status in child_statuses if status in pending_statuses),
                "failed": sum(1 for status in child_statuses if status in failed_statuses),
                "overall_status": parent_status
            }
        }

    def _persist_batch_result(self, task_id: str, result_data: Dict[str, Any], task_repo) -> None:
        """
        Persist batch result data to database.
        
        Args:
            task_id: Parent task ID
            result_data: Result data to persist
            task_repo: Task repository instance
        """
        try:
            task_repo.update_result(task_id, result_data)
        except Exception as result_error:
            self.logger.warning(f"Failed to persist batch result to database for task {task_id}: {result_error}",
                                extra={"task_id": task_id, "error": str(result_error)})

    def _handle_batch_parent_cancellation(self, task_id: str, current_task, session) -> None:
        """
        Handle cancellation of batch parent task by cancelling all child tasks.
        
        Args:
            task_id: Parent task ID
            current_task: Current task entity
            session: Database session
        """
        try:
            child_task_ids = self._get_batch_child_task_ids(current_task)
            if not child_task_ids:
                return  # Not a batch parent or no children to cancel

            self._log_batch_cancellation_start(task_id, len(child_task_ids))

            # Cancel each child task
            task_repo = self._get_task_repo(session)
            cancelled_children = self._cancel_child_tasks(task_id, child_task_ids, task_repo)

            self._log_batch_cancellation_complete(task_id, len(child_task_ids), cancelled_children)

        except Exception as e:
            self.logger.error(f"Failed to handle batch parent cancellation for {task_id}: {e}",
                              extra={"parent_task_id": task_id, "error": str(e)})

    def _get_batch_child_task_ids(self, task) -> List[str]:
        """
        Extract child task IDs from a batch parent task.
        
        Args:
            task: Task entity
            
        Returns:
            List of child task IDs, empty if not a batch parent
        """
        metadata = task.metadata_dict
        batch_info = metadata.get("batch", {})

        if not batch_info.get("is_parent", False):
            return []  # Not a batch parent

        return batch_info.get("child_task_ids", [])

    def _cancel_child_tasks(self, parent_task_id: str, child_task_ids: List[str], task_repo) -> int:
        """
        Cancel individual child tasks.
        
        Args:
            parent_task_id: Parent task ID for logging
            child_task_ids: List of child task IDs to cancel
            task_repo: Task repository instance
            
        Returns:
            Number of successfully cancelled child tasks
        """
        from src.models.base import TaskStatus
        cancelled_children = 0

        for child_task_id in child_task_ids:
            try:
                child_task = task_repo.get_by_id(child_task_id)
                if child_task and self._is_task_cancellable(child_task):
                    task_repo.update_status(child_task_id, TaskStatus.CANCELLED)
                    cancelled_children += 1
                    self._log_child_cancellation(parent_task_id, child_task_id, child_task.status)

            except Exception as e:
                self._log_child_cancellation_error(parent_task_id, child_task_id, e)

        return cancelled_children

    def _is_task_cancellable(self, task) -> bool:
        """
        Check if a task can be cancelled.
        
        Args:
            task: Task entity
            
        Returns:
            True if task can be cancelled
        """
        from src.models.base import TaskStatus
        cancellable_statuses = [TaskStatus.CREATED.value, TaskStatus.PENDING.value, TaskStatus.RUNNING.value]
        return task.status in cancellable_statuses

    def _log_batch_cancellation_start(self, parent_task_id: str, child_count: int) -> None:
        """Log the start of batch cancellation."""
        self.logger.info(f"Cancelling {child_count} child tasks for batch parent {parent_task_id}",
                         extra={
                             "parent_task_id": parent_task_id,
                             "child_count": child_count
                         })

    def _log_batch_cancellation_complete(self, parent_task_id: str, total_children: int,
                                         cancelled_children: int) -> None:
        """Log the completion of batch cancellation."""
        self.logger.info(f"Cancelled {cancelled_children} child tasks for batch parent {parent_task_id}",
                         extra={
                             "parent_task_id": parent_task_id,
                             "total_children": total_children,
                             "cancelled_children": cancelled_children
                         })

    def _log_child_cancellation(self, parent_task_id: str, child_task_id: str, previous_status: str) -> None:
        """Log successful child task cancellation."""
        self.logger.debug(f"Cancelled child task {child_task_id}",
                          extra={
                              "parent_task_id": parent_task_id,
                              "child_task_id": child_task_id,
                              "previous_status": previous_status
                          })

    def _log_child_cancellation_error(self, parent_task_id: str, child_task_id: str, error: Exception) -> None:
        """Log child task cancellation errors."""
        self.logger.warning(f"Failed to cancel child task {child_task_id}: {error}",
                            extra={
                                "parent_task_id": parent_task_id,
                                "child_task_id": child_task_id,
                                "error": str(error)
                            })

    # =====================================
    # Utility Methods
    # =====================================

    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
