"""
Context management package.

This package provides context management capabilities including:
- Context creation and management
- Context keys and constants  
- Context managers for different scenarios (API, tasks, background operations)
"""

from .context import Context
from .keys import (
    # Core context keys
    TASK_ID, USER_ID, REQUEST_ID, LOG_CORRELATION_ID,
    
    # Context metadata
    METADATA, EXECUTION_MODE, WORKER_CONTEXT
)
from .manager import ContextManager
from .task_registry import TaskContextRegistry

__all__ = [
    # Core classes
    "Context",
    "ContextManager",
    "TaskContextRegistry",
    
    # Context keys
    "TASK_ID", "USER_ID", "REQUEST_ID", "LOG_CORRELATION_ID",
    "METADATA", "EXECUTION_MODE", "WORKER_CONTEXT"
] 