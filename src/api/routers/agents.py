"""
Autonomous Agent router.

Provides clean, dedicated endpoints for all autonomous agent modes:
  POST /api/v1/agents/run         - single repo or clean-slate (no repository_url)
  POST /api/v1/agents/batch       - 1-50 repos, one task per repo
  POST /api/v1/agents/multi-repo  - 1-10 repos, single Claude process
"""

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from src.api.routers.agents_catalogue import execute_service_with_timeout, sanitize_parameter_value
from src.api.middleware.rate_limit import get_rate_limit_identifier
from src.providers.auth import require_role
from src.providers.logger import Logger
from src.providers.config_loader import get_config
from src.providers.cache.redis_client import get_redis_client
from ..dependencies import get_logger

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class RunRequest(BaseModel):
    prompt: str = Field(..., description="Task to perform")
    repository_url: Optional[str] = Field(
        None, description="GitHub repo URL (omit for clean-slate)"
    )
    branch: Optional[str] = Field(None, description="Feature branch (optional)")
    skills: List[str] = Field(default_factory=list, description="Skills to inject")
    slack_channel: Optional[str] = Field(None, description="Slack channel to post result to (e.g. #general)")
    agent: Optional[str] = Field(
        None, description="Agent name from claude-plugins (e.g. gng-readiness)"
    )
    source_id: Optional[str] = Field(None, description="Source identifier (e.g. DevRev ticket ID)")
    connector: Optional[str] = Field(None, description="Connector that triggered this task (devrev, dashboard, slack)")


class BatchRequest(BaseModel):
    prompt: str = Field(..., description="Task to apply to every repository")
    repositories: List[Dict[str, Any]] = Field(
        ..., description="List of {repository_url, branch?}"
    )
    skills: List[str] = Field(default_factory=list)
    agent: Optional[str] = Field(None, description="Agent name from claude-plugins")
    source_id: Optional[str] = Field(None, description="Source identifier (e.g. DevRev ticket ID)")
    connector: Optional[str] = Field(None, description="Connector that triggered this task (devrev, dashboard, slack)")

    @field_validator("repositories")
    @classmethod
    def at_least_one(cls, v: list) -> list:
        if not v:
            raise ValueError("At least one repository is required")
        if len(v) > 50:
            raise ValueError(f"Maximum 50 repositories allowed, got {len(v)}")
        return v


class MultiRepoRequest(BaseModel):
    prompt: str = Field(..., description="Task to apply across all repositories")
    repositories: List[Dict[str, Any]] = Field(
        ..., description="List of {repository_url, branch?}"
    )
    skills: List[str] = Field(default_factory=list)
    agent: Optional[str] = Field(None, description="Agent name from claude-plugins")
    source_id: Optional[str] = Field(None, description="Source identifier (e.g. DevRev ticket ID)")
    connector: Optional[str] = Field(None, description="Connector that triggered this task (devrev, dashboard, slack)")
    user_email: Optional[str] = Field(None, description="Email of the user who triggered the task (used when caller is a service account)")

    @field_validator("repositories")
    @classmethod
    def one_to_ten(cls, v: list) -> list:
        if len(v) < 1:
            raise ValueError("Multi-repo requires at least 1 repository")
        if len(v) > 10:
            raise ValueError(f"Multi-repo supports 1-10 repositories, got {len(v)}")
        return v


class AgentResponse(BaseModel):
    task_id: Optional[str] = None
    status: str
    message: str
    metadata: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sanitize(value: Any) -> Any:
    return sanitize_parameter_value(value)


async def _call_service(
    service, parameters: Dict[str, Any], timeout: int = 30
) -> Dict[str, Any]:
    return await execute_service_with_timeout(service, parameters, timeout)


def _get_service(name: str):
    from src.services.agents import (
        AutonomousAgentService,
        AutonomousAgentBatchService,
        AutonomousAgentMultiRepoService,
        AutonomousAgentCleanSlateService,
    )

    _services = {
        "autonomous-agent": AutonomousAgentService,
        "autonomous-agent-batch": AutonomousAgentBatchService,
        "autonomous-agent-multi-repo": AutonomousAgentMultiRepoService,
        "autonomous-agent-clean-slate": AutonomousAgentCleanSlateService,
    }
    service_class = _services.get(name)
    if not service_class:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": f"Service '{name}' is not available",
                "error_code": "SERVICE_UNAVAILABLE",
            },
        )
    return service_class()


# ---------------------------------------------------------------------------
# Rate-limit status endpoint
# ---------------------------------------------------------------------------

# The agents rate-limit bucket is derived from the included_path "/api/v1/agents"
# by the middleware: strip leading slash, replace / and - with _.
# Kept as a constant here so both sides use the same value without coupling.
_AGENTS_BUCKET = "api_v1_agents"


