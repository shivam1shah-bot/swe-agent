"""
Task repository for the SWE Agent.

Provides data access operations for Task entities.
"""

from abc import abstractmethod
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import json

from .base import BaseRepository, SQLAlchemyBaseRepository
from .exceptions import EntityNotFoundError, QueryExecutionError, TransactionError
from src.models import Task, TaskStatus
from src.providers.logger import Logger


class TaskRepository(BaseRepository[Task]):
    """
    Abstract Task repository interface.

    Defines task-specific data access operations.
    """

    @abstractmethod
    def get_by_workflow_name(self, workflow_name: str, limit: Optional[int] = None) -> List[Task]:
        """
        Get tasks by workflow name.

        Args:
            workflow_name: Name of the workflow
            limit: Maximum number of tasks to return

        Returns:
            List of tasks for the specified workflow
        """
        pass

    @abstractmethod
    def get_by_status(self, status: TaskStatus, limit: Optional[int] = None, offset: Optional[int] = None) -> List[Task]:
        """
        Get tasks by status.

        Args:
            status: Task status
            limit: Maximum number of tasks to return

        Returns:
            List of tasks with the specified status
        """
        pass

    @abstractmethod
    def get_by_statuses(self, statuses: List[TaskStatus], limit: Optional[int] = None, offset: Optional[int] = None) -> List[Task]:
        """
        Get tasks by multiple statuses.

        Args:
            statuses: List of task statuses
            limit: Maximum number of tasks to return
            offset: Number of tasks to skip

        Returns:
            List of tasks with any of the specified statuses
        """
        pass

    @abstractmethod
    def get_by_workflow_and_status(
        self,
        workflow_name: str,
        status: TaskStatus,
        limit: Optional[int] = None
    ) -> List[Task]:
        """
        Get tasks by workflow name and status.

        Args:
            workflow_name: Name of the workflow
            status: Task status
            limit: Maximum number of tasks to return

        Returns:
            List of tasks matching both criteria
        """
        pass

    @abstractmethod
    def get_recent_tasks(self, limit: int = 10) -> List[Task]:
        """
        Get recent tasks ordered by creation time.

        Args:
            limit: Maximum number of tasks to return

        Returns:
            List of recent tasks
        """
        pass

    @abstractmethod
    def update_status(self, task_id: str, status: TaskStatus) -> Task:
        """
        Update task status.

        Args:
            task_id: Task identifier
            status: New status

        Returns:
            Updated task

        Raises:
            EntityNotFoundError: If task does not exist
        """
        pass

    @abstractmethod
    def update_progress(self, task_id: str, progress: int) -> Task:
        """
        Update task progress.

        Args:
            task_id: Task identifier
            progress: Progress percentage (0-100)

        Returns:
            Updated task

        Raises:
            EntityNotFoundError: If task does not exist
        """
        pass

    @abstractmethod
    def update_result(self, task_id: str, result: Dict[str, Any]) -> Task:
        """
        Update task result.

        Args:
            task_id: Task identifier
            result: Task result data

        Returns:
            Updated task

        Raises:
            EntityNotFoundError: If task does not exist
        """
        pass

    @abstractmethod
    def update_metadata(self, task_id: str, metadata: Dict[str, Any]) -> Task:
        """
        Update task metadata.

        Args:
            task_id: Task identifier
            metadata: Task metadata dict

        Returns:
            Updated task

        Raises:
            EntityNotFoundError: If task does not exist
        """
        pass

    @abstractmethod
    def search_tasks(
        self,
        filters: Dict[str, Any],
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Task]:
        """
        Search tasks with complex filters.

        Args:
            filters: Dictionary of field filters
            limit: Maximum number of tasks to return
            offset: Number of tasks to skip

        Returns:
            List of matching tasks
        """
        pass


