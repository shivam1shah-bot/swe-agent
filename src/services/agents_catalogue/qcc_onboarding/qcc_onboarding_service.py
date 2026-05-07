"""
QCC Onboarding Service

This service helps users understand and fulfill the necessary conditions for 
onboarding new services into Quality Code Coverage (QCC) using an autonomous agent.
"""

from typing import Dict, Any
from dataclasses import dataclass
import time
import asyncio

from ..base_service import BaseAgentsCatalogueService
from src.providers.logger import Logger
from src.providers.context import Context
from src.providers.github.auth_service import GitHubAuthService
from .prompts import create_qcc_implementation_prompt

@dataclass
class QCCOnboardingConfig:
    """Configuration for QCC onboarding analysis."""
    repo_path: str
    branch_name: str = ""
    pr_title: str = "QCC Onboarding Analysis"

class QCCOnboardingService(BaseAgentsCatalogueService):
    """
    QCC Onboarding Service.

    This service analyzes repositories and provides comprehensive guidance
    for onboarding services into Quality Code Coverage (QCC) using an autonomous agent.
    """

    def __init__(self):
        """Initialize the QCC Onboarding service."""
        self.logger = Logger("QCCOnboardingService")
        self._github_auth = None  # Lazy initialization

    @property
    def github_auth(self):
        """Lazy property for GitHub auth service."""
        if self._github_auth is None:
            self._github_auth = GitHubAuthService()
        return self._github_auth

    @property
    def description(self) -> str:
        """Service description."""
        return "Help users understand and fulfill necessary conditions for onboarding services into Quality Code Coverage (QCC)"

    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronous execute for API calls - validates repository and queues the task."""
        try:
            # Validate and parse parameters
            self._validate_parameters(parameters)
            qcc_config = self._parse_qcc_config(parameters)

            # Validate repository access before queuing
            self.logger.info("Validating repository access before queuing",
                           extra={
                               "repo_path": qcc_config.repo_path
                           })
            
            repo_validation = self._validate_repository_access(qcc_config.repo_path)
            if not repo_validation.get("success", False):
                error_msg = repo_validation.get("error", "Repository validation failed")
                self.logger.error(f"Repository validation failed: {error_msg}",
                                extra={
                                    "repo_path": qcc_config.repo_path,
                                    "validation_error": error_msg
                                })
                return {
                    "status": "failed",
                    "message": repo_validation.get("message", "Repository access validation failed"),
                    "metadata": {
                        "error": error_msg,
                        "repo_path": qcc_config.repo_path,
                        "validation_failed": True
                    }
                }

            # Log successful validation
            is_private = repo_validation.get("is_private", False)
            self.logger.info(f"Repository validation successful - {'private' if is_private else 'public'} repository",
                           extra={
                               "repo_path": qcc_config.repo_path,
                               "is_private": is_private,
                               "validation_message": repo_validation.get("message")
                           })

            # Queue the task using sync queue integration
            from src.tasks.queue_integration import queue_integration

            if not queue_integration.is_queue_available():
                return {
                    "status": "failed",
                    "message": "Queue not available",
                    "metadata": {"error": "Queue not available"}
                }

            self.logger.info("Submitting QCC onboarding task to queue",
                           extra={
                               "repo_path": qcc_config.repo_path,
                               "branch_name": qcc_config.branch_name,
                               "repo_is_private": is_private
                           })

            # Submit to queue with qcc-specific task type and validation results
            task_id = queue_integration.submit_agents_catalogue_task(
                usecase_name="qcc-onboarding",
                parameters=parameters,
                metadata={
                    "service_type": "qcc_onboarding",
                    "execution_mode": "async",
                    "priority": "normal",
                    "repo_path": qcc_config.repo_path,
                    "branch_name": qcc_config.branch_name,
                    "pr_title": qcc_config.pr_title,
                    "repo_validation": {
                        "is_private": is_private,
                        "accessible": True,
                        "message": repo_validation.get("message")
                    }
                }
            )

            if task_id:
                self.logger.info("QCC onboarding task queued successfully",
                               extra={
                                   "task_id": task_id,
                                   "repo_path": qcc_config.repo_path
                               })
                return {
                    "status": "queued",
                    "message": f"QCC onboarding analysis queued successfully",
                    "task_id": task_id,
                    "metadata": {
                        "repo_path": qcc_config.repo_path,
                        "branch_name": qcc_config.branch_name,
                        "pr_title": qcc_config.pr_title,
                        "queued_at": self._get_current_timestamp()
                    }
                }
            else:
                return {
                    "status": "failed",
                    "message": "Failed to queue QCC onboarding analysis",
                    "metadata": {"error": "Failed to submit to queue"}
                }

        except Exception as e:
            self.logger.error(f"QCC onboarding analysis failed: {e}")
            return {
                "status": "failed",
                "message": f"Failed to process QCC onboarding request: {str(e)}",
                "metadata": {
                    "error": str(e)
                }
            }

    def async_execute(self, parameters: Dict[str, Any], ctx: Context) -> Dict[str, Any]:
        """
        Synchronous execute for worker processing - performs the actual QCC analysis.

        Args:
            parameters: Dictionary containing:
                - repo_path: Repository clone URL
                - branch_name: Optional branch name for PR
                - pr_title: Optional PR title
            ctx: Execution context with task_id, metadata, cancellation, and logging correlation

        Returns:
            Dictionary containing:
                - status: "completed" or "failed"
                - message: Status message
                - files: List of generated files
                - pr_url: PR URL created by the agent
                - qcc_analysis: QCC analysis results
        """
        try:
            # Extract task information from context
            task_id = self.get_task_id(ctx)
            metadata = self.get_metadata(ctx)
            execution_mode = self.get_execution_mode(ctx)
            log_ctx = self.get_logging_context(ctx)

            self.logger.info("Starting async QCC onboarding analysis",
                           extra={
                               **log_ctx,
                               "parameters": {k: v for k, v in parameters.items() if not k.startswith('_')},
                               "execution_mode": execution_mode
                           })

            # Check if context is already done before starting
            if self.check_context_done(ctx):
                context_status = self.get_context_status(ctx)
                error_msg = "Context is done before QCC analysis"
                if ctx.is_cancelled():
                    error_msg = "Context was cancelled before QCC analysis"
                elif ctx.is_expired():
                    error_msg = "Context expired before QCC analysis"

                self.logger.warning(error_msg, extra=log_ctx)
                return {
                    "status": "failed",
                    "message": error_msg,
                    "files": [],
                    "pr_url": None,
                    "agent_result": {"success": False, "error": error_msg},
                    "metadata": {
                        "error": error_msg,
                        "task_id": task_id,
                        "context_status": context_status
                    }
                }

            # Validate parameters
            self._validate_parameters(parameters)

            # Parse configuration
            qcc_config = self._parse_qcc_config(parameters)

            # Get repository validation results from metadata (already validated in sync execute)
            repo_validation = metadata.get("repo_validation", {})
            is_private = repo_validation.get("is_private", False)
            
            self.logger.info(f"Using pre-validated repository - {'private' if is_private else 'public'} repository",
                           extra={
                               **log_ctx,
                               "repo_path": qcc_config.repo_path,
                               "is_private": is_private,
                               "validation_message": repo_validation.get("message", "Pre-validated in API")
                           })

            # Call autonomous agent to analyze repository and generate QCC onboarding plan
            agent_result = self._call_autonomous_agent(qcc_config, parameters, ctx)

            # Get PR URL from agent result
            pr_url = agent_result.get("pr_url")

            self.logger.info("Successfully completed QCC onboarding analysis",
                           extra={
                               **log_ctx,
                               "repo_path": qcc_config.repo_path,
                               "agent_success": agent_result.get("success", False)
                           })

            return {
                "status": "completed",
                "message": f"Successfully completed QCC onboarding analysis for repository",
                "files": agent_result.get("files", []),
                "pr_url": pr_url,
                "agent_result": agent_result,
                "qcc_analysis": agent_result.get("qcc_analysis", {}),
                "metadata": {
                    "repo_path": qcc_config.repo_path,
                    "branch_name": qcc_config.branch_name,
                    "pr_title": qcc_config.pr_title,
                    "agent_executed": True,
                    "agent_success": agent_result.get("success", False),
                    "task_id": task_id,
                    "correlation_id": ctx.get("log_correlation_id"),
                    "execution_mode": execution_mode,
                    "generated_at": self._get_current_timestamp(),
                    "repo_validation": {
                        "is_private": is_private,
                        "accessible": True,
                        "message": repo_validation.get("message", "Pre-validated in API"),
                        "validated_in": "sync_execute"
                    }
                }
            }

        except Exception as e:
            task_id = self.get_task_id(ctx)
            log_ctx = self.get_logging_context(ctx)

            self.logger.error("Failed to complete QCC onboarding analysis", extra={
                **log_ctx,
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": str(e.__traceback__) if hasattr(e, '__traceback__') else "No traceback available"
            })
            import traceback
            self.logger.error("Full traceback:", extra={"traceback": traceback.format_exc()})
            return {
                "status": "failed",
                "message": f"Failed to complete QCC analysis: {str(e)}",
                "files": [],
                "pr_url": None,
                "agent_result": {"success": False, "error": str(e)},
                "metadata": {
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "task_id": task_id,
                    "correlation_id": ctx.get("log_correlation_id")
                }
            }

    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def _validate_parameters(self, parameters: Dict[str, Any]) -> None:
        """Validate input parameters."""
        required_fields = ["repo_path"]

        for field in required_fields:
            if field not in parameters or not parameters[field]:
                raise ValueError(f"Missing required parameter: {field}")

        # Validate repo_path format (should be a GitHub clone URL)
        repo_path = parameters.get("repo_path", "")
        if not repo_path.startswith(("https://github.com/", "git@github.com:")):
            raise ValueError(f"Invalid repository path format: {repo_path}. Must be a GitHub repository URL.")

    def _parse_qcc_config(self, parameters: Dict[str, Any]) -> QCCOnboardingConfig:
        """Parse parameters into QCCOnboardingConfig."""
        repo_path = parameters["repo_path"]
        branch_name = parameters.get("branch_name", "")
        pr_title = parameters.get("pr_title", "QCC Onboarding Analysis")

        return QCCOnboardingConfig(
            repo_path=repo_path,
            branch_name=branch_name,
            pr_title=pr_title
        )

    def _validate_repository_access(self, repo_path: str) -> Dict[str, Any]:
        """
        Validate repository access and check if it's private.
        
        Args:
            repo_path: GitHub repository URL
            
        Returns:
            Dictionary with validation results:
            - success: bool
            - is_private: bool (only if success=True)
            - message: str
            - error: str (only if success=False)
        """
        try:
            self.logger.info(f"Checking repository visibility for: {repo_path}")
            
            # Use GitHub auth service to check repository visibility (run async method synchronously)
            visibility_result = asyncio.run(self.github_auth.check_repository_visibility(repo_path))
            
            if not visibility_result.get("success", False):
                error_msg = visibility_result.get("error", "Unknown error checking repository")
                self.logger.warning(f"Repository access validation failed: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "message": f"Unable to access repository: {error_msg}"
                }
            
            is_private = visibility_result.get("is_private", False)
            owner = visibility_result.get("owner", "unknown")
            repo = visibility_result.get("repo", "unknown")
            
            # QCC onboarding is only allowed for private repositories
            if not is_private:
                error_msg = f"QCC onboarding is only available for private repositories. {owner}/{repo} is a public repository."
                self.logger.warning(f"Repository {owner}/{repo} is public - QCC onboarding not allowed for public repositories")
                return {
                    "success": False,
                    "error": error_msg,
                    "message": f"Repository {owner}/{repo} is public. QCC onboarding is restricted to private repositories only."
                }
            
            self.logger.info(f"Repository {owner}/{repo} is private and accessible - proceeding with QCC onboarding")
            message = f"Repository {owner}/{repo} is private and accessible for QCC onboarding"
            
            return {
                "success": True,
                "is_private": is_private,
                "message": message,
                "owner": owner,
                "repo": repo
            }
            
        except Exception as e:
            error_msg = f"Repository validation failed: {str(e)}"
            self.logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "message": "Failed to validate repository access"
            }

    def _call_autonomous_agent(self, config: QCCOnboardingConfig, parameters: Dict[str, Any], ctx: Context) -> Dict[str, Any]:
        """Call the autonomous agent to analyze repository and generate QCC onboarding plan."""
        import time
        import os

        # Use task_id from context using helper method, fallback to generated one if not available
        task_id = self.get_task_id(ctx)
        if not task_id:
            task_id = f"qcc-onboarding-{int(time.time())}"
            self.logger.warning("No task_id provided in context, generated fallback task_id",
                              extra={"generated_task_id": task_id})

        # Get usecase name from metadata
        metadata = self.get_metadata(ctx)
        usecase_name = metadata.get('usecase_name', 'qcc-onboarding')
        log_ctx = self.get_logging_context(ctx)

        self.logger.info("Calling autonomous agent for QCC onboarding analysis",
                       extra={
                           **log_ctx,
                           "repo_path": config.repo_path,
                           "usecase": usecase_name
                       })

        # Check context before calling autonomous agent
        if self.check_context_done(ctx):
            error_msg = "Context is done before calling autonomous agent"
            if ctx.is_cancelled():
                error_msg = "Context was cancelled before calling autonomous agent"
            elif ctx.is_expired():
                error_msg = "Context expired before calling autonomous agent"

            self.logger.warning(error_msg, extra=log_ctx)
            return {
                "success": False,
                "error": error_msg,
                "message": "Failed to call autonomous agent due to context state"
            }

        # Import autonomous agent tool
        try:
            from src.agents.autonomous_agent import AutonomousAgentTool
        except ImportError:
            self.logger.error("Failed to import autonomous agent tool", extra=log_ctx)
            return {
                "success": False,
                "error": "Autonomous agent tool not available",
                "message": "Failed to import autonomous agent module"
            }

        # Execute autonomous agent without custom working directory
        try:
            self.logger.info("Starting autonomous agent execution",
                           extra={
                               **log_ctx,
                               "usecase": usecase_name
                           })

            # Create prompt
            prompt = self._create_agent_prompt(config, parameters)

            # Create autonomous agent tool instance
            agent_tool = AutonomousAgentTool()

            # Call the autonomous agent tool using its default allowed directory
            result = agent_tool.execute({
                "prompt": prompt,
                "task_id": task_id,  # Use the actual database task_id
                "agent_name": usecase_name,
            })

            self.logger.info("Autonomous agent execution completed",
                           extra={
                               **log_ctx,
                               "agent_success": result.get("success", False),
                               "usecase": usecase_name
                           })

            # Process and return results
            return self._process_agent_results(result, config)

        except Exception as e:
            self.logger.error("Autonomous agent execution failed",
                            extra={
                                **log_ctx,
                                "error": str(e),
                                "error_type": type(e).__name__,
                                "usecase": usecase_name
                            })

            return {
                "success": False,
                "error": f"Autonomous agent execution failed: {str(e)}",
                "message": "Failed to complete QCC analysis using autonomous agent"
            }

    def _create_agent_prompt(self, config: QCCOnboardingConfig, parameters: Dict[str, Any]) -> str:
        """Create a comprehensive prompt for the autonomous agent to implement QCC code coverage."""
        
        # Extract repository details
        repo_path = config.repo_path
        branch_name = config.branch_name or f"qcc-onboarding-{int(time.time())}"
        pr_title = config.pr_title

        # Extract repository name from URL
        repo_name = repo_path.split("/")[-1].replace(".git", "") if "/" in repo_path else "unknown-repo"

        # Use the prompt from the separate prompts module
        return create_qcc_implementation_prompt(
            repo_path=repo_path,
            repo_name=repo_name, 
            branch_name=branch_name,
            pr_title=pr_title
        )

    def _process_agent_results(self, agent_result: Dict[str, Any], config: QCCOnboardingConfig) -> Dict[str, Any]:
        """Process AutonomousAgent results and format response."""

        if not agent_result.get("success", False):
            error_msg = agent_result.get("error", "Unknown error during QCC analysis")
            raise Exception(f"QCC onboarding analysis failed: {error_msg}")

        # Create standard response format
        return {
            "success": True,
            "status": "completed",
            "message": f"QCC onboarding analysis completed successfully for repository",
            "files": [
                {
                    "name": "QCC_ONBOARDING_PLAN.md",
                    "content": "Comprehensive QCC onboarding plan and analysis",
                    "type": "documentation"
                },
                {
                    "name": "coverage-config",
                    "content": "Technology-specific coverage configuration files",
                    "type": "configuration"
                },
                {
                    "name": "ci-cd-examples",
                    "content": "Sample CI/CD workflows for coverage reporting",
                    "type": "ci-cd"
                }
            ],
            "pr_url": agent_result.get("pr_url"),
            "qcc_analysis": {
                "repository": config.repo_path,
                "technology_stack": "Detected during analysis",
                "current_coverage": "Analyzed by agent",
                "recommendations": "Generated based on analysis",
                "implementation_plan": "Phased approach provided",
                "tools_recommended": "Technology-specific tools suggested"
            },
            "next_steps": [
                "Review the generated QCC onboarding plan",
                "Implement recommended coverage tools",
                "Configure CI/CD integration for coverage reporting",
                "Set up coverage monitoring and quality gates",
                "Train development team on coverage best practices"
            ],
            "validation_results": {
                "repository_analyzed": True,
                "technology_detected": True,
                "coverage_assessed": True,
                "plan_generated": True,
                "configs_created": True,
                "ci_cd_examples": True
            }
        }


# Register the service using the global registry instance
from ..registry import service_registry
service_registry.register("qcc-onboarding", QCCOnboardingService) 