"""
Telemetry Provider Package

This package provides Prometheus metrics integration using prometheus_client.
Designed to be extensible for future OpenTelemetry integration when packages are stable.

Structure:
- core: Core Meter class, setup functions, registry management
- instrumentation/: Auto-instrumentation for infrastructure components
  - database: DB query and pool metrics
  - cache: Cache operation metrics
  - http_client: External HTTP call metrics
  - process: Process-level resource metrics
- domain/: Business domain-specific metrics
  - claude: Claude/LLM operation metrics
"""

# Core exports
from .core import (
    setup_telemetry,
    get_meter,
    is_metrics_initialized,
    Meter,
)

# Backward compatibility: re-export from instrumentation and domain
# These allow existing imports to continue working during migration

# Database instrumentation
from .instrumentation.database import (
    track_db_query,
    record_db_query,
    update_db_pool_metrics,
)

# Cache instrumentation
from .instrumentation.cache import track_cache_op

# HTTP client instrumentation
from .instrumentation.http_client import (
    track_external_api_call,
    record_external_api_call,
)

# Claude domain metrics
from .domain.claude import (
    track_claude_execution,
    track_mcp_interaction,
)

__all__ = [
    # Core
    'setup_telemetry',
    'get_meter',
    'is_metrics_initialized',
    'Meter',
    # Database
    'track_db_query',
    'record_db_query',
    'update_db_pool_metrics',
    # Cache
    'track_cache_op',
    # HTTP Client
    'track_external_api_call',
    'record_external_api_call',
    # Claude
    'track_claude_execution',
    'track_mcp_interaction',
]
