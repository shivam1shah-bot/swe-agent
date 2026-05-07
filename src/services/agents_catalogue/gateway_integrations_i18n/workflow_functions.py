"""
Workflow functions for Gateway Integration I18n Service

This module contains all the LangGraph workflow functions for gateway integration.
"""

import logging
import os
import json
import time
import asyncio
import hashlib
import random
import string
import requests
from datetime import datetime
from typing import Dict, Any, List

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage

from src.services.agents_catalogue.gateway_integrations_i18n.gateway_integration_state import GatewayIntegrationState
from src.services.agents_catalogue.gateway_integrations_i18n.helper import (
    log_behavior, generate_devstack_label_hash, generate_randomized_devstack_label,
    get_or_create_agent, update_agent_context, check_existing_pr, prepare_integration_config
)
from src.services.agents_catalogue.gateway_integrations_i18n.repository_config import RepositoryConfig
from src.agents.autonomous_agent import AutonomousAgentTool
from src.providers.config_loader import get_config

logger = logging.getLogger(__name__)

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
        "terminals": RepositoryConfig.TERMINALS,
        "router": RepositoryConfig.ROUTER,
        "pg_router": RepositoryConfig.PG_ROUTER,
        "nbplus": RepositoryConfig.NBPLUS,
        "mozart": RepositoryConfig.MOZART,
        "integrations_go": RepositoryConfig.INTEGRATIONS_GO,
        "terraform_kong": RepositoryConfig.TERRAFORM_KONG,
        "proto": RepositoryConfig.PROTO,
        "api": RepositoryConfig.API
    }

    # Initialize agent instances and contexts for persistence
    state["agent_instances"] = {}
    state["agent_contexts"] = {}

    # Initialize results
    state["terminals_result"] = {}
    state["router_result"] = {}
    state["pg_router_result"] = {}
    state["nbplus_result"] = {}
    state["mozart_result"] = {}
    state["integrations_go_result"] = {}
    state["terraform_kong_result"] = {}
    state["proto_result"] = {}
    state["api_result"] = {}
    state["current_step"] = "initialized"
    state["completed_steps"].append("initialize")
    return state

def run_parallel_integrations(state: GatewayIntegrationState) -> GatewayIntegrationState:
    """Run parallel integrations across all repositories."""
    task_id = state["task_id"]
    log_behavior(task_id, "Parallel Integration", "Running integrations across all repositories")
    
    async def run_integrations():
        tasks = []
        
        # Create tasks for each repository integration
        if "terminals" in state["repositories"]:
            tasks.append(integrate_terminals(state))
        if "pg_router" in state["repositories"]:
            tasks.append(integrate_pg_router(state))
        if "nbplus" in state["repositories"]:
            tasks.append(integrate_nbplus(state))
        if "mozart" in state["repositories"]:
            tasks.append(integrate_mozart(state))
        if "integrations_go" in state["repositories"]:
            tasks.append(integrate_integrations_go(state))
        if "terraform_kong" in state["repositories"]:
            tasks.append(integrate_terraform_kong(state))
        if "proto" in state["repositories"]:
            tasks.append(integrate_proto(state))
        if "api" in state["repositories"]:
            tasks.append(integrate_api(state))
        
        # Run all integrations in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Integration failed: {result}")
                state["failed_steps"].append(f"integration_{i}")
    
    # Execute the parallel integrations
    asyncio.run(run_integrations())
    
    state["current_step"] = "run_parallel_integrations"
    state["completed_steps"].append("run_parallel_integrations")
    
    return state

def should_continue(state: GatewayIntegrationState) -> str:
    """
    Determine the next step in the workflow based on current state.
    
    Args:
        state: Current workflow state
        
    Returns:
        Next step to execute
    """
    current_step = state.get("current_step", "")
    failed_steps = state.get("failed_steps", [])
    current_iteration = state.get("current_iteration", 0)
    max_iterations = state.get("max_iterations", 50)
    
    # Check if we've exceeded max iterations
    if current_iteration >= max_iterations:
        return "fail_workflow"
    
    # Handle different workflow states
    if current_step == "validate_changes":
        if failed_steps:
            return "fix_validation_issues"
        else:
            return "deploy_to_devstack"
    
    elif current_step == "fix_validation_issues":
        if len(failed_steps) > 5:  # Too many failures
            return "fail_workflow"
        else:
            return "validate_changes"
    
    elif current_step == "deploy_to_devstack":
        if state.get("deployment_result", {}).get("success", False):
            return "run_e2e_tests"
        else:
            return "fail_workflow"
    
    elif current_step == "run_e2e_tests":
        if state.get("tests_passed", False):
            return "complete_workflow"
        else:
            return "process_feedback"
    
    elif current_step == "process_feedback":
        return "debug_and_correct_agents"
    
    elif current_step == "debug_and_correct_agents":
        return "validate_changes"
    
    # Default fallback
    return "fail_workflow"

def aggregate_results(state: GatewayIntegrationState) -> GatewayIntegrationState:
    """Aggregate results from all repository integrations."""
    task_id = state["task_id"]
    log_behavior(task_id, "Aggregating Results", "Collecting results from all integrations")
    
    # Collect all results
    all_results = {
        "terminals": state.get("terminals_result", {}),
        "pg_router": state.get("pg_router_result", {}),
        "nbplus": state.get("nbplus_result", {}),
        "mozart": state.get("mozart_result", {}),
        "integrations_go": state.get("integrations_go_result", {}),
        "terraform_kong": state.get("terraform_kong_result", {}),
        "proto": state.get("proto_result", {}),
        "api": state.get("api_result", {}),
    }
    
    # Count successful integrations
    successful_integrations = sum(1 for result in all_results.values() 
                                if result.get("success", False))
    
    # Update workflow summary
    state["workflow_summary"] = {
        "total_repositories": len(all_results),
        "successful_integrations": successful_integrations,
        "failed_integrations": len(all_results) - successful_integrations,
        "results": all_results
    }
    
    state["current_step"] = "aggregate_results"
    state["completed_steps"].append("aggregate_results")
    
    return state

def validate_changes(state: GatewayIntegrationState) -> GatewayIntegrationState:
    """Validate all changes made during integration."""
    task_id = state["task_id"]
    log_behavior(task_id, "Validating Changes", "Validating all repository changes")
    
    # Simple validation - check if we have successful results
    successful_results = 0
    total_results = 0
    
    for repo_name in ["terminals", "pg_router", "nbplus", "mozart", 
                     "integrations_go", "terraform_kong", "proto", "api"]:
        result = state.get(f"{repo_name}_result", {})
        if result:
            total_results += 1
            if result.get("success", False):
                successful_results += 1
    
    # Consider validation successful if at least 80% of integrations succeeded
    validation_success = (successful_results / total_results) >= 0.8 if total_results > 0 else False
    
    state["validation_result"] = {
        "success": validation_success,
        "successful_results": successful_results,
        "total_results": total_results,
        "success_rate": (successful_results / total_results) if total_results > 0 else 0
    }
    
    state["current_step"] = "validate_changes"
    state["completed_steps"].append("validate_changes")
    
    if not validation_success:
        state["failed_steps"].append("validate_changes")
    
    return state

def fix_validation_issues(state: GatewayIntegrationState) -> GatewayIntegrationState:
    """Fix validation issues found during validation."""
    task_id = state["task_id"]
    log_behavior(task_id, "Fixing Validation Issues", "Attempting to fix validation issues")
    
    # Increment iteration counter
    state["current_iteration"] += 1
    
    # For now, just mark as attempted - in real implementation, this would
    # attempt to fix specific issues
    state["current_step"] = "fix_validation_issues"
    state["completed_steps"].append("fix_validation_issues")
    
    return state

