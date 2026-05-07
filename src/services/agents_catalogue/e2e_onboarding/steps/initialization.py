"""
Initialization step for the E2E onboarding workflow.

This step performs initial setup for sequential execution.
"""

import logging
import time

from src.providers.telemetry import get_meter, is_metrics_initialized
from ..state import E2EOnboardingState
from ..helper import generate_branch_name, log_behavior
from .base import BaseWorkflowStep

logger = logging.getLogger(__name__)

# Import workflow stage metrics helper from base
from .base import _get_workflow_stage_metrics


class InitializationStep(BaseWorkflowStep):
    """
    Initialization step for E2E onboarding workflow.
    
    Sets up initial state for sequential processing.
    """

    async def execute(self, state: E2EOnboardingState) -> E2EOnboardingState:
        """
        Execute initialization for sequential workflow.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with initialization complete
        """
        agent_name = "e2e-onboarding"
        stage_name = "initialization"
        stage_start = time.time()
        task_id = state.get("task_id", "unknown")
        service = state.get("service", "unknown")
        
        try:
            log_behavior(task_id, "Initialization Step Started", 
                        f"Starting E2E onboarding initialization for service: {service}")
            logger.info(f"Starting E2E onboarding initialization for service: {state['service']}")
            
            # Generate branch name for this service
            branch_name = generate_branch_name(state["service"])
            log_behavior(task_id, "Branch Name Generated", 
                        f"Generated branch name for service {service}: {branch_name}")
            logger.info(f"Using branch name: {branch_name}")
            
            # Update state
            state["current_step"] = "sequential_repository_processing"
            state["completed_steps"].append("initialization")
            
            log_behavior(task_id, "Initialization Step Completed", 
                        f"E2E onboarding initialization completed successfully for service {service}")
            logger.info(f"INITIALIZATION_STEP_COMPLETED")
            
            # Record metrics for successful stage
            stage_duration = time.time() - stage_start
            status = "success"
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
            
        except Exception as e:
            error_msg = f"INITIALIZATION_STEP_FAILED: {str(e)}"
            log_behavior(task_id, "Initialization Step Failed", 
                        f"E2E onboarding initialization failed for service {service}: {str(e)}")
            logger.error(error_msg)
            state["failed_steps"].append("initialization")
            
            # Record metrics for failed stage
            stage_duration = time.time() - stage_start
            status = "failed"
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
            
            raise 