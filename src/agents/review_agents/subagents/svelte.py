"""
Svelte sub-agent for reviewing Svelte component patterns.

This sub-agent specializes in detecting Svelte-specific issues in frontend
code. It only executes when the PR contains .svelte files.

Prompts are managed in pr-prompt-kit (svelte_prompt.toml).
"""

from typing import Set

from src.agents.review_agents.constants import CATEGORY_LABELS, SubAgentCategory
from src.agents.review_agents.subagent_base import ReviewSubAgentBase
from src.agents.review_agents.subagent_registry import SubAgentRegistry
from src.agents.review_agents.utils.file_type_detector import has_files_with_extensions


class SvelteSubAgent(ReviewSubAgentBase):
    """
    Sub-agent specialized in Svelte component compliance review.

    Only executes when the PR diff contains .svelte files.
    Uses the should_execute() hook to skip non-Svelte PRs.

    Prompts are loaded from pr-prompt-kit's svelte_prompt.toml.
    """

    # Only .svelte files trigger execution — narrower than Blade which
    # triggers on any frontend file. This avoids false positives on repos
    # that have .ts/.js files but aren't Svelte projects.
    SVELTE_EXTENSIONS: Set[str] = {".svelte"}

    @property
    def category(self) -> str:
        """Return the category identifier for this sub-agent."""
        return SubAgentCategory.SVELTE.value

    @property
    def category_label(self) -> str:
        """Return the label for GitHub comments."""
        return CATEGORY_LABELS[SubAgentCategory.SVELTE.value]

    def should_execute(self, diff: str, **context) -> tuple[bool, str | None]:
        """
        Only execute when .svelte files are present in the diff.

        Args:
            diff: The PR diff content
            **context: Additional context (unused)

        Returns:
            Tuple of (should_run, skip_reason)
        """
        if not has_files_with_extensions(diff, self.SVELTE_EXTENSIONS):
            return False, "No .svelte files detected in diff"

        return True, None


# Auto-register on module import
SubAgentRegistry.register(SubAgentCategory.SVELTE.value, SvelteSubAgent)
