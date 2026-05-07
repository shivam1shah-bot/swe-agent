"""
Instrumentation Package

Auto-instrumentation modules for various infrastructure components:
- database: Database query and pool metrics
- cache: Cache operation metrics
- http_client: External HTTP call metrics
- process: Process-level resource metrics
"""

from .database import (
    track_db_query,
    record_db_query,
    update_db_pool_metrics,
)
from .cache import track_cache_op
from .http_client import (
    track_external_api_call,
    record_external_api_call,
)

__all__ = [
    # Database
    'track_db_query',
    'record_db_query',
    'update_db_pool_metrics',
    # Cache
    'track_cache_op',
    # HTTP Client
    'track_external_api_call',
    'record_external_api_call',
]

