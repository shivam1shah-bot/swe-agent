"""
Helper functions for Foundation Onboarding workflow.

This module contains utility functions for logging, branch name generation,
response formatting, and other common operations used throughout the
foundation onboarding workflow.
"""

import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Dict, Any, List

from src.providers.logger import Logger, SanitizationLevel
from .config import WorkflowConfig
from .state import FoundationOnboardingState

logger = Logger(__name__, logging.INFO, SanitizationLevel.LENIENT)


def log_behavior(task_id: str, action: str, description: str) -> None:
    """
    Log agent behavior for a task to create a timeline of actions.

    Creates a structured log file for each task that records all actions
    taken during the foundation onboarding workflow.

    Args:
        task_id: The ID of the task
        action: The action being performed (e.g., "Repo Creation Started")
        description: A detailed description of the action
    """
    
    timestamp = time.time()
    formatted_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    behavior_entry = {
        "timestamp": timestamp,
        "formatted_time": formatted_time,
        "action": action,
        "description": description
    }

    log_dir = os.path.join("tmp", "logs", "foundation-onboarding-logs")
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, f"task_{task_id}.json")
    try:
        if os.path.exists(log_file):
            with open(log_file, "r") as f:
                existing_logs = json.load(f)
            existing_logs.append(behavior_entry)
            logs_to_save = existing_logs
        else:
            logs_to_save = [behavior_entry]

        with open(log_file, "w") as f:
            json.dump(logs_to_save, f, indent=2)
        logger.debug(f"Saved behavior log for task {task_id}: {action}")
    except Exception as e:
        logger.error(f"Error saving behavior log for task {task_id}: {e}")


def generate_branch_name(service_name: str) -> str:
    """
    Generate a consistent branch name for a service.

    Creates a branch name following the pattern:
    feature/swe-agent/<service-name>-foundation-onboarding

    Args:
        service_name: Name of the service being onboarded

    Returns:
        Generated branch name string
    """
    
    clean_service_key = service_name.lower().replace('_', '-')
    return f"{WorkflowConfig.BRANCH_PREFIX}/{clean_service_key}-{WorkflowConfig.BRANCH_SUFFIX}"


def get_successful_steps(state: FoundationOnboardingState) -> List[str]:
    """
    Get list of successfully completed steps from state.

    Args:
        state: Current workflow state

    Returns:
        List of step names that completed successfully
    """
    
    return [
        step for step, result in state["step_results"].items()
        if result.get("success", False)
    ]


def get_failed_steps(state: FoundationOnboardingState) -> List[str]:
    """
    Get list of failed steps from state.

    Args:
        state: Current workflow state

    Returns:
        List of step names that failed
    """
    
    return [
        step for step, result in state["step_results"].items()
        if not result.get("success", False) and not result.get("skipped", False)
    ]


def get_skipped_steps(state: FoundationOnboardingState) -> List[str]:
    """
    Get list of skipped steps from state.

    Args:
        state: Current workflow state

    Returns:
        List of step names that were skipped
    """
    # TODO: Implement skipped steps extraction
    
    return [
        step for step, result in state["step_results"].items()
        if result.get("skipped", False)
    ]


def _get_workflow_summary(state: FoundationOnboardingState) -> Dict[str, Any]:
    """
    Generate a comprehensive summary of the workflow execution.

    Creates a detailed summary including success/failure counts,
    PR URLs, and error information for each step.

    Args:
        state: Final workflow state

    Returns:
        Dictionary containing workflow summary
    """
    
    successful_steps = get_successful_steps(state)
    failed_steps = get_failed_steps(state)
    skipped_steps = get_skipped_steps(state)

    pr_urls = []
    for step_name, result in state.get("step_results", {}).items():
        if result.get("pr_url"):
            pr_urls.append({
                "step": step_name,
                "pr_url": result["pr_url"],
                "success": result.get("success", False)
            })

    summary = {
        "task_id": state["task_id"],
        "service_name": state["service_name"],
        "workflow_completed": state["workflow_completed"],
        "current_iteration": state["current_iteration"],
        "total_steps": len(state.get("step_results", {})),
        "successful_steps": successful_steps,
        "success_count": len(successful_steps),
        "failed_steps": failed_steps,
        "failure_count": len(failed_steps),
        "skipped_steps": skipped_steps,
        "skipped_count": len(skipped_steps),
        "pr_urls": pr_urls,
        "errors": {
            step: state["step_results"].get(step, {}).get("error")
            for step in failed_steps
        }
    }
    
    return summary


def format_final_response(final_state: FoundationOnboardingState) -> Dict[str, Any]:
    """
    Format the final response from workflow state.

    Converts the final workflow state into a user-friendly response
    format suitable for API responses.

    Args:
        final_state: Final workflow state after execution

    Returns:
        Formatted response dictionary
    """
    
    try:
        summary = _get_workflow_summary(final_state)
        successful_steps = summary["successful_steps"]
        failed_steps = summary["failed_steps"]
        skipped_steps = summary["skipped_steps"]

        if len(failed_steps) == 0:
            status = "completed"
            message = f"Foundation onboarding completed successfully for all {len(successful_steps)} steps"
        elif len(successful_steps) > 0:
            status = "partial_success"
            message = f"Foundation onboarding completed with {len(successful_steps)} successes and {len(failed_steps)} failures"
        else:
            status = "failed"
            message = "Foundation onboarding failed for all steps"

        response = {
            "status": status,
            "task_id": summary["task_id"],
            "service_name": summary["service_name"],
            "message": message,
            "steps_completed": successful_steps,
            "steps_failed": failed_steps,
            "steps_skipped": skipped_steps,
            "pr_urls": summary["pr_urls"],
            "workflow_completed": summary["workflow_completed"],
            "timestamp": datetime.now().isoformat(),
            "summary": summary,
            # TODO: Add step-specific output URLs
            # - repo_url from repo_info
            # - database_connection_string from database_info
            # - spinnaker_pipeline_url from spinnaker_info
            # - monitoring_dashboard_url from monitoring_info
        }
        
        return response
    except Exception as e:
        logger.error(f"Error formatting final response: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "message": "Error formatting workflow results"
        }


def extract_pr_url(state: FoundationOnboardingState, result: Dict[str, Any], step_name: str) -> str:
    """
    Extract PR URL from step execution result.

    Parses the result content to find GitHub PR URLs.

    Args:
        state: Current workflow state
        result: Step execution result
        step_name: Name of the step

    Returns:
        PR URL string or empty string if not found
    """
    # Custom logic to be added
    pass


def validate_service_name(service_name: str) -> bool:
    """
    Validate that a service name follows naming conventions.

    Args:
        service_name: Name to validate

    Returns:
        True if valid, False otherwise
    """
    
    if not service_name or not service_name.strip():
        return False
    
    # Basic validation pattern
    pattern = r'^[a-zA-Z][a-zA-Z0-9-]*[a-zA-Z0-9]$'
    return bool(re.match(pattern, service_name)) and len(service_name) <= 63

