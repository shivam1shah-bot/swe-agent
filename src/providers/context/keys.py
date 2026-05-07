"""
Standard context keys for consistent context usage across the application.
"""

# Task execution context keys
TASK_ID = "task_id"
METADATA = "metadata"
WORKER_CONTEXT = "worker_context"
EXECUTION_MODE = "execution_mode"

# User and request context keys
USER_ID = "user_id"
REQUEST_ID = "request_id"

# Logging context keys
LOG_CORRELATION_ID = "log_correlation_id"

# Internal context keys (prefixed with underscore)
_DEADLINE = "_deadline"
_CANCELLED = "_cancelled"
_CANCEL_FUNC = "_cancel_func"
_CHILDREN = "_children" 