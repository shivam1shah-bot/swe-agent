"""
PR Review API Constants.

Defines constants for PR Review API to ensure consistent usage across codebase.
"""

from enum import Enum


class ApiVersion(str, Enum):
    """API version identifiers."""
    V1 = "v1"


class ReviewStatus(str, Enum):
    """
    Review job lifecycle status after enqueue.

    Clients use the status endpoint to observe lifecycle state.
    """
    ACCEPTED = "accepted"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AckStatus(str, Enum):
    """
    Acknowledgement status for the enqueue phase only.

    Indicates the admission result:
    - accepted: job created
    - queued: immediately placed into queue
    - already_exists: deduplicated to an existing review
    """
    ACCEPTED = "accepted"
    QUEUED = "queued"
    ALREADY_EXISTS = "already_exists"


class ErrorCode(str, Enum):
    """Error codes for API error responses."""
    VALIDATION_ERROR = "validation_error"
    UNAUTHORIZED = "unauthorized"
    RATE_LIMITED = "rate_limited"
    DUPLICATE_REQUEST = "duplicate_request"
    CLAUDE_UNAVAILABLE = "claude_unavailable"
    UPSTREAM_ERROR = "upstream_error"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"


class AgentType(str, Enum):
    """Agent type identifiers."""
    CLAUDE_CODE = "claude_code"


class AgentStatus(str, Enum):
    """Agent availability status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    COMING_SOON = "coming_soon"


# Review ID prefix
REVIEW_ID_PREFIX = "rev_"

# Default API version
DEFAULT_API_VERSION = ApiVersion.V1

# Queue alias for PR reviews
PR_REVIEW_QUEUE_ALIAS = "code_review_execution"

# Task type for PR reviews
PR_REVIEW_TASK_TYPE = "code_review"
