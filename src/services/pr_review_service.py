"""
PR Review service for the SWE Agent.

Provides business logic for PR review operations.
"""

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple

from src.constants.pr_review import (
    ApiVersion,
    ReviewStatus,
    AckStatus,
    ErrorCode,
    REVIEW_ID_PREFIX,
    DEFAULT_API_VERSION,
    PR_REVIEW_TASK_TYPE,
)
from src.models.review import PRReview
from src.models.pr_review import (
    PRMetadata,
    PRReviewEnqueueRequest,
    PRReviewAckResponse,
    ReviewStatusResponse,
    TelemetryLite,
    PRReviewLinks,
    PRIdentity,
    ReviewTimestamps,
    Error,
)
from src.providers.database.session import get_session
from src.repositories.pr_review_repository import SQLAlchemyPRReviewRepository
from src.repositories.exceptions import EntityNotFoundError, RepositoryError
from src.worker.queue_manager import QueueManager
from .base import BaseService
from .exceptions import (
    TaskNotFoundError,
    ValidationError,
    BusinessLogicError,
)


def generate_ulid() -> str:
    """
    Generate a ULID-like identifier.

    Uses timestamp + random bytes to create a unique, sortable ID.
    Format: 26 characters (10 timestamp + 16 random) in Crockford's Base32
    """
    import secrets

    # Crockford's Base32 alphabet (excludes I, L, O, U to avoid confusion)
    ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

    # Get current timestamp in milliseconds
    timestamp_ms = int(time.time() * 1000)

    # Encode timestamp (10 characters)
    timestamp_chars = []
    for _ in range(10):
        timestamp_chars.append(ALPHABET[timestamp_ms & 31])
        timestamp_ms >>= 5
    timestamp_chars.reverse()

    # Generate random part (16 characters = 80 bits)
    random_bytes = secrets.token_bytes(10)
    random_int = int.from_bytes(random_bytes, "big")
    random_chars = []
    for _ in range(16):
        random_chars.append(ALPHABET[random_int & 31])
        random_int >>= 5
    random_chars.reverse()

    return "".join(timestamp_chars + random_chars)


