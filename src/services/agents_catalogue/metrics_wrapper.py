"""
Metrics wrapper for agents catalogue services.

This module provides automatic metrics tracking for all agents without requiring
modifications to individual agent code.  At service registration time (see
``registry.py``), the ``track_agent_execution`` wrapper is applied to each
agent's ``execute()`` / ``async_execute()`` methods via monkey-patching.

Metrics emitted:
  - ``agents_catalogue_agent_invocations_total``      (counter)
  - ``agents_catalogue_agent_execution_duration_seconds`` (histogram)

All metrics use lazy initialisation so they are created only after the
telemetry subsystem has been set up — avoiding import-order issues.
"""

import functools
import re
import time
from typing import Dict, Any, Callable

from src.providers.context import Context
from src.providers.logger import Logger
from src.providers.telemetry import get_meter, is_metrics_initialized

logger = Logger("AgentMetricsWrapper")

# Lazy initialization of metrics
_metrics_meter = None
_agent_invocations = None
_agent_execution_duration = None


def _get_agent_metrics():
    """Lazy initialization of agent metrics."""
    global _metrics_meter, _agent_invocations, _agent_execution_duration

    if _agent_invocations is not None:
        return _agent_invocations, _agent_execution_duration

    if not is_metrics_initialized():
        return None, None

    try:
        _metrics_meter = get_meter("agents_catalogue")

        # Agent invocation and execution metrics
        _agent_invocations = _metrics_meter.create_counter(
            "agent_invocations_total",
            "Total number of agent invocations",
            labelnames=("agent_name", "execution_mode", "status")
        )

        _agent_execution_duration = _metrics_meter.create_histogram(
            "agent_execution_duration_seconds",
            "Agent execution duration in seconds",
            labelnames=("agent_name", "execution_mode", "status"),
            buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, float('inf'))
        )

        logger.info("Agent metrics initialized")
    except Exception as e:
        logger.error(f"Failed to initialize agent metrics: {e}", exc_info=True)
        return None, None

    return _agent_invocations, _agent_execution_duration


def get_agent_name(service_instance) -> str:
    """Extract agent name from service instance."""
    # Try to get agent name from various sources
    if hasattr(service_instance, '__class__'):
        class_name = service_instance.__class__.__name__
        # Convert CamelCase to kebab-case
        # e.g., "AutonomousAgentService" -> "autonomous-agent"
        #       "E2EOnboardingService"   -> "e2e-onboarding"
        if class_name.endswith("Service"):
            agent_name = class_name[:-7]  # Remove "Service" suffix
            # Convert to kebab-case:
            # 1. Insert hyphen between lowercase and uppercase: "agentService" -> "agent-Service"
            # 2. Insert hyphen between acronym (uppercase+digits) and CamelCase word:
            #    "E2EOnboarding" -> "E2E-Onboarding", "QCCOnboarding" -> "QCC-Onboarding"
            agent_name = re.sub(r'([a-z])([A-Z])', r'\1-\2', agent_name)
            agent_name = re.sub(r'([A-Z0-9]+)([A-Z][a-z])', r'\1-\2', agent_name)
            return agent_name.lower()
        return class_name.lower()
    return "unknown"


def _determine_status(result: Dict[str, Any]) -> str:
    """Determine status from result dictionary."""
    if not result:
        return "failed"
    
    status = result.get("status", "").lower()

    # Map various status values to standard ones.
    # Only two terminal states: "completed" and "failed".
    # Aligns with src/providers/telemetry/domain/claude.py._determine_status.
    if status in ("completed", "success"):
        return "completed"
    elif status in ("failed", "error", "failure"):
        return "failed"
    else:
        # Check for error indicators
        if result.get("error") or result.get("error_message"):
            return "failed"
        # Default to completed if no error indicators
        return "completed"


def track_agent_execution(agent_name: str, execution_mode: str, func: Callable) -> Callable:
    """
    Decorator to track agent execution metrics.
    
    Args:
        agent_name: Name of the agent
        execution_mode: Execution mode ("sync" or "async")
        func: Function to wrap
        
    Returns:
        Wrapped function with metrics tracking
    """
    import inspect
    
    # Check if function is async
    is_async = inspect.iscoroutinefunction(func)
    
    if is_async:
        @functools.wraps(func)
        async def async_wrapper(self, parameters: Dict[str, Any], ctx: Context, *args, **kwargs) -> Dict[str, Any]:
            """Wrapper for asynchronous async_execute method."""
            execution_start = time.time()
            invocations, duration = _get_agent_metrics()
            
            try:
                # Execute the original method
                result = await func(self, parameters, ctx, *args, **kwargs)
                
                # Determine status
                status = _determine_status(result)
                execution_time = time.time() - execution_start
                
                # Record metrics
                if invocations is not None:
                    invocations.labels(
                        agent_name=agent_name,
                        execution_mode=execution_mode,
                        status=status
                    ).inc()
                
                if duration is not None:
                    duration.labels(
                        agent_name=agent_name,
                        execution_mode=execution_mode,
                        status=status
                    ).observe(execution_time)
                
                return result
                
            except Exception as e:
                # Record failure metrics
                status = "failed"
                execution_time = time.time() - execution_start
                
                if invocations is not None:
                    invocations.labels(
                        agent_name=agent_name,
                        execution_mode=execution_mode,
                        status=status
                    ).inc()
                
                if duration is not None:
                    duration.labels(
                        agent_name=agent_name,
                        execution_mode=execution_mode,
                        status=status
                    ).observe(execution_time)
                
                # Re-raise the exception
                raise
        
        return async_wrapper
    else:
        @functools.wraps(func)
        def sync_wrapper(self, parameters: Dict[str, Any], *args, **kwargs) -> Dict[str, Any]:
            """Wrapper for synchronous execute method."""
            execution_start = time.time()
            invocations, duration = _get_agent_metrics()
            
            try:
                # Execute the original method
                result = func(self, parameters, *args, **kwargs)
                
                # Determine status
                status = _determine_status(result)
                execution_time = time.time() - execution_start
                
                # Record metrics
                if invocations is not None:
                    invocations.labels(
                        agent_name=agent_name,
                        execution_mode=execution_mode,
                        status=status
                    ).inc()
                
                if duration is not None:
                    duration.labels(
                        agent_name=agent_name,
                        execution_mode=execution_mode,
                        status=status
                    ).observe(execution_time)
                
                return result
                
            except Exception as e:
                # Record failure metrics
                status = "failed"
                execution_time = time.time() - execution_start
                
                if invocations is not None:
                    invocations.labels(
                        agent_name=agent_name,
                        execution_mode=execution_mode,
                        status=status
                    ).inc()
                
                if duration is not None:
                    duration.labels(
                        agent_name=agent_name,
                        execution_mode=execution_mode,
                        status=status
                    ).observe(execution_time)
                
                # Re-raise the exception
                raise
        
        return sync_wrapper

