"""
Task service module for managing tasks.
"""

import logging
import uuid
import json
import asyncio
import time
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional

# Import from new architecture
from src.models.task import Task, TaskStatus
# from src.models.workflow_registry import WorkflowRegistry, validate_workflow_name  # Removed - agents catalogue is the new workflow system
from src.services.task_service import TaskService
from src.providers.database.provider import DatabaseProvider
from src.providers.config_loader import get_config

# Set up logging
logger = logging.getLogger(__name__)

# Import system logger
from src.utils.system_logger import system_logger

class TaskManager:
    """Legacy task manager service for backward compatibility"""
    
    def __init__(self):
        """Initialize the task manager"""
        self._running_tasks = {}
        self._event_loop = None
        self._loop_thread = None
        self._shutdown_event = threading.Event()
        self.task_queue = asyncio.Queue()
        
        # Initialize the new service layer
        config = get_config()
        self.db_provider = DatabaseProvider()
        self.db_provider.initialize(config)
        self.task_service = TaskService(config, self.db_provider)
        
        self._start_event_loop()
    
    def _start_event_loop(self):
        """Start the event loop in a background thread"""
        def run_loop():
            """Run the event loop in the background thread"""
            self._event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._event_loop)
            
            logger.info("Task manager event loop started")
            
            # Run the event loop until shutdown
            try:
                self._event_loop.run_forever()
            except Exception as e:
                logger.exception(f"Error in task manager event loop: {e}")
            finally:
                self._event_loop.close()
                logger.info("Task manager event loop stopped")
        
        # Start the background thread
        self._loop_thread = threading.Thread(target=run_loop, daemon=True)
        self._loop_thread.start()
        
        # Wait a bit for the loop to start
        time.sleep(0.1)
    
    def get_event_loop(self):
        """Get the event loop"""
        if self._event_loop is None or self._event_loop.is_closed():
            self._start_event_loop()
        return self._event_loop
    
    def shutdown(self):
        """Shutdown the task manager and stop the event loop"""
        if self._event_loop and not self._event_loop.is_closed():
            self._event_loop.call_soon_threadsafe(self._event_loop.stop)
        
        self._shutdown_event.set()
        
        if self._loop_thread and self._loop_thread.is_alive():
            self._loop_thread.join(timeout=5)
    
    def _format_timestamp(self, timestamp):
        """Convert Unix timestamp to ISO format string"""
        if timestamp is None:
            return None
        if isinstance(timestamp, int):
            return datetime.fromtimestamp(timestamp).isoformat()
        return timestamp
    
    def create_task(self, name: str, description: str = None, parameters: Dict[str, Any] = None) -> str:
        """
        Create a new task.
        
        Args:
            name: The name of the task
            description: An optional description of the task
            parameters: Optional parameters for the task
            
        Returns:
            The ID of the created task
        """
        try:
            # Use the new service layer
            task = self.task_service.create_task(
                name=name,
                description=description,
                parameters=parameters
            )
            
            task_id = task["id"]
            
            # Log task creation with system logger
            system_logger.log_task_lifecycle(
                task_id=task_id,
                status="created",
                metadata={
                    "task_type": parameters.get("type") if parameters else None,
                    "priority": parameters.get("priority") if parameters else None,
                    "created_at": self._format_timestamp(task.get("created_at"))
                }
            )
            
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to create task: {e}")
            raise
    
    def update_task_status(self, task_id: str, status: TaskStatus, progress: int = None, 
                          result: Dict[str, Any] = None) -> bool:
        """Update task status"""
        try:
            # Use the new service layer
            self.task_service.update_task_status(task_id, status, progress)
            
            # Store result if provided
            if result is not None:
                self.task_service.update_task_result(task_id, result)
                logger.info(f"Task {task_id} result stored successfully")
            
            # Log with system logger
            system_logger.log_system_event(
                task_id=task_id,
                event="task_status_updated",
                details={
                    "new_status": status.value,
                    "progress": progress,
                    "updated_at": time.time(),
                    "result_stored": result is not None
                }
            )
            
            logger.info(f"Updated task {task_id} status to {status.value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update task {task_id} status: {e}")
            system_logger.log_error(
                task_id=task_id,
                error_type="task_status_update_error",
                error_message=str(e),
                traceback_str=str(e)
            )
            return False
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a task by ID.
        
        Args:
            task_id: The ID of the task
            
        Returns:
            The task as a dictionary, or None if not found
        """
        try:
            task = self.task_service.get_task(task_id)
            if not task:
                return None
            return self._task_to_dict(task)
        except Exception as e:
            logger.error(f"Failed to get task {task_id}: {e}")
            return None
    
    def get_task_status(self, task_id: str) -> Optional[str]:
        """
        Get the current status of a task.
        
        Args:
            task_id: The ID of the task
            
        Returns:
            The task status as a string, or None if not found
        """
        try:
            task = self.task_service.get_task(task_id)
            if not task:
                return None
            return task.get("status")
        except Exception as e:
            logger.error(f"Failed to get task {task_id} status: {e}")
            return None
    
    def _task_to_dict(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a Task dictionary to a standardized dictionary"""
        # Task is already a dictionary from the service layer
        result = {
            "id": task.get("id"),
            "name": task.get("name"),
            "description": task.get("description"),
            "status": task.get("status"),
            "progress": task.get("progress", 0),
            "created_at": self._format_timestamp(task.get("created_at")),
            "updated_at": self._format_timestamp(task.get("updated_at"))
        }
        
        # Parse parameters if they exist
        parameters = task.get("parameters", {})
        if isinstance(parameters, str):
            try:
                result["parameters"] = json.loads(parameters)
            except json.JSONDecodeError:
                result["parameters"] = {}
        else:
            result["parameters"] = parameters or {}
            
        # Parse result if it exists
        task_result = task.get("result", {})
        if isinstance(task_result, str):
            try:
                result["result"] = json.loads(task_result)
            except json.JSONDecodeError:
                result["result"] = {}
        else:
            result["result"] = task_result or {}
            
        # Parse metadata if it exists
        metadata = task.get("metadata", {})
        if isinstance(metadata, str):
            try:
                result["metadata"] = json.loads(metadata)
            except json.JSONDecodeError:
                result["metadata"] = {}
        else:
            result["metadata"] = metadata or {}
            
        return result
    
    def list_tasks(self, status: TaskStatus = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        List tasks with optional filters.
        
        Args:
            status: Optional status filter
            limit: Maximum number of tasks to return
            
        Returns:
            List of tasks as dictionaries
        """
        try:
            # Call the service with supported parameters
            result = self.task_service.list_tasks(status=status, limit=limit)
            tasks = result.get('tasks', [])
            
            # Convert tasks to standardized format
            return [self._task_to_dict(task) for task in tasks]
            
        except Exception as e:
            logger.error(f"Failed to list tasks: {e}")
            return []
    
    def submit_task(self, task_id: str, handler_func=None) -> bool:
        """Submit a task for execution"""
        try:
            task = self.get_task(task_id)
            if not task:
                logger.error(f"Task {task_id} not found for submission")
                return False
            
            # Update status to running
            self.update_task_status(task_id, TaskStatus.RUNNING)
            
            # Log task submission with system logger
            system_logger.log_system_event(
                task_id=task_id,
                event="task_submitted",
                details={
                    "submitted_at": time.time()
                }
            )
            
            # If handler is provided, execute the task
            if handler_func:
                # Schedule the task execution in the event loop
                if self._event_loop and not self._event_loop.is_closed():
                    asyncio.run_coroutine_threadsafe(
                        self._execute_task(task_id, handler_func),
                        self._event_loop
                    )
                else:
                    logger.error(f"Event loop not available for task {task_id}")
                    return False
            
            logger.info(f"Submitted task {task_id} for execution")
            
            return True
        except Exception as e:
            logger.error(f"Failed to submit task {task_id}: {e}")
            # Log error with system logger
            system_logger.log_error(
                task_id=task_id,
                error_type="task_submission_error",
                error_message=str(e),
                traceback_str=str(e)
            )
            return False
    
    async def _execute_task(self, task_id: str, handler_func):
        """Execute a task asynchronously"""
        try:
            logger.info(f"Starting execution of task {task_id}")
            
            # Get task details to extract parameters
            task = self.get_task(task_id)
            if not task:
                logger.error(f"Task {task_id} not found during execution")
                return
            
            # Extract parameters and workflow config
            parameters = task.get("parameters", {})
            workflow_config = task.get("workflow_config", {})
            
            # Log task execution start with system logger
            system_logger.log_system_event(
                task_id=task_id,
                event="task_execution_started",
                details={
                    "started_at": time.time(),
                    "handler": handler_func.__name__ if hasattr(handler_func, '__name__') else str(handler_func)
                }
            )
            
            # Execute the task with task_id, parameters, and workflow_config
            result = await handler_func(task_id, parameters, workflow_config)
            
            # Update task status to completed
            self.update_task_status(task_id, TaskStatus.COMPLETED, progress=100, result=result)
            
            # Log task completion with system logger
            system_logger.log_system_event(
                task_id=task_id,
                event="task_execution_completed",
                details={
                    "completed_at": time.time(),
                    "result_size": len(str(result)) if result else 0
                }
            )
            
            logger.info(f"Task {task_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            
            # Update task status to failed
            self.update_task_status(task_id, TaskStatus.FAILED, progress=0, result={"error": str(e)})
            
            # Log task failure with system logger
            system_logger.log_error(
                task_id=task_id,
                error_type="task_execution_error",
                error_message=str(e),
                traceback_str=str(e)
            )
            
        finally:
            # Remove from running tasks
            if task_id in self._running_tasks:
                del self._running_tasks[task_id]
    
    def get_available_workflows(self) -> List[Dict[str, str]]:
        """
        Get all available workflows from the registry.
        
        Returns:
            List of workflow dictionaries with name and description
        """
        # Workflow registry removed - return empty list, use agents catalogue instead
        return []
    
    def get_workflow_by_name(self, workflow_name: str) -> Optional[Dict[str, Any]]:
        """
        Get workflow information by name.
        
        Args:
            workflow_name: The name of the workflow
            
        Returns:
            The workflow information as a dictionary, or None if not found
        """
        # Workflow registry removed - return legacy workflow info
        return {
            "name": workflow_name,
            "description": f"Legacy workflow: {workflow_name}",
            "status": "deprecated"
        }

# Create a global task manager instance
task_manager = TaskManager() 