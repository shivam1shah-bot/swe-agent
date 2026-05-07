import logging
import os
import json
import time
from datetime import datetime
from typing import Dict, Any
import hashlib
import random
import string
import requests

from src.services.agents_catalogue.gateway_integration.gateway_integration_state import GatewayIntegrationState
from src.agents.autonomous_agent import AutonomousAgentTool
from src.providers.config_loader import get_config
from src.services.agents_catalogue.gateway_integration.repository_config import RepositoryConfig

logger = logging.getLogger(__name__)

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
    log_dir = os.path.join("tmp", "logs", "workflow-logs")
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

def generate_devstack_label_hash(gateway_name: str) -> str:
    """
    Generate a consistent hash from gateway name for devstack labels.

    Args:
        gateway_name: The gateway name to hash

    Returns:
        A 5-character hash string
    """
    # Create a consistent hash from the gateway name using SHA-256 (secure)
    hash_object = hashlib.sha256(gateway_name.lower().encode())

    # Take first 5 characters of the hex digest
    return hash_object.hexdigest()[:5]

def generate_randomized_devstack_label(gateway_name: str, task_id: str) -> str:
    """
    Generate a randomized devstack label for deployment.
    This ensures the label is unique and stays under Kubernetes 63-character limit.

    Args:
        gateway_name: The gateway name
        task_id: The task ID for additional uniqueness

    Returns:
        A randomized devstack label string
    """
    # Create a unique seed from gateway name and task_id using SHA-256 (secure)
    seed_data = f"{gateway_name.lower()}-{task_id}-{time.time()}"
    hash_object = hashlib.sha256(seed_data.encode())

    # Generate a random suffix for additional uniqueness
    random.seed(hash_object.hexdigest())
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

    # Combine gateway name prefix with random suffix
    gateway_prefix = gateway_name.lower()[:8]  # Limit to 8 chars
    label = f"swe-{gateway_prefix}-{random_suffix}"
    return label

def get_or_create_agent(
    state: GatewayIntegrationState,
    repo_name: str,
    tool_config: Dict[str, Any],
    is_retry: bool = False
) -> AutonomousAgentTool:

    """

    Get existing agent instance or create a new one for the given repository.
    Maintains agent state across workflow iterations.
    Args:

        state: The workflow state
        repo_name: Name of the repository
        tool_config: Configuration for the agent tool
        is_retry: Whether this is a retry iteration
    Returns:

        AutonomousAgentTool instance
    """

    task_id = state["task_id"]

    # Check if agent already exists
    if repo_name in state["agent_instances"]:

        agent = state["agent_instances"][repo_name]
        if is_retry:

            log_behavior(task_id, f"Agent Reused for {repo_name}",
                        f"Continuing with existing agent - iteration {state['current_iteration']}")
        return agent
    else:

        # Create new agent instance
        agent = AutonomousAgentTool(tool_config)

        # Store agent instance for future use
        state["agent_instances"][repo_name] = agent

        # Initialize context for this agent
        state["agent_contexts"][repo_name] = {
            "repository": repo_name,
            "created_at": datetime.now().isoformat(),
            "iterations": [],
            "files_modified": [],
            "previous_results": []
        }
        log_behavior(task_id, f"Agent Created for {repo_name}",
                    "New agent instance created and stored for persistence")
        return agent

def update_agent_context(
    state: GatewayIntegrationState,
    repo_name: str,
    result: Dict[str, Any]
) -> None:

    """

    Update agent context with results from the current iteration.
    Args:

        state: The workflow state
        repo_name: Name of the repository
        result: Result from the agent execution
    """

    if repo_name not in state["agent_contexts"]:

        state["agent_contexts"][repo_name] = {
            "repository": repo_name,
            "created_at": datetime.now().isoformat(),
            "iterations": [],
            "files_modified": [],
            "previous_results": []
        }
    context = state["agent_contexts"][repo_name]

    # Add current iteration data
    iteration_data = {
        "iteration": state["current_iteration"],
        "timestamp": datetime.now().isoformat(),
        "success": result.get("success", False),
        "files_modified": result.get("files_modified", []),
        "pr_url": result.get("pr_url"),
        "branch": result.get("branch"),
        "message": result.get("message", "")
    }
    context["iterations"].append(iteration_data)
    context["previous_results"].append(result)

    # Update cumulative files modified
    new_files = result.get("files_modified", [])
    for file in new_files:

        if file not in context["files_modified"]:

            context["files_modified"].append(file)

