"""
Service Repository step for E2E onboarding workflow.

Handles PR creation for the service_repo with automatic branch detection.
"""
from typing import Dict, Any

from .base import BaseRepositoryStep
from ..prompt_providers.service_repo import ServiceRepoPromptProvider
from ..state import E2EOnboardingState
from ..config import RepositoryConfig


class ServiceRepoStep(BaseRepositoryStep):
    """
    Step for processing service_repo in E2E onboarding workflow.
    
    Creates or updates PRs in the service's own repository with E2E testing
    configurations, with automatic branch reuse support.
    """
    
    def __init__(self):
        super().__init__("service_repo")
    
    def get_prompt(self, state: E2EOnboardingState, branch_name: str, existing_pr_info: Dict[str, Any]) -> str:
        """Generate prompt for service_repo processing."""
        service = state["service"]
        repository_path = f"https://github.com/razorpay/{service}"
        
        provider = ServiceRepoPromptProvider()
        return provider.build_complete_prompt(
            state=state,
            repository_path=repository_path,
            branch_name=branch_name,
            existing_pr_info=existing_pr_info,
        ) 