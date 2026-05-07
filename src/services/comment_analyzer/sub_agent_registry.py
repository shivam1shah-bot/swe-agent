"""
Sub-Agent Registry

Manages registration and instantiation of different sub-agent types.
"""

import logging
from typing import Dict, Any, Type, Optional

from src.services.comment_analyzer.sub_agent_base import SubAgentBase

logger = logging.getLogger(__name__)


class SubAgentRegistry:
    """Registry for sub-agent implementations"""

    _registry: Dict[str, Type[SubAgentBase]] = {}

    @classmethod
    def register(cls, name: str, sub_agent_class: Type[SubAgentBase]):
        """
        Register a sub-agent implementation.

        Args:
            name: Name of the sub-agent (e.g., "i18n", "security")
            sub_agent_class: Class that implements SubAgentBase
        """
        cls._registry[name] = sub_agent_class
        logger.info(f"Registered sub-agent: {name} -> {sub_agent_class.__name__}")

    @classmethod
    def create(
        cls,
        name: str,
        config: Dict[str, Any],
        github_token: str,
        repository: str,
        pr_number: int
    ) -> Optional[SubAgentBase]:
        """
        Create a sub-agent instance.

        Args:
            name: Name of the sub-agent to create
            config: Configuration for the sub-agent
            github_token: GitHub token
            repository: Repository in owner/repo format
            pr_number: PR number

        Returns:
            Sub-agent instance or None if not found
        """
        if name not in cls._registry:
            logger.error(f"Sub-agent '{name}' not found in registry")
            logger.info(f"Available sub-agents: {list(cls._registry.keys())}")
            return None

        sub_agent_class = cls._registry[name]
        logger.info(f"Creating sub-agent: {name} ({sub_agent_class.__name__})")

        return sub_agent_class(
            config=config,
            github_token=github_token,
            repository=repository,
            pr_number=pr_number
        )

    @classmethod
    def list_available(cls) -> list:
        """List all registered sub-agents"""
        return list(cls._registry.keys())