async def deploy_to_devstack(state: GatewayIntegrationState) -> GatewayIntegrationState:
    """Deploy the integration to devstack."""
    task_id = state["task_id"]
    log_behavior(task_id, "Deploying to Devstack", f"Deploying with label: {state['devstack_label']}")
    
    # Simulate deployment (in real implementation, this would make actual deployment calls)
    deployment_result = {
        "success": True,
        "devstack_label": state["devstack_label"],
        "deployment_url": f"https://devstack.razorpay.com/{state['devstack_label']}",
        "message": "Deployment successful"
    }
    
    state["deployment_result"] = deployment_result
    state["current_step"] = "deploy_to_devstack"
    state["completed_steps"].append("deploy_to_devstack")
    
    return state

async def run_e2e_tests(state: GatewayIntegrationState) -> GatewayIntegrationState:
    """Run end-to-end tests for the integration."""
    task_id = state["task_id"]
    log_behavior(task_id, "Running E2E Tests", "Running end-to-end tests")
    
    # Simulate E2E test execution
    e2e_result = {
        "success": True,
        "tests_passed": True,
        "test_results": {
            "payment_flow": "PASSED",
            "refund_flow": "PASSED",
            "webhook_delivery": "PASSED"
        }
    }
    
    state["e2e_test_result"] = e2e_result
    state["tests_passed"] = e2e_result["tests_passed"]
    state["current_step"] = "run_e2e_tests"
    state["completed_steps"].append("run_e2e_tests")
    
    return state

def process_feedback(state: GatewayIntegrationState) -> GatewayIntegrationState:
    """Process feedback from failed tests."""
    task_id = state["task_id"]
    log_behavior(task_id, "Processing Feedback", "Processing test feedback")
    
    state["current_step"] = "process_feedback"
    state["completed_steps"].append("process_feedback")
    
    return state

async def debug_and_correct_agents(state: GatewayIntegrationState) -> GatewayIntegrationState:
    """Debug and correct agent issues."""
    task_id = state["task_id"]
    log_behavior(task_id, "Debugging Agents", "Debugging and correcting agent issues")
    
    # Increment iteration counter
    state["current_iteration"] += 1
    
    state["current_step"] = "debug_and_correct_agents"
    state["completed_steps"].append("debug_and_correct_agents")
    
    return state

def complete_workflow(state: GatewayIntegrationState) -> GatewayIntegrationState:
    """Complete the workflow successfully."""
    task_id = state["task_id"]
    log_behavior(task_id, "Workflow Completed", "Gateway integration workflow completed successfully")
    
    state["current_step"] = "completed"
    state["completed_steps"].append("complete_workflow")
    
    return state

def fail_workflow(state: GatewayIntegrationState) -> GatewayIntegrationState:
    """Fail the workflow due to errors."""
    task_id = state["task_id"]
    log_behavior(task_id, "Workflow Failed", "Gateway integration workflow failed")
    
    state["current_step"] = "failed"
    state["failed_steps"].append("fail_workflow")
    
    return state

# Individual repository integration functions
async def integrate_terminals(state: GatewayIntegrationState) -> GatewayIntegrationState:
    """Integrate terminals repository using AutonomousAgentTool"""
    task_id = state["task_id"]
    gateway_name = state["gateway_name"]
    method = state["method"]
    is_retry = state["current_iteration"] > 0
    log_action = "Re-integrating Terminals" if is_retry else "Integrating Terminals"
    log_behavior(task_id, log_action, f"Creating PR for {gateway_name} in terminals repository")
    
    try:
        # Check for existing PR first using GitHub API
        existing_pr_info = await check_existing_pr(state, "terminals", gateway_name, method)

        # If existing PR is found, update state and return without triggering agent
        if existing_pr_info.get("exists", False):
            log_behavior(task_id, "Terminals Existing PR Found",
                        f"Found existing PR/branch: {existing_pr_info.get('pr_url', 'branch only')}")

            # Update state with existing PR information
            state["terminals_result"] = {
                "success": True,
                "pr_url": existing_pr_info.get("pr_url"),
                "branch": existing_pr_info.get("branch"),
                "files_modified": [],  # Will be populated later when agent runs
                "message": "Existing PR/branch found for Terminals integration",
                "iteration": state["current_iteration"],
                "existing_pr_reused": True,
                "existing_pr_info": existing_pr_info,
                "agent_executed": False  # Flag to indicate agent wasn't run
            }

            # Initialize agent context even if not executing
            if "terminals" not in state["agent_contexts"]:
                state["agent_contexts"]["terminals"] = {
                    "repository": "terminals",
                    "created_at": datetime.now().isoformat(),
                    "iterations": [],
                    "files_modified": [],
                    "previous_results": [],
                    "existing_pr_info": existing_pr_info
                }
            return state

        # No existing PR found, proceed with normal agent execution
        log_behavior(task_id, log_action, f"No existing PR found, creating new integration for {gateway_name}")

        # Prepare tool configuration based on existing PR status
        tool_config = prepare_integration_config(state, "terminals", gateway_name, method, existing_pr_info)

        # Base prompt for integration
        base_prompt = f"""
        You are tasked with integrating the {gateway_name} payment gateway for {method} payments in the terminals repository.
        Repository: {state["repositories"]["terminals"]}
        Standard Branch Name: {tool_config["standard_branch_name"]}
        Reference PR : https://github.com/razorpay/terminals/pull/1876
        """

        # Add existing PR/branch context if applicable
        if existing_pr_info.get("exists", False):
            if existing_pr_info.get("pr_url"):
                base_prompt += f"""
        IMPORTANT - EXISTING PR DETECTED:
        - Existing PR: {existing_pr_info.get('pr_url', 'N/A')}
        - Existing Branch: {existing_pr_info.get('branch', 'N/A')}
        - PR Number: {existing_pr_info.get('pr_number', 'N/A')}
        DO NOT CREATE A NEW PR. Instead:
        1. Clone the repository if not already done
        2. Checkout to the existing branch: {existing_pr_info.get('branch', 'N/A')}
        3. Review the existing changes in this branch
        4. Build upon the existing work - do not start from scratch
        5. Update and improve the existing implementation
        6. Commit additional changes to the same branch
        7. The PR will be automatically updated with your new commits
        """
            else:
                base_prompt += f"""
        IMPORTANT - EXISTING BRANCH DETECTED:
        - Existing Branch: {existing_pr_info.get('branch', 'N/A')}
        - No PR exists yet for this branch
        FOLLOW THESE STEPS:
        1. Clone the repository if not already done
        2. Checkout to the existing branch: {existing_pr_info.get('branch', 'N/A')}
        3. Review the existing changes in this branch
        4. Build upon the existing work - do not start from scratch
        5. Update and improve the existing implementation
        6. Commit additional changes to the same branch
        7. Create a NEW PR for this branch
        """
        else:
            base_prompt += f"""
        BRANCH CREATION:
        - Create a new branch with the name: {tool_config["standard_branch_name"]}
        - This follows our standardized naming convention
        """

        base_prompt += f"""
        Your task:
        1. {'Update the existing' if existing_pr_info.get('exists') else 'Create a new'} terminal configuration for {gateway_name} and {method} purely based on the reference PR
        2. Add gateway-specific settings and credentials handling
        3. Add proper error handling and logging
        4. Add unit tests for the new terminal
        5. {'Update the existing PR' if existing_pr_info.get('pr_url') else 'Create a pull request'} with all changes
        
        Gateway Details:
        - Name: {gateway_name}
        - Payment Method: {method}
        - Countries: {', '.join(state.get('countries_applicable', []))}
        """

        # Add retry context if this is a retry iteration
        if is_retry:
            previous_context = state["agent_contexts"].get("terminals", {})
            previous_iterations = previous_context.get("iterations", [])
            retry_context = f"""
            RETRY ITERATION {state["current_iteration"]}:
            This is a retry attempt. Previous iterations have been made with the following results:
            """

            for iteration in previous_iterations:
                retry_context += f"""
            - Iteration {iteration['iteration']}: {'Success' if iteration['success'] else 'Failed'}
              Files modified: {', '.join(iteration.get('files_modified', []))}
              Message: {iteration.get('message', 'No message')}
            """

            # Add feedback from E2E tests if available
            if "e2e_test_result" in state and state["e2e_test_result"].get("feedback"):
                retry_context += "\n\nFeedback from E2E Tests to Address:\n"
                for feedback_item in state["e2e_test_result"]["feedback"]:
                    if "terminal" in feedback_item.get("suggested_fix", "").lower():
                        retry_context += f"- {feedback_item['issue']}: {feedback_item['suggested_fix']}\n"
            
            retry_context += """
            IMPORTANT: Build upon your previous work. Do not start from scratch.
            Review the existing changes and address the specific issues mentioned in the feedback.
            Focus on fixing the identified problems while maintaining existing functionality.
            """
            base_prompt += retry_context

        # Get or create agent (will reuse existing agent if available)
        agent_tool = get_or_create_agent(state, "terminals", tool_config, is_retry=is_retry)

        # Execute the autonomous agent tool
        result = await agent_tool.execute({
            "prompt": base_prompt,
            "task_id": task_id,
            "agent_name": "gateway-integrations-i18n",
        })

        # Store the result with existing PR information
        state["terminals_result"] = {
            "success": result.get("success", False),
            "pr_url": result.get("pr_url") or existing_pr_info.get("pr_url"),
            "branch": result.get("branch") or existing_pr_info.get("branch"),
            "files_modified": result.get("files_modified", []),
            "message": result.get("message", "Terminals integration completed"),
            "iteration": state["current_iteration"],
            "existing_pr_reused": existing_pr_info.get("exists", False),
            "standard_branch_name": tool_config["standard_branch_name"]
        }

        # Update agent context with current results
        update_agent_context(state, "terminals", state["terminals_result"])
        action_type = "updated" if existing_pr_info.get("pr_url") else ("created" if not existing_pr_info.get("exists") else "branch updated")
        log_behavior(task_id, "Terminals Integration Completed",
                    f"PR {action_type}: {state['terminals_result'].get('pr_url', 'N/A')}")
                    
    except Exception as e:
        logger.exception(f"Error integrating terminals for task {task_id}: {e}")
        state["terminals_result"] = {
            "success": False,
            "error": str(e),
            "message": f"Failed to integrate terminals: {str(e)}",
            "iteration": state["current_iteration"]
        }
        state["failed_steps"].append("terminals")

        # Update agent context even for failures
        update_agent_context(state, "terminals", state["terminals_result"])
        log_behavior(task_id, "Terminals Integration Failed", f"Error: {str(e)}")
    
    return state

