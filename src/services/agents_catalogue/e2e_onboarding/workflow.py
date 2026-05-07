"""
E2E Onboarding LangGraph Workflow

This module contains the LangGraph workflow definition for the E2E onboarding process.
It implements sequential execution of repository processing steps following LangGraph best practices.
"""

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

from .state import E2EOnboardingState
from .steps import (
    InitializationStep,
    KubemanifestStep,
    E2ETestOrchestratorStep,
    EndToEndTestsStep,
    ITFStep,
    ServiceRepoStep,
    ValidationStep
)

def create_e2e_onboarding_workflow() -> CompiledStateGraph:
    """Create E2E onboarding workflow with sequential execution."""    
    workflow = StateGraph(E2EOnboardingState)
    
    # Create step instances
    initialization_step = InitializationStep()
    kube_manifest_step = KubemanifestStep()
    e2e_test_orchestrator_step = E2ETestOrchestratorStep()
    end_to_end_tests_step = EndToEndTestsStep()
    itf_step = ITFStep()
    service_repo_step = ServiceRepoStep()
    finalization_step = ValidationStep()
    
    # Add nodes 
    workflow.add_node("initialization", initialization_step.execute)
    workflow.add_node("kubemanifest", kube_manifest_step.execute)
    workflow.add_node("e2e_test_orchestrator", e2e_test_orchestrator_step.execute)
    workflow.add_node("end_to_end_tests", end_to_end_tests_step.execute)
    workflow.add_node("itf", itf_step.execute)
    workflow.add_node("service_repo", service_repo_step.execute)
    workflow.add_node("finalization", finalization_step.execute)
    
    # Set entry point and define workflow edges (sequential execution)
    workflow.set_entry_point("initialization")
    workflow.add_edge("initialization", "kubemanifest")
    workflow.add_edge("kubemanifest", "e2e_test_orchestrator")
    workflow.add_edge("e2e_test_orchestrator", "end_to_end_tests")
    workflow.add_edge("end_to_end_tests", "itf")
    workflow.add_edge("itf", "service_repo")
    workflow.add_edge("service_repo", "finalization")
    
    workflow.add_edge("finalization", END)
    
    return workflow.compile()