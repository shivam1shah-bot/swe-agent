"""
Cache Instrumentation

Provides metrics for cache operations (Redis, etc.):
- Operation duration (histogram)
- Operation counts by key pattern
"""

import time
from contextlib import contextmanager
from typing import Optional, Generator

from src.providers.logger import Logger
from src.providers.telemetry.core import get_meter, is_metrics_initialized

logger = Logger("CacheInstrumentation")

# Cache metrics
_cache_meter = None
_cache_op_duration = None


def _initialize_cache_metrics():
    """Initialize cache metrics if not already initialized."""
    global _cache_meter, _cache_op_duration
    
    if not is_metrics_initialized():
        return
    
    if _cache_op_duration is not None:
        return  # Already initialized
    
    try:
        _cache_meter = get_meter("dependency")
        _cache_op_duration = _cache_meter.create_histogram(
            "cache_op_duration_seconds",
            "Cache operation duration in seconds",
            labelnames=("operation", "key_pattern", "status"),
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, float('inf'))
        )
        logger.info("Cache metrics initialized")
    except Exception as e:
        logger.error(f"Failed to initialize cache metrics: {e}", exc_info=True)


@contextmanager
def track_cache_op(operation: str, key_pattern: Optional[str] = None) -> Generator[None, None, None]:
    """
    Context manager to track cache operation duration.
    
    Args:
        operation: Type of operation (get, set, delete, etc.)
        key_pattern: Key pattern for grouping (optional)
        
    Example:
        with track_cache_op("get", "user:*"):
            value = cache.get("user:123")
    """
    _initialize_cache_metrics()
    
    start_time = time.time()
    status = "success"
    
    try:
        yield
    except Exception:
        status = "error"
        raise
    finally:
        duration = time.time() - start_time
        if _cache_op_duration is not None:
            _cache_op_duration.labels(
                operation=operation,
                key_pattern=key_pattern or "unknown",
                status=status
            ).observe(duration)