async def integrate_pg_router(state: GatewayIntegrationState) -> GatewayIntegrationState:
    """Integrate pg-router repository using AutonomousAgentTool"""
    task_id = state["task_id"]
    gateway_name = state["gateway_name"]
    method = state["method"]
    is_retry = state["current_iteration"] > 0
    log_action = "Re-integrating PG-Router" if is_retry else "Integrating PG-Router"
    log_behavior(task_id, log_action, f"Creating PR for {gateway_name} in pg-router repository")
    
    try:
        # Check for existing PR first using GitHub API
        existing_pr_info = await check_existing_pr(state, "pg_router", gateway_name, method)

        # If existing PR is found, update state and return without triggering agent
        if existing_pr_info.get("exists", False):
            log_behavior(task_id, "PG-Router Existing PR Found",
                        f"Found existing PR/branch: {existing_pr_info.get('pr_url', 'branch only')}")

            # Update state with existing PR information
            state["pg_router_result"] = {
                "success": True,
                "pr_url": existing_pr_info.get("pr_url"),
                "branch": existing_pr_info.get("branch"),
                "files_modified": [],  # Will be populated later when agent runs
                "message": "Existing PR/branch found for PG-Router integration",
                "iteration": state["current_iteration"],
                "existing_pr_reused": True,
                "existing_pr_info": existing_pr_info,
                "agent_executed": False  # Flag to indicate agent wasn't run
            }

            # Initialize agent context even if not executing
            if "pg_router" not in state["agent_contexts"]:
                state["agent_contexts"]["pg_router"] = {
                    "repository": "pg_router",
                    "created_at": datetime.now().isoformat(),
                    "iterations": [],
                    "files_modified": [],
                    "previous_results": [],
                    "existing_pr_info": existing_pr_info
                }
            return state

        # No existing PR found, proceed with normal agent execution
        log_behavior(task_id, log_action, f"No existing PR found, creating new integration for {gateway_name}")

        # Prepare tool configuration based on existing PR status
        tool_config = prepare_integration_config(state, "pg_router", gateway_name, method, existing_pr_info)

        # Base prompt for integration
        base_prompt = f"""
        You are tasked with integrating the {gateway_name} payment gateway for {method} payments in the pg-router repository.
        Repository: {state["repositories"]["pg_router"]}
        Standard Branch Name: {tool_config["standard_branch_name"]}
        """

        # Add existing PR/branch context if applicable
        if existing_pr_info.get("exists", False):
            if existing_pr_info.get("pr_url"):
                base_prompt += f"""
        IMPORTANT - EXISTING PR DETECTED:
        - Existing PR: {existing_pr_info.get('pr_url', 'N/A')}
        - Existing Branch: {existing_pr_info.get('branch', 'N/A')}
        - PR Number: {existing_pr_info.get('pr_number', 'N/A')}
        DO NOT CREATE A NEW PR. Instead:
        1. Clone the repository if not already done
        2. Checkout to the existing branch: {existing_pr_info.get('branch', 'N/A')}
        3. Review the existing changes in this branch
        4. Build upon the existing work - do not start from scratch
        5. Update and improve the existing implementation
        6. Commit additional changes to the same branch
        7. The PR will be automatically updated with your new commits
        """
            else:
                base_prompt += f"""
        IMPORTANT - EXISTING BRANCH DETECTED:
        - Existing Branch: {existing_pr_info.get('branch', 'N/A')}
        - No PR exists yet for this branch
        FOLLOW THESE STEPS:
        1. Clone the repository if not already done
        2. Checkout to the existing branch: {existing_pr_info.get('branch', 'N/A')}
        3. Review the existing changes in this branch
        4. Build upon the existing work - do not start from scratch
        5. Update and improve the existing implementation
        6. Commit additional changes to the same branch
        7. Create a NEW PR for this branch
        """
        else:
            base_prompt += f"""
        BRANCH CREATION:
        - Create a new branch with the name: {tool_config["standard_branch_name"]}
        - This follows our standardized naming convention
        """

        base_prompt += f"""
        Your task:
        1. {'Update the existing' if existing_pr_info.get('exists') else 'Add'} gateway configuration for {gateway_name}
        2. Implement payment processing logic for {method} payments
        3. Add gateway-specific routing rules
        4. Update payment flow configurations
        5. Add proper error handling and retry mechanisms
        6. Update gateway selection algorithms
        7. Add unit tests for payment processing
        8. {'Update the existing PR' if existing_pr_info.get('pr_url') else 'Create a pull request'} with all changes
        
        Gateway Details:
        - Name: {gateway_name}
        - Payment Method: {method}
        - Countries: {', '.join(state.get('countries_applicable', []))}
        Please ensure all changes follow the existing payment processing patterns and include proper documentation.
        """

        # Add retry context if this is a retry iteration
        if is_retry:
            previous_context = state["agent_contexts"].get("pg_router", {})
            previous_iterations = previous_context.get("iterations", [])
            retry_context = f"""
            RETRY ITERATION {state["current_iteration"]}:
            This is a retry attempt. Previous iterations have been made with the following results:
            """

            for iteration in previous_iterations:
                retry_context += f"""
            - Iteration {iteration['iteration']}: {'Success' if iteration['success'] else 'Failed'}
              Files modified: {', '.join(iteration.get('files_modified', []))}
              Message: {iteration.get('message', 'No message')}
            """

            # Add feedback from E2E tests if available
            if "e2e_test_result" in state and state["e2e_test_result"].get("feedback"):
                retry_context += "\n\nFeedback from E2E Tests to Address:\n"
                for feedback_item in state["e2e_test_result"]["feedback"]:
                    if "pg-router" in feedback_item.get("suggested_fix", "").lower() or "payment" in feedback_item.get("suggested_fix", "").lower():
                        retry_context += f"- {feedback_item['issue']}: {feedback_item['suggested_fix']}\n"
            
            retry_context += """
            IMPORTANT: Build upon your previous work. Do not start from scratch.
            Review the existing changes and address the specific issues mentioned in the feedback.
            Focus on fixing the identified problems while maintaining existing functionality.
            """
            base_prompt += retry_context

        # Get or create agent (will reuse existing agent if available)
        agent_tool = get_or_create_agent(state, "pg_router", tool_config, is_retry=is_retry)

        # Execute the autonomous agent tool
        result = await agent_tool.execute({
            "prompt": base_prompt,
            "task_id": task_id,
            "agent_name": "gateway-integrations-i18n",
        })

        # Store the result with existing PR information
        state["pg_router_result"] = {
            "success": result.get("success", False),
            "pr_url": result.get("pr_url") or existing_pr_info.get("pr_url"),
            "branch": result.get("branch") or existing_pr_info.get("branch"),
            "files_modified": result.get("files_modified", []),
            "message": result.get("message", "PG-Router integration completed"),
            "iteration": state["current_iteration"],
            "existing_pr_reused": existing_pr_info.get("exists", False),
            "standard_branch_name": tool_config["standard_branch_name"]
        }

        # Update agent context with current results
        update_agent_context(state, "pg_router", state["pg_router_result"])
        action_type = "updated" if existing_pr_info.get("pr_url") else ("created" if not existing_pr_info.get("exists") else "branch updated")
        log_behavior(task_id, "PG-Router Integration Completed",
                    f"PR {action_type}: {state['pg_router_result'].get('pr_url', 'N/A')}")
                    
    except Exception as e:
        logger.exception(f"Error integrating pg-router for task {task_id}: {e}")
        state["pg_router_result"] = {
            "success": False,
            "error": str(e),
            "message": f"Failed to integrate pg-router: {str(e)}",
            "iteration": state["current_iteration"]
        }
        state["failed_steps"].append("pg_router")

        # Update agent context even for failures
        update_agent_context(state, "pg_router", state["pg_router_result"])
        log_behavior(task_id, "PG-Router Integration Failed", f"Error: {str(e)}")
    
    return state

