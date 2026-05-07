"""
Telemetry Core Module

Provides the foundational Prometheus metrics infrastructure shared by all
services (API, Worker, MCP server).  Every metric in the application flows
through the ``Meter`` class defined here.

Key responsibilities:
  1. ``Meter`` — thin wrapper around prometheus_client that mirrors the
     OpenTelemetry Meter API so a future migration is straightforward.
  2. ``setup_telemetry()`` — one-shot initialiser called during app startup;
     idempotent and safe to call from multiple entry-points.
  3. ``_start_metrics_server()`` — spins up a lightweight FastAPI/uvicorn
     daemon thread exposing ``/metrics`` on a dedicated port for Prometheus
     scraping (separate from the main application port).
"""

import threading
from typing import Dict, Any, Optional
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Summary,
    make_asgi_app,
    REGISTRY,
    CollectorRegistry,
)
import uvicorn

from src.providers.logger import Logger

logger = Logger("Telemetry")

# Global state
_metrics_initialized: bool = False
_metrics_app = None
_registry: Optional[CollectorRegistry] = None
_metrics_server_thread: Optional[threading.Thread] = None
_metrics_server_port: Optional[int] = None


class Meter:
    """
    Simple meter interface for creating metrics.
    
    This provides a simple abstraction that can be extended
    to support OpenTelemetry in the future.
    """
    
    def __init__(self, name: str, registry: Optional[CollectorRegistry] = None):
        """
        Initialize meter.
        
        Args:
            name: Name of the meter (used as prefix for metrics)
            registry: Prometheus registry to use (default: global registry)
        """
        self.name = name
        self.registry = registry or REGISTRY
    
    def create_counter(
        self,
        metric_name: str,
        description: str = "",
        labelnames: tuple = (),
        unit: str = ""
    ) -> Counter:
        """
        Create a counter metric.
        
        Args:
            metric_name: Name of the metric
            description: Description of the metric
            labelnames: Tuple of label names
            unit: Unit of the metric (for future OTEL compatibility)
            
        Returns:
            Counter metric instance
        """
        full_name = f"{self.name}_{metric_name}" if self.name else metric_name
        return Counter(
            full_name,
            description,
            labelnames=labelnames,
            registry=self.registry
        )
    
    def create_histogram(
        self,
        metric_name: str,
        description: str = "",
        labelnames: tuple = (),
        buckets: Optional[list] = None,
        unit: str = ""
    ) -> Histogram:
        """
        Create a histogram metric.
        
        Args:
            metric_name: Name of the metric
            description: Description of the metric
            labelnames: Tuple of label names
            buckets: Histogram buckets (default: Prometheus defaults)
            unit: Unit of the metric (for future OTEL compatibility)
            
        Returns:
            Histogram metric instance
        """
        full_name = f"{self.name}_{metric_name}" if self.name else metric_name
        return Histogram(
            full_name,
            description,
            labelnames=labelnames,
            buckets=buckets,
            registry=self.registry
        )
    
    def create_gauge(
        self,
        metric_name: str,
        description: str = "",
        labelnames: tuple = (),
        unit: str = ""
    ) -> Gauge:
        """
        Create a gauge metric.
        
        Args:
            metric_name: Name of the metric
            description: Description of the metric
            labelnames: Tuple of label names
            unit: Unit of the metric (for future OTEL compatibility)
            
        Returns:
            Gauge metric instance
        """
        full_name = f"{self.name}_{metric_name}" if self.name else metric_name
        return Gauge(
            full_name,
            description,
            labelnames=labelnames,
            registry=self.registry
        )
    
    def create_summary(
        self,
        metric_name: str,
        description: str = "",
        labelnames: tuple = (),
        unit: str = ""
    ) -> Summary:
        """
        Create a summary metric.
        
        Args:
            metric_name: Name of the metric
            description: Description of the metric
            labelnames: Tuple of label names
            unit: Unit of the metric (for future OTEL compatibility)
            
        Returns:
            Summary metric instance
        """
        full_name = f"{self.name}_{metric_name}" if self.name else metric_name
        return Summary(
            full_name,
            description,
            labelnames=labelnames,
            registry=self.registry
        )


