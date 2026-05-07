"""
Sub-Agent Implementations

This package contains implementations of specific sub-agents.
"""

from src.services.comment_analyzer.agents.i18n_agent import I18nSubAgent
from src.services.comment_analyzer.sub_agent_registry import SubAgentRegistry

# Register all sub-agents
SubAgentRegistry.register("i18n", I18nSubAgent)

# Future sub-agents can be registered here:
# SubAgentRegistry.register("security", SecuritySubAgent)
# SubAgentRegistry.register("performance", PerformanceSubAgent)
# SubAgentRegistry.register("code_quality", CodeQualitySubAgent)

__all__ = ["I18nSubAgent"]
