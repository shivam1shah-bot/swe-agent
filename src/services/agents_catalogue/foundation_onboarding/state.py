"""
Foundation Onboarding State Management

This module defines the state structure for the Foundation Onboarding LangGraph workflow.
Sequential execution with straightforward state management.
"""

from typing import Dict, Any, List, TypedDict, Optional

from langchain_core.messages import BaseMessage
from urllib3.exceptions import DependencyWarning


class FoundationOnboardingState(TypedDict):
    """
    State structure for the Foundation Onboarding LangGraph workflow.
    
    Maintains all data required throughout the onboarding process including
    input parameters, step results, and workflow progress tracking.
    
    Attributes:
        task_id: Unique identifier for the onboarding task
        service_name: Name of the service being onboarded
        input_parameters: All parameters provided for the onboarding
        messages: LangGraph message history for agent interactions
        current_step: Name of the currently executing step
        current_iteration: Retry iteration counter
        workflow_completed: Flag indicating workflow completion
        completed_steps: List of successfully completed step names
        failed_steps: List of failed step names
        skipped_steps: List of skipped step names
        step_results: Detailed results for each step execution
        
        # Step-specific state fields
        repo_info: Repository creation details (URL, clone path, etc.)
        database_info: Database provisioning details (connection strings, credentials)
        kubemanifest_info: Kubernetes manifest generation details
        spinnaker_info: Spinnaker pipeline configuration details
        kafka_info: Kafka consumer and topic setup details
        edge_info: Edge gateway onboarding details
        authz_info: Authorization configuration details
        monitoring_info: Monitoring and alerting setup details
    """

    # Core task information
    task_id: str
    service_name: str
    input_parameters: Dict[str, Any]

    # Message history for LangGraph
    messages: List[BaseMessage]

    # Workflow progress tracking
    current_step: str
    current_iteration: int
    workflow_completed: bool

    # Sequential execution tracking
    completed_steps: List[str]
    failed_steps: List[str]
    skipped_steps: List[str]
    step_results: Dict[str, Dict[str, Any]]  # step_name -> result

    # Step-specific state fields
    # TODO: Define detailed structure for each step's output data
    repo_info: Optional[Dict[str, Any]]
    database_info: Optional[Dict[str, Any]]
    kubemanifest_info: Optional[Dict[str, Any]]
    spinnaker_info: Optional[Dict[str, Any]]
    kafka_info: Optional[Dict[str, Any]]
    edge_info: Optional[Dict[str, Any]]
    authz_info: Optional[Dict[str, Any]]
    monitoring_info: Optional[Dict[str, Any]]


def create_initial_state(task_id: str, parameters: Dict[str, Any]) -> FoundationOnboardingState:
    """
    Create initial state for the Foundation Onboarding workflow.

    Args:
        task_id: Unique identifier for the task
        parameters: Task parameters provided by the user

    Returns:
        Initial FoundationOnboardingState with all fields initialized
    """
    
    # TODO:: add step specific information into to the inital state from the parameters, Dependening on how
    # we define our API Contract

    return FoundationOnboardingState(
        task_id=task_id,
        service_name=parameters.get("service_name", ""),
        input_parameters=parameters,
        messages=[],
        current_step="initialization",
        current_iteration=0,
        workflow_completed=False,
        step_results={},
        completed_steps=[],
        failed_steps=[],
        skipped_steps=[],

        ## TODO: ADD THIS!
        repo_info=None,
        database_info=None,
        kubemanifest_info=None,
        spinnaker_info=None,
        kafka_info=None,
        edge_info=None,
        authz_info=None,
        monitoring_info=None,
    )

