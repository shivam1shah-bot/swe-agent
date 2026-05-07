"""
Base classes for E2E onboarding workflow steps.

Provides common functionality and patterns for sequential workflow steps.
"""

import logging
import re
import requests
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any

from src.agents import AutonomousAgentTool
from src.providers.config_loader import get_config
from src.providers.http.client import http_request
from src.providers.telemetry import get_meter, is_metrics_initialized
from ..state import E2EOnboardingState
from ..helper import extract_pr_url, prepare_e2e_config, generate_branch_name, log_behavior
from ..config import RepositoryConfig

logger = logging.getLogger(__name__)

# Lazy initialization of workflow stage metrics
_workflow_metrics_meter = None
_workflow_stage_invocations = None
_workflow_stage_duration = None


def _get_workflow_stage_metrics():
    """Lazy initialization of workflow stage metrics."""
    global _workflow_metrics_meter, _workflow_stage_invocations, _workflow_stage_duration
    
    if _workflow_stage_invocations is not None:
        return _workflow_stage_invocations, _workflow_stage_duration
    
    if not is_metrics_initialized():
        return None, None
    
    try:
        _workflow_metrics_meter = get_meter("workflow")
        _workflow_stage_invocations = _workflow_metrics_meter.create_counter(
            "stage_invocations_total",
            "Total number of workflow stage invocations",
            labelnames=("agent_name", "stage_name", "status")
        )
        _workflow_stage_duration = _workflow_metrics_meter.create_histogram(
            "stage_duration_seconds",
            "Workflow stage execution duration in seconds",
            labelnames=("agent_name", "stage_name", "status"),
            buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, float('inf'))
        )
    except Exception as e:
        logger.error(f"Failed to initialize workflow stage metrics: {e}", exc_info=True)
        return None, None
    
    return _workflow_stage_invocations, _workflow_stage_duration

class BaseWorkflowStep(ABC):
    """Base class for workflow steps."""
    
    @abstractmethod
    async def execute(self, state: E2EOnboardingState) -> E2EOnboardingState:
        """Execute the workflow step."""
        pass


