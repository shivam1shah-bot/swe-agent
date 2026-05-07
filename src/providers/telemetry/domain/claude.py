"""
Claude Domain Metrics

SWE Agent operational metrics for Claude Code subprocess execution.
These measure what only the orchestrator can observe — not duplicated by
Claude Code's native OTEL telemetry (claude_code.*):

- execution_duration_seconds: wall-clock histogram per invocation
- mcp_interactions_total: MCP server setup success/failure
- errors_total: process-level errors (crashes, timeouts, soft failures)
"""

import functools
import time
from contextlib import contextmanager
from typing import Dict, Any, Callable, Optional

from src.providers.logger import Logger
from src.providers.telemetry.core import get_meter, is_metrics_initialized

logger = Logger("ClaudeMetrics")

# Lazy initialization of metrics
_metrics_meter = None
_claude_execution_duration = None
_claude_mcp_interactions = None
_claude_errors = None


def _get_claude_metrics():
    """Lazy initialization of Claude metrics."""
    global _metrics_meter, _claude_execution_duration, _claude_mcp_interactions, _claude_errors

    if _claude_execution_duration is not None:
        return _claude_execution_duration, _claude_mcp_interactions, _claude_errors

    if not is_metrics_initialized():
        return None, None, None

    try:
        _metrics_meter = get_meter("swe_agent_claude_code")

        # Wall-clock duration of each Claude subprocess invocation
        _claude_execution_duration = _metrics_meter.create_histogram(
            "execution_duration_seconds",
            "Wall-clock duration of each Claude Code subprocess invocation in seconds",
            labelnames=("agent_name", "action", "provider", "status"),
            buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0, float('inf'))
        )

        # MCP server interactions
        _claude_mcp_interactions = _metrics_meter.create_counter(
            "mcp_interactions_total",
            "Total number of MCP server interactions",
            labelnames=("mcp_name", "action", "status")
        )

        # Process-level errors (crashes, timeouts, soft failures)
        _claude_errors = _metrics_meter.create_counter(
            "errors_total",
            "Total number of Claude Code process-level errors",
            labelnames=("agent_name", "error_type", "action", "provider")
        )

        logger.info("Claude metrics initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Claude metrics: {e}", exc_info=True)
        return None, None, None

    return _claude_execution_duration, _claude_mcp_interactions, _claude_errors


def _determine_status(result: Dict[str, Any]) -> str:
    """Determine status from Claude result dictionary."""
    if not result:
        return "failed"
    
    # Check for error indicators
    if result.get("error") or result.get("error_message"):
        return "failed"
    
    # Check for success indicators
    if result.get("type") == "claude_code_response" and result.get("result"):
        return "completed"
    
    # Check return code if available
    if "returncode" in result:
        return "completed" if result["returncode"] == 0 else "failed"
    
    # Default to completed if no error indicators
    return "completed"


def track_claude_execution(action: str = "unknown", provider: str = "unknown") -> Callable:
    """
    Decorator to automatically track Claude Code execution metrics.
    
    This decorator wraps ClaudeCodeTool methods to automatically track:
    - Invocations (total, by action and provider)
    - Execution duration (histogram)
    - Success/failure rates
    
    Args:
        action: Action type (e.g., "run_prompt", "continue_session")
        provider: Provider type (e.g., "bedrock", "vertex_ai")
        
    Returns:
        Decorator function
        
    Example:
        @track_claude_execution(action="run_prompt", provider="bedrock")
        async def execute(self, params, context):
            ...
    """
    def decorator(func: Callable) -> Callable:
        import inspect
        
        is_async = inspect.iscoroutinefunction(func)
        
        if is_async:
            @functools.wraps(func)
            async def async_wrapper(self, *args, **kwargs) -> Dict[str, Any]:
                """Wrapper for asynchronous Claude methods."""
                execution_start = time.time()
                duration, _, errors = _get_claude_metrics()

                actual_provider = provider
                if hasattr(self, 'provider'):
                    actual_provider = self.provider or provider

                actual_action = action
                agent_name = "unknown"
                if args and isinstance(args[0], dict):
                    actual_action = args[0].get("action", action)
                    agent_name = args[0].get("agent_name", "unknown")

                try:
                    result = await func(self, *args, **kwargs)

                    status = _determine_status(result)
                    execution_time = time.time() - execution_start

                    if duration is not None:
                        duration.labels(
                            agent_name=agent_name,
                            action=actual_action,
                            provider=actual_provider,
                            status=status
                        ).observe(execution_time)

                    if status == "failed" and errors is not None:
                        errors.labels(
                            agent_name=agent_name,
                            error_type="soft_failure",
                            action=actual_action,
                            provider=actual_provider
                        ).inc()

                    return result

                except Exception as e:
                    status = "failed"
                    execution_time = time.time() - execution_start

                    if duration is not None:
                        duration.labels(
                            agent_name=agent_name,
                            action=actual_action,
                            provider=actual_provider,
                            status=status
                        ).observe(execution_time)

                    if errors is not None:
                        errors.labels(
                            agent_name=agent_name,
                            error_type=type(e).__name__,
                            action=actual_action,
                            provider=actual_provider
                        ).inc()

                    raise

            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(self, *args, **kwargs) -> Dict[str, Any]:
                """Wrapper for synchronous Claude methods."""
                execution_start = time.time()
                duration, _, errors = _get_claude_metrics()

                actual_provider = provider
                if hasattr(self, 'provider'):
                    actual_provider = self.provider or provider

                actual_action = action
                agent_name = "unknown"
                if args and isinstance(args[0], dict):
                    actual_action = args[0].get("action", action)
                    agent_name = args[0].get("agent_name", "unknown")

                try:
                    result = func(self, *args, **kwargs)

                    status = _determine_status(result)
                    execution_time = time.time() - execution_start

                    if duration is not None:
                        duration.labels(
                            agent_name=agent_name,
                            action=actual_action,
                            provider=actual_provider,
                            status=status
                        ).observe(execution_time)

                    if status == "failed" and errors is not None:
                        errors.labels(
                            agent_name=agent_name,
                            error_type="soft_failure",
                            action=actual_action,
                            provider=actual_provider
                        ).inc()

                    return result

                except Exception as e:
                    status = "failed"
                    execution_time = time.time() - execution_start

                    if duration is not None:
                        duration.labels(
                            agent_name=agent_name,
                            action=actual_action,
                            provider=actual_provider,
                            status=status
                        ).observe(execution_time)

                    if errors is not None:
                        errors.labels(
                            agent_name=agent_name,
                            error_type=type(e).__name__,
                            action=actual_action,
                            provider=actual_provider
                        ).inc()

                    raise

            return sync_wrapper
    
    return decorator


@contextmanager
def track_mcp_interaction(mcp_name: str, action: str = "unknown"):
    """
    Context manager to track MCP server interactions.
    
    Args:
        mcp_name: Name of the MCP server
        action: Action being performed (e.g., "add", "verify", "list")
        
    Example:
        with track_mcp_interaction("sequentialthinking", "add"):
            claude.mcp.add("sequentialthinking", ...)
    """
    _, mcp_interactions, _ = _get_claude_metrics()
    status = "success"
    
    try:
        yield
    except Exception:
        status = "failed"
        raise
    finally:
        if mcp_interactions is not None:
            mcp_interactions.labels(
                mcp_name=mcp_name,
                action=action,
                status=status
            ).inc()





