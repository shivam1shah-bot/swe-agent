"""
End-to-End Tests repository step for E2E onboarding workflow.

Handles PR creation for the end_to_end_tests repository with automatic branch detection.
"""
from typing import Dict, Any

from .base import BaseRepositoryStep
from ..prompt_providers.end_to_end_tests import EndToEndTestsPromptProvider
from ..state import E2EOnboardingState
from ..config import RepositoryConfig


class EndToEndTestsStep(BaseRepositoryStep):
    """
    Step for processing end_to_end_tests repository in E2E onboarding workflow.
    
    Creates or updates PRs in the end_to_end_tests repository with test cases
    and configurations, with automatic branch reuse support.
    """
    
    def __init__(self):
        super().__init__("end_to_end_tests")
    
    def get_prompt(self, state: E2EOnboardingState, branch_name: str, existing_pr_info: Dict[str, Any]) -> str:
        """Generate prompt for end_to_end_tests repository processing."""
        repository_path = RepositoryConfig.get_repository_url("end_to_end_tests", state)
        
        provider = EndToEndTestsPromptProvider()
        return provider.build_complete_prompt(
            state=state,
            repository_path=repository_path,
            branch_name=branch_name,
            existing_pr_info=existing_pr_info,
        ) 