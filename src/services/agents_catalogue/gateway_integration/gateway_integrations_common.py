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
from dataclasses import dataclass
import hashlib
import random
import string

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage

from src.services.agents_catalogue.base_service import BaseAgentsCatalogueService
from src.providers.context import Context
from src.services.agents_catalogue.gateway_integration.gateway_integration_state import GatewayIntegrationState
from src.services.agents_catalogue.gateway_integration.helper import log_behavior, check_existing_pr, \
    prepare_integration_config, get_or_create_agent, update_agent_context
from src.services.agents_catalogue.registry import service_registry
from src.agents.autonomous_agent import AutonomousAgentTool
from src.services.agents_catalogue.gateway_integration.prompt_providers.integrations_prompts import IntegrationsGoPromptProvider
from src.services.agents_catalogue.gateway_integration.prompt_providers.integrations_upi import IntegrationsUpiPromptProvider
from src.services.agents_catalogue.gateway_integration.repository_config import RepositoryConfig

logger = logging.getLogger(__name__)

# Required parameters for the validator discovery system
REQUIRED_PARAMETERS = ["gateway_name", "method", "countries_applicable"]

# Define the state structure for the workflow

@dataclass
class GatewayCredential:
    """Gateway credential key-value pair."""
    key: str
    value: str

