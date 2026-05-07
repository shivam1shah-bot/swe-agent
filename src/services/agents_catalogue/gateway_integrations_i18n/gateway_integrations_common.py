"""
Gateway Integration Service for Agents Catalogue

This service integrates payment gateways using the LangGraph workflow system.
It provides a unified interface for gateway integration automation.
"""

import logging
import os
import json
import time
import asyncio
from datetime import datetime
from typing import Dict, Any
import hashlib
import random
import string

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage

from src.services.agents_catalogue.base_service import BaseAgentsCatalogueService
from src.providers.context import Context
from src.services.agents_catalogue.gateway_integrations_i18n.gateway_integration_state import GatewayIntegrationState
from src.services.agents_catalogue.gateway_integrations_i18n.helper import (
    log_behavior, generate_devstack_label_hash, generate_randomized_devstack_label,
    get_or_create_agent, update_agent_context, validate_gateway_name, validate_method,
    validate_countries_applicable, validate_apis_to_integrate, 
    validate_encryption_algorithm, validate_max_iterations
)
from src.services.agents_catalogue.gateway_integrations_i18n.repository_config import RepositoryConfig
from src.services.agents_catalogue.gateway_integrations_i18n.workflow_functions import (
    initialize_workflow, run_parallel_integrations, aggregate_results,
    validate_changes, fix_validation_issues, deploy_to_devstack,
    run_e2e_tests, process_feedback, debug_and_correct_agents,
    complete_workflow, fail_workflow, should_continue,
    integrate_terminals, integrate_pg_router, integrate_nbplus,
    integrate_mozart, integrate_integrations_go, integrate_terraform_kong,
    integrate_proto, integrate_api, handle_gateway_integration_task,
    create_gateway_integration_graph
)
from src.services.agents_catalogue.registry import service_registry
from src.agents.autonomous_agent import AutonomousAgentTool

logger = logging.getLogger(__name__)