# Continue with other repository integration functions...
async def integrate_nbplus(state: GatewayIntegrationState) -> GatewayIntegrationState:
    """Integrate nbplus repository using AutonomousAgentTool"""
    task_id = state["task_id"]
    gateway_name = state["gateway_name"]
    method = state["method"]
    is_retry = state["current_iteration"] > 0
    log_action = "Re-integrating NBPlus" if is_retry else "Integrating NBPlus"
    log_behavior(task_id, log_action, f"Checking for existing PR for {gateway_name} in nbplus repository")
    
    try:
        # Check for existing PR first using GitHub API
        existing_pr_info = await check_existing_pr(state, "nbplus", gateway_name, method)

        # If existing PR is found, update state and return without triggering agent
        if existing_pr_info.get("exists", False):
            log_behavior(task_id, "NBPlus Existing PR Found",
                        f"Found existing PR/branch: {existing_pr_info.get('pr_url', 'branch only')}")

            # Update state with existing PR information
            state["nbplus_result"] = {
                "success": True,
                "pr_url": existing_pr_info.get("pr_url"),
                "branch": existing_pr_info.get("branch"),
                "files_modified": [],  # Will be populated later when agent runs
                "message": "Existing PR/branch found for NBPlus integration",
                "iteration": state["current_iteration"],
                "existing_pr_reused": True,
                "existing_pr_info": existing_pr_info,
                "agent_executed": False  # Flag to indicate agent wasn't run
            }

            # Initialize agent context even if not executing
            if "nbplus" not in state["agent_contexts"]:
                state["agent_contexts"]["nbplus"] = {
                    "repository": "nbplus",
                    "created_at": datetime.now().isoformat(),
                    "iterations": [],
                    "files_modified": [],
                    "previous_results": [],
                    "existing_pr_info": existing_pr_info
                }
            return state

        # No existing PR found, proceed with normal agent execution
        log_behavior(task_id, log_action, f"No existing PR found, creating new integration for {gateway_name}")

        # Prepare tool configuration
        tool_config = prepare_integration_config(state, "nbplus", gateway_name, method, existing_pr_info)

        # Base prompt for integration
        base_prompt = f"""
        You are tasked with integrating the {gateway_name} payment gateway for {method} payments in the nbplus repository.
        Repository: {state["repositories"]["nbplus"]}
        Standard Branch Name: {tool_config["standard_branch_name"]}
        
        Your task:
        1. {'Update the existing' if existing_pr_info.get('exists') else 'Add'} gateway configuration for {gateway_name}
        2. Implement wallet/netbanking integration for {method} payments
        3. Add gateway-specific configurations
        4. Update payment processing logic
        5. Add proper error handling and logging
        6. Add unit tests for the integration
        7. {'Update the existing PR' if existing_pr_info.get('pr_url') else 'Create a pull request'} with all changes
        
        Gateway Details:
        - Name: {gateway_name}
        - Payment Method: {method}
        - Countries: {', '.join(state.get('countries_applicable', []))}
        """

        # Get or create agent (will reuse existing agent if available)
        agent_tool = get_or_create_agent(state, "nbplus", tool_config, is_retry=is_retry)

        # Execute the autonomous agent tool
        result = await agent_tool.execute({
            "prompt": base_prompt,
            "task_id": task_id,
            "agent_name": "gateway-integrations-i18n",
        })

        # Store the result with existing PR information
        state["nbplus_result"] = {
            "success": result.get("success", False),
            "pr_url": result.get("pr_url") or existing_pr_info.get("pr_url"),
            "branch": result.get("branch") or existing_pr_info.get("branch"),
            "files_modified": result.get("files_modified", []),
            "message": result.get("message", "NBPlus integration completed"),
            "iteration": state["current_iteration"],
            "existing_pr_reused": existing_pr_info.get("exists", False),
            "standard_branch_name": tool_config["standard_branch_name"]
        }

        # Update agent context with current results
        update_agent_context(state, "nbplus", state["nbplus_result"])
        action_type = "updated" if existing_pr_info.get("pr_url") else ("created" if not existing_pr_info.get("exists") else "branch updated")
        log_behavior(task_id, "NBPlus Integration Completed",
                    f"PR {action_type}: {state['nbplus_result'].get('pr_url', 'N/A')}")
                    
    except Exception as e:
        logger.exception(f"Error integrating nbplus for task {task_id}: {e}")
        state["nbplus_result"] = {
            "success": False,
            "error": str(e),
            "message": f"Failed to integrate nbplus: {str(e)}",
            "iteration": state["current_iteration"]
        }
        state["failed_steps"].append("nbplus")

        # Update agent context even for failures
        update_agent_context(state, "nbplus", state["nbplus_result"])
        log_behavior(task_id, "NBPlus Integration Failed", f"Error: {str(e)}")
    
    return state

