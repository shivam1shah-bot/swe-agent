"""
Task model for the SWE Agent.
"""

import json
import time
from typing import Dict, Any, Optional

from sqlalchemy import Column, Integer, String, Text, Index

from .base import Base, TaskStatus


class Task(Base):
    """Task model for storing task information"""
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), default=TaskStatus.PENDING.value)
    progress = Column(Integer, default=0)

    # Core task data
    parameters = Column(Text, nullable=True)  # JSON string of parameters
    result = Column(Text, nullable=True)  # JSON string of result
    task_metadata = Column(Text, nullable=True)  # JSON string for performance and other metadata

    # FK → user_connector.id — who triggered this task
    user_id = Column(String(14), nullable=True)

    created_at = Column(Integer, default=lambda: int(time.time()))
    updated_at = Column(Integer, default=lambda: int(time.time()), onupdate=lambda: int(time.time()))

    # Add indexes for common queries
    __table_args__ = (
        Index('idx_status', 'status'),
        Index('idx_created_at', 'created_at'),
        Index('idx_updated_at', 'updated_at'),
        Index('idx_user_id', 'user_id'),
    )

    @property
    def metadata_dict(self) -> Dict[str, Any]:
        """Parse task_metadata JSON into dictionary."""
        if not self.task_metadata:
            return {}
        try:
            return json.loads(self.task_metadata)
        except (json.JSONDecodeError, TypeError):
            return {}

    @metadata_dict.setter
    def metadata_dict(self, value: Dict[str, Any]):
        """Set task_metadata from dictionary."""
        self.task_metadata = json.dumps(value) if value else None

    @property
    def result_dict(self) -> Dict[str, Any]:
        """Parse result JSON into dictionary."""
        if not self.result:
            return {}
        try:
            return json.loads(self.result)
        except (json.JSONDecodeError, TypeError):
            return {}

    @result_dict.setter
    def result_dict(self, value: Dict[str, Any]):
        """Set result from dictionary."""
        self.result = json.dumps(value) if value else None

    def update_metadata(self, **kwargs):
        """Update specific metadata fields."""
        current = self.metadata_dict
        for key, value in kwargs.items():
            if isinstance(value, dict) and key in current and isinstance(current[key], dict):
                current[key].update(value)
            else:
                current[key] = value
        self.metadata_dict = current

    def set_performance_start(self):
        """Set task start time for performance tracking."""
        self.update_metadata(performance={
            "start_time": int(time.time() * 1000),
            "retry_count": 0
        })

    def set_performance_end(self, queue_wait_time_ms: Optional[int] = None):
        """Set task end time and calculate execution time."""
        current_metadata = self.metadata_dict
        performance = current_metadata.get("performance", {})

        end_time = int(time.time() * 1000)
        start_time = performance.get("start_time", end_time)
        execution_time = end_time - start_time

        performance.update({
            "end_time": end_time,
            "execution_time_ms": execution_time
        })

        if queue_wait_time_ms is not None:
            performance["queue_wait_time_ms"] = queue_wait_time_ms

        self.update_metadata(performance=performance)

    def increment_retry_count(self):
        """Increment retry count in performance metadata."""
        current_metadata = self.metadata_dict
        performance = current_metadata.get("performance", {})
        performance["retry_count"] = performance.get("retry_count", 0) + 1
        self.update_metadata(performance=performance)
