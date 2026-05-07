"""
Schedules router for FastAPI.

Provides CRUD endpoints for managing cron-based skill execution schedules.
API pods handle DB CRUD only — APScheduler runs in a dedicated scheduler pod.
"""

import json
import time
from typing import Any, Dict, List, Optional

from croniter import croniter
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.dependencies import get_db_session
from src.models.schedule import Schedule
from src.providers.auth import require_role
from src.providers.logger import Logger
from src.repositories.schedule_repository import SQLAlchemyScheduleRepository
from src.utils.connector import generate_id

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ScheduleCreate(BaseModel):
    name: str
    skill_name: str
    cron_expression: str
    parameters: Dict[str, Any] = {}
    enabled: bool = True


class ScheduleUpdate(BaseModel):
    name: Optional[str] = None
    cron_expression: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None


class ScheduleResponse(BaseModel):
    id: str
    name: str
    skill_name: str
    cron_expression: str
    parameters: Dict[str, Any]
    enabled: bool
    last_run_at: Optional[int]
    created_at: int
    updated_at: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_repo(session) -> SQLAlchemyScheduleRepository:
    return SQLAlchemyScheduleRepository(session)


def _schedule_to_response(s: Schedule) -> ScheduleResponse:
    return ScheduleResponse(
        id=s.id,
        name=s.name,
        skill_name=s.skill_name,
        cron_expression=s.cron_expression,
        parameters=s.parameters_dict,
        enabled=bool(s.enabled),
        last_run_at=s.last_run_at,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


def _validate_cron(cron_expression: str):
    if not croniter.is_valid(cron_expression):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid cron expression: '{cron_expression}'",
        )


def _publish_reload(schedule_id: str, action: str = "upsert"):
    """Publish a reload signal to Redis so the scheduler pod reacts immediately."""
    try:
        from src.providers.cache import cache_provider
        redis_client = getattr(getattr(cache_provider, "_client", None), "client", None)
        if redis_client:
            redis_client.publish(
                "scheduler:reload",
                json.dumps({"action": action, "schedule_id": schedule_id}),
            )
    except Exception as e:
        Logger("SchedulesRouter").warning(
            f"Could not publish scheduler reload signal: {e}"
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
@require_role(["dashboard", "admin", "splitz", "devops"])
async def create_schedule(request: Request, body: ScheduleCreate, session: Session = Depends(get_db_session)):
    """Create a new cron schedule."""
    _validate_cron(body.cron_expression)

    now = int(time.time())
    schedule = Schedule(
        id=generate_id(),
        name=body.name,
        skill_name=body.skill_name,
        cron_expression=body.cron_expression,
        enabled=body.enabled,
        created_at=now,
        updated_at=now,
    )
    schedule.parameters_dict = body.parameters

    try:
        repo = _get_repo(session)
        created = repo.create(schedule)
        session.commit()
        response = _schedule_to_response(created)
    except Exception as e:
        session.rollback()
        Logger("SchedulesRouter").error(f"Failed to create schedule: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create schedule",
        )

    _publish_reload(response.id, "upsert")
    return response


@router.get("", response_model=List[ScheduleResponse])
@require_role(["dashboard", "admin", "splitz", "devops"])
async def list_schedules(request: Request, session: Session = Depends(get_db_session)):
    """List all schedules."""
    try:
        repo = _get_repo(session)
        schedules = repo.get_all()
        return [_schedule_to_response(s) for s in schedules]
    except Exception as e:
        Logger("SchedulesRouter").error(f"Failed to list schedules: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list schedules",
        )


@router.get("/{schedule_id}", response_model=ScheduleResponse)
@require_role(["dashboard", "admin", "splitz", "devops"])
async def get_schedule(request: Request, schedule_id: str, session: Session = Depends(get_db_session)):
    """Get a schedule by ID."""
    try:
        repo = _get_repo(session)
        schedule = repo.get_by_id(schedule_id)
        if not schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Schedule '{schedule_id}' not found",
            )
        return _schedule_to_response(schedule)
    except HTTPException:
        raise
    except Exception as e:
        Logger("SchedulesRouter").error(f"Failed to get schedule {schedule_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get schedule",
        )


@router.put("/{schedule_id}", response_model=ScheduleResponse)
@require_role(["dashboard", "admin", "splitz", "devops"])
async def update_schedule(request: Request, schedule_id: str, body: ScheduleUpdate, session: Session = Depends(get_db_session)):
    """Update a schedule."""
    if body.cron_expression is not None:
        _validate_cron(body.cron_expression)

    fields: Dict[str, Any] = {}
    if body.name is not None:
        fields["name"] = body.name
    if body.cron_expression is not None:
        fields["cron_expression"] = body.cron_expression
    if body.parameters is not None:
        fields["parameters"] = json.dumps(body.parameters)
    if body.enabled is not None:
        fields["enabled"] = body.enabled

    if not fields:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No fields to update",
        )

    try:
        repo = _get_repo(session)
        updated = repo.update_fields(schedule_id, **fields)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Schedule '{schedule_id}' not found",
            )
        session.commit()
        response = _schedule_to_response(updated)
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        Logger("SchedulesRouter").error(f"Failed to update schedule {schedule_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update schedule",
        )

    action = "upsert" if response.enabled else "remove"
    _publish_reload(schedule_id, action)
    return response


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
@require_role(["dashboard", "admin", "splitz", "devops"])
async def delete_schedule(request: Request, schedule_id: str, session: Session = Depends(get_db_session)):
    """Delete a schedule."""
    try:
        repo = _get_repo(session)
        deleted = repo.delete(schedule_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Schedule '{schedule_id}' not found",
            )
        session.commit()
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        Logger("SchedulesRouter").error(f"Failed to delete schedule {schedule_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete schedule",
        )

    _publish_reload(schedule_id, "remove")


@router.post("/{schedule_id}/trigger", response_model=Dict[str, Any])
@require_role(["dashboard", "admin", "splitz", "devops"])
async def trigger_schedule(request: Request, schedule_id: str, session: Session = Depends(get_db_session)):
    """Manually fire a schedule immediately by calling /agents/run."""
    # Fetch schedule data and let the session close (via Depends) before the slow HTTP call.
    # This avoids holding a DB connection open for the full 30s HTTP timeout.
    try:
        repo = _get_repo(session)
        schedule = repo.get_by_id(schedule_id)
        if not schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Schedule '{schedule_id}' not found",
            )
        skill_name = schedule.skill_name
        parameters = schedule.parameters_dict
        schedule_name = schedule.name
    except HTTPException:
        raise
    except Exception as e:
        Logger("SchedulesRouter").error(f"Failed to fetch schedule {schedule_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch schedule",
        )
    # Session is closed by Depends(get_db_session) here, before the HTTP call below.

    from src.providers.config_loader import get_config
    from src.services.scheduler_service import call_agents_run

    config = get_config()
    success = await call_agents_run(
        config=config,
        skill_name=skill_name,
        parameters=parameters,
        schedule_name=schedule_name,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to trigger schedule — agents/run call failed",
        )

    return {"schedule_id": schedule_id, "status": "triggered"}
