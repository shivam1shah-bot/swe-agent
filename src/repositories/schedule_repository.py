"""
Schedule repository for cron-based skill execution.

Provides data access operations for Schedule entities.
"""

import time
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from .base import SQLAlchemyBaseRepository
from .exceptions import EntityNotFoundError, QueryExecutionError, TransactionError
from src.models.schedule import Schedule
from src.providers.logger import Logger


class SQLAlchemyScheduleRepository(SQLAlchemyBaseRepository[Schedule]):
    """SQLAlchemy implementation of Schedule repository."""

    def __init__(self, session: Session):
        super().__init__(session, Schedule)
        self.logger = Logger("ScheduleRepository")

    def create(self, schedule: Schedule) -> Schedule:
        """Create a new schedule."""
        try:
            current_time = int(time.time())
            if not schedule.created_at:
                schedule.created_at = current_time
            if not schedule.updated_at:
                schedule.updated_at = current_time
            return super().create(schedule)
        except SQLAlchemyError as e:
            self.logger.error("Failed to create schedule", extra={"error": str(e)})
            raise TransactionError("create_schedule", str(e))

    def get_by_id(self, schedule_id: str) -> Optional[Schedule]:
        """Get a schedule by ID."""
        try:
            return super().get_by_id(schedule_id)
        except SQLAlchemyError as e:
            self.logger.error("Failed to get schedule by ID", extra={"schedule_id": schedule_id, "error": str(e)})
            raise QueryExecutionError(f"get_by_id({schedule_id})", str(e))

    def get_all(self, limit: Optional[int] = None, offset: Optional[int] = None) -> List[Schedule]:
        """Get all schedules ordered by created_at descending."""
        try:
            query = self.session.query(Schedule).order_by(Schedule.created_at.desc())
            if offset is not None:
                query = query.offset(offset)
            if limit is not None:
                query = query.limit(limit)
            return query.all()
        except SQLAlchemyError as e:
            self.logger.error("Failed to list schedules", extra={"error": str(e)})
            raise QueryExecutionError("get_all", str(e))

    def list_enabled(self) -> List[Schedule]:
        """Get all enabled schedules."""
        try:
            return self.session.query(Schedule).filter(Schedule.enabled == True).all()
        except SQLAlchemyError as e:
            self.logger.error("Failed to list enabled schedules", extra={"error": str(e)})
            raise QueryExecutionError("list_enabled", str(e))

    def update_fields(self, schedule_id: str, **fields) -> Optional[Schedule]:
        """Update specific fields on a schedule by ID."""
        try:
            schedule = self.get_by_id(schedule_id)
            if not schedule:
                return None
            for key, value in fields.items():
                if hasattr(schedule, key):
                    setattr(schedule, key, value)
            schedule.updated_at = int(time.time())
            self.session.flush()
            return schedule
        except SQLAlchemyError as e:
            self.logger.error("Failed to update schedule", extra={"schedule_id": schedule_id, "error": str(e)})
            raise TransactionError(f"update_fields({schedule_id})", str(e))

    def delete(self, schedule_id: str) -> bool:
        """Delete a schedule by ID."""
        try:
            return super().delete(schedule_id)
        except SQLAlchemyError as e:
            self.logger.error("Failed to delete schedule", extra={"schedule_id": schedule_id, "error": str(e)})
            raise TransactionError(f"delete({schedule_id})", str(e))
