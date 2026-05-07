"""
UserConnector model — one row per user (unique on user_email).

connector_id is a merged JSON blob holding identity fields from ALL connectors
the user has triggered tasks through. New keys are added on each interaction;
existing keys are never overwritten.

Example connector_id after using both Slack and Dashboard:
  {
    "slack_id":     "U08CLA6QH0U",
    "slack_handle": "arnav.gaur",
    "username":     "arnav.gaur@razorpay.com"
  }

Which connector was used for a specific task is stored in task_metadata.connector
on the tasks table, not here.
"""

import time

from sqlalchemy import BigInteger, Column, Index, JSON, String

from .base import Base


class UserConnector(Base):
    __tablename__ = "user_connector"

    id           = Column(String(14),  primary_key=True)
    user_email   = Column(String(255), nullable=False, unique=True)
    connector_id = Column(JSON,        nullable=True)   # merged identity fields across connectors
    created_at   = Column(BigInteger,  default=lambda: int(time.time()))

    __table_args__ = (
        Index("idx_uc_user_email", "user_email"),
    )