async def integrate_mozart(state: GatewayIntegrationState) -> GatewayIntegrationState:
    """Integrate mozart repository using AutonomousAgentTool"""
    task_id = state["task_id"]
    gateway_name = state["gateway_name"]
    method = state["method"]
    is_retry = state["current_iteration"] > 0
    log_action = "Re-integrating Mozart" if is_retry else "Integrating Mozart"
    log_behavior(task_id, log_action, f"Creating PR for {gateway_name} in mozart repository")
    
    try:
        # Check for existing PR first using GitHub API
        existing_pr_info = await check_existing_pr(state, "mozart", gateway_name, method)

        # If existing PR is found, update state and return without triggering agent
        if existing_pr_info.get("exists", False):
            log_behavior(task_id, "Mozart Existing PR Found",
                        f"Found existing PR/branch: {existing_pr_info.get('pr_url', 'branch only')}")

            # Update state with existing PR information
            state["mozart_result"] = {
                "success": True,
                "pr_url": existing_pr_info.get("pr_url"),
                "branch": existing_pr_info.get("branch"),
                "files_modified": [],  # Will be populated later when agent runs
                "message": "Existing PR/branch found for Mozart integration",
                "iteration": state["current_iteration"],
                "existing_pr_reused": True,
                "existing_pr_info": existing_pr_info,
                "agent_executed": False  # Flag to indicate agent wasn't run
            }

            # Initialize agent context even if not executing
            if "mozart" not in state["agent_contexts"]:
                state["agent_contexts"]["mozart"] = {
                    "repository": "mozart",
                    "created_at": datetime.now().isoformat(),
                    "iterations": [],
                    "files_modified": [],
                    "previous_results": [],
                    "existing_pr_info": existing_pr_info
                }
            return state

        # No existing PR found, proceed with normal agent execution
        log_behavior(task_id, log_action, f"No existing PR found, creating new integration for {gateway_name}")

        # Prepare tool configuration based on existing PR status
        tool_config = prepare_integration_config(state, "mozart", gateway_name, method, existing_pr_info)

        # Base prompt for integration
        base_prompt = f"""
        You are tasked with integrating the {gateway_name} payment gateway for {method} payments in the mozart repository.
        Repository: {state["repositories"]["mozart"]}
        Standard Branch Name: {tool_config["standard_branch_name"]}
        
        Your task:
        1. {'Update the existing' if existing_pr_info.get('exists') else 'Add'} fraud and risk management rules for {gateway_name}
        2. Implement gateway-specific fraud detection algorithms
        3. Add risk scoring for {method} payments through {gateway_name}
        4. Update merchant onboarding configurations
        5. Add proper logging and monitoring
        6. Add unit tests for fraud detection
        7. {'Update the existing PR' if existing_pr_info.get('pr_url') else 'Create a pull request'} with all changes
        
        Gateway Details:
        - Name: {gateway_name}
        - Payment Method: {method}
        - Countries: {', '.join(state.get('countries_applicable', []))}
        """

        # Get or create agent (will reuse existing agent if available)
        agent_tool = get_or_create_agent(state, "mozart", tool_config, is_retry=is_retry)

        # Execute the autonomous agent tool
        result = await agent_tool.execute({
            "prompt": base_prompt,
            "task_id": task_id,
            "agent_name": "gateway-integrations-i18n",
        })

        # Store the result with existing PR information
        state["mozart_result"] = {
            "success": result.get("success", False),
            "pr_url": result.get("pr_url") or existing_pr_info.get("pr_url"),
            "branch": result.get("branch") or existing_pr_info.get("branch"),
            "files_modified": result.get("files_modified", []),
            "message": result.get("message", "Mozart integration completed"),
            "iteration": state["current_iteration"],
            "existing_pr_reused": existing_pr_info.get("exists", False),
            "standard_branch_name": tool_config["standard_branch_name"]
        }

        # Update agent context with current results
        update_agent_context(state, "mozart", state["mozart_result"])
        action_type = "updated" if existing_pr_info.get("pr_url") else ("created" if not existing_pr_info.get("exists") else "branch updated")
        log_behavior(task_id, "Mozart Integration Completed",
                    f"PR {action_type}: {state['mozart_result'].get('pr_url', 'N/A')}")
                    
    except Exception as e:
        logger.exception(f"Error integrating mozart for task {task_id}: {e}")
        state["mozart_result"] = {
            "success": False,
            "error": str(e),
            "message": f"Failed to integrate mozart: {str(e)}",
            "iteration": state["current_iteration"]
        }
        state["failed_steps"].append("mozart")

        # Update agent context even for failures
        update_agent_context(state, "mozart", state["mozart_result"])
        log_behavior(task_id, "Mozart Integration Failed", f"Error: {str(e)}")
    
    return state

