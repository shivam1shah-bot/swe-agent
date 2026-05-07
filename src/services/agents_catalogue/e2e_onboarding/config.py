"""
Configuration settings for the E2E onboarding service.

Centralizes all configurable parameters including repositories, workflow settings,
agent parameters, and branch naming with automatic branch detection.
"""

from .validator import E2EOnboardingValidator
from typing import Dict, Any


class RepositoryConfig:
    """Repository configuration for E2E onboarding."""

    REPOSITORIES = {
        "kubemanifest": "https://github.com/razorpay/kube-manifests",
        "e2e_test_orchestrator": "https://github.com/razorpay/e2e-test-orchestrator",
        "end_to_end_tests": "https://github.com/razorpay/end-to-end-tests",
        "itf": "https://github.com/razorpay/goutils"
    }
    
    @staticmethod
    def get_repository_url(repository_name: str, state: Dict[str, Any] = None) -> str:
        """
        Get repository URL dynamically.
        
        Args:
            repository_name: Name of the repository
            state: Optional state dictionary to get service_url from
            
        Returns:
            Repository URL
        """
        # Check if it's a static repository
        if repository_name in RepositoryConfig.REPOSITORIES:
            return RepositoryConfig.REPOSITORIES[repository_name]
        
        # For service_repo, get URL from state
        if repository_name == "service_repo" and state:
            return state.get("input_parameters", {}).get("service_url", "")
        
        # Fallback
        return ""

    SERVICE_VALIDATORS = {
        "e2e-onboarding": E2EOnboardingValidator().validate_parameters,
    }


class WorkflowConfig:
    """Workflow execution configuration."""

    BRANCH_PREFIX = "feature/swe-agent"
    BRANCH_SUFFIX = "e2e-onboarding"