"""
Pydantic models for PR Review API.

These models define the request/response schemas for the PR Review API endpoints.
"""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict

from src.constants.pr_review import (
    ApiVersion,
    ReviewStatus,
    AckStatus,
    ErrorCode,
    AgentStatus,
    DEFAULT_API_VERSION,
)


# --- Request Models ---


class PRMetadata(BaseModel):
    """PR metadata for review request."""

    pr_url: str = Field(
        ...,
        description="Full URL to the pull request",
        examples=["https://github.com/razorpay/ai-pr-reviewer/pull/125"],
    )
    pr_number: int = Field(
        ...,
        ge=1,
        description="PR number",
        examples=[125],
    )
    repository: str = Field(
        ...,
        pattern=r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$",
        description="Repository in owner/name format",
        examples=["razorpay/ai-pr-reviewer"],
    )
    author: str = Field(
        ...,
        description="PR author username",
        examples=["richesh.gupta"],
    )
    title: str = Field(
        ...,
        description="PR title",
        examples=["fix: Authentication bug"],
    )
    branch: str = Field(
        ...,
        description="Source branch name",
        examples=["bugfix/auth-issue"],
    )
    target_branch: str = Field(
        ...,
        description="Target/base branch name",
        examples=["master"],
    )
    description: Optional[str] = Field(
        None,
        description="PR description/body text (optional; omit if unavailable)",
        examples=["Fixes a bug in auth flow"],
    )


class PRReviewEnqueueRequest(BaseModel):
    """Request model for enqueuing a PR review."""

    pr_metadata: PRMetadata = Field(
        ...,
        description="PR metadata for the review",
    )
    pr_context: Optional[str] = Field(
        None,
        description="Additional context about the PR (related issues, design docs, etc.)",
        examples=["Related to incident #INC-42 and design doc link ..."],
    )
    correlation_id: Optional[str] = Field(
        None,
        description="UUID v4 for request tracing; server generates if omitted",
        examples=["3b38b8e9-2c0f-4a4e-a5d5-0c5bd1acb9a1"],
    )
    idempotency_key: Optional[str] = Field(
        None,
        description="Single idempotency key to deduplicate requests. Format: repo_name:pr_number:run_id",
        examples=["razorpay/ai-pr-reviewer:125:1731508800000"],
    )


# --- Response Models ---


class TelemetryLite(BaseModel):
    """Lightweight telemetry information."""

    correlation_id: str = Field(
        ...,
        description="Echoed or server-generated correlation ID",
        examples=["3b38b8e9-2c0f-4a4e-a5d5-0c5bd1acb9a1"],
    )
    timestamp: str = Field(
        ...,
        description="ISO 8601 timestamp of response generation",
        examples=["2025-11-13T12:00:00Z"],
    )


class PRReviewLinks(BaseModel):
    """Links for PR review response."""

    status_url: Optional[str] = Field(
        None,
        description="Canonical URL for polling status",
        examples=["https://swe-agent-api.concierge.stage.razorpay.in/api/v1/pr-review/rev_01JH8NM3..."],
    )


class PRReviewAckResponse(BaseModel):
    """Response model for PR review enqueue acknowledgement."""

    api_version: str = Field(
        default=DEFAULT_API_VERSION.value,
        description="API version",
        examples=["v1"],
    )
    review_id: str = Field(
        ...,
        description="Server-generated stable ID for this review",
        examples=["rev_01JH8NM3W8C4M7R7JX7WZ9QY5Q"],
    )
    status: AckStatus = Field(
        ...,
        description="Acknowledgement status (enqueue admission result only)",
        examples=["accepted"],
    )
    telemetry: Optional[TelemetryLite] = Field(
        None,
        description="Telemetry information",
    )
    links: Optional[PRReviewLinks] = Field(
        None,
        description="Related links",
    )


class PRIdentity(BaseModel):
    """PR identity for correlation."""

    repository: str = Field(
        ...,
        description="Repository in owner/name format",
        examples=["razorpay/ai-pr-reviewer"],
    )
    pr_number: int = Field(
        ...,
        description="PR number",
        examples=[125],
    )


