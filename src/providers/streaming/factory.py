"""
Streaming factory.

Factory for creating streaming agents and transports based on configuration.
"""

import importlib
from typing import Dict, Any, Optional, TYPE_CHECKING

from .registry import StreamingRegistry, STREAMING_AGENTS, TRANSPORT_REGISTRY

if TYPE_CHECKING:
    from src.services.streaming.agents.base_agent import BaseStreamingAgent
    from src.services.streaming.transports.base_transport import BaseTransport

try:
    from src.providers.logger import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class StreamingFactory:
    """
    Factory for creating streaming components.
    
    Provides methods to create agents and transports based on registry configuration.
    """
    
    @staticmethod
    def create_agent(agent_id: str, config: Optional[Dict[str, Any]] = None) -> "BaseStreamingAgent":
        """
        Create a streaming agent by ID.
        
        Args:
            agent_id: Agent identifier from registry
            config: Optional configuration override
            
        Returns:
            BaseStreamingAgent: Initialized agent instance
            
        Raises:
            ValueError: If agent ID is unknown or invalid
            RuntimeError: If agent creation fails
        """
        logger.info(f"Creating streaming agent: {agent_id}")
        
        # Get agent configuration from registry
        agent_config = StreamingRegistry.get_agent_by_id(agent_id)
        if not agent_config:
            raise ValueError(f"Unknown agent ID: {agent_id}")
        
        if agent_config.get("status") != "active":
            raise ValueError(f"Agent {agent_id} is not active")
        
        framework = agent_config.get("framework")
        
        try:
            if framework == "google_adk":
                return StreamingFactory._create_adk_agent(agent_config, config)
            else:
                raise ValueError(f"Unsupported agent framework: {framework}")
                
        except Exception as e:
            logger.error(f"Failed to create agent {agent_id}: {e}")
            raise RuntimeError(f"Agent creation failed for {agent_id}: {e}")
    
    @staticmethod
    def create_transport(transport_type: str = "sse", config: Optional[Dict[str, Any]] = None) -> "BaseTransport":
        """
        Create a transport by type.
        
        Args:
            transport_type: Transport type identifier (default: 'sse')
            config: Optional transport configuration
            
        Returns:
            BaseTransport: Transport instance
            
        Raises:
            ValueError: If transport type is unsupported
            RuntimeError: If transport creation fails
        """
        logger.info(f"Creating transport: {transport_type}")
        
        # Validate transport is supported
        if not StreamingRegistry.is_transport_supported(transport_type):
            available = list(StreamingRegistry.get_available_transports().keys())
            raise ValueError(f"Unsupported transport: {transport_type}. Available: {available}")
        
        try:
            if transport_type == "sse":
                return StreamingFactory._create_sse_transport(config)
            else:
                raise ValueError(f"Transport {transport_type} not implemented yet")
                
        except Exception as e:
            logger.error(f"Failed to create transport {transport_type}: {e}")
            raise RuntimeError(f"Transport creation failed for {transport_type}: {e}")
    
    @staticmethod
    def create_session_components(agent_id: str, transport_type: str = "sse", 
                                config: Optional[Dict[str, Any]] = None) -> tuple["BaseStreamingAgent", "BaseTransport"]:
        """
        Create both agent and transport for a streaming session.
        
        Args:
            agent_id: Agent identifier
            transport_type: Transport type (default: 'sse')
            config: Optional configuration for both components
            
        Returns:
            tuple[BaseStreamingAgent, BaseTransport]: Agent and transport instances
            
        Raises:
            ValueError: If agent and transport are incompatible
            RuntimeError: If creation fails
        """
        # Validate compatibility
        if not StreamingRegistry.validate_agent_transport_compatibility(agent_id, transport_type):
            raise ValueError(f"Agent {agent_id} is not compatible with transport {transport_type}")
        
        # Create components
        agent_config = config.get("agent", {}) if config else {}
        transport_config = config.get("transport", {}) if config else {}
        
        agent = StreamingFactory.create_agent(agent_id, agent_config)
        transport = StreamingFactory.create_transport(transport_type, transport_config)
        
        logger.info(f"Created session components: agent={agent_id}, transport={transport_type}")
        return agent, transport
    
    @staticmethod
    def get_default_transport() -> str:
        """
        Get the default transport type.
        
        Returns:
            str: Default transport identifier
        """
        return "sse"
    
    @staticmethod
    def _create_adk_agent(agent_config: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> "BaseStreamingAgent":
        """
        Create Google ADK agent.
        
        Args:
            agent_config: Agent configuration from registry
            config: Optional configuration override
            
        Returns:
            BaseStreamingAgent: ADK agent instance
        """
        from src.services.streaming.agents.adk_agent_adapter import ADKAgentAdapter
        
        module_path = agent_config["module_path"]
        merged_config = {**agent_config.get("config", {}), **(config or {})}
        
        adapter = ADKAgentAdapter(module_path, merged_config)
        logger.debug(f"Created ADK agent adapter for {module_path}")
        
        return adapter
    
    @staticmethod
    def _create_sse_transport(config: Optional[Dict[str, Any]] = None) -> "BaseTransport":
        """
        Create SSE transport.
        
        Args:
            config: Optional transport configuration
            
        Returns:
            BaseTransport: SSE transport instance
        """
        from src.services.streaming.transports.sse_transport import SSETransport
        
        transport = SSETransport()
        logger.debug("Created SSE transport")
        
        return transport
    
    @staticmethod
    def list_available_agents() -> list[Dict[str, Any]]:
        """
        List all available agents.
        
        Returns:
            list[Dict[str, Any]]: List of agent configurations
        """
        return StreamingRegistry.get_agent_list()
    
    @staticmethod
    def list_available_transports() -> list[Dict[str, Any]]:
        """
        List all available transports.
        
        Returns:
            list[Dict[str, Any]]: List of transport configurations
        """
        return StreamingRegistry.get_transport_list()
    
    @staticmethod
    def list_knowledge_agents() -> list[Dict[str, Any]]:
        """
        List available knowledge agents specifically.
        
        Returns:
            list[Dict[str, Any]]: List of knowledge agent configurations
        """
        knowledge_agents = StreamingRegistry.get_knowledge_agents()
        return [
            {
                "id": agent_id,
                "name": config["name"],
                "description": config["description"],
                "capabilities": config["capabilities"]
            }
            for agent_id, config in knowledge_agents.items()
        ]
