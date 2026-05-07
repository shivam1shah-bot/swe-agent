"""
QCC Onboarding Service Package

This package contains the QCC (Quality Code Coverage) onboarding service
and related components for implementing code coverage with graceful shutdown
and S3 integration.
"""

from .qcc_onboarding_service import QCCOnboardingService
from .prompts import create_qcc_implementation_prompt

__all__ = [
    "QCCOnboardingService",
    "create_qcc_implementation_prompt"
] 