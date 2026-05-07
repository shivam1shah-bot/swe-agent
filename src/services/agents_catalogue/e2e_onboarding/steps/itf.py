"""
ITF repository step for E2E onboarding workflow.

Handles PR creation for the itf repository with automatic branch detection.
"""
from typing import Dict, Any

from .base import BaseRepositoryStep
from ..prompt_providers.itf import ITFPromptProvider
from ..state import E2EOnboardingState
from ..config import RepositoryConfig


class ITFStep(BaseRepositoryStep):
    """
    Step for processing itf repository in E2E onboarding workflow.
    
    Creates or updates PRs in the ITF (Integration Test Framework) repository
    with test framework configurations, with automatic branch reuse support.
    """
    
    def __init__(self):
        super().__init__("itf")
    
    def get_prompt(self, state: E2EOnboardingState, branch_name: str, existing_pr_info: Dict[str, Any]) -> str:
        """Generate prompt for itf repository processing."""
        repository_path = RepositoryConfig.get_repository_url("itf", state)
        
        provider = ITFPromptProvider()
        return provider.build_complete_prompt(
            state=state,
            repository_path=repository_path,
            branch_name=branch_name,
            existing_pr_info=existing_pr_info,
        ) 