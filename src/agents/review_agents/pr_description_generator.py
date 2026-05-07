"""
PR Description Generator for automated PR summary generation.

Uses pr-prompt-kit's description prompt to generate:
- PR summary
- Change type (feature/bugfix/refactor)
- Key changes list
- Potential risks
"""

import asyncio
import logging
import os
import re
from datetime import datetime
from typing import Dict, Any, List, Optional

from pr_prompt_kit import PRAgentKit

from src.agents.terminal_agents.claude_code import ClaudeCodeTool
from src.agents.review_agents.models import PRDescriptionResult
from src.providers.github.auth_service import GitHubAuthService
from src.constants.github_bots import GitHubBot

logger = logging.getLogger(__name__)


class PRDescriptionGenerator:
    """Generates AI-powered PR descriptions using pr-prompt-kit."""

    def __init__(
        self,
        working_directory: str,
        kit: Optional[PRAgentKit] = None,
        github_bot: GitHubBot = GitHubBot.CODE_REVIEW,
    ):
        """
        Initialize PR Description Generator.

        Args:
            working_directory: Directory for Claude Code execution
            kit: Optional PRAgentKit instance (creates new if not provided)
            github_bot: GitHub bot for authentication
        """
        self._working_directory = working_directory
        self._kit = kit or PRAgentKit()
        self._github_bot = github_bot
        self._auth_service = GitHubAuthService()
        self._claude_tool = ClaudeCodeTool.get_instance()
        self._logger = logging.getLogger(__name__)

    async def generate_and_post(
        self,
        diff: str,
        repository: str,
        pr_number: int,
        title: str,
        description: str,
        branch: str,
        target_branch: str = "main",
    ) -> PRDescriptionResult:
        """
        Generate PR description and post it as a PR comment.

        Args:
            diff: PR diff content
            repository: Repository in "owner/repo" format
            pr_number: Pull request number
            title: Current PR title
            description: Current PR description/body
            branch: Source branch name
            target_branch: Target branch name (default: main)

        Returns:
            PRDescriptionResult with generation and posting status
        """
        result = PRDescriptionResult()

        try:
            # 1. Get configuration
            config = self._kit.config.get_description_config()

            # 2. Render description prompt
            self._logger.info(f"Rendering description prompt for PR #{pr_number}")
            rendered = self._kit.render_description(
                variables={
                    "title": title or "",
                    "branch": branch,
                    "target_branch": target_branch,
                    "diff": diff,
                    "description": description or "",
                    "generate_ai_title": config.generate_ai_title,
                    "use_bullet_points": config.use_bullet_points,
                    "enable_pr_type": config.enable_pr_type,
                    "enable_pr_diagram": config.enable_pr_diagram,
                    "extra_instructions": "",  # Optional extra instructions for LLM
                    "date": datetime.now().strftime("%Y-%m-%d"),  # Current date
                    "pr_number": pr_number,
                    "repository": repository,
                }
            )

            # 3. Execute via Claude Code
            self._logger.info(f"Executing description generation for PR #{pr_number}")
            response = await self._execute_claude(rendered)

            # 4. Parse markdown response
            parsed = self._parse_markdown_description(response)

            # 5. Extract fields from parsed response
            result.full_description = parsed.get("full_description")
            result.summary = parsed.get("summary")

            # 6. Post description as PR comment
            if result.full_description:
                self._logger.info(f"Posting description comment to PR #{pr_number}")
                await self._post_description_comment(
                    repository, pr_number, result
                )
                result.posted = True
            else:
                self._logger.warning(f"No valid description generated for PR #{pr_number}")

            return result

        except Exception as e:
            self._logger.error(
                f"Description generation failed for PR #{pr_number}: {e}",
                exc_info=True,
            )
            result.error = str(e)
            return result

    async def _execute_claude(self, rendered_prompt) -> str:
        """Execute Claude prompt via ClaudeCodeTool."""
        result = await self._claude_tool.execute(
            params={
                "action": "run_prompt",
                "prompt": rendered_prompt.user,
                "system_prompt": rendered_prompt.system,
                "working_directory": self._working_directory,
                "additional_allowed_tools": "Skill",  # Enable Skill tool for reviews
            }
        )

        if result.get("error"):
            raise RuntimeError(f"Claude execution failed: {result['error']}")

        return result.get("result", "")

    def _parse_markdown_description(self, response: str) -> Dict[str, Any]:
        """
        Parse the 5-section PR description format from LLM response.

        Expects format starting with <!-- pr-description-bot --> marker.
        The LLM outputs a complete markdown description that should be posted directly.

        Args:
            response: LLM response text with markdown sections

        Returns:
            Dictionary with full_description and summary fields
        """
        result: Dict[str, Any] = {}

        # Look for bot marker - indicates valid format
        bot_marker = "<!-- pr-description-bot -->"
        if bot_marker not in response:
            self._logger.warning("Response missing bot marker, cannot parse")
            return result

        # Extract everything from bot marker onwards
        marker_pos = response.find(bot_marker)
        full_description = response[marker_pos:].strip()
        result["full_description"] = full_description

        # Extract summary for logging/validation
        pr_desc_match = re.search(
            r"## PR Description\s*\n(.+?)(?=\n## |\Z)",
            full_description,
            re.DOTALL,
        )
        if pr_desc_match:
            result["summary"] = pr_desc_match.group(1).strip()

        self._logger.debug(
            f"Parsed description: has_full={bool(result.get('full_description'))}, "
            f"summary_length={len(result.get('summary', ''))}"
        )

        return result

    async def _find_existing_bot_comment(
        self,
        repository: str,
        pr_number: int,
        env: dict,
    ) -> Optional[int]:
        """
        Find existing bot description comment ID.

        Args:
            repository: Repository in "owner/repo" format
            pr_number: Pull request number
            env: Environment variables with GITHUB_TOKEN

        Returns:
            Comment ID if found, None otherwise
        """
        process = await asyncio.create_subprocess_exec(
            "gh", "api",
            f"repos/{repository}/issues/{pr_number}/comments",
            "--jq", '.[] | select(.body | contains("<!-- pr-description-bot -->")) | .id',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            self._logger.warning(f"Failed to fetch comments: {stderr.decode()}")
            return None

        # Get first matching comment ID
        output = stdout.decode().strip()
        if output:
            # May have multiple IDs (one per line), take first
            first_id = output.split('\n')[0].strip()
            if first_id.isdigit():
                return int(first_id)

        return None

    async def _update_comment(
        self,
        repository: str,
        comment_id: int,
        body: str,
        env: dict,
    ) -> None:
        """
        Update an existing comment via GitHub API.

        Args:
            repository: Repository in "owner/repo" format
            comment_id: Comment ID to update
            body: New comment body
            env: Environment variables with GITHUB_TOKEN
        """
        process = await asyncio.create_subprocess_exec(
            "gh", "api",
            f"repos/{repository}/issues/comments/{comment_id}",
            "--method", "PATCH",
            "--field", f"body={body}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(f"Failed to update comment: {stderr.decode()}")

        self._logger.info(f"Updated existing comment {comment_id}")

    async def _post_description_comment(
        self,
        repository: str,
        pr_number: int,
        desc_result: PRDescriptionResult,
    ) -> None:
        """
        Post PR description as a comment using gh CLI.

        Posts the full formatted description from the LLM directly.

        Args:
            repository: Repository in "owner/repo" format
            pr_number: Pull request number
            desc_result: PRDescriptionResult with full_description
        """
        # Use full formatted description from LLM
        if desc_result.full_description:
            comment_body = desc_result.full_description
        else:
            # Fallback (shouldn't happen with new prompt)
            comment_body = (
                "## PR Description\n\n"
                f"{desc_result.summary or 'No description generated.'}"
            )

        # Add footer
        comment_body += "\n\n---\n*Generated by rCoRe*"

        # Get GitHub token
        token = await self._auth_service.get_token(self._github_bot)
        env = os.environ.copy()
        env["GITHUB_TOKEN"] = token

        # Check for existing bot comment
        existing_comment_id = await self._find_existing_bot_comment(
            repository, pr_number, env
        )

        if existing_comment_id:
            # Update existing comment
            self._logger.info(
                f"Found existing description comment {existing_comment_id}, updating..."
            )
            await self._update_comment(repository, existing_comment_id, comment_body, env)
            self._logger.info(
                f"Updated description comment on {repository}#{pr_number}"
            )
        else:
            # Create new comment
            self._logger.info(
                f"No existing description comment found, creating new..."
            )
            process = await asyncio.create_subprocess_exec(
                "gh",
                "pr",
                "comment",
                str(pr_number),
                "--repo",
                repository,
                "--body",
                comment_body,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                raise RuntimeError(
                    f"Failed to post description comment: {error_msg}"
                )

            self._logger.info(
                f"Posted new description comment to {repository}#{pr_number}"
            )
