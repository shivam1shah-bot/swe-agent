"""
Trino MCP Agent for Google ADK Web.
This agent connects to the Trino MCP server and provides data querying capabilities.
"""

from typing import Optional

from .config import get_trino_config

try:
    from src.providers.logger import get_logger
    logger = get_logger(__name__)
except ImportError:
    # Fallback to standard logging if provider not available
    import logging
    logger = logging.getLogger(__name__)

def create_trino_agent():
    """
    Create and return the Trino MCP Agent.
    
    Returns:
        LlmAgent instance configured for Trino MCP server
    """
    try:
        # Import Google ADK components directly - no conflicts since src/mcp was renamed to src/mcp_server
        # This allows the external 'mcp' PyPI package to be imported without namespace collisions
        from google.adk.agents.llm_agent import LlmAgent
        from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StreamableHTTPConnectionParams
        
        # Load Trino configuration
        trino_config = get_trino_config()
        
        # Configuration values
        trino_mcp_url = trino_config.get("mcp_url")
        agent_model = trino_config.get("model")
        agent_name = trino_config.get("name")
        agent_instruction = trino_config.get("instruction")
        
        logger.info(f"Creating Trino MCP agent with model: {agent_model}")
        logger.info(f"Connecting to MCP server: {trino_mcp_url}")
        
        # Initialize the MCPToolset with Trino MCP server
        trino_toolset = MCPToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=trino_mcp_url
            )
            # Optional: Add tool_filter if you want to limit specific tools
            # tool_filter=['execute_query', 'list_catalogs', 'describe_table']
        )
        
        # Create the LlmAgent
        agent = LlmAgent(
            model=agent_model,
            name=agent_name,
            instruction=agent_instruction,
            tools=[trino_toolset]  # Pass MCPToolset as part of tools list
        )
        
        logger.info(f"Successfully created Trino MCP agent: {agent_name}")
        return agent
        
    except ImportError as e:
        logger.error(f"Failed to import Google ADK components: {e}")
        logger.error("Please ensure Google ADK is installed: pip install google-adk")
        return None
    except Exception as e:
        logger.error(f"Error creating Trino MCP agent: {e}")
        return None

# Create the root_agent that ADK Web will discover
root_agent = create_trino_agent()
