"""
Plugin Metrics router for FastAPI.

This module provides REST API endpoints for Claude Code plugins to push metrics
to the central Prometheus endpoint. Metrics are then scraped by VictoriaMetrics.

These endpoints are intentionally public (no authentication) to allow plugins
running on developer laptops to push metrics without requiring API credentials.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

from src.models.plugin_metrics import (
    PluginMetricEvent,
    BatchPluginMetricRequest,
    PluginMetricResponse,
    PluginMetricErrorResponse,
    PluginMetricsHealthResponse,
    MetricEventType,
)

# Import the existing review metrics infrastructure
from src.agents.review_agents.metrics import (
    record_mcp_calls,
    record_execution_completion,
    record_user_activity,
    SKILLS_INVOCATIONS_TOTAL,
)

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


def get_current_timestamp() -> str:
    """Get current ISO 8601 timestamp."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _process_metric_event(event: PluginMetricEvent) -> None:
    """
    Process a single metric event and record to Prometheus.

    Args:
        event: The metric event to process
    """
    if event.event_type == MetricEventType.SKILL_INVOKED:
        # Record skill invocation - use "unknown" if skill_name not provided
        skill_name = event.skill_name or "unknown"
        SKILLS_INVOCATIONS_TOTAL.labels(
            skill_name=skill_name,
            repository=event.repository,
            plugin_name=event.plugin_name,
        ).inc()
        logger.debug(
            f"Recorded skill invoked: skill={skill_name}, "
            f"repo={event.repository}, plugin={event.plugin_name}"
        )

    elif event.event_type == MetricEventType.SKILL_COMPLETED:
        # Record skill completion to Prometheus metrics
        # Note: skill_name is optional - we always record the completion metric
        skill_name = event.skill_name or "unknown"

        # Determine status based on whether issues were found
        status = "success"
        if event.issues_found is not None and event.issues_found > 0:
            status = "issues_found"

        # Record execution completion with duration
        record_execution_completion(
            repository=event.repository,
            status=status,
            duration_seconds=event.duration_seconds,
            plugin_name=event.plugin_name,
        )

        logger.info(
            f"Skill completed: skill={skill_name}, "
            f"repo={event.repository}, "
            f"issues_found={event.issues_found}, "
            f"duration_seconds={event.duration_seconds}, "
            f"status={status}"
        )

    elif event.event_type == MetricEventType.MCP_TOOL_CALLED:
        # Record MCP tool calls
        if event.mcp_tools:
            mcp_calls = [
                {"tool_name": tool.tool_name}
                for tool in event.mcp_tools
                for _ in range(tool.call_count)  # Expand by call count
            ]
            record_mcp_calls(mcp_calls, event.repository, event.plugin_name)
            logger.debug(
                f"Recorded MCP tool calls: {len(mcp_calls)} calls for "
                f"repo={event.repository}, plugin={event.plugin_name}"
            )

    elif event.event_type == MetricEventType.USER_ACTIVITY:
        # Record user activity (low cardinality metric)
        if event.user:
            record_user_activity(
                user=event.user,
                plugin_name=event.plugin_name,
            )
            logger.debug(
                f"Recorded user activity: user={event.user}, "
                f"plugin={event.plugin_name}"
            )


@router.post(
    "/event",
    response_model=PluginMetricResponse,
    responses={
        200: {
            "model": PluginMetricResponse,
            "description": "Metric recorded successfully",
        },
        400: {
            "model": PluginMetricErrorResponse,
            "description": "Invalid request (validation error)",
        },
        500: {
            "model": PluginMetricErrorResponse,
            "description": "Internal server error",
        },
    },
)
async def record_plugin_metric(event: PluginMetricEvent) -> PluginMetricResponse:
    """
    Record a single metric event from a Claude Code plugin.

    This endpoint allows plugins to push metrics for:
    - Skill invocations (skill_invoked)
    - Skill completions with results (skill_completed)
    - MCP tool calls (mcp_tool_called)
    - User activity tracking (user_activity) - low cardinality

    **No authentication required** - this endpoint is intentionally public
    to allow plugins running on developer laptops to push metrics.
    """
    try:
        _process_metric_event(event)

        return PluginMetricResponse(
            success=True,
            message=f"Metric recorded: {event.event_type.value}",
            events_recorded=1,
            server_timestamp=get_current_timestamp(),
        )

    except Exception as e:
        logger.exception(f"Error recording plugin metric: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": str(e),
                "error_code": "INTERNAL_ERROR",
            },
        )


@router.post(
    "/batch",
    response_model=PluginMetricResponse,
    responses={
        200: {
            "model": PluginMetricResponse,
            "description": "Metrics recorded successfully",
        },
        400: {
            "model": PluginMetricErrorResponse,
            "description": "Invalid request (validation error)",
        },
        500: {
            "model": PluginMetricErrorResponse,
            "description": "Internal server error",
        },
    },
)
async def record_plugin_metrics_batch(
    request: BatchPluginMetricRequest,
) -> PluginMetricResponse:
    """
    Record multiple metric events from a Claude Code plugin in a single request.

    Useful for batching metrics at the end of a review session.
    Maximum 100 events per batch.

    **No authentication required** - this endpoint is intentionally public.
    """
    try:
        events_recorded = 0

        for event in request.events:
            try:
                _process_metric_event(event)
                events_recorded += 1
            except Exception as e:
                logger.warning(f"Failed to process event in batch: {e}")
                # Continue processing other events

        return PluginMetricResponse(
            success=True,
            message=f"Batch complete: {events_recorded}/{len(request.events)} events recorded",
            events_recorded=events_recorded,
            server_timestamp=get_current_timestamp(),
        )

    except Exception as e:
        logger.exception(f"Error recording plugin metrics batch: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": str(e),
                "error_code": "INTERNAL_ERROR",
            },
        )


@router.get(
    "/health",
    response_model=PluginMetricsHealthResponse,
    responses={
        200: {
            "model": PluginMetricsHealthResponse,
            "description": "Service is healthy",
        },
    },
)
async def plugin_metrics_health() -> PluginMetricsHealthResponse:
    """
    Health check for the plugin metrics endpoint.

    Returns status of the metrics recording subsystem.
    **No authentication required**.
    """
    try:
        # Verify Prometheus registry is accessible
        from prometheus_client import REGISTRY

        # Basic check - can we access the registry?
        registry_available = REGISTRY is not None

        return PluginMetricsHealthResponse(
            status="healthy" if registry_available else "unhealthy",
            service="external_metrics/claude_plugins",
            timestamp=get_current_timestamp(),
            prometheus_registry=registry_available,
        )

    except Exception as e:
        logger.error(f"Plugin metrics health check failed: {e}")
        return PluginMetricsHealthResponse(
            status="unhealthy",
            service="external_metrics/claude_plugins",
            timestamp=get_current_timestamp(),
            prometheus_registry=False,
        )
