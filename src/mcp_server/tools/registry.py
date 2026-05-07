"""
MCP Tool Registry for managing and executing MCP tools.

Provides centralized registration, discovery, and execution of MCP tools
organized by functional domains.
"""

import asyncio
from typing import Dict, List, Any, Optional, Type
from abc import ABC, abstractmethod

from src.providers.logger import Logger
from .base_tool import BaseMCPTool


class MCPToolRegistry:
    """
    MCP Tool Registry that uses HTTP client to call API service.
    
    This registry creates tool instances that proxy requests to the
    SWE Agent API service via HTTP instead of direct service access.
    """
    
    def __init__(self, api_client):
        """
        Initialize the tool registry with API client.
        
        Args:
            api_client: HTTP client for calling SWE Agent API service
        """
        self.logger = Logger("MCPToolRegistry")
        self.api_client = api_client
        self.tools: Dict[str, BaseMCPTool] = {}
        self._initialized = False
    
    async def initialize(self):
        """Initialize the registry and register all available tools."""
        if self._initialized:
            return
        
        try:
            # Register health tools
            await self._register_health_tools()
            
            # Register task tools
            await self._register_task_tools()
            
            # Register agents catalogue tools
            await self._register_agents_tools()
            
            # Register admin tools
            await self._register_admin_tools()
            
            self._initialized = True
            self.logger.info("MCP tool registry initialized", tool_count=len(self.tools))
            
        except Exception as e:
            self.logger.error("Failed to initialize tool registry", error=str(e))
            raise
    
    async def _register_health_tools(self):
        """Register health domain tools."""
        try:
            from .health.overall_health import OverallHealthTool
            
            health_tools = [
                OverallHealthTool(self.api_client)
            ]
            
            for tool in health_tools:
                await self.register_tool(tool)
                
            self.logger.info("Registered health tools", count=len(health_tools))
            
        except ImportError as e:
            self.logger.warning("Some health tools could not be imported", error=str(e))
        except Exception as e:
            self.logger.error("Error registering health tools", error=str(e))
            raise
    
    async def _register_task_tools(self):
        """Register task domain tools."""
        try:
            from .tasks.get_task import GetTaskTool
            from .tasks.list_tasks import ListTasksTool
            from .tasks.get_task_execution_logs import GetTaskExecutionLogsTool
            
            task_tools = [
                GetTaskTool(self.api_client),
                ListTasksTool(self.api_client),
                GetTaskExecutionLogsTool(self.api_client)
            ]
            
            for tool in task_tools:
                await self.register_tool(tool)
                
            self.logger.info("Registered task tools", count=len(task_tools))
            
        except ImportError as e:
            self.logger.warning("Some task tools could not be imported", error=str(e))
        except Exception as e:
            self.logger.error("Error registering task tools", error=str(e))
            raise
    
    async def _register_agents_tools(self):
        """Register agents catalogue domain tools."""
        try:
            from .agents_catalogue.list_agents_catalogue_services import ListAgentsCatalogueServicesTool
            from .agents_catalogue.get_agents_catalogue_items import GetAgentsCatalogueItemsTool
            from .agents_catalogue.get_agents_catalogue_config import GetAgentsCatalogueConfigTool
            
            agents_tools = [
                ListAgentsCatalogueServicesTool(self.api_client),
                GetAgentsCatalogueItemsTool(self.api_client),
                GetAgentsCatalogueConfigTool(self.api_client)
            ]
            
            for tool in agents_tools:
                await self.register_tool(tool)
                
            self.logger.info("Registered agents catalogue tools", count=len(agents_tools))
            
        except ImportError as e:
            self.logger.warning("Some agents catalogue tools could not be imported", error=str(e))
        except Exception as e:
            self.logger.error("Error registering agents catalogue tools", error=str(e))
            raise
    
    async def _register_admin_tools(self):
        """Register admin domain tools."""
        try:
            # No admin tools currently registered
            admin_tools = []
            
            for tool in admin_tools:
                await self.register_tool(tool)
                
            self.logger.info("Registered admin tools", count=len(admin_tools))
            
        except ImportError as e:
            self.logger.warning("Some admin tools could not be imported", error=str(e))
        except Exception as e:
            self.logger.error("Error registering admin tools", error=str(e))
            raise
    
    async def register_tool(self, tool: BaseMCPTool):
        """
        Register a tool in the registry.
        
        Args:
            tool: Tool instance to register
        """
        if not isinstance(tool, BaseMCPTool):
            raise ValueError(f"Tool must be an instance of BaseMCPTool, got {type(tool)}")
        
        if tool.name in self.tools:
            self.logger.warning("Tool already registered, replacing", tool_name=tool.name)
        
        self.tools[tool.name] = tool
        self.logger.debug("Registered tool", tool_name=tool.name, domain=tool.domain)
    
    def unregister_tool(self, tool_name: str) -> bool:
        """
        Unregister a tool from the registry.
        
        Args:
            tool_name: Name of the tool to unregister
            
        Returns:
            True if tool was unregistered
        """
        if tool_name in self.tools:
            del self.tools[tool_name]
            self.logger.info("Unregistered tool", tool_name=tool_name)
            return True
        return False
    
    def get_tool(self, tool_name: str) -> Optional[BaseMCPTool]:
        """
        Get a tool by name.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Tool instance or None if not found
        """
        return self.tools.get(tool_name)
    
    def get_registered_tools(self) -> Dict[str, BaseMCPTool]:
        """
        Get all registered tools.
        
        Returns:
            Dictionary of tool name to tool instance
        """
        return self.tools.copy()
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        List all registered tools in MCP format.
        
        Returns:
            List of tool definitions for MCP
        """
        if not self._initialized:
            await self.initialize()
        
        tools = []
        for tool in self.tools.values():
            tool_def = {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema
            }
            
            # Add optional annotations
            if hasattr(tool, 'annotations') and tool.annotations:
                tool_def["annotations"] = tool.annotations
            
            tools.append(tool_def)
        
        return tools
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Execute a tool with the given arguments.
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Arguments to pass to the tool
            
        Returns:
            Tool execution result
            
        Raises:
            ValueError: If tool is not found
            Exception: If tool execution fails
        """
        if not self._initialized:
            await self.initialize()
        
        tool = self.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Tool '{tool_name}' not found")
        
        self.logger.info("Executing tool", tool_name=tool_name, arguments=arguments)
        
        try:
            # Execute the tool
            result = await tool.execute(**arguments)
            
            self.logger.info("Tool execution completed", tool_name=tool_name, success=True)
            return result
            
        except Exception as e:
            self.logger.error("Tool execution failed", tool_name=tool_name, error=str(e))
            raise
    
    def get_tools_by_domain(self, domain: str) -> List[BaseMCPTool]:
        """
        Get tools by domain.
        
        Args:
            domain: Domain name (e.g., "health", "tasks")
            
        Returns:
            List of tools in the specified domain
        """
        return [tool for tool in self.tools.values() if tool.domain == domain]
    
    def get_available_domains(self) -> List[str]:
        """
        Get list of available domains.
        
        Returns:
            List of domain names
        """
        domains = set()
        for tool in self.tools.values():
            domains.add(tool.domain)
        return sorted(list(domains))
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """
        Get registry statistics.
        
        Returns:
            Dictionary with registry statistics
        """
        domain_counts = {}
        for tool in self.tools.values():
            domain = tool.domain
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
        
        return {
            "total_tools": len(self.tools),
            "domains": list(domain_counts.keys()),
            "tools_by_domain": domain_counts,
            "initialized": self._initialized
        } 