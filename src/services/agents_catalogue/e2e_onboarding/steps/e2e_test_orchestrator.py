"""
E2E Orchestrator repository step for E2E onboarding workflow.

Handles PR creation for the e2e_test_orchestrator repository with automatic branch detection.
"""
from typing import Any, Dict

from .base import BaseRepositoryStep
from ..prompt_providers.e2e_test_orchestrator import E2ETestOrchestratorPromptProvider
from ..state import E2EOnboardingState
from ..config import RepositoryConfig


class E2ETestOrchestratorStep(BaseRepositoryStep):
    """
    Step for processing e2e_test_orchestrator repository in E2E onboarding workflow.
    
    Creates or updates PRs in the e2e_test_orchestrator repository with test
    orchestration configurations, with automatic branch reuse support.
    """
    
    def __init__(self):
        super().__init__("e2e_test_orchestrator")
    
    def get_prompt(self, state: E2EOnboardingState, branch_name: str, existing_pr_info: Dict[str, Any]) -> str:
        """Generate prompt for e2e_test_orchestrator repository processing."""
        repository_path = RepositoryConfig.get_repository_url("e2e_test_orchestrator", state)
        
        provider = E2ETestOrchestratorPromptProvider()
        return provider.build_complete_prompt(
            state=state,
            repository_path=repository_path,
            branch_name=branch_name,
            existing_pr_info=existing_pr_info,
        )