"""
Edge Onboarding step for the Foundation Onboarding workflow.

This step configures edge gateway routing and API management
for the new service, making it accessible through the gateway.
"""

import logging
from typing import Dict, Any, List

from ..state import FoundationOnboardingState
from ..helper import log_behavior, generate_branch_name
from .base import BaseFoundationStep

logger = logging.getLogger(__name__)


class EdgeOnboardingStep(BaseFoundationStep):
    """
    Edge Onboarding step for Foundation Onboarding workflow.
    
    Responsibilities:
    - Create PR in edge-config repository
    """

    def __init__(self):
        """Initialize the edge onboarding step."""
        super().__init__(step_name="edge_onboarding")

    async def execute_step(self, state: FoundationOnboardingState) -> FoundationOnboardingState:
        """
        Execute edge gateway configuration for the new service.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with edge information
        """
        task_id = state.get("task_id", "unknown")
        service_name = state.get("service_name", "unknown")
        
        logger.info(f"[EDGE_ONBOARDING] Starting edge configuration for {service_name}")
        log_behavior(task_id, "Edge Onboarding Started", 
                    f"Configuring edge gateway for service {service_name}")
        
        try:
            # Business logic to be added
            pass
            
        except Exception as e:
            logger.error(f"[EDGE_ONBOARDING] Failed to configure edge: {str(e)}")
            raise

    async def _is_step_execution_allowed(self, state: FoundationOnboardingState) -> bool:
        """
        Check if edge onboarding should be executed.
        
        Edge onboarding might be skipped if:
        - edge_config is not provided
        - skip_edge=True in parameters
        - Service is internal-only (no external access needed)
        
        Args:
            state: Current workflow state
            
        Returns:
            True if step should execute
        """
        input_params = state.get("input_parameters", {})
        
        if input_params.get("skip_edge", False):
            logger.info("[EDGE_ONBOARDING] skip_edge=True, skipping")
            return False
        
        if input_params.get("internal_only", False):
            logger.info("[EDGE_ONBOARDING] Service is internal-only, skipping edge")
            return False
        
        return True
