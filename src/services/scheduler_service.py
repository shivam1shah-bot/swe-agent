"""
Scheduler service — APScheduler wrapper for cron-based skill execution.

Used ONLY by the scheduler pod (commands/scheduler.py).
API pods do NOT instantiate this service.

On each cron trigger, the scheduler calls POST /api/v1/agents/run with the
schedule's prompt and skills — the same path a user would use manually.
"""

import asyncio
import logging
import time
from typing import Any, Dict

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.base import JobLookupError

from src.models.schedule import Schedule
from src.providers.logger import Logger

logger = logging.getLogger(__name__)


async def call_agents_run(
    config: Dict[str, Any],
    skill_name: str,
    parameters: Dict[str, Any],
    schedule_name: str,
) -> bool:
    """
    POST /api/v1/agents/run with the schedule's prompt and skills.

    `skill_name` is injected into the `skills` list so the agent loads that
    skill. `parameters` must contain at least `prompt`; any extra keys are
    ignored by the agents/run endpoint.

    Returns True if the API accepted the request (2xx), False otherwise.
    """
    _log = Logger("SchedulerService._call_agents_run")

    api_base = config.get("app", {}).get("api_base_url", "")
    if not api_base:
        raise RuntimeError("app.api_base_url is not configured — cannot trigger schedule")
    url = f"{api_base}/api/v1/agents/run"

    # Build the payload expected by RunRequest
    prompt = parameters.get("prompt", "")
    # skills list: start from parameters, always include skill_name
    skills: list = list(parameters.get("skills", []))
    if skill_name and skill_name not in skills:
        skills.insert(0, skill_name)

    payload = {"prompt": prompt, "skills": skills}
    # Pass through optional fields stored in parameters
    if parameters.get("repository_url"):
        payload["repository_url"] = parameters["repository_url"]
    if parameters.get("branch"):
        payload["branch"] = parameters["branch"]
    if parameters.get("slack_channel"):
        payload["slack_channel"] = parameters["slack_channel"]

    # Use admin credentials for internal calls
    auth_users = config.get("auth", {}).get("users", {})
    username = "admin"
    password = auth_users.get("admin", "")
    if not password:
        raise RuntimeError("auth.users.admin password is not configured")

    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload, auth=(username, password))

            if resp.is_success:
                _log.info(
                    f"Triggered schedule '{schedule_name}': POST {url} → {resp.status_code}"
                    f" task_id={resp.json().get('task_id')}"
                )
                return True

            if resp.status_code < 500:
                # 4xx — client error, no point retrying
                _log.error(
                    f"Schedule '{schedule_name}' trigger failed (no retry): "
                    f"{resp.status_code} {resp.text}"
                )
                return False

            _log.warning(
                f"Schedule '{schedule_name}' attempt {attempt + 1}/{max_retries} "
                f"failed with {resp.status_code} — retrying"
            )

        except (httpx.TimeoutException, httpx.ConnectError) as e:
            _log.warning(
                f"Schedule '{schedule_name}' attempt {attempt + 1}/{max_retries} "
                f"network error: {e} — retrying"
            )
        except Exception as e:
            _log.error(f"Schedule '{schedule_name}' trigger error: {e}")
            return False

        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)  # 1s, 2s backoff

    _log.error(f"Schedule '{schedule_name}' failed after {max_retries} attempts")
    return False


class SchedulerService:
    """
    Manages cron job scheduling via APScheduler.

    Loads enabled schedules from DB on startup, registers APScheduler jobs,
    and fires tasks into SQS via the existing queue system on each cron trigger.
    """

    def __init__(self, config, database_provider):
        self._config = config
        self._db_provider = database_provider
        self.logger = Logger("SchedulerService")

        self.scheduler = AsyncIOScheduler(
            jobstores={"default": MemoryJobStore()},
            job_defaults={
                "coalesce": True,
                "misfire_grace_time": 300,  # 5 min grace — agents can take several minutes to start
                "max_instances": 1,
            },
        )

    def _get_session(self):
        """Get a database session."""
        from src.providers.database.session import session_factory
        return session_factory.create_session()

    def _get_repo(self, session):
        from src.repositories.schedule_repository import SQLAlchemyScheduleRepository
        return SQLAlchemyScheduleRepository(session)

    async def start(self):
        """Load enabled schedules from DB, register jobs, and start the scheduler."""
        self.logger.info("Starting scheduler service...")

        session = self._get_session()
        try:
            repo = self._get_repo(session)
            schedules = repo.list_enabled()
            self.logger.info(f"Found {len(schedules)} enabled schedule(s)")
            for schedule in schedules:
                self._register_job(schedule)
        finally:
            session.close()

        self.scheduler.start()
        self.logger.info(f"Scheduler started with {len(self.scheduler.get_jobs())} job(s)")

    async def shutdown(self):
        """Shut down the scheduler gracefully."""
        self.scheduler.shutdown(wait=False)
        self.logger.info("Scheduler shut down")

    def _register_job(self, schedule: Schedule):
        """Register or replace an APScheduler job for the given schedule."""
        try:
            self.scheduler.add_job(
                self._fire,
                CronTrigger.from_crontab(schedule.cron_expression),
                id=schedule.id,
                args=[schedule.id],
                replace_existing=True,
            )
            self.logger.info(
                f"Registered job for schedule '{schedule.name}' ({schedule.id})"
                f" cron='{schedule.cron_expression}'"
            )
        except Exception as e:
            self.logger.error(
                f"Failed to register job for schedule {schedule.id}: {e}"
            )

    def _remove_job(self, schedule_id: str):
        """Remove an APScheduler job if it exists."""
        try:
            self.scheduler.remove_job(schedule_id)
            self.logger.info(f"Removed job for schedule {schedule_id}")
        except JobLookupError:
            pass  # Job doesn't exist — that's fine

    def upsert_schedule(self, schedule_id: str):
        """
        Reload a schedule from DB and update the APScheduler job.

        Called by the scheduler pod when it receives a reload signal.
        """
        session = self._get_session()
        try:
            repo = self._get_repo(session)
            schedule = repo.get_by_id(schedule_id)
            if schedule and schedule.enabled:
                self._register_job(schedule)
            else:
                self._remove_job(schedule_id)
        finally:
            session.close()

    def remove_schedule(self, schedule_id: str):
        """Remove a schedule's APScheduler job."""
        self._remove_job(schedule_id)

    async def _fire(self, schedule_id: str):
        """Called by APScheduler on each cron trigger."""
        session = self._get_session()
        try:
            repo = self._get_repo(session)
            schedule = repo.get_by_id(schedule_id)

            if not schedule or not schedule.enabled:
                self.logger.info(f"Skipping disabled/missing schedule {schedule_id}")
                return

            self.logger.info(f"Firing schedule '{schedule.name}' ({schedule_id})")

            success = await call_agents_run(
                config=self._config,
                skill_name=schedule.skill_name,
                parameters=schedule.parameters_dict,
                schedule_name=schedule.name,
            )

            if success:
                repo.update_fields(schedule_id, last_run_at=int(time.time()))
                session.commit()

        except Exception as e:
            self.logger.error(f"Error firing schedule {schedule_id}: {e}")
            try:
                session.rollback()
            except Exception:
                pass
        finally:
            session.close()
