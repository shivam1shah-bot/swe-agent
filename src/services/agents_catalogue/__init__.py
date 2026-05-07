"""
Agents Catalogue services package.

This package contains all the agents catalogue services and their implementations.
"""

from . import repo_context_generator
from . import spinnaker_pipeline
from .api_doc_generator.service import APIDocGeneratorService
from .bank_uat_agent.service import BankUATService
from .base_service import BaseAgentsCatalogueService
from .spinnaker_pipeline import SpinnakerPipelineService
from .gateway_integration.gateway_integrations_common import GatewayIntegrationService
from .repo_context_generator import RepoContextGeneratorService
from .qcc_onboarding import QCCOnboardingService
from .e2e_onboarding import E2EOnboardingService
from .registry import service_registry, register_service, get_service_for_usecase
from .validator_discovery import validator_discovery
from .bank_integration.service import BankIntegrationService
from .genspec_service import GenSpecService

__all__ = [
    "BaseAgentsCatalogueService",
    "service_registry",
    "register_service",
    "get_service_for_usecase",
    "validator_discovery",
    "SpinnakerPipelineService",
    "GatewayIntegrationService",
    "RepoContextGeneratorService",
    "QCCOnboardingService",
    "GenSpecService",
    "E2EOnboardingService",
    "BankIntegrationService",
    "APIDocGeneratorService",
    "BankUATService"
]