class I18nGatewayIntegrationService(BaseAgentsCatalogueService):
    """
    Gateway Integration Service for Agents Catalogue.
    
    Automates the integration of new payment gateways, including setup, 
    configuration, and standardized testing procedures using LangGraph workflow.
    """
    
    def __init__(self):
        """Initialize the Gateway Integration Service."""
        self.logger = logger
        self.capabilities = [
            "gateway_integration",
            "multi_repository_updates", 
            "automated_testing",
            "devstack_deployment",
            "pr_creation",
            "langgraph_workflow"
        ]
        self.version = "1.0.0"
    
    @property
    def description(self) -> str:
        """Service description."""
        return "Automates the integration of new payment gateways, including setup, configuration, and standardized testing procedures."
    
    def log_behavior(self, task_id: str, action: str, description: str) -> None:
        """
        Log agent behavior for a task to create a timeline of actions.
        
        Args:
            task_id: The ID of the task
            action: The action being performed
            description: A description of the action
        """
        log_behavior(task_id, action, description)
    
    def generate_devstack_label_hash(self, gateway_name: str) -> str:
        """
        Generate a consistent hash from gateway name for devstack labels.
        
        Args:
            gateway_name: The gateway name to hash
            
        Returns:
            A 5-character hash string
        """
        return generate_devstack_label_hash(gateway_name)
    
    def generate_randomized_devstack_label(self, gateway_name: str, task_id: str) -> str:
        """
        Generate a randomized devstack label for deployment.
        This ensures the label is unique and stays under Kubernetes 63-character limit.
        
        Args:
            gateway_name: The gateway name
            task_id: The task ID for additional uniqueness
            
        Returns:
            A randomized devstack label string
        """
        return generate_randomized_devstack_label(gateway_name, task_id)
    
    def get_or_create_agent(
        self,
        state: GatewayIntegrationState,
        repo_name: str,
        tool_config: Dict[str, Any],
        is_retry: bool = False
    ) -> AutonomousAgentTool:
        """
        Get or create an agent for a specific repository, maintaining state across calls.
        
        Args:
            state: Current workflow state
            repo_name: Name of the repository
            tool_config: Configuration for the tool
            is_retry: Whether this is a retry operation
            
        Returns:
            AutonomousAgentTool instance
        """
        # Check if agent already exists for this repository
        if repo_name in state["agent_instances"] and not is_retry:
            self.logger.info(f"Reusing existing agent for {repo_name}")
            return state["agent_instances"][repo_name]
        
        # Create new agent instance
        self.logger.info(f"Creating new agent for {repo_name} (retry: {is_retry})")
        agent = AutonomousAgentTool(**tool_config)
        
        # Store agent instance in state
        state["agent_instances"][repo_name] = agent
        
        # Initialize context for this agent if not exists
        if repo_name not in state["agent_contexts"]:
            state["agent_contexts"][repo_name] = {}
        
        return agent
    
    def update_agent_context(
        self,
        state: GatewayIntegrationState,
        repo_name: str,
        result: Dict[str, Any]
    ) -> None:
        """
        Update the agent context with the result of the latest operation.
        
        Args:
            state: Current workflow state
            repo_name: Name of the repository
            result: Result of the operation to store in context
        """
        if repo_name not in state["agent_contexts"]:
            state["agent_contexts"][repo_name] = {}
        
        # Store the latest result
        state["agent_contexts"][repo_name]["last_result"] = result
        state["agent_contexts"][repo_name]["last_updated"] = time.time()
        
        # Store PR URL if available
        if result.get("pr_url"):
            state["agent_contexts"][repo_name]["pr_url"] = result["pr_url"]
        
        # Store branch name if available
        if result.get("branch_name"):
            state["agent_contexts"][repo_name]["branch_name"] = result["branch_name"]
    
    def create_gateway_integration_graph(self) -> StateGraph:
        """Create the LangGraph workflow for gateway integration"""
        return create_gateway_integration_graph()
    
    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronous execute for API calls - queues the task and returns immediately."""
        try:
            # Validate required parameters
            self._validate_parameters(parameters)
            
            # Queue the task using sync queue integration
            from src.tasks.queue_integration import queue_integration
            
            if not queue_integration.is_queue_available():
                return {
                    "status": "failed",
                    "message": "Queue not available",
                    "metadata": {"error": "Queue not available"}
                }
            
            self.logger.info("Submitting gateway integration task to queue",
                           extra={
                               "gateway_name": parameters.get("gateway_name"),
                               "method": parameters.get("method")
                           })
            
            # Submit to queue with gateway-integration-specific task type
            task_id = queue_integration.submit_agents_catalogue_task(
                usecase_name="gateway-integrations-i18n",
                parameters=parameters,
                metadata={
                    "service_type": "gateway_integration",
                    "execution_mode": "async",
                    "priority": "high",
                    "gateway_name": parameters.get("gateway_name"),
                    "method": parameters.get("method"),
                    "countries_applicable": parameters.get("countries_applicable", []),
                    "workflow_type": "langgraph"
                }
            )
            
            if task_id:
                self.logger.info("Gateway integration task queued successfully", 
                               extra={
                                   "task_id": task_id,
                                   "gateway_name": parameters.get("gateway_name"),
                                   "method": parameters.get("method")
                               })
                return {
                    "status": "queued",
                    "message": f"Gateway integration for {parameters.get('gateway_name')} queued successfully",
                    "task_id": task_id,
                    "workflow_type": "langgraph",
                    "metadata": {
                        "gateway_name": parameters.get("gateway_name"),
                        "method": parameters.get("method"),
                        "countries_applicable": parameters.get("countries_applicable", []),
                        "queued_at": self._get_current_timestamp()
                    }
                }
            else:
                return {
                    "status": "failed",
                    "message": "Failed to queue gateway integration",
                    "metadata": {"error": "Failed to submit to queue"}
                }
                
        except Exception as e:
            self.logger.error(f"Gateway integration submission failed: {e}")
            return {
                "status": "failed",
                "message": f"Failed to process gateway integration request: {str(e)}",
                "metadata": {
                    "error": str(e)
                }
            }
    
    async def async_execute(self, parameters: Dict[str, Any], ctx: Context) -> Dict[str, Any]:
        """
        Asynchronous execute for worker processing - performs the actual gateway integration using LangGraph.

        Args:
            parameters: Service-specific parameters for gateway integration
            ctx: Execution context with task_id, metadata, cancellation, and logging correlation

        Returns:
            Dictionary containing:
                - status: "completed" or "failed"
                - message: Status message
                - workflow_type: "langgraph"
                - summary: Workflow execution summary
                - repositories_modified: Number of repositories modified
                - devstack_label: Deployment label
                - pr_urls: List of created PR URLs
        """
        execution_start = time.time()

        try:
            # Extract task information from context
            task_id = self.get_task_id(ctx)
            log_ctx = self.get_logging_context(ctx)

            self.logger.info("Starting async gateway integration using LangGraph", extra=log_ctx)

            # Check if context is already done before starting
            if self.check_context_done(ctx):
                error_msg = "Context is done before gateway integration generation"
                if ctx.is_cancelled():
                    error_msg = "Context was cancelled before gateway integration generation"
                elif ctx.is_expired():
                    error_msg = "Context expired before gateway integration generation"

                self.logger.warning(error_msg, extra=log_ctx)
                return {
                    "status": "failed",
                    "message": error_msg,
                    "workflow_type": "langgraph",
                    "metadata": {
                        "error": error_msg,
                        "task_id": task_id,
                        "correlation_id": ctx.get("log_correlation_id")
                    }
                }

            # Validate required parameters
            self._validate_parameters(parameters)

            # Parse and normalize parameters for the LangGraph workflow
            workflow_parameters = self._prepare_workflow_parameters(parameters)

            # Handle gateway integration task using LangGraph workflow
            workflow_result = await handle_gateway_integration_task(task_id, workflow_parameters)

            execution_time = time.time() - execution_start

            # Process and format the results
            final_result = self._format_response(workflow_result, parameters, execution_time, task_id)

            # Add worker-specific metadata
            final_result["metadata"] = final_result.get("metadata", {})
            final_result["metadata"].update({
                "correlation_id": ctx.get("log_correlation_id"),
                "execution_mode": "async",
                "processed_by_worker": True
            })

            return final_result

        except Exception as e:
            execution_time = time.time() - execution_start

            # Try to get context info if available
            task_id = None
            log_ctx = {}
            try:
                task_id = self.get_task_id(ctx)
                log_ctx = self.get_logging_context(ctx)
            except:
                pass

            self.logger.error("Failed to generate gateway integration", extra={
                **log_ctx,
                "error": str(e),
                "error_type": type(e).__name__,
                "execution_time": execution_time
            })

            return {
                "status": "failed",
                "message": f"Failed to generate gateway integration: {str(e)}",
                "workflow_type": "langgraph",
                "error": str(e),
                "execution_time": execution_time,
                "metadata": {
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "task_id": task_id,
                    "correlation_id": ctx.get("log_correlation_id") if ctx else None
                }
            }

    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    async def handle_gateway_integration_task(self, task_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a gateway integration task using LangGraph workflow.

        Args:
            task_id: The ID of the task
            parameters: The parameters for the task

        Returns:
            The result of the task
        """
        return await handle_gateway_integration_task(task_id, parameters)

    def _validate_parameters(self, parameters: Dict[str, Any]) -> None:
        """
        Validate required parameters for gateway integration.

        Args:
            parameters: Parameters to validate

        Raises:
            ValueError: If required parameters are missing or invalid
        """
        required_params = ["gateway_name", "method", "countries_applicable"]

        for param in required_params:
            if param not in parameters:
                raise ValueError(f"Missing required parameter: {param}")

            if not parameters[param]:
                raise ValueError(f"Parameter '{param}' cannot be empty")

        # Validate using imported validation functions
        validate_gateway_name(parameters["gateway_name"])
        validate_method(parameters["method"])
        validate_countries_applicable(parameters["countries_applicable"])

        # Validate optional parameters
        if "apis_to_integrate" in parameters:
            validate_apis_to_integrate(parameters["apis_to_integrate"])

        if "encryption_algorithm" in parameters:
            validate_encryption_algorithm(parameters["encryption_algorithm"])

        if "max_iterations" in parameters:
            validate_max_iterations(parameters["max_iterations"])

        if "credentials" in parameters:
            credentials = parameters["credentials"]
            if not isinstance(credentials, list):
                raise ValueError("credentials must be a list of key-value pairs")

            for cred in credentials:
                if not isinstance(cred, dict) or "key" not in cred or "value" not in cred:
                    raise ValueError("Each credential must have 'key' and 'value' fields")

    def _prepare_workflow_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare parameters for the LangGraph workflow.

        Args:
            parameters: Input parameters from agents catalogue

        Returns:
            Parameters formatted for the LangGraph workflow
        """
        # Use custom method if provided, otherwise use the selected method
        method = parameters.get("custom_method", "").strip() or parameters["method"]

        workflow_params = {
            "gateway_name": parameters["gateway_name"].strip(),
            "method": method,
            "countries_applicable": parameters["countries_applicable"],
            "apis_to_integrate": parameters.get("apis_to_integrate", []),
            "encryption_algorithm": parameters.get("encryption_algorithm", "AES-256"),
            "additional_test_cases": parameters.get("additional_test_cases", 0),
            "max_iterations": parameters.get("max_iterations", 50)
        }

        # Add custom instructions and notes as metadata (not used by workflow but stored for reference)
        if parameters.get("custom_instructions"):
            workflow_params["custom_instructions"] = parameters["custom_instructions"]

        if parameters.get("integration_notes"):
            workflow_params["integration_notes"] = parameters["integration_notes"]

        # Process credentials into a structured format
        if parameters.get("credentials"):
            workflow_params["gateway_credentials"] = {
                cred["key"]: cred["value"]
                for cred in parameters["credentials"]
                if cred.get("key") and cred.get("value")
            }

        return workflow_params

    def _format_response(self, workflow_result: Dict[str, Any],
                        original_parameters: Dict[str, Any],
                        execution_time: float,
                        task_id: str) -> Dict[str, Any]:
        """
        Format the workflow result for agents catalogue response.

        Args:
            workflow_result: Result from the LangGraph workflow
            original_parameters: Original input parameters
            execution_time: Execution time in seconds
            task_id: Task ID

        Returns:
            Formatted response for agents catalogue
        """
        success = workflow_result.get("success", False)

        if success:
            # Extract PR URLs from workflow result summary
            pr_urls = []
            summary = workflow_result.get("summary", {})

            # Collect PR URLs from different repositories
            for repo_key in ["terminals_result", "pg_router_result", "nbplus_result",
                           "mozart_result", "integrations_go_result", "terraform_kong_result",
                           "proto_result", "api_result"]:
                if summary.get(repo_key, {}).get("pr_url"):
                    pr_urls.append(summary[repo_key]["pr_url"])

            return {
                "status": "completed",
                "message": f"Successfully integrated {original_parameters['gateway_name']} gateway for {original_parameters.get('custom_method') or original_parameters['method']} payments",
                "workflow_type": "langgraph",
                "task_id": task_id,
                "execution_time": execution_time,
                "gateway_name": workflow_result.get("gateway_name"),
                "method": workflow_result.get("method"),
                "countries_applicable": workflow_result.get("countries_applicable", []),
                "summary": summary,
                "metadata": {
                    "repositories_modified": workflow_result.get("repositories_modified", 0),
                    "devstack_label": workflow_result.get("devstack_label", ""),
                    "iterations_completed": workflow_result.get("iterations_completed", 0),
                    "e2e_tests_passed": workflow_result.get("e2e_tests_passed", False),
                    "deployment_successful": workflow_result.get("deployment_successful", False),
                    "pr_count": len(pr_urls),
                    "workflow_completed": True
                },
                "pr_urls": pr_urls,
                "devstack_label": workflow_result.get("devstack_label", ""),
                "next_steps": [
                    "Review the created pull requests",
                    "Test the integration in the devstack environment",
                    "Merge PRs after review and testing",
                    "Monitor deployment in staging environment"
                ]
            }
        else:
            return {
                "status": "failed",
                "message": workflow_result.get("error", "Gateway integration workflow failed"),
                "workflow_type": "langgraph",
                "task_id": task_id,
                "execution_time": execution_time,
                "error": workflow_result.get("error", "Unknown error"),
                "failed_steps": workflow_result.get("failed_steps", []),
                "current_step": workflow_result.get("current_step", "unknown"),
                "iterations_completed": workflow_result.get("iterations_completed", 0),
                "summary": workflow_result.get("summary", {}),
                "suggestions": [
                    "Check the error details and logs",
                    "Verify gateway configuration parameters",
                    "Ensure all required repositories are accessible",
                    "Contact the integration team for assistance"
                ]
            }

# Register the service
service_registry.register("gateway-integrations-i18n", I18nGatewayIntegrationService)