"""
Database Instrumentation

Provides metrics for database operations:
- Query duration (histogram)
- Connection pool state (gauges)
"""

import time
from contextlib import contextmanager
from typing import Generator

from src.providers.logger import Logger
from src.providers.telemetry.core import get_meter, is_metrics_initialized

logger = Logger("DatabaseInstrumentation")

# Database metrics
_db_meter = None
_db_query_duration = None
_db_pool_connections = None
_db_pool_checkedout = None
_db_pool_overflow = None


def _initialize_db_metrics():
    """Initialize database metrics if not already initialized."""
    global _db_meter, _db_query_duration, _db_pool_connections, _db_pool_checkedout, _db_pool_overflow
    
    if not is_metrics_initialized():
        return
    
    if _db_query_duration is not None:
        return  # Already initialized
    
    try:
        _db_meter = get_meter("dependency")
        _db_query_duration = _db_meter.create_histogram(
            "db_query_duration_seconds",
            "Database query duration in seconds",
            labelnames=("database", "operation", "status"),
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, float('inf'))
        )
        _db_pool_connections = _db_meter.create_gauge(
            "db_pool_connections",
            "Total connections in the database pool (checked out + idle)",
            labelnames=("database",)
        )
        _db_pool_checkedout = _db_meter.create_gauge(
            "db_pool_checkedout",
            "Number of connections currently checked out (in use)",
            labelnames=("database",)
        )
        _db_pool_overflow = _db_meter.create_gauge(
            "db_pool_overflow",
            "Number of overflow connections currently in use",
            labelnames=("database",)
        )
        logger.info("Database metrics initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database metrics: {e}", exc_info=True)


@contextmanager
def track_db_query(operation: str, database: str = "default") -> Generator[None, None, None]:
    """
    Context manager to track database query duration.
    
    Args:
        operation: Type of operation (select, insert, update, delete, etc.)
        database: Database name for the query (default: "default")
        
    Example:
        with track_db_query("select", "swe_agent"):
            result = db.query(User).all()
    """
    _initialize_db_metrics()
    
    start_time = time.time()
    status = "success"
    
    try:
        yield
    except Exception:
        status = "error"
        raise
    finally:
        duration = time.time() - start_time
        if _db_query_duration is not None:
            _db_query_duration.labels(
                database=database,
                operation=operation,
                status=status
            ).observe(duration)


def record_db_query(
    operation: str,
    status: str,
    duration: float,
    database: str = "default",
) -> None:
    """
    Record a DB query duration metric.
    
    Use this when you can't use the context manager (e.g., with SQLAlchemy events).
    
    Args:
        operation: Type of operation (select, insert, update, delete, etc.)
        status: Query status ("success" or "error")
        duration: Query duration in seconds
        database: Database name (default: "default")
    """
    _initialize_db_metrics()
    if _db_query_duration is not None:
        _db_query_duration.labels(
            database=database,
            operation=operation,
            status=status,
        ).observe(duration)


def update_db_pool_metrics(
    database: str,
    pool_size: int,
    checkedout: int,
    overflow: int,
) -> None:
    """
    Update database connection pool gauge metrics.
    
    Args:
        database: Database name for labeling
        pool_size: Total connections in pool (idle + checked out, excluding overflow)
        checkedout: Number of connections currently in use
        overflow: Number of overflow connections currently in use
    """
    _initialize_db_metrics()
    if _db_pool_connections is not None:
        _db_pool_connections.labels(database=database).set(pool_size + overflow)
    if _db_pool_checkedout is not None:
        _db_pool_checkedout.labels(database=database).set(checkedout)
    if _db_pool_overflow is not None:
        _db_pool_overflow.labels(database=database).set(overflow)

