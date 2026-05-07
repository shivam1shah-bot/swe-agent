"""
Unit tests for GitHub CLI Tool.

Tests GitHub CLI command execution, authentication, and error handling.
"""

import pytest
import asyncio
from unittest.mock import Mock, MagicMock, patch, AsyncMock

from src.tools.github_cli import GitHubCLITool
from src.providers.github.exceptions import GitHubCLIError, GitHubAuthenticationError


class TestGitHubCLITool:
    """Test suite for GitHubCLITool."""

    @pytest.fixture
    def mock_auth_service(self):
        """Create a mock GitHubAuthService."""
        service = AsyncMock()
        service.get_token_info = AsyncMock(return_value={
            "authenticated": True,
            "token_available": True
        })
        service.ensure_gh_auth = AsyncMock()
        service.get_comprehensive_status = AsyncMock(return_value={
            "overall_status": "healthy"
        })
        return service

    @pytest.fixture
    def tool(self, mock_auth_service):
        """Create a GitHubCLITool instance with mocked auth service."""
        with patch('src.tools.github_cli.GitHubAuthService', return_value=mock_auth_service):
            return GitHubCLITool()

    def test_init(self):
        """Test tool initialization."""
        with patch('src.tools.github_cli.GitHubAuthService'):
            tool = GitHubCLITool()
            assert tool.name == "github_cli"
            assert tool.timeout == 300
            assert tool.auth_service is not None

    def test_init_with_config(self):
        """Test tool initialization with custom config."""
        config = {"timeout": 600}
        with patch('src.tools.github_cli.GitHubAuthService'):
            tool = GitHubCLITool(config=config)
            assert tool.config == config

    @pytest.mark.asyncio
    async def test_execute_success(self, tool, mock_auth_service):
        """Test successful command execution."""
        mock_result = {
            "success": True,
            "stdout": "version 2.0.0",
            "stderr": "",
            "exit_code": 0,
            "execution_time": 0.5
        }

        with patch.object(tool, '_execute_command', return_value=mock_result):
            result = await tool.execute({"command": "gh --version"})

            assert result["success"] is True
            assert result["stdout"] == "version 2.0.0"
            assert result["exit_code"] == 0
            assert "command" in result

    @pytest.mark.asyncio
    async def test_execute_missing_command(self, tool):
        """Test execution with missing command parameter."""
        result = await tool.execute({})

        assert result["success"] is False
        assert "error" in result
        assert "required" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_execute_empty_command(self, tool):
        """Test execution with empty command."""
        result = await tool.execute({"command": "   "})

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_execute_authentication_error(self, tool, mock_auth_service):
        """Test execution when authentication fails."""
        mock_auth_service.get_token_info = AsyncMock(return_value={
            "authenticated": False
        })

        result = await tool.execute({"command": "gh pr list"})

        assert result["success"] is False
        assert "authentication" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_execute_with_custom_timeout(self, tool):
        """Test execution with custom timeout."""
        mock_result = {
            "success": True,
            "stdout": "output",
            "stderr": "",
            "exit_code": 0,
            "execution_time": 1.0
        }

        with patch.object(tool, '_execute_command', return_value=mock_result) as mock_exec:
            await tool.execute({"command": "gh --version", "timeout": 120})

            mock_exec.assert_called_once_with("gh --version", 120)

    @pytest.mark.asyncio
    async def test_execute_command_timeout(self, tool):
        """Test command execution timeout."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(side_effect=asyncio.TimeoutError())

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            result = await tool._execute_command("slow_command", timeout=1)

            assert result["success"] is False
            assert "timed out" in result["stderr"].lower()
            assert result["exit_code"] == 124

    @pytest.mark.asyncio
    async def test_execute_command_success(self, tool):
        """Test successful command execution."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(
            b"stdout output",
            b"stderr output"
        ))
        mock_process.returncode = 0

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            result = await tool._execute_command("test_command", timeout=10)

            assert result["success"] is True
            assert result["stdout"] == "stdout output"
            assert result["stderr"] == "stderr output"
            assert result["exit_code"] == 0
            assert "execution_time" in result

    @pytest.mark.asyncio
    async def test_execute_command_failure(self, tool):
        """Test failed command execution."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(
            b"",
            b"command not found"
        ))
        mock_process.returncode = 127

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            result = await tool._execute_command("invalid_command", timeout=10)

            assert result["success"] is False
            assert result["exit_code"] == 127
            assert "command not found" in result["stderr"]

    @pytest.mark.asyncio
    async def test_execute_command_exception(self, tool):
        """Test command execution with exception."""
        with patch('asyncio.create_subprocess_exec', side_effect=Exception("Process error")):
            result = await tool._execute_command("test_command", timeout=10)

            assert result["success"] is False
            assert result["exit_code"] == -1
            assert "Process error" in result["stderr"]

    @pytest.mark.asyncio
    async def test_execute_command_non_utf8_output(self, tool):
        """Test command execution with non-UTF8 output."""
        mock_process = AsyncMock()
        # Binary output that's not valid UTF-8
        mock_process.communicate = AsyncMock(return_value=(
            b"\x80\x81\x82",
            b"\x90\x91"
        ))
        mock_process.returncode = 0

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            result = await tool._execute_command("test_command", timeout=10)

            # Should handle gracefully using errors='replace'
            assert result["success"] is True
            assert isinstance(result["stdout"], str)
            assert isinstance(result["stderr"], str)

    @pytest.mark.asyncio
    async def test_ensure_authentication_success(self, tool, mock_auth_service):
        """Test successful authentication check."""
        await tool._ensure_authentication()

        mock_auth_service.get_token_info.assert_called_once()
        mock_auth_service.ensure_gh_auth.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_authentication_no_token(self, tool, mock_auth_service):
        """Test authentication check when no token is available."""
        mock_auth_service.get_token_info = AsyncMock(return_value={
            "authenticated": False
        })

        with pytest.raises(GitHubAuthenticationError):
            await tool._ensure_authentication()

    @pytest.mark.asyncio
    async def test_ensure_authentication_setup_failure(self, tool, mock_auth_service):
        """Test authentication check when setup fails."""
        mock_auth_service.ensure_gh_auth = AsyncMock(side_effect=Exception("Setup failed"))

        with pytest.raises(GitHubAuthenticationError):
            await tool._ensure_authentication()

    def test_validate_params_valid(self, tool):
        """Test parameter validation with valid params."""
        params = {"command": "gh --version"}
        assert tool.validate_params(params) is True

    def test_validate_params_empty_command(self, tool):
        """Test parameter validation with empty command."""
        params = {"command": ""}
        assert tool.validate_params(params) is False

    def test_validate_params_whitespace_command(self, tool):
        """Test parameter validation with whitespace-only command."""
        params = {"command": "   "}
        assert tool.validate_params(params) is False

    def test_validate_params_missing_command(self, tool):
        """Test parameter validation with missing command."""
        params = {}
        assert tool.validate_params(params) is False

    def test_validate_params_non_string_command(self, tool):
        """Test parameter validation with non-string command."""
        params = {"command": 123}
        assert tool.validate_params(params) is False

    @pytest.mark.asyncio
    async def test_get_status_healthy(self, tool, mock_auth_service):
        """Test getting tool status when healthy."""
        status = await tool.get_status()

        assert status["tool_name"] == "github_cli"
        assert status["status"] == "ready"
        assert "authentication" in status
        assert "capabilities" in status

    @pytest.mark.asyncio
    async def test_get_status_not_ready(self, tool, mock_auth_service):
        """Test getting tool status when not ready."""
        mock_auth_service.get_comprehensive_status = AsyncMock(return_value={
            "overall_status": "unhealthy"
        })

        status = await tool.get_status()

        assert status["status"] == "not_ready"

    @pytest.mark.asyncio
    async def test_get_status_error(self, tool, mock_auth_service):
        """Test getting tool status when error occurs."""
        mock_auth_service.get_comprehensive_status = AsyncMock(
            side_effect=Exception("Status error")
        )

        status = await tool.get_status()

        assert status["status"] == "error"
        assert "error" in status

    @pytest.mark.asyncio
    async def test_test_functionality_success(self, tool, mock_auth_service):
        """Test functionality test with all working."""
        git_result = {
            "success": True,
            "stdout": "git version 2.30.0",
            "stderr": ""
        }
        gh_result = {
            "success": True,
            "stdout": "gh version 2.0.0",
            "stderr": ""
        }

        with patch.object(tool, '_execute_command', side_effect=[git_result, gh_result]):
            result = await tool.test_functionality()

            assert result["git_available"] is True
            assert result["gh_available"] is True
            assert result["overall_status"] == "working"
            assert "git version" in result["git_version"]

    @pytest.mark.asyncio
    async def test_test_functionality_git_only(self, tool, mock_auth_service):
        """Test functionality when only git is available."""
        git_result = {
            "success": True,
            "stdout": "git version 2.30.0",
            "stderr": ""
        }

        mock_auth_service.get_token_info = AsyncMock(return_value={
            "authenticated": False
        })

        with patch.object(tool, '_execute_command', return_value=git_result):
            result = await tool.test_functionality()

            assert result["git_available"] is True
            assert result["gh_available"] is False
            assert result["overall_status"] == "working"

    @pytest.mark.asyncio
    async def test_test_functionality_failure(self, tool, mock_auth_service):
        """Test functionality test when git is not available."""
        git_result = {
            "success": False,
            "stdout": "",
            "stderr": "command not found"
        }

        with patch.object(tool, '_execute_command', return_value=git_result):
            result = await tool.test_functionality()

            assert result["git_available"] is False
            assert result["overall_status"] == "issues"

    @pytest.mark.asyncio
    async def test_test_functionality_exception(self, tool, mock_auth_service):
        """Test functionality test when exception occurs."""
        with patch.object(tool, '_execute_command', side_effect=Exception("Test error")):
            result = await tool.test_functionality()

            assert result["git_available"] is False
            assert result["gh_available"] is False
            assert result["overall_status"] == "error"
            assert "error" in result

    @pytest.mark.asyncio
    async def test_execute_command_tracks_time(self, tool):
        """Test that command execution tracks time correctly."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"output", b""))
        mock_process.returncode = 0

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            with patch('time.time', side_effect=[0, 1.5]):  # Start and end times
                result = await tool._execute_command("test", timeout=10)

                assert result["execution_time"] == 1.5

    @pytest.mark.asyncio
    async def test_execute_passes_context(self, tool, mock_auth_service):
        """Test that execute can receive context parameter."""
        mock_result = {
            "success": True,
            "stdout": "output",
            "stderr": "",
            "exit_code": 0,
            "execution_time": 0.1
        }

        with patch.object(tool, '_execute_command', return_value=mock_result):
            context = {"user": "test_user"}
            result = await tool.execute({"command": "test"}, context=context)

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_handles_general_exception(self, tool, mock_auth_service):
        """Test that execute handles unexpected exceptions gracefully."""
        with patch.object(tool, '_ensure_authentication', side_effect=Exception("Unexpected")):
            result = await tool.execute({"command": "test"})

            assert result["success"] is False
            assert "error" in result
            assert "Unexpected" in result["error"]

    def test_tool_has_description(self, tool):
        """Test that tool has a description."""
        assert len(tool.description) > 0
        assert "GitHub" in tool.description or "github" in tool.description

    @pytest.mark.asyncio
    async def test_command_splitting(self, tool):
        """Test that commands are properly split into parts."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 0

        with patch('asyncio.create_subprocess_exec', return_value=mock_process) as mock_exec:
            await tool._execute_command("gh pr list --limit 10", timeout=10)

            # Verify command was split correctly
            mock_exec.assert_called_once()
            args = mock_exec.call_args[0]
            assert "gh" in args
            assert "pr" in args
            assert "list" in args

    def test_get_parameter_schema(self, tool):
        """Test that parameter schema is properly defined."""
        schema = tool._get_parameter_schema()

        assert schema is not None
        assert "type" in schema
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "command" in schema["properties"]
        assert "timeout" in schema["properties"]
        assert "required" in schema
        assert "command" in schema["required"]

    def test_get_output_schema(self, tool):
        """Test that output schema is properly defined."""
        schema = tool._get_output_schema()

        assert schema is not None
        assert "type" in schema
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "success" in schema["properties"]
        assert "stdout" in schema["properties"]
        assert "stderr" in schema["properties"]
        assert "exit_code" in schema["properties"]
        assert "command" in schema["properties"]
        assert "execution_time" in schema["properties"]

    def test_get_capabilities(self, tool):
        """Test that get_capabilities returns proper structure."""
        capabilities = tool.get_capabilities()

        assert capabilities is not None
        assert "name" in capabilities
        assert capabilities["name"] == "github_cli"
        assert "description" in capabilities
        assert "parameters" in capabilities
        assert "output" in capabilities
        assert capabilities["parameters"] == tool._get_parameter_schema()
        assert capabilities["output"] == tool._get_output_schema()
