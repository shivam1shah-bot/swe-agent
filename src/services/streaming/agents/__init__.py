"""
Agent layer package.

Contains agent adapters for different frameworks that can be used in streaming sessions.
"""

from .base_agent import BaseStreamingAgent
from .adk_agent_adapter import ADKAgentAdapter

__all__ = [
    "BaseStreamingAgent",
    "ADKAgentAdapter"
]