@router.get("/rate-limit-status", summary="Get total agent rate limit usage for the current user")
async def get_rate_limit_status(request: Request) -> Dict[str, Any]:
    """
    Returns the shared rate-limit counter for all /api/v1/agents/* calls.

    All agent sub-systems (single repo, batch, multi-repo, clean slate) share
    one bucket keyed by the /api/v1/agents prefix.
    """
    rate_limit_cfg = get_config().get("rate_limit", {})
    limit = rate_limit_cfg.get("requests_per_window", 10)
    window = rate_limit_cfg.get("window_seconds", 60)

    # Re-use the same identifier logic as the middleware to guarantee consistency.
    identifier = get_rate_limit_identifier(request)

    used = 0
    reset_in = window
    try:
        redis = get_redis_client()
        if redis.is_initialized():
            redis_key = f"rate_limit:{identifier}:{_AGENTS_BUCKET}"
            raw = redis.client.get(redis_key)
            used = int(raw) if raw else 0
            raw_ttl = redis.client.ttl(redis_key)
            reset_in = raw_ttl if raw_ttl and raw_ttl > 0 else window
    except Exception as exc:
        Logger("agents.rate_limit_status").warning(f"Failed to read rate-limit counter: {exc}")

    return {
        "identifier": identifier,
        "used": used,
        "limit": limit,
        "remaining": max(0, limit - used),
        "window_seconds": window,
        "reset_in_seconds": reset_in,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/run",
    response_model=AgentResponse,
    summary="Run autonomous agent (single repo or clean-slate)",
)
@require_role(["dashboard", "admin", "splitz", "devops"])
async def run_agent(
    request: Request,
    body: RunRequest,
    logger: Logger = Depends(get_logger),
):
    """
    Run the autonomous agent on a single repository or in clean-slate mode.

    - With `repository_url`: clones the repo, makes changes, opens a draft PR.
    - Without `repository_url`: works in a fresh temp workspace (clean-slate).
    """
    try:
        parameters: Dict[str, Any] = {
            "prompt": _sanitize(body.prompt),
            "skills": body.skills,
        }
        if body.repository_url:
            parameters["repository_url"] = _sanitize(body.repository_url)
        if body.branch:
            parameters["branch"] = _sanitize(body.branch)
        if body.agent:
            parameters["agent"] = _sanitize(body.agent)
        if body.slack_channel:
            parameters["slack_channel"] = body.slack_channel.strip().lstrip("#")

        # Route to the appropriate service
        service_name = (
            "autonomous-agent"
            if body.repository_url
            else "autonomous-agent-clean-slate"
        )
        service = _get_service(service_name)

        logger.info(
            "Running autonomous agent",
            extra={"service": service_name, "has_repo": bool(body.repository_url)},
        )

        result = await _call_service(service, parameters)

        if result.get("status") == "failed":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": result.get("message", "Agent execution failed"),
                    "error_code": "AGENT_FAILED",
                },
            )

        task_id = result.get("task_id")
        # Store slack_channel in task metadata so _notify_slack can post there
        if task_id and body.slack_channel:
            try:
                from src.utils.connector import store_connector_metadata, CONNECTOR_DASHBOARD
                from sqlalchemy import text
                from src.providers.database.connection import get_engine
                engine = get_engine()
                with engine.connect() as conn:
                    row = conn.execute(text("SELECT task_metadata FROM tasks WHERE id = :id"), {"id": task_id}).fetchone()
                    import json
                    existing = json.loads(row[0]) if row and row[0] else {}
                    existing["slack_notify_channel"] = body.slack_channel.strip().lstrip("#")
                    conn.execute(text("UPDATE tasks SET task_metadata = :m WHERE id = :id"),
                                 {"m": json.dumps(existing), "id": task_id})
                    conn.commit()
            except Exception as e:
                logger.warning(f"Failed to store slack_channel in task metadata: {e}")
        if task_id:
            try:
                from src.utils.connector import (
                    store_connector_metadata,
                    CONNECTOR_DASHBOARD,
                )

                current_user = getattr(request.state, "current_user", {}) or {}
                connector_name = _sanitize(body.connector or "") or CONNECTOR_DASHBOARD
                store_connector_metadata(
                    task_id=task_id,
                    connector_name=connector_name,
                    user_email=current_user.get(
                        "email", current_user.get("username", "")
                    ),
                    user_name=current_user.get("username", ""),
                    source_id=_sanitize(body.source_id or ""),
                )
            except Exception as e:
                logger.warning(f"Failed to store connector metadata: {e}")

        return AgentResponse(
            task_id=task_id,
            status=result.get("status", "queued"),
            message=result.get("message", "Agent task queued"),
            metadata=result.get("metadata"),
        )

    except HTTPException:
        raise
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail={"error": "Request timed out"},
        )
    except Exception as e:
        logger.exception("Unexpected error in /agents/run", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"error": str(e)}
        )