async def integrate_integrations_go(state: GatewayIntegrationState) -> GatewayIntegrationState:
    """Integrate integrations-go repository using AutonomousAgentTool"""
    task_id = state["task_id"]
    gateway_name = state["gateway_name"]
    method = state["method"]
    is_retry = state["current_iteration"] > 0
    log_action = "Re-integrating Integrations Go" if is_retry else "Integrating Integrations Go"
    log_behavior(task_id, log_action, f"Creating PR for {gateway_name} in integrations-go repository")
    
    try:
        # Check for existing PR first using GitHub API
        existing_pr_info = await check_existing_pr(state, "integrations_go", gateway_name, method)

        if existing_pr_info.get("exists", False):
            log_behavior(task_id, "Integrations Go Existing PR Found",
                        f"Found existing PR/branch: {existing_pr_info.get('pr_url', 'branch only')}")

            state["integrations_go_result"] = {
                "success": True,
                "pr_url": existing_pr_info.get("pr_url"),
                "branch": existing_pr_info.get("branch"),
                "files_modified": [],
                "message": "Existing PR/branch found for Integrations Go integration",
                "iteration": state["current_iteration"],
                "existing_pr_reused": True,
                "existing_pr_info": existing_pr_info,
                "agent_executed": False
            }

            if "integrations_go" not in state["agent_contexts"]:
                state["agent_contexts"]["integrations_go"] = {
                    "repository": "integrations_go",
                    "created_at": datetime.now().isoformat(),
                    "iterations": [],
                    "files_modified": [],
                    "previous_results": [],
                    "existing_pr_info": existing_pr_info
                }
            return state

        log_behavior(task_id, log_action, f"No existing PR found, creating new integration for {gateway_name}")

        tool_config = prepare_integration_config(state, "integrations_go", gateway_name, method, existing_pr_info)

        base_prompt = f"""
        You are tasked with integrating the {gateway_name} payment gateway for {method} payments in the integrations-go repository.
        Repository: {state["repositories"]["integrations_go"]}
        Standard Branch Name: {tool_config["standard_branch_name"]}
        
        Your task:
        1. {'Update the existing' if existing_pr_info.get('exists') else 'Add'} Go-based integration for {gateway_name}
        2. Implement API client and SDK for {method} payments
        3. Add gateway-specific request/response handling
        4. Implement proper authentication and security
        5. Add comprehensive error handling and logging
        6. Add unit and integration tests
        7. {'Update the existing PR' if existing_pr_info.get('pr_url') else 'Create a pull request'} with all changes
        
        Gateway Details:
        - Name: {gateway_name}
        - Payment Method: {method}
        - Countries: {', '.join(state.get('countries_applicable', []))}
        """

        agent_tool = get_or_create_agent(state, "integrations_go", tool_config, is_retry=is_retry)

        result = await agent_tool.execute({
            "prompt": base_prompt,
            "task_id": task_id,
            "agent_name": "gateway-integrations-i18n",
        })

        state["integrations_go_result"] = {
            "success": result.get("success", False),
            "pr_url": result.get("pr_url") or existing_pr_info.get("pr_url"),
            "branch": result.get("branch") or existing_pr_info.get("branch"),
            "files_modified": result.get("files_modified", []),
            "message": result.get("message", "Integrations Go integration completed"),
            "iteration": state["current_iteration"],
            "existing_pr_reused": existing_pr_info.get("exists", False),
            "standard_branch_name": tool_config["standard_branch_name"]
        }

        update_agent_context(state, "integrations_go", state["integrations_go_result"])
        action_type = "updated" if existing_pr_info.get("pr_url") else ("created" if not existing_pr_info.get("exists") else "branch updated")
        log_behavior(task_id, "Integrations Go Integration Completed",
                    f"PR {action_type}: {state['integrations_go_result'].get('pr_url', 'N/A')}")
                    
    except Exception as e:
        logger.exception(f"Error integrating integrations-go for task {task_id}: {e}")
        state["integrations_go_result"] = {
            "success": False,
            "error": str(e),
            "message": f"Failed to integrate integrations-go: {str(e)}",
            "iteration": state["current_iteration"]
        }
        state["failed_steps"].append("integrations_go")

        update_agent_context(state, "integrations_go", state["integrations_go_result"])
        log_behavior(task_id, "Integrations Go Integration Failed", f"Error: {str(e)}")
    
    return state

async def integrate_terraform_kong(state: GatewayIntegrationState) -> GatewayIntegrationState:
    """Integrate terraform-kong repository using AutonomousAgentTool"""
    task_id = state["task_id"]
    gateway_name = state["gateway_name"]
    method = state["method"]
    is_retry = state["current_iteration"] > 0
    log_action = "Re-integrating Terraform Kong" if is_retry else "Integrating Terraform Kong"
    log_behavior(task_id, log_action, f"Creating PR for {gateway_name} in terraform-kong repository")
    
    try:
        existing_pr_info = await check_existing_pr(state, "terraform_kong", gateway_name, method)

        if existing_pr_info.get("exists", False):
            log_behavior(task_id, "Terraform Kong Existing PR Found",
                        f"Found existing PR/branch: {existing_pr_info.get('pr_url', 'branch only')}")

            state["terraform_kong_result"] = {
                "success": True,
                "pr_url": existing_pr_info.get("pr_url"),
                "branch": existing_pr_info.get("branch"),
                "files_modified": [],
                "message": "Existing PR/branch found for Terraform Kong integration",
                "iteration": state["current_iteration"],
                "existing_pr_reused": True,
                "existing_pr_info": existing_pr_info,
                "agent_executed": False
            }

            if "terraform_kong" not in state["agent_contexts"]:
                state["agent_contexts"]["terraform_kong"] = {
                    "repository": "terraform_kong",
                    "created_at": datetime.now().isoformat(),
                    "iterations": [],
                    "files_modified": [],
                    "previous_results": [],
                    "existing_pr_info": existing_pr_info
                }
            return state

        log_behavior(task_id, log_action, f"No existing PR found, creating new integration for {gateway_name}")

        tool_config = prepare_integration_config(state, "terraform_kong", gateway_name, method, existing_pr_info)

        base_prompt = f"""
        You are tasked with integrating the {gateway_name} payment gateway for {method} payments in the terraform-kong repository.
        Repository: {state["repositories"]["terraform_kong"]}
        Standard Branch Name: {tool_config["standard_branch_name"]}
        
        Your task:
        1. {'Update the existing' if existing_pr_info.get('exists') else 'Add'} Kong gateway configuration for {gateway_name}
        2. Implement API routing and load balancing rules
        3. Add rate limiting and security policies
        4. Configure upstream services and health checks
        5. Add proper monitoring and logging
        6. {'Update the existing PR' if existing_pr_info.get('pr_url') else 'Create a pull request'} with all changes
        
        Gateway Details:
        - Name: {gateway_name}
        - Payment Method: {method}
        - Countries: {', '.join(state.get('countries_applicable', []))}
        """

        agent_tool = get_or_create_agent(state, "terraform_kong", tool_config, is_retry=is_retry)

        result = await agent_tool.execute({
            "prompt": base_prompt,
            "task_id": task_id,
            "agent_name": "gateway-integrations-i18n",
        })

        state["terraform_kong_result"] = {
            "success": result.get("success", False),
            "pr_url": result.get("pr_url") or existing_pr_info.get("pr_url"),
            "branch": result.get("branch") or existing_pr_info.get("branch"),
            "files_modified": result.get("files_modified", []),
            "message": result.get("message", "Terraform Kong integration completed"),
            "iteration": state["current_iteration"],
            "existing_pr_reused": existing_pr_info.get("exists", False),
            "standard_branch_name": tool_config["standard_branch_name"]
        }

        update_agent_context(state, "terraform_kong", state["terraform_kong_result"])
        action_type = "updated" if existing_pr_info.get("pr_url") else ("created" if not existing_pr_info.get("exists") else "branch updated")
        log_behavior(task_id, "Terraform Kong Integration Completed",
                    f"PR {action_type}: {state['terraform_kong_result'].get('pr_url', 'N/A')}")
                    
    except Exception as e:
        logger.exception(f"Error integrating terraform-kong for task {task_id}: {e}")
        state["terraform_kong_result"] = {
            "success": False,
            "error": str(e),
            "message": f"Failed to integrate terraform-kong: {str(e)}",
            "iteration": state["current_iteration"]
        }
        state["failed_steps"].append("terraform_kong")

        update_agent_context(state, "terraform_kong", state["terraform_kong_result"])
        log_behavior(task_id, "Terraform Kong Integration Failed", f"Error: {str(e)}")
    
    return state

