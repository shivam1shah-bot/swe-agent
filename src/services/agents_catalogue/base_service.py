"""
Base service interface for agents catalogue.

This module defines the common interface that all agents catalogue services must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

# Import the new context system
from src.providers.context import Context, TASK_ID, METADATA, EXECUTION_MODE, LOG_CORRELATION_ID


class BaseAgentsCatalogueService(ABC):
    """Abstract base class for all agents catalogue services."""
    
    @abstractmethod
    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synchronous execution - for API/dashboard calls.
        
        Args:
            parameters: Service-specific parameters
            
        Returns:
            Service execution results
        """
        pass

    @abstractmethod
    def async_execute(self, parameters: Dict[str, Any], ctx: Context) -> Dict[str, Any]:
        """
        Asynchronous execution - for worker processing.
        
        This method is called by the worker for actual task processing.
        Must be implemented by each service.

        Args:
            parameters: Service-specific parameters (clean, without context data)
            ctx: Execution context with task_id, metadata, cancellation, and logging correlation
            
        Returns:
            Service execution results
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Service description."""
        pass
    
    def get_task_id(self, ctx: Context) -> Optional[str]:
        """
        Extract task_id from context.
        
        Args:
            ctx: Execution context
            
        Returns:
            Task ID if available, None otherwise
        """
        return ctx.get(TASK_ID)
    
    def get_metadata(self, ctx: Context) -> Dict[str, Any]:
        """
        Extract metadata from context.
        
        Args:
            ctx: Execution context
            
        Returns:
            Metadata dictionary
        """
        return ctx.get(METADATA, {})
    
    def get_execution_mode(self, ctx: Context) -> str:
        """
        Extract execution mode from context.
        
        Args:
            ctx: Execution context
            
        Returns:
            Execution mode (async, sync, background)
        """
        return ctx.get(EXECUTION_MODE, "unknown")
    
    def get_logging_context(self, ctx: Context) -> Dict[str, Any]:
        """
        Get logging context for correlation.
        
        Args:
            ctx: Execution context
            
        Returns:
            Dictionary of logging context data
        """
        return ctx.get_logging_context()
    
    def check_context_done(self, ctx: Context) -> bool:
        """
        Check if context is done (cancelled or expired).
        
        Args:
            ctx: Execution context
            
        Returns:
            True if context is done
        """
        return ctx.done()
    
    def get_context_status(self, ctx: Context) -> Dict[str, Any]:
        """
        Get context status information.
        
        Args:
            ctx: Execution context
            
        Returns:
            Context status dictionary
        """
        return {
            "cancelled": ctx.is_cancelled(),
            "expired": ctx.is_expired(),
            "done": ctx.done(),
            "time_remaining": ctx.time_remaining(),
            "correlation_id": ctx.get(LOG_CORRELATION_ID)
        }
    
    # Legacy helper methods for backward compatibility during migration
    def _extract_task_context(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        DEPRECATED: Extract task context from enhanced parameters.
        Use Context instead.
        """
        return parameters.get("_task_context", {})
    
    def _get_task_id(self, parameters: Dict[str, Any]) -> Optional[str]:
        """
        DEPRECATED: Extract task_id from enhanced parameters.
        Use get_task_id(ctx) instead.
        """
        task_context = self._extract_task_context(parameters)
        return task_context.get("task_id")
    
    def _get_usecase_name(self, parameters: Dict[str, Any]) -> str:
        """
        DEPRECATED: Extract usecase name from enhanced parameters.
        Use Context metadata instead.
        """
        task_context = self._extract_task_context(parameters)
        return task_context.get("usecase_name", "unknown")
    
    def _get_service_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        DEPRECATED: Extract service-specific parameters, excluding task context.
        Parameters are now clean by default with Context.
        """
        return {k: v for k, v in parameters.items() if k != "_task_context"} 