"""Autonomous Agent Service — single repository execution."""

import asyncio
import os
import shutil
import tempfile
import time
import traceback
from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.providers.context import Context
from src.providers.logger import Logger
from src.providers.github.auth_service import GitHubAuthService
from .base import BaseAgentService
from .prompts import build_combined_prompt
from .validations import validate_parameters


@dataclass
class AutonomousAgentConfig:
    prompt: str
    working_dir: Optional[str] = None
    repository_url: Optional[str] = None
    branch: Optional[str] = None


class AutonomousAgentService(BaseAgentService):
    def __init__(self):
        self.logger = Logger("AutonomousAgentService")
        self._github_auth = None

    @property
    def github_auth(self) -> GitHubAuthService:
        if self._github_auth is None:
            self._github_auth = GitHubAuthService()
        return self._github_auth

    @property
    def description(self) -> str:
        return "Execute autonomous agent tasks using Claude"

    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        try:
            validate_parameters(parameters)
            agent_config = self._parse_agent_config(parameters)

            if isinstance(agent_config.branch, str) and agent_config.branch:
                if agent_config.branch.strip().lower() in {"main", "master"}:
                    error_msg = f"Branch '{agent_config.branch}' is not allowed. Please use a feature branch."
                    self.logger.warning("Invalid branch specified", extra={"branch": agent_config.branch})
                    return {"status": "failed", "message": error_msg, "metadata": {"error": error_msg, "validation_failed": True}}

            is_private = None
            if isinstance(agent_config.repository_url, str) and agent_config.repository_url.strip():
                repo_validation = self._validate_repository_access(agent_config.repository_url)
                if not repo_validation.get("success", False):
                    error_msg = repo_validation.get("error", "Repository validation failed")
                    return {
                        "status": "failed",
                        "message": repo_validation.get("message", "Repository access validation failed"),
                        "metadata": {"error": error_msg, "repository_url": agent_config.repository_url, "validation_failed": True},
                    }
                is_private = repo_validation.get("is_private", False)

            from src.tasks.queue_integration import queue_integration
            if not queue_integration.is_queue_available():
                return {"status": "failed", "message": "Queue not available", "metadata": {"error": "Queue not available"}}

            task_id = queue_integration.submit_agents_catalogue_task(
                usecase_name="autonomous-agent",
                parameters=parameters,
                metadata={"service_type": "autonomous_agent", "execution_mode": "async", "priority": "normal", "prompt_length": len(agent_config.prompt)},
            )

            if task_id:
                return {
                    "status": "queued",
                    "message": "Autonomous agent task queued successfully",
                    "task_id": task_id,
                    "metadata": {
                        "prompt_length": len(agent_config.prompt),
                        "repository_url": agent_config.repository_url,
                        "branch": agent_config.branch,
                        "queued_at": self._get_current_timestamp(),
                    },
                }
            return {"status": "failed", "message": "Failed to queue autonomous agent task", "metadata": {"error": "Failed to submit to queue"}}

        except Exception as e:
            self.logger.error(f"Autonomous agent task submission failed: {e}")
            return {"status": "failed", "message": f"Failed to process autonomous agent request: {str(e)}", "metadata": {"error": str(e)}}

    def async_execute(self, parameters: Dict[str, Any], ctx: Context) -> Dict[str, Any]:
        try:
            task_id = self.get_task_id(ctx)
            log_ctx = self.get_logging_context(ctx)

            if self.check_context_done(ctx):
                error_msg = "Context was cancelled before autonomous agent execution" if ctx.is_cancelled() else \
                    "Context expired before autonomous agent execution" if ctx.is_expired() else \
                    "Context is done before autonomous agent execution"
                self.logger.warning(error_msg, extra=log_ctx)
                return {"status": "failed", "message": error_msg, "agent_result": {"success": False, "error": error_msg}, "metadata": {"error": error_msg, "task_id": task_id}}

            validate_parameters(parameters)
            agent_config = self._parse_agent_config(parameters)
            agent_result = self._call_autonomous_agent(agent_config, parameters, ctx)

            return {
                "status": "completed",
                "message": "Successfully executed autonomous agent task",
                "agent_result": agent_result,
                "metadata": {
                    "prompt_length": len(agent_config.prompt),
                    "agent_success": agent_result.get("success", False),
                    "task_id": task_id,
                    "completed_at": self._get_current_timestamp(),
                },
            }

        except Exception as e:
            task_id = self.get_task_id(ctx)
            log_ctx = self.get_logging_context(ctx)
            self.logger.error("Failed to execute autonomous agent", extra={**log_ctx, "error": str(e), "traceback": traceback.format_exc()})
            return {"status": "failed", "message": f"Failed to execute autonomous agent: {str(e)}", "agent_result": {"success": False, "error": str(e)}, "metadata": {"error": str(e), "task_id": task_id}}

    def _parse_agent_config(self, parameters: Dict[str, Any]) -> AutonomousAgentConfig:
        prompt_raw = parameters.get("prompt")
        return AutonomousAgentConfig(
            prompt=prompt_raw.strip() if isinstance(prompt_raw, str) else "",
            working_dir=parameters.get("working_dir"),
            repository_url=parameters.get("repository_url"),
            branch=parameters.get("branch"),
        )

    def _validate_repository_access(self, repository_url: str) -> Dict[str, Any]:
        try:
            visibility_result = asyncio.run(self.github_auth.check_repository_visibility(repository_url))
            if not visibility_result.get("success", False):
                error_msg = visibility_result.get("error", "Unknown error checking repository")
                return {"success": False, "error": error_msg, "message": f"Unable to access repository: {error_msg}"}

            is_private = visibility_result.get("is_private", False)
            owner = visibility_result.get("owner", "unknown")
            repo = visibility_result.get("repo", "unknown")

            if not is_private:
                error_msg = f"Autonomous agent is only available for private repositories. {owner}/{repo} is a public repository."
                return {"success": False, "error": error_msg, "message": f"Repository {owner}/{repo} is public. Autonomous agent is restricted to private repositories only."}

            return {"success": True, "is_private": True, "message": f"Repository {owner}/{repo} is private and accessible", "owner": owner, "repo": repo}

        except Exception as e:
            error_msg = f"Repository validation failed: {str(e)}"
            self.logger.error(error_msg)
            return {"success": False, "error": error_msg, "message": "Failed to validate repository access"}

    def _call_autonomous_agent(self, config: AutonomousAgentConfig, parameters: Dict[str, Any], ctx: Context) -> Dict[str, Any]:
        task_id = self.get_task_id(ctx)
        if not task_id:
            task_id = f"autonomous-agent-{int(time.time())}"

        metadata = self.get_metadata(ctx)
        usecase_name = metadata.get("usecase_name", "autonomous-agent")
        log_ctx = self.get_logging_context(ctx)

        if self.check_context_done(ctx):
            error_msg = "Context was cancelled before calling autonomous agent" if ctx.is_cancelled() else \
                "Context expired before calling autonomous agent" if ctx.is_expired() else \
                "Context is done before calling autonomous agent"
            self.logger.warning(error_msg, extra=log_ctx)
            return {"success": False, "error": error_msg}

        try:
            from src.agents.autonomous_agent import AutonomousAgentTool
        except ImportError:
            self.logger.error("Failed to import autonomous agent tool", extra=log_ctx)
            return {"success": False, "error": "Autonomous agent tool not available"}

        temp_dir = None
        working_dir = config.working_dir

        try:
            if not working_dir:
                temp_dir = tempfile.mkdtemp(prefix=f"autonomous-agent-{task_id}-", suffix="-workspace")
                working_dir = temp_dir

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
                        extra={**log_ctx, "agent": agent_param, "agent_skills": agent_config.skills}
                    )
                    skills = merged
                    agent_body = agent_config.body

            combined_prompt = build_combined_prompt(
                repository_url=config.repository_url or "",
                branch=config.branch,
                user_prompt=config.prompt,
                skills=skills,
            )

            agent_params = {
                "prompt": combined_prompt,
                "task_id": task_id,
                "working_dir": working_dir,
                "agent_name": usecase_name,
            }
            if config.repository_url:
                agent_params["repository_url"] = config.repository_url
            if config.branch:
                agent_params["branch"] = config.branch
            if skills:
                agent_params["skills"] = skills
            if agent_body:
                agent_params["agent_body"] = agent_body
            if parameters.get("is_batch_child"):
                agent_params["is_batch_child"] = True

            result = AutonomousAgentTool().execute(agent_params)
            return result

        except Exception as e:
            self.logger.error("Autonomous agent execution failed", extra={**log_ctx, "error": str(e)})
            return {"success": False, "error": f"Autonomous agent execution failed: {str(e)}"}

        finally:
            if temp_dir and os.path.exists(temp_dir):
                try:
                    # Clean up flows.yaml from devstackctl
                    self.cleanup_flows_yaml(temp_dir, self.logger, log_ctx)

                    shutil.rmtree(temp_dir)
                    self.logger.info("Cleaned up temporary workspace", extra={**log_ctx, "temp_dir": temp_dir})
                except Exception as cleanup_error:
                    self.logger.warning("Failed to clean up temporary workspace", extra={**log_ctx, "cleanup_error": str(cleanup_error)})


from src.services.agents_catalogue.registry import service_registry
service_registry.register("autonomous-agent", AutonomousAgentService)
