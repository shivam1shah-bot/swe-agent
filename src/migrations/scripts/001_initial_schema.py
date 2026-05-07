"""
Initial schema migration for the SWE Agent.

Creates the database schema with tasks table including workflow support.
This establishes the baseline schema with workflow columns that will be
simplified in later migrations.
"""

import logging
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)


def upgrade(engine):
    """Create the initial clean schema."""
    logger.info("Creating initial schema")
    
    with engine.connect() as conn:
        # Create tasks table with clean schema
        logger.info("Creating tasks table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tasks (
                id VARCHAR(36) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                status VARCHAR(50) NOT NULL DEFAULT 'pending',
                progress INT DEFAULT 0,
                message TEXT,
                workflow_name VARCHAR(100) NOT NULL,
                workflow_config TEXT,
                parameters TEXT,
                result TEXT,
                created_at BIGINT NOT NULL,
                updated_at BIGINT NOT NULL,
                
                INDEX idx_status (status),
                INDEX idx_workflow_name (workflow_name),
                INDEX idx_workflow_name_status (workflow_name, status),
                INDEX idx_created_at (created_at),
                INDEX idx_updated_at (updated_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """))
        
        # Create migration_history table (enhanced version)
        logger.info("Creating migration_history table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS migration_history (
                id INT PRIMARY KEY AUTO_INCREMENT,
                version_number INT NOT NULL UNIQUE,
                migration_name VARCHAR(255) NOT NULL,
                filename VARCHAR(255) NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                rollback_sql TEXT,
                INDEX idx_version_number (version_number),
                INDEX idx_applied_at (applied_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """))
        
        conn.commit()
        logger.info("Initial schema created successfully")


def downgrade(engine):
    """Drop all tables (clean rollback)."""
    logger.info("Rolling back initial schema")
    
    with engine.connect() as conn:
        # Drop tables in reverse order
        logger.info("Dropping migration_history table...")
        try:
            conn.execute(text("DROP TABLE IF EXISTS migration_history"))
        except OperationalError as e:
            logger.warning(f"Could not drop migration_history table: {e}")
        
        logger.info("Dropping tasks table...")
        try:
            conn.execute(text("DROP TABLE IF EXISTS tasks"))
        except OperationalError as e:
            logger.warning(f"Could not drop tasks table: {e}")
        
        conn.commit()
        logger.info("Initial schema rollback completed")


# Migration metadata
__description__ = "Initial schema with tasks table including workflow support"
__rollback_sql__ = """
DROP TABLE IF EXISTS migration_history;
DROP TABLE IF EXISTS tasks;
""" 