class PRReviewService(BaseService):
    """PR Review service for managing code review jobs."""

    def __init__(self, config: Dict[str, Any], database_provider):
        """
        Initialize the PR review service.

        Args:
            config: Application configuration
            database_provider: Database provider instance
        """
        super().__init__("PRReviewService")
        self._db_provider = database_provider
        self._config = config
        self._queue_manager: Optional[QueueManager] = None
        self.initialize(config)

    def _configure(self, config: Dict[str, Any]) -> None:
        """Configure the service."""
        self._config = config
        # Get base URL for status links
        app_config = config.get("app", {})
        self._api_base_url = app_config.get("api_base_url", "http://localhost:28002")

    def _get_queue_manager(self) -> QueueManager:
        """Get or create queue manager instance."""
        if self._queue_manager is None:
            self._queue_manager = QueueManager()
        return self._queue_manager

    def _get_review_repo(self, session) -> SQLAlchemyPRReviewRepository:
        """Get the PR review repository with a given session."""
        return SQLAlchemyPRReviewRepository(session)

    def _generate_review_id(self) -> str:
        """Generate a unique review ID with prefix."""
        return f"{REVIEW_ID_PREFIX}{generate_ulid()}"

    def _generate_correlation_id(self) -> str:
        """Generate a correlation ID if not provided."""
        return str(uuid.uuid4())

    def _get_current_iso_timestamp(self) -> str:
        """Get current timestamp in ISO 8601 format."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _unix_to_iso(self, unix_timestamp: Optional[int]) -> Optional[str]:
        """Convert Unix timestamp to ISO 8601 format."""
        if unix_timestamp is None:
            return None
        return datetime.fromtimestamp(unix_timestamp, timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    def _build_status_url(self, review_id: str) -> str:
        """Build the status URL for a review."""
        return f"{self._api_base_url}/api/v1/pr-review/{review_id}"

    def enqueue_review(
        self, request: PRReviewEnqueueRequest
    ) -> Tuple[PRReviewAckResponse, int]:
        """
        Enqueue a PR for review.

        Args:
            request: PR review enqueue request

        Returns:
            Tuple of (acknowledgement response, HTTP status code)

        Raises:
            ValidationError: If request validation fails
            BusinessLogicError: If enqueueing fails
        """
        self._validate_initialized()

        # Generate correlation ID if not provided
        correlation_id = request.correlation_id or self._generate_correlation_id()
        current_timestamp = self._get_current_iso_timestamp()

        with get_session() as session:
            repo = self._get_review_repo(session)

            # Check for existing review by idempotency key
            if request.idempotency_key:
                existing_review = repo.get_by_idempotency_key(request.idempotency_key)
                if existing_review:
                    self.logger.info(
                        "Found existing review for idempotency key",
                        extra={
                            "idempotency_key": request.idempotency_key,
                            "review_id": existing_review.id,
                        },
                    )
                    # Return existing review with already_exists status
                    return (
                        PRReviewAckResponse(
                            api_version=DEFAULT_API_VERSION.value,
                            review_id=existing_review.id,
                            status=AckStatus.ALREADY_EXISTS,
                            telemetry=TelemetryLite(
                                correlation_id=correlation_id,
                                timestamp=current_timestamp,
                            ),
                            links=PRReviewLinks(
                                status_url=self._build_status_url(existing_review.id)
                            ),
                        ),
                        200,  # HTTP 200 for duplicate
                    )

            # Generate new review ID
            review_id = self._generate_review_id()

            # Create PR review record
            review = PRReview(
                id=review_id,
                idempotency_key=request.idempotency_key,
                status=ReviewStatus.ACCEPTED.value,
                pr_metadata=json.dumps(request.pr_metadata.model_dump()),
                pr_context=request.pr_context,
                correlation_id=correlation_id,
                enqueued_at=int(time.time()),
            )

            try:
                repo.create(review)
                session.commit()

                self.logger.info(
                    "Created PR review",
                    extra={
                        "review_id": review_id,
                        "repository": request.pr_metadata.repository,
                        "pr_number": request.pr_metadata.pr_number,
                    },
                )
            except Exception as e:
                session.rollback()
                self._log_error("create_review", e, review_id=review_id)
                raise BusinessLogicError(f"Failed to create review: {e}")

        # Queue the review task
        try:
            queue_success = self._queue_review_task(review_id, request, correlation_id)
            if queue_success:
                # Update status to queued
                with get_session() as session:
                    repo = self._get_review_repo(session)
                    repo.update_status(review_id, ReviewStatus.QUEUED)
                    session.commit()
        except Exception as e:
            self._log_error("queue_review_task", e, review_id=review_id)
            # Don't fail the request, the review is created
            self.logger.warning(
                "Failed to queue review task, review created but not queued",
                extra={"review_id": review_id, "error": str(e)},
            )

        return (
            PRReviewAckResponse(
                api_version=DEFAULT_API_VERSION.value,
                review_id=review_id,
                status=AckStatus.ACCEPTED,
                telemetry=TelemetryLite(
                    correlation_id=correlation_id,
                    timestamp=current_timestamp,
                ),
                links=PRReviewLinks(status_url=self._build_status_url(review_id)),
            ),
            202,  # HTTP 202 for new
        )

    def _queue_review_task(
        self, review_id: str, request: PRReviewEnqueueRequest, correlation_id: str
    ) -> bool:
        """
        Queue a review task for processing.

        Args:
            review_id: Review identifier
            request: Original enqueue request
            correlation_id: Correlation ID for tracing

        Returns:
            True if queued successfully
        """
        queue_manager = self._get_queue_manager()

        task_data = {
            "task_type": PR_REVIEW_TASK_TYPE,
            "review_id": review_id,
            "correlation_id": correlation_id,
            "pr_metadata": request.pr_metadata.model_dump(),
            "pr_context": request.pr_context,
            "created_at": int(time.time()),
        }

        # Let queue_manager determine queue from task_routing config
        success = queue_manager.send_task(task_data)

        if success:
            self.logger.info(
                "Queued review task",
                extra={
                    "review_id": review_id,
                    "task_type": PR_REVIEW_TASK_TYPE,
                },
            )
        else:
            self.logger.error(
                "Failed to queue review task",
                extra={
                    "review_id": review_id,
                    "task_type": PR_REVIEW_TASK_TYPE,
                },
            )

        return success

    def get_review_status(self, review_id: str) -> ReviewStatusResponse:
        """
        Get the status of a PR review.

        Args:
            review_id: Review identifier

        Returns:
            Review status response

        Raises:
            TaskNotFoundError: If review not found
        """
        self._validate_initialized()

        with get_session() as session:
            repo = self._get_review_repo(session)
            review = repo.get_by_id(review_id)

            if not review:
                raise TaskNotFoundError(f"Review not found: {review_id}")

            # Parse PR metadata
            pr_metadata = review.pr_metadata_dict

            # Build response
            response = ReviewStatusResponse(
                api_version=DEFAULT_API_VERSION.value,
                review_id=review.id,
                status=ReviewStatus(review.status),
                pr_identity=PRIdentity(
                    repository=pr_metadata.get("repository", ""),
                    pr_number=pr_metadata.get("pr_number", 0),
                ),
                telemetry=TelemetryLite(
                    correlation_id=review.correlation_id,
                    timestamp=self._get_current_iso_timestamp(),
                ),
                timestamps=ReviewTimestamps(
                    enqueued_at=self._unix_to_iso(review.enqueued_at),
                    started_at=self._unix_to_iso(review.started_at),
                    completed_at=self._unix_to_iso(review.completed_at),
                ),
            )

            # Add error info if failed
            if review.status == ReviewStatus.FAILED.value and review.error_info_dict:
                error_info = review.error_info_dict
                response.error = Error(
                    code=ErrorCode(error_info.get("code", ErrorCode.UPSTREAM_ERROR.value)),
                    message=error_info.get("message", "Unknown error"),
                )

            return response

    def update_review_status(
        self,
        review_id: str,
        status: ReviewStatus,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Update review status (called by worker).

        Args:
            review_id: Review identifier
            status: New status
            error_code: Error code (for failed status)
            error_message: Error message (for failed status)

        Raises:
            TaskNotFoundError: If review not found
        """
        self._validate_initialized()

        error_info = None
        if status == ReviewStatus.FAILED and error_code:
            error_info = {
                "code": error_code,
                "message": error_message or "Unknown error",
            }

        with get_session() as session:
            repo = self._get_review_repo(session)
            try:
                repo.update_status(review_id, status, error_info)
                session.commit()
                self.logger.info(
                    "Updated review status",
                    extra={"review_id": review_id, "status": status.value},
                )
            except EntityNotFoundError:
                raise TaskNotFoundError(f"Review not found: {review_id}")
            except Exception as e:
                session.rollback()
                self._log_error("update_review_status", e, review_id=review_id)
                raise BusinessLogicError(f"Failed to update review status: {e}")

    def health_check(self) -> Dict[str, Any]:
        """Perform health check on the service."""
        base_health = super().health_check()

        # Add additional checks if needed
        try:
            with get_session() as session:
                repo = self._get_review_repo(session)
                # Quick query to verify database connectivity
                repo.get_recent_reviews(limit=1)
                base_health["database"] = "healthy"
        except Exception as e:
            base_health["database"] = f"unhealthy: {str(e)}"
            base_health["status"] = "degraded"

        return base_health
