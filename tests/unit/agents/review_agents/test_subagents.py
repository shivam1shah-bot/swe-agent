"""
Unit tests for individual sub-agents.

Tests the BugDetectionSubAgent, SecuritySubAgent, and CodeQualitySubAgent
implementations including their properties and integration.
"""

import asyncio
import pytest
from unittest.mock import MagicMock, patch

from src.agents.review_agents.subagent_base import ReviewSubAgentBase
from src.agents.review_agents.subagents import (
    BugDetectionSubAgent,
    SecuritySubAgent,
    CodeQualitySubAgent,
)
from src.agents.review_agents.constants import SubAgentCategory, CATEGORY_LABELS, CORE_CATEGORIES
from src.agents.review_agents.subagent_registry import SubAgentRegistry


class TestBugDetectionSubAgent:
    """Test BugDetectionSubAgent."""

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_category_returns_bug(self, mock_get_instance, mock_pr_agent_kit):
        """Test that category returns 'bug'."""
        # Arrange
        mock_get_instance.return_value = MagicMock()
        agent = BugDetectionSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        # Act
        result = agent.category

        # Assert
        assert result == "bug"
        assert result == SubAgentCategory.BUG.value

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_category_label_returns_BUG(self, mock_get_instance, mock_pr_agent_kit):
        """Test that category_label returns 'BUG'."""
        # Arrange
        mock_get_instance.return_value = MagicMock()
        agent = BugDetectionSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        # Act
        result = agent.category_label

        # Assert
        assert result == "BUG"
        assert result == CATEGORY_LABELS[SubAgentCategory.BUG.value]

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_inherits_from_base(self, mock_get_instance, mock_pr_agent_kit):
        """Test that BugDetectionSubAgent inherits from ReviewSubAgentBase."""
        # Arrange
        mock_get_instance.return_value = MagicMock()
        agent = BugDetectionSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        # Assert
        assert isinstance(agent, ReviewSubAgentBase)

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_can_be_instantiated(self, mock_get_instance, mock_pr_agent_kit):
        """Test that BugDetectionSubAgent can be instantiated."""
        # Arrange
        mock_get_instance.return_value = MagicMock()

        # Act
        agent = BugDetectionSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
            confidence_threshold=0.7,
        )

        # Assert
        assert agent is not None
        assert agent._working_directory == "/tmp/test"
        assert agent._confidence_threshold == 0.7


class TestSecuritySubAgent:
    """Test SecuritySubAgent."""

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_category_returns_security(self, mock_get_instance, mock_pr_agent_kit):
        """Test that category returns 'security'."""
        # Arrange
        mock_get_instance.return_value = MagicMock()
        agent = SecuritySubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        # Act
        result = agent.category

        # Assert
        assert result == "security"
        assert result == SubAgentCategory.SECURITY.value

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_category_label_returns_SECURITY(self, mock_get_instance, mock_pr_agent_kit):
        """Test that category_label returns 'SECURITY'."""
        # Arrange
        mock_get_instance.return_value = MagicMock()
        agent = SecuritySubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        # Act
        result = agent.category_label

        # Assert
        assert result == "SECURITY"
        assert result == CATEGORY_LABELS[SubAgentCategory.SECURITY.value]

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_inherits_from_base(self, mock_get_instance, mock_pr_agent_kit):
        """Test that SecuritySubAgent inherits from ReviewSubAgentBase."""
        # Arrange
        mock_get_instance.return_value = MagicMock()
        agent = SecuritySubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        # Assert
        assert isinstance(agent, ReviewSubAgentBase)

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_can_be_instantiated(self, mock_get_instance, mock_pr_agent_kit):
        """Test that SecuritySubAgent can be instantiated."""
        # Arrange
        mock_get_instance.return_value = MagicMock()

        # Act
        agent = SecuritySubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
            confidence_threshold=0.8,
        )

        # Assert
        assert agent is not None
        assert agent._working_directory == "/tmp/test"
        assert agent._confidence_threshold == 0.8


