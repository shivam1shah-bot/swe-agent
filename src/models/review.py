"""
PR Review model for the SWE Agent.

Stores PR review job information and status.
"""

import json
import time
from typing import Dict, Any, Optional

from sqlalchemy import Column, Integer, String, Text, Index

from .base import Base
from src.constants.pr_review import ReviewStatus


class PRReview(Base):
    """PR Review model for storing review job information."""

    __tablename__ = "pr_reviews"

    # Primary key: ULID with rev_ prefix (e.g., rev_01JH8NM3W8C4M7R7JX7WZ9QY5Q)
    id = Column(String(36), primary_key=True, index=True)

    # Idempotency key for deduplication (format: repo_name:pr_number:run_id)
    idempotency_key = Column(String(255), unique=True, nullable=True, index=True)

    # Review status
    status = Column(String(20), default=ReviewStatus.ACCEPTED.value, nullable=False)

    # PR metadata stored as JSON
    pr_metadata = Column(Text, nullable=False)  # JSON: pr_url, pr_number, repository, author, etc.

    # Additional PR context
    pr_context = Column(Text, nullable=True)

    # Correlation ID for request tracing
    correlation_id = Column(String(36), nullable=False, index=True)

    # Error info when status = failed (stored as JSON)
    error_info = Column(Text, nullable=True)

    # Review lifecycle timestamps (stored as Unix timestamps)
    enqueued_at = Column(Integer, nullable=True)
    started_at = Column(Integer, nullable=True)
    completed_at = Column(Integer, nullable=True)

    # Record timestamps
    created_at = Column(Integer, default=lambda: int(time.time()))
    updated_at = Column(Integer, default=lambda: int(time.time()), onupdate=lambda: int(time.time()))

    # Indexes for common queries
    __table_args__ = (
        Index("idx_pr_reviews_status", "status"),
        Index("idx_pr_reviews_created_at", "created_at"),
        Index("idx_pr_reviews_enqueued_at", "enqueued_at"),
        Index("idx_pr_reviews_repository_pr", "pr_metadata"),  # For JSON queries if supported
    )

    @property
    def pr_metadata_dict(self) -> Dict[str, Any]:
        """Parse pr_metadata JSON into dictionary."""
        if not self.pr_metadata:
            return {}
        try:
            return json.loads(self.pr_metadata)
        except (json.JSONDecodeError, TypeError):
            return {}

    @pr_metadata_dict.setter
    def pr_metadata_dict(self, value: Dict[str, Any]):
        """Set pr_metadata from dictionary."""
        self.pr_metadata = json.dumps(value) if value else None

    @property
    def error_info_dict(self) -> Optional[Dict[str, Any]]:
        """Parse error_info JSON into dictionary."""
        if not self.error_info:
            return None
        try:
            return json.loads(self.error_info)
        except (json.JSONDecodeError, TypeError):
            return None

    @error_info_dict.setter
    def error_info_dict(self, value: Optional[Dict[str, Any]]):
        """Set error_info from dictionary."""
        self.error_info = json.dumps(value) if value else None

    def set_enqueued(self):
        """Mark review as enqueued with current timestamp."""
        self.status = ReviewStatus.QUEUED.value
        self.enqueued_at = int(time.time())
        self.updated_at = int(time.time())

    def set_running(self):
        """Mark review as running with current timestamp."""
        self.status = ReviewStatus.RUNNING.value
        self.started_at = int(time.time())
        self.updated_at = int(time.time())

    def set_completed(self):
        """Mark review as completed with current timestamp."""
        self.status = ReviewStatus.COMPLETED.value
        self.completed_at = int(time.time())
        self.updated_at = int(time.time())

    def set_failed(self, error_code: str, error_message: str):
        """Mark review as failed with error info."""
        self.status = ReviewStatus.FAILED.value
        self.completed_at = int(time.time())
        self.error_info_dict = {
            "code": error_code,
            "message": error_message,
        }
        self.updated_at = int(time.time())

    def get_repository(self) -> Optional[str]:
        """Get repository from pr_metadata."""
        return self.pr_metadata_dict.get("repository")

    def get_pr_number(self) -> Optional[int]:
        """Get PR number from pr_metadata."""
        return self.pr_metadata_dict.get("pr_number")
