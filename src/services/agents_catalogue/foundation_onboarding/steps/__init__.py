"""
Foundation Onboarding Workflow Steps

This module contains all the individual steps for the Foundation Onboarding workflow.
Each step is responsible for a specific part of the service onboarding process.

Steps are executed sequentially in the following order:
1. InitializationStep - Initial setup and validation
2. RepoCreationStep - Create GitHub repository
3. DatabaseCreationStep - Provision database
4. KubemanifestStep - Generate Kubernetes manifests
5. SpinnakerPipelineStep - Create Spinnaker pipeline
6. ConsumerTopicSetupStep - Setup Kafka consumers and topics
7. EdgeOnboardingStep - Configure edge gateway
8. AuthzOnboardingStep - Setup authorization
9. MonitoringSetupStep - Configure monitoring
10. ValidationStep - Final validation
"""

from .base import BaseFoundationStep, BaseWorkflowStep
from .initialization import InitializationStep
from .repo_creation import RepoCreationStep
from .database_creation import DatabaseCreationStep
from .kubemanifest import KubemanifestStep
from .spinnaker_pipeline import SpinnakerPipelineStep
from .consumer_topic_setup import ConsumerTopicSetupStep
from .edge_onboarding import EdgeOnboardingStep
from .authz_onboarding import AuthzOnboardingStep
from .monitoring_setup import MonitoringSetupStep
from .validation import ValidationStep

__all__ = [
    # Base classes
    "BaseFoundationStep",
    "BaseWorkflowStep",
    
    # Workflow steps (in execution order)
    "InitializationStep",
    "RepoCreationStep",
    "DatabaseCreationStep",
    "KubemanifestStep",
    "SpinnakerPipelineStep",
    "ConsumerTopicSetupStep",
    "EdgeOnboardingStep",
    "AuthzOnboardingStep",
    "MonitoringSetupStep",
    "ValidationStep",
]

