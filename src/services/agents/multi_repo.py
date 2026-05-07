"""Autonomous Agent Multi-Repo Service — single Claude process across multiple repos."""

import asyncio
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.providers.context import Context
from src.providers.logger import Logger
from src.providers.github.auth_service import GitHubAuthService
from .base import BaseAgentService
from .prompts import build_multi_repo_prompt
from .validations import validate_repository_url, validate_branch_name


@dataclass
class MultiRepoRepository:
    repository_url: str
    branch: Optional[str] = None


class AutonomousAgentMultiRepoService(BaseAgentService):
    def __init__(self):
        self.logger = Logger("AutonomousAgentMultiRepoService")
        self._github_auth = None

    @property
    def github_auth(self) -> GitHubAuthService:
        if self._github_auth is None:
            self._github_auth = GitHubAuthService()
        return self._github_auth

    @property
    def description(self) -> str:
        return "Execute autonomous agent tasks across 1–10 repositories using a single Claude process"

    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        try:
            self._validate_parameters(parameters)
            repositories = self._parse_repositories(parameters.get("repositories", []))

            validation_errors = []
            for i, repo in enumerate(repositories):
                try:
                    self._validate_single_repository(repo)
                except Exception as e:
                    validation_errors.append(
                        f"Repository {i + 1} ({repo.repository_url}): {str(e)}"
                    )

            if validation_errors:
                error_msg = "Multi-repo validation failed:\n" + "\n".join(
                    validation_errors
                )
                return {
                    "status": "failed",
                    "message": error_msg,
                    "metadata": {
                        "error": error_msg,
                        "validation_errors": validation_errors,
                        "validation_failed": True,
                    },
                }

            from src.tasks.queue_integration import queue_integration

            if not queue_integration.is_queue_available():
                return {
                    "status": "failed",
                    "message": "Queue not available",
                    "metadata": {"error": "Queue not available"},
                }

            task_id = queue_integration.submit_agents_catalogue_task(
                usecase_name="autonomous-agent-multi-repo",
                parameters=parameters,
                metadata={
                    "service_type": "autonomous_agent_multi_repo",
                    "execution_mode": "async",
                    "priority": "normal",
                    "repository_count": len(repositories),
                },
            )

            if task_id:
                return {
                    "status": "queued",
                    "message": f"Multi-repo autonomous agent task queued for {len(repositories)} repositories",
                    "task_id": task_id,
                    "metadata": {
                        "repository_count": len(repositories),
                        "queued_at": self._get_current_timestamp(),
                    },
                }
            return {
                "status": "failed",
                "message": "Failed to queue multi-repo autonomous agent task",
                "metadata": {"error": "Failed to submit to queue"},
            }

        except Exception as e:
            self.logger.error(f"Multi-repo task submission failed: {e}")
            return {
                "status": "failed",
                "message": f"Failed to process multi-repo request: {str(e)}",
                "metadata": {"error": str(e)},
            }

    def async_execute(self, parameters: Dict[str, Any], ctx: Context) -> Dict[str, Any]:
        try:
            task_id = self.get_task_id(ctx)
            log_ctx = self.get_logging_context(ctx)

            if self.check_context_done(ctx):
                error_msg = (
                    "Context was cancelled before multi-repo execution"
                    if ctx.is_cancelled()
                    else "Context expired before multi-repo execution"
                    if ctx.is_expired()
                    else "Context is done before multi-repo execution"
                )
                self.logger.warning(error_msg, extra=log_ctx)
                return {
                    "status": "failed",
                    "message": error_msg,
                    "agent_result": {"success": False, "error": error_msg},
                    "metadata": {"error": error_msg, "task_id": task_id},
                }

            prompt = parameters.get("prompt", "")
            repositories = parameters.get("repositories", [])
            skills = parameters.get("skills", [])

            # Resolve agent from claude-plugins if specified
            agent_body = ""
            agent_config = None
            agent_param = parameters.get("agent", "")
            if agent_param:
                from src.agents.agent_resolver import resolve_agent

                agent_config = resolve_agent(agent_param)
                if agent_config:
                    merged = list(dict.fromkeys(agent_config.skills + skills))
                    self.logger.info(
                        f"Agent '{agent_param}' resolved: skills {skills} -> {merged}",
                        extra={**log_ctx, "agent": agent_param},
                    )
                    skills = merged
                    agent_body = agent_config.body

            from src.agents.autonomous_agent import AutonomousAgentTool

            temp_dir = tempfile.mkdtemp(
                prefix=f"multi-repo-agent-{task_id}-", suffix="-workspace"
            )

            try:
                cloned_repos = []
                clone_errors = []
                for repo in repositories:
                    repo_url = repo.get("repository_url", "")
                    repo_name = repo_url.rstrip("/").split("/")[-1]
                    repo_dir = os.path.join(temp_dir, repo_name)
                    if not os.path.isdir(repo_dir):
                        self.logger.info(
                            f"Pre-cloning {repo_url}",
                            extra={**log_ctx, "repo": repo_name},
                        )
                        result_clone = subprocess.run(
                            [
                                "gh",
                                "repo",
                                "clone",
                                f"razorpay/{repo_name}",
                                repo_name,
                                "--",
                                "--depth",
                                "1",
                                "--single-branch",
                                "--branch",
                                "master",
                            ],
                            capture_output=True,
                            text=True,
                            cwd=temp_dir,
                            timeout=120,
                        )
                        if result_clone.returncode != 0:
                            clone_errors.append(
                                f"{repo_name}: {result_clone.stderr[:200]}"
                            )
                            self.logger.warning(
                                f"Failed to clone {repo_url}",
                                extra={**log_ctx, "error": result_clone.stderr[:200]},
                            )
                        else:
                            cloned_repos.append(repo_name)
                    else:
                        cloned_repos.append(repo_name)

                if not cloned_repos:
                    return {
                        "status": "failed",
                        "message": "Failed to clone any repositories",
                        "agent_result": {"success": False, "error": str(clone_errors)},
                        "metadata": {"error": str(clone_errors), "task_id": task_id},
                    }

                combined_prompt = build_multi_repo_prompt(
                    repositories=repositories,
                    cloned_repo_names=cloned_repos,
                    prompt=prompt,
                    task_id=task_id or "",
                )

                agent_params = {
                    "prompt": combined_prompt,
                    "task_id": task_id,
                    "working_dir": temp_dir,
                    "agent_name": "autonomous-agent-multi-repo",
                    "skills": skills,
                }
                if agent_body:
                    agent_params["agent_body"] = agent_body
                if agent_config and agent_config.max_turns is not None:
                    agent_params["max_turns"] = agent_config.max_turns

                result = AutonomousAgentTool().execute(agent_params)
                self.logger.info(
                    "Multi-repo execution completed",
                    extra={**log_ctx, "agent_success": result.get("success", False)},
                )

                return {
                    "status": "completed",
                    "message": "Multi-repo autonomous agent task completed",
                    "agent_result": result,
                    "metadata": {
                        "repository_count": len(repositories),
                        "task_id": task_id,
                        "completed_at": self._get_current_timestamp(),
                    },
                }

            except Exception as e:
                self.logger.error(
                    "Multi-repo execution failed", extra={**log_ctx, "error": str(e)}
                )
                return {
                    "status": "failed",
                    "message": f"Failed to execute multi-repo autonomous agent: {str(e)}",
                    "agent_result": {"success": False, "error": str(e)},
                    "metadata": {"error": str(e), "task_id": task_id},
                }

            finally:
                # Clean up flows.yaml from devstackctl
                self.cleanup_flows_yaml(temp_dir, self.logger, log_ctx)

                shutil.rmtree(temp_dir, ignore_errors=True)
                self.logger.info(
                    "Cleaned up multi-repo workspace",
                    extra={**log_ctx, "temp_dir": temp_dir},
                )

        except Exception as e:
            task_id = self.get_task_id(ctx)
            self.logger.error(
                "Multi-repo async_execute failed",
                extra={"error": str(e), "task_id": task_id},
            )
            return {
                "status": "failed",
                "message": f"Failed to execute multi-repo autonomous agent: {str(e)}",
                "agent_result": {"success": False, "error": str(e)},
                "metadata": {"error": str(e)},
            }

    def _validate_parameters(self, parameters: Dict[str, Any]) -> None:
        prompt = parameters.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Missing required parameter: prompt")
        repositories = parameters.get("repositories")
        if not repositories or not isinstance(repositories, list):
            raise ValueError(
                "Missing required parameter: repositories (must be a list)"
            )
        if len(repositories) < 1:
            raise ValueError("Multi-repo requires at least 1 repository")
        if len(repositories) > 10:
            raise ValueError(
                f"Too many repositories: {len(repositories)}. Multi-repo supports 1–10 repositories."
            )

    def _parse_repositories(
        self, repositories_data: List[Dict[str, Any]]
    ) -> List[MultiRepoRepository]:
        repositories = []
        for i, repo_data in enumerate(repositories_data):
            if not isinstance(repo_data, dict):
                raise ValueError(f"Repository {i + 1} must be a dictionary")
            repository_url = repo_data.get("repository_url")
            if not repository_url:
                raise ValueError(
                    f"Repository {i + 1} missing required field: repository_url"
                )
            repositories.append(
                MultiRepoRepository(
                    repository_url=repository_url, branch=repo_data.get("branch")
                )
            )
        return repositories

    def _validate_single_repository(self, repo: MultiRepoRepository) -> None:
        validate_repository_url(repo.repository_url)
        if repo.branch:
            validate_branch_name(repo.branch)
        visibility_result = asyncio.run(
            self.github_auth.check_repository_visibility(repo.repository_url)
        )
        if not visibility_result.get("success", False):
            raise ValueError(
                f"Unable to access repository: {visibility_result.get('error', 'Unknown error')}"
            )
        if not visibility_result.get("is_private", False):
            owner = visibility_result.get("owner", "unknown")
            repo_name = visibility_result.get("repo", "unknown")
            raise ValueError(
                f"Repository {owner}/{repo_name} is public. Multi-repo agent only works with private repositories."
            )


from src.services.agents_catalogue.registry import service_registry

service_registry.register(
    "autonomous-agent-multi-repo", AutonomousAgentMultiRepoService
)
