"""
Connector metadata utility.

Two things happen on each task trigger:

1. user_connector table (upsert per user_email):
   - One row per user — unique on user_email
   - connector_id JSON merges identity fields across all connectors:
     add new keys, never overwrite existing ones
   - No connector name stored here — pure user identity

2. tasks.task_metadata (which connector was used for THIS task):
   - Stores {"connector": {"name": "slack", "source_id": "...", "user_email": "..."}}
   - Lets us know the trigger source per task
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)

CONNECTOR_SLACK = "slack"
CONNECTOR_DEVREV = "devrev"
CONNECTOR_DASHBOARD = "dashboard"

_BASE62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def generate_id() -> str:
    """Generate a 14-character base62 unique ID."""
    ts = int(time.time() * 1000)
    ts_chars = []
    for _ in range(8):
        ts_chars.append(_BASE62[ts % 62])
        ts //= 62
    ts_part = ''.join(reversed(ts_chars))
    rand_bytes = int.from_bytes(os.urandom(4), 'big')
    rand_chars = []
    for _ in range(6):
        rand_chars.append(_BASE62[rand_bytes % 62])
        rand_bytes //= 62
    return ts_part + ''.join(reversed(rand_chars))


def store_connector_metadata(
    task_id: str,
    connector_name: str,
    user_email: str,
    user_name: str = "",
    source_id: Optional[str] = None,
    extra: Optional[dict] = None,
) -> None:
    """
    1. Upsert user_connector — merge new identity keys without overwriting existing.
    2. Store connector info in task_metadata for this task.
    3. Set tasks.user_id to the user_connector row id.
    """
    try:
        from sqlalchemy import text
        from src.providers.database.connection import get_engine

        extra = extra or {}

        # Identity fields contributed by this connector interaction
        new_fields: dict = {}
        if connector_name == CONNECTOR_SLACK:
            new_fields = {
                "slack_id":     extra.get("user_id", ""),
                "slack_handle": user_name,
            }
        elif connector_name == CONNECTOR_DASHBOARD:
            new_fields = {"username": user_name or user_email}
        elif connector_name == CONNECTOR_DEVREV:
            new_fields = {
                "ticket_id":  source_id or "",
                "created_by": user_email,
            }
        else:
            new_fields = {"id": extra.get("user_id", "") or user_email}

        new_fields = {k: v for k, v in new_fields.items() if v}

        engine = get_engine()
        with engine.connect() as conn:
            user_connector_id = None

            # Only upsert user_connector if we have a user_email
            if user_email and user_email.strip():
                row = conn.execute(
                    text("SELECT id, connector_id FROM user_connector WHERE user_email = :email"),
                    {"email": user_email},
                ).fetchone()

                if row:
                    user_connector_id = row[0]
                    existing = json.loads(row[1]) if row[1] else {}
                    # Merge: new_fields fills gaps, existing values take precedence
                    merged = {**new_fields, **existing}
                    if merged != existing:
                        conn.execute(
                            text("UPDATE user_connector SET connector_id = :cid WHERE id = :id"),
                            {"cid": json.dumps(merged), "id": user_connector_id},
                        )
                else:
                    user_connector_id = generate_id()
                    conn.execute(
                        text("""
                            INSERT INTO user_connector (id, user_email, connector_id, created_at)
                            VALUES (:id, :email, :cid, :ts)
                        """),
                        {
                            "id":    user_connector_id,
                            "email": user_email,
                            "cid":   json.dumps(new_fields),
                            "ts":    int(time.time()),
                        },
                    )
                conn.commit()

            # Always store connector info in task_metadata; only set user_id if we have one
            task_row = conn.execute(
                text("SELECT task_metadata FROM tasks WHERE id = :id"),
                {"id": task_id},
            ).fetchone()

            meta = {}
            if task_row and task_row[0]:
                try:
                    meta = json.loads(task_row[0])
                except Exception:
                    meta = {}

            meta["connector"] = {
                "name":       connector_name,
                "user_email": user_email or None,
                "source_id":  source_id,
            }

            if user_connector_id:
                conn.execute(
                    text("UPDATE tasks SET user_id = :uid, task_metadata = :meta WHERE id = :id"),
                    {"uid": user_connector_id, "meta": json.dumps(meta), "id": task_id},
                )
            else:
                conn.execute(
                    text("UPDATE tasks SET task_metadata = :meta WHERE id = :id"),
                    {"meta": json.dumps(meta), "id": task_id},
                )
            conn.commit()

        logger.info(
            f"Stored connector metadata for task {task_id}",
            extra={"connector": connector_name, "user_email": user_email},
        )
    except Exception as exc:
        logger.warning(f"Failed to store connector metadata for task {task_id}: {exc}")