def initialize_workflow(state: GatewayIntegrationState) -> GatewayIntegrationState:

    """Initialize the gateway integration workflow"""

    task_id = state["task_id"]
    gateway_name = state["gateway_name"]
    log_behavior(task_id, "Workflow Initialized", f"Starting gateway integration for {gateway_name}")

    # Generate randomized devstack label for consistent usage throughout workflow
    devstack_label = generate_randomized_devstack_label(gateway_name, task_id)
    state["devstack_label"] = devstack_label
    log_behavior(task_id, "Devstack Label Generated", f"Using devstack label: {devstack_label}")

    # Initialize repositories
    state["repositories"] = {
        "integrations-go": RepositoryConfig.INTEGRATIONS_GO,
        "integrations-upi": RepositoryConfig.INTEGRATIONS_UPI
    }

    # Initialize agent instances and contexts for persistence
    state["agent_instances"] = {}
    state["agent_contexts"] = {}
    state["integrations_go_result"] = {}

    # Initialize results
    state["integrations_upi_result"] = {}
    state["integrations_go_result"] = {}
    state["current_step"] = "initialized"
    state["completed_steps"].append("initialize")
    return state


async def check_github_branch_and_pr(repo_url: str, branch_name: str) -> Dict[str, Any]:

    """

    Check if a branch exists in GitHub and if it has an associated PR using GitHub REST API.
    Args:

        repo_url: GitHub repository URL
        branch_name: Branch name to check
    Returns:

        Dictionary with branch and PR information
    """

    try:

        # Extract owner and repo name from URL

        # e.g., "https://github.com/razorpay/terminals" -> owner="razorpay", repo="terminals"

        import re
        match = re.match(r'https://github\.com/([^/]+)/([^/]+)/?', repo_url)
        if not match:

            return {"exists": False, "error": "Invalid repository URL format"}
        owner, repo = match.groups()

        # Debug logging
        logger.info(f"Checking GitHub for branch: {branch_name} in {owner}/{repo}")

        # GitHub API base URL
        api_base = "https://api.github.com"

        # Headers for GitHub API (add auth token if available)
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "SWE-Agent"
        }

        # Add auth token if available from configuration
        config = get_config()
        github_token = config.get("github.token")
        if github_token:

            headers["Authorization"] = f"token {github_token}"
            logger.info(f"Using GitHub token for authentication (token length: {len(github_token)})")
        else:

            logger.warning("No GitHub token found in environment variables")
        try:

            # Check if branch exists using GitHub API
            branch_url = f"{api_base}/repos/{owner}/{repo}/branches/{branch_name}"
            logger.info(f"Making branch API call to: {branch_url}")
            branch_response = requests.get(branch_url, headers=headers, timeout=10)
            logger.info(f"Branch API response: status={branch_response.status_code}")
            if branch_response.status_code != 200:

                logger.info(f"Branch API response body: {branch_response.text[:500]}")
            branch_exists = branch_response.status_code == 200
            if not branch_exists:

                logger.info(f"Branch {branch_name} does not exist in {owner}/{repo}")
                return {"exists": False, "branch_exists": False}
            logger.info(f"Branch {branch_name} exists in {owner}/{repo}")

            # Check for PRs with this branch as head using GitHub API
            prs_url = f"{api_base}/repos/{owner}/{repo}/pulls"
            prs_params = {
                "head": f"{owner}:{branch_name}",
                "state": "open"
            }
            logger.info(f"Making PR API call to: {prs_url} with params: {prs_params}")
            prs_response = requests.get(prs_url, headers=headers, params=prs_params, timeout=10)
            logger.info(f"PR API response: status={prs_response.status_code}")
            if prs_response.status_code == 200:

                prs_data = prs_response.json()
                logger.info(f"PR API returned {len(prs_data)} PRs")
                if prs_data and len(prs_data) > 0:

                    pr = prs_data[0]  # Get the first matching PR
                    logger.info(f"Found PR: {pr.get('html_url')} (#{pr.get('number')})")
                    return {
                        "exists": True,
                        "branch_exists": True,
                        "pr_exists": True,
                        "pr_url": pr.get("html_url", ""),
                        "pr_number": pr.get("number"),
                        "pr_title": pr.get("title", ""),
                        "branch": branch_name
                    }
                else:

                    logger.info(f"No PRs found for branch {branch_name}")
                    return {
                        "exists": True,
                        "branch_exists": True,
                        "pr_exists": False,
                        "branch": branch_name
                    }
            else:

                logger.warning(f"GitHub API error checking PRs: {prs_response.status_code}")
                logger.warning(f"PR API response body: {prs_response.text[:500]}")
                return {
                    "exists": True,
                    "branch_exists": True,
                    "pr_exists": False,
                    "branch": branch_name
                }
        except requests.exceptions.RequestException as e:

            logger.warning(f"GitHub API request failed: {e}")
            return {"exists": False, "error": f"GitHub API error: {str(e)}"}
    except Exception as e:

        logger.exception(f"Error checking GitHub branch and PR: {e}")
        return {"exists": False, "error": str(e)}