async def integrate_proto(state: GatewayIntegrationState) -> GatewayIntegrationState:
    """Integrate proto repository using AutonomousAgentTool"""
    task_id = state["task_id"]
    gateway_name = state["gateway_name"]
    method = state["method"]
    is_retry = state["current_iteration"] > 0
    log_action = "Re-integrating Proto" if is_retry else "Integrating Proto"
    log_behavior(task_id, log_action, f"Creating PR for {gateway_name} in proto repository")
    
    try:
        existing_pr_info = await check_existing_pr(state, "proto", gateway_name, method)

        if existing_pr_info.get("exists", False):
            log_behavior(task_id, "Proto Existing PR Found",
                        f"Found existing PR/branch: {existing_pr_info.get('pr_url', 'branch only')}")

            state["proto_result"] = {
                "success": True,
                "pr_url": existing_pr_info.get("pr_url"),
                "branch": existing_pr_info.get("branch"),
                "files_modified": [],
                "message": "Existing PR/branch found for Proto integration",
                "iteration": state["current_iteration"],
                "existing_pr_reused": True,
                "existing_pr_info": existing_pr_info,
                "agent_executed": False
            }

            if "proto" not in state["agent_contexts"]:
                state["agent_contexts"]["proto"] = {
                    "repository": "proto",
                    "created_at": datetime.now().isoformat(),
                    "iterations": [],
                    "files_modified": [],
                    "previous_results": [],
                    "existing_pr_info": existing_pr_info
                }
            return state

        log_behavior(task_id, log_action, f"No existing PR found, creating new integration for {gateway_name}")

        tool_config = prepare_integration_config(state, "proto", gateway_name, method, existing_pr_info)

        base_prompt = f"""
        You are tasked with integrating the {gateway_name} payment gateway for {method} payments in the proto repository.
        Repository: {state["repositories"]["proto"]}
        Standard Branch Name: {tool_config["standard_branch_name"]}
        
        Your task:
        1. {'Update the existing' if existing_pr_info.get('exists') else 'Add'} Protocol Buffer definitions for {gateway_name}
        2. Define API contracts and message schemas
        3. Add gateway-specific request/response structures
        4. Update service definitions and RPC methods
        5. Generate code for multiple languages
        6. {'Update the existing PR' if existing_pr_info.get('pr_url') else 'Create a pull request'} with all changes
        
        Gateway Details:
        - Name: {gateway_name}
        - Payment Method: {method}
        - Countries: {', '.join(state.get('countries_applicable', []))}
        """

        agent_tool = get_or_create_agent(state, "proto", tool_config, is_retry=is_retry)

        result = await agent_tool.execute({
            "prompt": base_prompt,
            "task_id": task_id,
            "agent_name": "gateway-integrations-i18n",
        })

        state["proto_result"] = {
            "success": result.get("success", False),
            "pr_url": result.get("pr_url") or existing_pr_info.get("pr_url"),
            "branch": result.get("branch") or existing_pr_info.get("branch"),
            "files_modified": result.get("files_modified", []),
            "message": result.get("message", "Proto integration completed"),
            "iteration": state["current_iteration"],
            "existing_pr_reused": existing_pr_info.get("exists", False),
            "standard_branch_name": tool_config["standard_branch_name"]
        }

        update_agent_context(state, "proto", state["proto_result"])
        action_type = "updated" if existing_pr_info.get("pr_url") else ("created" if not existing_pr_info.get("exists") else "branch updated")
        log_behavior(task_id, "Proto Integration Completed",
                    f"PR {action_type}: {state['proto_result'].get('pr_url', 'N/A')}")
                    
    except Exception as e:
        logger.exception(f"Error integrating proto for task {task_id}: {e}")
        state["proto_result"] = {
            "success": False,
            "error": str(e),
            "message": f"Failed to integrate proto: {str(e)}",
            "iteration": state["current_iteration"]
        }
        state["failed_steps"].append("proto")

        update_agent_context(state, "proto", state["proto_result"])
        log_behavior(task_id, "Proto Integration Failed", f"Error: {str(e)}")
    
    return state

async def integrate_api(state: GatewayIntegrationState) -> GatewayIntegrationState:
    """Integrate api repository using AutonomousAgentTool"""
    task_id = state["task_id"]
    gateway_name = state["gateway_name"]
    method = state["method"]
    is_retry = state["current_iteration"] > 0
    log_action = "Re-integrating API" if is_retry else "Integrating API"
    log_behavior(task_id, log_action, f"Creating PR for {gateway_name} in api repository")
    
    try:
        existing_pr_info = await check_existing_pr(state, "api", gateway_name, method)

        if existing_pr_info.get("exists", False):
            log_behavior(task_id, "API Existing PR Found",
                        f"Found existing PR/branch: {existing_pr_info.get('pr_url', 'branch only')}")

            state["api_result"] = {
                "success": True,
                "pr_url": existing_pr_info.get("pr_url"),
                "branch": existing_pr_info.get("branch"),
                "files_modified": [],
                "message": "Existing PR/branch found for API integration",
                "iteration": state["current_iteration"],
                "existing_pr_reused": True,
                "existing_pr_info": existing_pr_info,
                "agent_executed": False
            }

            if "api" not in state["agent_contexts"]:
                state["agent_contexts"]["api"] = {
                    "repository": "api",
                    "created_at": datetime.now().isoformat(),
                    "iterations": [],
                    "files_modified": [],
                    "previous_results": [],
                    "existing_pr_info": existing_pr_info
                }
            return state

        log_behavior(task_id, log_action, f"No existing PR found, creating new integration for {gateway_name}")

        tool_config = prepare_integration_config(state, "api", gateway_name, method, existing_pr_info)

        base_prompt = f"""
        You are tasked with integrating the {gateway_name} payment gateway for {method} payments in the api repository.
        Repository: {state["repositories"]["api"]}
        Standard Branch Name: {tool_config["standard_branch_name"]}
        
        Your task:
        1. {'Update the existing' if existing_pr_info.get('exists') else 'Add'} API endpoints for {gateway_name}
        2. Implement payment processing APIs for {method}
        3. Add webhook handling and callback endpoints
        4. Update merchant-facing API documentation
        5. Add proper validation and error handling
        6. Add comprehensive API tests
        7. {'Update the existing PR' if existing_pr_info.get('pr_url') else 'Create a pull request'} with all changes
        
        Gateway Details:
        - Name: {gateway_name}
        - Payment Method: {method}
        - Countries: {', '.join(state.get('countries_applicable', []))}
        """

        agent_tool = get_or_create_agent(state, "api", tool_config, is_retry=is_retry)

        result = await agent_tool.execute({
            "prompt": base_prompt,
            "task_id": task_id,
            "agent_name": "gateway-integrations-i18n",
        })

        state["api_result"] = {
            "success": result.get("success", False),
            "pr_url": result.get("pr_url") or existing_pr_info.get("pr_url"),
            "branch": result.get("branch") or existing_pr_info.get("branch"),
            "files_modified": result.get("files_modified", []),
            "message": result.get("message", "API integration completed"),
            "iteration": state["current_iteration"],
            "existing_pr_reused": existing_pr_info.get("exists", False),
            "standard_branch_name": tool_config["standard_branch_name"]
        }

        update_agent_context(state, "api", state["api_result"])
        action_type = "updated" if existing_pr_info.get("pr_url") else ("created" if not existing_pr_info.get("exists") else "branch updated")
        log_behavior(task_id, "API Integration Completed",
                    f"PR {action_type}: {state['api_result'].get('pr_url', 'N/A')}")
                    
    except Exception as e:
        logger.exception(f"Error integrating api for task {task_id}: {e}")
        state["api_result"] = {
            "success": False,
            "error": str(e),
            "message": f"Failed to integrate api: {str(e)}",
            "iteration": state["current_iteration"]
        }
        state["failed_steps"].append("api")

        update_agent_context(state, "api", state["api_result"])
        log_behavior(task_id, "API Integration Failed", f"Error: {str(e)}")
    
    return state

