"""
Kube manifest repository step for E2E onboarding workflow.

Handles PR creation for the Kube manifest repository with automatic branch detection.
"""
from typing import Dict, Any

from .base import BaseRepositoryStep
from ..prompt_providers.kubemanifest import KubemanifestPromptProvider
from ..state import E2EOnboardingState
from ..config import RepositoryConfig
from src.providers.logger import Logger, SanitizationLevel
import logging
logger = Logger(__name__, logging.INFO, SanitizationLevel.LENIENT)


class KubemanifestStep(BaseRepositoryStep):
    """
    Step for processing Kube manifest repository in E2E onboarding workflow.
    
    Creates or updates PRs in the Kube manifest repository with Kubernetes
    configurations for E2E testing, with automatic branch reuse support.
    
    Overrides validation logic to check use_ephemeral_db parameter.
    """
    
    def __init__(self):
        super().__init__("kubemanifest")
    
    async def _is_step_execution_allowed(self, repository_name: str, state: E2EOnboardingState) -> bool:
        """
        Override validation logic for kubemanifest step.
        
        Kubemanifest step is only allowed when use_ephemeral_db is True.
        
        Args:
            repository_name: Name of the repository (should be "kubemanifest")
            state: Current workflow state
            
        Returns:
            bool: True if step execution is allowed, False otherwise
        """
        logger.info(f"[FLOW] Kubemanifest step validation - checking use_ephemeral_db")
        logger.info(f"[FLOW] Input parameters: {state.get('input_parameters', {})}")
        
        use_ephemeral_db = state.get("input_parameters", {}).get("use_ephemeral_db")
        
        if use_ephemeral_db is False:
            logger.info(f"[FLOW] Kubemanifest step execution skipped - use_ephemeral_db is False")
            return False
        
        logger.info(f"[FLOW] Kubemanifest step execution allowed - use_ephemeral_db is {use_ephemeral_db}")
        return True
    
    def get_prompt(self, state: E2EOnboardingState, branch_name: str, existing_pr_info: Dict[str, Any]) -> str:
        """Generate prompt for kubemanifest repository processing."""
        repository_path = RepositoryConfig.get_repository_url("kubemanifest", state)

        logger.info(f"Existing PR info: {state.get('step_results', {}).get(self.repository_name, {})}")
        provider = KubemanifestPromptProvider()
        return provider.build_complete_prompt(
            state=state,
            repository_path=repository_path,
            branch_name=branch_name,
            existing_pr_info=existing_pr_info,
        ) 