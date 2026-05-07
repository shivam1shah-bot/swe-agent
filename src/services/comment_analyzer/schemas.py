"""
Pydantic schemas for Comment Analyzer API requests.
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class CommentAnalyzerRequest(BaseModel):
    """Request to trigger comment analysis on a PR."""

    repository: str = Field(
        ...,
        pattern=r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$",
        description="Repository in owner/name format",
        examples=["razorpay/test-repo"],
    )
    pr_number: int = Field(
        ...,
        ge=1,
        description="PR number to analyze",
        examples=[123],
    )
    commit_sha: str = Field(
        ...,
        description="Commit SHA to create status on",
        examples=["abc123def456"],
    )
    sub_agent_identifier: str = Field(
        default="rcore-v2",
        description="Sub-agent identifier to filter comments by",
        examples=["rcore-v2"],
    )
    severity_threshold: int = Field(
        default=9,
        ge=1,
        le=10,
        description="Minimum severity threshold for filtering comments (1-10 scale)",
        examples=[9],
    )
    blocking_enabled: bool = Field(
        default=False,
        description="Whether to block PR on critical issues",
        examples=[False],
    )
    include_file_extensions: Optional[List[str]] = Field(
        None,
        description="File extensions to include (whitelist)",
        examples=[[".js", ".ts", ".py"]],
    )
    exclude_file_extensions: Optional[List[str]] = Field(
        None,
        description="File extensions to exclude (blacklist)",
        examples=[[".md", ".txt"]],
    )
    exclude_file_patterns: Optional[List[str]] = Field(
        None,
        description="Glob patterns to exclude",
        examples=[["**/test/**", "**/vendor/**"]],
    )
    run_url: Optional[str] = Field(
        None,
        description="URL to link from commit status",
        examples=["https://github.com/razorpay/test-repo/actions/runs/123"],
    )


class CommentAnalyzerResponse(BaseModel):
    """Response from triggering comment analysis."""

    success: bool = Field(..., description="Whether task was queued successfully")
    message: str = Field(..., description="Status message")
    task_id: Optional[str] = Field(None, description="Task ID for tracking")