class BaseRepositoryStep(BaseWorkflowStep):
    """
    Base class for repository processing steps.
    
    Handles common logic for sequential repository processing.
    """
    
    def __init__(self, repository_name: str):
        self.repository_name = repository_name
    
    @abstractmethod
    def get_prompt(self, state: E2EOnboardingState, branch_name: str, existing_pr_info: Dict[str, Any]) -> str:
        """Generate the prompt for this repository step."""
        pass
    
    async def execute(self, state: E2EOnboardingState) -> E2EOnboardingState:
        """
        Execute repository processing step sequentially.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated workflow state
        """
        agent_name = "e2e-onboarding"
        stage_name = self.repository_name
        stage_start = time.time()
        task_id = state.get("task_id", "unknown")
        service = state.get("service", "unknown")
        logger.info(f"[FLOW] Starting execute method for {self.repository_name} - task_id: {task_id}, service: {service}")
        
        try:
            is_step_execution_allowed = await self._is_step_execution_allowed(self.repository_name, state)
            if not is_step_execution_allowed:
                logger.info(f"[FLOW] Input parameters for use_ephemeral_db is {state.get('input_parameters', {})}")
                logger.info(f"[FLOW] Validate step execution failed, skipping {self.repository_name} repository processing")
                logger.info(f"[FLOW] Returning state")
                
                # Log current state for debugging
                logger.info(f"[FLOW] Completed steps: {state.get('completed_steps', [])}")
                logger.info(f"[FLOW] Failed steps: {state.get('failed_steps', [])}")
                logger.info(f"[FLOW] Step results: {state.get('step_results', {})}")
                logger.info(f"[FLOW] Repositories: {state.get('repositories', {})}")
                logger.info(f"[FLOW] Current step: {state.get('current_step', 'unknown')}")
                
                # Remove repository from repositories to track processing
                if self.repository_name in state.get("repositories", {}):
                    del state["repositories"][self.repository_name]
                    logger.info(f"[FLOW] Removed {self.repository_name} from repositories")
                
                # Mark as skipped in step results
                state["step_results"][self.repository_name] = {
                    "skipped": True,
                    "reason": "Step execution not allowed due to use_ephemeral_db is False",
                    "timestamp": None,
                    "error": None
                }
                logger.info(f"[FLOW] Marked {self.repository_name} as skipped in step_results")
                
                return state

            log_behavior(task_id, f"Repository Step Started: {self.repository_name}", 
                        f"Starting {self.repository_name} repository processing for service {service}")
            logger.info(f"Starting {self.repository_name} repository processing")
            logger.info(f"[FLOW] Called log_behavior for repository step start")
            
            branch_name = generate_branch_name(state["service"])
            logger.info(f"[FLOW] Generated branch name: {branch_name}")
            log_behavior(task_id, f"Branch Name Generated: {self.repository_name}", 
                        f"Using branch name: {branch_name}")
            logger.info(f"[FLOW] Called log_behavior for branch name generation")
            
            # Check for existing branch/PR
            existing_pr_info = await self.check_existing_pr(state, branch_name)
            logger.info(f"[FLOW] Checked existing PR - result: {existing_pr_info}")
            
            if existing_pr_info.get("exists", False):
                log_behavior(task_id, f"Existing PR Found: {self.repository_name}", 
                           f"Found existing PR/branch for {self.repository_name}: {existing_pr_info.get('pr_url', 'branch only')}")
                logger.info(f"[FLOW] Found existing PR/branch, called log_behavior")
            else:
                log_behavior(task_id, f"No Existing PR: {self.repository_name}", 
                           f"No existing PR found for {self.repository_name}, will create new")
                logger.info(f"[FLOW] No existing PR found, called log_behavior")
            
            e2e_config = prepare_e2e_config(
                service=state["service"],
                repo_name=self.repository_name,
                branch_info={
                    "branch_name": branch_name,
                    "has_existing_work": existing_pr_info.get("exists", False)
                },
            )
            logger.info(f"[FLOW] Prepared e2e_config: {e2e_config}")
            
            # Get or create agent with state persistence
            is_retry = state.get("current_iteration", 0) > 0
            action_type = "Re-executing" if is_retry else "Executing"
            logger.info(f"[FLOW] Determined retry status: is_retry={is_retry}, action_type={action_type}")
            log_behavior(task_id, f"Agent {action_type}: {self.repository_name}", 
                        f"{action_type} autonomous agent for {self.repository_name} (retry: {is_retry})")
            logger.info(f"[FLOW] Called log_behavior for agent execution")
            
            agent_tool = self._get_agent_instance(
                repo_name=self.repository_name,
                tool_config=e2e_config,
                is_retry=is_retry
            )
            logger.info(f"[FLOW] Got agent instance: {type(agent_tool).__name__}")

            prompt = self.get_prompt(state, branch_name, existing_pr_info)
            logger.info(f"[FLOW] Generated prompt (length: {len(prompt)} chars)")
            
            result = agent_tool.execute({
                "prompt": prompt,
                "task_id": state['task_id'],
                "agent_name": agent_name  # For Claude metrics tracking
            })
            logger.info(f"[FLOW] Agent execution completed - result: {result}")
            
            self._process_result(state, result, e2e_config)
            logger.info(f"[FLOW] Processed result - state updated")
            
            log_behavior(task_id, f"Repository Step Completed: {self.repository_name}", 
                        f"Completed {self.repository_name} repository processing")
            logger.info(f"Completed {self.repository_name} repository processing")
            logger.info(f"[FLOW] Execute method completed successfully for {self.repository_name}")
            
            # Determine actual success from result (not just absence of exception)
            step_result = state.get("step_results", {}).get(self.repository_name, {})
            actual_success = step_result.get("success", False)
            
            # Record metrics based on actual success status
            stage_duration = time.time() - stage_start
            status = "success" if actual_success else "failed"
            invocations, duration = _get_workflow_stage_metrics()
            if invocations is not None:
                invocations.labels(
                    agent_name=agent_name,
                    stage_name=stage_name,
                    status=status
                ).inc()
            if duration is not None:
                duration.labels(
                    agent_name=agent_name,
                    stage_name=stage_name,
                    status=status
                ).observe(stage_duration)
            
            return state
            
        except Exception as e:
            error_msg = f"Failed to process {self.repository_name} repository: {str(e)}"
            logger.error(f"[FLOW] Exception caught in execute method: {error_msg}")
            log_behavior(task_id, f"Repository Step Failed: {self.repository_name}", error_msg)
            logger.error(error_msg)
            logger.info(f"[FLOW] Called log_behavior for repository step failure")
            self._handle_error(state, e)
            logger.info(f"[FLOW] Called _handle_error method")
            
            # Record metrics for failed stage
            stage_duration = time.time() - stage_start
            status = "failed"
            invocations, duration = _get_workflow_stage_metrics()
            if invocations is not None:
                invocations.labels(
                    agent_name=agent_name,
                    stage_name=stage_name,
                    status=status
                ).inc()
            if duration is not None:
                duration.labels(
                    agent_name=agent_name,
                    stage_name=stage_name,
                    status=status
                ).observe(stage_duration)
            
            return state
    
    def _get_agent_instance(
        self,
        repo_name: str,
        tool_config: Dict[str, Any],
        is_retry: bool = False
    ) -> "AutonomousAgentTool":
        """
        Get an agent for a specific repository, maintaining state across calls.

        Args:
            repo_name: Name of the repository
            tool_config: Configuration for the tool
            is_retry: Whether this is a retry operation

        Returns:
            AutonomousAgent instance
        """
        logger.info(f"[FLOW] Entering _get_agent_instance for {repo_name} (retry: {is_retry})")
        
        # Create new agent instance
        logger.info(f"Creating new agent for {repo_name} (retry: {is_retry})")
        from src.agents.autonomous_agent import AutonomousAgentTool
        logger.info(f"[FLOW] Imported AutonomousAgentTool")
        
        agent = AutonomousAgentTool(config=tool_config)
        logger.info(f"[FLOW] Created AutonomousAgentTool instance with config keys: {list(tool_config.keys()) if tool_config else 'None'}")

        return agent
    
    def _process_result(
        self, 
        state: E2EOnboardingState, 
        result: Dict[str, Any], 
        e2e_config: Dict[str, Any]
    ) -> None:
        """Process the result of agent execution."""
        task_id = state.get("task_id", "unknown")
        logger.info(f"[FLOW] Entering _process_result for {self.repository_name}")
        
        pr_url = extract_pr_url(state, result, self.repository_name)
        logger.info(f"[FLOW] Extracted PR URL: {pr_url}")
        # Determine success based on result
        success = result.get("success", False) and pr_url is not None
        logger.info(f"[FLOW] Determined success status: {success} (result.success={result.get('success')}, pr_url_exists={pr_url is not None})")
        
        # Create result entry
        result_data = {
            "success": success,
            "pr_url": pr_url,
            "commit_hash": result.get("commit_hash"),
            "branch_name": e2e_config.get("branch_name"),
            "timestamp": result.get("timestamp"),
            "error": None if success else result.get("error", "Unknown error")
        }
        logger.info(f"[FLOW] Created result_data: {result_data}")
        
        # Update state
        state["step_results"][self.repository_name] = result_data
        logger.info(f"[FLOW] Updated state step_results for {self.repository_name}")
        
        if success:
            state["completed_steps"].append(self.repository_name)
            logger.info(f"[FLOW] Added {self.repository_name} to completed_steps")
            log_behavior(task_id, f"PR Created Successfully: {self.repository_name}", 
                        f"Successfully created PR for {self.repository_name}: {pr_url}")
            logger.info(f"Successfully created PR for {self.repository_name}: {pr_url}")
            logger.info(f"[FLOW] Called log_behavior for successful PR creation")
        else:
            state["failed_steps"].append(self.repository_name)
            logger.info(f"[FLOW] Added {self.repository_name} to failed_steps")
            error_msg = result.get("error", "Unknown error occurred")
            log_behavior(task_id, f"PR Creation Failed: {self.repository_name}", 
                        f"Failed to process {self.repository_name}: {error_msg}")
            logger.error(f"Failed to process {self.repository_name}: {error_msg}")
            logger.info(f"[FLOW] Called log_behavior for failed PR creation")
    
    def _handle_error(self, state: E2EOnboardingState, error: Exception) -> None:
        """Handle execution errors."""
        task_id = state.get("task_id", "unknown")
        error_msg = str(error)
        logger.info(f"[FLOW] Entering _handle_error for {self.repository_name} - error: {error_msg}")
        
        log_behavior(task_id, f"Execution Error: {self.repository_name}", 
                    f"Execution error in {self.repository_name}: {error_msg}")
        logger.info(f"[FLOW] Called log_behavior for execution error")
        
        # Update state with error information
        state["failed_steps"].append(self.repository_name)
        logger.info(f"[FLOW] Added {self.repository_name} to failed_steps")
        
        # Create error result
        error_result = {
            "success": False,
            "error": error_msg,
            "timestamp": datetime.now().isoformat(),
            "branch_name": generate_branch_name(state["service"])
        }
        logger.info(f"[FLOW] Created error_result: {error_result}")
        
        state["step_results"][self.repository_name] = error_result
        logger.info(f"[FLOW] Updated state step_results with error for {self.repository_name}")
    
    async def check_github_branch_and_pr(self, repo_url: str, branch_name: str) -> Dict[str, Any]:
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
            # e.g., "https://github.com/razorpay/kubemanifest" -> owner="razorpay", repo="kubemanifest"
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
            github_token = (config.get("github") or {}).get("token")
            if github_token:
                headers["Authorization"] = f"token {github_token}"
                logger.info(f"Using GitHub token for authentication (token length: {len(github_token)})")
            else:
                logger.warning("No GitHub token found in environment variables")
            
            try:
                # Check if branch exists using GitHub API
                branch_url = f"{api_base}/repos/{owner}/{repo}/branches/{branch_name}"
                logger.info(f"Making branch API call to: {branch_url}")
                branch_response = http_request(
                    service="github",
                    operation="e2e-onboarding",
                    endpoint_template="/repos/{owner}/{repo}/branches/{branch}",
                    method="GET",
                    url=branch_url,
                    headers=headers,
                    timeout=10,
                )
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
                prs_response = http_request(
                    service="github",
                    operation="e2e-onboarding",
                    endpoint_template="/repos/{owner}/{repo}/pulls",
                    method="GET",
                    url=prs_url,
                    headers=headers,
                    params=prs_params,
                    timeout=10,
                )
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
    
    async def check_existing_pr(self, state: E2EOnboardingState, branch_name: str) -> Dict[str, Any]:
        """
        Check if there's already an existing branch/PR for this E2E onboarding step.
        
        Args:
            state: The workflow state
            branch_name: Branch name to check
            
        Returns:
            Dictionary with existing PR information or empty dict if none found
        """
        task_id = state["task_id"]
        logger.info(f"[FLOW] Entering check_existing_pr for {self.repository_name} with branch: {branch_name}")
        
        try:
            # Check if manual PR URLs are provided in state (for user-specified existing PRs)
            manual_prs = state.get("existing_prs", {})
            logger.info(f"[FLOW] Checking manual PRs: {manual_prs}")
            if self.repository_name in manual_prs:
                pr_url = manual_prs[self.repository_name]
                logger.info(f"Manual PR found for {self.repository_name}: {pr_url}, Branch: {branch_name}")
                logger.info(f"[FLOW] Returning manual PR result")
                return {
                    "exists": True,
                    "pr_url": pr_url,
                    "branch": branch_name,
                    "from_manual": True
                }
            
            # Check step results for previous PR information
            step_results = state.get("step_results", {})
            logger.info(f"[FLOW] Checking step results: {step_results}")
            if self.repository_name in step_results:
                previous_result = step_results[self.repository_name]
                logger.info(f"[FLOW] Found previous result for {self.repository_name}: {previous_result}")
                if previous_result.get("pr_url") and previous_result.get("branch_name"):
                    logger.info(f"Found existing PR for {self.repository_name}: {previous_result['pr_url']}, Branch: {previous_result['branch_name']}")
                    logger.info(f"[FLOW] Returning previous result")
                    return {
                        "exists": True,
                        "pr_url": previous_result["pr_url"],
                        "branch": previous_result["branch_name"],
                        "from_previous_result": True
                    }
            
            # Get repository URL from config
            repo_url = RepositoryConfig.get_repository_url(self.repository_name, state)
            logger.info(f"[FLOW] Got repository URL from config: {repo_url}")
            if not repo_url:
                logger.warning(f"No repository URL found for {self.repository_name}")
                logger.info(f"[FLOW] No repo URL found, returning exists=False")
                return {"exists": False, "branch": branch_name}
            # Check GitHub for existing branch and PR
            logger.info(f"[FLOW] Calling check_github_branch_and_pr")
            github_result = await self.check_github_branch_and_pr(repo_url, branch_name)
            logger.info(f"[FLOW] GitHub check result: {github_result}")
            
            if github_result.get("pr_exists", False):
                logger.info(f"GitHub PR found for {self.repository_name}: {github_result['pr_url']}, Branch: {github_result['branch']}")
                logger.info(f"[FLOW] Returning GitHub PR result")
                return {
                    "exists": True,
                    "pr_url": github_result["pr_url"],
                    "branch": github_result["branch"],
                    "pr_number": github_result.get("pr_number"),
                    "pr_title": github_result.get("pr_title"),
                    "from_github": True
                }
            elif github_result.get("branch_exists", False):
                logger.info(f"GitHub branch found for {self.repository_name}: Branch exists but no PR: {github_result['branch']}")
                logger.info(f"[FLOW] Returning GitHub branch-only result")
                return {
                    "exists": True,
                    "pr_url": None,
                    "branch": github_result["branch"],
                    "branch_only": True,
                    "from_github": True
                }
            
            logger.info(f"No existing PR/branch found for {self.repository_name}. Will create new branch: {branch_name}")
            logger.info(f"[FLOW] No existing PR/branch found, returning exists=False")
            return {"exists": False, "branch": branch_name}
            
        except Exception as e:
            logger.exception(f"Error checking existing PR for {self.repository_name}: {e}")
            logger.info(f"[FLOW] Exception in check_existing_pr: {str(e)}")
            # Still return the branch name for creation
            return {"exists": False, "error": str(e), "branch": branch_name}

    async def _is_step_execution_allowed(self, repository_name: str, state: E2EOnboardingState) -> bool:
        """Validate if the step should be executed."""
        logger.info(f"[FLOW] Checking if step execution is allowed for {repository_name}")
        logger.info(f"[FLOW] Input parameters: {state.get('input_parameters', {})}")
        # Default behavior: allow execution for all steps
        # Individual step classes can override this method for custom validation
        return True
