"""
Create PR reviews table migration.

Creates the pr_reviews table for storing AI-powered PR review jobs.
"""

import logging
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)


def upgrade(engine):
    """Create the pr_reviews table."""
    logger.info("Creating pr_reviews table")

    with engine.connect() as conn:
        # Create pr_reviews table
        logger.info("Creating pr_reviews table...")
        conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS pr_reviews (
                id VARCHAR(36) PRIMARY KEY,
                idempotency_key VARCHAR(255) UNIQUE,
                status VARCHAR(20) NOT NULL DEFAULT 'accepted',
                pr_metadata TEXT NOT NULL,
                pr_context TEXT,
                correlation_id VARCHAR(36) NOT NULL,
                error_info TEXT,
                enqueued_at BIGINT,
                started_at BIGINT,
                completed_at BIGINT,
                created_at BIGINT NOT NULL,
                updated_at BIGINT NOT NULL,

                INDEX idx_pr_reviews_idempotency_key (idempotency_key),
                INDEX idx_pr_reviews_status (status),
                INDEX idx_pr_reviews_correlation_id (correlation_id),
                INDEX idx_pr_reviews_created_at (created_at),
                INDEX idx_pr_reviews_enqueued_at (enqueued_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
            )
        )

        conn.commit()
        logger.info("pr_reviews table created successfully")


def downgrade(engine):
    """Drop the pr_reviews table."""
    logger.info("Rolling back pr_reviews table")

    with engine.connect() as conn:
        logger.info("Dropping pr_reviews table...")
        try:
            conn.execute(text("DROP TABLE IF EXISTS pr_reviews"))
        except OperationalError as e:
            logger.warning(f"Could not drop pr_reviews table: {e}")

        conn.commit()
        logger.info("pr_reviews table rollback completed")


# Migration metadata
__description__ = "Create pr_reviews table for AI-powered PR review jobs"
__rollback_sql__ = """
DROP TABLE IF EXISTS pr_reviews;
"""