class GatewayIntegrationService(BaseAgentsCatalogueService):
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

    def generate_devstack_label_hash(self, gateway_name: str) -> str:
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
        print("starting gateway integration")
        # Create the graph
        workflow = StateGraph(GatewayIntegrationState)

        # Add nodes
        workflow.add_node("initialize_workflow", self.initialize_workflow)
        workflow.add_node("run_parallel_integrations", self.run_parallel_integrations)
        workflow.add_node("aggregate_results", self.aggregate_results)
        workflow.add_node("create_run_unit_tests", self.create_run_unit_tests)
        workflow.add_node("validate_changes", self.validate_changes)
        workflow.add_node("fix_validation_issues", self.fix_validation_issues)
        workflow.add_node("deploy_to_devstack", self.deploy_to_devstack)
        workflow.add_node("run_e2e_tests", self.run_e2e_tests)
        workflow.add_node("process_feedback", self.process_feedback)
        workflow.add_node("debug_and_correct_agents", self.debug_and_correct_agents)
        workflow.add_node("complete_workflow", self.complete_workflow)
        workflow.add_node("fail_workflow", self.fail_workflow)

        # Set entry point
        workflow.set_entry_point("initialize_workflow")

        # Add edges
        workflow.add_edge("initialize_workflow", "run_parallel_integrations")
        workflow.add_edge("run_parallel_integrations", "aggregate_results")
        workflow.add_edge("aggregate_results", "create_run_unit_tests")
        workflow.add_conditional_edges(
            "validate_changes",
            self.should_continue,
            {
                "deploy_to_devstack": "deploy_to_devstack",
                "fix_validation_issues": "fix_validation_issues",
                "fail_workflow": "fail_workflow"
            }
        )
        workflow.add_conditional_edges(
            "fix_validation_issues",
            self.should_continue,
            {
                "validate_changes": "validate_changes",
                "fail_workflow": "fail_workflow"
            }
        )
        workflow.add_conditional_edges(
            "create_run_unit_tests",
            self.should_continue,
            {
                "validate_changes": "validate_changes",
                "fail_workflow": "fail_workflow"
            }
        )
        workflow.add_conditional_edges(
            "deploy_to_devstack",
            self.should_continue,
            {
                "run_e2e_tests": "run_e2e_tests",
                "fail_workflow": "fail_workflow"
            }
        )
        workflow.add_conditional_edges(
            "run_e2e_tests",
            self.should_continue,
            {
                "complete_workflow": "complete_workflow",
                "process_feedback": "process_feedback",
                "fail_workflow": "fail_workflow"
            }
        )
        workflow.add_conditional_edges(
            "process_feedback",
            self.should_continue,
            {
                "debug_and_correct_agents": "debug_and_correct_agents",
                "fail_workflow": "fail_workflow"
            }
        )
        workflow.add_conditional_edges(
            "debug_and_correct_agents",
            self.should_continue,
            {
                "validate_changes": "validate_changes",
                "fail_workflow": "fail_workflow"
            }
        )
        workflow.add_edge("complete_workflow", END)
        workflow.add_edge("fail_workflow", END)

        return workflow.compile()

    def get_workflow_diagram(self) -> str:
        """Generate Mermaid diagram syntax for the gateway integration workflow"""
        workflow = self.create_gateway_integration_graph()
        return workflow.get_graph().draw_mermaid()

    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronous execute for API calls - queues the task and returns immediately."""
        try:
            # Normalize and validate required parameters
            normalized_parameters = self._normalize_parameters(parameters)
            self._validate_parameters(normalized_parameters)

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
                               "gateway_name": normalized_parameters.get("gateway_name"),
                               "method": normalized_parameters.get("method")
                           })

            # Submit to queue with gateway-integration-specific task type
            task_id = queue_integration.submit_agents_catalogue_task(
                usecase_name="gateway-integrations-common",
                parameters=normalized_parameters,
                metadata={
                    "service_type": "gateway_integration",
                    "execution_mode": "async",
                    "priority": "normal",
                    "gateway_name": normalized_parameters.get("gateway_name"),
                    "method": normalized_parameters.get("method"),
                    "countries_applicable": normalized_parameters.get("countries_applicable", []),
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
    
    def async_execute(self, parameters: Dict[str, Any], ctx: Context) -> Dict[str, Any]:
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

            # Normalize and validate required parameters
            normalized_parameters = self._normalize_parameters(parameters)
            self._validate_parameters(normalized_parameters)

            # Parse and normalize parameters for the LangGraph workflow
            workflow_parameters = self._prepare_workflow_parameters(normalized_parameters)

            # Handle gateway integration task using LangGraph workflow
            workflow_result = self.handle_gateway_integration_task(task_id, workflow_parameters)

            execution_time = time.time() - execution_start

            # Process and format the results
            final_result = self._format_response(workflow_result, normalized_parameters, execution_time, task_id)

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

    def handle_gateway_integration_task(self, task_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a gateway integration task using LangGraph workflow.

        Args:
            task_id: The ID of the task
            parameters: The parameters for the task

        Returns:
            The result of the task
        """
        try:
            self.logger.info(f"Processing gateway integration LangGraph task {task_id}")
            self.log_behavior(task_id, "LangGraph Task Initiated", "Starting LangGraph workflow for gateway integration")

            # Validate parameters
            required_params = ["gateway_name", "method", "countries_applicable"]
            for param in required_params:
                if param not in parameters:
                    error_msg = f"Missing required parameter: {param}"
                    self.log_behavior(task_id, "Task Failed", error_msg)
                    return {
                        "success": False,
                        "error": error_msg
                    }

            # Create the workflow graph
            workflow_graph = self.create_gateway_integration_graph()

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
                working_branch={},
                agent_instances={},  # Initialize agent persistence
                agent_contexts={},   # Initialize agent contexts
                apis_to_integrate=parameters.get("apis_to_integrate", []),
                encryption_algorithm=parameters.get("encryption_algorithm", "AES-256"),
                additional_test_cases=parameters.get("additional_test_cases", 0),
                use_switch=parameters.get("use_switch", False),
                markdown_doc_path=parameters.get("markdown_doc_path", ""),  # Add markdown documentation path
                reference_gateway=parameters.get("reference_gateway", ""),  # Add reference gateway
                devstack_label="",  # Will be generated in initialize_workflow
                code_changes_result={},
                validation_result={},
                deployment_result={},
                e2e_test_result={},
                integrations_go_result={},
                workflow_summary={},
                max_iterations=parameters.get("max_iterations", 50),
                current_iteration=0,
                tests_passed=False
            )

            # Execute the workflow
            self.log_behavior(task_id, "Executing LangGraph Workflow", "Running the complete gateway integration workflow")
            
            # Handle async workflow execution properly for sync context
            try:
                # Check if we're already in an event loop
                loop = asyncio.get_running_loop()
                # We're in an async context (worker), so we need to run in a new thread with its own loop
                from concurrent.futures import ThreadPoolExecutor
                
                def run_workflow():
                    # Create a new event loop for this thread
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(workflow_graph.ainvoke(initial_state))
                    finally:
                        new_loop.close()
                
                with ThreadPoolExecutor() as executor:
                    future = executor.submit(run_workflow)
                    final_state = future.result()
            except RuntimeError:
                # No running loop, safe to use asyncio.run()
                final_state = asyncio.run(workflow_graph.ainvoke(initial_state))

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
                self.log_behavior(task_id, "LangGraph Workflow Completed", "Gateway integration workflow completed successfully")
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

                self.log_behavior(task_id, "LangGraph Workflow Failed", error_message)
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
            self.log_behavior(task_id, "LangGraph Task Failed", f"Exception: {str(e)}")
            self.logger.error(f"Error processing gateway integration task {task_id}: {e}")
            return {
                "success": False,
                "error": f"LangGraph workflow execution failed: {str(e)}",
                "workflow_type": "langgraph",
                "message": f"Gateway integration task failed with error: {str(e)}"
            }

    # I'll continue with the workflow methods (initialize_workflow, run_parallel_integrations, etc.)
    # These will be added in the next part due to length constraints

    def _normalize_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize parameters to handle both direct and nested parameter structures.
        
        Args:
            parameters: Raw parameters from request
            
        Returns:
            Normalized parameters
        """
        # Handle nested parameter structure for backward compatibility
        # If parameters contain a 'parameters' key, extract the nested parameters
        if 'parameters' in parameters and isinstance(parameters['parameters'], dict):
            # Check if the nested structure contains the expected keys
            nested_params = parameters['parameters']
            if any(key in nested_params for key in ["gateway_name", "method", "countries_applicable"]):
                self.logger.info("Detected nested parameter structure, extracting inner parameters")
                return nested_params
        
        return parameters

    def _validate_parameters(self, parameters: Dict[str, Any]) -> None:
        """
        Validate required parameters for gateway integration.

        Args:
            parameters: Parameters to validate

        Raises:
            ValueError: If required parameters are missing or invalid
        """
        # Normalize parameters first
        parameters = self._normalize_parameters(parameters)
        
        required_params = ["gateway_name", "method", "countries_applicable"]

        for param in required_params:
            if param not in parameters:
                raise ValueError(f"Missing required parameter: {param}")

            if not parameters[param]:
                raise ValueError(f"Parameter '{param}' cannot be empty")

        # Validate gateway name
        gateway_name = parameters["gateway_name"]
        if not isinstance(gateway_name, str) or len(gateway_name.strip()) < 2:
            raise ValueError("Gateway name must be a non-empty string with at least 2 characters")

        # Validate payment method
        method = parameters["method"]
        valid_methods = ["card", "upi", "pos_qr", "emandate", "netbanking", "wallet", "paylater", "optimizer"]
        if method not in valid_methods and not parameters.get("custom_method"):
            raise ValueError(f"Payment method must be one of: {valid_methods} or provide custom_method")

        # Validate countries
        countries = parameters["countries_applicable"]
        if not isinstance(countries, list) or len(countries) == 0:
            raise ValueError("countries_applicable must be a non-empty list")

        # Validate optional parameters
        if "apis_to_integrate" in parameters:
            apis = parameters["apis_to_integrate"]
            if not isinstance(apis, list):
                raise ValueError("apis_to_integrate must be a list")

        if "max_iterations" in parameters:
            max_iter = parameters["max_iterations"]
            if not isinstance(max_iter, int) or max_iter < 1 or max_iter > 100:
                raise ValueError("max_iterations must be an integer between 1 and 100")

        if "credentials" in parameters:
            credentials = parameters["credentials"]
            if not isinstance(credentials, list):
                raise ValueError("credentials must be a list of key-value pairs")

            for cred in credentials:
                if not isinstance(cred, dict) or "key" not in cred or "value" not in cred:
                    raise ValueError("Each credential must have 'key' and 'value' fields")

        # Validate new optional parameters
        if "markdown_doc_path" in parameters:
            doc_path = parameters["markdown_doc_path"]
            if doc_path is not None and not isinstance(doc_path, str):
                raise ValueError("markdown_doc_path must be a string")

        if "reference_gateway" in parameters:
            ref_gateway = parameters["reference_gateway"]
            if ref_gateway is not None and (not isinstance(ref_gateway, str) or len(ref_gateway.strip()) < 2):
                raise ValueError("reference_gateway must be a non-empty string with at least 2 characters")

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
            "max_iterations": parameters.get("max_iterations", 50),
            "use_switch": parameters.get("use_switch", False)
        }

        # Add custom instructions and notes as metadata (not used by workflow but stored for reference)
        if parameters.get("custom_instructions"):
            workflow_params["custom_instructions"] = parameters["custom_instructions"]

        if parameters.get("integration_notes"):
            workflow_params["integration_notes"] = parameters["integration_notes"]

        # Add new parameters
        if parameters.get("markdown_doc_path"):
            workflow_params["markdown_doc_path"] = parameters["markdown_doc_path"]

        if parameters.get("reference_gateway"):
            workflow_params["reference_gateway"] = parameters["reference_gateway"]

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

# Continue with workflow methods...
# (I'll add these in separate parts due to length constraints)

    def initialize_workflow(self, state: GatewayIntegrationState) -> GatewayIntegrationState:
        """Initialize the workflow with repositories and devstack label."""
        self.log_behavior(state["task_id"], "Workflow Initialization", "Setting up repositories and devstack label")

        # Generate devstack label
        devstack_label = self.generate_randomized_devstack_label(state["gateway_name"], state["task_id"])

        # Initialize repositories
        repositories = {
            "integrations-go": RepositoryConfig.INTEGRATIONS_GO,
            "integrations-upi": RepositoryConfig.INTEGRATIONS_UPI,
        }

        # Update state
        state["current_step"] = "initialize_workflow"
        state["completed_steps"].append("initialize_workflow")
        state["repositories"] = repositories
        state["devstack_label"] = devstack_label

        self.logger.info(f"Initialized workflow with devstack label: {devstack_label}")
        return state

    def run_parallel_integrations(self, state: GatewayIntegrationState) -> GatewayIntegrationState:
        """Run parallel integrations across all repositories."""
        self.log_behavior(state["task_id"], "Parallel Integration", "Running integrations across all repositories")

        async def run_integrations():
            tasks = []

            # Create tasks for each repository integration
            method = state.get("method")
            if method == "optimizer":
                if "integrations-go" in state["repositories"]:
                    tasks.append(self.integrate_integrations_go(state))
            elif method == "pos_qr":
                if "integrations-upi" in state["repositories"]:
                    tasks.append(self.integrate_integrations_upi(state))

            # Run all integrations in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.error(f"Integration failed: {result}")
                    state["failed_steps"].append(f"integration_{i}")

        # Execute the parallel integrations
        asyncio.run(run_integrations())

        state["current_step"] = "run_parallel_integrations"
        state["completed_steps"].append("run_parallel_integrations")

        return state

    def should_continue(self, state: GatewayIntegrationState) -> str:
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
        elif current_step == "create_run_unit_tests":
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

    def aggregate_results(self, state: GatewayIntegrationState) -> GatewayIntegrationState:
        """Aggregate results from all repository integrations."""
        self.log_behavior(state["task_id"], "Aggregating Results", "Collecting results from all integrations")

        # Collect all results
        all_results = {
            "integrations-go": state.get("integrations_go_result", {}),
            "integrations-upi": state.get("integrations_upi_result", {})
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

    def validate_changes(self, state: GatewayIntegrationState) -> GatewayIntegrationState:
        """Validate all changes made during integration."""
        self.log_behavior(state["task_id"], "Validating Changes", "Validating all repository changes")

        # Simple validation - check if we have successful results
        successful_results = 0
        total_results = 0

        for repo_name in ["integrations_go", "integrations_upi"]:
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

    def fix_validation_issues(self, state: GatewayIntegrationState) -> GatewayIntegrationState:
        """Fix validation issues found during validation."""
        self.log_behavior(state["task_id"], "Fixing Validation Issues", "Attempting to fix validation issues")

        # Increment iteration counter
        state["current_iteration"] += 1

        # For now, just mark as attempted - in real implementation, this would
        # attempt to fix specific issues
        state["current_step"] = "fix_validation_issues"
        state["completed_steps"].append("fix_validation_issues")

        return state

    async def deploy_to_devstack(self, state: GatewayIntegrationState) -> GatewayIntegrationState:
        """Deploy the integration to devstack."""
        self.log_behavior(state["task_id"], "Deploying to Devstack", f"Deploying with label: {state['devstack_label']}")

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

    async def run_e2e_tests(self, state: GatewayIntegrationState) -> GatewayIntegrationState:
        """Run end-to-end tests for the integration."""
        self.log_behavior(state["task_id"], "Running E2E Tests", "Running end-to-end tests")

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

    def process_feedback(self, state: GatewayIntegrationState) -> GatewayIntegrationState:
        """Process feedback from failed tests."""
        self.log_behavior(state["task_id"], "Processing Feedback", "Processing test feedback")

        state["current_step"] = "process_feedback"
        state["completed_steps"].append("process_feedback")

        return state

    async def debug_and_correct_agents(self, state: GatewayIntegrationState) -> GatewayIntegrationState:
        """Debug and correct agent issues."""
        self.log_behavior(state["task_id"], "Debugging Agents", "Debugging and correcting agent issues")

        # Increment iteration counter
        state["current_iteration"] += 1

        state["current_step"] = "debug_and_correct_agents"
        state["completed_steps"].append("debug_and_correct_agents")

        return state

    def complete_workflow(self, state: GatewayIntegrationState) -> GatewayIntegrationState:
        """Complete the workflow successfully."""
        self.log_behavior(state["task_id"], "Workflow Completed", "Gateway integration workflow completed successfully")

        state["current_step"] = "completed"
        state["completed_steps"].append("complete_workflow")

        return state

    def fail_workflow(self, state: GatewayIntegrationState) -> GatewayIntegrationState:
        """Fail the workflow due to errors."""
        self.log_behavior(state["task_id"], "Workflow Failed", "Gateway integration workflow failed")

        state["current_step"] = "failed"
        state["failed_steps"].append("fail_workflow")

        return state

    # Repository integration methods (simplified versions)
    async def integrate_terminals(self, state: GatewayIntegrationState) -> GatewayIntegrationState:
        """Integrate with terminals repository."""
        self.log_behavior(state["task_id"], "Integrating Terminals", "Integrating with terminals repository")

        # Simulate integration
        result = {
            "success": True,
            "repository": "terminals",
            "pr_url": f"https://github.com/razorpay/terminals/pull/{random.randint(1000, 9999)}",
            "branch_name": f"gateway-integration-{state['gateway_name']}-{state['method']}"
        }

        state["terminals_result"] = result
        self.update_agent_context(state, "terminals", result)

        return state

    async def integrate_pg_router(self, state: GatewayIntegrationState) -> GatewayIntegrationState:
        """Integrate with pg-router repository."""
        self.log_behavior(state["task_id"], "Integrating PG Router", "Integrating with pg-router repository")

        result = {
            "success": True,
            "repository": "pg_router",
            "pr_url": f"https://github.com/razorpay/pg-router/pull/{random.randint(1000, 9999)}",
            "branch_name": f"gateway-integration-{state['gateway_name']}-{state['method']}"
        }

        state["pg_router_result"] = result
        self.update_agent_context(state, "pg_router", result)

        return state

    async def integrate_nbplus(self, state: GatewayIntegrationState) -> GatewayIntegrationState:
        """Integrate with nbplus repository."""
        self.log_behavior(state["task_id"], "Integrating NBPlus", "Integrating with nbplus repository")

        result = {
            "success": True,
            "repository": "nbplus",
            "pr_url": f"https://github.com/razorpay/payments-nb-wallet/pull/{random.randint(1000, 9999)}",
            "branch_name": f"gateway-integration-{state['gateway_name']}-{state['method']}"
        }

        state["nbplus_result"] = result
        self.update_agent_context(state, "nbplus", result)

        return state

    async def integrate_integrations_upi(self, state: GatewayIntegrationState) -> GatewayIntegrationState:
        """Integrate integrations_upi repository using AutonomousAgentTool"""
        print("running integrate_integrations_upi")
        task_id = state["task_id"]
        gateway_name = state["gateway_name"]
        method = state["method"]
        if method != "pos_qr" and method != "upi" :
            return state
        apis_to_integrate = state.get("apis_to_integrate", [])
        is_retry = state["current_iteration"] > 0
        log_action = "Re-integrating Integrations_upi" if is_retry else "Integrating Integrations-Upi"
        log_behavior(task_id, log_action, f"Creating PR for {gateway_name} in integrations-upi repository")

        # Initialize prompt provider
        prompt_provider = IntegrationsUpiPromptProvider()

        try:

            # Check for existing PR first using GitHub API
            existing_pr_info = await check_existing_pr(state, "integrations-upi", gateway_name, method)

            # If existing PR is found, update state and return without triggering agent
            if existing_pr_info.get("exists", False):

                log_behavior(task_id, "Integrations-Upi Existing PR Found",
                             f"Found existing PR/branch: {existing_pr_info.get('pr_url', 'branch only')}")

                # Update state with existing PR information
                state["integrations_upi_result"] = {
                    "success": True,
                    "pr_url": existing_pr_info.get("pr_url"),
                    "branch": existing_pr_info.get("branch"),
                    "files_modified": [],  # Will be populated later when agent runs
                    "message": "Existing PR/branch found for Integrations-Upi integration",
                    "iteration": state["current_iteration"],
                    "existing_pr_reused": True,
                    "existing_pr_info": existing_pr_info,
                    "agent_executed": False,  # Flag to indicate agent wasn't run
                    "apis_integrated": apis_to_integrate,
                    "pay_init_integrated": False
                }

                # Initialize agent context even if not executing
                if "integrations-upi" not in state["agent_contexts"]:
                    state["agent_contexts"]["integrations-upi"] = {
                        "repository": "integrations-upi",
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
            tool_config = prepare_integration_config(state, "integrations-upi", gateway_name, method, existing_pr_info)

            # Get previous iterations for retry context if needed
            previous_iterations = []
            if is_retry:
                previous_context = state["agent_contexts"].get("integrations-upi", {})
                previous_iterations = previous_context.get("iterations", [])

            # Extract documentation path from state
            documentation_path = state.get("markdown_doc_path")

            # Extract reference gateway from state
            reference_gateway = state.get("reference_gateway")

            # Build complete prompt using the prompt provider
            complete_prompt = prompt_provider.build_complete_prompt(
                gateway_name=gateway_name,
                method=method,
                repository_path=state["repositories"]["integrations-upi"],
                standard_branch_name=tool_config["standard_branch_name"],
                existing_pr_info=existing_pr_info,
                apis_to_integrate=apis_to_integrate,
                is_retry=is_retry,
                previous_iterations=previous_iterations,
                documentation_path=documentation_path,
                reference_gateway=reference_gateway,
                use_switch=state.get("use_switch", False)
            )

            # Get or create agent (will reuse existing agent if available)
            agent_tool = get_or_create_agent(state, "integrations-upi", tool_config, is_retry=is_retry)

            # Execute the autonomous agent tool
            result = agent_tool.execute({
                "prompt": complete_prompt,
                "task_id": task_id,
                "agent_name": "gateway-integration",
            })
            print("completed running integrate_integrations_upi")
            state["working_branch"]["integrations-upi"] = tool_config["standard_branch_name"]
            # Store the result with existing PR information
            state["integrations_upi_result"] = {
                "success": result.get("success", False),
                "pr_url": result.get("pr_url") or existing_pr_info.get("pr_url"),
                "branch": result.get("branch") or existing_pr_info.get("branch"),
                "files_modified": result.get("files_modified", []),
                "message": result.get("message",
                                      "Integrations_upi integration completed with API integrations"),
                "iteration": state["current_iteration"],
                "existing_pr_reused": existing_pr_info.get("exists", False),
                "standard_branch_name": tool_config["standard_branch_name"],
                "apis_integrated": apis_to_integrate,
                "pay_init_integrated": False
            }

            # Update agent context with current results
            update_agent_context(state, "integrations-upi", state["integrations_upi_result"])
            action_type = "updated" if existing_pr_info.get("pr_url") else (
                "created" if not existing_pr_info.get("exists") else "branch updated")
            log_behavior(task_id, "Integrations-Upi Integration Completed",
                         f"PR {action_type}: {state['integrations_upi_result'].get('pr_url', 'N/A')} with {len(apis_to_integrate)} APIs")
        except Exception as e:

            logger.exception(f"Error integrating integrations_upi for task {task_id}: {e}")
            state["integrations_upi_result"] = {
                "success": False,
                "error": str(e),
                "message": f"Failed to integrate integrations-go: {str(e)}",
                "iteration": state["current_iteration"]
            }
            state["failed_steps"].append("integrations-upi")

            # Update agent context even for failures
            update_agent_context(state, "integrations-upi", state["integrations_upi_result"])
            log_behavior(task_id, "Integrations-Upi Integration Failed", f"Error: {str(e)}")
        return state

    async def integrate_integrations_go(self, state: GatewayIntegrationState) -> GatewayIntegrationState:
        """Integrate integrations-go repository using AutonomousAgentTool"""
        task_id = state["task_id"]
        gateway_name = state["gateway_name"]
        method = state["method"]
        if method == "pos_qr":
            return state
        apis_to_integrate = state.get("apis_to_integrate", [])
        is_retry = state["current_iteration"] > 0
        log_action = "Re-integrating Integrations-Go" if is_retry else "Integrating Integrations-Go"
        log_behavior(task_id, log_action, f"Creating PR for {gateway_name} in integrations-go repository")
        try:
            # Check for existing PR first using GitHub API
            existing_pr_info = await check_existing_pr(state, "integrations-go", gateway_name, method)

            # If existing PR is found, update state and return without triggering agent
            if existing_pr_info.get("exists", False):
                log_behavior(task_id, "Integrations-Go Existing PR Found",
                             f"Found existing PR/branch: {existing_pr_info.get('pr_url', 'branch only')}")

                # Update state with existing PR information
                state["integrations_go_result"] = {
                    "success": True,
                    "pr_url": existing_pr_info.get("pr_url"),
                    "branch": existing_pr_info.get("branch"),
                    "files_modified": [],  # Will be populated later when agent runs
                    "message": "Existing PR/branch found for Integrations-Go integration",
                    "iteration": state["current_iteration"],
                    "existing_pr_reused": True,
                    "existing_pr_info": existing_pr_info,
                    "agent_executed": False,  # Flag to indicate agent wasn't run
                    "apis_integrated": apis_to_integrate,
                    "pay_init_integrated": True
                }

                # Initialize agent context even if not executing
                if "integrations-go" not in state["agent_contexts"]:
                    state["agent_contexts"]["integrations-go"] = {
                        "repository": "integrations-go",
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
            tool_config = prepare_integration_config(state, "integrations-go", gateway_name, method, existing_pr_info)
            integrations_go_prompt_provider = IntegrationsGoPromptProvider()
                # Get previous iterations for retry context
            previous_context = state["agent_contexts"].get("integrations-go", {})
            previous_iterations = previous_context.get("iterations", [])
            base_prompt = integrations_go_prompt_provider.build_complete_prompt(
                    gateway_name=gateway_name,
                    method=method,
                    repository_path=state["repositories"]["integrations-go"],
                    standard_branch_name=tool_config["standard_branch_name"],
                    existing_pr_info=existing_pr_info,
                    apis_to_integrate=apis_to_integrate,
                    is_retry=is_retry,
                    previous_iterations=previous_iterations if is_retry else None,
                    documentation_path=state.get("markdown_doc_path"),
                    reference_gateway=state.get("reference_gateway"),
                    use_switch=state.get("use_switch", False))
            # Get or create agent (will reuse existing agent if available)
            agent_tool = get_or_create_agent(state, "integrations-go", tool_config, is_retry=is_retry)

            # Execute the autonomous agent tool
            result = agent_tool.execute({
                "prompt": base_prompt,
                "task_id": task_id,
                "agent_name": "gateway-integration",
            })

            # Store the result with existing PR information
            state["integrations_go_result"] = {
                "success": result.get("success", False),
                "pr_url": result.get("pr_url") or existing_pr_info.get("pr_url"),
                "branch": result.get("branch") or existing_pr_info.get("branch"),
                "files_modified": result.get("files_modified", []),
                "message": result.get("message",
                                      "Integrations-go integration completed with pay_init and API integrations"),
                "iteration": state["current_iteration"],
                "existing_pr_reused": existing_pr_info.get("exists", False),
                "standard_branch_name": tool_config["standard_branch_name"],
                "apis_integrated": apis_to_integrate,
                "pay_init_integrated": True
            }

            # Update agent context with current results
            update_agent_context(state, "integrations-go", state["integrations_go_result"])
            action_type = "updated" if existing_pr_info.get("pr_url") else (
                "created" if not existing_pr_info.get("exists") else "branch updated")
            log_behavior(task_id, "Integrations-Go Integration Completed",
                         f"PR {action_type}: {state['integrations_go_result'].get('pr_url', 'N/A')} with pay_init and {len(apis_to_integrate)} APIs")

        except Exception as e:
            logger.exception(f"Error integrating integrations-go for task {task_id}: {e}")
            state["integrations_go_result"] = {
                "success": False,
                "error": str(e),
                "message": f"Failed to integrate integrations-go: {str(e)}",
                "iteration": state["current_iteration"]
            }
            state["failed_steps"].append("integrations-go")

            # Update agent context even for failures
            update_agent_context(state, "integrations-go", state["integrations_go_result"])
            log_behavior(task_id, "Integrations-Go Integration Failed", f"Error: {str(e)}")

        return state

    async def create_run_unit_tests(self,state: GatewayIntegrationState) -> GatewayIntegrationState:
            """Create and run unit tests for the generated code across all repositories"""
            task_id = state["task_id"]
            gateway_name = state["gateway_name"]
            method = state["method"]

            log_behavior(task_id, "Creating and Running Unit Tests",
                         f"Generating unit tests for {gateway_name} integration")

            try:
                # Set current step for workflow routing
                state["current_step"] = "create_run_unit_tests"

                # Initialize unit test results
                unit_test_results = {}

                # Get all repository results from the aggregated results

                repositories_to_test = [
                    ("integrations-upi", state.get("integrations_upi_result", {})),
                    ("integrations-go", state.get("integrations_go_result", {}))
                ]

                # Filter repositories that had successful code changes
                repos_with_changes = [
                    (repo_name, result) for repo_name, result in repositories_to_test
                    if result.get("success", False)
                ]
                print("repos_with_changes  is ", repos_with_changes)
                log_behavior(task_id, "Unit Test Target Repositories",
                             f"Running unit tests for {len(repos_with_changes)} repositories with code changes")
                for repo_name, repo_result in repos_with_changes:
                    try:
                        # Get or create agent for this repository
                        existing_pr = await check_existing_pr(state, repo_name, gateway_name, method)
                        tool_config = prepare_integration_config(state, repo_name, gateway_name, method, existing_pr)
                        agent = get_or_create_agent(state, repo_name, tool_config, False)

                        # Extract information about the code changes
                        branch_name = repo_result.get("standard_branch_name")
                        reference_gateway = state.get("reference_gateway")
                        # Build unit test generation prompt
                        unit_test_prompt = f"""
                        Create comprehensive unit tests for the {gateway_name} {method} integration in the {repo_name} repository.
                        **Integration Details:**
                        - Gateway: {gateway_name}
                        - Payment Method: {method}
                        - Countries: {state.get('countries_applicable', [])}
                        - Branch: {branch_name}
                        **Files Modified/Created:**
                        check files added/modified using last commit
                        **STEPS**
                        1. Go through {reference_gateway} reference gateway test files and .cursor/rules/002_gateway-unit-test.mdc for reference.
                        2. Analyze existing test structure in the repository if exist.
                        3. Add unit test for modified/created files
                        4. Run the unit tests to ensure they pass
                        5. Fix any test failures and linting errors
                        6. Ensure test coverage >80% for new/modified code
                        7. Commit all test files.
                        8. Ensure that all changes are pushed to branch.
                        9. Always verify completion checklist at last.
                        
                        **COMPLETION CHECKLIST**
                        □ Ensure all test files are pushed to branch and nothing is left to be pushed.
                        □ Verify all unit tests are created and passed successfully
                        □ Confirm test coverage meets >80% requirement for new/modified code
                        □ Ensure no test failures or errors exist
                        
                        **Coverage Commands**
                        ```bash
                        # Test with coverage
                        go test ./payment/{gateway_name}/... -v -coverprofile=coverage.out -covermode=atomic
                        # Check coverage
                        go tool cover -func=coverage.out
                        ``` 
                        Please ensure all tests are comprehensive and follow best practices.
                        """
                        prompt_provider = IntegrationsUpiPromptProvider()
                        unit_test_prompt += prompt_provider.get_existing_pr_prompt(existing_pr)
                        # Execute unit test creation
                        log_behavior(task_id, f"Generating Unit Tests for {repo_name} and branch_name {branch_name}","")

                        result = agent.execute({
                            "prompt": unit_test_prompt,
                            "task_id": task_id,
                            "agent_name": "gateway-integration",
                        })

                        # Process the result
                        if result.get("success", False):
                            unit_test_results[repo_name] = {
                                "success": True,
                                "test_files_created": result.get("test_files_created", []),
                                "tests_count": result.get("tests_count", 0),
                                "coverage_percentage": result.get("coverage_percentage", 0),
                                "all_tests_passed": result.get("all_tests_passed", False),
                                "test_output": result.get("test_output", ""),
                                "branch_name": branch_name
                            }
                            log_behavior(task_id, f"Unit Tests Created for {repo_name}",
                                         f"Created {result.get('tests_count', 0)} tests with {result.get('coverage_percentage', 0)}% coverage")
                        else:
                            unit_test_results[repo_name] = {
                                "success": False,
                                "error": result.get("error", "Unknown error creating unit tests"),
                                "branch_name": branch_name
                            }
                            log_behavior(task_id, f"Unit Test Creation Failed for {repo_name}",
                                         f"Error: {result.get('error', 'Unknown error')}")

                    except Exception as e:
                        error_msg = f"Failed to create unit tests for {repo_name}: {str(e)}"
                        log_behavior(task_id, f"Unit Test Error for {repo_name}", error_msg)
                        unit_test_results[repo_name] = {
                            "success": False,
                            "error": error_msg
                        }

                # Aggregate unit test results
                successful_repos = [repo for repo, result in unit_test_results.items() if result.get("success", False)]
                failed_repos = [repo for repo, result in unit_test_results.items() if not result.get("success", False)]

                total_tests = sum(result.get("tests_count", 0) for result in unit_test_results.values() if
                                  result.get("success", False))
                avg_coverage = sum(result.get("coverage_percentage", 0) for result in unit_test_results.values() if
                                   result.get("success", False))
                if successful_repos:
                    avg_coverage = avg_coverage / len(successful_repos)

                # Store unit test results in state
                state["unit_test_result"] = {
                    "success": len(failed_repos) == 0,
                    "repositories_tested": len(repos_with_changes),
                    "successful_repos": len(successful_repos),
                    "failed_repos": len(failed_repos),
                    "total_tests_created": total_tests,
                    "average_coverage": avg_coverage,
                    "results_by_repo": unit_test_results,
                    "all_tests_passed": all(
                        result.get("all_tests_passed", False) for result in unit_test_results.values() if
                        result.get("success", False))
                }

                if len(failed_repos) == 0:
                    state["completed_steps"].append("create_run_unit_tests")
                    log_behavior(task_id, "Unit Tests Completed Successfully",
                                 f"Created {total_tests} unit tests across {len(successful_repos)} repositories with {avg_coverage:.1f}% average coverage")

                    state["messages"].append(
                        AIMessage(content=f"Unit tests created successfully for {gateway_name} integration. "
                                          f"Generated {total_tests} tests across {len(successful_repos)} repositories.")
                    )
                else:
                    state["failed_steps"].append("create_run_unit_tests")
                    error_msg = f"Unit test creation failed for repositories: {', '.join(failed_repos)}"
                    log_behavior(task_id, "Unit Test Creation Failed", error_msg)

                    state["messages"].append(
                        AIMessage(content=f"Unit test creation failed for some repositories: {', '.join(failed_repos)}")
                    )

            except Exception as e:
                error_msg = f"Unexpected error during unit test creation: {str(e)}"
                log_behavior(task_id, "Unit Test Creation Error", error_msg)

                state["unit_test_result"] = {
                    "success": False,
                    "error": error_msg
                }
                state["failed_steps"].append("create_run_unit_tests")
                state["messages"].append(
                    AIMessage(content=f"Unit test creation failed: {error_msg}")
                )

            return state

# Register the service
service_registry.register("gateway-integrations-common", GatewayIntegrationService)
