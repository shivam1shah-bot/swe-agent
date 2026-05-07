"""
Add agents_catalogue_items table migration.

Creates the agents_catalogue_items table for storing agent catalogue use cases
with clean enum values (api, micro-frontend).
"""

import logging
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)


def upgrade(engine):
    """Create the agents_catalogue_items table with clean enum values."""
    logger.info("Creating agents_catalogue_items table")
    
    with engine.connect() as conn:
        # Check if new table exists first
        result = conn.execute(text("""
            SELECT COUNT(*) as count 
            FROM information_schema.tables 
            WHERE table_schema = DATABASE() 
            AND table_name = 'agents_catalogue_items'
        """))
        table_exists = result.fetchone()[0] > 0
        
        if table_exists:
            logger.info("Table agents_catalogue_items already exists, attempting to recreate...")
            try:
                # Try to drop existing table if it exists (requires DROP privilege)
                logger.info("Dropping existing agents_catalogue_items table...")
                conn.execute(text("DROP TABLE IF EXISTS agents_catalogue_items"))
                logger.info("Successfully dropped existing agents_catalogue_items table")
            except OperationalError as e:
                if "DROP command denied" in str(e):
                    logger.warning("DROP command denied - table already exists, skipping recreation")
                    logger.info("Agents catalogue items table already exists and cannot be dropped due to permissions")
                    return
                else:
                    raise
        
        # Create agents_catalogue_items table with new enum format
        logger.info("Creating agents_catalogue_items table with clean enum values...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS agents_catalogue_items (
                id VARCHAR(36) PRIMARY KEY,
                name VARCHAR(255) NOT NULL UNIQUE,
                description TEXT,
                type ENUM('api', 'micro-frontend') NOT NULL,
                lifecycle ENUM('experimental', 'production', 'deprecated') DEFAULT 'experimental',
                owners TEXT NOT NULL,
                tags TEXT,
                created_at BIGINT NOT NULL,
                updated_at BIGINT NOT NULL,
                
                INDEX idx_name (name),
                INDEX idx_type (type),
                INDEX idx_lifecycle (lifecycle),
                INDEX idx_created_at (created_at),
                UNIQUE KEY uk_name (name)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """))
        
        conn.commit()
        logger.info("Successfully created agents_catalogue_items table with clean enum values")


def downgrade(engine):
    """Drop the agents_catalogue_items table."""
    logger.info("Dropping agents_catalogue_items table")
    
    with engine.connect() as conn:
        try:
            conn.execute(text("DROP TABLE IF EXISTS agents_catalogue_items"))
            conn.commit()
            logger.info("Successfully dropped agents_catalogue_items table")
        except OperationalError as e:
            if "DROP command denied" in str(e):
                logger.warning("DROP command denied - cannot drop agents_catalogue_items table due to permissions")
                logger.info("Manual intervention required to drop agents_catalogue_items table")
            else:
                raise


# Migration metadata
__description__ = "Add agents_catalogue_items table with clean enum values for agent catalogue"
__rollback_sql__ = """
DROP TABLE IF EXISTS agents_catalogue_items;
""" 