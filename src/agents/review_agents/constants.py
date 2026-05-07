"""
Constants for PR Review agents.

Provides enums, thresholds, and category mappings for the
PR Review Main Agent system.
"""

from enum import Enum
from typing import Dict, List


class SubAgentCategory(str, Enum):
    """Categories for review sub-agents."""
    # Core Categories (Phase 1)
    BUG = "bug"
    SECURITY = "security"
    CODE_QUALITY = "code_quality"

    # Extended Categories (Future Phases)
    PERFORMANCE = "performance"
    STYLE = "style"
    DEVOPS = "devops"
    TESTING = "testing"
    I18N = "i18n"  # Internationalization
    BLADE = "blade"  # Blade Design System (frontend only)
    SVELTE = "svelte"  # Svelte/TypeScript (frontend only)
    PRE_MORTEM = "pre_mortem"  # Pre-mortem analysis for reliability/quality


class ReviewAgentType(str, Enum):
    """Types of top-level review agents."""
    PR_DESCRIPTION = "pr_description"
    REVIEW_ANALYSIS = "review_analysis"


class Severity(str, Enum):
    """Severity levels for suggestions."""
    CRITICAL = "critical"    # importance >= 8
    IMPORTANT = "important"  # importance >= 5
    MINOR = "minor"          # importance >= 3
    NIT = "nit"              # importance < 3


