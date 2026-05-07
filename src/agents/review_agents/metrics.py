"""
Prometheus Metrics for Claude Code Plugins.

Exposes metrics for MCP tool usage and Skills invocations across all plugins
in the marketplace. Metrics are registered globally on import and can be
recorded during plugin execution (code-review, discover, etc.) or PR review workflows.
"""

import logging
from typing import Any, Dict, List, Optional

from prometheus_client import Counter, Histogram, REGISTRY

logger = logging.getLogger(__name__)


# =============================================================================
# MCP Tool Usage Metrics
# =============================================================================

# Counter for total MCP tool invocations
MCP_TOOL_CALLS_TOTAL = Counter(
    "swe_agent_plugin_mcp_tool_calls_total",
    "Total number of MCP tool invocations across all plugins",
    labelnames=["mcp_server", "tool_name", "repository", "plugin_name"],
    registry=REGISTRY,
)

# Counter for MCP server usage (aggregated by server)
MCP_SERVER_USAGE_TOTAL = Counter(
    "swe_agent_plugin_mcp_server_usage_total",
    "Total number of times each MCP server was used across all plugins",
    labelnames=["mcp_server", "repository", "plugin_name"],
    registry=REGISTRY,
)


# =============================================================================
# Skills Usage Metrics
# =============================================================================

# Counter for skill invocations
SKILLS_INVOCATIONS_TOTAL = Counter(
    "swe_agent_plugin_skills_invocations_total",
    "Total number of skill invocations across all plugins",
    labelnames=["skill_name", "repository", "plugin_name"],
    registry=REGISTRY,
)


# =============================================================================
# Execution Metrics
# =============================================================================

# Histogram for execution duration
EXECUTION_DURATION_SECONDS = Histogram(
    "swe_agent_plugin_execution_duration_seconds",
    "Duration of plugin execution in seconds",
    labelnames=["repository", "status", "plugin_name"],
    buckets=[5, 10, 30, 60, 120, 300, 600, 1200],  # 5s to 20min
    registry=REGISTRY,
)

# =============================================================================
# PR Severity Assessment Metrics
# =============================================================================

# Counter for PR severity assessments
PR_SEVERITY_TOTAL = Counter(
    "swe_agent_pr_severity_total",
    "Total PRs assessed by severity level",
    labelnames=["severity", "rule_source", "repository", "generated_skill_name"],
    registry=REGISTRY,
)


# Counter for executions completed
EXECUTIONS_COMPLETED_TOTAL = Counter(
    "swe_agent_plugin_executions_completed_total",
    "Total number of plugin executions completed",
    labelnames=["repository", "status", "plugin_name"],
    registry=REGISTRY,
)


# =============================================================================
# PR Auto-Approval Metrics
# =============================================================================

# Counter for auto-approval decisions
PR_AUTO_APPROVE_TOTAL = Counter(
    "swe_agent_pr_auto_approve_total",
    "Total PR auto-approval decisions by outcome",
    labelnames=["outcome", "rule_source", "repository", "repo_skill_name"],
    registry=REGISTRY,
)


# =============================================================================
# User Activity Metrics (Low Cardinality)
# =============================================================================

# Counter for user activity - only user + plugin_name labels for low cardinality
# Max cardinality: ~3000 users × 2 plugins = 6,000 time series
USER_ACTIVITY_TOTAL = Counter(
    "swe_agent_plugin_user_activity_total",
    "Total user activity events across all plugins (low cardinality)",
    labelnames=["user", "plugin_name"],
    registry=REGISTRY,
)


# =============================================================================
# Helper Functions
# =============================================================================

