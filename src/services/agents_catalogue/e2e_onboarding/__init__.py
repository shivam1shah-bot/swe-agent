"""
E2E Onboarding Module

This module provides automated E2E onboarding functionality for services
using LangGraph workflow with parallel repository processing.
"""

from .service import E2EOnboardingService
from .config import RepositoryConfig, WorkflowConfig
from .state import E2EOnboardingState
from .validator import E2EOnboardingValidator

__all__ = [
    "E2EOnboardingService",
    "RepositoryConfig", 
    "WorkflowConfig",
    "E2EOnboardingState",
    "E2EOnboardingValidator"
]

__version__ = "2.0.0" 