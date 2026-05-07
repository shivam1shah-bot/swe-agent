"""
Create schedules table migration.

Adds the schedules table for cron-based skill execution scheduling.
APScheduler's own apscheduler_jobs table is created automatically by SQLAlchemyJobStore.
"""

import logging
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)


def upgrade(engine):
    """Create the schedules table."""
    logger.info("Creating schedules table")

    with engine.connect() as conn:
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS schedules (
                    id              CHAR(14)     NOT NULL,
                    name            VARCHAR(255) NOT NULL,
                    skill_name      VARCHAR(255) NOT NULL,
                    cron_expression VARCHAR(100) NOT NULL,
                    parameters      TEXT,
                    enabled         TINYINT(1)   NOT NULL DEFAULT 1,
                    last_run_at     BIGINT,
                    created_at      BIGINT       NOT NULL,
                    updated_at      BIGINT       NOT NULL,
                    PRIMARY KEY (id),
                    INDEX idx_enabled    (enabled),
                    INDEX idx_skill_name (skill_name),
                    INDEX idx_created_at (created_at),
                    INDEX idx_updated_at (updated_at)
                )
            """))
            conn.commit()
            logger.info("Schedules table created successfully")
        except OperationalError as e:
            if "already exists" in str(e):
                logger.info("Schedules table already exists, skipping")
            else:
                logger.error(f"Failed to create schedules table: {e}")
                raise


def downgrade(engine):
    """Drop the schedules table."""
    logger.info("Dropping schedules table")

    with engine.connect() as conn:
        try:
            conn.execute(text("DROP TABLE IF EXISTS schedules"))
            conn.commit()
            logger.info("Schedules table dropped successfully")
        except OperationalError as e:
            logger.error(f"Failed to drop schedules table: {e}")
            raise


__description__ = "Create schedules table for cron-based skill execution"
__rollback_sql__ = "DROP TABLE IF EXISTS schedules;"