def record_mcp_calls(
    mcp_calls: List[Dict[str, Any]],
    repository: str,
    plugin_name: str = "swe-agent",
) -> None:
    """
    Record MCP tool usage metrics from a list of MCP calls.

    Accepts two dict formats:
      - Pre-parsed (from ``_parse_claude_output_from_file``):
        ``{"server": "blade-mcp", "tool": "get_component_docs", ...}``
      - Raw tool name (from external plugin API):
        ``{"tool_name": "mcp__blade-mcp__get_component_docs"}``

    Args:
        mcp_calls: List of MCP call dictionaries
        repository: Repository in "owner/repo" format
        plugin_name: Name of the plugin/source (default: "swe-agent" for PR reviews)
    """
    if not mcp_calls:
        return

    recorded = 0

    for call in mcp_calls:
        # Pre-parsed format: {"server": "...", "tool": "...", "tool_name": "..."}
        # Produced by ClaudeCodeTool._parse_claude_output_from_file()
        if call.get("server") and call.get("tool"):
            server_name = call["server"]
            actual_tool = call["tool"]
        else:
            # Raw format: {"tool_name": "mcp__server__tool"}
            # Produced by external plugin API submissions
            tool_name = call.get("tool_name", "")
            if not tool_name.startswith("mcp__"):
                continue
            parts = tool_name.split("__")
            if len(parts) < 3:
                continue
            server_name = parts[1]
            actual_tool = parts[2]

        # Record individual tool call
        MCP_TOOL_CALLS_TOTAL.labels(
            mcp_server=server_name,
            tool_name=actual_tool,
            repository=repository,
            plugin_name=plugin_name,
        ).inc()

        # Record server usage (aggregated)
        MCP_SERVER_USAGE_TOTAL.labels(
            mcp_server=server_name,
            repository=repository,
            plugin_name=plugin_name,
        ).inc()

        recorded += 1

    if recorded:
        logger.debug(f"Recorded {recorded} MCP metrics for repository={repository}, plugin={plugin_name}")


def record_skills_usage(
    skills_used: List[str],
    repository: str,
    plugin_name: str = "swe-agent",
) -> None:
    """
    Record skills usage metrics.

    Args:
        skills_used: List of skill names that were invoked
        repository: Repository in "owner/repo" format
        plugin_name: Name of the plugin/source (default: "swe-agent" for PR reviews)
    """
    if not skills_used:
        return

    for skill_name in skills_used:
        SKILLS_INVOCATIONS_TOTAL.labels(
            skill_name=skill_name,
            repository=repository,
            plugin_name=plugin_name,
        ).inc()

        logger.debug(
            f"Recorded skill metric: skill={skill_name}, "
            f"repository={repository}, plugin={plugin_name}"
        )


def record_user_activity(
    user: str,
    plugin_name: str,
) -> None:
    """
    Record user activity metrics (low cardinality).

    This metric intentionally only uses user + plugin_name labels
    to keep cardinality low (~6,000 max time series).

    Args:
        user: Username (e.g., "richesh.gupta")
        plugin_name: Name of the plugin (e.g., "code-review", "discover")
    """
    if not user:
        return

    USER_ACTIVITY_TOTAL.labels(
        user=user,
        plugin_name=plugin_name,
    ).inc()

    logger.debug(
        f"Recorded user activity: user={user}, plugin={plugin_name}"
    )


def record_execution_completion(
    repository: str,
    status: str,
    duration_seconds: Optional[float] = None,
    plugin_name: str = "swe-agent",
) -> None:
    """
    Record execution completion metrics.

    Args:
        repository: Repository in "owner/repo" format
        status: Execution status ('success', 'failed', 'partial')
        duration_seconds: Optional duration of the execution in seconds
        plugin_name: Name of the plugin/source (default: "swe-agent")
    """
    EXECUTIONS_COMPLETED_TOTAL.labels(
        repository=repository,
        status=status,
        plugin_name=plugin_name,
    ).inc()

    if duration_seconds is not None:
        EXECUTION_DURATION_SECONDS.labels(
            repository=repository,
            status=status,
            plugin_name=plugin_name,
        ).observe(duration_seconds)

    logger.debug(
        f"Recorded execution completion: repository={repository}, status={status}, "
        f"duration={duration_seconds}s, plugin={plugin_name}"
    )


