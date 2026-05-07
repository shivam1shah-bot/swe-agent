"""
Database provider for the SWE Agent.

Main entry point for database operations with configuration injection.
"""

import logging
from typing import Dict, Any
from sqlalchemy import text

from .connection import initialize_engine, close_engine, get_engine
from .session import session_factory
from src.migrations.manager import MigrationManager

logger = logging.getLogger(__name__)


def _mask_sensitive_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a copy of config with sensitive information masked for logging.

    Args:
        config: Original configuration dictionary

    Returns:
        Dictionary with sensitive values masked
    """
    masked_config = config.copy()
    sensitive_keys = ['password', 'passwd', 'pwd', 'secret', 'key', 'token', 'uri']

    for key in masked_config:
        if any(sensitive_key in key.lower() for sensitive_key in sensitive_keys):
            if masked_config[key]:
                masked_config[key] = '***masked***'

    return masked_config


class DatabaseProvider:
    """
    Main database provider that manages connections, sessions, and migrations.

    This class handles database initialization, configuration injection,
    and provides access to database operations.
    """

    def __init__(self):
        self._initialized = False
        self._migration_manager = None

    def initialize(self, config: Dict[str, Any]) -> None:
        """
        Initialize the database provider with configuration.

        Args:
            config: Configuration dictionary containing database settings
        """
        if self._initialized:
            logger.warning("Database provider already initialized")
            return

        logger.info("Initializing database provider")

        # Extract database configuration
        # Try both nested (providers.database) and direct (database) config paths
        db_config = config.get("providers", {}).get("database", {})
        if not db_config:
            db_config = config.get("database", {})

        if not db_config:
            logger.warning("No database configuration found, using defaults")
            db_config = self._get_default_config()
        else:
            # Log configuration with sensitive data masked
            masked_config = _mask_sensitive_config(db_config)
            logger.info(f"Using database configuration: {masked_config}")

        # Initialize database engine
        engine = initialize_engine({"database": db_config})

        # Initialize session factory
        session_factory.initialize()

        # Initialize migration manager
        self._migration_manager = MigrationManager(engine)

        self._initialized = True
        logger.info("Database provider initialized successfully")

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default database configuration."""
        return {
            "host": "localhost",
            "port": 3306,
            "username": "root",
            "password": "",
            "database": "swe_agent",
            "pool_size": 10,
            "max_overflow": 20,
            "pool_timeout": 30,
            "pool_recycle": 3600,
            "echo": False
        }

    def is_initialized(self) -> bool:
        """Check if the database provider is initialized."""
        return self._initialized

    def get_migration_manager(self) -> MigrationManager:
        """
        Get the migration manager.

        Returns:
            MigrationManager instance

        Raises:
            RuntimeError: If provider has not been initialized
        """
        if not self._initialized:
            raise RuntimeError("Database provider not initialized. Call initialize() first.")

        return self._migration_manager

    def run_migrations(self) -> None:
        """Run pending database migrations."""
        if not self._initialized:
            raise RuntimeError("Database provider not initialized. Call initialize() first.")

        logger.info("Running database migrations")
        self._migration_manager.run_migrations()
        logger.info("Database migrations completed")

    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the database connection.

        Returns:
            Dictionary containing health check results
        """
        if not self._initialized:
            return {
                "status": "error",
                "message": "Database provider not initialized"
            }

        try:
            import time
            start_time = time.time()

            engine = get_engine()
            with engine.connect() as conn:
                # Test basic connectivity
                result = conn.execute(text("SELECT 1 as health_check"))
                result.fetchone()

                # Test connection pool info (safely)
                pool = engine.pool
                pool_status = {}
                try:
                    # Safely get pool metrics - not all methods exist in all SQLAlchemy versions
                    if hasattr(pool, 'size'):
                        pool_status["size"] = pool.size()
                    if hasattr(pool, 'checkedin'):
                        pool_status["checked_in"] = pool.checkedin()
                    if hasattr(pool, 'checkedout'):
                        pool_status["checked_out"] = pool.checkedout()
                    if hasattr(pool, 'overflow'):
                        pool_status["overflow"] = pool.overflow()
                    if hasattr(pool, 'invalidated'):
                        pool_status["invalidated"] = pool.invalidated()
                except (AttributeError, Exception) as e:
                    pool_status["error"] = f"Pool metrics unavailable: {e}"

            response_time = round((time.time() - start_time) * 1000, 2)

            return {
                "status": "healthy",
                "message": "Database connection successful",
                "response_time_ms": response_time,
                "pool_status": pool_status
            }
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "error",
                "message": f"Database connection failed: {str(e)}",
                "error_type": type(e).__name__
            }

    def close(self) -> None:
        """Close the database provider and cleanup resources."""
        if not self._initialized:
            return

        logger.info("Closing database provider")

        # Close session factory
        session_factory.close()

        # Close database engine
        close_engine()

        self._initialized = False
        self._migration_manager = None

        logger.info("Database provider closed")


# Global database provider instance
database_provider = DatabaseProvider()