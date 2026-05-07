import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Dict, Any, List

from src.providers.logger import Logger, SanitizationLevel
from .config import RepositoryConfig, WorkflowConfig
from .state import E2EOnboardingState

logger = Logger(__name__, logging.INFO, SanitizationLevel.LENIENT)


def log_behavior(task_id: str, action: str, description: str) -> None:
    """
    Log agent behavior for a task to create a timeline of actions.

    Args:
        task_id: The ID of the task
        action: The action being performed
        description: A description of the action
    """
    timestamp = time.time()
    formatted_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    behavior_entry = {
        "timestamp": timestamp,
        "formatted_time": formatted_time,
        "action": action,
        "description": description
    }

    # Create structured directory for logs
    log_dir = os.path.join("tmp", "logs", "e2e-onboarding-logs")
    os.makedirs(log_dir, exist_ok=True)

    # Save the behavior log to a file
    log_file = os.path.join(log_dir, f"task_{task_id}.json")
    try:
        # Check if file exists
        if os.path.exists(log_file):
            with open(log_file, "r") as f:
                existing_logs = json.load(f)
            existing_logs.append(behavior_entry)
            logs_to_save = existing_logs
        else:
            logs_to_save = [behavior_entry]

        # Write updated logs
        with open(log_file, "w") as f:
            json.dump(logs_to_save, f, indent=2)
        logger.debug(f"Saved behavior log for task {task_id}: {action}")
    except Exception as e:
        logger.error(f"Error saving behavior log for task {task_id}: {e}")


def generate_branch_name(service: str) -> str:
    """Generate branch name for a service."""
    clean_service_key = service.lower().replace('_', '-')
    return f"{WorkflowConfig.BRANCH_PREFIX}/{clean_service_key}-{WorkflowConfig.BRANCH_SUFFIX}"


def prepare_e2e_config(
        service: str,
        repo_name: str,
        branch_info: Dict[str, Any]
) -> Dict[str, Any]:
    """Prepare tool configuration for the agent based on existing work detection."""
    branch_name = branch_info["branch_name"]
    has_existing_work = branch_info.get("has_existing_work", False)

    config = {
        "branch_name": branch_name,
        "service": service,
        "repository_name": repo_name,
    }

    if has_existing_work:
        config.update({
            "commit_message": f"Update E2E onboarding for {service} (iteration)",
            "pr_title": f"[UPDATE] E2E Onboarding: {service}",
            "pr_description": f"Updated E2E onboarding configuration for {service} service.\n\nThis is an iterative update to the existing work.",
            "mode": "update_existing"
        })
        logger.info(f"Configured for updating existing work in {repo_name} on branch {branch_name}")
    else:
        config.update({
            "commit_message": f"Add E2E onboarding for {service}",
            "pr_title": f"E2E Onboarding: {service}",
            "pr_description": f"Initial E2E onboarding configuration for {service} service.\n\nThis PR adds all necessary configurations for end-to-end testing integration.",
            "mode": "create_new"
        })
        logger.info(f"Configured for creating new work in {repo_name} on branch {branch_name}")

    return config

def get_successful_repositories(state: E2EOnboardingState) -> List[str]:
    """Returns a list of repository names that completed successfully."""
    return [
        repo for repo, result in state["step_results"].items()
        if result.get("success", False)
    ]


def get_failed_repositories(state: E2EOnboardingState) -> List[str]:
    """Returns a list of repository names that failed."""
    return [
        repo for repo, result in state["step_results"].items()
        if not result.get("success", False) and not result.get("skipped", False)
    ]

def get_skipped_repositories(state: E2EOnboardingState) -> List[str]:
    """Returns a list of repository names that were skipped."""
    return [
        repo for repo, result in state["step_results"].items()
        if result.get("skipped", False)
    ]


