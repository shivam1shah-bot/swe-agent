"""
Base classes for Foundation Onboarding workflow steps.

Provides common functionality and patterns for sequential workflow steps
including state management, logging, error handling, and agent execution.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any

from ..state import FoundationOnboardingState
from ..helper import log_behavior, generate_branch_name
from ..config import RepositoryConfig

logger = logging.getLogger(__name__)


class BaseWorkflowStep(ABC):
    """
    Abstract base class for all workflow steps.
    
    Defines the interface that all workflow steps must implement.
    """
    
    @abstractmethod
    async def execute(self, state: FoundationOnboardingState) -> FoundationOnboardingState:
        """
        Execute the workflow step.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated workflow state after step execution
        """
        pass


class BaseFoundationStep(BaseWorkflowStep):
    """
    Base class for foundation onboarding steps.
    
    Provides common functionality for steps that interact with external
    services, APIs, or repositories. Handles logging, error management,
    and state updates.
    """
    
    def __init__(self, step_name: str):
        """
        Initialize the foundation step.
        
        Args:
            step_name: Unique identifier for this step
        """
        self.step_name = step_name
    
    async def execute(self, state: FoundationOnboardingState) -> FoundationOnboardingState:
        """
        Execute the foundation step with standard error handling and logging.
        
        This method wraps the step-specific logic with common functionality
        including logging, error handling, and state updates.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated workflow state
        """
        
        task_id = state.get("task_id", "unknown")
        service_name = state.get("service_name", "unknown")
        
        logger.info(f"[FLOW] Starting {self.step_name} step - task_id: {task_id}, service: {service_name}")
        
        try:
            # Check if step execution is allowed based on configuration
            is_allowed = await self._is_step_execution_allowed(state)
            if not is_allowed:
                logger.info(f"[FLOW] Step {self.step_name} skipped - not allowed by configuration")
                return self._mark_step_skipped(state, "Step skipped based on configuration")
            
            log_behavior(task_id, f"{self.step_name} Started", 
                        f"Starting {self.step_name} for service {service_name}")
            
            # Execute step-specific logic
            state = await self.execute_step(state)
            
            log_behavior(task_id, f"{self.step_name} Completed", 
                        f"Completed {self.step_name} for service {service_name}")
            
            logger.info(f"[FLOW] Completed {self.step_name} step successfully")
            return state
            
        except Exception as e:
            error_msg = f"Failed to execute {self.step_name}: {str(e)}"
            logger.error(f"[FLOW] {error_msg}")
            log_behavior(task_id, f"{self.step_name} Failed", error_msg)
            return self._handle_error(state, e)
    
    @abstractmethod
    async def execute_step(self, state: FoundationOnboardingState) -> FoundationOnboardingState:
        """
        Execute the step-specific logic.
        
        This method must be implemented by each concrete step class
        to provide the actual step functionality.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated workflow state
        """
        pass
    
    async def _is_step_execution_allowed(self, state: FoundationOnboardingState) -> bool:
        """
        Check if this step should be executed based on configuration.
        
        Override this method in subclasses to implement step-specific
        skip logic based on input parameters or prior step results.
        
        Args:
            state: Current workflow state
            
        Returns:
            True if step should execute, False to skip
        """
        
        return True
    
    def _mark_step_skipped(self, state: FoundationOnboardingState, reason: str) -> FoundationOnboardingState:
        """
        Mark this step as skipped in the state.
        
        Args:
            state: Current workflow state
            reason: Reason for skipping
            
        Returns:
            Updated state with step marked as skipped
        """
        
        state["skipped_steps"].append(self.step_name)
        state["step_results"][self.step_name] = {
            "skipped": True,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
            "error": None
        }
        return state
    
    def _handle_error(self, state: FoundationOnboardingState, error: Exception) -> FoundationOnboardingState:
        """
        Handle execution errors and update state.
        
        Args:
            state: Current workflow state
            error: Exception that occurred
            
        Returns:
            Updated state with error information
        """
        
        error_msg = str(error)
        
        state["failed_steps"].append(self.step_name)
        state["step_results"][self.step_name] = {
            "success": False,
            "error": error_msg,
            "timestamp": datetime.now().isoformat(),
        }
        
        return state
    
    def _mark_step_success(self, state: FoundationOnboardingState, result: Dict[str, Any]) -> FoundationOnboardingState:
        """
        Mark this step as successfully completed.
        
        Args:
            state: Current workflow state
            result: Step execution result data
            
        Returns:
            Updated state with success information
        """
        
        state["completed_steps"].append(self.step_name)
        state["step_results"][self.step_name] = {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "error": None,
            **result
        }
        
        return state

