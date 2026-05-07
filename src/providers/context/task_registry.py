"""
Task Context Registry for cross-thread context access.

Extends the existing context system to enable task context lookup
across thread boundaries for subprocess tracking and cancellation.
"""

import threading
import logging
from typing import Dict, Optional
from .context import Context
from .keys import WORKER_CONTEXT, TASK_ID

logger = logging.getLogger(__name__)


class TaskContextRegistry:
    """
    Global registry for task contexts to enable cross-thread access.
    
    This registry allows any thread to look up the context (and worker instance)
    for a running task, enabling subprocess tracking across thread boundaries.
    """
    
    _registry: Dict[str, Context] = {}
    _lock = threading.Lock()
    
    @classmethod
    def register_task_context(cls, task_id: str, context: Context) -> None:
        """
        Register a task context for cross-thread access.
        
        Args:
            task_id: Unique task identifier
            context: Task context containing worker instance and metadata
        """
        if not task_id:
            logger.warning("Attempted to register context with empty task_id")
            return
            
        with cls._lock:
            cls._registry[task_id] = context
            
        logger.debug(f"Registered task context: {task_id}, correlation_id: {context.get('log_correlation_id')}")
    
    @classmethod
    def get_task_context(cls, task_id: str) -> Optional[Context]:
        """
        Get task context by task_id.
        
        Args:
            task_id: Task identifier to look up
            
        Returns:
            Context object if found, None otherwise
        """
        if not task_id:
            return None
            
        with cls._lock:
            return cls._registry.get(task_id)
    
    @classmethod
    def get_worker_for_task(cls, task_id: str):
        """
        Get worker instance for a task.
        
        Args:
            task_id: Task identifier to look up
            
        Returns:
            Worker instance if found, None otherwise
        """
        context = cls.get_task_context(task_id)
        if context:
            worker_context = context.get(WORKER_CONTEXT, {})
            worker_instance = worker_context.get("worker_instance")
            
            if worker_instance:
                # Handle both worker instances and string values gracefully
                worker_id = getattr(worker_instance, 'worker_id', str(worker_instance))
                logger.debug(f"Found worker instance for task {task_id}: {worker_id}")
                return worker_instance
            else:
                logger.debug(f"No worker instance found in context for task {task_id}")
        else:
            logger.debug(f"No context found for task {task_id}")
            
        return None
    
    @classmethod
    def cleanup_task(cls, task_id: str) -> None:
        """
        Clean up completed task context.
        
        Args:
            task_id: Task identifier to clean up
        """
        if not task_id:
            return
            
        with cls._lock:
            removed_context = cls._registry.pop(task_id, None)
            
        if removed_context:
            logger.debug(f"Cleaned up task context: {task_id}")
        else:
            logger.debug(f"No context to clean up for task: {task_id}")
    
    @classmethod
    def get_registry_stats(cls) -> Dict[str, int]:
        """
        Get registry statistics for monitoring.
        
        Returns:
            Dictionary with registry statistics
        """
        with cls._lock:
            active_tasks = len(cls._registry)
            
        return {
            "active_task_contexts": active_tasks
        }
    
    @classmethod
    def list_active_tasks(cls) -> list:
        """
        List all active task IDs in the registry.
        
        Returns:
            List of active task IDs
        """
        with cls._lock:
            return list(cls._registry.keys())