async def check_existing_pr(
    state: GatewayIntegrationState,
    repo_name: str,
    gateway_name: str,
    method: str
) -> Dict[str, Any]:

    """

    Check if there's already an existing branch/PR for this gateway integration.
    Args:

        state: The workflow state
        repo_name: Name of the repository
        gateway_name: Gateway name
        method: Payment method
    Returns:

        Dictionary with existing PR information or empty dict if none found
    """

    task_id = state["task_id"]
    try:

        # Generate the standardized branch name
        branch_name = f"feature/swe-agent/{gateway_name.lower()}-{method.lower()}-integration"

        # First check if manual PR URLs are provided in state (for user-specified existing PRs)
        manual_prs = state.get("existing_prs", {})
        if repo_name in manual_prs:

            pr_url = manual_prs[repo_name]
            log_behavior(task_id, f"Manual PR Found for {repo_name}",
                        f"User-specified PR: {pr_url}, Branch: {branch_name}")
            return {
                "exists": True,
                "pr_url": pr_url,
                "branch": branch_name,
                "from_manual": True
            }

        # Check agent context for previous PR information
        if repo_name in state["agent_contexts"]:

            context = state["agent_contexts"][repo_name]
            for iteration in context.get("iterations", []):

                if iteration.get("pr_url") and iteration.get("branch"):

                    log_behavior(task_id, f"Found Existing PR for {repo_name}",
                                f"PR: {iteration['pr_url']}, Branch: {iteration['branch']}")
                    return {
                        "exists": True,
                        "pr_url": iteration["pr_url"],
                        "branch": iteration["branch"],
                        "from_context": True
                    }

        # Check GitHub for existing branch and PR using the standardized branch name
        repo_url = state["repositories"][repo_name]
        github_result = await check_github_branch_and_pr(repo_url, branch_name)
        if github_result.get("pr_exists", False):

            log_behavior(task_id, f"GitHub PR Found for {repo_name}",
                        f"PR: {github_result['pr_url']}, Branch: {github_result['branch']}")
            return {
                "exists": True,
                "pr_url": github_result["pr_url"],
                "branch": github_result["branch"],
                "pr_number": github_result.get("pr_number"),
                "pr_title": github_result.get("pr_title"),
                "from_github": True
            }
        elif github_result.get("branch_exists", False):

            log_behavior(task_id, f"GitHub Branch Found for {repo_name}",
                        f"Branch exists but no PR: {github_result['branch']}")
            return {
                "exists": True,
                "pr_url": None,
                "branch": github_result["branch"],
                "branch_only": True,
                "from_github": True
            }
        log_behavior(task_id, f"No Existing PR/Branch Found for {repo_name}",
                    f"Will create new branch: {branch_name}")
        return {"exists": False, "branch": branch_name}
    except Exception as e:

        logger.exception(f"Error checking existing PR for {repo_name}: {e}")
        # Still return the branch name for creation
        branch_name = f"feature/swe-agent/{gateway_name.lower()}-{method.lower()}-integration"
        return {"exists": False, "error": str(e), "branch": branch_name}

def prepare_integration_config(
    state: GatewayIntegrationState,
    repo_name: str,
    gateway_name: str,
    method: str,
    existing_pr_info: Dict[str, Any]
) -> Dict[str, Any]:

    """

    Prepare tool configuration for integration, considering existing PRs.
    Args:

        state: The workflow state
        repo_name: Name of the repository
        gateway_name: Gateway name
        method: Payment method
        existing_pr_info: Information about existing PR if any
    Returns:

        Tool configuration dictionary
    """

    # Use standardized branch naming format
    standard_branch_name = f"feature/swe-agent/{gateway_name.lower()}-{method.lower()}-integration"
    if existing_pr_info.get("exists", False):

        # Use existing branch if available, otherwise fall back to standard format
        branch_name = existing_pr_info.get("branch", standard_branch_name)
        if existing_pr_info.get("pr_url"):

            # Existing PR - update it
            commit_message = f"Update {gateway_name} gateway integration for {method} payments - iteration {state['current_iteration']}"
            pr_title = f"Update {gateway_name} Gateway Integration for {method} Payments"
            pr_description = f"This PR continues the integration of {gateway_name} gateway with {method} payment method.\n\nIteration: {state['current_iteration']}\nExisting PR: {existing_pr_info.get('pr_url', 'N/A')}"
        else:

            # Existing branch but no PR - create PR
            commit_message = f"Add {gateway_name} gateway integration for {method} payments"
            pr_title = f"Integrate {gateway_name} Gateway for {method} Payments"
            pr_description = f"This PR adds support for {gateway_name} gateway with {method} payment method.\n\nUsing existing branch: {branch_name}"
    else:

        # Create new branch with standard naming
        branch_name = standard_branch_name
        commit_message = f"Add {gateway_name} gateway integration for {method} payments"
        pr_title = f"Integrate {gateway_name} Gateway for {method} Payments"
        pr_description = f"This PR adds support for {gateway_name} gateway with {method} payment method."
    return {
        "task_description": f"Integrate {gateway_name} gateway in {repo_name} repository",
        "repository_url": state["repositories"][repo_name],
        "branch_name": branch_name,
        "commit_message": commit_message,
        "pr_title": pr_title,
        "pr_description": pr_description,
        "existing_pr": existing_pr_info,
        "standard_branch_name": standard_branch_name  # Pass this to the agent prompt
    }