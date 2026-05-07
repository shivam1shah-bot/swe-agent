"""
Streaming registry.

Contains registry of available agents and transports for streaming functionality.
"""

from typing import Dict, Any, List, Optional

# Current streaming agents (ADK only)
STREAMING_AGENTS: Dict[str, Dict[str, Any]] = {
    "trino_data_assistant": {
        "id": "trino_data_assistant",
        "name": "Trino Data Assistant",
        "description": "Query and analyze data from Trino databases using SQL. Provides data insights and helps with database exploration.",
        "type": "knowledge_agent",
        "framework": "google_adk",
        "module_path": "src.agents.google_adk.trino_agent",
        "adapter_class": "ADKAgentAdapter",
        "capabilities": [
            "data_query",
            "data_analysis", 
            "sql_execution",
            "database_exploration",
            "query_optimization"
        ],
        "transport_support": ["sse"],
        "status": "active",
        "config": {
            "timeout": 30,
            "max_query_rows": 1000
        }
    }
    # Future agents can be added here:
    # "code_assistant": {
    #     "id": "code_assistant",
    #     "name": "Code Assistant", 
    #     "type": "development_agent",
    #     "framework": "langchain",
    #     "status": "planned"
    # }
}

# Current transports (SSE only)
TRANSPORT_REGISTRY: Dict[str, Dict[str, Any]] = {
    "sse": {
        "id": "sse",
        "name": "Server-Sent Events",
        "description": "HTTP-based streaming using Server-Sent Events",
        "class": "SSETransport",
        "module": "src.services.streaming.transports.sse_transport",
        "supported": True,
        "features": [
            "auto_reconnect",
            "event_ordering",
            "browser_compatible"
        ]
    }
    # Future transports:
    # "websocket": {
    #     "id": "websocket", 
    #     "name": "WebSocket",
    #     "class": "WebSocketTransport",
    #     "module": "src.services.streaming.transports.websocket_transport",
    #     "supported": False
    # }
}


class StreamingRegistry:
    """
    Registry for managing streaming agents and transports.
    
    Provides methods to query and filter available streaming components.
    """
    
    @staticmethod
    def get_available_agents() -> Dict[str, Dict[str, Any]]:
        """
        Get all available streaming agents.
        
        Returns:
            Dict[str, Dict[str, Any]]: Dictionary of agent configurations
        """
        return {k: v for k, v in STREAMING_AGENTS.items() if v.get("status") == "active"}
    
    @staticmethod
    def get_agent_by_id(agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get agent configuration by ID.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Optional[Dict[str, Any]]: Agent configuration or None if not found
        """
        return STREAMING_AGENTS.get(agent_id)
    
    @staticmethod
    def get_agents_by_type(agent_type: str) -> Dict[str, Dict[str, Any]]:
        """
        Get agents filtered by type.
        
        Args:
            agent_type: Type of agents to filter (e.g., 'knowledge_agent', 'development_agent')
            
        Returns:
            Dict[str, Dict[str, Any]]: Filtered agent configurations
        """
        return {
            k: v for k, v in STREAMING_AGENTS.items()
            if v.get("type") == agent_type and v.get("status") == "active"
        }
    
    @staticmethod
    def get_agents_by_framework(framework: str) -> Dict[str, Dict[str, Any]]:
        """
        Get agents filtered by framework.
        
        Args:
            framework: Framework name (e.g., 'google_adk', 'langchain')
            
        Returns:
            Dict[str, Dict[str, Any]]: Filtered agent configurations
        """
        return {
            k: v for k, v in STREAMING_AGENTS.items()
            if v.get("framework") == framework and v.get("status") == "active"
        }
    
    @staticmethod
    def get_knowledge_agents() -> Dict[str, Dict[str, Any]]:
        """
        Get all knowledge agents specifically.
        
        Returns:
            Dict[str, Dict[str, Any]]: Knowledge agent configurations
        """
        return StreamingRegistry.get_agents_by_type("knowledge_agent")
    
    @staticmethod
    def agent_supports_capability(agent_id: str, capability: str) -> bool:
        """
        Check if an agent supports a specific capability.
        
        Args:
            agent_id: Agent identifier
            capability: Capability to check
            
        Returns:
            bool: True if agent supports the capability
        """
        agent = StreamingRegistry.get_agent_by_id(agent_id)
        if not agent:
            return False
        
        capabilities = agent.get("capabilities", [])
        return capability in capabilities
    
    @staticmethod
    def agent_supports_transport(agent_id: str, transport: str) -> bool:
        """
        Check if an agent supports a specific transport.
        
        Args:
            agent_id: Agent identifier
            transport: Transport type to check
            
        Returns:
            bool: True if agent supports the transport
        """
        agent = StreamingRegistry.get_agent_by_id(agent_id)
        if not agent:
            return False
        
        supported_transports = agent.get("transport_support", [])
        return transport in supported_transports
    
    @staticmethod
    def get_available_transports() -> Dict[str, Dict[str, Any]]:
        """
        Get all available transports.
        
        Returns:
            Dict[str, Dict[str, Any]]: Dictionary of transport configurations
        """
        return {k: v for k, v in TRANSPORT_REGISTRY.items() if v.get("supported", False)}
    
    @staticmethod
    def get_transport_by_id(transport_id: str) -> Optional[Dict[str, Any]]:
        """
        Get transport configuration by ID.
        
        Args:
            transport_id: Transport identifier
            
        Returns:
            Optional[Dict[str, Any]]: Transport configuration or None if not found
        """
        return TRANSPORT_REGISTRY.get(transport_id)
    
    @staticmethod
    def is_transport_supported(transport_id: str) -> bool:
        """
        Check if a transport is supported.
        
        Args:
            transport_id: Transport identifier
            
        Returns:
            bool: True if transport is supported
        """
        transport = StreamingRegistry.get_transport_by_id(transport_id)
        return transport is not None and transport.get("supported", False)
    
    @staticmethod
    def validate_agent_transport_compatibility(agent_id: str, transport_id: str) -> bool:
        """
        Validate that an agent and transport are compatible.
        
        Args:
            agent_id: Agent identifier
            transport_id: Transport identifier
            
        Returns:
            bool: True if agent and transport are compatible
        """
        return (
            StreamingRegistry.agent_supports_transport(agent_id, transport_id) and
            StreamingRegistry.is_transport_supported(transport_id)
        )
    
    @staticmethod
    def get_agent_list() -> List[Dict[str, Any]]:
        """
        Get list of available agents with basic info.
        
        Returns:
            List[Dict[str, Any]]: List of agent info dictionaries
        """
        agents = StreamingRegistry.get_available_agents()
        return [
            {
                "id": agent_id,
                "name": config["name"],
                "description": config["description"],
                "type": config["type"],
                "framework": config["framework"],
                "capabilities": config["capabilities"]
            }
            for agent_id, config in agents.items()
        ]
    
    @staticmethod
    def get_transport_list() -> List[Dict[str, Any]]:
        """
        Get list of available transports with basic info.
        
        Returns:
            List[Dict[str, Any]]: List of transport info dictionaries
        """
        transports = StreamingRegistry.get_available_transports()
        return [
            {
                "id": transport_id,
                "name": config["name"],
                "description": config["description"],
                "features": config.get("features", [])
            }
            for transport_id, config in transports.items()
        ]
