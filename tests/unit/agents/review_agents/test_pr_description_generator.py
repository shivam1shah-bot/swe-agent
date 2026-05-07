"""
Unit tests for PRDescriptionGenerator.

Tests cover:
- Description generation with valid responses
- Handling of empty/invalid responses
- Error handling during Claude execution
- Markdown parsing logic
- Comment posting and updating
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from src.agents.review_agents.pr_description_generator import PRDescriptionGenerator
from src.agents.review_agents.models import PRDescriptionResult
from src.constants.github_bots import GitHubBot


@pytest.fixture
def mock_kit():
    """Mock PRAgentKit for description generation."""
    mock = MagicMock()
    mock_config = MagicMock()
    mock_config.generate_ai_title = False
    mock_config.use_bullet_points = True
    mock_config.enable_pr_type = True
    mock_config.enable_pr_diagram = False
    mock.config.get_description_config.return_value = mock_config

    # Mock rendered prompt
    mock_rendered = MagicMock()
    mock_rendered.system = "You are a PR description generator."
    mock_rendered.user = "Generate a description for this PR."
    mock.render_description.return_value = mock_rendered

    return mock


@pytest.fixture
def mock_claude_tool():
    """Mock ClaudeCodeTool for description generation."""
    mock_tool = MagicMock()
    mock_tool.execute = AsyncMock(
        return_value={
            "result": """
<!-- pr-description-bot -->
## PR Description
This PR adds a new feature for user authentication.

## Changes
- Added login endpoint
- Added logout endpoint

## Risk Assessment
Low risk - standard authentication flow.
"""
        }
    )
    return mock_tool


@pytest.fixture
def mock_claude_tool_empty():
    """Mock ClaudeCodeTool that returns empty response."""
    mock_tool = MagicMock()
    mock_tool.execute = AsyncMock(return_value={"result": ""})
    return mock_tool


@pytest.fixture
def mock_claude_tool_error():
    """Mock ClaudeCodeTool that returns an error."""
    mock_tool = MagicMock()
    mock_tool.execute = AsyncMock(
        return_value={"error": True, "message": "Claude execution failed"}
    )
    return mock_tool


@pytest.fixture
def mock_auth_service():
    """Mock GitHubAuthService."""
    mock = MagicMock()
    mock.get_token = AsyncMock(return_value="test-token")
    return mock


@pytest.fixture
def generator(mock_kit, mock_claude_tool, mock_auth_service, tmp_path):
    """Create PRDescriptionGenerator with mocked dependencies."""
    with patch(
        "src.agents.review_agents.pr_description_generator.ClaudeCodeTool"
    ) as MockClaudeTool, patch(
        "src.agents.review_agents.pr_description_generator.GitHubAuthService"
    ) as MockAuthService:
        MockClaudeTool.get_instance.return_value = mock_claude_tool
        MockAuthService.return_value = mock_auth_service

        gen = PRDescriptionGenerator(
            working_directory=str(tmp_path),
            kit=mock_kit,
            github_bot=GitHubBot.CODE_REVIEW,
        )
        # Inject mocks
        gen._claude_tool = mock_claude_tool
        gen._auth_service = mock_auth_service
        return gen


class TestPRDescriptionGenerator:
    """Tests for PRDescriptionGenerator class."""

    @pytest.mark.asyncio
    async def test_generate_and_post_returns_result_object(
        self, generator, mock_claude_tool
    ):
        """Test that generate_and_post returns PRDescriptionResult."""
        # Mock the posting subprocess
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(return_value=(b"", b""))
            mock_exec.return_value = mock_process

            result = await generator.generate_and_post(
                diff="+ new line\n- old line",
                repository="test/repo",
                pr_number=123,
                title="Test PR",
                description="Test description",
                branch="feature/test",
                target_branch="main",
            )

            assert isinstance(result, PRDescriptionResult)
            assert result.full_description is not None
            assert "<!-- pr-description-bot -->" in result.full_description

    @pytest.mark.asyncio
    async def test_generate_extracts_summary(self, generator, mock_claude_tool):
        """Test that summary is extracted from PR Description section."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(return_value=(b"", b""))
            mock_exec.return_value = mock_process

            result = await generator.generate_and_post(
                diff="+ new line",
                repository="test/repo",
                pr_number=123,
                title="Test PR",
                description="",
                branch="feature/test",
                target_branch="main",
            )

            assert result.summary is not None
            assert "user authentication" in result.summary.lower()

    @pytest.mark.asyncio
    async def test_handles_missing_bot_marker(self, generator, mock_claude_tool):
        """Test handling when response is missing bot marker."""
        # Override mock to return response without marker
        mock_claude_tool.execute = AsyncMock(
            return_value={
                "result": "This is a description without the bot marker."
            }
        )

        result = await generator.generate_and_post(
            diff="+ new line",
            repository="test/repo",
            pr_number=123,
            title="Test PR",
            description="",
            branch="feature/test",
            target_branch="main",
        )

        # Should not post since no valid description was parsed
        assert result.full_description is None
        assert result.posted is False

    @pytest.mark.asyncio
    async def test_handles_claude_execution_error(
        self, generator, mock_claude_tool
    ):
        """Test graceful handling of Claude execution errors."""
        mock_claude_tool.execute = AsyncMock(
            return_value={"error": True, "message": "Claude unavailable"}
        )

        result = await generator.generate_and_post(
            diff="+ new line",
            repository="test/repo",
            pr_number=123,
            title="Test PR",
            description="",
            branch="feature/test",
            target_branch="main",
        )

        assert result.posted is False
        assert result.error is not None
        assert "failed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_handles_exception_during_execution(self, generator, mock_claude_tool):
        """Test handling when Claude execution raises an exception."""
        mock_claude_tool.execute = AsyncMock(
            side_effect=Exception("Unexpected error")
        )

        result = await generator.generate_and_post(
            diff="+ new line",
            repository="test/repo",
            pr_number=123,
            title="Test PR",
            description="",
            branch="feature/test",
            target_branch="main",
        )

        assert result.posted is False
        assert result.error is not None
        assert "Unexpected error" in result.error

    @pytest.mark.asyncio
    async def test_posts_description_comment(self, generator, mock_claude_tool):
        """Test that description is posted as PR comment."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            # Mock for finding existing comment (none found)
            # and for creating new comment
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(return_value=(b"", b""))
            mock_exec.return_value = mock_process

            result = await generator.generate_and_post(
                diff="+ new line",
                repository="test/repo",
                pr_number=123,
                title="Test PR",
                description="",
                branch="feature/test",
                target_branch="main",
            )

            assert result.posted is True
            # Verify subprocess was called for posting
            assert mock_exec.called


class TestParseMarkdownDescription:
    """Tests for _parse_markdown_description method."""

    def test_parses_valid_response(self, generator):
        """Test parsing of valid markdown response."""
        response = """Some preamble text

