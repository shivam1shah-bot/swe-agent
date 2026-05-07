"""
Schedule model for cron-based skill execution.
"""

import json
import time
from typing import Dict, Any, Optional

from sqlalchemy import BigInteger, Column, String, Text, Boolean, Index, CHAR

from .base import Base


class Schedule(Base):
    """Schedule model for storing cron-based skill execution configurations."""

    __tablename__ = "schedules"

    id = Column(CHAR(14), primary_key=True)
    name = Column(String(255), nullable=False)
    skill_name = Column(String(255), nullable=False)
    cron_expression = Column(String(100), nullable=False)
    parameters = Column(Text, nullable=True)   # JSON string
    enabled = Column(Boolean, default=True, nullable=False)
    last_run_at = Column(BigInteger, nullable=True)
    created_at = Column(BigInteger, default=lambda: int(time.time()), nullable=False)
    updated_at = Column(BigInteger, default=lambda: int(time.time()), onupdate=lambda: int(time.time()), nullable=False)

    __table_args__ = (
        Index('idx_enabled', 'enabled'),
        Index('idx_skill_name', 'skill_name'),
        Index('idx_created_at', 'created_at'),
        Index('idx_updated_at', 'updated_at'),
    )

    @property
    def parameters_dict(self) -> Dict[str, Any]:
        """Parse parameters JSON into dictionary."""
        if not self.parameters:
            return {}
        try:
            return json.loads(self.parameters)
        except (json.JSONDecodeError, TypeError):
            return {}

    @parameters_dict.setter
    def parameters_dict(self, value: Optional[Dict[str, Any]]):
        """Set parameters from dictionary."""
        self.parameters = json.dumps(value) if value else None
