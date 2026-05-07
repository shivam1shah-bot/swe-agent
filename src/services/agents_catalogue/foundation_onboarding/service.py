"""
Foundation Onboarding Service

This module contains the main service class for the Foundation Onboarding workflow.
It provides the entry point for both synchronous (queue submission) and asynchronous
(background worker) execution of the foundation onboarding process.
"""

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
from .workflow import create_foundation_onboarding_workflow
from .validator import FoundationOnboardingValidator

logger = Logger(__name__, logging.INFO, SanitizationLevel.LENIENT)


class FoundationOnboardingService(BaseAgentsCatalogueService):
    """
    Foundation Onboarding Service with sequential LangGraph workflow.
    
    Provides automated foundation onboarding functionality for new services
    with comprehensive parameter validation, workflow execution, and
    configuration support including:
    - Repository creation and setup
    - Database provisioning
    - Kubernetes manifest generation
    - Spinnaker pipeline configuration
    - Kafka consumer and topic setup
    - Edge gateway onboarding
    - Authorization configuration
    - Monitoring and alerting setup
    """

    def __init__(self):
        """Initialize the Foundation Onboarding service."""        
        self.validator = FoundationOnboardingValidator()

    @property
    def description(self) -> str:
        """Service description for registry and documentation."""
        return (
            "Automated foundation onboarding service that orchestrates the complete "
            "setup of a new service including repository creation, database provisioning, "
            "Kubernetes manifests, Spinnaker pipelines, Kafka setup, edge gateway routing, "
            "authorization policies, and monitoring configuration"
        )

    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Queue Foundation Onboarding task for background processing.
        
        This method validates parameters and submits the task to the
        background processing queue. The actual workflow execution
        happens in the worker via async_execute.

        Args:
            parameters: Onboarding parameters from the API request

        Returns:
            Dictionary with queue submission status and task_id
        """
        
        try:
            logger.info("Foundation onboarding initiated", parameters=parameters)

            self.validator.validate_parameters(parameters)
            service_name = parameters["service_name"]
            logger.info("Foundation onboarding parameters validated")

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
                usecase_name="foundation-onboarding",
                parameters=parameters
            )

            if task_id:
                return {
                    "status": "queued",
                    "message": f"Foundation onboarding workflow queued for {service_name} successfully",
                    "task_id": task_id,
                    "metadata": {
                        "queued_at": datetime.now(timezone.utc).isoformat(),
                        "validated_parameters": {**parameters}
                    }
                }
            else:
                return {
                    "status": "failed",
                    "message": "Failed to queue foundation onboarding",
                    "metadata": {
                        "error": "Failed to submit to queue"
                    }
                }

        except Exception as e:
            logger.error(f"Error queuing foundation onboarding task: {str(e)}")
            return {
                "status": "failed",
                "message": "Failed to queue foundation onboarding task",
                "metadata": {
                    "error": str(e)
                }
            }

    def async_execute(self, parameters: Dict[str, Any], ctx: Context) -> Dict[str, Any]:
        """
        Execute Foundation Onboarding workflow in background worker.
        
        This method is called by the background worker to execute the
        actual LangGraph workflow. It creates the initial state,
        runs the workflow, and formats the response.

        Args:
            parameters: Validated onboarding parameters
            ctx: Execution context from the worker

        Returns:
            Dictionary with workflow execution results
        """
        
        execution_start = time.time()
        final_state = {}

        # Extract task information from context
        task_id = self.get_task_id(ctx)
        log_ctx = self.get_logging_context(ctx)

        try:
            # Validate required parameters
            self.validator.validate_parameters(parameters)

            log_behavior(task_id, "Parameters Validated", 
                        f"Foundation onboarding parameters validated successfully for task {task_id}")

            logger.info(f"Parameters validated for task {task_id}", data=log_ctx)

            log_behavior(task_id, "Workflow Initialization",
                        "Creating LangGraph workflow and initial state")

            workflow = create_foundation_onboarding_workflow()

            initial_state = create_initial_state(
                task_id=task_id,
                parameters=parameters
            )

            log_behavior(task_id, "LangGraph Workflow Execution", 
                        "Executing LangGraph workflow with sequential step processing")
            
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

            # Log final workflow status
            if response.get("status") == "completed":
                successful_steps = len(response.get("steps_completed", []))
                log_behavior(task_id, "Foundation Onboarding Workflow Success", 
                        f"Foundation onboarding completed successfully. {successful_steps} steps processed successfully")
            else:
                failed_steps = len(response.get("steps_failed", []))
                log_behavior(task_id, "Foundation Onboarding Workflow Partial Success", 
                        f"Foundation onboarding completed with {failed_steps} failed steps")

            response["metadata"] = response.get("metadata", {})
            response["metadata"].update({
                "correlation_id": ctx.get("log_correlation_id"),
                "execution_mode": "async",
                "processed_by_worker": True,
                "execution_time": execution_time,
            })

            logger.info(f"Foundation onboarding workflow completed for task: {task_id}", data={
                **log_ctx,
                "execution_time": execution_time,
            })
            return response

        except Exception as e:
            execution_time = time.time() - execution_start
            
            log_behavior(task_id, "Foundation Onboarding Workflow Failed", 
                        f"Foundation onboarding workflow failed with error: {str(e)}")

            logger.error("Error executing foundation onboarding workflow", data={
                **log_ctx,
                "error": str(e),
                "error_type": type(e).__name__,
                "execution_time": execution_time
            })

            return {
                "status": "failed",
                "message": f"Error executing foundation onboarding workflow: {str(e)}",
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


# Register the service with the agents catalogue registry
from ..registry import service_registry
service_registry.register("foundation-onboarding", FoundationOnboardingService)