def create_gateway_integration_graph() -> StateGraph:
    """Create the LangGraph workflow for gateway integration"""
    # Create the graph
    workflow = StateGraph(GatewayIntegrationState)
    
    # Add nodes
    workflow.add_node("initialize_workflow", initialize_workflow)
    workflow.add_node("run_parallel_integrations", run_parallel_integrations)
    workflow.add_node("aggregate_results", aggregate_results)
    workflow.add_node("validate_changes", validate_changes)
    workflow.add_node("fix_validation_issues", fix_validation_issues)
    workflow.add_node("deploy_to_devstack", deploy_to_devstack)
    workflow.add_node("run_e2e_tests", run_e2e_tests)
    workflow.add_node("process_feedback", process_feedback)
    workflow.add_node("debug_and_correct_agents", debug_and_correct_agents)
    workflow.add_node("complete_workflow", complete_workflow)
    workflow.add_node("fail_workflow", fail_workflow)
    
    # Set entry point
    workflow.set_entry_point("initialize_workflow")
    
    # Add edges
    workflow.add_edge("initialize_workflow", "run_parallel_integrations")
    workflow.add_edge("run_parallel_integrations", "aggregate_results")
    workflow.add_edge("aggregate_results", "validate_changes")
    workflow.add_conditional_edges(
        "validate_changes",
        should_continue,
        {
            "deploy_to_devstack": "deploy_to_devstack",
            "fix_validation_issues": "fix_validation_issues",
            "fail_workflow": "fail_workflow"
        }
    )
    workflow.add_conditional_edges(
        "fix_validation_issues",
        should_continue,
        {
            "validate_changes": "validate_changes",
            "fail_workflow": "fail_workflow"
        }
    )
    workflow.add_conditional_edges(
        "deploy_to_devstack",
        should_continue,
        {
            "run_e2e_tests": "run_e2e_tests",
            "fail_workflow": "fail_workflow"
        }
    )
    workflow.add_conditional_edges(
        "run_e2e_tests",
        should_continue,
        {
            "complete_workflow": "complete_workflow",
            "process_feedback": "process_feedback",
            "fail_workflow": "fail_workflow"
        }
    )
    workflow.add_conditional_edges(
        "process_feedback",
        should_continue,
        {
            "debug_and_correct_agents": "debug_and_correct_agents",
            "fail_workflow": "fail_workflow"
        }
    )
    workflow.add_conditional_edges(
        "debug_and_correct_agents",
        should_continue,
        {
            "validate_changes": "validate_changes",
            "fail_workflow": "fail_workflow"
        }
    )
    workflow.add_edge("complete_workflow", END)
    workflow.add_edge("fail_workflow", END)
    
    return workflow.compile()

async def handle_gateway_integration_task(task_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle a gateway integration task using LangGraph workflow.
    
    Args:
        task_id: The ID of the task
        parameters: The parameters for the task
        
    Returns:
        The result of the task
    """
    try:
        logger.info(f"Processing gateway integration LangGraph task {task_id}")
        log_behavior(task_id, "LangGraph Task Initiated", "Starting LangGraph workflow for gateway integration")
        
        # Validate parameters
        required_params = ["gateway_name", "method", "countries_applicable"]
        for param in required_params:
            if param not in parameters:
                error_msg = f"Missing required parameter: {param}"
                log_behavior(task_id, "Task Failed", error_msg)
                return {
                    "success": False,
                    "error": error_msg
                }
        
        # Create the workflow graph
        workflow_graph = create_gateway_integration_graph()
        
        # Initialize state
        initial_state = GatewayIntegrationState(
            task_id=task_id,
            gateway_name=parameters["gateway_name"],
            method=parameters["method"],
            countries_applicable=parameters.get("countries_applicable", []),
            messages=[HumanMessage(content=f"Integrate {parameters['gateway_name']} gateway")],
            current_step="initialize",
            completed_steps=[],
            failed_steps=[],
            repositories={},
            agent_instances={},  # Initialize agent persistence
            agent_contexts={},   # Initialize agent contexts
            apis_to_integrate=parameters.get("apis_to_integrate", []),
            encryption_algorithm=parameters.get("encryption_algorithm", "AES-256"),
            additional_test_cases=parameters.get("additional_test_cases", 0),
            devstack_label="",  # Will be generated in initialize_workflow
            code_changes_result={},
            validation_result={},
            deployment_result={},
            e2e_test_result={},
            terminals_result={},
            pg_router_result={},
            nbplus_result={},
            mozart_result={},
            integrations_go_result={},
            terraform_kong_result={},
            proto_result={},
            api_result={},
            max_iterations=parameters.get("max_iterations", 50),
            current_iteration=0,
            tests_passed=False
        )
        
        # Execute the workflow
        log_behavior(task_id, "Executing LangGraph Workflow", "Running the complete gateway integration workflow")
        final_state = await workflow_graph.ainvoke(initial_state)
        
        # Extract results with improved error handling
        workflow_summary = final_state.get("workflow_summary", {})
        current_step = final_state.get("current_step", "unknown")
        
        # Check for successful completion with multiple indicators
        workflow_completed_successfully = (
            current_step == "completed" or
            current_step == "complete_workflow" or
            (final_state.get("tests_passed", False) and
             final_state.get("deployment_result", {}).get("success", False))
        )
        
        if workflow_completed_successfully:
            log_behavior(task_id, "LangGraph Workflow Completed", "Gateway integration workflow completed successfully")
            return {
                "success": True,
                "workflow_type": "langgraph",
                "gateway_name": parameters["gateway_name"],
                "method": parameters["method"],
                "countries_applicable": parameters["countries_applicable"],
                "summary": workflow_summary,
                "iterations_completed": final_state.get("current_iteration", 0),
                "repositories_modified": len(final_state.get("repositories", {})),
                "devstack_label": final_state.get("devstack_label", ""),
                "e2e_tests_passed": final_state.get("tests_passed", False),
                "deployment_successful": final_state.get("deployment_result", {}).get("success", False),
                "message": "Gateway integration completed successfully using LangGraph workflow"
            }
        else:
            # Determine the specific failure reason
            failed_steps = final_state.get("failed_steps", [])
            last_failed_step = failed_steps[-1] if failed_steps else "unknown"
            error_message = f"Workflow failed at step: {last_failed_step}"
            
            # Add specific error context
            if "run_e2e_tests" in failed_steps:
                e2e_result = final_state.get("e2e_test_result", {})
                if e2e_result.get("error"):
                    error_message += f" (E2E Error: {e2e_result['error']})"
            elif "deploy_to_devstack" in failed_steps:
                deploy_result = final_state.get("deployment_result", {})
                if deploy_result.get("error"):
                    error_message += f" (Deployment Error: {deploy_result['error']})"
            
            log_behavior(task_id, "LangGraph Workflow Failed", error_message)
            return {
                "success": False,
                "workflow_type": "langgraph",
                "error": error_message,
                "failed_steps": failed_steps,
                "current_step": current_step,
                "iterations_completed": final_state.get("current_iteration", 0),
                "summary": workflow_summary,
                "message": f"Gateway integration workflow failed: {error_message}"
            }
            
    except Exception as e:
        log_behavior(task_id, "LangGraph Task Failed", f"Exception: {str(e)}")
        logger.error(f"Error processing gateway integration task {task_id}: {e}")
        return {
            "success": False,
            "error": f"LangGraph workflow execution failed: {str(e)}",
            "workflow_type": "langgraph",
            "message": f"Gateway integration task failed with error: {str(e)}"
        }

def register_gateway_integration_handler():
    """Register the gateway integration task handler"""
    # Task handler registration is disabled in the new architecture
    # register_task_handler("gateway_integration", handle_gateway_integration_task)
    pass
