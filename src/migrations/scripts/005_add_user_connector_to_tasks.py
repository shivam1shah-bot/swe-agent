"""
Create user_connector table and add tasks.user_id.

user_connector: one row per user (unique on user_email).
  connector_id — merged JSON of identity fields across all connectors.
                 New keys added; existing keys never overwritten.

Which connector triggered a task is stored in task_metadata.connector on tasks.
tasks.user_id — FK reference to user_connector.id (VARCHAR 14).
"""

import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)


def upgrade(engine):
    logger.info("Running migration 005: create user_connector, add tasks.user_id")

    with engine.connect() as conn:
        # 1. Create user_connector table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_connector (
                id           VARCHAR(14)  NOT NULL,
                user_email   VARCHAR(255) NOT NULL,
                connector_id JSON         DEFAULT NULL,
                created_at   BIGINT       DEFAULT NULL,

                PRIMARY KEY (id),
                UNIQUE KEY uq_uc_user_email (user_email),
                INDEX idx_uc_user_email (user_email)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """))
        conn.commit()
        logger.info("user_connector table created")

        # 2. Add tasks.user_id
        try:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN user_id VARCHAR(14) DEFAULT NULL"))
            conn.execute(text("CREATE INDEX idx_tasks_user_id ON tasks (user_id)"))
            conn.commit()
            logger.info("Added tasks.user_id column")
        except Exception as e:
            if "Duplicate column" in str(e) or "Duplicate key name" in str(e):
                logger.info("tasks.user_id already exists, skipping")
            else:
                raise

    logger.info("Migration 005 complete")


def downgrade(engine):
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE tasks DROP COLUMN user_id"))
            conn.commit()
        except Exception:
            pass
        conn.execute(text("DROP TABLE IF EXISTS user_connector"))
        conn.commit()
    logger.info("Migration 005 downgrade complete")