class PRSeverity(str, Enum):
    """PR-level severity classification."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# Default actions for each severity level (overridable via config)
# LOW severity PRs with no actionable suggestions are auto-approved.
# The safety guard in ReviewMainAgent downgrades APPROVE → COMMENT if suggestions exist.
# LOW severity PRs with no actionable suggestions are auto-approved.
# The safety guard in ReviewMainAgent downgrades APPROVE → COMMENT if suggestions exist.
# MEDIUM and HIGH use COMMENT — blocking PRs is too aggressive for the initial rollout.
DEFAULT_SEVERITY_ACTIONS: Dict[str, str] = {
    PRSeverity.LOW.value: "approve",
    PRSeverity.MEDIUM.value: "comment",
    PRSeverity.HIGH.value: "comment",
}

# Maps config action string to GitHub review event
ACTION_TO_REVIEW_EVENT: Dict[str, str] = {
    "comment": "COMMENT",
    "approve": "APPROVE",
    "request_changes": "REQUEST_CHANGES",
    "none": "COMMENT",
}

# Bot marker for idempotent severity comments
SEVERITY_BOT_MARKER = "<!-- pr-severity-bot -->"

# Minimum suggestion importance that overrides auto-approve from repo skill.
# Even if the skill says auto_approve: true, suggestions at this importance
# or above will force a downgrade to COMMENT. Acts as a platform-level safety net.
DEFAULT_APPROVE_BLOCK_THRESHOLD: int = 8  # CRITICAL only

# Review mode: controls whether the bot can approve/request_changes or only comment.
# "full"         = bot can post APPROVE, REQUEST_CHANGES, or COMMENT
# "comment_only" = all review events are clamped to COMMENT
REVIEW_MODE_FULL = "full"
REVIEW_MODE_COMMENT_ONLY = "comment_only"
VALID_REVIEW_MODES = {REVIEW_MODE_FULL, REVIEW_MODE_COMMENT_ONLY}
DEFAULT_REVIEW_MODE = REVIEW_MODE_FULL


# Default thresholds for filtering
DEFAULT_CONFIDENCE_THRESHOLD: float = 0.6
DEFAULT_IMPORTANCE_THRESHOLD: int = 5
DEFAULT_NIT_THRESHOLD: int = 3  # Below this is considered a "nit"

# Core categories for Phase 1 implementation
CORE_CATEGORIES: List[str] = [
    SubAgentCategory.BUG.value,
    SubAgentCategory.SECURITY.value,
    SubAgentCategory.CODE_QUALITY.value,
    SubAgentCategory.STYLE.value,
    SubAgentCategory.I18N.value,
    SubAgentCategory.BLADE.value,
    SubAgentCategory.SVELTE.value,
    SubAgentCategory.PRE_MORTEM.value,
]

# All available categories (for future expansion)
ALL_CATEGORIES: List[str] = [cat.value for cat in SubAgentCategory]

# pr-prompt-kit category mappings
CATEGORY_TO_PROMPT_KIT: Dict[str, str] = {
    SubAgentCategory.BUG.value: "bug",
    SubAgentCategory.SECURITY.value: "security",
    SubAgentCategory.CODE_QUALITY.value: "code_quality",
    SubAgentCategory.PERFORMANCE.value: "performance",
    SubAgentCategory.STYLE.value: None,  # Uses render_suggestions with languages, not render_subagent
    SubAgentCategory.DEVOPS.value: "code_quality",  # Future: dedicated prompt
    SubAgentCategory.TESTING.value: "testing",
    SubAgentCategory.I18N.value: None,  # Uses pr_review_prompt_i18n, custom render
    SubAgentCategory.BLADE.value: "blade",  # Uses blade_design_system_prompt from pr-prompt-kit
    SubAgentCategory.SVELTE.value: "svelte",  # Uses svelte_prompt from pr-prompt-kit
    SubAgentCategory.PRE_MORTEM.value: None,  # Uses custom skill-based prompt rendering
}

# Category labels for GitHub comments
CATEGORY_LABELS: Dict[str, str] = {
    SubAgentCategory.BUG.value: "BUG",
    SubAgentCategory.SECURITY.value: "SECURITY",
    SubAgentCategory.CODE_QUALITY.value: "CODE_QUALITY",
    SubAgentCategory.PERFORMANCE.value: "PERFORMANCE",
    SubAgentCategory.STYLE.value: "STYLE",
    SubAgentCategory.DEVOPS.value: "DEVOPS",
    SubAgentCategory.TESTING.value: "TESTING",
    SubAgentCategory.I18N.value: "I18N",
    SubAgentCategory.BLADE.value: "BLADE",
    SubAgentCategory.SVELTE.value: "SVELTE",
    SubAgentCategory.PRE_MORTEM.value: "PRE_MORTEM",
}


def get_severity(importance: int) -> Severity:
    """Get severity level based on importance score."""
    if importance >= 8:
        return Severity.CRITICAL
    elif importance >= 5:
        return Severity.IMPORTANT
    elif importance >= 3:
        return Severity.MINOR
    else:
        return Severity.NIT


# Error handling constants
DIFF_TOO_LARGE_MESSAGE = """## PR Too Large for Automated Review

This PR's diff exceeds GitHub's **20,000 line limit** and cannot be reviewed automatically.

**Recommendation:** Please split this PR into smaller, more focused changes:
- Separate refactoring from feature changes
- Break large features into incremental PRs
- Move generated/vendored files to separate PRs

Smaller PRs are easier to review and less likely to introduce bugs."""


# Skills required for the code review pipeline.
# source: where the skill normally comes from
#   - "generated"     → repo-specific, auto-generated via LLM if missing
#   - "agent-skills"  → generic, installed from razorpay/agent-skills via agentfill
#   - "review-helpers" → copied from swe-agent's .claude/skills/review-helpers/
REQUIRED_REVIEW_SKILLS: Dict[str, Dict[str, str]] = {
    "risk-assessment": {
        "source": "generated",
        "description": "Repo-specific risk tiers and critical path maps for severity assessment",
    },
    "code-review": {
        "source": "agent-skills",
        "description": "Domain context and conventions for sub-agents and filter layer",
    },
    "pre-mortem": {
        "source": "agent-skills",
        "description": "Pre-mortem checklist references for reliability analysis",
    },
    "i18n-anomaly-detection": {
        "source": "review-helpers",
        "description": "Internationalization anomaly detection rules",
    },
}
