"""
Foundation Onboarding LangGraph Workflow

This module contains the LangGraph workflow definition for the Foundation Onboarding process.
It implements sequential execution of service onboarding steps following LangGraph best practices.

Workflow Steps (in order):
1. Initialization - Setup and validate initial state
2. Repo Creation - Create GitHub repository for the service
3. Database Creation - Provision database resources
4. Kubemanifest - Generate Kubernetes manifests
5. Spinnaker Pipeline - Create deployment pipeline
6. Consumer & Topic Setup - Setup Kafka consumers and topics
7. Edge Onboarding - Configure edge gateway routing
8. Authz Onboarding - Setup authorization policies
9. Monitoring Setup - Configure monitoring and alerting
10. Validation - Final validation and cleanup
"""

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

from .state import FoundationOnboardingState
from .steps import (
    InitializationStep,
    RepoCreationStep,
    DatabaseCreationStep,
    KubemanifestStep,
    SpinnakerPipelineStep,
    ConsumerTopicSetupStep,
    EdgeOnboardingStep,
    AuthzOnboardingStep,
    MonitoringSetupStep,
    ValidationStep,
)


def create_foundation_onboarding_workflow() -> CompiledStateGraph:
    """
    Create Foundation Onboarding workflow with sequential execution.
    
    This workflow orchestrates the complete service onboarding process
    through a series of sequential steps. Each step must complete
    successfully before the next step begins.
    
    Returns:
        Compiled LangGraph StateGraph ready for execution
    """
    # TODO: Implement complete workflow creation
    # - Create StateGraph with FoundationOnboardingState
    # - Instantiate all step classes
    # - Add all nodes to the workflow
    # - Define edges for sequential execution
    # - Set entry point
    # - Add conditional routing if needed (for error handling)
    # - Compile and return the workflow
    
    workflow = StateGraph(FoundationOnboardingState)
    
    # Create step instances
    initialization_step = InitializationStep()
    repo_creation_step = RepoCreationStep()
    database_creation_step = DatabaseCreationStep()
    kubemanifest_step = KubemanifestStep()
    spinnaker_pipeline_step = SpinnakerPipelineStep()
    consumer_topic_setup_step = ConsumerTopicSetupStep()
    edge_onboarding_step = EdgeOnboardingStep()
    authz_onboarding_step = AuthzOnboardingStep()
    monitoring_setup_step = MonitoringSetupStep()
    validation_step = ValidationStep()
    
    # Add nodes to workflow
    workflow.add_node("initialization", initialization_step.execute)
    workflow.add_node("repo_creation", repo_creation_step.execute)
    workflow.add_node("database_creation", database_creation_step.execute)
    workflow.add_node("kubemanifest", kubemanifest_step.execute)
    workflow.add_node("spinnaker_pipeline", spinnaker_pipeline_step.execute)
    workflow.add_node("consumer_topic_setup", consumer_topic_setup_step.execute)
    workflow.add_node("edge_onboarding", edge_onboarding_step.execute)
    workflow.add_node("authz_onboarding", authz_onboarding_step.execute)
    workflow.add_node("monitoring_setup", monitoring_setup_step.execute)
    workflow.add_node("validation", validation_step.execute)
    
    # Set entry point
    workflow.set_entry_point("initialization")
    
    # Define sequential workflow edges
    workflow.add_edge("initialization", "repo_creation")
    workflow.add_edge("repo_creation", "database_creation")
    workflow.add_edge("database_creation", "kubemanifest")
    workflow.add_edge("kubemanifest", "spinnaker_pipeline")
    workflow.add_edge("spinnaker_pipeline", "consumer_topic_setup")
    workflow.add_edge("consumer_topic_setup", "edge_onboarding")
    workflow.add_edge("edge_onboarding", "authz_onboarding")
    workflow.add_edge("authz_onboarding", "monitoring_setup")
    workflow.add_edge("monitoring_setup", "validation")
    
    # Final edge to END
    workflow.add_edge("validation", END)
    
    return workflow.compile()


## TODO:: In next phase if required.
def create_foundation_onboarding_workflow_with_error_handling() -> CompiledStateGraph:
    """
    Create Foundation Onboarding workflow with conditional error handling.
    
    This is an alternative workflow that includes conditional routing
    for error handling and step skipping based on configuration.
    
    Returns:
        Compiled LangGraph StateGraph with error handling
    """
    # TODO: Implement workflow with conditional routing
    # - Add conditional edges based on step success/failure
    # - Add error handling nodes
    # - Add rollback nodes if needed
    # - Implement step skipping based on configuration
    
    # For now, return the basic workflow
    return create_foundation_onboarding_workflow()