def _get_workflow_summary(state: E2EOnboardingState) -> Dict[str, Any]:
    """
    Generates a comprehensive summary of the workflow execution.
    """
    successful_repos = get_successful_repositories(state)
    failed_repos = get_failed_repositories(state)
    skipped_repos = get_skipped_repositories(state)

    pr_urls = []
    logger.info(f"[SUMMARY] Iterating over repositories: {list(state['repositories'].keys())}")
    
    # Log complete step_results first
    step_results = state.get('step_results', {})
    for repo_name, result in step_results.items():
        logger.info(f"[SUMMARY]   {repo_name}: {result}")
    
    for repo, repo_url in state["repositories"].items():
        logger.info(f"[SUMMARY] Processing repo: {repo}, url: {repo_url}")
        result = state["step_results"].get(repo, {})
        logger.info(f"[SUMMARY] Result for {repo}: success={result.get('success')}, pr_url={result.get('pr_url')}, branch_name={result.get('branch_name')}")
        if result.get("pr_url"):
            pr_urls.append({
                "repository": repo,
                "pr_url": result["pr_url"],
                "success": result.get("success", False)
            })
            logger.info(f"[SUMMARY] Added PR URL for {repo}: {result['pr_url']}")
        else:
            logger.info(f"[SUMMARY] No PR URL found for {repo}")

    # Include branch information from step results
    branch_info = {}
    logger.info(f"[SUMMARY] Building branch_info:")
    for repo, repo_url in state["repositories"].items():
        result = state["step_results"].get(repo, {})
        logger.info(f"[SUMMARY] Checking branch for {repo}: branch_name={result.get('branch_name')}")
        if result.get("branch_name"):
            branch_info[repo] = {
                "branch_name": result["branch_name"],
                "success": result.get("success", False)
            }
            logger.info(f"[SUMMARY] Added branch info for {repo}: {branch_info[repo]}")
        else:
            logger.info(f"[SUMMARY] No branch_name found for {repo}")
    
    logger.info(f"[SUMMARY] Final branch_info: {branch_info}")

    summary = {
        "task_id": state["task_id"],
        "service": state["service"],
        "workflow_completed": state["workflow_completed"],
        "current_iteration": state["current_iteration"],
        "total_repositories": len(state["repositories"]),
        "successful_repositories": successful_repos,
        "success_count": len(successful_repos),
        "failed_repositories": failed_repos,
        "failure_count": len(failed_repos),
        "skipped_repositories": skipped_repos,
        "skipped_count": len(skipped_repos),
        "pr_urls": pr_urls,
        "branch_info": branch_info,
        "errors": {
            repo: state["step_results"].get(repo, {}).get("error")
            for repo in failed_repos
        }
    }
    
    logger.info(f"[SUMMARY] Created summary with keys: {list(summary.keys())}")
    logger.info(f"[SUMMARY] Total repositories: {summary['total_repositories']}")
    logger.info(f"[SUMMARY] Success count: {summary['success_count']}")
    logger.info(f"[SUMMARY] Failure count: {summary['failure_count']}")
    logger.info(f"[SUMMARY] Skipped count: {summary['skipped_count']}")
    logger.info(f"[SUMMARY] PR URLs count: {len(summary['pr_urls'])}")
    logger.info(f"[SUMMARY] Branch info count: {len(summary['branch_info'])}")
    logger.info(f"[SUMMARY] Complete summary: {summary}")
    
    return summary

def format_final_response(final_state: E2EOnboardingState) -> Dict[str, Any]:
    """Format the final response from workflow state."""
    try:
        summary = _get_workflow_summary(final_state)
        successful_repos = summary["successful_repositories"]
        failed_repos = summary["failed_repositories"]
        skipped_repos = summary["skipped_repositories"]
        pr_urls = summary["pr_urls"]
        branch_info = summary["branch_info"]

        if len(failed_repos) == 0:
            status = "completed"
            message = f"E2E onboarding completed successfully for all {len(successful_repos)} repositories"
        elif len(successful_repos) > 0:
            status = "partial_success"
            message = f"E2E onboarding completed with {len(successful_repos)} successes and {len(failed_repos)} failures"
        else:
            status = "failed"
            message = "E2E onboarding failed for all repositories"
            
        repositories_processed = summary["total_repositories"]

        response = {
            "status": status,
            "task_id": summary["task_id"],
            "service": summary["service"],
            "message": message,
            "repositories_processed": repositories_processed,
            "successful_repositories": successful_repos,
            "failed_repositories": failed_repos,
            "skipped_repositories": skipped_repos,
            "pr_urls": pr_urls,
            "branch_info": branch_info,
            "workflow_completed": summary["workflow_completed"],
            "timestamp": datetime.now().isoformat(),
            "summary": summary
        }
        
        return response
    except Exception as e:
        logger.error(f"Error formatting final response: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "message": "Error formatting workflow results"
        }

def extract_pr_url(state: E2EOnboardingState, result: Dict[str, Any], repository_name: str) -> str:
    """Fetch the PR URL from the result."""
    logger.info(f"[FLOW] Entering extract_pr_url for {repository_name}")
    try:
        if isinstance(result, dict):
            if 'result' in result and isinstance(result['result'], dict):
                content = result['result'].get('content', '')
                if isinstance(content, str):
                    # First try to find full GitHub PR URL
                    pr_url_pattern = r'https://github\.com/[^/]+/[^/]+/pull/\d+'
                    match = re.search(pr_url_pattern, content)
                    if match:
                        return match.group(0)
                    
                    # If no full URL found, look for PR number pattern like #2254
                    pr_number_pattern = r'#(\d+)'
                    pr_match = re.search(pr_number_pattern, content)
                    if pr_match:
                        pr_number = pr_match.group(1)
                        # Get the actual repository URL from config and extract repo name
                        repo_url = RepositoryConfig.get_repository_url(repository_name, state)
                        if repo_url:
                            # Extract owner/repo from URL like "https://github.com/razorpay/kube-manifests"
                            url_match = re.match(r'https://github\.com/([^/]+)/([^/]+)/?', repo_url)
                            if url_match:
                                owner, repo = url_match.groups()
                                return f"https://github.com/{owner}/{repo}/pull/{pr_number}"
                        # Fallback to original approach if config lookup fails
                        return f"https://github.com/razorpay/{repository_name}/pull/{pr_number}"
            
            if 'pr_url' in result:
                return result['pr_url']
            
        return result.get("pr_url", "")
    except Exception as e:
        logger.error(f"[FLOW] Error fetching PR URL from result: {e}")
        return result.get("pr_url", "") 