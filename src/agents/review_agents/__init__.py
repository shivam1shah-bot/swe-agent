"""
PR Review Agents package.

Provides the ReviewMainAgent orchestrator and sub-agents for
comprehensive code review analysis.

Usage:
    # Import and register all core sub-agents
    from src.agents.review_agents import subagents
    from src.agents.review_agents import SubAgentRegistry

    # Create all core sub-agents for parallel execution
    agents = SubAgentRegistry.create_core_agents("/path/to/repo")

    # Or create a specific sub-agent
    bug_agent = SubAgentRegistry.create_agent("bug", "/path/to/repo")
"""

from src.agents.review_agents.constants import (
    ALL_CATEGORIES,
    CATEGORY_LABELS,
    CATEGORY_TO_PROMPT_KIT,
    CORE_CATEGORIES,
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_IMPORTANCE_THRESHOLD,
    DEFAULT_NIT_THRESHOLD,
    ReviewAgentType,
    Severity,
    SubAgentCategory,
    get_severity,
)
from src.agents.review_agents.models import (
    PRDescriptionResult,
    ReviewResult,
    SubAgentResult,
    Suggestion,
)
from src.agents.review_agents.subagent_base import ReviewSubAgentBase
from src.agents.review_agents.subagent_registry import SubAgentRegistry

# Import subagents module to make it available as review_agents.subagents
from src.agents.review_agents import subagents
from src.agents.review_agents.subagents import (
    BugDetectionSubAgent,
    CodeQualitySubAgent,
    SecuritySubAgent,
)

__all__ = [
    # Enums
    "SubAgentCategory",
    "ReviewAgentType",
    "Severity",
    # Constants
    "CORE_CATEGORIES",
    "ALL_CATEGORIES",
    "DEFAULT_CONFIDENCE_THRESHOLD",
    "DEFAULT_IMPORTANCE_THRESHOLD",
    "DEFAULT_NIT_THRESHOLD",
    "CATEGORY_LABELS",
    "CATEGORY_TO_PROMPT_KIT",
    # Functions
    "get_severity",
    # Models
    "Suggestion",
    "SubAgentResult",
    "ReviewResult",
    "PRDescriptionResult",
    # Base Classes
    "ReviewSubAgentBase",
    # Registry
    "SubAgentRegistry",
    # Sub-Agents
    "BugDetectionSubAgent",
    "SecuritySubAgent",
    "CodeQualitySubAgent",
    # Subagents module
    "subagents",
]
