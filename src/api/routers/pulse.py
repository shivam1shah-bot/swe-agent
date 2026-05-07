"""
Pulse router — AI usage tracking dashboard endpoints.
"""

import logging
from enum import Enum
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.dependencies import get_db_session, get_current_user
from src.models.pulse_schemas import (
    TurnIngest, EditIngest, CommitIngest,
    PulseHealthResponse, IngestResponse,
    OverviewResponse, ReposResponse, CommitsResponse, PromptsResponse, PeopleResponse,
)
from src.services.pulse_ingest_service import ingest_turn, ingest_edit, ingest_commit
from src.services.pulse_aggregation_service import (
    aggregate_overview,
    aggregate_repos,
    aggregate_commits,
    aggregate_prompts,
    aggregate_people,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class RepoSort(str, Enum):
    cost = "cost"
    ai_pct = "ai_pct"
    tokens = "tokens"
    prompts = "prompts"
    ai_lines = "ai_lines"


class CommitSort(str, Enum):
    cost = "cost"
    tokens = "tokens"
    ai_lines = "ai_lines"
    ai_pct = "ai_pct"
    prompts = "prompts"
    date = "date"


class PromptSort(str, Enum):
    cost = "cost"
    tokens = "tokens"
    output = "output"
    newest = "newest"


class PeopleSort(str, Enum):
    cost = "cost"
    tokens = "tokens"
    prompts = "prompts"
    lines = "lines"


# ---------------------------------------------------------------------------
# Read endpoints (dashboard) — require authentication
# ---------------------------------------------------------------------------

@router.get("/overview", response_model=OverviewResponse)
def get_overview(
    days: Optional[int] = Query(default=None, ge=1, le=365),
    db: Session = Depends(get_db_session),
    current_user: Dict[str, str] = Depends(get_current_user),
):
    try:
        return aggregate_overview(db, days)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in pulse overview: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/repos", response_model=ReposResponse)
def get_repos(
    sort: RepoSort = RepoSort.cost,
    days: Optional[int] = Query(default=None, ge=1, le=365),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db_session),
    current_user: Dict[str, str] = Depends(get_current_user),
):
    try:
        return aggregate_repos(db, sort.value, days, limit, offset)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in pulse repos: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/commits", response_model=CommitsResponse)
def get_commits(
    sort: CommitSort = CommitSort.cost,
    days: Optional[int] = Query(default=None, ge=1, le=365),
    repo: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db_session),
    current_user: Dict[str, str] = Depends(get_current_user),
):
    try:
        return aggregate_commits(db, sort.value, days, repo, limit, offset)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in pulse commits: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/prompts", response_model=PromptsResponse)
def get_prompts(
    sort: PromptSort = PromptSort.cost,
    days: Optional[int] = Query(default=None, ge=1, le=365),
    repo: Optional[str] = None,
    email: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db_session),
    current_user: Dict[str, str] = Depends(get_current_user),
):
    try:
        return aggregate_prompts(db, sort.value, days, repo, email, limit, offset)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in pulse prompts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/people", response_model=PeopleResponse)
def get_people(
    sort: PeopleSort = PeopleSort.cost,
    days: Optional[int] = Query(default=None, ge=1, le=365),
    repo: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db_session),
    current_user: Dict[str, str] = Depends(get_current_user),
):
    try:
        return aggregate_people(db, sort.value, days, repo, limit, offset)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in pulse people: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Ingest endpoints (data collection from developer laptops)
# No authentication — CLI clients send data without user tokens.
# Payload size is bounded by max_length / ge=0 constraints on schema fields.
# ---------------------------------------------------------------------------

@router.post("/ingest/turn", response_model=IngestResponse)
def post_ingest_turn(
    payload: TurnIngest,
    db: Session = Depends(get_db_session),
):
    try:
        record = payload.model_dump()
        ingest_turn(db, record)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error ingesting turn: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ingest failed")


@router.post("/ingest/edit", response_model=IngestResponse)
def post_ingest_edit(
    payload: EditIngest,
    db: Session = Depends(get_db_session),
):
    try:
        record = payload.model_dump()
        ingest_edit(db, record)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error ingesting edit: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ingest failed")


@router.post("/ingest/commit", response_model=IngestResponse)
def post_ingest_commit(
    payload: CommitIngest,
    db: Session = Depends(get_db_session),
):
    try:
        record = payload.model_dump()
        ingest_commit(db, record)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error ingesting commit: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ingest failed")


@router.get("/health", response_model=PulseHealthResponse)
def pulse_health():
    return {"status": "healthy", "service": "pulse"}
