"""
OTEL Event Emitter for SWE Agent Task Lifecycle

Emits structured log records via OTLP gRPC to the OTEL Collector,
which routes them to ClickHouse for analytics and audit.

Events emitted:
  - ``swe_agent.task_started``  – when a Claude Code task begins
  - ``swe_agent.task_completed`` – on successful completion (includes cost, tokens)
  - ``swe_agent.task_failed``   – on failure (includes error details)

These complement Claude Code's native OTEL events (user_prompt, tool_result,
api_request) by adding task-level context that only the SWE Agent knows
(task_id, agent_name, repo, task_type).
"""

import logging
import time
from typing import Any, Dict, Optional

from src.providers.logger import Logger

_logger = Logger("OTELEvents")
_python_logger = logging.getLogger(__name__)

_logger_provider = None
_otel_logger = None
_initialized = False


def init_otel_events(config: Dict[str, Any]) -> None:
    """Initialize the OTEL log/event emitter.

    Should be called once during worker startup from ``_setup_telemetry()``.
    No-ops if already initialized or if OTEL is disabled in config.

    Args:
        config: The ``[telemetry.otel]`` config dict with keys:
                ``enabled``, ``endpoint``, ``service_name``.
    """
    global _logger_provider, _otel_logger, _initialized

    if _initialized:
        return

    if not config.get("enabled") or not config.get("logs_enabled", True):
        _logger.info("OTEL events disabled by config")
        return

    try:
        from opentelemetry.sdk._logs import LoggerProvider
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
        from opentelemetry.sdk.resources import Resource
        import os

        service_name = config.get("service_name", "swe-agent-worker")
        endpoint = config.get("endpoint")
        if not endpoint:
            raise ValueError("telemetry.otel.endpoint is required when OTEL is enabled")
        env_name = os.getenv("APP_ENV", "dev")

        resource = Resource.create({
            "service.name": service_name,
            "service.namespace": "swe-agent",
            "deployment.environment": env_name,
        })

        exporter = OTLPLogExporter(endpoint=endpoint, insecure=True)
        _logger_provider = LoggerProvider(resource=resource)
        _logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
        _otel_logger = _logger_provider.get_logger("swe-agent.tasks")

        _initialized = True
        _logger.info("OTEL event emitter initialized", extra={"endpoint": endpoint})
    except Exception as e:
        _logger.error(f"Failed to initialize OTEL event emitter: {e}", exc_info=True)


def shutdown_otel_events() -> None:
    """Flush pending events and shut down the OTEL log provider."""
    global _logger_provider
    if _logger_provider is not None:
        try:
            _logger_provider.shutdown()
        except Exception as e:
            _logger.warning(f"Error shutting down OTEL event emitter: {e}")


def _emit(event_name: str, attributes: Dict[str, str], body: str = "") -> None:
    """Emit a single structured log record via OTLP.

    Silently no-ops if the emitter is not initialized.
    """
    if _otel_logger is None:
        return

    try:
        from opentelemetry._logs import SeverityNumber

        ts_ns = int(time.time() * 1e9)
        _otel_logger.emit(
            timestamp=ts_ns,
            severity_number=SeverityNumber.INFO,
            severity_text="INFO",
            body=body or event_name,
            attributes={**attributes, "event.name": event_name},
        )
    except Exception as e:
        _python_logger.debug(f"Failed to emit OTEL event {event_name}: {e}")


def emit_task_started(
    task_id: str,
    agent_name: str,
    prompt: str = "",
    repo: str = "",
    task_type: str = "autonomous_agent",
) -> None:
    """Emit a task-started event."""
    attrs = {
        "task.id": task_id,
        "agent.name": agent_name,
        "task.type": task_type,
    }
    if repo:
        attrs["repo"] = repo

    body = prompt[:2000] if prompt else ""
    _emit("swe_agent.task_started", attrs, body=body)


def emit_task_completed(
    task_id: str,
    agent_name: str,
    duration_s: float = 0.0,
    cost_usd: float = 0.0,
    input_tokens: int = 0,
    output_tokens: int = 0,
    num_turns: int = 0,
    repo: str = "",
) -> None:
    """Emit a task-completed event with cost and token summary."""
    attrs = {
        "task.id": task_id,
        "agent.name": agent_name,
        "duration_s": str(round(duration_s, 2)),
        "cost_usd": str(round(cost_usd, 6)),
        "input_tokens": str(input_tokens),
        "output_tokens": str(output_tokens),
        "num_turns": str(num_turns),
        "status": "completed",
    }
    if repo:
        attrs["repo"] = repo

    _emit("swe_agent.task_completed", attrs)


def emit_task_failed(
    task_id: str,
    agent_name: str,
    error_type: str = "unknown",
    error_message: str = "",
    duration_s: float = 0.0,
    repo: str = "",
) -> None:
    """Emit a task-failed event."""
    attrs = {
        "task.id": task_id,
        "agent.name": agent_name,
        "error_type": error_type,
        "status": "failed",
        "duration_s": str(round(duration_s, 2)),
    }
    if repo:
        attrs["repo"] = repo

    _emit("swe_agent.task_failed", attrs, body=error_message[:2000])
