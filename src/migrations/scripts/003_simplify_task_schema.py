"""
Simplify task schema migration.

Removes workflow-related columns (message, workflow_name, workflow_config) 
and adds task_metadata column for performance tracking and additional information.
Uses task_metadata instead of metadata to avoid SQLAlchemy built-in attribute conflicts.
"""

import logging
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)


def upgrade(engine):
    """Remove workflow columns and add metadata column."""
    logger.info("Simplifying task schema - removing workflow columns and adding metadata")
    
    with engine.connect() as conn:
        # Check if columns exist before attempting to drop them
        logger.info("Checking existing table structure...")
        
        try:
            # Add task_metadata column first (if it doesn't exist)
            logger.info("Adding task_metadata column...")
            conn.execute(text("""
                ALTER TABLE tasks 
                ADD COLUMN task_metadata TEXT AFTER result
            """))
            logger.info("Added task_metadata column successfully")
        except OperationalError as e:
            if "Duplicate column name" in str(e):
                logger.info("task_metadata column already exists, skipping")
            else:
                logger.warning(f"Could not add task_metadata column: {e}")
        
        try:
            # Drop workflow-related columns
            logger.info("Dropping message column...")
            conn.execute(text("ALTER TABLE tasks DROP COLUMN message"))
            logger.info("Dropped message column successfully")
        except OperationalError as e:
            if "check that column/key exists" in str(e) or "doesn't exist" in str(e):
                logger.info("message column doesn't exist, skipping")
            else:
                logger.warning(f"Could not drop message column: {e}")
        
        try:
            logger.info("Dropping workflow_name column...")
            conn.execute(text("ALTER TABLE tasks DROP COLUMN workflow_name"))
            logger.info("Dropped workflow_name column successfully")
        except OperationalError as e:
            if "check that column/key exists" in str(e) or "doesn't exist" in str(e):
                logger.info("workflow_name column doesn't exist, skipping")
            else:
                logger.warning(f"Could not drop workflow_name column: {e}")
        
        try:
            logger.info("Dropping workflow_config column...")
            conn.execute(text("ALTER TABLE tasks DROP COLUMN workflow_config"))
            logger.info("Dropped workflow_config column successfully")
        except OperationalError as e:
            if "check that column/key exists" in str(e) or "doesn't exist" in str(e):
                logger.info("workflow_config column doesn't exist, skipping")
            else:
                logger.warning(f"Could not drop workflow_config column: {e}")
        
        try:
            # Drop workflow-related indexes if they exist
            logger.info("Dropping workflow-related indexes...")
            try:
                conn.execute(text("DROP INDEX idx_workflow_name ON tasks"))
                logger.info("Dropped idx_workflow_name successfully")
            except OperationalError as e:
                if "check that column/key exists" in str(e) or "doesn't exist" in str(e):
                    logger.info("idx_workflow_name doesn't exist, skipping")
                else:
                    logger.warning(f"Could not drop idx_workflow_name: {e}")
            
            try:
                conn.execute(text("DROP INDEX idx_workflow_name_status ON tasks"))
                logger.info("Dropped idx_workflow_name_status successfully")
            except OperationalError as e:
                if "check that column/key exists" in str(e) or "doesn't exist" in str(e):
                    logger.info("idx_workflow_name_status doesn't exist, skipping")
                else:
                    logger.warning(f"Could not drop idx_workflow_name_status: {e}")
                    
        except OperationalError as e:
            logger.warning(f"Could not drop workflow indexes: {e}")
        
        conn.commit()
        logger.info("Task schema simplification completed successfully")


def downgrade(engine):
    """Restore workflow columns (without data)."""
    logger.info("Restoring workflow columns to task schema")
    
    with engine.connect() as conn:
        try:
            # Add back workflow columns
            logger.info("Adding back workflow columns...")
            conn.execute(text("""
                ALTER TABLE tasks 
                ADD COLUMN message TEXT AFTER progress,
                ADD COLUMN workflow_name VARCHAR(100) NOT NULL DEFAULT 'deprecated' AFTER message,
                ADD COLUMN workflow_config TEXT AFTER workflow_name
            """))
            
            # Recreate workflow indexes
            logger.info("Recreating workflow indexes...")
            conn.execute(text("""
                CREATE INDEX idx_workflow_name ON tasks (workflow_name)
            """))
            conn.execute(text("""
                CREATE INDEX idx_workflow_name_status ON tasks (workflow_name, status)
            """))
            
            # Remove task_metadata column
            logger.info("Removing task_metadata column...")
            conn.execute(text("ALTER TABLE tasks DROP COLUMN task_metadata"))
            
            conn.commit()
            logger.info("Workflow columns restored successfully")
            
        except OperationalError as e:
            logger.error(f"Failed to restore workflow columns: {e}")
            conn.rollback()
            raise


# Migration metadata
__description__ = "Simplify task schema by removing workflow columns and adding task_metadata"
__rollback_sql__ = """
ALTER TABLE tasks 
ADD COLUMN message TEXT AFTER progress,
ADD COLUMN workflow_name VARCHAR(100) NOT NULL DEFAULT 'deprecated' AFTER message,
ADD COLUMN workflow_config TEXT AFTER workflow_name;

CREATE INDEX idx_workflow_name ON tasks (workflow_name);
CREATE INDEX idx_workflow_name_status ON tasks (workflow_name, status);

ALTER TABLE tasks DROP COLUMN task_metadata;
""" 