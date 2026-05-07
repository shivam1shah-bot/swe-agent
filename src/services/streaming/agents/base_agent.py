"""
Base streaming agent interface.

Defines the interface for agent implementations that can be used in streaming sessions.
This allows for future extensibility to support different AI frameworks.
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Any


class BaseStreamingAgent(ABC):
    """
    Base interface for streaming agents.
    
    This abstract class defines the contract that all agent implementations
    must follow, enabling pluggable agent frameworks for different use cases.
    """
    
    @abstractmethod
    async def process_message(self, message: str, context: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process a user message and yield streaming events.
        
        This method should handle the user's message, interact with the underlying
        AI agent/framework, and yield events as they occur (tool calls, responses, etc.).
        
        Args:
            message: User message to process
            context: Session context including user preferences, conversation history, etc.
            
        Yields:
            Dict[str, Any]: Event data in the format:
                {
                    "event_type": str,  # Type of event (tool_execution_start, agent_message, etc.)
                    "data": dict,       # Event-specific data
                    "timestamp": str,   # ISO timestamp
                    "turn_complete": bool  # Whether this completes the conversation turn
                }
                
        Raises:
            ValueError: If message or context is invalid
            RuntimeError: If agent processing fails
        """
        pass
    
    @abstractmethod
    def get_agent_info(self) -> Dict[str, Any]:
        """
        Get metadata about this agent.
        
        Returns:
            Dict[str, Any]: Agent information including:
                - id: Agent identifier
                - name: Human-readable name
                - description: Agent description
                - framework: Framework name (e.g., 'google_adk', 'langchain')
                - capabilities: List of agent capabilities
                - version: Agent version if applicable
        """
        pass
    
    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> None:
        """
        Initialize the agent with configuration.
        
        This method should set up the agent with any required configuration,
        authentication, or resource initialization.
        
        Args:
            config: Agent-specific configuration
            
        Raises:
            ValueError: If configuration is invalid
            RuntimeError: If initialization fails
        """
        pass
    
    async def cleanup(self) -> None:
        """
        Clean up agent resources.
        
        This method should clean up any resources, connections, or state
        associated with the agent. Default implementation does nothing.
        """
        pass
    
    def get_supported_capabilities(self) -> list[str]:
        """
        Get list of capabilities supported by this agent.
        
        Returns:
            list[str]: List of capability identifiers
        """
        info = self.get_agent_info()
        return info.get("capabilities", [])
    
    def supports_capability(self, capability: str) -> bool:
        """
        Check if agent supports a specific capability.
        
        Args:
            capability: Capability identifier to check
            
        Returns:
            bool: True if capability is supported
        """
        return capability in self.get_supported_capabilities()
    
    def get_framework(self) -> str:
        """
        Get the framework name for this agent.
        
        Returns:
            str: Framework identifier
        """
        info = self.get_agent_info()
        return info.get("framework", "unknown")
