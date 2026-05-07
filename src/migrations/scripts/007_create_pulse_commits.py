"""
Create pulse_commits and pulse_commit_prompts tables for AI usage tracking.
"""

import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)


def upgrade(engine):
    """Create pulse_commits and pulse_commit_prompts tables."""
    logger.info("Creating pulse_commits and pulse_commit_prompts tables")

    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS pulse_commits (
                id CHAR(14) PRIMARY KEY,
                commit_hash VARCHAR(64) NOT NULL UNIQUE,
                repo VARCHAR(255) NOT NULL,
                branch VARCHAR(255),
                author_email VARCHAR(255),
                commit_author VARCHAR(255),
                commit_message TEXT,
                commit_timestamp VARCHAR(50),
                timestamp VARCHAR(50),
                unix_ts DOUBLE,
                files_changed INT NOT NULL DEFAULT 0,
                diff_summary TEXT,
                prompt_count INT NOT NULL DEFAULT 0,
                input_tokens INT NOT NULL DEFAULT 0,
                output_tokens INT NOT NULL DEFAULT 0,
                cache_read_tokens INT NOT NULL DEFAULT 0,
                cache_creation_tokens INT NOT NULL DEFAULT 0,
                estimated_cost_usd DOUBLE NOT NULL DEFAULT 0.0,
                total_lines_added INT NOT NULL DEFAULT 0,
                ai_lines INT NOT NULL DEFAULT 0,
                human_lines INT NOT NULL DEFAULT 0,
                ai_percentage DOUBLE NOT NULL DEFAULT 0.0,
                file_attribution JSON,
                created_at BIGINT NOT NULL,
                updated_at BIGINT NOT NULL,

                INDEX idx_pulse_commits_hash (commit_hash),
                INDEX idx_pulse_commits_repo (repo),
                INDEX idx_pulse_commits_author_email (author_email),
                INDEX idx_pulse_commits_unix_ts (unix_ts),
                INDEX idx_created_at (created_at),
                INDEX idx_updated_at (updated_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS pulse_commit_prompts (
                id CHAR(14) PRIMARY KEY,
                commit_id CHAR(14) NOT NULL,
                prompt TEXT,
                timestamp VARCHAR(50),
                model VARCHAR(100),
                turn_type VARCHAR(50),
                cost_usd DOUBLE NOT NULL DEFAULT 0.0,
                tools_used JSON,
                skill_invoked VARCHAR(255),
                assistant_preview TEXT,
                turn_id CHAR(14),
                created_at BIGINT NOT NULL,
                updated_at BIGINT NOT NULL,

                INDEX idx_pulse_cp_commit_id (commit_id),
                INDEX idx_pulse_cp_turn_id (turn_id),
                INDEX idx_created_at (created_at),
                INDEX idx_updated_at (updated_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """))
        conn.commit()
        logger.info("pulse_commits and pulse_commit_prompts tables created successfully")


def downgrade(engine):
    """Drop pulse_commit_prompts then pulse_commits (FK order)."""
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS pulse_commit_prompts"))
        conn.execute(text("DROP TABLE IF EXISTS pulse_commits"))
        conn.commit()
    logger.info("pulse_commits and pulse_commit_prompts tables dropped")
