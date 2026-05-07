"""
Filter Layer for PR Review Suggestions.

AI-powered filtering that evaluates suggestions from sub-agents before posting
to GitHub. Uses LLM to score suggestions 0-10 and filter out nits, false
positives, and duplicates.
"""

import logging
import os
import tempfile
from typing import Any, Dict, List, Optional, Set

from pr_prompt_kit import PRAgentKit
from pr_prompt_kit.parser import parse_yaml

from src.agents.review_agents.utils.diff_line_parser import (
    FileDiffInfo,
    parse_unified_diff,
)
from src.agents.terminal_agents.claude_code import ClaudeCodeTool


class FilterLayer:
    """AI-powered filter for PR review suggestions."""

    def __init__(
        self,
        working_directory: str,
        kit: Optional[PRAgentKit] = None,
        min_score_threshold: int = 5,
        pre_filter_threshold: int = 3,
    ):
        """
        Initialize FilterLayer.

        Args:
            working_directory: Working directory for code execution
            kit: PRAgentKit instance (optional, will create if not provided)
            min_score_threshold: Minimum LLM score to keep suggestions (0-10, default: 5)
            pre_filter_threshold: Minimum importance for pre-filter (default: 3)
        """
        self._working_directory = working_directory
        self._kit = kit or PRAgentKit()
        self._claude_tool = ClaudeCodeTool.get_instance()
        self._min_score_threshold = min_score_threshold
        self._pre_filter_threshold = pre_filter_threshold
        self._logger = logging.getLogger(__name__)

        # Tool usage tracking
        self._mcp_calls: List[Dict[str, Any]] = []
        self._skills_used: List[str] = []

    @property
    def mcp_calls(self) -> List[Dict[str, Any]]:
        """Return MCP calls made during filtering."""
        return self._mcp_calls

    @property
    def skills_used(self) -> List[str]:
        """Return skills used during filtering."""
        return self._skills_used

    def reset_tool_usage(self) -> None:
        """Reset tool usage tracking for a new filtering session."""
        self._mcp_calls = []
        self._skills_used = []

    async def apply(
        self,
        suggestions: List[Dict[str, Any]],
        diff: str,
        pr_context: Dict[str, Any],
        pr_files: Optional[Set[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Apply AI-based filtering to suggestions.

        Four-stage filtering:
        1. Pre-filter: Remove obvious nits (importance < threshold)
        2. LLM evaluation: Score 0-10, detect duplicates via AI
        3. Post-filter: Keep only llm_score >= threshold, sort by score
        4. Route: Assign comment_type based on file presence in PR

        Args:
            suggestions: List of suggestion dictionaries from sub-agents
            diff: PR diff content
            pr_context: PR metadata (title, description, repository, etc.)
            pr_files: Set of file paths in the PR (for routing)

        Returns:
            Filtered and sorted list of suggestions with llm_score, llm_reasoning,
            and comment_type fields added
        """
        # Early return for empty input
        if not suggestions:
            self._logger.info("No suggestions to filter")
            return []

        # Reset tool usage tracking for this filtering session
        self.reset_tool_usage()

        self._logger.info(f"Filtering {len(suggestions)} suggestions")

        # Stage 1: Fast Python pre-filter
        candidates = self._pre_filter(suggestions)
        self._logger.info(f"After pre-filter: {len(candidates)} suggestions")

        if not candidates:
            return []

        # Stage 2: LLM evaluation (includes AI-based deduplication)
        evaluated = await self._evaluate_with_llm(candidates, diff, pr_context)

        # Stage 3: Post-filter by score
        filtered = self._post_filter(evaluated)
        self._logger.info(
            f"After post-filter: {len(filtered)} suggestions (threshold: {self._min_score_threshold})"
        )

        # Stage 4: Assign comment types based on file presence and line validity in PR
        if pr_files is not None:
            filtered = self._assign_comment_types(filtered, pr_files, diff)

        return filtered

    def _pre_filter(self, suggestions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Fast pre-filter: remove obvious nits.

        Filters out suggestions with importance < pre_filter_threshold (default: 3).
        This removes obvious nits cheaply before expensive LLM evaluation.

        Args:
            suggestions: List of suggestion dictionaries

        Returns:
            Filtered suggestions
        """
        filtered = [
            s
            for s in suggestions
            if s.get("importance", 0) >= self._pre_filter_threshold
        ]

        skipped = len(suggestions) - len(filtered)
        if skipped > 0:
            self._logger.info(
                f"Pre-filter removed {skipped} low-importance suggestions"
            )

        return filtered

    async def _evaluate_with_llm(
        self,
        suggestions: List[Dict[str, Any]],
        diff: str,
        pr_context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Evaluate suggestions using LLM with suggestion_filter_prompt.

        The LLM scores each suggestion 0-10 based on impact and accuracy,
        and detects duplicates via AI (not Python code).

        Returns suggestions with added fields:
        - llm_score: int (0-10)
        - llm_reasoning: str

        Args:
            suggestions: Candidate suggestions after pre-filter
            diff: PR diff content
            pr_context: PR metadata

        Returns:
            Suggestions with llm_score and llm_reasoning added
        """
        try:
            # Ensure all suggestions have required fields for template
            # The suggestion_filter_prompt template uses Jinja dot notation (s.existing_code)
            # which throws AttributeError if key doesn't exist
            for s in suggestions:
                if "existing_code" not in s:
                    s["existing_code"] = ""

            # Render prompt
            rendered = self._kit.prompts.render(
                "suggestion_filter_prompt",
                variables={
                    "title": pr_context.get("title", ""),
                    "description": pr_context.get("description", ""),
                    "diff": diff,
                    "suggestions": suggestions,
                },
            )

            self._logger.info(f"Evaluating {len(suggestions)} suggestions with LLM")

            # Create temp file for stream-json output (enables MCP/Skill tracking)
            output_fd, output_file = tempfile.mkstemp(
                prefix="review-filter-", suffix=".jsonl"
            )
            os.close(output_fd)

            try:
                # Execute via ClaudeCodeTool with stream-json for MCP tracking
                response = await self._claude_tool.execute(
                    {
                        "prompt": rendered.user,
                        "system_prompt": rendered.system,
                        "working_directory": self._working_directory,
                        "additional_allowed_tools": "Skill",  # Enable Skill tool for reviews
                        "agent_name": "code-review",  # For Prometheus metrics labelling
                        "output_file": output_file,  # stream-json for MCP/Skill tracking
                    }
                )

                # Capture tool usage from response (populated by stream-json parsing)
                if response.get("mcp_calls"):
                    self._mcp_calls.extend(response["mcp_calls"])
                if response.get("skills_used"):
                    self._skills_used.extend(response["skills_used"])

                if self._mcp_calls or self._skills_used:
                    self._logger.info(
                        f"FilterLayer tool usage: {len(self._mcp_calls)} MCP calls, "
                        f"{len(self._skills_used)} skills"
                    )

                # Parse and merge scores
                return self._merge_scores(suggestions, response)
            finally:
                try:
                    os.unlink(output_file)
                except OSError:
                    pass

        except KeyError as e:
            self._logger.error(
                f"Prompt 'suggestion_filter_prompt' not found in pr-prompt-kit: {e}"
            )
            # Fallback: use importance as score
            for s in suggestions:
                s["llm_score"] = s.get("importance", 5)
                s["llm_reasoning"] = "Filter prompt not available, using importance"
            return suggestions
        except Exception as e:
            self._logger.error(f"LLM evaluation failed: {e}")
            # Fallback: use importance as score
            for s in suggestions:
                s["llm_score"] = s.get("importance", 5)
                s["llm_reasoning"] = f"LLM evaluation error: {str(e)}"
            return suggestions

    def _merge_scores(
        self,
        original_suggestions: List[Dict[str, Any]],
        response: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Parse LLM YAML response and merge scores into suggestions.

        Handles errors gracefully:
        - If LLM fails: use original importance as score
        - If parse fails: score = 0
        - If index mismatch: score = 0

        Args:
            original_suggestions: Original suggestions before LLM evaluation
            response: Response from ClaudeCodeTool.execute()

        Returns:
            Suggestions with llm_score and llm_reasoning added
        """
        if "error" in response:
            self._logger.warning(f"LLM error: {response.get('message')}")
            # Fallback: use original importance
            for s in original_suggestions:
                s["llm_score"] = s.get("importance", 5)
                s["llm_reasoning"] = "LLM evaluation failed, using importance"
            return original_suggestions

        result_text = response.get("result", "")
        try:
            parsed = parse_yaml(result_text)
            evaluations = parsed.get("evaluations", [])

            if not evaluations:
                self._logger.warning("LLM returned empty evaluations")
                for s in original_suggestions:
                    s["llm_score"] = s.get("importance", 5)
                    s["llm_reasoning"] = "No evaluations from LLM"
                return original_suggestions

            # Map evaluations to suggestions by index
            for i, suggestion in enumerate(original_suggestions):
                if i < len(evaluations):
                    eval_result = evaluations[i]
                    suggestion["llm_score"] = eval_result.get("score", 0)
                    suggestion["llm_reasoning"] = eval_result.get("reason", "")
                else:
                    suggestion["llm_score"] = 0
                    suggestion["llm_reasoning"] = "No evaluation received"
                    self._logger.warning(
                        f"No evaluation for suggestion {i} in {suggestion.get('file', 'unknown')}"
                    )

            return original_suggestions

        except Exception as e:
            self._logger.error(f"Failed to parse LLM response: {e}")
            # Fallback
            for s in original_suggestions:
                s["llm_score"] = 0
                s["llm_reasoning"] = f"Parse error: {str(e)}"
            return original_suggestions

    def _post_filter(
        self, suggestions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Filter suggestions by llm_score and sort.

        Keeps only suggestions with llm_score >= min_score_threshold.
        Sorts by (llm_score, importance) descending (highest scores first).

        Args:
            suggestions: Suggestions with llm_score added

        Returns:
            Filtered and sorted suggestions
        """
        # Filter by threshold
        filtered = [
            s
            for s in suggestions
            if s.get("llm_score", 0) >= self._min_score_threshold
        ]

        # Sort by score (higher scores first)
        sorted_suggestions = sorted(
            filtered,
            key=lambda s: (s.get("llm_score", 0), s.get("importance", 0)),
            reverse=True,
        )

        return sorted_suggestions

    def _assign_comment_types(
        self,
        suggestions: List[Dict[str, Any]],
        pr_files: Set[str],
        diff: str,
    ) -> List[Dict[str, Any]]:
        """
        Assign comment_type based on file presence AND line validity in PR diff.

        Routing logic:
        - Files IN PR AND lines in diff hunks → "inline" (inline comment with code)
        - Files IN PR but lines NOT in diff hunks → "general" (review body only)
        - Files NOT in PR → "general" (review body only)

        This prevents GitHub 422 errors when posting inline comments on lines
        that aren't part of the PR diff (e.g., suggestions on unchanged lines).

        For general suggestions, we clear suggestion_code since inline code
        suggestions cannot be posted for lines outside the diff.

        Args:
            suggestions: List of suggestion dictionaries
            pr_files: Set of file paths in the PR
            diff: The PR diff content for line validation

        Returns:
            Suggestions with comment_type field added
        """
        # Parse diff to get valid line ranges per file
        diff_info = parse_unified_diff(diff) if diff else {}

        for suggestion in suggestions:
            file_path = suggestion.get("file", "")
            line = suggestion.get("line", 0)
            line_end = suggestion.get("line_end")

            # Check 1: File must be in PR
            if file_path not in pr_files:
                suggestion["comment_type"] = "general"
                suggestion["suggestion_code"] = None
                self._logger.info(
                    f"Routing '{file_path}:{line}' as general (file not in PR)"
                )
                continue

            # Check 2: File must have parsed diff info
            file_diff = diff_info.get(file_path)
            if not file_diff:
                suggestion["comment_type"] = "general"
                suggestion["suggestion_code"] = None
                self._logger.info(
                    f"Routing '{file_path}:{line}' as general (no diff info for file)"
                )
                continue

            # Check 3: Line(s) must be within valid diff hunks
            if line_end and line_end > line:
                is_valid = file_diff.is_range_valid(line, line_end)
            else:
                is_valid = file_diff.is_line_valid(line)

            if is_valid:
                suggestion["comment_type"] = "inline"
            else:
                suggestion["comment_type"] = "general"
                suggestion["suggestion_code"] = None
                valid_ranges = self._format_valid_ranges(file_diff)
                self._logger.info(
                    f"Routing '{file_path}:{line}' as general "
                    f"(line not in diff, valid ranges: {valid_ranges})"
                )

        return suggestions

    def _format_valid_ranges(self, file_diff: FileDiffInfo) -> str:
        """Format valid line ranges for logging.

        Args:
            file_diff: FileDiffInfo containing hunks.

        Returns:
            String representation of valid line ranges.
        """
        ranges = file_diff.get_valid_ranges()
        if not ranges:
            return "none"
        return ", ".join(f"{start}-{end}" for start, end in ranges)
