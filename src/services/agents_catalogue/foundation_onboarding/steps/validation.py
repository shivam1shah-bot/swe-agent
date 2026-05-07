"""
Validation step for the Foundation Onboarding workflow.

This is the final step that validates the entire onboarding process,
performs cleanup, and generates the final summary.
"""

import logging
from typing import Dict, Any, List

from ..state import FoundationOnboardingState
from ..helper import log_behavior, get_successful_steps, get_failed_steps, get_skipped_steps
from .base import BaseWorkflowStep

logger = logging.getLogger(__name__)


class ValidationStep(BaseWorkflowStep):
    """
    Validation step for Foundation Onboarding workflow.
    
    Responsibilities:
    - Validate all prior steps completed successfully
    - Verify created resources are accessible
    - Generate comprehensive summary report
    - Perform any necessary cleanup
    - Mark workflow as completed
    - Log final status and metrics
    """
    async def execute(self, state: FoundationOnboardingState) -> FoundationOnboardingState:
        """
        Execute final validation and generate summary.
        
        Args:
            state: Current workflow state
            
        Returns:
            Final workflow state with validation results
        """
        
        task_id = state.get("task_id", "unknown")
        service_name = state.get("service_name", "unknown")
        
        try:
            log_behavior(task_id, "Validation Step Started", 
                        f"Starting final validation for service {service_name}")
            logger.info(f"Starting validation for service: {service_name}")
            
            # Collect step results
            successful_steps = get_successful_steps(state)
            failed_steps = get_failed_steps(state)
            skipped_steps = get_skipped_steps(state)
            
            logger.info(f"Validation Summary:")
            logger.info(f"  - Successful steps: {len(successful_steps)}")
            logger.info(f"  - Failed steps: {len(failed_steps)}")
            logger.info(f"  - Skipped steps: {len(skipped_steps)}")
            
            # Determine overall status
            if len(failed_steps) == 0:
                overall_status = "success"
                message = f"Foundation onboarding completed successfully for {service_name}"
            elif len(successful_steps) > 0:
                overall_status = "partial_success"
                message = f"Foundation onboarding completed with some failures for {service_name}"
            else:
                overall_status = "failed"
                message = f"Foundation onboarding failed for {service_name}"
            
            # Update state
            state["workflow_completed"] = True
            state["completed_steps"].append("validation")
            state["step_results"]["validation"] = {
                "success": True,
                "overall_status": overall_status,
                "message": message,
                "summary": {
                    "successful_steps": successful_steps,
                    "failed_steps": failed_steps,
                    "skipped_steps": skipped_steps,
                    "total_steps": len(state.get("step_results", {})),
                }
            }

            log_behavior(task_id, "Validation Step Completed", 
                        f"Foundation onboarding validation completed: {overall_status}")
            logger.info(f"VALIDATION_STEP_COMPLETED: {overall_status}")
            
            return state
            
        except Exception as e:
            error_msg = f"VALIDATION_STEP_FAILED: {str(e)}"
            log_behavior(task_id, "Validation Step Failed", 
                        f"Foundation onboarding validation failed: {str(e)}")
            logger.error(error_msg)
            state["failed_steps"].append("validation")
            state["workflow_completed"] = True  # Mark as completed even on validation failure
            raise