def _get_telemetry_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract telemetry configuration from main config.
    
    Args:
        config: App Telemetry Configuration Dictionary
        
    Returns:
        Telemetry configuration dictionary with defaults
    """
    return {
        "enabled": config.get("enabled", False),
        "exporter": config.get("exporter", "prometheus"),
        "metrics_path": config.get("metrics_path", "/metrics"),
        "metrics_port": int(config.get("metrics_port", 8080)),  # Port for separate metrics server
        "service_name": config.get("service_name", "swe-agent-default"),
        "service_version": config.get("service_version", "1.0.0"),
        "labels": config.get("labels", {}),
        "prometheus": config.get("prometheus", {})
    }


def setup_telemetry(config: Dict[str, Any]) -> None:
    """
    Initialize core telemetry infrastructure for the service.

    Sets up the Prometheus registry and starts the dedicated metrics ASGI
    server.  Does **not** initialise any service-specific metrics (HTTP
    middleware, review metrics, etc.) — each service entry-point is
    responsible for calling its own ``initialize_*_metrics()`` after this
    function returns.

    Idempotent: safe to call multiple times; subsequent calls are no-ops.

    Args:
        config: Telemetry configuration dictionary (typically
                ``app_config["telemetry"]`` with service-specific overrides).

    Raises:
        ValueError: If exporter type is not supported.
        RuntimeError: If the metrics server fails to start.
    """
    global _metrics_initialized

    if _metrics_initialized:
        return

    # Apply configuration (validates exporter type and sets Prometheus registry)
    initialize_metrics_config(config)
    # Start a dedicated metrics ASGI server if a port is configured
    start_metrics_server(config)
    _metrics_initialized = True

    # Initialize OTEL event emitter (logs/events to OTEL Collector)
    try:
        from src.providers.telemetry.otel_events import init_otel_events
        otel_config = config.get("otel", {})
        if "service_name" not in otel_config:
            otel_config["service_name"] = config.get("service_name", "swe-agent")
        init_otel_events(otel_config)
    except Exception as e:
        logger.warning(f"OTEL event emitter init failed, continuing without OTEL events: {e}", exc_info=True)

    logger.info("Telemetry initialized successfully")


def initialize_metrics_config(config: Dict[str, Any]) -> None:
    """
    Initialize and apply telemetry configuration for metrics.
    
    This extracts and validates telemetry settings and prepares the
    Prometheus registry. It does not start any servers and does not flip
    the global initialization flag; higher-level orchestration is done by
    `setup_telemetry`.
    
    Args:
        config: Main application configuration dictionary (should have
                telemetry config already modified with service-specific values)
    
    Raises:
        ValueError: If exporter type is not supported
    """
    global _registry
    
    telemetry_config = _get_telemetry_config(config)
    
    if not telemetry_config.get("enabled", True):
        return

    exporter_type = telemetry_config.get("exporter", "prometheus").lower()
    if exporter_type != "prometheus":
        raise ValueError(
            f"Unsupported exporter type: {exporter_type}. "
            f"Currently only 'prometheus' exporter is supported."
        )
    
    # Use default registry (can be extended to use custom registry)
    _registry = REGISTRY


def start_metrics_server(config: Dict[str, Any]) -> None:
    """
    Start a dedicated metrics ASGI server if configured.
    
    When `telemetry.metrics_port` is a positive integer, a lightweight
    ASGI app serving `/metrics` is started on that port using a background
    daemon thread. Safe to call multiple times; no-ops if already running
    on the same port or when telemetry is disabled.
    
    Args:
        config: Main application configuration dictionary
    """
    telemetry_config = _get_telemetry_config(config)
    
    if not telemetry_config.get("enabled", True):
        return
    
    metrics_port = telemetry_config.get("metrics_port")
    if metrics_port and metrics_port > 0:
        _start_metrics_server(metrics_port)


def get_meter(name: str, version: Optional[str] = None) -> Meter:
    """
    Get a Meter instance for creating metrics.
    
    Args:
        name: Name of the meter (typically the module/component name)
        version: Optional version string for the meter (for future OTEL compatibility)
        
    Returns:
        Meter instance for creating metrics
        
    Raises:
        RuntimeError: If metrics have not been initialized
        
    Example:
        meter = get_meter("api.router")
        counter = meter.create_counter("api_requests_total", "Total API requests")
        counter.labels(method="GET", path="/api/v1/health").inc()
        
        histogram = meter.create_histogram("api_request_duration_seconds", "Request duration")
        histogram.labels(method="GET", path="/api/v1/health").observe(0.123)
    """
    if not _metrics_initialized:
        raise RuntimeError(
            "Metrics not initialized. Call setup_telemetry(config) during startup."
        )
    
    return Meter(name, _registry)


def _start_metrics_server(port: int) -> None:
    """
    Start a separate uvicorn ASGI server on the specified port for metrics.

    This creates a lightweight FastAPI app that only serves the metrics endpoint,
    running in a background thread. This is useful when metrics need to be exposed
    on a different port than the main application (e.g., for Prometheus scraping).

    Uses ``uvicorn.Server`` directly (instead of ``uvicorn.run()``) to avoid
    installing signal handlers, which is only allowed on the main thread and
    would conflict with the main application server.

    Args:
        port: Port number to start the metrics server on
    """
    global _metrics_server_thread, _metrics_server_port

    if _metrics_server_port == port:
        return

    try:
        import asyncio
        # Create a minimal FastAPI app for metrics only
        from fastapi import FastAPI
        metrics_fastapi_app = FastAPI(title="SWE Agent Metrics", docs_url=None, redoc_url=None)

        # Mount the metrics ASGI app
        metrics_asgi_app = make_asgi_app(_registry)
        metrics_fastapi_app.mount("/metrics", metrics_asgi_app)

        # Add root endpoint that redirects to metrics
        @metrics_fastapi_app.get("/")
        async def metrics_root():
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url="/metrics")

        # Start uvicorn server in a background daemon thread.
        # We use uvicorn.Server + uvicorn.Config instead of uvicorn.run()
        # because uvicorn.run() calls asyncio.run() which tries to install
        # signal handlers — only allowed on the main thread (raises ValueError
        # on Python 3.13 and silently breaks the main server's event loop).
        def run_metrics_server():
            try:
                config = uvicorn.Config(
                    metrics_fastapi_app,
                    host="0.0.0.0",
                    port=port,
                    log_level="error",
                    access_log=False,
                )
                server = uvicorn.Server(config)
                # Disable signal handler installation (not allowed off main thread)
                server.install_signal_handlers = lambda: None
                loop = asyncio.new_event_loop()
                loop.run_until_complete(server.serve())
            except Exception as e:
                logger.error(f"Metrics server thread error: {e}", exc_info=True)

        _metrics_server_thread = threading.Thread(
            target=run_metrics_server,
            daemon=True,
            name=f"metrics-server-{port}"
        )
        _metrics_server_thread.start()
        _metrics_server_port = port

        logger.debug(f"Metrics ASGI server started on port {port}")
    except Exception as e:
        logger.error(
            f"Failed to start metrics server on port {port}: {e}",
            exc_info=True
        )
        raise


def is_metrics_initialized() -> bool:
    """
    Check if metrics have been initialized.
    
    Returns:
        True if metrics are initialized, False otherwise
    """
    return _metrics_initialized