# Backward compatibility alias
def record_review_completion(
    repository: str,
    status: str,
    duration_seconds: Optional[float] = None,
) -> None:
    """Deprecated: Use record_execution_completion instead."""
    record_execution_completion(repository, status, duration_seconds, "swe-agent")


def record_severity_assessment(
    severity: str,
    rule_source: str,
    repository: str,
    generated_skill_name: str = "",
) -> None:
    """
    Record PR severity assessment metric.

    Args:
        severity: Severity level ("low", "medium", "high")
        rule_source: Rule source ("repo_skill", "standard_rules", or "generated_context")
        repository: Repository in "owner/repo" format
        generated_skill_name: Name of the auto-generated skill (only set when
            rule_source is "generated_context", e.g. "risk-assessment")
    """
    PR_SEVERITY_TOTAL.labels(
        severity=severity,
        rule_source=rule_source,
        repository=repository,
        generated_skill_name=generated_skill_name,
    ).inc()

    logger.debug(
        "Recorded severity metric: severity=%s, rule_source=%s, "
        "repo=%s, generated_skill_name=%s",
        severity, rule_source, repository, generated_skill_name,
    )


def record_auto_approve_decision(
    outcome: str,
    rule_source: str,
    repository: str,
    repo_skill_name: Optional[str] = None,
) -> None:
    """
    Record a PR auto-approval decision.

    Args:
        outcome: Decision outcome. One of:
            - "approved": skill-driven auto-approve succeeded
            - "overridden": auto-approve blocked by critical suggestions
            - "config_approved": config-driven APPROVE (e.g. LOW severity, no suggestions)
            - "not_eligible": skill said auto_approve=false or no skill present
        rule_source: "repo_skill" or "standard_rules"
        repository: Repository in "owner/repo" format
        repo_skill_name: Name of the repo skill (e.g. "risk-assessment"), or None
    """
    PR_AUTO_APPROVE_TOTAL.labels(
        outcome=outcome,
        rule_source=rule_source,
        repository=repository,
        repo_skill_name=repo_skill_name or "none",
    ).inc()

    logger.debug(
        f"Recorded auto-approve decision: outcome={outcome}, "
        f"rule_source={rule_source}, repo={repository}, "
        f"skill={repo_skill_name}"
    )


def record_tool_usage(
    mcp_calls: Optional[List[Dict[str, Any]]],
    skills_used: Optional[List[str]],
    repository: str,
) -> None:
    """
    Convenience function to record both MCP and skills usage in one call.

    Args:
        mcp_calls: List of MCP call dictionaries
        skills_used: List of skill names
        repository: Repository in "owner/repo" format
    """
    if mcp_calls:
        record_mcp_calls(mcp_calls, repository)

    if skills_used:
        record_skills_usage(skills_used, repository)


# =============================================================================
# Initialization Function
# =============================================================================

def initialize_plugin_metrics() -> None:
    """
    Initialize plugin metrics for registration with Prometheus.

    This function ensures all plugin metrics are registered with the global
    Prometheus REGISTRY before the metrics server starts serving. The metrics
    are registered as module-level globals when this module is imported.

    Should be called during worker telemetry setup, similar to how the API
    service initializes HTTP metrics via initialize_http_metrics().

    This is effectively a no-op since metrics are already registered as module
    globals on import, but it provides:
    1. A clear trigger point to force the module import
    2. Logging to confirm initialization occurred
    3. Consistency with the existing HTTP metrics initialization pattern
    """
    logger.info(
        "Plugin metrics initialized and registered with Prometheus: "
        "MCP_TOOL_CALLS_TOTAL, MCP_SERVER_USAGE_TOTAL, SKILLS_INVOCATIONS_TOTAL, "
        "EXECUTION_DURATION_SECONDS, EXECUTIONS_COMPLETED_TOTAL, USER_ACTIVITY_TOTAL, "
        "PR_SEVERITY_TOTAL, PR_AUTO_APPROVE_TOTAL"
    )


# Backward compatibility alias
def initialize_review_metrics() -> None:
    """Deprecated: Use initialize_plugin_metrics instead."""
    initialize_plugin_metrics()
