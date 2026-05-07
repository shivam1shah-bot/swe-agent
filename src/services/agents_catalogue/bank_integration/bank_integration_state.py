"""
Bank Integration State Management

Defines the state structure for the LangGraph-based bank integration workflow.
This state tracks progress across multiple services: integrations-go, FTS, Payouts, X-Balance, Terminals, Kube-manifests.
"""

from typing import Dict, Any, List, Optional, TypedDict
from langchain_core.messages import BaseMessage
from src.agents.autonomous_agent import AutonomousAgentTool


class BankIntegrationState(TypedDict):
    """
    State structure for the bank integration workflow.
    
    This state manages the complete lifecycle of integrating a new bank
    across multiple services and repositories.
    """
    # Core identification
    task_id: str
    bank_name: str
    version: str
    branch_name: Optional[str]
    
    # Bank documentation (optional)
    bank_documentation: Optional[str]
    bank_doc_filename: Optional[str]
    
    # Service enablement flags
    enable_integrations_go: bool
    enable_fts: bool
    enable_payouts: bool
    enable_xbalance: bool
    enable_terminals: bool
    enable_kube_manifests: bool
    
    # Workflow tracking
    messages: List[BaseMessage]
    current_step: str
    completed_steps: List[str]
    failed_steps: List[str]
    
    # Repository management
    repositories: Dict[str, str]  # repo_name -> repo_url
    working_branch: Dict[str, str]  # repo_name -> branch_name
    
    # Agent persistence
    agent_instances: Dict[str, AutonomousAgentTool]
    agent_contexts: Dict[str, Dict[str, Any]]
    
    # Service-specific results
    integrations_go_result: Optional[Dict[str, Any]]
    fts_result: Optional[Dict[str, Any]]
    payouts_result: Optional[Dict[str, Any]]
    xbalance_result: Optional[Dict[str, Any]]
    terminals_result: Optional[Dict[str, Any]]
    kube_manifests_result: Optional[Dict[str, Any]]
    
    # Workflow control
    workflow_summary: Dict[str, Any]
    max_iterations: int
    current_iteration: int
    
    # Validation and testing
    validation_result: Optional[Dict[str, Any]]
    unit_test_result: Optional[Dict[str, Any]]
    integration_test_result: Optional[Dict[str, Any]]
    
    # Git and PR management
    pr_urls: List[str]
    git_setup_status: Dict[str, str]  # repo_name -> status
    commit_status: Dict[str, str]  # repo_name -> status
    push_status: Dict[str, str]  # repo_name -> status
    
    # Error handling
    error_messages: List[str]
    retry_count: int
    max_retries: int
    
    # Configuration from server1.py
    routes_to_generate: Optional[Dict[str, bool]]
    filtered_generation_order: Optional[List[Dict]]
    generated_files: Dict[str, str]
    files_with_issues: Optional[List[str]]
    validation_results: Optional[Dict[str, List[str]]]
    previous_validation_results: Optional[Dict[str, List[str]]]
    
    # FTS-specific fields (from server1.py)
    fts_modifications: Optional[str]
    fts_changes_status: Optional[str]
    fts_git_setup_status: Optional[str]
    fts_apply_status: Optional[str]
    fts_commit_status: Optional[str]
    fts_push_status: Optional[str]
    fts_branch_name: Optional[str]
    fts_git_error: Optional[str]
    
    # Payouts-specific fields (from server1.py)
    payouts_modifications: Optional[str]
    payouts_changes_status: Optional[str]
    payouts_apply_status: Optional[str]
    payouts_applied_files: Optional[List[str]]
    payouts_git_setup_status: Optional[str]
    payouts_branch_name: Optional[str]
    payouts_commit_status: Optional[str]
    payouts_pr_branch: Optional[str]
    payouts_error: Optional[str]
    
    # X-Balance-specific fields (from server1.py)
    xbalance_modifications: Optional[str]
    xbalance_changes_status: Optional[str]
    xbalance_apply_status: Optional[str]
    xbalance_applied_files: Optional[List[str]]
    xbalance_git_setup_status: Optional[str]
    xbalance_branch_name: Optional[str]
    xbalance_commit_status: Optional[str]
    xbalance_pr_branch: Optional[str]
    xbalance_error: Optional[str]
    
    # Success criteria
    all_services_completed: bool
    all_prs_created: bool
    pipeline_complete: bool