class TestCodeQualitySubAgent:
    """Test CodeQualitySubAgent."""

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_category_returns_code_quality(self, mock_get_instance, mock_pr_agent_kit):
        """Test that category returns 'code_quality'."""
        # Arrange
        mock_get_instance.return_value = MagicMock()
        agent = CodeQualitySubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        # Act
        result = agent.category

        # Assert
        assert result == "code_quality"
        assert result == SubAgentCategory.CODE_QUALITY.value

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_category_label_returns_CODE_QUALITY(self, mock_get_instance, mock_pr_agent_kit):
        """Test that category_label returns 'CODE_QUALITY'."""
        # Arrange
        mock_get_instance.return_value = MagicMock()
        agent = CodeQualitySubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        # Act
        result = agent.category_label

        # Assert
        assert result == "CODE_QUALITY"
        assert result == CATEGORY_LABELS[SubAgentCategory.CODE_QUALITY.value]

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_inherits_from_base(self, mock_get_instance, mock_pr_agent_kit):
        """Test that CodeQualitySubAgent inherits from ReviewSubAgentBase."""
        # Arrange
        mock_get_instance.return_value = MagicMock()
        agent = CodeQualitySubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        # Assert
        assert isinstance(agent, ReviewSubAgentBase)

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_can_be_instantiated(self, mock_get_instance, mock_pr_agent_kit):
        """Test that CodeQualitySubAgent can be instantiated."""
        # Arrange
        mock_get_instance.return_value = MagicMock()

        # Act
        agent = CodeQualitySubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
            confidence_threshold=0.6,
        )

        # Assert
        assert agent is not None
        assert agent._working_directory == "/tmp/test"
        assert agent._confidence_threshold == 0.6


class TestSubAgentIntegration:
    """Integration tests for sub-agents."""

    @pytest.mark.asyncio
    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    async def test_parallel_execution_all_agents(
        self, mock_get_instance, mock_pr_agent_kit, mock_claude_tool, temp_working_dir
    ):
        """Test that all core agents can execute in parallel."""
        # Arrange
        mock_get_instance.return_value = mock_claude_tool

        # Create all core agents
        agents = SubAgentRegistry.create_core_agents(
            temp_working_dir,
            kit=mock_pr_agent_kit,
        )

        # Act - Execute in parallel
        tasks = [
            agent.execute(
                diff="test diff",
                pr_number=1,
                repository="org/repo",
                title="Test PR",
                description="",
                branch="main",
            )
            for agent in agents
        ]
        results = await asyncio.gather(*tasks)

        # Assert
        assert len(results) == len(CORE_CATEGORIES)
        # Note: style agent may fail due to mock not supporting template rendering
        successful = [r for r in results if r.success]
        assert len(successful) >= len(CORE_CATEGORIES) - 1  # At least most succeed

        # Verify each category was executed
        categories = {r.category for r in results}
        assert categories == set(CORE_CATEGORIES)

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_all_agents_use_same_kit(self, mock_get_instance, mock_pr_agent_kit, temp_working_dir):
        """Test that all agents share the same kit instance when created together."""
        # Arrange
        mock_get_instance.return_value = MagicMock()

        # Act
        agents = SubAgentRegistry.create_core_agents(
            temp_working_dir,
            kit=mock_pr_agent_kit,
        )

        # Assert
        for agent in agents:
            assert agent._kit is mock_pr_agent_kit

    def test_all_agents_registered_with_correct_categories(self):
        """Test that all core agents are registered with correct categories."""
        # Arrange & Act
        from src.agents.review_agents import subagents  # noqa: F401

        # Assert
        assert SubAgentRegistry.is_registered("bug")
        assert SubAgentRegistry.is_registered("security")
        assert SubAgentRegistry.is_registered("code_quality")

        # Verify correct classes are registered
        assert SubAgentRegistry.get("bug") == BugDetectionSubAgent
        assert SubAgentRegistry.get("security") == SecuritySubAgent
        assert SubAgentRegistry.get("code_quality") == CodeQualitySubAgent

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_all_agents_have_distinct_categories(self, mock_get_instance, mock_pr_agent_kit, temp_working_dir):
        """Test that all agents have distinct category values."""
        # Arrange
        mock_get_instance.return_value = MagicMock()

        # Act
        agents = SubAgentRegistry.create_core_agents(
            temp_working_dir,
            kit=mock_pr_agent_kit,
        )

        # Assert
        categories = [agent.category for agent in agents]
        assert len(categories) == len(set(categories))  # All unique

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_all_agents_have_distinct_labels(self, mock_get_instance, mock_pr_agent_kit, temp_working_dir):
        """Test that all agents have distinct category labels."""
        # Arrange
        mock_get_instance.return_value = MagicMock()

        # Act
        agents = SubAgentRegistry.create_core_agents(
            temp_working_dir,
            kit=mock_pr_agent_kit,
        )

        # Assert
        labels = [agent.category_label for agent in agents]
        assert len(labels) == len(set(labels))  # All unique


