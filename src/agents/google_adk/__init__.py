"""
Google ADK Agent module for SWE Agent.

This module provides Google ADK (Agent Development Kit) integration with MCP (Model Context Protocol)
for connecting to external data sources and services.
"""

# Import root_agent from trino_agent for ADK Web compatibility
try:
    from .trino_agent import root_agent
except Exception as e:
    # If initialization fails (missing config/dependencies), create placeholder
    import logging
    logging.getLogger(__name__).warning(f"Could not initialize ADK root_agent: {e}")
    root_agent = None

__all__ = [
    "root_agent"
]
