"""
Code quality sub-agent for analyzing code quality issues in PR code changes.

This sub-agent specializes in detecting code quality issues that could lead to
maintainability problems, technical debt, or developer confusion.
"""

from src.agents.review_agents.constants import CATEGORY_LABELS, SubAgentCategory
from src.agents.review_agents.subagent_base import ReviewSubAgentBase
from src.agents.review_agents.subagent_registry import SubAgentRegistry


class CodeQualitySubAgent(ReviewSubAgentBase):
    """
    Sub-agent specialized in detecting code quality issues.

    Analyzes code changes for:
    - Code complexity (cyclomatic complexity)
    - Naming conventions and clarity
    - Code duplication
    - SOLID principle violations
    - Error handling patterns
    - Dead code
    - Magic numbers/strings
    - Documentation gaps
    - Function/method length
    - Coupling and cohesion issues
    """

    @property
    def category(self) -> str:
        """Return the pr-prompt-kit category for code quality analysis."""
        return SubAgentCategory.CODE_QUALITY.value

    @property
    def category_label(self) -> str:
        """Return the label for GitHub comments."""
        return CATEGORY_LABELS[SubAgentCategory.CODE_QUALITY.value]


# Auto-register on module import
SubAgentRegistry.register(SubAgentCategory.CODE_QUALITY.value, CodeQualitySubAgent)
