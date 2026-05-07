"""
Create pulse_edits table for AI file edit tracking.
"""

import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)


def upgrade(engine):
    """Create the pulse_edits table."""
    logger.info("Creating pulse_edits table")

    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS pulse_edits (
                id CHAR(14) PRIMARY KEY,
                prompt_id VARCHAR(255),
                session_id VARCHAR(255),
                repo VARCHAR(255) NOT NULL,
                branch VARCHAR(255),
                author_email VARCHAR(255),
                timestamp VARCHAR(50),
                unix_ts DOUBLE,
                tool_category VARCHAR(50),
                tool_name VARCHAR(100),
                file_edited TEXT,
                files_changed JSON,
                files_new JSON,
                lines_added_by_ai INT NOT NULL DEFAULT 0,
                lines_removed_by_ai INT NOT NULL DEFAULT 0,
                diff_stats JSON,
                model VARCHAR(100),
                prompt TEXT,
                skill_invoked VARCHAR(255),
                assistant_preview TEXT,
                input_tokens INT NOT NULL DEFAULT 0,
                output_tokens INT NOT NULL DEFAULT 0,
                cache_read_tokens INT NOT NULL DEFAULT 0,
                cache_creation_tokens INT NOT NULL DEFAULT 0,
                session_cost_usd DOUBLE,
                created_at BIGINT NOT NULL,
                updated_at BIGINT NOT NULL,

                INDEX idx_pulse_edits_prompt_id (prompt_id),
                INDEX idx_pulse_edits_repo (repo),
                INDEX idx_pulse_edits_author_email (author_email),
                INDEX idx_pulse_edits_unix_ts (unix_ts),
                INDEX idx_created_at (created_at),
                INDEX idx_updated_at (updated_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """))
        conn.commit()
        logger.info("pulse_edits table created successfully")


def downgrade(engine):
    """Drop the pulse_edits table."""
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS pulse_edits"))
        conn.commit()
    logger.info("pulse_edits table dropped")
