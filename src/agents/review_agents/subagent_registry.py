"""
Registry for dynamic sub-agent discovery and instantiation.

Provides a central registry pattern for managing review sub-agents,
enabling extensibility and factory-based creation of agent instances.
"""

import logging
from typing import Dict, List, Optional, Type

from pr_prompt_kit import PRAgentKit

from src.agents.review_agents.constants import CORE_CATEGORIES

logger = logging.getLogger(__name__)

# Forward declaration to avoid circular imports
# The actual type is defined in subagent_base.py
ReviewSubAgentBase = "ReviewSubAgentBase"


class SubAgentRegistry:
    """
    Registry for dynamic sub-agent discovery and instantiation.

    This class provides a central registry for all review sub-agents,
    allowing dynamic registration, discovery, and factory-based creation.

    Usage:
        # Register a sub-agent (typically done at module import)
        SubAgentRegistry.register("bug", BugDetectionSubAgent)

        # Create a single agent
        agent = SubAgentRegistry.create_agent("bug", "/path/to/repo")

        # Create all core agents for parallel execution
        agents = SubAgentRegistry.create_core_agents("/path/to/repo")

    Thread Safety:
        The registry uses class-level state and should be populated
        at import time. Runtime modifications should be avoided in
        multi-threaded contexts.
    """

    _registry: Dict[str, Type] = {}

    @classmethod
    def register(cls, category: str, agent_class: Type) -> None:
        """
        Register a sub-agent class for a category.

        Args:
            category: The category identifier (e.g., 'bug', 'security')
            agent_class: The sub-agent class to register

        Example:
            SubAgentRegistry.register("bug", BugDetectionSubAgent)
        """
        if category in cls._registry:
            logger.warning(
                f"Overwriting existing registration for category '{category}'"
            )
        cls._registry[category] = agent_class
        logger.debug(f"Registered sub-agent '{agent_class.__name__}' for category '{category}'")

    @classmethod
    def unregister(cls, category: str) -> bool:
        """
        Unregister a sub-agent class.

        Args:
            category: The category to unregister

        Returns:
            True if the category was registered and removed, False otherwise
        """
        if category in cls._registry:
            del cls._registry[category]
            logger.debug(f"Unregistered sub-agent for category '{category}'")
            return True
        return False

    @classmethod
    def get(cls, category: str) -> Optional[Type]:
        """
        Get a sub-agent class by category.

        Args:
            category: The category identifier

        Returns:
            The sub-agent class if registered, None otherwise
        """
        return cls._registry.get(category)

    @classmethod
    def get_all_categories(cls) -> List[str]:
        """
        List all registered categories.

        Returns:
            Sorted list of registered category names
        """
        return sorted(cls._registry.keys())

    @classmethod
    def is_registered(cls, category: str) -> bool:
        """
        Check if a category is registered.

        Args:
            category: The category to check

        Returns:
            True if the category has a registered sub-agent
        """
        return category in cls._registry

    @classmethod
    def create_agent(
        cls,
        category: str,
        working_directory: str,
        kit: Optional[PRAgentKit] = None,
        confidence_threshold: float = 0.6,
    ) -> "ReviewSubAgentBase":
        """
        Factory method to create a sub-agent instance.

        Args:
            category: The category of sub-agent to create
            working_directory: Directory where Claude Code CLI will execute
            kit: Optional PRAgentKit instance (shared across agents)
            confidence_threshold: Minimum confidence for suggestions

        Returns:
            An instance of the registered sub-agent class

        Raises:
            ValueError: If the category is not registered
        """
        agent_class = cls._registry.get(category)
        if agent_class is None:
            available = ", ".join(cls.get_all_categories())
            raise ValueError(
                f"Unknown sub-agent category: '{category}'. "
                f"Available categories: {available or 'none'}"
            )

        return agent_class(
            working_directory=working_directory,
            kit=kit,
            confidence_threshold=confidence_threshold,
        )

    @classmethod
    def create_core_agents(
        cls,
        working_directory: str,
        kit: Optional[PRAgentKit] = None,
        confidence_threshold: float = 0.6,
    ) -> List["ReviewSubAgentBase"]:
        """
        Create instances of all core sub-agents.

        This is the primary factory method for parallel execution scenarios,
        creating one agent per core category (bug, security, code_quality).

        Args:
            working_directory: Directory where Claude Code CLI will execute
            kit: Optional PRAgentKit instance (shared across all agents)
            confidence_threshold: Minimum confidence for suggestions

        Returns:
            List of sub-agent instances for all core categories

        Raises:
            ValueError: If any core category is not registered
        """
        # Use shared kit instance for efficiency
        shared_kit = kit or PRAgentKit()

        agents = []
        missing_categories = []

        for category in CORE_CATEGORIES:
            if not cls.is_registered(category):
                missing_categories.append(category)
                continue

            agent = cls.create_agent(
                category=category,
                working_directory=working_directory,
                kit=shared_kit,
                confidence_threshold=confidence_threshold,
            )
            agents.append(agent)

        if missing_categories:
            logger.warning(
                f"Some core categories are not registered: {missing_categories}. "
                f"Import the subagents package to register them."
            )

        return agents

    @classmethod
    def create_agents_for_categories(
        cls,
        categories: List[str],
        working_directory: str,
        kit: Optional[PRAgentKit] = None,
        confidence_threshold: float = 0.6,
    ) -> List["ReviewSubAgentBase"]:
        """
        Create sub-agent instances for specific categories.

        Useful for creating a subset of agents or custom category combinations.

        Args:
            categories: List of category names to create agents for
            working_directory: Directory where Claude Code CLI will execute
            kit: Optional PRAgentKit instance (shared across all agents)
            confidence_threshold: Minimum confidence for suggestions

        Returns:
            List of sub-agent instances for the specified categories

        Raises:
            ValueError: If any specified category is not registered
        """
        shared_kit = kit or PRAgentKit()
        agents = []

        for category in categories:
            agent = cls.create_agent(
                category=category,
                working_directory=working_directory,
                kit=shared_kit,
                confidence_threshold=confidence_threshold,
            )
            agents.append(agent)

        return agents

    @classmethod
    def clear(cls) -> None:
        """
        Clear all registrations.

        Primarily used for testing purposes.
        """
        cls._registry.clear()
        logger.debug("Cleared all sub-agent registrations")
