"""
Process Instrumentation

Tracks process-level resource metrics:
- File descriptors
- Memory usage (already available from prometheus_client)
- GC collections (already available from prometheus_client)
"""

from src.providers.logger import Logger
from src.providers.telemetry.core import is_metrics_initialized

logger = Logger("ProcessInstrumentation")

# Process metrics
_process_open_fds = None


def _initialize_process_metrics():
    """Initialize process resource metrics if not already initialized."""
    global _process_open_fds
    
    if not is_metrics_initialized():
        return
    
    if _process_open_fds is not None:
        return  # Already initialized
    
    try:
        # prometheus_client ships a default ProcessCollector that already
        # exposes process_open_fds, process_resident_memory_bytes, etc.
        # We check the registry once (no per-collector logging) and skip
        # creation if the metric already exists to avoid duplicates.
        try:
            from prometheus_client import REGISTRY
            existing = {
                name
                for collector in REGISTRY._collector_to_names
                if hasattr(collector, '_name')
                for name in [collector._name]
            }
            if 'process_open_fds' in existing:
                return  # already provided by default collector
        except Exception:
            pass

        logger.debug("Process resource metrics — using default prometheus_client collectors")
    except Exception as e:
        logger.error(f"Failed to initialize process metrics: {e}", exc_info=True)



# Initialize metrics on module import
_initialize_process_metrics()