<!-- pr-description-bot -->
## PR Description
This is the summary of changes.

## Changes
- Change 1
- Change 2
"""
        result = generator._parse_markdown_description(response)

        assert result.get("full_description") is not None
        assert "<!-- pr-description-bot -->" in result["full_description"]
        assert result.get("summary") is not None

    def test_returns_empty_for_missing_marker(self, generator):
        """Test that missing bot marker returns empty result."""
        response = """
## PR Description
This is a description without the marker.
"""
        result = generator._parse_markdown_description(response)

        assert result.get("full_description") is None

    def test_extracts_summary_from_pr_description_section(self, generator):
        """Test that summary is extracted from PR Description section."""
        response = """
<!-- pr-description-bot -->
## PR Description
This is the summary that should be extracted.

## Changes
- Change 1
"""
        result = generator._parse_markdown_description(response)

        assert result.get("summary") is not None
        assert "summary that should be extracted" in result["summary"]


class TestExecuteClaude:
    """Tests for _execute_claude method."""

    @pytest.mark.asyncio
    async def test_calls_claude_tool_with_correct_params(
        self, generator, mock_claude_tool, mock_kit
    ):
        """Test that Claude is called with correct parameters."""
        rendered = mock_kit.render_description.return_value

        await generator._execute_claude(rendered)

        mock_claude_tool.execute.assert_called_once()
        call_args = mock_claude_tool.execute.call_args
        params = call_args[1]["params"] if "params" in call_args[1] else call_args[0][0]

        assert params["action"] == "run_prompt"
        assert params["prompt"] == rendered.user
        assert params["system_prompt"] == rendered.system

    @pytest.mark.asyncio
    async def test_raises_on_error_response(self, generator, mock_claude_tool):
        """Test that error response raises RuntimeError."""
        mock_claude_tool.execute = AsyncMock(
            return_value={"error": True, "message": "Failed"}
        )
        mock_rendered = MagicMock()
        mock_rendered.system = "system"
        mock_rendered.user = "user"

        with pytest.raises(RuntimeError) as exc_info:
            await generator._execute_claude(mock_rendered)

        assert "Claude execution failed" in str(exc_info.value)
