"""
Core sub-agents for PR review.

Importing this module registers all core sub-agents with the SubAgentRegistry.
Each sub-agent is a thin wrapper around ReviewSubAgentBase that specifies
its category for pr-prompt-kit prompt selection.

Usage:
    # Import to register all core sub-agents
    from src.agents.review_agents import subagents

    # Or import specific sub-agents
    from src.agents.review_agents.subagents import BugDetectionSubAgent

    # Create agents via registry (recommended)
    from src.agents.review_agents.subagent_registry import SubAgentRegistry
    agents = SubAgentRegistry.create_core_agents("/path/to/repo")
"""

# Import sub-agents to trigger their registration with SubAgentRegistry
from src.agents.review_agents.subagents.bug_detection import BugDetectionSubAgent
from src.agents.review_agents.subagents.code_quality import CodeQualitySubAgent
from src.agents.review_agents.subagents.security import SecuritySubAgent
from src.agents.review_agents.subagents.styleguide import StyleGuideSubAgent
from src.agents.review_agents.subagents.i18n import I18nSubAgent
from src.agents.review_agents.subagents.blade import BladeSubAgent
from src.agents.review_agents.subagents.svelte import SvelteSubAgent
from src.agents.review_agents.subagents.pre_mortem import PreMortemSubAgent

__all__ = [
    "BugDetectionSubAgent",
    "SecuritySubAgent",
    "CodeQualitySubAgent",
    "StyleGuideSubAgent",
    "I18nSubAgent",
    "BladeSubAgent",
    "SvelteSubAgent",
    "PreMortemSubAgent",
]
