"""
Context manager for creating and managing contexts.
"""

import logging
from typing import Dict, Any, Optional
from .context import Context
from .keys import (
    TASK_ID, METADATA, WORKER_CONTEXT, EXECUTION_MODE,
    USER_ID, REQUEST_ID, LOG_CORRELATION_ID
)


class ContextManager:
    """
    Factory for creating contexts from different data sources.
    """
    
    @staticmethod
    def create_task_context(task_data: Dict[str, Any]) -> Context:
        """
        Create context from task data.
        
        Args:
            task_data: Task data dictionary containing task_id, metadata, etc.
            
        Returns:
            New context with task data
        """
        logger = logging.getLogger(__name__)
        
        # Extract task information
        task_id = task_data.get('task_id')
        metadata = task_data.get('metadata', {})
        
        # Create context values
        values = {
            TASK_ID: task_id,
            METADATA: metadata,
            EXECUTION_MODE: 'async',
            WORKER_CONTEXT: {
                'queue_processed': True,
                'worker_type': 'task_processor'
            }
        }
        
        # Add user_id if available in metadata
        if 'user_id' in metadata:
            values[USER_ID] = metadata['user_id']
        
        # Create context
        ctx = Context(values=values)
        
        logger.debug(f"Created task context for task_id: {task_id}, correlation_id: {ctx.get(LOG_CORRELATION_ID)}")
        
        return ctx
    
    @staticmethod
    def create_api_context(request_data: Dict[str, Any]) -> Context:
        """
        Create context from API request data.
        
        Args:
            request_data: Request data dictionary containing request_id, user_id, etc.
            
        Returns:
            New context with request data
        """
        logger = logging.getLogger(__name__)
        
        # Extract request information
        request_id = request_data.get('request_id')
        user_id = request_data.get('user_id')
        
        # Create context values
        values = {
            REQUEST_ID: request_id,
            USER_ID: user_id,
            EXECUTION_MODE: 'sync',
            METADATA: request_data.get('metadata', {})
        }
        
        # Create context
        ctx = Context(values=values)
        
        logger.debug(f"Created API context for request_id: {request_id}, user_id: {user_id}, correlation_id: {ctx.get(LOG_CORRELATION_ID)}")
        
        return ctx
    
    @staticmethod
    def create_background_context(operation_name: str, metadata: Optional[Dict[str, Any]] = None) -> Context:
        """
        Create context for background operations.
        
        Args:
            operation_name: Name of the background operation
            metadata: Optional metadata
            
        Returns:
            New context for background operation
        """
        logger = logging.getLogger(__name__)
        
        # Create context values
        values = {
            EXECUTION_MODE: 'background',
            METADATA: metadata or {},
            'operation_name': operation_name
        }
        
        # Create context
        ctx = Context(values=values)
        
        logger.debug(f"Created background context for operation: {operation_name}, correlation_id: {ctx.get(LOG_CORRELATION_ID)}")
        
        return ctx
    
    @staticmethod
    def create_child_context(parent_ctx: Context, **additional_values) -> Context:
        """
        Create child context with additional values.
        
        Args:
            parent_ctx: Parent context
            **additional_values: Additional key-value pairs to add
            
        Returns:
            New child context
        """
        child_ctx = Context(parent=parent_ctx, values=additional_values)
        
        logger = logging.getLogger(__name__)
        logger.debug(f"Created child context with parent correlation_id: {parent_ctx.get(LOG_CORRELATION_ID)}, child correlation_id: {child_ctx.get(LOG_CORRELATION_ID)}")
        
        return child_ctx