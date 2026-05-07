"""Autonomous Agent Batch Service — one task per repo, parent task tracks the batch."""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.providers.context import Context
from src.providers.logger import Logger
from src.providers.github.auth_service import GitHubAuthService
from .base import BaseAgentService
from .validations import validate_repository_url, validate_branch_name


@dataclass
class BatchRepository:
    repository_url: str
    branch: Optional[str] = None


class AutonomousAgentBatchService(BaseAgentService):
    def __init__(self):
        self.logger = Logger("AutonomousAgentBatchService")
        self._github_auth = None

    @property
    def github_auth(self) -> GitHubAuthService:
        if self._github_auth is None:
            self._github_auth = GitHubAuthService()
        return self._github_auth

    @property
    def description(self) -> str:
        return "Execute autonomous agent tasks across multiple repositories in batch"

    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        try:
            self._validate_batch_parameters(parameters)
            repositories = self._parse_repositories(parameters.get("repositories", []))

            validation_errors = []
            for i, repo in enumerate(repositories):
                try:
                    self._validate_single_repository(repo)
                except Exception as e:
                    validation_errors.append(f"Repository {i + 1} ({repo.repository_url}): {str(e)}")

            if validation_errors:
                error_msg = "Batch validation failed:\n" + "\n".join(validation_errors)
                self.logger.error("Batch repository validation failed", extra={"validation_errors": validation_errors})
                return {"status": "failed", "message": error_msg, "metadata": {"error": error_msg, "validation_errors": validation_errors, "validation_failed": True}}

            parent_task_id = self._create_parent_task(parameters, repositories)

            child_task_ids = []
            failed_submissions = []
            batch_agent = parameters.get("agent", "")
            batch_skills = parameters.get("skills", [])
            for i, repo in enumerate(repositories):
                try:
                    child_task_id = self._submit_child_task(parent_task_id, parameters.get("prompt"), repo, i + 1, agent=batch_agent, skills=batch_skills)
                    if child_task_id:
                        child_task_ids.append(child_task_id)
                    else:
                        failed_submissions.append(f"Repository {i + 1} ({repo.repository_url}): Failed to submit")
                except Exception as e:
                    failed_submissions.append(f"Repository {i + 1} ({repo.repository_url}): {str(e)}")

            self._update_parent_with_children(parent_task_id, child_task_ids)

            response = {
                "status": "queued",
                "message": f"Batch autonomous agent started for {len(child_task_ids)} repositories",
                "task_id": parent_task_id,
                "metadata": {
                    "parent_task_id": parent_task_id,
                    "total_repositories": len(repositories),
                    "successful_children": len(child_task_ids),
                    "child_task_ids": child_task_ids,
                    "batch_created_at": self._get_current_timestamp(),
                },
            }
            if failed_submissions:
                response["metadata"]["failed_submissions"] = failed_submissions
                response["message"] += f" ({len(failed_submissions)} failed to submit)"

            return response

        except Exception as e:
            self.logger.error(f"Batch submission failed: {e}")
            return {"status": "failed", "message": f"Failed to process batch request: {str(e)}", "metadata": {"error": str(e)}}

    def async_execute(self, parameters: Dict[str, Any], ctx: Context) -> Dict[str, Any]:
        # Batch processing is handled by child tasks submitted to autonomous-agent service.
        return {"status": "completed", "message": "Batch async execute not implemented — child tasks handle processing", "batch_result": {"success": True}}

    def _validate_batch_parameters(self, parameters: Dict[str, Any]) -> None:
        prompt = parameters.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Missing required parameter: prompt")
        repositories = parameters.get("repositories")
        if not repositories or not isinstance(repositories, list):
            raise ValueError("Missing required parameter: repositories (must be a list)")
        if len(repositories) == 0:
            raise ValueError("At least one repository is required")
        if len(repositories) > 50:
            raise ValueError(f"Too many repositories: {len(repositories)}. Maximum allowed: 50")

    def _parse_repositories(self, repositories_data: List[Dict[str, Any]]) -> List[BatchRepository]:
        repositories = []
        for i, repo_data in enumerate(repositories_data):
            if not isinstance(repo_data, dict):
                raise ValueError(f"Repository {i + 1} must be a dictionary")
            repository_url = repo_data.get("repository_url")
            if not repository_url:
                raise ValueError(f"Repository {i + 1} missing required field: repository_url")
            repositories.append(BatchRepository(repository_url=repository_url, branch=repo_data.get("branch")))
        return repositories

    def _validate_single_repository(self, repo: BatchRepository) -> None:
        validate_repository_url(repo.repository_url)
        if repo.branch:
            validate_branch_name(repo.branch)
        visibility_result = asyncio.run(self.github_auth.check_repository_visibility(repo.repository_url))
        if not visibility_result.get("success", False):
            raise ValueError(f"Unable to access repository: {visibility_result.get('error', 'Unknown error')}")
        if not visibility_result.get("is_private", False):
            owner = visibility_result.get("owner", "unknown")
            repo_name = visibility_result.get("repo", "unknown")
            raise ValueError(f"Repository {owner}/{repo_name} is public. Batch autonomous agent only works with private repositories.")

    def _create_parent_task(self, parameters: Dict[str, Any], repositories: List[BatchRepository]) -> str:
        from src.tasks.service import task_manager
        from src.services.task_service import TaskService
        from src.providers.database.provider import DatabaseProvider
        from src.providers.config_loader import get_config
        from src.providers.database.session import get_session
        from src.repositories.task_repository import SQLAlchemyTaskRepository

        parent_task_id = task_manager.create_task(
            name=f"Batch Autonomous Agent: {len(repositories)} repositories",
            description=f"Batch execution across {len(repositories)} repositories: {parameters.get('prompt', '')[:100]}",
            parameters={"batch_type": "autonomous_agent_batch", "prompt": parameters.get("prompt"), "repository_count": len(repositories)},
        )

        batch_metadata = {
            "batch": {
                "is_parent": True,
                "repositories": [{"repository_url": repo.repository_url, "branch": repo.branch} for repo in repositories],
                "child_task_ids": [],
                "prompt": parameters.get("prompt"),
                "created_at": self._get_current_timestamp(),
            }
        }

        config = get_config()
        task_service = TaskService(config, DatabaseProvider())
        task = task_service.get_task(parent_task_id)
        current_metadata = task.get("metadata", {})
        current_metadata.update(batch_metadata)

        with get_session() as session:
            SQLAlchemyTaskRepository(session).update_metadata(parent_task_id, current_metadata)

        self.logger.info("Created parent task for batch", extra={"parent_task_id": parent_task_id, "repository_count": len(repositories)})
        return parent_task_id

    def _submit_child_task(self, parent_task_id: str, prompt: str, repo: BatchRepository, repo_index: int,
                           agent: str = "", skills: list = None) -> str:
        from src.tasks.queue_integration import queue_integration

        child_parameters = {"prompt": prompt, "repository_url": repo.repository_url, "is_batch_child": True}
        if repo.branch:
            child_parameters["branch"] = repo.branch
        if agent:
            child_parameters["agent"] = agent
        if skills:
            child_parameters["skills"] = skills

        child_task_id = queue_integration.submit_agents_catalogue_task(
            usecase_name="autonomous-agent",
            parameters=child_parameters,
            metadata={"batch": {"is_child": True, "parent_task_id": parent_task_id, "repository_url": repo.repository_url, "branch": repo.branch, "repository_index": repo_index}, "service_type": "autonomous_agent", "execution_mode": "async", "priority": "normal"},
        )

        if child_task_id:
            self.logger.info("Submitted child task", extra={"parent_task_id": parent_task_id, "child_task_id": child_task_id, "repository_url": repo.repository_url})
        else:
            self.logger.error("Failed to submit child task", extra={"parent_task_id": parent_task_id, "repository_url": repo.repository_url})

        return child_task_id

    def _update_parent_with_children(self, parent_task_id: str, child_task_ids: List[str]) -> None:
        from src.providers.database.session import get_session
        from src.repositories.task_repository import SQLAlchemyTaskRepository
        from src.models.base import TaskStatus

        with get_session() as session:
            task_repo = SQLAlchemyTaskRepository(session)
            parent_task = task_repo.get_by_id(parent_task_id)
            if not parent_task:
                self.logger.error(f"Parent task {parent_task_id} not found when updating with children")
                return
            current_metadata = parent_task.metadata_dict
            if "batch" not in current_metadata:
                current_metadata["batch"] = {}
            current_metadata["batch"]["child_task_ids"] = child_task_ids
            current_metadata["batch"]["updated_at"] = self._get_current_timestamp()
            task_repo.update_metadata(parent_task_id, current_metadata)
            task_repo.update_status(parent_task_id, TaskStatus.COMPLETED)

        self.logger.info("Updated parent task with child task IDs", extra={"parent_task_id": parent_task_id, "child_count": len(child_task_ids)})


from src.services.agents_catalogue.registry import service_registry
service_registry.register("autonomous-agent-batch", AutonomousAgentBatchService)