class SQLAlchemyTaskRepository(SQLAlchemyBaseRepository[Task], TaskRepository):
    """
    SQLAlchemy implementation of TaskRepository.

    Provides concrete data access operations using SQLAlchemy ORM.
    """

    def __init__(self, session: Session):
        """
        Initialize the task repository.

        Args:
            session: SQLAlchemy session
        """
        super().__init__(session, Task)
        self.logger = Logger("TaskRepository")

    def get_by_workflow_name(self, workflow_name: str, limit: Optional[int] = None) -> List[Task]:
        """Get tasks by workflow name using SQLAlchemy - deprecated, returns empty list."""
        self.logger.warning("get_by_workflow_name is deprecated - workflow_name field removed from Task model")
        return []

    def get_by_status(self, status: TaskStatus, limit: Optional[int] = None, offset: Optional[int] = None) -> List[Task]:
        """Get tasks by status using SQLAlchemy with pagination and proper ordering."""
        try:
            from sqlalchemy import case, desc
            
            # For status-specific queries, we still want proper ordering within that status
            query = self.session.query(Task).filter(Task.status == status.value)
            query = query.order_by(desc(Task.created_at))

            if offset:
                query = query.offset(offset)
            if limit:
                query = query.limit(limit)

            return query.all()
        except SQLAlchemyError as e:
            self.logger.error("Failed to get tasks by status",
                              extra={"status": status.value, "limit": limit, "offset": offset, "error": str(e)})
            raise QueryExecutionError(f"get_by_status({status.value})", str(e))

    def get_by_workflow_and_status(
        self,
        workflow_name: str,
        status: TaskStatus,
        limit: Optional[int] = None
    ) -> List[Task]:
        """Get tasks by workflow name and status using SQLAlchemy - deprecated, returns empty list."""
        self.logger.warning("get_by_workflow_and_status is deprecated - workflow_name field removed from Task model")
        return []

    def get_recent_tasks(self, limit: int = 10) -> List[Task]:
        """Get recent tasks using SQLAlchemy."""
        try:
            return self.session.query(Task).order_by(Task.created_at.desc()).limit(limit).all()
        except SQLAlchemyError as e:
            self.logger.error("Failed to get recent tasks",
                              extra={"limit": limit, "error": str(e)})
            raise QueryExecutionError(f"get_recent_tasks(limit={limit})", str(e))

    def update_status(self, task_id: str, status: TaskStatus) -> Task:
        """Update task status using SQLAlchemy."""
        try:
            task = self.get_by_id(task_id)
            if not task:
                raise EntityNotFoundError("Task", task_id)

            task.status = status.value

            import time
            task.updated_at = int(time.time())

            self.session.flush()
            return task
        except SQLAlchemyError as e:
            error_str = str(e).lower()
            if "lost connection" in error_str or "2013" in error_str:
                self.logger.error("Database connection lost while updating task status",
                                task_id=task_id, error=str(e), error_type="connection_timeout")
            else:
                self.logger.error("Failed to update task status",
                                  extra={"task_id": task_id, "error": str(e)})
            raise TransactionError(f"update_status({task_id})", str(e))

    def update_progress(self, task_id: str, progress: int) -> Task:
        """Update task progress using SQLAlchemy."""
        try:
            task = self.get_by_id(task_id)
            if not task:
                raise EntityNotFoundError("Task", task_id)

            # Validate progress range
            if not 0 <= progress <= 100:
                raise ValueError(f"Progress must be between 0 and 100, got {progress}")

            task.progress = progress

            import time
            task.updated_at = int(time.time())

            self.session.flush()
            return task
        except SQLAlchemyError as e:
            self.logger.error("Failed to update task progress", task_id=task_id, error=str(e))
            raise TransactionError(f"update_progress({task_id})", str(e))

    def update_result(self, task_id: str, result: Dict[str, Any]) -> Task:
        """Update task result using SQLAlchemy."""
        try:
            task = self.get_by_id(task_id)
            if not task:
                raise EntityNotFoundError("Task", task_id)

            # Convert result to JSON string for storage
            task.result = json.dumps(result) if result else None

            import time
            task.updated_at = int(time.time())

            self.session.flush()
            return task
        except SQLAlchemyError as e:
            self.logger.error("Failed to update task result", task_id=task_id, error=str(e))
            raise TransactionError(f"update_result({task_id})", str(e))

    def update_metadata(self, task_id: str, metadata: Dict[str, Any]) -> Task:
        """Update task metadata using SQLAlchemy."""
        try:
            task = self.get_by_id(task_id)
            if not task:
                raise EntityNotFoundError("Task", task_id)

            # Convert metadata to JSON string for storage in task_metadata field
            task.task_metadata = json.dumps(metadata) if metadata else None

            import time
            task.updated_at = int(time.time())

            self.session.flush()
            return task
        except SQLAlchemyError as e:
            self.logger.error("Failed to update task metadata", task_id=task_id, error=str(e))
            raise TransactionError(f"update_metadata({task_id})", str(e))

    def search_tasks(
        self,
        filters: Dict[str, Any],
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Task]:
        """Search tasks with complex filters using SQLAlchemy."""
        try:
            query = self.session.query(Task)

            # Apply filters
            for field, value in filters.items():
                if hasattr(Task, field):
                    if field == 'status' and isinstance(value, TaskStatus):
                        query = query.filter(getattr(Task, field) == value.value)
                    else:
                        query = query.filter(getattr(Task, field) == value)

            # Default ordering
            query = query.order_by(Task.created_at.desc())

            # Apply pagination
            if offset:
                query = query.offset(offset)
            if limit:
                query = query.limit(limit)

            return query.all()
        except SQLAlchemyError as e:
            self.logger.error("Failed to search tasks with filters", filters=filters, error=str(e))
            raise QueryExecutionError(f"search_tasks({filters})", str(e))

    def get_by_id(self, task_id: str) -> Optional[Task]:
        """Override to add error handling and connection timeout detection."""
        try:
            return super().get_by_id(task_id)
        except SQLAlchemyError as e:
            error_str = str(e).lower()
            if "lost connection" in error_str or "2013" in error_str:
                self.logger.error("Database connection lost while getting task by ID",
                                task_id=task_id, error=str(e), error_type="connection_timeout")
            else:
                self.logger.error("Failed to get task by ID", task_id=task_id, error=str(e))
            raise QueryExecutionError(f"get_by_id({task_id})", str(e))

    def create(self, task: Task) -> Task:
        """Override to add error handling and validation."""
        try:
            # Set timestamps if not set
            import time
            current_time = int(time.time())
            if not task.created_at:
                task.created_at = current_time
            if not task.updated_at:
                task.updated_at = current_time

            return super().create(task)
        except SQLAlchemyError as e:
            self.logger.error("Failed to create task",
                              extra={"error": str(e)})
            raise TransactionError("create_task", str(e))

    def get_all(self, limit: Optional[int] = None, offset: Optional[int] = None) -> List[Task]:
        """Get all tasks with proper ordering: running/pending first, then by created_at DESC."""
        try:
            from sqlalchemy import case, desc
            
            # Create ordering: running/pending tasks first, then by created_at DESC
            status_priority = case(
                (Task.status == TaskStatus.RUNNING.value, 1),
                (Task.status == TaskStatus.PENDING.value, 2),
                else_=3
            )
            
            query = self.session.query(Task).order_by(
                status_priority,
                desc(Task.created_at)
            )
            
            if offset:
                query = query.offset(offset)
            if limit:
                query = query.limit(limit)
                
            return query.all()
        except SQLAlchemyError as e:
            self.logger.error("Failed to get all tasks with ordering",
                              extra={"limit": limit, "offset": offset, "error": str(e)})
            raise QueryExecutionError(f"get_all(limit={limit}, offset={offset})", str(e))

    def get_by_statuses(self, statuses: List[TaskStatus], limit: Optional[int] = None, offset: Optional[int] = None) -> List[Task]:
        """Get tasks by multiple statuses using SQLAlchemy with pagination and proper ordering."""
        try:
            from sqlalchemy import case, desc
            
            # Convert status enums to values
            status_values = [status.value for status in statuses]
            
            # Create ordering: running/pending tasks first, then by created_at DESC
            status_priority = case(
                (Task.status == TaskStatus.RUNNING.value, 1),
                (Task.status == TaskStatus.PENDING.value, 2),
                else_=3
            )
            
            query = self.session.query(Task).filter(Task.status.in_(status_values))
            query = query.order_by(status_priority, desc(Task.created_at))

            if offset:
                query = query.offset(offset)
            if limit:
                query = query.limit(limit)

            return query.all()
        except SQLAlchemyError as e:
            self.logger.error("Failed to get tasks by statuses",
                              extra={"statuses": [s.value for s in statuses], "limit": limit, "offset": offset, "error": str(e)})
            raise QueryExecutionError(f"get_by_statuses({[s.value for s in statuses]})", str(e))

    def get_by_connector_filter(
        self,
        user_email: Optional[str] = None,
        connector: Optional[str] = None,
        status: Optional[TaskStatus] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Task]:
        """Filter tasks by user_email and/or connector stored in task_metadata JSON."""
        try:
            from sqlalchemy import case, desc, func
            status_priority = case(
                (Task.status == TaskStatus.RUNNING.value, 1),
                (Task.status == TaskStatus.PENDING.value, 2),
                else_=3
            )
            query = self.session.query(Task)

            if user_email:
                query = query.filter(
                    func.json_unquote(func.json_extract(Task.task_metadata, '$.connector.user_email')).like(f'%{user_email}%')
                )
            if connector:
                query = query.filter(
                    func.json_unquote(func.json_extract(Task.task_metadata, '$.connector.name')) == connector
                )
            if status:
                query = query.filter(Task.status == status.value)

            query = query.order_by(status_priority, desc(Task.created_at))
            if offset:
                query = query.offset(offset)
            if limit:
                query = query.limit(limit)
            return query.all()
        except SQLAlchemyError as e:
            self.logger.error("Failed to get tasks by connector filter", extra={"error": str(e)})
            raise QueryExecutionError(f"get_by_connector_filter()", str(e))