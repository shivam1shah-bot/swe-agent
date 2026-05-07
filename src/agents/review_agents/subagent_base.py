"""
Base class for review sub-agents.

Provides the common infrastructure for all specialized review agents:
- Prompt rendering via pr-prompt-kit
- Execution via ClaudeCodeTool
- YAML response parsing
- Structured result handling
"""

import logging
import os
import tempfile
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pr_prompt_kit import PRAgentKit, RenderedPrompt, parse_yaml

from src.agents.review_agents.constants import CATEGORY_LABELS
from src.agents.review_agents.models import SubAgentResult
from src.agents.terminal_agents.claude_code import ClaudeCodeTool

logger = logging.getLogger(__name__)


class ReviewSubAgentBase(ABC):
    """
    Abstract base class for review sub-agents.

    Each sub-agent specializes in a specific type of code analysis
    (bug detection, security, code quality, etc.) and uses pr-prompt-kit
    prompts executed via Claude Code CLI.

    Usage:
        class BugDetectionSubAgent(ReviewSubAgentBase):
            @property
            def category(self) -> str:
                return "bug"

            @property
            def category_label(self) -> str:
                return "BUG"

        agent = BugDetectionSubAgent(working_directory="/path/to/repo")
        result = await agent.execute(diff="...", pr_number=123, repository="org/repo")
    """

    def __init__(
        self,
        working_directory: str,
        kit: Optional[PRAgentKit] = None,
        confidence_threshold: float = 0.6,
    ):
        """
        Initialize the sub-agent.

        Args:
            working_directory: Directory where Claude Code CLI will execute
            kit: Optional PRAgentKit instance (creates new one if not provided)
            confidence_threshold: Minimum confidence for suggestions (passed to prompts)
        """
        self._working_directory = working_directory
        self._kit = kit or PRAgentKit()
        self._confidence_threshold = confidence_threshold
        self._claude_tool = ClaudeCodeTool.get_instance()

        logger.info(
            f"Initialized {self.__class__.__name__} sub-agent "
            f"(category={self.category}, confidence_threshold={confidence_threshold})"
        )

    @property
    @abstractmethod
    def category(self) -> str:
        """
        Return the pr-prompt-kit category this sub-agent handles.

        This should match the category name in pr-prompt-kit
        (e.g., 'bug', 'security', 'code_quality', 'performance', 'testing').

        Returns:
            str: The category identifier
        """
        pass

    @property
    @abstractmethod
    def category_label(self) -> str:
        """
        Return the human-readable category label for GitHub comments.

        This is used in the comment formatting (e.g., 'BUG', 'SECURITY').

        Returns:
            str: The category label for display
        """
        pass

    def should_execute(self, diff: str, **context) -> tuple[bool, str | None]:
        """
        Determine if this sub-agent should execute based on the diff content.

        Override this method in sub-agents that should only run for specific
        file types or conditions. The default implementation always executes.

        This hook enables:
        - Frontend-only agents (BladeSubAgent runs only for .tsx/.jsx files)
        - Language-specific agents (Python security only for .py files)
        - Conditional execution based on PR context

        Args:
            diff: The PR diff content to analyze
            **context: Additional context (pr_number, repository, etc.)

        Returns:
            Tuple of (should_run, skip_reason):
            - should_run: True if agent should execute, False to skip
            - skip_reason: Human-readable reason if skipping, None otherwise

        Example:
            def should_execute(self, diff: str, **context) -> tuple[bool, str | None]:
                if not has_frontend_files(diff):
                    return False, "No frontend files in diff"
                return True, None
        """
        return True, None

    async def execute(
        self,
        diff: str,
        pr_number: int,
        repository: str,
        title: str,
        description: str,
        branch: str,
        **kwargs: Any,
    ) -> SubAgentResult:
        """
        Execute the sub-agent analysis on the given diff.

        This is the main entry point for sub-agent execution. It:
        1. Checks should_execute() hook for conditional execution
        2. Renders the prompt using pr-prompt-kit
        3. Executes via ClaudeCodeTool
        4. Parses the YAML response
        5. Returns a structured SubAgentResult

        Args:
            diff: The PR diff content to analyze
            pr_number: Pull request number
            repository: Repository in owner/name format (e.g., 'razorpay/api')
            title: PR title
            description: PR description/body
            branch: Source branch name
            **kwargs: Additional context variables for the prompt

        Returns:
            SubAgentResult with suggestions and execution metadata
        """
        start_time = time.time()

        # Check if sub-agent should execute based on diff content
        should_run, skip_reason = self.should_execute(
            diff,
            pr_number=pr_number,
            repository=repository,
            title=title,
            description=description,
            branch=branch,
            **kwargs,
        )

        if not should_run:
            logger.info(
                f"SubAgent[{self.category}] skipping execution: {skip_reason}"
            )
            return SubAgentResult(
                category=self.category,
                suggestions=[],
                success=True,
                error=None,
                execution_time_ms=0,
                skipped=True,
                skip_reason=skip_reason,
            )

        try:
            # 1. Render prompt using pr-prompt-kit
            logger.info(f"SubAgent[{self.category}] rendering prompt...")
            rendered_prompt = self._render_prompt(
                diff=diff,
                pr_number=pr_number,
                repository=repository,
                title=title,
                description=description,
                branch=branch,
                **kwargs,
            )

            # 2. Execute via Claude Code CLI
            logger.info(f"SubAgent[{self.category}] executing Claude prompt...")
            response_text, mcp_calls, skills_used = await self._execute_claude(rendered_prompt)

            # 3. Parse YAML response
            logger.info(f"SubAgent[{self.category}] parsing response...")
            suggestions = self._parse_response(response_text)

            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.info(
                f"SubAgent[{self.category}] completed in {execution_time_ms}ms, "
                f"found {len(suggestions)} suggestions"
            )

            return SubAgentResult(
                category=self.category,
                suggestions=suggestions,
                success=True,
                error=None,
                execution_time_ms=execution_time_ms,
                mcp_calls=mcp_calls,
                skills_used=skills_used,
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.error(
                f"SubAgent[{self.category}] failed after {execution_time_ms}ms: {e}",
                exc_info=True,
            )

            return SubAgentResult(
                category=self.category,
                suggestions=[],
                success=False,
                error=str(e),
                execution_time_ms=execution_time_ms,
            )

    def _render_prompt(
        self,
        diff: str,
        pr_number: int,
        repository: str,
        title: str,
        description: str,
        branch: str,
        **kwargs: Any,
    ) -> RenderedPrompt:
        """
        Render the prompt using pr-prompt-kit.

        Args:
            diff: The PR diff content
            pr_number: Pull request number
            repository: Repository in owner/name format
            title: PR title
            description: PR description/body
            branch: Source branch name
            **kwargs: Additional variables for the prompt

        Returns:
            RenderedPrompt with system and user prompts
        """
        variables = {
            "diff": diff,
            "pr_number": pr_number,
            "repository": repository,
            "title": title,
            "description": description,
            "branch": branch,
            "confidence_threshold": self._confidence_threshold,
            **kwargs,
        }

        return self._kit.render_subagent(self.category, variables=variables)

    async def _execute_claude(self, rendered_prompt: RenderedPrompt) -> tuple[str, list, list]:
        """
        Execute the rendered prompt via ClaudeCodeTool with working directory context.

        Uses stream-json mode (via output_file) to enable multi-turn tool
        invocation tracking. This allows the Skill tool to be invoked and
        tracked, and captures MCP tool calls made during execution.

        The working_directory parameter is passed to ClaudeCodeTool which sets the
        subprocess cwd, giving Claude access to the repository via file tools
        (Read, Glob, Grep) without changing the process's global working directory.

        Args:
            rendered_prompt: The prompt with system and user content

        Returns:
            Tuple of (result_text, mcp_calls, skills_used):
            - result_text: The text response from Claude
            - mcp_calls: List of MCP tool invocations
            - skills_used: List of skill names invoked

        Raises:
            RuntimeError: If Claude execution fails
        """
        # Create temp file for stream-json output (enables skill tracking)
        fd, output_file = tempfile.mkstemp(
            prefix=f"subagent-{self.category}-",
            suffix=".jsonl",
            dir=self._working_directory,
        )
        os.close(fd)

        try:
            params = {
                "action": "run_prompt",
                "prompt": rendered_prompt.user,
                "system_prompt": rendered_prompt.system,
                "additional_allowed_tools": "Skill",  # Enable Skill tool for reviews
                "working_directory": self._working_directory,  # Pass to subprocess cwd
                "output_file": output_file,  # Enables stream-json mode
            }

            logger.info(
                f"SubAgent[{self.category}] executing with working directory: "
                f"{self._working_directory}"
            )

            response = await self._claude_tool.execute(params)
        finally:
            # Cleanup temp output file
            try:
                if os.path.exists(output_file):
                    os.unlink(output_file)
            except OSError as cleanup_err:
                logger.warning(
                    f"SubAgent[{self.category}] failed to cleanup output file: {cleanup_err}"
                )

        # Check for errors
        if "error" in response:
            error_msg = response.get("message", response.get("error", "Unknown error"))
            raise RuntimeError(f"Claude execution failed: {error_msg}")

        # Extract the result text
        result = response.get("result", "")
        if not result:
            logger.warning(f"SubAgent[{self.category}] received empty response from Claude")

        # Extract tool usage from response (populated by stream-json parser)
        mcp_calls = response.get("mcp_calls", [])
        skills_used = response.get("skills_used", [])

        if mcp_calls or skills_used:
            logger.info(
                f"SubAgent[{self.category}] tool usage: "
                f"{len(mcp_calls)} MCP calls, {len(skills_used)} skills"
            )

        return result, mcp_calls, skills_used

    def _parse_response(self, response_text: str) -> List[Dict[str, Any]]:
        """
        Parse the YAML response from Claude into suggestions.

        Expects YAML format with a 'suggestions' list:
        ```yaml
        suggestions:
          - file: src/main.py
            line: 42
            importance: 7
            confidence: 0.85
            description: "Potential null pointer..."
            suggestion_code: "if value is not None:"
        ```

        Args:
            response_text: Raw text response from Claude

        Returns:
            List of suggestion dictionaries with category labels added
        """
        if not response_text or not response_text.strip():
            logger.warning(f"SubAgent[{self.category}] received empty response")
            return []

        try:
            # Use pr-prompt-kit's parse_yaml for consistent parsing
            parsed = parse_yaml(response_text)

            if parsed is None:
                logger.warning(f"SubAgent[{self.category}] parse_yaml returned None")
                return []

            # Extract suggestions list
            suggestions = parsed.get("suggestions", [])

            if not isinstance(suggestions, list):
                logger.warning(
                    f"SubAgent[{self.category}] expected list of suggestions, "
                    f"got {type(suggestions).__name__}"
                )
                return []

            # Add category label to each suggestion if not present
            for suggestion in suggestions:
                if isinstance(suggestion, dict) and "category" not in suggestion:
                    suggestion["category"] = self.category_label

            return suggestions

        except Exception as e:
            logger.warning(
                f"SubAgent[{self.category}] failed to parse YAML response: {e}"
            )
            # Log a preview of the response for debugging
            preview = response_text[:500] if len(response_text) > 500 else response_text
            logger.debug(f"Response preview: {preview}")
            return []

