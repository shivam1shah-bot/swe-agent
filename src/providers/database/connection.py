"""
Database connection management for the SWE Agent.

Handles database engine creation and connection pooling.
"""

import logging
import re
import time
from typing import Optional
from urllib.parse import quote
from sqlalchemy import create_engine, Engine, event
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)

# Global engine instance
_engine: Optional[Engine] = None

_SQL_OP_RE = re.compile(r"^\s*(select|insert|update|delete|replace|call)\b", re.IGNORECASE)
_QUERY_START_KEY = "swe_agent_query_start"


def _extract_sql_operation(statement: str) -> str:
    if not statement:
        return "unknown"
    m = _SQL_OP_RE.search(statement)
    return (m.group(1).lower() if m else "unknown")


def _attach_db_metrics(engine: Engine, database_name: str = "default") -> None:
    """
    Attach SQLAlchemy event listeners to measure DB query latencies and pool metrics.
    
    Args:
        engine: SQLAlchemy Engine instance
        database_name: Database name for metric labeling
    """
    from src.providers.telemetry.instrumentation.database import record_db_query, update_db_pool_metrics

    def _update_pool_gauges():
        """Update pool gauge metrics from current pool state."""
        try:
            pool = engine.pool
            update_db_pool_metrics(
                database=database_name,
                pool_size=pool.size(),
                checkedout=pool.checkedout(),
                overflow=pool.overflow(),
            )
        except Exception:
            # Metrics must never break DB operations
            pass

    @event.listens_for(engine, "before_cursor_execute")
    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        conn.info[_QUERY_START_KEY] = time.perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        start = conn.info.pop(_QUERY_START_KEY, None)
        if start is None:
            return
        duration = time.perf_counter() - start
        op = _extract_sql_operation(statement)
        try:
            record_db_query(operation=op, status="success", duration=duration, database=database_name)
        except Exception:
            # Metrics must never break DB operations
            return

    @event.listens_for(engine, "handle_error")
    def _handle_error(exception_context):
        conn = exception_context.connection
        if conn is None:
            return
        start = conn.info.pop(_QUERY_START_KEY, None)
        if start is None:
            return
        duration = time.perf_counter() - start
        stmt = exception_context.statement or ""
        op = _extract_sql_operation(stmt)
        try:
            record_db_query(operation=op, status="error", duration=duration, database=database_name)
        except Exception:
            return

    # Pool connection events - update gauges on checkout/checkin
    @event.listens_for(engine, "checkout")
    def _on_checkout(dbapi_conn, connection_record, connection_proxy):
        """Called when a connection is checked out from the pool."""
        _update_pool_gauges()

    @event.listens_for(engine, "checkin")
    def _on_checkin(dbapi_conn, connection_record):
        """Called when a connection is returned to the pool."""
        _update_pool_gauges()


def _mask_database_url(url: str) -> str:
    """
    Mask sensitive information in database URLs for logging.
    
    Args:
        url: Database URL potentially containing credentials
        
    Returns:
        URL with credentials masked
    """
    # Pattern to match database URLs with credentials
    # Matches: protocol://username:password@host:port/database
    pattern = r'(.*://)([^:]+):([^@]+)(@.*)'
    match = re.match(pattern, url)
    
    if match:
        protocol, username, password, host_and_db = match.groups()
        # Mask the password but keep first/last characters if longer than 4 chars
        if len(password) > 4:
            masked_password = password[0] + '*' * (len(password) - 2) + password[-1]
        else:
            masked_password = '***'
        return f"{protocol}{username}:{masked_password}{host_and_db}"
    
    return url


def create_database_engine(
    host: str,
    port: int,
    username: str,
    password: str,
    database: str,
    pool_size: int = 10,
    max_overflow: int = 20,
    pool_timeout: int = 30,
    pool_recycle: int = 3600,
    pool_pre_ping: bool = False,
    echo: bool = False
) -> Engine:
    """
    Create a SQLAlchemy engine with connection pooling.
    
    Args:
        host: Database host
        port: Database port
        username: Database username
        password: Database password
        database: Database name
        pool_size: Number of connections to maintain in pool
        max_overflow: Maximum overflow connections
        pool_timeout: Timeout for getting connection from pool
        pool_recycle: Time to recycle connections (seconds)
        pool_pre_ping: Enable connection health checks before use
        echo: Whether to echo SQL statements
        
    Returns:
        SQLAlchemy Engine instance
    """
    # URL-encode username and password to handle special characters
    encoded_username = quote(username, safe='')
    encoded_password = quote(password, safe='')
    
    database_url = f"mysql+pymysql://{encoded_username}:{encoded_password}@{host}:{port}/{database}"
    
    engine = create_engine(
        database_url,
        poolclass=QueuePool,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_recycle=pool_recycle,
        pool_pre_ping=pool_pre_ping,
        echo=echo,
        # MySQL specific settings for connection stability
        connect_args={
            "charset": "utf8mb4",
            "autocommit": False,
            "connect_timeout": 10,
            "read_timeout": 30,
            "write_timeout": 30,
        }
    )

    # Centralized DB query duration and pool metrics
    try:
        _attach_db_metrics(engine, database_name=database)
    except Exception as e:
        logger.warning(f"Failed to attach DB metrics listeners: {e}")
    
    # Log with masked URL for security
    masked_url = _mask_database_url(database_url)
    logger.info(f"Created database engine: {masked_url}")
    return engine


def initialize_engine(config: dict) -> Engine:
    """
    Initialize the global database engine from configuration.
    
    Args:
        config: Database configuration dictionary
        
    Returns:
        SQLAlchemy Engine instance
    """
    global _engine
    
    if _engine is not None:
        logger.warning("Database engine already initialized, returning existing instance")
        return _engine
    
    db_config = config.get("database", {})
    
    _engine = create_database_engine(
        host=db_config.get("host", "localhost"),
        port=db_config.get("port", 3306),
        username=db_config.get("user", db_config.get("username", "root")),
        password=db_config.get("password", ""),
        database=db_config.get("name", db_config.get("database", "swe_agent")),
        pool_size=db_config.get("pool_size", 10),
        max_overflow=db_config.get("max_overflow", 20),
        pool_timeout=db_config.get("pool_timeout", 30),
        pool_recycle=db_config.get("pool_recycle", 3600),
        pool_pre_ping=db_config.get("pool_pre_ping", False),
        echo=db_config.get("echo", False)
    )
    
    return _engine


def get_engine() -> Engine:
    """
    Get the global database engine.
    
    Returns:
        SQLAlchemy Engine instance
        
    Raises:
        RuntimeError: If engine has not been initialized
    """
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call initialize_engine() first.")
    
    return _engine


def close_engine() -> None:
    """Close the global database engine and cleanup connections."""
    global _engine
    
    if _engine is not None:
        logger.info("Closing database engine")
        _engine.dispose()
        _engine = None 