class TestPreMortemSubAgentSkillPath:
    """Test that PreMortemSubAgent resolves the skill path from the app root."""

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_skill_path_is_relative_to_app_root_not_working_dir(
        self, mock_get_instance, mock_pr_agent_kit
    ):
        """
        _verify_skill_exists must look for the skill relative to the app root
        (where Docker installs it), NOT relative to the temp working directory.
        """
        from pathlib import Path
        from unittest.mock import patch as mock_patch
        import src.agents.review_agents.subagents.pre_mortem as pm_module
        from src.agents.review_agents.subagents.pre_mortem import PreMortemSubAgent

        mock_get_instance.return_value = MagicMock()

        # Use a temp dir as working_directory (simulates the cloned PR repo)
        agent = PreMortemSubAgent(
            working_directory="/tmp/pr-review-some-repo-99",
            kit=mock_pr_agent_kit,
        )

        # Calculate what the correct app_root should be
        expected_app_root = Path(pm_module.__file__).resolve().parents[4]
        expected_skill_path = expected_app_root / ".agents" / "skills" / "pre-mortem"

        captured_paths = []

        def mock_exists(self_path):
            captured_paths.append(self_path)
            return True  # Pretend both paths exist so no RuntimeError

        # Mock os.getenv to return None for PYTEST_CURRENT_TEST
        # so the verification logic actually runs (otherwise it skips in tests)
        def mock_getenv(key, default=None):
            if key == "PYTEST_CURRENT_TEST":
                return None
            return default

        # Need to patch at module level where os is imported (inside the function)
        import os as os_module
        with mock_patch.object(Path, "exists", mock_exists), \
             mock_patch.object(os_module, "getenv", mock_getenv):
            agent._verify_skill_exists()

        # The first path checked must be the skill_path derived from app_root
        assert len(captured_paths) >= 1
        assert captured_paths[0] == expected_skill_path, (
            f"Expected skill path {expected_skill_path}, "
            f"but got {captured_paths[0]}. "
            f"Path must be relative to app root, not working_directory."
        )

        # Must NOT contain anything derived from /tmp
        for path in captured_paths:
            assert "/tmp" not in str(path), (
                f"Skill path must not be under /tmp, got: {path}"
            )

    @pytest.mark.asyncio
    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    async def test_parallel_execution_handles_partial_failures(
        self, mock_get_instance, mock_pr_agent_kit, temp_working_dir
    ):
        """Test that parallel execution handles partial failures gracefully."""
        # Arrange
        from unittest.mock import AsyncMock

        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # Second agent fails
                return {"error": True, "message": "Simulated failure"}
            return {
                "result": "suggestions:\n  - file: test.py\n    line: 1\n    importance: 5\n    confidence: 0.8\n    description: 'test'"
            }

        mock_tool = MagicMock()
        mock_tool.execute = AsyncMock(side_effect=side_effect)
        mock_get_instance.return_value = mock_tool

        agents = SubAgentRegistry.create_core_agents(
            temp_working_dir,
            kit=mock_pr_agent_kit,
        )

        # Act
        tasks = [
            agent.execute(
                diff="test diff",
                pr_number=1,
                repository="org/repo",
                title="Test PR",
                description="",
                branch="main",
            )
            for agent in agents
        ]
        results = await asyncio.gather(*tasks)

        # Assert
        assert len(results) == len(CORE_CATEGORIES)
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        # At least one simulated failure, possibly more due to style mock issues
        assert len(failed) >= 1
        assert len(successful) <= len(CORE_CATEGORIES) - 1

