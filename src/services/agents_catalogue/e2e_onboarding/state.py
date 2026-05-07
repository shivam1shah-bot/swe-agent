"""
E2E Onboarding State Management

This module defines the simplified state structure for the E2E onboarding LangGraph workflow.
Sequential execution with straightforward state management.
"""

from typing import Dict, Any, List, TypedDict

from langchain_core.messages import BaseMessage

from .config import RepositoryConfig

class E2EOnboardingState(TypedDict):
    """
    Simplified state structure for the E2E onboarding LangGraph workflow.
    
    Sequential execution without reducers or complex state management.
    """

    # Core task information and task parameters
    task_id: str
    service: str
    input_parameters: Dict[str, Any]

    # Message history
    messages: List[BaseMessage]

    # Workflow progress tracking
    current_step: str
    current_iteration: int
    workflow_completed: bool

    # Repository information
    repositories: Dict[str, str]  # repo_name -> repo_url

    # Sequential execution tracking
    completed_steps: List[str]
    failed_steps: List[str]
    skipped_steps: List[str]
    step_results: Dict[str, Dict[str, Any]]  # repo_name -> result


def create_initial_state(task_id: str, parameters: Dict[str, Any]) -> E2EOnboardingState:
    """
    Create initial state for the E2E onboarding workflow.

    Args:
        task_id: Unique identifier for the task
        parameters: Task parameters provided by the user

    Returns:
        Initial E2EOnboardingState
    """
    return E2EOnboardingState(
        task_id=task_id,
        service=parameters['service_name'],
        input_parameters=parameters,
        messages=[],
        current_step="initialization",
        current_iteration=0,
        workflow_completed=False,
        repositories=RepositoryConfig.REPOSITORIES,
        step_results={},
        completed_steps=[],
        failed_steps=[],
    )