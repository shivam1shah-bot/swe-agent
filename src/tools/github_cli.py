"""
GitHub CLI Tool - Simplified.
Simple GitHub CLI tool that uses the new simplified authentication service.
"""

import asyncio
import logging
import subprocess
from typing import Dict, Any, Optional

from .base import BaseTool
from ..providers.github.auth_service import GitHubAuthService
from ..providers.github.exceptions import GitHubCLIError, GitHubAuthenticationError

logger = logging.getLogger(__name__)


class GitHubCLITool(BaseTool):
    """Simplified GitHub CLI tool using the new authentication service."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the GitHub CLI tool."""
        super().__init__(
            name="github_cli",
            description="Simplified GitHub CLI tool with automatic authentication",
            config=config
        )
        self.auth_service = GitHubAuthService()
        self.timeout = 300  # 5 minutes default timeout
        
    async def execute(self, params: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute GitHub CLI commands."""
        try:
            # Validate parameters
            command = params.get("command", "").strip()
            if not command:
                return {
                    "success": False,
                    "error": "Command parameter is required",
                    "message": "Provide a git or gh command to execute"
                }
            
            timeout = params.get("timeout", self.timeout)
            
            # Ensure authentication
            await self._ensure_authentication()
            
            # Execute the command
            logger.info(f"Executing GitHub CLI command: {command}")
            result = await self._execute_command(command, timeout)
            
            return {
                "success": result.get("success", False),
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
                "exit_code": result.get("exit_code", -1),
                "command": command,
                "execution_time": result.get("execution_time", 0)
            }
            
        except GitHubAuthenticationError as e:
            logger.error(f"GitHub authentication error: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "GitHub authentication failed"
            }
        except Exception as e:
            logger.error(f"GitHub CLI tool execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "GitHub CLI tool execution failed"
            }
            
    async def _ensure_authentication(self) -> None:
        """Ensure GitHub authentication is ready."""
        try:
            # Check if token is available
            token_info = await self.auth_service.get_token_info()
            
            if not token_info.get("authenticated", False):
                raise GitHubAuthenticationError(
                    "No GitHub token available. Ensure worker is running to refresh tokens."
                )
            
            # Ensure CLI tools are set up
            await self.auth_service.ensure_gh_auth()
            
            logger.debug("GitHub authentication verified")
            
        except Exception as e:
            logger.error(f"Authentication setup failed: {e}")
            raise GitHubAuthenticationError(f"Failed to setup GitHub authentication: {str(e)}")
    
    async def _execute_command(self, command: str, timeout: int) -> Dict[str, Any]:
        """Execute a shell command."""
        import time
        start_time = time.time()
        
        try:
            # Split command into parts
            command_parts = command.split()
            
            # Create subprocess
            process = await asyncio.create_subprocess_exec(
                *command_parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Wait for completion with timeout
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            
            execution_time = time.time() - start_time
            
            return {
                "success": process.returncode == 0,
                "stdout": stdout.decode('utf-8', errors='replace'),
                "stderr": stderr.decode('utf-8', errors='replace'), 
                "exit_code": process.returncode,
                "execution_time": round(execution_time, 2)
            }
            
        except asyncio.TimeoutError:
            logger.error(f"Command timed out after {timeout} seconds: {command}")
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Command timed out after {timeout} seconds",
                "exit_code": 124,  # Standard timeout exit code
                "execution_time": timeout
            }
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Command execution failed: {e}")
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1,
                "execution_time": round(execution_time, 2)
            }
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate input parameters."""
        return isinstance(params.get("command"), str) and len(params.get("command", "").strip()) > 0
    
    async def get_status(self) -> Dict[str, Any]:
        """Get tool status."""
        try:
            # Get authentication status
            auth_status = await self.auth_service.get_comprehensive_status()
            
            return {
                "tool_name": self.name,
                "status": "ready" if auth_status.get("overall_status") == "healthy" else "not_ready",
                "authentication": auth_status,
                "capabilities": {
                    "git_commands": True,
                    "gh_commands": True,
                    "repository_operations": True
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get tool status: {e}")
            return {
                "tool_name": self.name,
                "status": "error",
                "error": str(e)
            }
    
    async def test_functionality(self) -> Dict[str, Any]:
        """Test tool functionality."""
        try:
            # Test basic git command
            git_test = await self._execute_command("git --version", 10)

            # Test gh CLI if authentication is available
            gh_test = {"success": False, "stdout": "", "stderr": "Authentication not available"}
            try:
                token_info = await self.auth_service.get_token_info()
                if token_info.get("authenticated", False):
                    await self.auth_service.ensure_gh_auth()
                    gh_test = await self._execute_command("gh --version", 10)
            except Exception as e:
                gh_test["stderr"] = str(e)

            return {
                "git_available": git_test.get("success", False),
                "git_version": git_test.get("stdout", "").strip(),
                "gh_available": gh_test.get("success", False),
                "gh_version": gh_test.get("stdout", "").strip(),
                "overall_status": "working" if git_test.get("success") else "issues"
            }

        except Exception as e:
            logger.error(f"Tool functionality test failed: {e}")
            return {
                "git_available": False,
                "gh_available": False,
                "overall_status": "error",
                "error": str(e)
            }

    def _get_parameter_schema(self) -> Dict[str, Any]:
        """
        Get the parameter schema for this tool.

        Returns:
            Dict[str, Any]: Dictionary describing the parameter schema
        """
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The git or gh CLI command to execute"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Optional timeout in seconds for command execution",
                    "default": 300
                }
            },
            "required": ["command"]
        }

    def _get_output_schema(self) -> Dict[str, Any]:
        """
        Get the output schema for this tool.

        Returns:
            Dict[str, Any]: Dictionary describing the output schema
        """
        return {
            "type": "object",
            "properties": {
                "success": {
                    "type": "boolean",
                    "description": "Whether the command executed successfully"
                },
                "stdout": {
                    "type": "string",
                    "description": "Standard output from the command"
                },
                "stderr": {
                    "type": "string",
                    "description": "Standard error output from the command"
                },
                "exit_code": {
                    "type": "integer",
                    "description": "Exit code of the command"
                },
                "command": {
                    "type": "string",
                    "description": "The command that was executed"
                },
                "execution_time": {
                    "type": "number",
                    "description": "Time taken to execute the command in seconds"
                },
                "error": {
                    "type": "string",
                    "description": "Error message if the execution failed"
                },
                "message": {
                    "type": "string",
                    "description": "Additional message about the execution result"
                }
            }
        } 