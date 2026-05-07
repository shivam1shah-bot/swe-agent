import logging
import os
import json
import time
import asyncio
from datetime import datetime
from typing import Dict, Any, List, TypedDict, Annotated
from dataclasses import dataclass
import hashlib
import random
import string
import requests

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from src.services.agents_catalogue.base_service import BaseAgentsCatalogueService
from src.providers.context import Context
from src.services.agents_catalogue.registry import service_registry
from src.agents.autonomous_agent import AutonomousAgentTool
from src.providers.config_loader import get_config
from src.services.agents_catalogue.gateway_integration.prompt_providers.integrations_prompts import IntegrationsGoPromptProvider
from src.services.agents_catalogue.gateway_integration.prompt_providers.integrations_upi import IntegrationsUpiPromptProvider

class GatewayIntegrationState(TypedDict):
    """State structure for the gateway integration workflow"""

    task_id: str
    gateway_name: str
    method: str
    countries_applicable: List[str]
    messages: Annotated[List[BaseMessage], add_messages]

    # Workflow progress tracking
    current_step: str
    completed_steps: List[str]
    failed_steps: List[str]

    # Repository information
    repositories: Dict[str, str]
    working_branch: Dict[str, str]

    # Agent persistence - NEW: Store agent instances to maintain state
    agent_instances: Dict[str, Any]
    agent_contexts: Dict[str, Dict[str, Any]]

    # Integration parameters
    apis_to_integrate: List[str]
    encryption_algorithm: str
    additional_test_cases: int
    use_switch: bool

    # Documentation and reference parameters
    markdown_doc_path: str
    reference_gateway: str

    # Deployment label - Store the devstack label for consistent usage
    devstack_label: str

    # Step results
    code_changes_result: Dict[str, Any]
    validation_result: Dict[str, Any]
    deployment_result: Dict[str, Any]
    e2e_test_result: Dict[str, Any]
    unit_test_result: Dict[str, Any]

    # Parallel repository results
    integrations_upi_result: Dict[str, Any]
    integrations_go_result: Dict[str, Any]

    # Workflow summary
    workflow_summary: Dict[str, Any]

    # Loop control
    max_iterations: int
    current_iteration: int
    tests_passed: bool