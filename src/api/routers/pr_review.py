"""
PR Review router for FastAPI.

This module provides REST API endpoints for PR review operations.
"""

import logging
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, status, Depends, Request, Response, Header
from pydantic import ValidationError as PydanticValidationError

from src.constants.pr_review import (
    ApiVersion,
    ErrorCode,
    DEFAULT_API_VERSION,
)
from src.models.pr_review import (
    PRReviewEnqueueRequest,
    PRReviewAckResponse,
    ReviewStatusResponse,
    ErrorResponse,
    Error,
    FieldError,
    TelemetryLite,
)
from src.providers.auth import require_role
from src.providers.logger import Logger
from src.services.pr_review_service import PRReviewService
from src.services.exceptions import TaskNotFoundError, ValidationError, BusinessLogicError

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


def get_pr_review_service(request: Request) -> PRReviewService:
    """Dependency to get the PR review service instance."""
    try:
        return request.app.state.pr_review_service
    except AttributeError as e:
        logger.error(f"Failed to get PR review service from app state: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PR review service not available",
        )


def get_correlation_id(
    x_correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
) -> Optional[str]:
    """Get correlation ID from headers."""
    return x_correlation_id or x_request_id


def get_current_timestamp() -> str:
    """Get current ISO 8601 timestamp."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_error_response(
    error_code: ErrorCode,
    message: str,
    correlation_id: Optional[str] = None,
    field_errors: list = None,
    retry_after_s: int = None,
) -> ErrorResponse:
    """Build a standardized error response."""
    import uuid

    return ErrorResponse(
        api_version=DEFAULT_API_VERSION.value,
        error=Error(
            code=error_code,
            message=message,
            field_errors=field_errors,
            retry_after_s=retry_after_s,
        ),
        telemetry=TelemetryLite(
            correlation_id=correlation_id or str(uuid.uuid4()),
            timestamp=get_current_timestamp(),
        ),
    )


@router.post(
    "",
    response_model=PRReviewAckResponse,
    responses={
        200: {
            "model": PRReviewAckResponse,
            "description": "Deduplicated; an equivalent active/recent review already exists",
        },
        202: {
            "model": PRReviewAckResponse,
            "description": "Enqueued successfully (new review)",
        },
        400: {
            "model": ErrorResponse,
            "description": "Invalid request (validation error)",
        },
        401: {
            "model": ErrorResponse,
            "description": "Unauthorized (invalid or missing API key)",
        },
        429: {
            "model": ErrorResponse,
            "description": "Rate limit exceeded",
        },
        500: {
            "model": ErrorResponse,
            "description": "Internal server error",
        },
        503: {
            "model": ErrorResponse,
            "description": "Service unavailable (Claude Code agent not available)",
        },
    },
)
@require_role(["dashboard", "admin"])
async def enqueue_pr_review(
    request: Request,
    response: Response,
    review_request: PRReviewEnqueueRequest,
    pr_review_service: PRReviewService = Depends(get_pr_review_service),
    correlation_id: Optional[str] = Depends(get_correlation_id),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """
    Enqueue PR for review (acknowledgement only).

    Enqueue an AI-powered code review job using Claude Code.

    The service will:
    - Build prompts internally by importing AI PR Reviewer templates
    - Analyze the PR and post comments directly to GitHub
    - Return an acknowledgement with a review_id for status polling

    Idempotency:
    - Provide `idempotency_key` in the request body or `Idempotency-Key` header
    - Format: `repo_name:pr_number:run_id`
    - Example: `razorpay/ai-pr-reviewer:125:1731508800000`
    """
    log = Logger("PRReviewRouter")

    try:
        # Use header idempotency key if not in body
        if idempotency_key and not review_request.idempotency_key:
            review_request.idempotency_key = idempotency_key

        # Use header correlation ID if not in body
        if correlation_id and not review_request.correlation_id:
            review_request.correlation_id = correlation_id

        # Enqueue the review
        ack_response, http_status = pr_review_service.enqueue_review(review_request)

        # Set HTTP status code
        response.status_code = http_status

        # Set Location header
        if ack_response.links and ack_response.links.status_url:
            response.headers["Location"] = ack_response.links.status_url

        log.info(
            "PR review enqueued",
            extra={
                "review_id": ack_response.review_id,
                "status": ack_response.status.value,
                "http_status": http_status,
                "repository": review_request.pr_metadata.repository,
                "pr_number": review_request.pr_metadata.pr_number,
            },
        )

        return ack_response

    except ValidationError as e:
        log.warning(f"Validation error in enqueue_pr_review: {e}")
        error_response = build_error_response(
            ErrorCode.VALIDATION_ERROR,
            str(e),
            correlation_id=correlation_id,
            field_errors=[FieldError(field=e.field, message=e.message)] if hasattr(e, "field") else None,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response.model_dump(),
        )

    except BusinessLogicError as e:
        log.error(f"Business logic error in enqueue_pr_review: {e}")
        error_response = build_error_response(
            ErrorCode.UPSTREAM_ERROR,
            str(e),
            correlation_id=correlation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response.model_dump(),
        )

    except Exception as e:
        log.exception(f"Unhandled error in enqueue_pr_review: {e}")
        error_response = build_error_response(
            ErrorCode.UPSTREAM_ERROR,
            "Internal server error",
            correlation_id=correlation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response.model_dump(),
        )


@router.get(
    "/{review_id}",
    response_model=ReviewStatusResponse,
    responses={
        200: {
            "model": ReviewStatusResponse,
            "description": "Status retrieved successfully",
        },
        401: {
            "model": ErrorResponse,
            "description": "Unauthorized (invalid or missing API key)",
        },
        404: {
            "model": ErrorResponse,
            "description": "Review not found",
        },
        500: {
            "model": ErrorResponse,
            "description": "Internal server error",
        },
    },
)
@require_role(["dashboard", "admin"])
async def get_pr_review_status(
    request: Request,
    review_id: str,
    pr_review_service: PRReviewService = Depends(get_pr_review_service),
    correlation_id: Optional[str] = Depends(get_correlation_id),
):
    """
    Get PR review status (status-only).

    Retrieve the status of an enqueued review job.
    No progress percentage or suggestion payloads are returned.
    """
    log = Logger("PRReviewRouter")

    try:
        status_response = pr_review_service.get_review_status(review_id)

        log.info(
            "PR review status retrieved",
            extra={
                "review_id": review_id,
                "status": status_response.status.value,
            },
        )

        return status_response

    except TaskNotFoundError as e:
        log.warning(f"Review not found: {review_id}")
        error_response = build_error_response(
            ErrorCode.NOT_FOUND,
            "review_id not found",
            correlation_id=correlation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response.model_dump(),
        )

    except Exception as e:
        log.exception(f"Unhandled error in get_pr_review_status: {e}")
        error_response = build_error_response(
            ErrorCode.UPSTREAM_ERROR,
            "Internal server error",
            correlation_id=correlation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response.model_dump(),
        )
