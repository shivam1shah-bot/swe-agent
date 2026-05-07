"""
Unit tests for ReviewSubAgentBase.

Tests the base class functionality including initialization,
prompt rendering, async execution, and YAML parsing.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.review_agents.subagent_base import ReviewSubAgentBase
from src.agents.review_agents.models import SubAgentResult


class ConcreteSubAgent(ReviewSubAgentBase):
    """Concrete implementation of ReviewSubAgentBase for testing."""

    @property
    def category(self) -> str:
        return "test_category"

    @property
    def category_label(self) -> str:
        return "TEST"


class TestReviewSubAgentBaseInit:
    """Test ReviewSubAgentBase initialization."""

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_init_sets_working_directory(self, mock_get_instance):
        """Test that init sets the working directory."""
        # Arrange
        mock_get_instance.return_value = MagicMock()

        # Act
        agent = ConcreteSubAgent(working_directory="/path/to/repo")

        # Assert
        assert agent._working_directory == "/path/to/repo"

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_init_creates_kit_if_not_provided(self, mock_get_instance):
        """Test that init creates a PRAgentKit if not provided."""
        # Arrange
        mock_get_instance.return_value = MagicMock()

        # Act
        agent = ConcreteSubAgent(working_directory="/path/to/repo")

        # Assert
        assert agent._kit is not None

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_init_uses_provided_kit(self, mock_get_instance, mock_pr_agent_kit):
        """Test that init uses the provided PRAgentKit."""
        # Arrange
        mock_get_instance.return_value = MagicMock()

        # Act
        agent = ConcreteSubAgent(
            working_directory="/path/to/repo",
            kit=mock_pr_agent_kit,
        )

        # Assert
        assert agent._kit is mock_pr_agent_kit

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_init_sets_confidence_threshold(self, mock_get_instance):
        """Test that init sets the confidence threshold."""
        # Arrange
        mock_get_instance.return_value = MagicMock()

        # Act
        agent = ConcreteSubAgent(
            working_directory="/path/to/repo",
            confidence_threshold=0.8,
        )

        # Assert
        assert agent._confidence_threshold == 0.8

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_init_gets_claude_tool_instance(self, mock_get_instance):
        """Test that init gets the ClaudeCodeTool singleton."""
        # Arrange
        mock_tool = MagicMock()
        mock_get_instance.return_value = mock_tool

        # Act
        agent = ConcreteSubAgent(working_directory="/path/to/repo")

        # Assert
        mock_get_instance.assert_called_once()
        assert agent._claude_tool is mock_tool


class TestReviewSubAgentBaseRenderPrompt:
    """Test prompt rendering."""

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_render_prompt_calls_kit(self, mock_get_instance, mock_pr_agent_kit):
        """Test that _render_prompt calls the kit's render_subagent method."""
        # Arrange
        mock_get_instance.return_value = MagicMock()
        agent = ConcreteSubAgent(
            working_directory="/path/to/repo",
            kit=mock_pr_agent_kit,
        )

        # Act
        agent._render_prompt(
            diff="test diff",
            pr_number=123,
            repository="org/repo",
            title="Test PR",
            description="Test description",
            branch="main",
        )

        # Assert
        mock_pr_agent_kit.render_subagent.assert_called_once()

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_render_prompt_passes_variables(self, mock_get_instance, mock_pr_agent_kit):
        """Test that _render_prompt passes all variables to the kit."""
        # Arrange
        mock_get_instance.return_value = MagicMock()
        agent = ConcreteSubAgent(
            working_directory="/path/to/repo",
            kit=mock_pr_agent_kit,
        )

        # Act
        agent._render_prompt(
            diff="test diff",
            pr_number=123,
            repository="org/repo",
            title="Test PR",
            description="Test description",
            branch="feature/test",
        )

        # Assert
        call_args = mock_pr_agent_kit.render_subagent.call_args
        assert call_args[0][0] == "test_category"  # category
        variables = call_args[1]["variables"]
        assert variables["diff"] == "test diff"
        assert variables["pr_number"] == 123
        assert variables["repository"] == "org/repo"
        assert variables["title"] == "Test PR"
        assert variables["description"] == "Test description"
        assert variables["branch"] == "feature/test"

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_render_prompt_includes_confidence_threshold(self, mock_get_instance, mock_pr_agent_kit):
        """Test that _render_prompt includes confidence_threshold in variables."""
        # Arrange
        mock_get_instance.return_value = MagicMock()
        agent = ConcreteSubAgent(
            working_directory="/path/to/repo",
            kit=mock_pr_agent_kit,
            confidence_threshold=0.75,
        )

        # Act
        agent._render_prompt(
            diff="test diff",
            pr_number=123,
            repository="org/repo",
            title="Test PR",
            description="",
            branch="main",
        )

        # Assert
        variables = mock_pr_agent_kit.render_subagent.call_args[1]["variables"]
        assert variables["confidence_threshold"] == 0.75


