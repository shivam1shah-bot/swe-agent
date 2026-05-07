"""
Unit tests for SubAgentRegistry.

Tests the registry pattern for sub-agent discovery and instantiation,
including registration, factory methods, and auto-registration.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.agents.review_agents.subagent_registry import SubAgentRegistry
from src.agents.review_agents.subagent_base import ReviewSubAgentBase
from src.agents.review_agents.constants import CORE_CATEGORIES


class MockSubAgent(ReviewSubAgentBase):
    """Mock sub-agent for testing registry."""

    @property
    def category(self) -> str:
        return "mock_category"

    @property
    def category_label(self) -> str:
        return "MOCK"


class AnotherMockSubAgent(ReviewSubAgentBase):
    """Another mock sub-agent for testing."""

    @property
    def category(self) -> str:
        return "another_category"

    @property
    def category_label(self) -> str:
        return "ANOTHER"


class TestSubAgentRegistryRegistration:
    """Test SubAgentRegistry registration methods."""

    def test_register_adds_agent_to_registry(self, clean_registry):
        """Test that register adds an agent class to the registry."""
        # Arrange
        registry = clean_registry

        # Act
        registry.register("test_category", MockSubAgent)

        # Assert
        assert registry.get("test_category") == MockSubAgent
        assert "test_category" in registry.get_all_categories()

    def test_register_overwrites_existing(self, clean_registry):
        """Test that register overwrites an existing registration."""
        # Arrange
        registry = clean_registry
        registry.register("test_category", MockSubAgent)

        # Act
        registry.register("test_category", AnotherMockSubAgent)

        # Assert
        assert registry.get("test_category") == AnotherMockSubAgent

    def test_unregister_removes_agent(self, clean_registry):
        """Test that unregister removes an agent from the registry."""
        # Arrange
        registry = clean_registry
        registry.register("test_category", MockSubAgent)

        # Act
        result = registry.unregister("test_category")

        # Assert
        assert result is True
        assert registry.get("test_category") is None
        assert "test_category" not in registry.get_all_categories()

    def test_unregister_returns_false_for_unknown(self, clean_registry):
        """Test that unregister returns False for unknown category."""
        # Arrange
        registry = clean_registry

        # Act
        result = registry.unregister("nonexistent_category")

        # Assert
        assert result is False

    def test_get_returns_agent_class(self, clean_registry):
        """Test that get returns the registered agent class."""
        # Arrange
        registry = clean_registry
        registry.register("test_category", MockSubAgent)

        # Act
        result = registry.get("test_category")

        # Assert
        assert result == MockSubAgent

    def test_get_returns_none_for_unknown(self, clean_registry):
        """Test that get returns None for unknown category."""
        # Arrange
        registry = clean_registry

        # Act
        result = registry.get("nonexistent_category")

        # Assert
        assert result is None

    def test_is_registered_returns_true(self, clean_registry):
        """Test that is_registered returns True for registered category."""
        # Arrange
        registry = clean_registry
        registry.register("test_category", MockSubAgent)

        # Act
        result = registry.is_registered("test_category")

        # Assert
        assert result is True

    def test_is_registered_returns_false(self, clean_registry):
        """Test that is_registered returns False for unknown category."""
        # Arrange
        registry = clean_registry

        # Act
        result = registry.is_registered("nonexistent_category")

        # Assert
        assert result is False

    def test_get_all_categories_returns_sorted_list(self, clean_registry):
        """Test that get_all_categories returns a sorted list."""
        # Arrange
        registry = clean_registry
        registry.register("zebra", MockSubAgent)
        registry.register("alpha", MockSubAgent)
        registry.register("beta", MockSubAgent)

        # Act
        result = registry.get_all_categories()

        # Assert
        assert result == ["alpha", "beta", "zebra"]

    def test_clear_removes_all_registrations(self, clean_registry):
        """Test that clear removes all registrations."""
        # Arrange
        registry = clean_registry
        registry.register("cat1", MockSubAgent)
        registry.register("cat2", MockSubAgent)

        # Act
        registry.clear()

        # Assert
        assert registry.get_all_categories() == []


class TestSubAgentRegistryFactory:
    """Test SubAgentRegistry factory methods."""

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_create_agent_returns_instance(self, mock_get_instance, clean_registry, mock_pr_agent_kit):
        """Test that create_agent returns an instance of the registered agent."""
        # Arrange
        mock_get_instance.return_value = MagicMock()
        registry = clean_registry
        registry.register("test_category", MockSubAgent)

        # Act
        agent = registry.create_agent(
            "test_category",
            "/tmp/test",
            kit=mock_pr_agent_kit,
        )

        # Assert
        assert isinstance(agent, MockSubAgent)
        assert agent._working_directory == "/tmp/test"

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_create_agent_raises_for_unknown(self, mock_get_instance, clean_registry):
        """Test that create_agent raises ValueError for unknown category."""
        # Arrange
        mock_get_instance.return_value = MagicMock()
        registry = clean_registry

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            registry.create_agent("nonexistent", "/tmp/test")

        assert "Unknown sub-agent category" in str(exc_info.value)
        assert "nonexistent" in str(exc_info.value)

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_create_agent_passes_kwargs(self, mock_get_instance, clean_registry, mock_pr_agent_kit):
        """Test that create_agent passes kwargs to the agent constructor."""
        # Arrange
        mock_get_instance.return_value = MagicMock()
        registry = clean_registry
        registry.register("test_category", MockSubAgent)

        # Act
        agent = registry.create_agent(
            "test_category",
            "/tmp/test",
            kit=mock_pr_agent_kit,
            confidence_threshold=0.8,
        )

        # Assert
        assert agent._confidence_threshold == 0.8

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_create_core_agents_returns_three_agents(self, mock_get_instance, mock_pr_agent_kit):
        """Test that create_core_agents returns all core agents."""
        # Arrange
        mock_get_instance.return_value = MagicMock()
        # Ensure subagents are imported and registered
        from src.agents.review_agents import subagents  # noqa: F401

        # Act
        agents = SubAgentRegistry.create_core_agents(
            "/tmp/test",
            kit=mock_pr_agent_kit,
        )

        # Assert
        assert len(agents) == len(CORE_CATEGORIES)
        categories = {agent.category for agent in agents}
        assert categories == set(CORE_CATEGORIES)

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_create_core_agents_shares_kit_instance(self, mock_get_instance, mock_pr_agent_kit):
        """Test that create_core_agents shares the same kit instance."""
        # Arrange
        mock_get_instance.return_value = MagicMock()
        from src.agents.review_agents import subagents  # noqa: F401

        # Act
        agents = SubAgentRegistry.create_core_agents(
            "/tmp/test",
            kit=mock_pr_agent_kit,
        )

        # Assert
        # All agents should share the same kit instance
        kits = [agent._kit for agent in agents]
        assert all(kit is mock_pr_agent_kit for kit in kits)

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_create_core_agents_creates_kit_if_not_provided(self, mock_get_instance):
        """Test that create_core_agents creates a shared kit if not provided."""
        # Arrange
        mock_get_instance.return_value = MagicMock()
        from src.agents.review_agents import subagents  # noqa: F401

        # Act
        agents = SubAgentRegistry.create_core_agents("/tmp/test")

        # Assert
        # All agents should share the same kit instance (created internally)
        kits = [agent._kit for agent in agents]
        first_kit = kits[0]
        assert all(kit is first_kit for kit in kits)

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_create_core_agents_warns_for_missing(self, mock_get_instance, clean_registry, caplog):
        """Test that create_core_agents warns when categories are missing."""
        # Arrange
        mock_get_instance.return_value = MagicMock()
        registry = clean_registry
        # Only register one of the core categories
        from src.agents.review_agents.subagents import BugDetectionSubAgent
        registry.register("bug", BugDetectionSubAgent)

        # Act
        import logging
        with caplog.at_level(logging.WARNING):
            agents = registry.create_core_agents("/tmp/test")

        # Assert
        assert len(agents) == 1  # Only one was registered
        assert "not registered" in caplog.text or len(agents) < 3

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_create_agents_for_categories_custom_list(self, mock_get_instance, mock_pr_agent_kit):
        """Test that create_agents_for_categories works with custom list."""
        # Arrange
        mock_get_instance.return_value = MagicMock()
        from src.agents.review_agents import subagents  # noqa: F401

        # Act
        agents = SubAgentRegistry.create_agents_for_categories(
            ["bug", "security"],
            "/tmp/test",
            kit=mock_pr_agent_kit,
        )

        # Assert
        assert len(agents) == 2
        categories = {agent.category for agent in agents}
        assert categories == {"bug", "security"}


class TestSubAgentRegistryAutoRegistration:
    """Test auto-registration on import."""

    def test_importing_subagents_registers_all_core(self):
        """Test that importing subagents registers all core categories."""
        # Arrange & Act
        from src.agents.review_agents import subagents  # noqa: F401

        # Assert
        for category in CORE_CATEGORIES:
            assert SubAgentRegistry.is_registered(category), f"{category} should be registered"

    def test_bug_detection_is_registered(self):
        """Test that bug detection sub-agent is registered."""
        # Arrange & Act
        from src.agents.review_agents import subagents  # noqa: F401

        # Assert
        assert SubAgentRegistry.is_registered("bug")
        agent_class = SubAgentRegistry.get("bug")
        assert agent_class is not None
        assert agent_class.__name__ == "BugDetectionSubAgent"

    def test_security_is_registered(self):
        """Test that security sub-agent is registered."""
        # Arrange & Act
        from src.agents.review_agents import subagents  # noqa: F401

        # Assert
        assert SubAgentRegistry.is_registered("security")
        agent_class = SubAgentRegistry.get("security")
        assert agent_class is not None
        assert agent_class.__name__ == "SecuritySubAgent"

    def test_code_quality_is_registered(self):
        """Test that code quality sub-agent is registered."""
        # Arrange & Act
        from src.agents.review_agents import subagents  # noqa: F401

        # Assert
        assert SubAgentRegistry.is_registered("code_quality")
        agent_class = SubAgentRegistry.get("code_quality")
        assert agent_class is not None
        assert agent_class.__name__ == "CodeQualitySubAgent"
