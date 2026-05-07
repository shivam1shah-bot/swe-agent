"""
Bug detection sub-agent for identifying potential bugs in PR code changes.

This sub-agent specializes in detecting common programming errors and bugs
that could lead to runtime failures, data corruption, or incorrect behavior.
"""

from src.agents.review_agents.constants import CATEGORY_LABELS, SubAgentCategory
from src.agents.review_agents.subagent_base import ReviewSubAgentBase
from src.agents.review_agents.subagent_registry import SubAgentRegistry


class BugDetectionSubAgent(ReviewSubAgentBase):
    """
    Sub-agent specialized in detecting potential bugs.

    Analyzes code changes for:
    - Null pointer/reference issues
    - Off-by-one errors
    - Resource leaks (file handles, connections)
    - Logic errors and edge cases
    - Exception handling issues
    - Uninitialized variables
    - Race conditions
    - Memory management issues
    """

    @property
    def category(self) -> str:
        """Return the pr-prompt-kit category for bug detection."""
        return SubAgentCategory.BUG.value

    @property
    def category_label(self) -> str:
        """Return the label for GitHub comments."""
        return CATEGORY_LABELS[SubAgentCategory.BUG.value]


# Auto-register on module import
SubAgentRegistry.register(SubAgentCategory.BUG.value, BugDetectionSubAgent)
