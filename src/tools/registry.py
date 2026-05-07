"""
Tool Registry module.
This module manages the registration and retrieval of tools.
"""

import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class ToolRegistry:
    """
    Registry for Tools.
    Manages the registration and retrieval of tools.
    """
    
    def __init__(self):
        """Initialize the Tool Registry."""
        self.tools = {}
        logger.info("Tool Registry initialized")
    
    def register_tool(self, tool_name: str, tool_instance: Any) -> None:
        """
        Register a tool instance.
        
        Args:
            tool_name: The name of the tool
            tool_instance: The tool instance
        """
        self.tools[tool_name] = tool_instance
        logger.info(f"Registered tool: {tool_name}")
    
    def get_tool(self, tool_name: str) -> Optional[Any]:
        """
        Get a tool instance by name.
        
        Args:
            tool_name: The name of the tool to retrieve
            
        Returns:
            Optional[Any]: The tool instance, or None if not found
        """
        tool = self.tools.get(tool_name)
        if not tool:
            logger.warning(f"Tool not found: {tool_name}")
        return tool
    
    def get_all_tools(self) -> Dict[str, Any]:
        """
        Get all registered tools.
        
        Returns:
            Dict[str, Any]: Dictionary of all registered tools
        """
        return self.tools
    
    def get_available_tool_names(self) -> List[str]:
        """
        Get a list of all available tool names.
        
        Returns:
            List[str]: List of available tool names
        """
        return list(self.tools.keys())
    
    def get_tools_info(self) -> List[Dict[str, Any]]:
        """
        Get information about all registered tools.
        
        Returns:
            List[Dict[str, Any]]: List of tool information dictionaries
        """
        tools_info = []
        for name, tool in self.tools.items():
            tools_info.append({
                "name": name,
                "description": getattr(tool, "description", "No description available"),
                "capabilities": tool.get_capabilities() if hasattr(tool, "get_capabilities") else {}
            })
        return tools_info

    def register_default_tools(self) -> None:
        """Register default tools in the registry."""
        try:
            # Register GitHub CLI Tool
            from .github_cli import GitHubCLITool
            github_cli_tool = GitHubCLITool()
            self.register_tool("github_cli", github_cli_tool)
            
            # Register Linting Tool
            from .static_analysis import LintingTool
            linting_tool = LintingTool()
            self.register_tool("linting", linting_tool)
            
            logger.info("Default tools registered successfully")
            
        except Exception as e:
            logger.error(f"Failed to register default tools: {e}")

# Global tool registry instance
global_tool_registry = ToolRegistry()

def get_global_tool_registry() -> ToolRegistry:
    """Get the global tool registry instance."""
    return global_tool_registry

def register_github_cli_tool(config: Dict[str, Any] = None) -> None:
    """Register the GitHub CLI tool in the global registry."""
    try:
        from .github_cli import GitHubCLITool
        github_cli_tool = GitHubCLITool(config)
        global_tool_registry.register_tool("github_cli", github_cli_tool)
        logger.info("GitHub CLI tool registered in global registry")
    except Exception as e:
        logger.error(f"Failed to register GitHub CLI tool: {e}")

def get_github_cli_tool() -> Optional[Any]:
    """Get the GitHub CLI tool from the global registry."""
    return global_tool_registry.get_tool("github_cli")
