"""
Security analysis sub-agent for identifying security vulnerabilities in PR code changes.

This sub-agent specializes in detecting security issues that could lead to
data breaches, unauthorized access, or system compromise.
"""

from src.agents.review_agents.constants import CATEGORY_LABELS, SubAgentCategory
from src.agents.review_agents.subagent_base import ReviewSubAgentBase
from src.agents.review_agents.subagent_registry import SubAgentRegistry


class SecuritySubAgent(ReviewSubAgentBase):
    """
    Sub-agent specialized in detecting security vulnerabilities.

    Analyzes code changes for:
    - SQL injection vulnerabilities
    - Cross-site scripting (XSS)
    - Authentication/authorization issues
    - Secrets/credentials exposure
    - Input validation gaps
    - Insecure cryptographic practices
    - Path traversal vulnerabilities
    - Command injection
    - SSRF vulnerabilities
    - Insecure deserialization
    """

    @property
    def category(self) -> str:
        """Return the pr-prompt-kit category for security analysis."""
        return SubAgentCategory.SECURITY.value

    @property
    def category_label(self) -> str:
        """Return the label for GitHub comments."""
        return CATEGORY_LABELS[SubAgentCategory.SECURITY.value]


# Auto-register on module import
SubAgentRegistry.register(SubAgentCategory.SECURITY.value, SecuritySubAgent)
