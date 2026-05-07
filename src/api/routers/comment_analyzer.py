"""
Comment Analyzer router for FastAPI.

Provides endpoint to trigger comment analysis on GitHub PRs.
"""

from fastapi import APIRouter, HTTPException, status, Depends, Request, Response
from typing import Dict, Any

from src.services.comment_analyzer.schemas import CommentAnalyzerRequest, CommentAnalyzerResponse
from src.providers.logger import Logger
from src.providers.auth import require_role
from src.worker.queue_manager import QueueManager

router = APIRouter()
logger = Logger("CommentAnalyzerRouter")


@router.post(
    "/analyze",
    response_model=CommentAnalyzerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@require_role(["dashboard", "admin"])
async def trigger_comment_analysis(
    request: Request,
    response: Response,
    analysis_request: CommentAnalyzerRequest
):
    """
    Trigger comment analysis on a GitHub PR.

    This endpoint queues a background task to analyze PR comments
    from AI sub-agents and post commit status / review comments to GitHub.

    No database storage - results posted directly to GitHub.
    """
    try:
        logger.info(
            f"Triggering comment analysis for {analysis_request.repository}#{analysis_request.pr_number}",
            extra={
                "repository": analysis_request.repository,
                "pr_number": analysis_request.pr_number,
                "commit_sha": analysis_request.commit_sha,
                "sub_agent_identifier": analysis_request.sub_agent_identifier,
            }
        )

        # Queue the task
        queue_manager = QueueManager()

        task_data = {
            "task_type": "comment_analysis",
            "repository": analysis_request.repository,
            "pr_number": analysis_request.pr_number,
            "commit_sha": analysis_request.commit_sha,
            "sub_agent_identifier": analysis_request.sub_agent_identifier,
            "severity_threshold": analysis_request.severity_threshold,
            "blocking_enabled": analysis_request.blocking_enabled,
            "include_file_extensions": analysis_request.include_file_extensions or [],
            "exclude_file_extensions": analysis_request.exclude_file_extensions or [],
            "exclude_file_patterns": analysis_request.exclude_file_patterns or [],
            "run_url": analysis_request.run_url or "",
        }

        success = queue_manager.send_task(task_data)

        if not success:
            logger.error("Failed to queue comment analysis task")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to queue analysis task"
            )

        logger.info(
            f"Comment analysis queued for {analysis_request.repository}#{analysis_request.pr_number}",
            extra={"task_data": task_data}
        )

        return CommentAnalyzerResponse(
            success=True,
            message=f"Analysis queued for {analysis_request.repository}#{analysis_request.pr_number}",
            task_id=None  # No task tracking since no database
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error triggering comment analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )
