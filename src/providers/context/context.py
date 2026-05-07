"""
Core Context class for request/task scoped context management.
"""

import time
import uuid
import logging
from typing import Any, Dict, Optional, Callable, Tuple
from .keys import _DEADLINE, _CANCELLED, _CANCEL_FUNC, _CHILDREN, LOG_CORRELATION_ID


class Context:
    """
    Request/task scoped context similar to Go's context.Context.
    
    Provides:
    - Value storage with parent chain lookup
    - Cancellation support
    - Timeout/deadline support
    - Automatic logging correlation
    """
    
    def __init__(self, parent: Optional['Context'] = None, values: Optional[Dict[str, Any]] = None):
        """
        Initialize a new context.
        
        Args:
            parent: Parent context (for value inheritance)
            values: Initial values for this context
        """
        self.parent = parent
        self.values = values or {}
        self._logger = logging.getLogger(__name__)
        
        # Initialize cancellation state
        self.values[_CANCELLED] = False
        self.values[_CANCEL_FUNC] = None
        self.values[_CHILDREN] = []
        self.values[_DEADLINE] = None
        
        # Generate log correlation ID if not inherited
        if not self.get(LOG_CORRELATION_ID):
            self.values[LOG_CORRELATION_ID] = str(uuid.uuid4())
        
        # Register with parent if exists
        if parent:
            parent_children = parent.values.get(_CHILDREN, [])
            parent_children.append(self)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from context or parent chain.
        
        Args:
            key: Context key to retrieve
            default: Default value if key not found
            
        Returns:
            Value from context or default
        """
        # Check current context first
        if key in self.values:
            return self.values[key]
        
        # Check parent chain
        if self.parent:
            return self.parent.get(key, default)
        
        return default
    
    def with_value(self, key: str, value: Any) -> 'Context':
        """
        Create child context with additional value.
        
        Args:
            key: Context key
            value: Value to store
            
        Returns:
            New child context with the value
        """
        child_values = {key: value}
        return Context(parent=self, values=child_values)
    
    def with_cancel(self) -> Tuple['Context', Callable]:
        """
        Create cancellable context with cancel function.
        
        Returns:
            Tuple of (cancellable_context, cancel_function)
        """
        def cancel():
            """Cancel this context and all children."""
            self.values[_CANCELLED] = True
            
            # Cancel all children
            for child in self.values.get(_CHILDREN, []):
                if hasattr(child, 'values') and child.values.get(_CANCEL_FUNC):
                    child.values[_CANCEL_FUNC]()
            
            self._logger.debug(f"Context cancelled: {self.get(LOG_CORRELATION_ID)}")
        
        # Create child context with cancel function
        child_values = {_CANCEL_FUNC: cancel}
        child_ctx = Context(parent=self, values=child_values)
        
        return child_ctx, cancel
    
    def with_timeout(self, timeout_seconds: float) -> 'Context':
        """
        Create context with timeout.
        
        Args:
            timeout_seconds: Timeout in seconds
            
        Returns:
            New context with deadline
        """
        deadline = time.time() + timeout_seconds
        child_values = {_DEADLINE: deadline}
        child_ctx = Context(parent=self, values=child_values)
        
        self._logger.debug(f"Context created with timeout: {timeout_seconds}s, correlation_id: {child_ctx.get(LOG_CORRELATION_ID)}")
        
        return child_ctx
    
    def with_deadline(self, deadline: float) -> 'Context':
        """
        Create context with absolute deadline.
        
        Args:
            deadline: Absolute deadline (timestamp)
            
        Returns:
            New context with deadline
        """
        child_values = {_DEADLINE: deadline}
        child_ctx = Context(parent=self, values=child_values)
        
        self._logger.debug(f"Context created with deadline: {deadline}, correlation_id: {child_ctx.get(LOG_CORRELATION_ID)}")
        
        return child_ctx
    
    def is_cancelled(self) -> bool:
        """
        Check if context is cancelled.
        
        Returns:
            True if context is cancelled
        """
        return self.get(_CANCELLED, False)
    
    def is_expired(self) -> bool:
        """
        Check if context has exceeded its deadline.
        
        Returns:
            True if context has expired
        """
        deadline = self.get(_DEADLINE)
        if deadline is None:
            return False
        
        return time.time() > deadline
    
    def done(self) -> bool:
        """
        Check if context is done (cancelled or expired).
        
        Returns:
            True if context is done
        """
        return self.is_cancelled() or self.is_expired()
    
    def time_remaining(self) -> Optional[float]:
        """
        Get remaining time until deadline.
        
        Returns:
            Seconds remaining or None if no deadline
        """
        deadline = self.get(_DEADLINE)
        if deadline is None:
            return None
        
        remaining = deadline - time.time()
        return max(0, remaining)
    
    def get_logging_context(self) -> Dict[str, Any]:
        """
        Get context data for logging correlation.
        
        Returns:
            Dictionary of logging context data
        """
        return {
            "correlation_id": self.get(LOG_CORRELATION_ID),
            "task_id": self.get("task_id"),
            "request_id": self.get("request_id"),
            "user_id": self.get("user_id"),
            "execution_mode": self.get("execution_mode")
        }
    
    def __repr__(self) -> str:
        """String representation of context."""
        correlation_id = self.get(LOG_CORRELATION_ID, "unknown")
        task_id = self.get("task_id", "unknown")
        return f"Context(correlation_id={correlation_id}, task_id={task_id}, done={self.done()})" 