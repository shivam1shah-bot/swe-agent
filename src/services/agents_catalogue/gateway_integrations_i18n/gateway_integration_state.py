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
from src.agents.autonomous_agent import AutonomousAgentTool
from src.providers.config_loader import get_config

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
    repositories: Dict[str, str]  # repo_name -> repo_url
    
    # Agent persistence - NEW: Store agent instances to maintain state
    agent_instances: Dict[str, Any]  # repo_name -> AutonomousAgentTool instance
    agent_contexts: Dict[str, Dict[str, Any]]  # repo_name -> context data
    
    # Integration parameters
    apis_to_integrate: List[str]
    encryption_algorithm: str
    additional_test_cases: int
    
    # Deployment label - Store the devstack label for consistent usage
    devstack_label: str
    
    # Step results
    code_changes_result: Dict[str, Any]
    validation_result: Dict[str, Any]
    deployment_result: Dict[str, Any]
    e2e_test_result: Dict[str, Any]
    
    # Parallel repository results
    terminals_result: Dict[str, Any]
    pg_router_result: Dict[str, Any]
    nbplus_result: Dict[str, Any]
    mozart_result: Dict[str, Any]
    integrations_go_result: Dict[str, Any]
    terraform_kong_result: Dict[str, Any]
    proto_result: Dict[str, Any]
    api_result: Dict[str, Any]
    
    # Loop control
    max_iterations: int
    current_iteration: int
    tests_passed: bool

@dataclass
class GatewayCredential:
    """Gateway credential key-value pair."""
    key: str
    value: str
