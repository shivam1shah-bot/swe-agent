"""Autonomous Agent Clean Slate Service — fresh workspace, no repository."""

import shutil
import tempfile
from typing import Any, Dict

from src.providers.context import Context
from src.providers.logger import Logger
from .base import BaseAgentService
from .prompts import build_clean_slate_prompt


class AutonomousAgentCleanSlateService(BaseAgentService):
    def __init__(self):
        self.logger = Logger("AutonomousAgentCleanSlateService")

    @property
    def description(self) -> str:
        return "Execute autonomous agent tasks from scratch in a temp workspace (no repository required)"

    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        try:
            self._validate_parameters(parameters)

            from src.tasks.queue_integration import queue_integration
            if not queue_integration.is_queue_available():
                return {"status": "failed", "message": "Queue not available", "metadata": {"error": "Queue not available"}}

            task_id = queue_integration.submit_agents_catalogue_task(
                usecase_name="autonomous-agent-clean-slate",
                parameters=parameters,
                metadata={"service_type": "autonomous_agent_clean_slate", "execution_mode": "async", "priority": "normal"},
            )

            if task_id:
                return {
                    "status": "queued",
                    "message": "Clean slate autonomous agent task queued successfully",
                    "task_id": task_id,
                    "metadata": {"queued_at": self._get_current_timestamp()},
                }
            return {"status": "failed", "message": "Failed to queue clean slate autonomous agent task", "metadata": {"error": "Failed to submit to queue"}}

        except Exception as e:
            self.logger.error(f"Clean slate task submission failed: {e}")
            return {"status": "failed", "message": f"Failed to process clean slate request: {str(e)}", "metadata": {"error": str(e)}}

    def async_execute(self, parameters: Dict[str, Any], ctx: Context) -> Dict[str, Any]:
        try:
            task_id = self.get_task_id(ctx)
            log_ctx = self.get_logging_context(ctx)

            if self.check_context_done(ctx):
                error_msg = "Context was cancelled before clean slate execution" if ctx.is_cancelled() else \
                    "Context expired before clean slate execution" if ctx.is_expired() else \
                    "Context is done before clean slate execution"
                self.logger.warning(error_msg, extra=log_ctx)
                return {"status": "failed", "message": error_msg, "agent_result": {"success": False, "error": error_msg}, "metadata": {"error": error_msg, "task_id": task_id}}

            prompt = parameters.get("prompt", "")
            skills = parameters.get("skills", [])

            # Resolve agent from claude-plugins if specified
            agent_body = ""
            agent_param = parameters.get("agent", "")
            if agent_param:
                from src.agents.agent_resolver import resolve_agent
                agent_config = resolve_agent(agent_param)
                if agent_config:
                    merged = list(dict.fromkeys(agent_config.skills + skills))
                    self.logger.info(
                        f"Agent '{agent_param}' resolved: skills {skills} -> {merged}",
                        extra={**log_ctx, "agent": agent_param}
                    )
                    skills = merged
                    agent_body = agent_config.body

            slack_channel = parameters.get("slack_channel", "")
            combined_prompt = build_clean_slate_prompt(prompt, skills=skills, slack_channel=slack_channel or None)

            from src.agents.autonomous_agent import AutonomousAgentTool

            temp_dir = tempfile.mkdtemp(prefix=f"clean-slate-agent-{task_id}-", suffix="-workspace")

            try:
                agent_params = {
                    "prompt": combined_prompt,
                    "task_id": task_id,
                    "working_dir": temp_dir,
                    "agent_name": "autonomous-agent-clean-slate",
                    "skills": skills,
                }
                if agent_body:
                    agent_params["agent_body"] = agent_body
                result = AutonomousAgentTool().execute(agent_params)
                self.logger.info("Clean slate execution completed", extra={**log_ctx, "agent_success": result.get("success", False)})

                return {
                    "status": "completed",
                    "message": "Clean slate autonomous agent task completed",
                    "agent_result": result,
                    "metadata": {"task_id": task_id, "completed_at": self._get_current_timestamp()},
                }

            except Exception as e:
                self.logger.error("Clean slate execution failed", extra={**log_ctx, "error": str(e)})
                return {"status": "failed", "message": f"Failed to execute clean slate autonomous agent: {str(e)}", "agent_result": {"success": False, "error": str(e)}, "metadata": {"error": str(e), "task_id": task_id}}

            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
                self.logger.info("Cleaned up clean slate workspace", extra={**log_ctx, "temp_dir": temp_dir})

        except Exception as e:
            task_id = self.get_task_id(ctx)
            self.logger.error("Clean slate async_execute failed", extra={"error": str(e), "task_id": task_id})
            return {"status": "failed", "message": f"Failed to execute clean slate autonomous agent: {str(e)}", "agent_result": {"success": False, "error": str(e)}, "metadata": {"error": str(e)}}

    def _validate_parameters(self, parameters: Dict[str, Any]) -> None:
        # prompt is optional when skills are provided — the skill itself defines the task
        prompt = parameters.get("prompt", "")
        skills = parameters.get("skills", [])
        if not skills and (not isinstance(prompt, str) or not prompt.strip()):
            raise ValueError("Missing required parameter: prompt (or provide at least one skill)")


from src.services.agents_catalogue.registry import service_registry
service_registry.register("autonomous-agent-clean-slate", AutonomousAgentCleanSlateService)
