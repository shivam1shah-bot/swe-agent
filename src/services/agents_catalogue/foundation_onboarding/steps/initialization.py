"""
Initialization step for the Foundation Onboarding workflow.

This step performs initial setup and validation before the main
onboarding workflow begins. It prepares the state and validates
all prerequisites are met.
"""

import logging

from ..state import FoundationOnboardingState
from ..helper import generate_branch_name, log_behavior
from ..config import RepositoryConfig
from .base import BaseWorkflowStep

logger = logging.getLogger(__name__)


class InitializationStep(BaseWorkflowStep):
    """
    Initialization step for Foundation Onboarding workflow.
    
    Responsibilities:
    - Validate all prerequisites are met
    - Initialize repository URLs in state
    - Generate branch names for all repositories
    - Set up any required API clients or connections
    - Log workflow start
    """

    async def execute(self, state: FoundationOnboardingState) -> FoundationOnboardingState:
        """
        Execute initialization for the foundation onboarding workflow.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with initialization complete
        """
        
        task_id = state.get("task_id", "unknown")
        service_name = state.get("service_name", "unknown")
        
        try:
            log_behavior(task_id, "Initialization Step Started", 
                        f"Starting foundation onboarding initialization for service: {service_name}")
            logger.info(f"Starting foundation onboarding initialization for service: {service_name}")
            
            # Generate branch name for this service
            branch_name = generate_branch_name(service_name)
            log_behavior(task_id, "Branch Name Generated", 
                        f"Generated branch name for service {service_name}: {branch_name}")
            logger.info(f"Using branch name: {branch_name}")
            
            # Initialize repository URLs
            # TODO: Populate repositories dict with URLs from RepositoryConfig
            # based on which steps are enabled in input_parameters
            
            # Update state
            state["current_step"] = "repo_creation"
            state["completed_steps"].append("initialization")
            
            log_behavior(task_id, "Initialization Step Completed", 
                        f"Foundation onboarding initialization completed successfully for service {service_name}")
            logger.info("INITIALIZATION_STEP_COMPLETED")
            
            return state
            
        except Exception as e:
            error_msg = f"INITIALIZATION_STEP_FAILED: {str(e)}"
            log_behavior(task_id, "Initialization Step Failed", 
                        f"Foundation onboarding initialization failed for service {service_name}: {str(e)}")
            logger.error(error_msg)
            state["failed_steps"].append("initialization")
            raise

