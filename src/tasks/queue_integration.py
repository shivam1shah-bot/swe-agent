"""
Queue Integration for SWE Agent Task System.
Provides integration between the existing task management and the queue system.
"""

import logging
import uuid
from typing import Dict, Any, Optional
from datetime import datetime

from src.worker.queue_manager import QueueManager
from src.models.base import TaskStatus
from .service import task_manager

logger = logging.getLogger(__name__)


class TaskQueueIntegration:
    """
    Integrates the task management system with the queue system for async processing.
    """
    
    def __init__(self):
        """Initialize the queue integration."""
        self.queue_manager = self._create_queue_manager()
    
    def _create_queue_manager(self):
        """Create and initialize queue manager."""
        try:
            from src.worker.queue_manager import QueueManager
            return QueueManager()
        except Exception as e:
            # Log error but don't fail initialization - allows system to start
            # Queue functionality will be disabled
            logger.error(f"Failed to initialize queue manager: {e}")
            return None
    
    def is_queue_available(self) -> bool:
        """Check if queue system is available."""
        return self.queue_manager is not None
    
    def submit_task_async(
        self, 
        task_type: str, 
        parameters: Dict[str, Any], 
        name: Optional[str] = None,
        description: Optional[str] = None,
        priority: int = 0
    ) -> Optional[str]:
        """
        Submit a task for async processing via the queue system.
        
        Args:
            task_type: Type of task to process
            parameters: Task parameters
            name: Optional task name
            description: Optional task description
            priority: Task priority (higher = more important)
            
        Returns:
            Task ID if successful, None otherwise
        """
        if not self.is_queue_available():
            logger.error("Queue system not available, cannot submit async task")
            return None
        
        try:
            # Create task in the database first
            task_id = task_manager.create_task(
                name=name or f"Async {task_type} task",
                description=description or f"Async processing of {task_type}",
                parameters=parameters
            )
            
            # Prepare task data for queue
            task_data = {
                'task_id': task_id,
                'task_type': task_type,
                'parameters': parameters,
                'priority': priority,
                'created_at': datetime.now().isoformat(),
                'submitted_by': 'task_system'
            }
            
            # Send to queue
            success = self.queue_manager.send_task(task_data)
            
            if success:
                # Update task status to indicate it's queued
                task_manager.update_task_status(
                    task_id,
                    TaskStatus.PENDING,
                    0,
                    "Task queued for async processing"
                )
                logger.info(f"Task {task_id} submitted to queue successfully")
                return task_id
            else:
                # If queue submission failed, mark task as failed
                task_manager.update_task_status(
                    task_id,
                    TaskStatus.FAILED,
                    0,
                    "Failed to submit task to queue"
                )
                logger.error(f"Failed to submit task {task_id} to queue")
                return None
                
        except Exception as e:
            logger.error(f"Error submitting async task: {e}")
            return None
    
    def submit_autonomous_agent_task(
        self,
        repository_url: str,
        task_description: str,
        branch: Optional[str] = None,
        **kwargs
    ) -> Optional[str]:
        """Submit an autonomous agent task for async processing."""
        parameters = {
            'repository_url': repository_url,
            'task_description': task_description,
            'branch': branch or 'main',
            **kwargs
        }
        
        return self.submit_task_async(
            task_type='autonomous_agent',
            parameters=parameters,
            name=f"Autonomous Agent: {repository_url}",
            description=f"Process: {task_description}"
        )

    def submit_agents_catalogue_task(
        self,
        usecase_name: str,
        parameters: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Optional[str]:
        """Submit an agents catalogue execution task for async processing."""
        task_parameters = {
            **parameters,
            **kwargs
        }
        
        task_metadata = {
            'usecase_name': usecase_name,
            'created_via': 'agents_catalogue_api',
            **(metadata or {})
        }
        
        # Create task in the database first
        try:
            task_id = task_manager.create_task(
                name=f"Agents Catalogue: {usecase_name}",
                description=f"Execute agents catalogue service: {usecase_name}",
                parameters=task_parameters
            )
            
            # Prepare task data for queue
            task_data = {
                'task_id': task_id,
                'task_type': 'agents_catalogue_execution',
                'parameters': task_parameters,
                'metadata': task_metadata,
                'priority': kwargs.get('priority', 0),
                'created_at': datetime.now().isoformat(),
                'submitted_by': 'agents_catalogue_api'
            }
            
            # Send to queue
            success = self.queue_manager.send_task(task_data)
            
            if success:
                # Update task status to indicate it's queued
                task_manager.update_task_status(
                    task_id,
                    TaskStatus.PENDING,
                    0,
                    "Task queued for async processing"
                )
                logger.info(f"Agents catalogue task {task_id} submitted to queue successfully")
                return task_id
            else:
                # If queue submission failed, mark task as failed
                task_manager.update_task_status(
                    task_id,
                    TaskStatus.FAILED,
                    0,
                    "Failed to submit task to queue"
                )
                logger.error(f"Failed to submit agents catalogue task {task_id} to queue")
                return None
                
        except Exception as e:
            logger.error(f"Error submitting agents catalogue task: {e}")
            return None
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        if not self.is_queue_available():
            return {'error': 'Queue system not available'}
        
        try:
            return self.queue_manager.get_queue_stats()
        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            return {'error': str(e)}
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check of the queue integration."""
        try:
            if not self.is_queue_available():
                return {
                    'healthy': False,
                    'error': 'Queue manager not initialized',
                    'queue_available': False
                }
            
            # Get queue stats as a health indicator
            stats = self.get_queue_stats()
            healthy = 'error' not in stats
            
            return {
                'healthy': healthy,
                'queue_available': True,
                'queue_type': self.queue_manager.queue_type,
                'queue_stats': stats,
                'last_check': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'error': str(e),
                'queue_available': False,
                'last_check': datetime.now().isoformat()
            }


# Global instance for easy access
queue_integration = TaskQueueIntegration() 