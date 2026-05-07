"""
E2E Onboarding Prompt Providers

This module contains repository-specific prompt providers for the E2E onboarding workflow.
Each provider follows the provider class pattern with methods for different prompt sections.
"""

# Import provider classes
from .kubemanifest import KubemanifestPromptProvider
from .e2e_test_orchestrator import E2ETestOrchestratorPromptProvider  
from .end_to_end_tests import EndToEndTestsPromptProvider
from .itf import ITFPromptProvider
from .service_repo import ServiceRepoPromptProvider

# All backward compatibility functions have been removed
# Use the provider classes instead

__all__ = [
    # Provider classes
    "KubemanifestPromptProvider",
    "E2ETestOrchestratorPromptProvider", 
    "EndToEndTestsPromptProvider",
    "ITFPromptProvider",
    "ServiceRepoPromptProvider"
] 