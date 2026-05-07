"""
Data models for PR Review agents.

Provides dataclasses for suggestions, results, and review outcomes
used throughout the PR Review Main Agent system.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


@dataclass
class Suggestion:
    """A single review suggestion from a sub-agent."""
    file: str
    line: int
    category: str
    importance: int
    confidence: float
    description: str
    suggestion_code: Optional[str] = None
    existing_code: Optional[str] = None
    line_end: Optional[int] = None
    comment_type: Literal["inline", "general"] = "inline"
    source_subagent: Optional[str] = None
    source_skill: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert suggestion to dictionary format."""
        return {
            "file": self.file,
            "line": self.line,
            "line_end": self.line_end,
            "category": self.category,
            "importance": self.importance,
            "confidence": self.confidence,
            "description": self.description,
            "suggestion_code": self.suggestion_code,
            "existing_code": self.existing_code,
            "comment_type": self.comment_type,
            "source_subagent": self.source_subagent,
            "source_skill": self.source_skill,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Suggestion":
        """Create a Suggestion from a dictionary."""
        return cls(
            file=data.get("file", ""),
            line=data.get("line", 1),
            line_end=data.get("line_end"),
            category=data.get("category", "GENERAL"),
            importance=data.get("importance", 5),
            confidence=data.get("confidence", 1.0),
            description=data.get("description", ""),
            suggestion_code=data.get("suggestion_code"),
            existing_code=data.get("existing_code"),
            comment_type=data.get("comment_type", "inline"),
            source_subagent=data.get("source_subagent"),
            source_skill=data.get("source_skill"),
        )


@dataclass
class SubAgentResult:
    """Result from a single sub-agent execution."""
    category: str
    suggestions: List[Dict[str, Any]]
    success: bool
    error: Optional[str] = None
    execution_time_ms: int = 0
    skipped: bool = False
    skip_reason: Optional[str] = None
    mcp_calls: List[Dict[str, Any]] = field(default_factory=list)
    skills_used: List[str] = field(default_factory=list)
    summary_data: Optional[Dict[str, Any]] = None  # Subagent-specific summary metadata (e.g., pre-mortem analysis)

    @property
    def suggestion_count(self) -> int:
        """Return number of suggestions."""
        return len(self.suggestions)

    @property
    def was_skipped(self) -> bool:
        """Check if the sub-agent was skipped."""
        return self.skipped

    @property
    def has_tool_usage(self) -> bool:
        """Check if any MCP tools or skills were used."""
        return bool(self.mcp_calls) or bool(self.skills_used)


@dataclass
class SeverityAssessment:
    """Result of PR-level severity assessment."""
    severity: str                                       # "low", "medium", "high"
    confidence: float                                   # 0.0 - 1.0
    rule_source: str                                    # "repo_skill" or "standard_rules"
    reasoning: str                                      # LLM explanation of why
    category_breakdown: Dict[str, Dict[str, Any]]       # {category: {count, max_importance}}
    repo_skill_name: Optional[str] = None               # e.g. "code-review" if repo skill used
    auto_approve: bool = False                          # True only when repo skill explicitly approves
    auto_approve_raw: bool = False                      # LLM's raw verdict before guard (tracks auto-gen intent)
    error: Optional[str] = None

    @property
    def has_error(self) -> bool:
        """Check if an error occurred."""
        return self.error is not None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "severity": self.severity,
            "confidence": self.confidence,
            "rule_source": self.rule_source,
            "reasoning": self.reasoning,
            "category_breakdown": self.category_breakdown,
            "repo_skill_name": self.repo_skill_name,
            "auto_approve": self.auto_approve,
            "auto_approve_raw": self.auto_approve_raw,
            "error": self.error,
        }

    @classmethod
    def default_low(cls) -> "SeverityAssessment":
        """Default LOW assessment when there are no suggestions."""
        return cls(
            severity="low",
            confidence=1.0,
            rule_source="standard_rules",
            reasoning="No suggestions found after filtering. PR has no detected issues.",
            category_breakdown={},
        )


@dataclass
class ReviewResult:
    """Result of a complete PR review."""
    suggestions: List[Suggestion] = field(default_factory=list)
    description_posted: bool = False
    review_posted: bool = False
    review_id: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    severity_assessment: Optional[SeverityAssessment] = None

    @property
    def total_suggestions(self) -> int:
        """Return total number of suggestions."""
        return len(self.suggestions)

    @property
    def has_errors(self) -> bool:
        """Check if any errors occurred during review."""
        return len(self.errors) > 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert review result to dictionary format."""
        return {
            "total_suggestions": self.total_suggestions,
            "description_posted": self.description_posted,
            "review_posted": self.review_posted,
            "review_id": self.review_id,
            "errors": self.errors if self.has_errors else None,
            "suggestions_by_category": self._group_by_category(),
            "severity_assessment": (
                self.severity_assessment.to_dict()
                if self.severity_assessment else None
            ),
        }

    def _group_by_category(self) -> Dict[str, int]:
        """Group suggestion counts by category."""
        counts: Dict[str, int] = {}
        for suggestion in self.suggestions:
            cat = suggestion.category
            counts[cat] = counts.get(cat, 0) + 1
        return counts

    def add_suggestion(self, suggestion: Suggestion) -> None:
        """Add a suggestion to the review result."""
        self.suggestions.append(suggestion)

    def add_error(self, error: str) -> None:
        """Add an error message to the review result."""
        self.errors.append(error)


@dataclass
class PRDescriptionResult:
    """Result from PR Description Generator."""
    title: Optional[str] = None
    summary: Optional[str] = None
    changes: List[str] = field(default_factory=list)
    pr_type: Optional[str] = None
    full_description: Optional[str] = None  # Complete formatted description from LLM
    posted: bool = False
    error: Optional[str] = None

    @property
    def has_error(self) -> bool:
        """Check if an error occurred."""
        return self.error is not None

    def to_dict(self) -> Dict[str, Any]:
        """Convert PR description result to dictionary format."""
        return {
            "title": self.title,
            "summary": self.summary,
            "changes": self.changes,
            "pr_type": self.pr_type,
            "full_description": self.full_description,
            "posted": self.posted,
            "error": self.error,
        }


@dataclass
class PublishResult:
    """Result of publishing suggestions to GitHub."""
    success: bool
    review_id: Optional[int] = None
    comments_posted: int = 0
    comments_skipped: int = 0
    error: Optional[str] = None

    @property
    def has_error(self) -> bool:
        """Check if an error occurred."""
        return self.error is not None

    def to_dict(self) -> Dict[str, Any]:
        """Convert publish result to dictionary format."""
        return {
            "success": self.success,
            "review_id": self.review_id,
            "comments_posted": self.comments_posted,
            "comments_skipped": self.comments_skipped,
            "error": self.error,
        }
