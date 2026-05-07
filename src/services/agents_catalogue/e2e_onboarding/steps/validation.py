"""
Finalization Step for E2E Onboarding Workflow

This module contains the finalization step that validates results,
determines success/failure, and completes the workflow.
"""

import logging
import time

from src.providers.telemetry import get_meter, is_metrics_initialized
from .base import BaseWorkflowStep
from ..state import E2EOnboardingState
from ..helper import get_successful_repositories, get_failed_repositories, log_behavior

logger = logging.getLogger(__name__)

# Import workflow stage metrics helper from base
from .base import _get_workflow_stage_metrics


class ValidationStep(BaseWorkflowStep):
    """
    Finalization step for the E2E onboarding workflow.
    
    This step combines validation, completion, and failure handling:
    1. Validates results from all parallel repository steps
    2. Updates the final checklist status
    3. Logs success/failure details with PR URLs and errors
    4. Marks workflow as completed
    """

    async def execute(self, state: E2EOnboardingState) -> E2EOnboardingState:
        """
        Execute the finalization step.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated workflow state with final results
        """
        agent_name = "e2e-onboarding"
        stage_name = "validation"
        stage_start = time.time()
        task_id = state["task_id"]
        service_key = state["service"]

        for repo, result in state.get("step_results", {}).items():
            logger.info(f"repo: {repo}, result: {result}")


        log_behavior(task_id, "Validation Step Started", 
                    f"Starting workflow finalization and validation for service {service_key}")
        logger.info(f"[{task_id}] Starting workflow finalization for {service_key}")

        # Get successful and failed repositories
        successful_repos = get_successful_repositories(state)
        failed_repos = get_failed_repositories(state)

        # Count results
        total_repos = len(state["repositories"])
        success_count = len(successful_repos)
        failure_count = len(failed_repos)

        log_behavior(task_id, "Repository Results Analysis", 
                    f"Analyzed {total_repos} repositories: {success_count} successful, {failure_count} failed")

        # Determine if all PRs are ready
        all_prs_ready = success_count == total_repos

        # Mark workflow as completed (always true since this is the final step)
        state["workflow_completed"] = True

        # Determine final status and log results
        if all_prs_ready:
            # Complete success
            state["current_step"] = "completed"
            state["completed_steps"].append("complete_workflow")

            log_behavior(task_id, "E2E Onboarding Complete Success", 
                        f"E2E onboarding completed successfully for {service_key} - all {success_count} repositories processed successfully")
            logger.info(f"[{task_id}] E2E onboarding completed successfully for {service_key}")
            logger.info(f"[{task_id}] Successfully created {success_count} PRs across all repositories")

            # Log successful PR URLs
            pr_urls = []
            for repo in successful_repos:
                result = state["step_results"].get(repo, {})
                if result.get("pr_url"):
                    pr_urls.append(f"{repo}: {result['pr_url']}")
                    logger.info(f"[{task_id}] {repo.title()} PR: {result['pr_url']}")
            
            if pr_urls:
                log_behavior(task_id, "All PRs Created Successfully", 
                           f"Created PRs for all repositories: {', '.join(pr_urls)}")

        else:
            # Partial or complete failure
            if success_count > 0:
                state["current_step"] = "partially_failed"
                log_behavior(task_id, "E2E Onboarding Partial Success", 
                           f"E2E onboarding partially successful for {service_key} - {success_count}/{total_repos} repositories processed successfully")
                logger.warning(f"[{task_id}] E2E onboarding partially failed for {service_key}")
                logger.info(f"[{task_id}] Successfully processed {success_count}/{total_repos} repositories")

                # Log successful PR URLs
                for repo in successful_repos:
                    result = state["step_results"].get(repo, {})
                    if result.get("pr_url"):
                        logger.info(f"[{task_id}] {repo.title()} PR (Success): {result['pr_url']}")
            else:
                state["current_step"] = "failed"
                log_behavior(task_id, "E2E Onboarding Complete Failure", 
                           f"E2E onboarding failed completely for {service_key} - no repositories processed successfully")
                logger.error(f"[{task_id}] E2E onboarding failed completely for {service_key}")

            # Log failed repositories and errors
            if failed_repos:
                failed_details = []
                logger.error(f"[{task_id}] Failed repositories: {', '.join(failed_repos)}")
                for repo in failed_repos:
                    result = state["step_results"].get(repo, {})
                    error_msg = result.get("error", "Unknown error")
                    failed_details.append(f"{repo}: {error_msg}")
                    logger.error(f"[{task_id}] {repo.title()} Error: {error_msg}")
                
                log_behavior(task_id, "Failed Repositories Summary", 
                           f"Failed repositories and errors: {'; '.join(failed_details)}")

        # Log final summary
        final_summary = f"Total: {total_repos}, Success: {success_count}, Failed: {failure_count}"
        log_behavior(task_id, "Validation Step Completed", 
                    f"E2E onboarding validation completed - {final_summary}")
        logger.info(f"[{task_id}] Final Summary - {final_summary}")

        # Record metrics for validation stage
        stage_duration = time.time() - stage_start
        status = "success" if all_prs_ready else ("partial" if success_count > 0 else "failed")
        invocations, duration = _get_workflow_stage_metrics()
        if invocations is not None:
            invocations.labels(
                agent_name=agent_name,
                stage_name=stage_name,
                status=status
            ).inc()
        if duration is not None:
            duration.labels(
                agent_name=agent_name,
                stage_name=stage_name,
                status=status
            ).observe(stage_duration)

        return state