class ReviewTimestamps(BaseModel):
    """Timestamps for review lifecycle."""

    enqueued_at: Optional[str] = Field(
        None,
        description="ISO 8601 time when the job was accepted into the queue",
        examples=["2025-11-13T12:00:00Z"],
    )
    started_at: Optional[str] = Field(
        None,
        description="ISO 8601 time when processing started",
        examples=["2025-11-13T12:01:10Z"],
    )
    completed_at: Optional[str] = Field(
        None,
        description="ISO 8601 time when processing finished",
        examples=["2025-11-13T12:05:38Z"],
    )


class FieldError(BaseModel):
    """Field-level validation error."""

    field: str = Field(
        ...,
        description="JSON path of the invalid field",
        examples=["pr_metadata.pr_number"],
    )
    message: str = Field(
        ...,
        description="Error message for this field",
        examples=["field is required"],
    )


class Error(BaseModel):
    """Error details."""

    code: ErrorCode = Field(
        ...,
        description="Error code indicating the type of failure",
        examples=["validation_error"],
    )
    message: str = Field(
        ...,
        description="Human-readable error description",
        examples=["Invalid field: pr_metadata.pr_number is required"],
    )
    field_errors: Optional[List[FieldError]] = Field(
        None,
        description="Present when code = validation_error",
    )
    retry_after_s: Optional[int] = Field(
        None,
        ge=0,
        description="Present when code = rate_limited. Seconds to wait before retry.",
        examples=[30],
    )


class ReviewStatusResponse(BaseModel):
    """Response model for PR review status."""

    api_version: str = Field(
        default=DEFAULT_API_VERSION.value,
        description="API version",
        examples=["v1"],
    )
    review_id: str = Field(
        ...,
        description="Review identifier",
        examples=["rev_01JH8NM3W8C4M7R7JX7WZ9QY5Q"],
    )
    status: ReviewStatus = Field(
        ...,
        description="Review lifecycle status after enqueue",
        examples=["running"],
    )
    pr_identity: PRIdentity = Field(
        ...,
        description="PR identity for correlation",
    )
    telemetry: Optional[TelemetryLite] = Field(
        None,
        description="Telemetry information",
    )
    error: Optional[Error] = Field(
        None,
        description="Error details (present when status = failed)",
    )
    timestamps: Optional[ReviewTimestamps] = Field(
        None,
        description="Review lifecycle timestamps",
    )


class ErrorResponse(BaseModel):
    """Error response model."""

    api_version: str = Field(
        default=DEFAULT_API_VERSION.value,
        description="API version",
        examples=["v1"],
    )
    error: Error = Field(
        ...,
        description="Error details",
    )
    telemetry: Optional[TelemetryLite] = Field(
        None,
        description="Telemetry information",
    )


# --- Health Response Models ---


class Agent(BaseModel):
    """Agent information for health check."""

    name: str = Field(
        ...,
        description="Human-readable agent name",
        examples=["Claude Code"],
    )
    type: str = Field(
        ...,
        description="Agent type identifier",
        examples=["claude_code"],
    )
    status: AgentStatus = Field(
        ...,
        description="Agent availability status",
        examples=["active"],
    )
    description: str = Field(
        ...,
        description="Agent description",
        examples=["AI-powered code generation and analysis using Claude"],
    )


class HealthResponse(BaseModel):
    """Health check response model."""

    agents: List[Agent] = Field(
        ...,
        description="List of available agents",
    )
    total_count: int = Field(
        ...,
        ge=0,
        description="Total number of agents (excluding coming_soon)",
        examples=[1],
    )
    active_count: int = Field(
        ...,
        ge=0,
        description="Number of currently active agents",
        examples=[1],
    )
    timestamp: str = Field(
        ...,
        description="ISO 8601 timestamp of health snapshot",
        examples=["2025-11-13T12:00:00Z"],
    )
    unix_timestamp: Optional[float] = Field(
        None,
        description="Optional Unix epoch seconds for convenience",
        examples=[1762171349.57884],
    )
