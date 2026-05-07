"""
Database session management for the SWE Agent.

Provides session factory and context managers for database operations.
"""

import logging
import re
from contextlib import contextmanager
from typing import Generator, Optional
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from .connection import get_engine, _mask_database_url

logger = logging.getLogger(__name__)

# Global session factory
_session_factory: Optional[sessionmaker] = None


def _mask_error_message(error_message: str) -> str:
    """
    Mask any database URLs that might appear in error messages.

    Args:
        error_message: Original error message

    Returns:
        Error message with any database URLs masked
    """
    # Pattern to find database URLs in error messages
    url_pattern = r'([a-zA-Z]+\+[a-zA-Z]+://[^@]+:[^@]+@[^\s]+)'

    def replace_url(match):
        return _mask_database_url(match.group(1))

    return re.sub(url_pattern, replace_url, error_message)


class SessionFactory:
    """Factory for creating database sessions."""

    def __init__(self):
        self._session_maker = None

    def initialize(self) -> None:
        """Initialize the session factory with the database engine."""
        global _session_factory

        if _session_factory is not None:
            logger.warning("Session factory already initialized")
            return

        engine = get_engine()
        _session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        self._session_maker = _session_factory
        logger.info("Session factory initialized")

    def create_session(self) -> Session:
        """
        Create a new database session.

        Returns:
            SQLAlchemy Session instance

        Raises:
            RuntimeError: If session factory has not been initialized
        """
        if _session_factory is None:
            raise RuntimeError("Session factory not initialized. Call initialize() first.")

        return _session_factory()

    def close(self) -> None:
        """Close the session factory."""
        global _session_factory

        if _session_factory is not None:
            logger.info("Closing session factory")
            _session_factory = None
            self._session_maker = None


# Global session factory instance
session_factory = SessionFactory()


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions with automatic transaction management.

    Yields:
        SQLAlchemy Session instance

    Example:
        with get_session() as session:
            task = session.query(Task).first()
            # Session is automatically committed and closed
    """
    if _session_factory is None:
        raise RuntimeError("Session factory not initialized. Call session_factory.initialize() first.")

    session = _session_factory()
    try:
        yield session
        session.commit()
        logger.debug("Database transaction committed successfully")
    except SQLAlchemyError as e:
        session.rollback()
        masked_error = _mask_error_message(str(e))

        # Check for connection timeout errors
        error_str = str(e).lower()
        if "lost connection" in error_str or "timeout" in error_str or "2013" in error_str:
            logger.error(f"Database connection timeout detected: {masked_error}")
        else:
            logger.error(f"Database transaction rolled back due to error: {masked_error}")
        raise
    except Exception as e:
        session.rollback()
        masked_error = _mask_error_message(str(e))
        logger.error(f"Database transaction rolled back due to unexpected error: {masked_error}")
        raise
    finally:
        session.close()
        logger.debug("Database session closed")


@contextmanager
def get_readonly_session() -> Generator[Session, None, None]:
    """
    Context manager for read-only database sessions.

    Yields:
        SQLAlchemy Session instance (read-only)

    Example:
        with get_readonly_session() as session:
            tasks = session.query(Task).all()
            # No commit, session is just closed
    """
    if _session_factory is None:
        raise RuntimeError("Session factory not initialized. Call session_factory.initialize() first.")

    session = _session_factory()
    try:
        yield session
        logger.debug("Read-only database session completed")
    except Exception as e:
        masked_error = _mask_error_message(str(e))
        logger.error(f"Error in read-only session: {masked_error}")
        raise
    finally:
        session.close()
        logger.debug("Read-only database session closed")


def create_session() -> Session:
    """
    Create a new database session (for dependency injection).

    Returns:
        SQLAlchemy Session instance

    Note:
        Caller is responsible for closing the session.
    """
    global _session_factory
    if _session_factory is None:
        raise RuntimeError("Session factory not initialized. Call session_factory.initialize() first.")

    return _session_factory()