@router.post(
    "/batch",
    response_model=AgentResponse,
    summary="Run autonomous agent across multiple repos (batch)",
)
@require_role(["dashboard", "admin", "splitz", "devops"])
async def batch_agent(
    request: Request,
    body: BatchRequest,
    logger: Logger = Depends(get_logger),
):
    """
    Run the autonomous agent in batch mode: one independent task per repository (1-50 repos).
    Returns a parent task_id that tracks all child tasks.
    """
    try:
        parameters: Dict[str, Any] = {
            "prompt": _sanitize(body.prompt),
            "repositories": body.repositories,
            "skills": body.skills,
        }
        if body.agent:
            parameters["agent"] = _sanitize(body.agent)

        service = _get_service("autonomous-agent-batch")

        logger.info("Running batch agent", extra={"repo_count": len(body.repositories)})

        result = await _call_service(service, parameters)

        if result.get("status") == "failed":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": result.get("message", "Batch agent failed"),
                    "error_code": "AGENT_FAILED",
                },
            )

        task_id = result.get("task_id")
        if task_id:
            try:
                from src.utils.connector import store_connector_metadata, CONNECTOR_DASHBOARD
                current_user = getattr(request.state, "current_user", {}) or {}
                connector_name = _sanitize(body.connector or "") or CONNECTOR_DASHBOARD
                store_connector_metadata(
                    task_id=task_id,
                    connector_name=connector_name,
                    user_email=current_user.get("email", current_user.get("username", "")),
                    user_name=current_user.get("username", ""),
                    source_id=_sanitize(body.source_id or ""),
                )
            except Exception as e:
                logger.warning(f"Failed to store connector metadata for batch task: {e}")

        return AgentResponse(
            task_id=task_id,
            status=result.get("status", "queued"),
            message=result.get("message", "Batch agent task queued"),
            metadata=result.get("metadata"),
        )

    except HTTPException:
        raise
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail={"error": "Request timed out"},
        )
    except Exception as e:
        logger.exception("Unexpected error in /agents/batch", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"error": str(e)}
        )


@router.post(
    "/multi-repo",
    response_model=AgentResponse,
    summary="Run autonomous agent across multiple repos (single process)",
)
@require_role(["dashboard", "admin", "splitz", "devops"])
async def multi_repo_agent(
    request: Request,
    body: MultiRepoRequest,
    logger: Logger = Depends(get_logger),
):
    """
    Run the autonomous agent across 1-10 repositories as a single Claude process.
    All repos are pre-cloned into a shared workspace; Claude works across them together.
    """
    try:
        parameters: Dict[str, Any] = {
            "prompt": _sanitize(body.prompt),
            "repositories": body.repositories,
            "skills": body.skills,
        }
        if body.agent:
            parameters["agent"] = _sanitize(body.agent)

        service = _get_service("autonomous-agent-multi-repo")

        logger.info(
            "Running multi-repo agent", extra={"repo_count": len(body.repositories)}
        )

        result = await _call_service(service, parameters)

        if result.get("status") == "failed":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": result.get("message", "Multi-repo agent failed"),
                    "error_code": "AGENT_FAILED",
                },
            )

        task_id = result.get("task_id")
        if task_id:
            try:
                from src.utils.connector import (
                    store_connector_metadata,
                    CONNECTOR_DEVREV,
                    CONNECTOR_DASHBOARD,
                )
                connector_name = _sanitize(body.connector or "") or CONNECTOR_DASHBOARD
                current_user = getattr(request.state, "current_user", {}) or {}
                # Prefer explicit user_email from request body (set by DevRev webhook
                # which runs as a service account and passes the ticket creator's email).
                # Fall back to the authenticated user's identity.
                user_email = (
                    _sanitize(body.user_email or "")
                    or current_user.get("email", current_user.get("username", ""))
                )
                store_connector_metadata(
                    task_id=task_id,
                    connector_name=connector_name,
                    user_email=user_email,
                    user_name=current_user.get("username", ""),
                    source_id=_sanitize(body.source_id or ""),
                )
            except Exception as e:
                logger.warning(f"Failed to store connector metadata for multi-repo task: {e}")

        return AgentResponse(
            task_id=task_id,
            status=result.get("status", "queued"),
            message=result.get("message", "Multi-repo agent task queued"),
            metadata=result.get("metadata"),
        )

    except HTTPException:
        raise
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail={"error": "Request timed out"},
        )
    except Exception as e:
        logger.exception("Unexpected error in /agents/multi-repo", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"error": str(e)}
        )
