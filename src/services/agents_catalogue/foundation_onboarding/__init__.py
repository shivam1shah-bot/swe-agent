"""
Foundation Onboarding Module

This module provides automated foundation onboarding functionality for new services
using LangGraph workflow with sequential step processing.

Foundation onboarding covers the complete service setup including:
- Repository creation
- Database provisioning
- Kubernetes manifest setup
- Spinnaker pipeline configuration
- Kafka consumer and topic setup
- Edge gateway onboarding
- Authorization (Authz) onboarding
- Monitoring and alerting setup
"""

from .service import FoundationOnboardingService
from .config import RepositoryConfig, WorkflowConfig
from .state import FoundationOnboardingState
from .validator import FoundationOnboardingValidator

__all__ = [
    "FoundationOnboardingService",
    "RepositoryConfig",
    "WorkflowConfig",
    "FoundationOnboardingState",
    "FoundationOnboardingValidator"
]

__version__ = "1.0.0"

