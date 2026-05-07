"""
HTTP Client Instrumentation

Provides metrics for outbound HTTP calls to external services:
- Call duration (histogram)
- Status codes
- Service and endpoint tracking
"""

import time
from contextlib import contextmanager
from typing import Union, Generator

from src.providers.logger import Logger
from src.providers.telemetry.core import get_meter, is_metrics_initialized

logger = Logger("HttpClientInstrumentation")

# External API call metrics
_http_meter = None
_external_api_call_duration = None


def _initialize_http_client_metrics():
    """Initialize HTTP client metrics if not already initialized."""
    global _http_meter, _external_api_call_duration
    
    if not is_metrics_initialized():
        return
    
    if _external_api_call_duration is not None:
        return  # Already initialized
    
    try:
        _http_meter = get_meter("dependency")
        _external_api_call_duration = _http_meter.create_histogram(
            "external_api_call_duration_seconds",
            "External API call duration in seconds",
            labelnames=("service", "operation", "endpoint_template", "method", "status_code"),
            buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, float('inf'))
        )
        logger.info("HTTP client metrics initialized")
    except Exception as e:
        logger.error(f"Failed to initialize HTTP client metrics: {e}", exc_info=True)


@contextmanager
def track_external_api_call(
    service: str,
    endpoint_template: str,
    method: str = "GET",
    operation: str = "unknown",
) -> Generator[dict, None, None]:
    """
    Context manager to track external API call duration.

    Yields a mutable ``result`` dict.  Callers **should** set
    ``result["status_code"]`` inside the ``with`` block so the metric
    records the real HTTP status.  If the block raises, ``status_code``
    is automatically set to ``"error"``.

    Args:
        service: Service name (e.g., "github", "slack", "s3")
        endpoint_template: Low-cardinality endpoint template (e.g., "/repos/{owner}/{repo}")
        method: HTTP method (GET, POST, etc.)
        operation: Bounded operation/workflow identifier (e.g., "e2e-onboarding")

    Example:
        with track_external_api_call("github", "/repos/{owner}/{repo}", "GET",
                                     operation="list-repos") as ctx:
            response = requests.get(url)
            ctx["status_code"] = str(response.status_code)
    """
    _initialize_http_client_metrics()

    start_time = time.time()
    result: dict = {"status_code": "200"}

    try:
        yield result
    except Exception:
        result["status_code"] = "error"
        raise
    finally:
        duration = time.time() - start_time
        if _external_api_call_duration is not None:
            _external_api_call_duration.labels(
                service=service,
                operation=operation,
                endpoint_template=endpoint_template,
                method=method,
                status_code=result["status_code"],
            ).observe(duration)


def record_external_api_call(
    service: str,
    operation: str,
    endpoint_template: str,
    method: str,
    status_code: Union[int, str],
    duration: float
) -> None:
    """
    Record an external API call metric.
    
    Use this when you can't use the context manager.
    
    Args:
        service: Service name (e.g., "github", "slack")
        operation: Bounded operation/workflow identifier (e.g., "e2e-onboarding")
        endpoint_template: Low-cardinality endpoint template
        method: HTTP method
        status_code: HTTP status code
        duration: Call duration in seconds
    """
    _initialize_http_client_metrics()
    
    if _external_api_call_duration is not None:
        _external_api_call_duration.labels(
            service=service,
            operation=operation,
            endpoint_template=endpoint_template,
            method=method,
            status_code=str(status_code)
        ).observe(duration)

