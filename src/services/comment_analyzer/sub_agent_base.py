"""
Base classes for sub-agent implementations.

This module provides abstract base classes that each sub-agent must implement
to handle comment extraction, filtering, analysis, and action determination.
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SeverityLevel(Enum):
    """Severity levels as per tech spec"""
    CRITICAL = "critical"  # 9-10
    HIGH = "high"          # 7-8
    MEDIUM = "medium"      # 4-6
    LOW = "low"            # 1-3


@dataclass
class Comment:
    """Represents a GitHub PR comment with full GitHub metadata"""
    id: int
    body: str
    author: str
    file_path: Optional[str]
    line: Optional[int]
    severity: int = 5
    category: str = "other"
    excluded: bool = False
    # GitHub metadata for context analysis
    original_commit_id: Optional[str] = None
    commit_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    position: Optional[int] = None
    # Authorization feedback from authorized team members
    has_authorized_feedback: bool = False
    feedback_type: Optional[str] = None  # "TP" (True Positive) or "FP" (False Positive)
    feedback_author: Optional[str] = None
    feedback_details: Optional[str] = None


@dataclass
class AnalysisResult:
    """Result of comment analysis"""
    comment: Comment
    addressed: bool
    confidence: str
    reasoning: str
    severity_level: SeverityLevel


@dataclass
class SubAgentResult:
    """Results from a sub-agent analysis"""
    sub_agent_name: str
    status: str  # PASS or FAIL
    total_comments: int
    addressed: int
    not_addressed: int
    unaddressed_by_severity: Dict[str, int]
    critical_issues: List[Comment]
    addressed_comments: List[Comment]
    actions_executed: List[Dict[str, Any]]


class SubAgentBase(ABC):
    """
    Abstract base class for all sub-agents.

    Sub-agents define their own workflow by implementing the execute() method.
    Helper methods are provided for common tasks but are optional.
    """

    def __init__(self, config: Dict[str, Any], github_token: str, repository: str, pr_number: int):
        """
        Initialize the sub-agent.

        Args:
            config: Sub-agent specific configuration
            github_token: GitHub authentication token
            repository: Repository in owner/repo format
            pr_number: PR number
        """
        self.config = config
        self.name = config.get("name", "unknown")
        self.identifier = config.get("identifier", "unknown")
        self.github_token = github_token
        self.repository = repository
        self.pr_number = pr_number
        self.severity_threshold = config.get("severity_threshold", 9)
        self.thresholds = config.get("thresholds", {"fail_on_critical_count": 1})

    @abstractmethod
    def execute(self, all_reviews: List[Dict[str, Any]]) -> SubAgentResult:
        """
        Execute the sub-agent's workflow and return results.

        Sub-agents implement their own workflow by composing helper methods
        or implementing custom logic. This provides maximum flexibility for
        different analysis strategies.

        Args:
            all_reviews: All reviews from the PR

        Returns:
            SubAgentResult with analysis results and actions
        """
        pass

    # =========================================================================
    # Helper Methods (Optional - use as needed in your workflow)
    # =========================================================================

    def determine_actions(self, results: List[AnalysisResult]) -> SubAgentResult:
        """
        Helper: Determine actions based on thresholds.

        Default implementation for determining pass/fail status based on
        unaddressed critical issues. Sub-agents can override for custom logic.

        Args:
            results: List of analysis results

        Returns:
            SubAgentResult with status and actions
        """
        logger.info(f"\n[{self.name}] Determining actions based on {len(results)} analysis results")

        # Count by severity
        unaddressed_by_severity = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0
        }

        critical_issues = []
        addressed_comments = []
        addressed_count = 0
        not_addressed_count = 0

        logger.info(f"\nCounting results by status and severity...")
        for i, result in enumerate(results):
            if result.addressed:
                addressed_count += 1
                addressed_comments.append(result.comment)
                status_icon = "✓"
            else:
                not_addressed_count += 1
                severity_level = result.severity_level.value
                unaddressed_by_severity[severity_level] += 1
                status_icon = "✗"

                if severity_level == "critical":
                    critical_issues.append(result.comment)

            logger.info(f"  {status_icon} Comment #{i+1}: {result.comment.file_path}:{result.comment.line}")
            logger.info(f"    Addressed: {result.addressed}, Severity: {result.severity_level.value}, Confidence: {result.confidence}")

        # Determine status based on thresholds
        fail_on_critical = self.thresholds.get("fail_on_critical_count", 1)

        logger.info(f"\nSummary:")
        logger.info(f"Addressed: {addressed_count}")
        logger.info(f"Not Addressed: {not_addressed_count}")
        logger.info(f"  - Critical: {unaddressed_by_severity['critical']}")
        logger.info(f"  - High: {unaddressed_by_severity['high']}")
        logger.info(f"  - Medium: {unaddressed_by_severity['medium']}")
        logger.info(f"  - Low: {unaddressed_by_severity['low']}")

        status = "FAIL" if unaddressed_by_severity["critical"] >= fail_on_critical else "PASS"

        logger.info(f"\nDecision:")
        logger.info(f"Threshold: Fail if critical count >= {fail_on_critical}")
        logger.info(f"Critical count: {unaddressed_by_severity['critical']}")
        logger.info(f"Status: {status}")

        if status == "FAIL" and critical_issues:
            logger.info(f"\nCritical issues blocking this PR:")
            for issue in critical_issues:
                logger.info(f"  - {issue.file_path}:{issue.line}")
                logger.info(f"    {issue.body[:100]}...")

        logger.info(f"\n[{self.name}] Actions determined: Status = {status}")
        logger.info(f"  - Addressed comments (will be marked resolved): {len(addressed_comments)}")

        return SubAgentResult(
            sub_agent_name=self.name,
            status=status,
            total_comments=len(results),
            addressed=addressed_count,
            not_addressed=not_addressed_count,
            unaddressed_by_severity=unaddressed_by_severity,
            critical_issues=critical_issues,
            addressed_comments=addressed_comments,
            actions_executed=[]
        )
