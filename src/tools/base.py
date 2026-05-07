"""
Base Tool module.
This module defines the base class for all tool implementations.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class BaseTool(ABC):
    """
    Base class for all tools.
    
    Tools execute actions requested by the AI Core via the Task Processing Unit.
    """
    # Add a class-level registry to track MCP registrations
    _MCP_REGISTERED = set()
    
    def __init__(self, name: str, description: str, config: Dict[str, Any] = None):
        """
        Initialize the Base Tool.
        
        Args:
            name: Name of the tool
            description: Description of what the tool does
            config: Configuration for the tool
        """
        self.name = name
        self.description = description
        self.config = config or {}
        logger.info(f"Initialized tool: {name}")
    
    # Add helper method to track MCP registration
    @classmethod
    def is_mcp_registered(cls, mcp_name: str) -> bool:
        """Check if an MCP has already been registered by any tool instance."""
        return mcp_name in BaseTool._MCP_REGISTERED
    
    @classmethod
    def mark_mcp_registered(cls, mcp_name: str) -> None:
        """Mark an MCP as registered to avoid redundant registration."""
        BaseTool._MCP_REGISTERED.add(mcp_name)
    
    @abstractmethod
    async def execute(self, params: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute the tool with the given parameters.
        
        Args:
            params: Parameters for the tool execution
            context: Additional context that might be needed
            
        Returns:
            Dict[str, Any]: The result of the tool execution
        """
        pass
    
    @abstractmethod
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """
        Validate the parameters for the tool.
        
        Args:
            params: Parameters to validate
            
        Returns:
            bool: True if parameters are valid, False otherwise
        """
        pass
    
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Get the capabilities of this tool.
        
        Returns:
            Dict[str, Any]: Dictionary of capabilities
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self._get_parameter_schema(),
            "output": self._get_output_schema()
        }
    
    @abstractmethod
    def _get_parameter_schema(self) -> Dict[str, Any]:
        """
        Get the parameter schema for this tool.
        
        Returns:
            Dict[str, Any]: Dictionary describing the parameter schema
        """
        pass
    
    @abstractmethod
    def _get_output_schema(self) -> Dict[str, Any]:
        """
        Get the output schema for this tool.
        
        Returns:
            Dict[str, Any]: Dictionary describing the output schema
        """
        pass