class TestReviewSubAgentBaseExecute:
    """Test async execute method."""

    @pytest.fixture(autouse=True)
    def mock_temp_file(self):
        """Mock tempfile/os operations for stream-json output file."""
        with patch("src.agents.review_agents.subagent_base.tempfile.mkstemp", return_value=(999, "/tmp/fake-output.jsonl")), \
             patch("src.agents.review_agents.subagent_base.os.close"), \
             patch("src.agents.review_agents.subagent_base.os.path.exists", return_value=True), \
             patch("src.agents.review_agents.subagent_base.os.unlink"):
            yield

    @pytest.mark.asyncio
    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    async def test_execute_renders_prompt(self, mock_get_instance, mock_pr_agent_kit, mock_claude_tool):
        """Test that execute renders the prompt."""
        # Arrange
        mock_get_instance.return_value = mock_claude_tool
        agent = ConcreteSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        # Act
        with patch.object(agent, "_render_prompt", wraps=agent._render_prompt) as mock_render:
            await agent.execute(
                diff="test diff",
                pr_number=123,
                repository="org/repo",
                title="Test PR",
                description="",
                branch="main",
            )

            # Assert
            mock_render.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    async def test_execute_calls_claude(self, mock_get_instance, mock_pr_agent_kit, mock_claude_tool):
        """Test that execute calls the Claude tool."""
        # Arrange
        mock_get_instance.return_value = mock_claude_tool
        agent = ConcreteSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        # Act
        await agent.execute(
            diff="test diff",
            pr_number=123,
            repository="org/repo",
            title="Test PR",
            description="",
            branch="main",
        )

        # Assert
        mock_claude_tool.execute.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    async def test_execute_parses_yaml_response(self, mock_get_instance, mock_pr_agent_kit, mock_claude_tool):
        """Test that execute parses the YAML response."""
        # Arrange
        mock_get_instance.return_value = mock_claude_tool
        agent = ConcreteSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        # Act
        result = await agent.execute(
            diff="test diff",
            pr_number=123,
            repository="org/repo",
            title="Test PR",
            description="",
            branch="main",
        )

        # Assert
        assert len(result.suggestions) == 1
        assert result.suggestions[0]["file"] == "test.py"
        assert result.suggestions[0]["line"] == 10

    @pytest.mark.asyncio
    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    async def test_execute_returns_subagent_result(self, mock_get_instance, mock_pr_agent_kit, mock_claude_tool):
        """Test that execute returns a SubAgentResult."""
        # Arrange
        mock_get_instance.return_value = mock_claude_tool
        agent = ConcreteSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        # Act
        result = await agent.execute(
            diff="test diff",
            pr_number=123,
            repository="org/repo",
            title="Test PR",
            description="",
            branch="main",
        )

        # Assert
        assert isinstance(result, SubAgentResult)
        assert result.category == "test_category"
        assert result.success is True
        assert result.error is None
        assert result.execution_time_ms >= 0

    @pytest.mark.asyncio
    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    async def test_execute_handles_claude_error(self, mock_get_instance, mock_pr_agent_kit, mock_claude_tool_error):
        """Test that execute handles Claude errors gracefully."""
        # Arrange
        mock_get_instance.return_value = mock_claude_tool_error
        agent = ConcreteSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        # Act
        result = await agent.execute(
            diff="test diff",
            pr_number=123,
            repository="org/repo",
            title="Test PR",
            description="",
            branch="main",
        )

        # Assert
        assert isinstance(result, SubAgentResult)
        assert result.success is False
        assert result.error is not None
        assert "Claude execution failed" in result.error

    @pytest.mark.asyncio
    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    async def test_execute_handles_parse_error(self, mock_get_instance, mock_pr_agent_kit):
        """Test that execute handles YAML parse errors gracefully."""
        # Arrange
        mock_tool = MagicMock()
        mock_tool.execute = AsyncMock(return_value={"result": "not valid yaml: [["})
        mock_get_instance.return_value = mock_tool
        agent = ConcreteSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        # Act
        result = await agent.execute(
            diff="test diff",
            pr_number=123,
            repository="org/repo",
            title="Test PR",
            description="",
            branch="main",
        )

        # Assert
        # Parse errors should result in empty suggestions but success=True
        assert isinstance(result, SubAgentResult)
        assert result.suggestions == []
        assert result.success is True

    @pytest.mark.asyncio
    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    async def test_execute_passes_working_directory_param(
        self, mock_get_instance, mock_pr_agent_kit, mock_claude_tool
    ):
        """Test that execute passes working_directory in params to ClaudeCodeTool."""
        # Arrange
        mock_get_instance.return_value = mock_claude_tool
        agent = ConcreteSubAgent(
            working_directory="/path/to/repo",
            kit=mock_pr_agent_kit,
        )

        # Act
        await agent.execute(
            diff="test diff",
            pr_number=123,
            repository="org/repo",
            title="Test PR",
            description="",
            branch="main",
        )

        # Assert
        # Verify working_directory was passed in the params
        mock_claude_tool.execute.assert_called_once()
        call_args = mock_claude_tool.execute.call_args
        params = call_args[0][0] if call_args[0] else call_args[1].get("params", {})
        assert params.get("working_directory") == "/path/to/repo"

    @pytest.mark.asyncio
    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    async def test_execute_handles_error_without_directory_issues(
        self, mock_get_instance, mock_pr_agent_kit
    ):
        """Test that execute handles errors correctly without directory restoration logic."""
        # Arrange
        mock_tool = MagicMock()
        mock_tool.execute = AsyncMock(side_effect=RuntimeError("Test error"))
        mock_get_instance.return_value = mock_tool
        agent = ConcreteSubAgent(
            working_directory="/path/to/repo",
            kit=mock_pr_agent_kit,
        )

        # Act
        result = await agent.execute(
            diff="test diff",
            pr_number=123,
            repository="org/repo",
            title="Test PR",
            description="",
            branch="main",
        )

        # Assert
        assert result.success is False
        assert "Test error" in result.error


