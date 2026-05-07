"""
Pydantic models for Plugin Metrics API.

These models define the request/response schemas for the Plugin Metrics API endpoints,
which allow Claude Code plugins to push metrics to the central Prometheus endpoint.
"""

from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict


# --- Enums ---


class MetricEventType(str, Enum):
    """Types of metric events that plugins can report."""

    SKILL_INVOKED = "skill_invoked"
    SKILL_COMPLETED = "skill_completed"
    MCP_TOOL_CALLED = "mcp_tool_called"
    USER_ACTIVITY = "user_activity"


# --- Request Models ---


class MCPToolCall(BaseModel):
    """Individual MCP tool call record."""

    tool_name: str = Field(
        ...,
        description="Full MCP tool name in format 'mcp__<server>__<tool>'",
        examples=["mcp__blade-mcp__get_blade_component_docs"],
    )
    call_count: int = Field(
        default=1,
        ge=1,
        description="Number of times this tool was called",
    )


class PluginMetricEvent(BaseModel):
    """Request model for recording a single metric event from a plugin."""

    event_type: MetricEventType = Field(
        ...,
        description="Type of metric event being recorded",
    )
    skill_name: Optional[str] = Field(
        None,
        description="Name of the skill (for skill_invoked/skill_completed events)",
        examples=["blade-review", "security-review", "testing-review"],
    )
    repository: str = Field(
        ...,
        pattern=r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$",
        description="Repository in owner/name format",
        examples=["razorpay/api", "razorpay/checkout"],
    )
    issues_found: Optional[int] = Field(
        None,
        ge=0,
        description="Number of issues found (for skill_completed events)",
    )
    duration_seconds: Optional[float] = Field(
        None,
        ge=0,
        description="Duration in seconds (for skill_completed events)",
    )
    mcp_tools: Optional[List[MCPToolCall]] = Field(
        None,
        description="List of MCP tools called (for mcp_tool_called events)",
    )
    plugin_name: str = Field(
        default="code-review",
        description="Name of the plugin reporting metrics",
        examples=["code-review", "discover"],
    )
    user: Optional[str] = Field(
        None,
        description="Username for user activity tracking (low-cardinality)",
        examples=["john.doe", "richesh.gupta"],
    )
    client_timestamp: Optional[str] = Field(
        None,
        description="ISO 8601 timestamp from the client",
        examples=["2024-01-15T10:30:00Z"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "event_type": "skill_invoked",
                    "skill_name": "blade-review",
                    "repository": "razorpay/checkout",
                    "plugin_name": "code-review",
                },
                {
                    "event_type": "skill_completed",
                    "skill_name": "security-review",
                    "repository": "razorpay/api",
                    "issues_found": 3,
                    "duration_seconds": 45.2,
                    "plugin_name": "code-review",
                },
                {
                    "event_type": "mcp_tool_called",
                    "repository": "razorpay/checkout",
                    "mcp_tools": [
                        {"tool_name": "mcp__blade-mcp__get_blade_component_docs", "call_count": 2},
                        {"tool_name": "mcp__blade-mcp__get_blade_pattern_docs", "call_count": 1},
                    ],
                    "plugin_name": "code-review",
                },
                {
                    "event_type": "user_activity",
                    "repository": "razorpay/api",
                    "plugin_name": "discover",
                    "user": "richesh.gupta",
                },
            ]
        }
    )


class BatchPluginMetricRequest(BaseModel):
    """Request model for recording multiple metric events in a batch."""

    events: List[PluginMetricEvent] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of metric events to record (max 100 per batch)",
    )


# --- Response Models ---


class PluginMetricResponse(BaseModel):
    """Response model for successful metric recording."""

    success: bool = Field(
        default=True,
        description="Whether the metric was recorded successfully",
    )
    message: str = Field(
        default="Metric recorded",
        description="Human-readable status message",
    )
    events_recorded: int = Field(
        default=1,
        ge=0,
        description="Number of events successfully recorded",
    )
    server_timestamp: str = Field(
        ...,
        description="ISO 8601 server timestamp when metric was recorded",
        examples=["2024-01-15T10:30:00Z"],
    )


class PluginMetricErrorResponse(BaseModel):
    """Response model for metric recording errors."""

    success: bool = Field(
        default=False,
        description="Always false for error responses",
    )
    error: str = Field(
        ...,
        description="Error message describing what went wrong",
    )
    error_code: str = Field(
        ...,
        description="Machine-readable error code",
        examples=["VALIDATION_ERROR", "INTERNAL_ERROR"],
    )


class PluginMetricsHealthResponse(BaseModel):
    """Response model for plugin metrics health check."""

    status: str = Field(
        default="healthy",
        description="Health status",
    )
    service: str = Field(
        default="external_metrics/claude_plugins",
        description="Service name",
    )
    timestamp: str = Field(
        ...,
        description="ISO 8601 timestamp",
    )
    prometheus_registry: bool = Field(
        default=True,
        description="Whether Prometheus registry is available",
    )
