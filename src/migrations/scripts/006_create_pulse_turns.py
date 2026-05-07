"""
Create pulse_turns table for AI usage tracking.
"""

import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)


def upgrade(engine):
    """Create the pulse_turns table."""
    logger.info("Creating pulse_turns table")

    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS pulse_turns (
                id CHAR(14) PRIMARY KEY,
                prompt_id VARCHAR(255) UNIQUE,
                session_id VARCHAR(255),
                repo VARCHAR(255) NOT NULL,
                branch VARCHAR(255),
                author_email VARCHAR(255),
                user_prompt TEXT,
                user_prompt_ts VARCHAR(50),
                assistant_turn_ts VARCHAR(50),
                timestamp VARCHAR(50),
                unix_ts DOUBLE,
                model VARCHAR(100),
                turn_type VARCHAR(50),
                tools_used JSON,
                skill_invoked VARCHAR(255),
                cost_usd DOUBLE,
                assistant_preview TEXT,
                input_tokens INT NOT NULL DEFAULT 0,
                output_tokens INT NOT NULL DEFAULT 0,
                cache_read_tokens INT NOT NULL DEFAULT 0,
                cache_creation_tokens INT NOT NULL DEFAULT 0,
                created_at BIGINT NOT NULL,
                updated_at BIGINT NOT NULL,

                INDEX idx_pulse_turns_prompt_id (prompt_id),
                INDEX idx_pulse_turns_repo (repo),
                INDEX idx_pulse_turns_author_email (author_email),
                INDEX idx_pulse_turns_unix_ts (unix_ts),
                INDEX idx_created_at (created_at),
                INDEX idx_updated_at (updated_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """))
        conn.commit()
        logger.info("pulse_turns table created successfully")


def downgrade(engine):
    """Drop the pulse_turns table."""
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS pulse_turns"))
        conn.commit()
    logger.info("pulse_turns table dropped")
