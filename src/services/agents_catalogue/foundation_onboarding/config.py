"""
Configuration settings for the Foundation Onboarding service.

Centralizes all configurable parameters including repositories, workflow settings,
infrastructure endpoints, and service naming conventions.
"""

from typing import Dict, Any


class RepositoryConfig:
    """
    Repository configuration for Foundation Onboarding.
    
    Defines the GitHub repositories that will be modified during the
    foundation onboarding process.
    """
    
    # Repository URLs to be added based on business requirements
    pass


class WorkflowConfig:
    """
    Workflow execution configuration for Foundation Onboarding.
    
    Contains settings for branch naming, timeouts, retry policies,
    and other workflow execution parameters.
    """

    # Branch naming configuration
    BRANCH_PREFIX = "feature/swe-agent"
    BRANCH_SUFFIX = "foundation-onboarding"


class InfrastructureConfig:
    """
    Infrastructure endpoints and configuration for Foundation Onboarding.
    
    Contains endpoints for various infrastructure services used during
    the onboarding process.
    """
    
    # Infrastructure endpoints to be added based on business requirements
    pass