class TestReviewSubAgentBaseParseResponse:
    """Test YAML response parsing."""

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_parse_response_extracts_suggestions(self, mock_get_instance, sample_yaml_response):
        """Test that _parse_response extracts suggestions from YAML."""
        # Arrange
        mock_get_instance.return_value = MagicMock()
        agent = ConcreteSubAgent(working_directory="/tmp")

        # Act
        suggestions = agent._parse_response(sample_yaml_response)

        # Assert
        assert len(suggestions) == 2
        assert suggestions[0]["file"] == "src/main.py"
        assert suggestions[0]["line"] == 42
        assert suggestions[1]["file"] == "src/utils.py"
        assert suggestions[1]["line"] == 100

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_parse_response_adds_category_label(self, mock_get_instance, sample_yaml_response):
        """Test that _parse_response adds category label to suggestions."""
        # Arrange
        mock_get_instance.return_value = MagicMock()
        agent = ConcreteSubAgent(working_directory="/tmp")

        # Act
        suggestions = agent._parse_response(sample_yaml_response)

        # Assert
        for suggestion in suggestions:
            assert suggestion["category"] == "TEST"

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_parse_response_preserves_existing_category(self, mock_get_instance, sample_yaml_response_with_category):
        """Test that _parse_response preserves existing category in suggestion."""
        # Arrange
        mock_get_instance.return_value = MagicMock()
        agent = ConcreteSubAgent(working_directory="/tmp")

        # Act
        suggestions = agent._parse_response(sample_yaml_response_with_category)

        # Assert
        assert suggestions[0]["category"] == "EXISTING_CATEGORY"

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_parse_response_handles_empty_response(self, mock_get_instance):
        """Test that _parse_response handles empty response."""
        # Arrange
        mock_get_instance.return_value = MagicMock()
        agent = ConcreteSubAgent(working_directory="/tmp")

        # Act
        suggestions = agent._parse_response("")

        # Assert
        assert suggestions == []

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_parse_response_handles_whitespace_only(self, mock_get_instance):
        """Test that _parse_response handles whitespace-only response."""
        # Arrange
        mock_get_instance.return_value = MagicMock()
        agent = ConcreteSubAgent(working_directory="/tmp")

        # Act
        suggestions = agent._parse_response("   \n\t  ")

        # Assert
        assert suggestions == []

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_parse_response_handles_invalid_yaml(self, mock_get_instance, invalid_yaml_response):
        """Test that _parse_response handles invalid YAML gracefully."""
        # Arrange
        mock_get_instance.return_value = MagicMock()
        agent = ConcreteSubAgent(working_directory="/tmp")

        # Act
        suggestions = agent._parse_response(invalid_yaml_response)

        # Assert
        assert suggestions == []

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_parse_response_handles_missing_suggestions(self, mock_get_instance):
        """Test that _parse_response handles response without suggestions key."""
        # Arrange
        mock_get_instance.return_value = MagicMock()
        agent = ConcreteSubAgent(working_directory="/tmp")

        # Act
        suggestions = agent._parse_response("other_key: value")

        # Assert
        assert suggestions == []

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_parse_response_handles_non_list_suggestions(self, mock_get_instance):
        """Test that _parse_response handles non-list suggestions value."""
        # Arrange
        mock_get_instance.return_value = MagicMock()
        agent = ConcreteSubAgent(working_directory="/tmp")

        # Act
        suggestions = agent._parse_response("suggestions: not_a_list")

        # Assert
        assert suggestions == []
