import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Dict, Any

from src.providers.logger import Logger, SanitizationLevel
from ..base_service import BaseAgentsCatalogueService
from src.providers.context import Context
from .state import create_initial_state
from .helper import format_final_response, log_behavior
from .workflow import create_e2e_onboarding_workflow
from .validator import E2EOnboardingValidator

logger = Logger(__name__,  logging.INFO, SanitizationLevel.LENIENT)

class E2EOnboardingService(BaseAgentsCatalogueService):
    """
    E2E Onboarding Service with sequential LangGraph workflow.
    
    Provides automated E2E onboarding functionality for services with comprehensive
    parameter validation, workflow execution, and configuration support including:
    - Database configuration (ephemeral and static)
    - Authentication setup for E2E tests
    - Helm chart value overrides
    - Multi-repository branch coordination
    - Comprehensive parameter validation
    """

    def __init__(self):
        """Initialize the E2E onboarding service."""
        self.validator = E2EOnboardingValidator()

    @property
    def description(self) -> str:
        """Service description."""
        return ("Automated end-to-end onboarding service that orchestrates sequential workflow "
                "across multiple repositories (kubemanifest, e2e-orchestrator, end-to-end-tests, "
                "ITF, and service repositories) with intelligent branch detection, deterministic "
                "naming, parameter validation, and background processing capabilities")

    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Queue E2E onboarding task for background processing."""
        try:
            logger.info("E2E onboarding initiated", parameters=parameters)

            self.validator.validate_parameters(parameters)
            service_name = parameters["service_name"]
            logger.info("E2E onboarding parameters validated")

            from src.tasks.queue_integration import queue_integration
            if not queue_integration.is_queue_available():
                return {
                    "status": "failed",
                    "message": "Queue not available",
                    "metadata": {
                        "error": "Queue not available"
                    }
                }

            task_id = queue_integration.submit_agents_catalogue_task(
                usecase_name="e2e-onboarding",
                parameters=parameters
            )

            if task_id:
                return {
                    "status": "queued",
                    "message": f"E2E onboarding workflow queued for {service_name} successfully",
                    "task_id": task_id,
                    "metadata": {
                        "queued_at": datetime.now(timezone.utc).isoformat(),
                        "validated_parameters": {**parameters}
                    }
                }
            else:
                return {
                    "status": "failed",
                    "message": "Failed to queue e2e onboarding",
                    "metadata": {
                        "error": "Failed to submit to queue"
                    }
                }

        except Exception as e:
            logger.error(f"Error queuing E2E onboarding task: {str(e)}")
            return {
                "status": "failed",
                "message": "Failed to queue E2E onboarding task",
                "metadata": {
                    "error": str(e)
                }
            }

    def async_execute(self, parameters: Dict[str, Any], ctx: Context) -> Dict[str, Any]:
        """Execute E2E onboarding workflow in background worker."""

        execution_start = time.time()
        final_state = {}

        # Extract task information from context
        task_id = self.get_task_id(ctx)
        log_ctx = self.get_logging_context(ctx)

        try:
            # Validate required parameters
            self.validator.validate_parameters(parameters)

            log_behavior(task_id, "Parameters Validated", 
                        f"E2E onboarding parameters validated successfully for task {task_id}")

            logger.info(f"Parameters validated for task {task_id}", data=log_ctx)


            log_behavior(task_id, "Workflow Initialization",
                        "Creating LangGraph workflow and initial state")

            workflow = create_e2e_onboarding_workflow()

            initial_state = create_initial_state(
                task_id=task_id,
                parameters=parameters
            )

            log_behavior(task_id, "LangGraph Workflow Execution", 
                        "Executing LangGraph workflow with sequential repository processing")
            
            try:
                # Check if event loop is already running (worker context)
                asyncio.get_running_loop()

                # Event loop exists, run in separate thread
                def run_workflow():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(workflow.ainvoke(initial_state))
                    finally:
                        new_loop.close()

                with ThreadPoolExecutor() as executor:
                    future = executor.submit(run_workflow)
                    final_state = future.result()
            except RuntimeError:
                # No event loop running, can use asyncio.run directly
                final_state = asyncio.run(workflow.ainvoke(initial_state))
            
            log_behavior(task_id, "LangGraph Workflow Completed", 
                        f"LangGraph workflow execution completed for task {task_id}")
            
            execution_time = time.time() - execution_start

            response = format_final_response(final_state)
            status = response.get("status", "unknown")

            # Log final workflow status
            if status == "completed":
                successful_repos = len([repo for repo, result in final_state.get("step_results", {}).items() 
                                    if result.get("success", False)])
                total_repos = len(final_state.get("repositories", {}))
                log_behavior(task_id, "E2E Onboarding Workflow Success", 
                        f"E2E onboarding completed successfully. {successful_repos}/{total_repos} repositories processed successfully")
            else:
                failed_repos = len([repo for repo, result in final_state.get("step_results", {}).items() 
                                if not result.get("success", False)])
                log_behavior(task_id, "E2E Onboarding Workflow Partial Success", 
                        f"E2E onboarding completed with {failed_repos} failed repositories")

            response["metadata"] = response.get("metadata", {})
            response["metadata"].update({
                "correlation_id": ctx.get("log_correlation_id"),
                "execution_mode": "async",
                "processed_by_worker": True,
                "execution_time": execution_time,
            })

            logger.info(f"E2E onboarding workflow completed for task: {task_id}", data={
                **log_ctx,
                "execution_time": execution_time,
            })
            return response

        except Exception as e:
            execution_time = time.time() - execution_start

            log_behavior(task_id, "E2E Onboarding Workflow Failed", 
                        f"E2E onboarding workflow failed with error: {str(e)}")

            logger.error("Error executing E2E onboarding workflow", data={
                **log_ctx,
                "error": str(e),
                "error_type": type(e).__name__,
                "execution_time": execution_time,
            })

            return {
                "status": "failed",
                "message": f"Error executing E2E onboarding workflow: {str(e)}",
                "workflow_type": "langgraph",
                "error": str(e),
                "execution_time": execution_time,
                "metadata": {
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "task_id": task_id,
                    "correlation_id": ctx.get("log_correlation_id") if ctx else None
                }
            }


# Register the service
from ..registry import service_registry
service_registry.register("e2e-onboarding", E2EOnboardingService)