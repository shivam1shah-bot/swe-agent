"""
Review Identifiers and Filters

This module defines identifiers for different types of automated reviews
posted by bots on GitHub PRs, and provides utilities to distinguish between them.
"""

from enum import Enum
from typing import Dict, Optional


class ReviewType(Enum):
    """Types of automated reviews posted by bots"""

    # AI Code Review - Main PR review with inline code suggestions
    AI_CODE_REVIEW = "ai_code_review"

    # Comment Analysis Summary - Summary of comment analysis results
    COMMENT_ANALYSIS_SUMMARY = "comment_analysis_summary"

    # PR Too Large - Message when PR diff exceeds limits
    PR_TOO_LARGE = "pr_too_large"

    # Unknown - Other bot reviews
    UNKNOWN = "unknown"


# Identifiers for each review type
REVIEW_IDENTIFIERS: Dict[ReviewType, Dict[str, str]] = {
    ReviewType.AI_CODE_REVIEW: {
        "header": "## AI Code Review",
        "description": "Main automated PR review with inline code suggestions",
        "posted_as": "review",
        "format": "## AI Code Review\n\nFound **{count}** inline suggestion(s).",
    },
    ReviewType.COMMENT_ANALYSIS_SUMMARY: {
        "header": "## 📊 Comment Analysis Summary",
        "description": "Summary of comment analysis results",
        "posted_as": "issue_comment",
        "format": "## 📊 Comment Analysis Summary - {sub_agent_type}\n\n**Analysis Status:** {status}",
    },
    ReviewType.PR_TOO_LARGE: {
        "header": "## PR Too Large for Automated Review",
        "description": "Message posted when PR diff exceeds GitHub's limits",
        "posted_as": "review",
        "format": "## PR Too Large for Automated Review\n\nThis PR's diff exceeds...",
    },
}


def identify_review_type(review_body: str) -> ReviewType:
    """
    Identify the type of automated review based on its body content.

    Args:
        review_body: The body text of the review

    Returns:
        ReviewType enum indicating the type of review

    Examples:
        >>> identify_review_type("## AI Code Review\\n\\nFound 5 inline suggestions")
        ReviewType.AI_CODE_REVIEW

        >>> identify_review_type("## 📊 Comment Analysis Summary - I18N")
        ReviewType.COMMENT_ANALYSIS_SUMMARY

        >>> identify_review_type("## PR Too Large for Automated Review")
        ReviewType.PR_TOO_LARGE
    """
    if not review_body:
        return ReviewType.UNKNOWN

    # Check for each known review type by header
    for review_type, identifiers in REVIEW_IDENTIFIERS.items():
        if identifiers["header"] in review_body:
            return review_type

    return ReviewType.UNKNOWN


def is_ai_code_review(review_body: str) -> bool:
    """
    Check if a review is an AI Code Review.

    Args:
        review_body: The body text of the review

    Returns:
        True if it's an AI Code Review, False otherwise

    Examples:
        >>> is_ai_code_review("## AI Code Review\\n\\nNo issues found")
        True

        >>> is_ai_code_review("## 📊 Comment Analysis Summary - I18N")
        False
    """
    return identify_review_type(review_body) == ReviewType.AI_CODE_REVIEW


def is_comment_analysis_summary(review_body: str) -> bool:
    """
    Check if a comment is a Comment Analysis Summary.

    Args:
        review_body: The body text of the comment

    Returns:
        True if it's a Comment Analysis Summary, False otherwise

    Examples:
        >>> is_comment_analysis_summary("## 📊 Comment Analysis Summary - I18N")
        True

        >>> is_comment_analysis_summary("## AI Code Review\\n\\nFound 5 issues")
        False
    """
    return identify_review_type(review_body) == ReviewType.COMMENT_ANALYSIS_SUMMARY


def get_review_type_description(review_type: ReviewType) -> str:
    """
    Get a human-readable description of a review type.

    Args:
        review_type: The ReviewType enum

    Returns:
        Description string

    Examples:
        >>> get_review_type_description(ReviewType.AI_CODE_REVIEW)
        'Main automated PR review with inline code suggestions'
    """
    if review_type in REVIEW_IDENTIFIERS:
        return REVIEW_IDENTIFIERS[review_type]["description"]
    return "Unknown review type"


def filter_ai_code_reviews(reviews: list) -> list:
    """
    Filter a list of reviews to only include AI Code Reviews.

    Args:
        reviews: List of review dictionaries from GitHub API

    Returns:
        Filtered list containing only AI Code Reviews

    Examples:
        >>> reviews = [
        ...     {"body": "## AI Code Review\\n\\nFound 3 issues", "id": 1},
        ...     {"body": "## 📊 Comment Analysis Summary - I18N", "id": 2},
        ...     {"body": "## PR Too Large for Automated Review", "id": 3},
        ... ]
        >>> filtered = filter_ai_code_reviews(reviews)
        >>> len(filtered)
        1
        >>> filtered[0]["id"]
        1
    """
    return [
        review
        for review in reviews
        if is_ai_code_review(review.get("body", ""))
    ]


def get_review_metadata(review_body: str) -> Dict[str, str]:
    """
    Extract metadata about a review based on its type.

    Args:
        review_body: The body text of the review

    Returns:
        Dictionary containing metadata about the review

    Examples:
        >>> metadata = get_review_metadata("## AI Code Review\\n\\nFound 5 suggestions")
        >>> metadata["type"]
        'ai_code_review'
        >>> metadata["header"]
        '## AI Code Review'
    """
    review_type = identify_review_type(review_body)

    metadata = {
        "type": review_type.value,
        "type_enum": review_type,
        "description": get_review_type_description(review_type),
    }

    if review_type in REVIEW_IDENTIFIERS:
        metadata.update({
            "header": REVIEW_IDENTIFIERS[review_type]["header"],
            "posted_as": REVIEW_IDENTIFIERS[review_type]["posted_as"],
        })

    return metadata


# Constants for backwards compatibility
AI_CODE_REVIEW_HEADER = REVIEW_IDENTIFIERS[ReviewType.AI_CODE_REVIEW]["header"]
COMMENT_ANALYSIS_HEADER = REVIEW_IDENTIFIERS[ReviewType.COMMENT_ANALYSIS_SUMMARY]["header"]
PR_TOO_LARGE_HEADER = REVIEW_IDENTIFIERS[ReviewType.PR_TOO_LARGE]["header"]
