"""
HTTP Request Metrics Middleware for FastAPI.

Tracks HTTP request metrics including:
- Request rate (http_requests_total)
- Error rate (filtered by status_code)
- Request duration (http_request_duration_seconds)
"""

import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Match

from src.providers.logger import Logger
from src.providers.telemetry import get_meter, is_metrics_initialized

logger = Logger("MetricsMiddleware")

# Initialize metrics
_metrics_meter = None
_http_requests_total = None
_http_request_duration_seconds = None


def initialize_http_metrics():
    """
    Initialize HTTP metrics globally.
    
    This should be called during application startup, after telemetry is initialized.
    """
    global _metrics_meter, _http_requests_total, _http_request_duration_seconds
    
    if not is_metrics_initialized():
        logger.debug("Metrics not initialized, skipping HTTP metrics setup")
        return
    
    if _http_requests_total is not None:
        logger.debug("HTTP metrics already initialized")
        return  # Already initialized
    
    try:
        _metrics_meter = get_meter("http")
        _http_requests_total = _metrics_meter.create_counter(
            "requests_total",
            "Total number of HTTP requests received",
            labelnames=("method", "handler", "status_code")
        )
        _http_request_duration_seconds = _metrics_meter.create_histogram(
            "request_duration_seconds",
            "HTTP request duration in seconds",
            labelnames=("method", "handler", "status_code"),
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float('inf'))
        )
        logger.info("HTTP metrics initialized")
    except Exception as e:
        logger.error(f"Failed to initialize HTTP metrics: {e}", exc_info=True)


def _get_handler_path(request: Request) -> str:
    """
    Extract the handler path from the request.
    Args:
        request: FastAPI request object
        
    Returns:
        Handler path string with resolved path parameters
        (e.g., "/api/v1/agents-catalogue/workflow/e2e-onboarding")
    """
    # Use the actual request path which contains resolved path parameters
    # This gives us the real path values instead of the route pattern
    return request.url.path


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track HTTP request metrics.
    
    Tracks:
    - Request rate (http_requests_total)
    - Error rate (via status_code label)
    - Request duration (http_request_duration_seconds)
    """
    
    def __init__(self, app, excluded_paths: list = None):
        """
        Initialize the metrics middleware.
        
        Args:
            app: FastAPI application instance
            excluded_paths: List of paths to exclude from metrics tracking
        """
        super().__init__(app)
        self.logger = Logger("MetricsMiddleware")
        self.excluded_paths = excluded_paths or [
            "/metrics",
            "/metrics/",
            "/health",
            "/api/v1/health",
            "/api/v1/health/liveness",
            "/api/v1/health/readiness"
        ]
        
        self.logger.info(f"Metrics middleware initialized with {len(self.excluded_paths)} excluded paths")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request through metrics middleware.
        
        Args:
            request: FastAPI request object
            call_next: Next middleware/handler in chain
            
        Returns:
            Response from downstream
        """
        # Skip metrics for excluded paths
        if self._should_skip_metrics(request):
            return await call_next(request)
        
        # Skip if metrics not initialized
        if _http_requests_total is None or _http_request_duration_seconds is None:
            return await call_next(request)
        
        # Track request start time
        start_time = time.time()
        method = request.method
        handler = _get_handler_path(request)
        
        try:
            # Process request
            response = await call_next(request)
            
            # Get status code
            status_code = response.status_code
            
            # Record metrics
            _http_requests_total.labels(
                method=method,
                handler=handler,
                status_code=str(status_code)
            ).inc()
            
            # Record duration
            duration = time.time() - start_time
            _http_request_duration_seconds.labels(
                method=method,
                handler=handler,
                status_code=str(status_code)
            ).observe(duration)
            
            return response
            
        except Exception as e:
            # Record error metrics
            # Try to get status code from exception (e.g., HTTPException)
            status_code = "500"  # Default to 500
            if hasattr(e, 'status_code'):
                status_code = str(e.status_code)
            elif hasattr(e, 'status'):
                status_code = str(e.status)
            
            duration = time.time() - start_time
            
            _http_requests_total.labels(
                method=method,
                handler=handler,
                status_code=status_code
            ).inc()
            
            _http_request_duration_seconds.labels(
                method=method,
                handler=handler,
                status_code=status_code
            ).observe(duration)
            
            # Re-raise the exception
            raise
    
    def _should_skip_metrics(self, request: Request) -> bool:
        """
        Check if metrics should be skipped for this request.
        
        Args:
            request: FastAPI request object
            
        Returns:
            True if metrics should be skipped
        """
        path = request.url.path
        return any(path.startswith(excluded) for excluded in self.excluded_paths)

