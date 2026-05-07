"""
Database Creation step for the Foundation Onboarding workflow.

This step handles the provisioning of database resources for the new service.
It creates the database, sets up users, and configures access credentials.
"""

import logging
from typing import Dict, Any

from ..state import FoundationOnboardingState
from ..helper import log_behavior
from .base import BaseFoundationStep

logger = logging.getLogger(__name__)


class DatabaseCreationStep(BaseFoundationStep):
    """
    Database Creation step for Foundation Onboarding workflow.
    
    Responsibilities:
    - Provision database based on configuration (postgres, mysql, etc.)
    - Create database
    - Generate and store connection credentials
    - Configure database for the appropriate environment

    TODO:: We might need to add password to credstash for the service.
    That I feel can be onboarded onto the service team to add.
    """

    def __init__(self):
        """Initialize the database creation step."""
        super().__init__(step_name="database_creation")

    async def execute_step(self, state: FoundationOnboardingState) -> FoundationOnboardingState:
        """
        Execute database provisioning for the new service.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with database information
        """
        task_id = state.get("task_id", "unknown")
        service_name = state.get("service_name", "unknown")
        
        logger.info(f"[DATABASE_CREATION] Starting database provisioning for {service_name}")
        log_behavior(task_id, "Database Creation Started", 
                    f"Provisioning database for service {service_name}")
        
        try:
            # Business logic to be added
            pass
            
        except Exception as e:
            logger.error(f"[DATABASE_CREATION] Failed to provision database: {str(e)}")
            raise

    async def _is_step_execution_allowed(self, state: FoundationOnboardingState) -> bool:
        """
        Check if database creation should be executed.
        
        Database creation might be skipped if:
        - database_config is not provided in parameters
        - skip_database=True in parameters
        
        Args:
            state: Current workflow state
            
        Returns:
            True if step should execute
        """
        input_params = state.get("input_parameters", {})
        
        # If no database config is provided, skip database creation
        if not input_params.get("database_config"):
            logger.info("[DATABASE_CREATION] No database config provided, skipping")
            return False
        
        return True
