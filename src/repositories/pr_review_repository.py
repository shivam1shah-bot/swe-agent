"""
PR Review repository for the SWE Agent.

Provides data access operations for PRReview entities.
"""

import time
from abc import abstractmethod
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from .base import BaseRepository, SQLAlchemyBaseRepository
from .exceptions import EntityNotFoundError, QueryExecutionError, TransactionError
from src.models.review import PRReview
from src.constants.pr_review import ReviewStatus
from src.providers.logger import Logger


class PRReviewRepository(BaseRepository[PRReview]):
    """
    Abstract PR Review repository interface.

    Defines PR review-specific data access operations.
    """

    @abstractmethod
    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[PRReview]:
        """
        Get a review by its idempotency key.

        Args:
            idempotency_key: Idempotency key (format: repo_name:pr_number:run_id)

        Returns:
            PRReview instance or None if not found
        """
        pass

    @abstractmethod
    def get_by_status(
        self, status: ReviewStatus, limit: Optional[int] = None, offset: Optional[int] = None
    ) -> List[PRReview]:
        """
        Get reviews by status.

        Args:
            status: Review status
            limit: Maximum number of reviews to return
            offset: Number of reviews to skip

        Returns:
            List of reviews with the specified status
        """
        pass

    @abstractmethod
    def get_by_repository_and_pr(
        self, repository: str, pr_number: int, limit: Optional[int] = None
    ) -> List[PRReview]:
        """
        Get reviews by repository and PR number.

        Args:
            repository: Repository in owner/name format
            pr_number: PR number
            limit: Maximum number of reviews to return

        Returns:
            List of reviews for the specified PR
        """
        pass

    @abstractmethod
    def get_by_correlation_id(self, correlation_id: str) -> Optional[PRReview]:
        """
        Get a review by its correlation ID.

        Args:
            correlation_id: Correlation ID for request tracing

        Returns:
            PRReview instance or None if not found
        """
        pass

    @abstractmethod
    def update_status(
        self,
        review_id: str,
        status: ReviewStatus,
        error_info: Optional[Dict[str, Any]] = None,
    ) -> PRReview:
        """
        Update review status.

        Args:
            review_id: Review identifier
            status: New status
            error_info: Optional error information (for failed status)

        Returns:
            Updated review

        Raises:
            EntityNotFoundError: If review does not exist
        """
        pass

    @abstractmethod
    def get_recent_reviews(self, limit: int = 10) -> List[PRReview]:
        """
        Get recent reviews ordered by creation time.

        Args:
            limit: Maximum number of reviews to return

        Returns:
            List of recent reviews
        """
        pass

    @abstractmethod
    def atomic_claim_for_processing(
        self,
        review_id: str,
        allowed_from_statuses: List[ReviewStatus],
    ) -> bool:
        """
        Atomically claim a review for processing using UPDATE ... WHERE.

        This prevents TOCTOU race conditions by combining the check and update
        into a single atomic database operation. Only one worker can successfully
        claim a review even if multiple workers try simultaneously.

        Args:
            review_id: Review identifier to claim
            allowed_from_statuses: List of statuses that allow claiming
                (e.g., QUEUED, FAILED, ACCEPTED for retry scenarios)

        Returns:
            True if the review was successfully claimed (status updated to RUNNING)
            False if the review was already claimed or in a non-claimable status
        """
        pass


class SQLAlchemyPRReviewRepository(SQLAlchemyBaseRepository[PRReview], PRReviewRepository):
    """
    SQLAlchemy implementation of PRReviewRepository.

    Provides concrete data access operations using SQLAlchemy ORM.
    """

    def __init__(self, session: Session):
        """
        Initialize the PR review repository.

        Args:
            session: SQLAlchemy session
        """
        super().__init__(session, PRReview)
        self.logger = Logger("PRReviewRepository")

    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[PRReview]:
        """Get review by idempotency key using SQLAlchemy."""
        try:
            return (
                self.session.query(PRReview)
                .filter(PRReview.idempotency_key == idempotency_key)
                .first()
            )
        except SQLAlchemyError as e:
            self.logger.error(
                "Failed to get review by idempotency key",
                extra={"idempotency_key": idempotency_key, "error": str(e)},
            )
            raise QueryExecutionError(f"get_by_idempotency_key({idempotency_key})", str(e))

    def get_by_status(
        self, status: ReviewStatus, limit: Optional[int] = None, offset: Optional[int] = None
    ) -> List[PRReview]:
        """Get reviews by status using SQLAlchemy with pagination."""
        try:
            from sqlalchemy import desc

            query = self.session.query(PRReview).filter(PRReview.status == status.value)
            query = query.order_by(desc(PRReview.created_at))

            if offset:
                query = query.offset(offset)
            if limit:
                query = query.limit(limit)

            return query.all()
        except SQLAlchemyError as e:
            self.logger.error(
                "Failed to get reviews by status",
                extra={"status": status.value, "limit": limit, "offset": offset, "error": str(e)},
            )
            raise QueryExecutionError(f"get_by_status({status.value})", str(e))

    def get_by_repository_and_pr(
        self, repository: str, pr_number: int, limit: Optional[int] = None
    ) -> List[PRReview]:
        """Get reviews by repository and PR number using SQLAlchemy."""
        try:
            from sqlalchemy import desc

            # Query using JSON-like pattern matching
            # Note: This assumes MySQL's JSON functions or similar
            query = self.session.query(PRReview)
            # Filter by JSON fields in pr_metadata
            query = query.filter(
                PRReview.pr_metadata.like(f'%"repository": "{repository}"%'),
                PRReview.pr_metadata.like(f'%"pr_number": {pr_number}%'),
            )
            query = query.order_by(desc(PRReview.created_at))

            if limit:
                query = query.limit(limit)

            return query.all()
        except SQLAlchemyError as e:
            self.logger.error(
                "Failed to get reviews by repository and PR",
                extra={"repository": repository, "pr_number": pr_number, "error": str(e)},
            )
            raise QueryExecutionError(
                f"get_by_repository_and_pr({repository}, {pr_number})", str(e)
            )

    def get_by_correlation_id(self, correlation_id: str) -> Optional[PRReview]:
        """Get review by correlation ID using SQLAlchemy."""
        try:
            return (
                self.session.query(PRReview)
                .filter(PRReview.correlation_id == correlation_id)
                .first()
            )
        except SQLAlchemyError as e:
            self.logger.error(
                "Failed to get review by correlation ID",
                extra={"correlation_id": correlation_id, "error": str(e)},
            )
            raise QueryExecutionError(f"get_by_correlation_id({correlation_id})", str(e))

    def update_status(
        self,
        review_id: str,
        status: ReviewStatus,
        error_info: Optional[Dict[str, Any]] = None,
    ) -> PRReview:
        """Update review status using SQLAlchemy."""
        try:
            import json

            review = self.get_by_id(review_id)
            if not review:
                raise EntityNotFoundError("PRReview", review_id)

            review.status = status.value
            review.updated_at = int(time.time())

            # Update lifecycle timestamps based on status
            if status == ReviewStatus.QUEUED and not review.enqueued_at:
                review.enqueued_at = int(time.time())
            elif status == ReviewStatus.RUNNING and not review.started_at:
                review.started_at = int(time.time())
            elif status in (ReviewStatus.COMPLETED, ReviewStatus.FAILED):
                if not review.completed_at:
                    review.completed_at = int(time.time())
                if error_info:
                    review.error_info = json.dumps(error_info)

            self.session.flush()
            return review
        except EntityNotFoundError:
            raise
        except SQLAlchemyError as e:
            error_str = str(e).lower()
            if "lost connection" in error_str or "2013" in error_str:
                self.logger.error(
                    "Database connection lost while updating review status",
                    review_id=review_id,
                    error=str(e),
                    error_type="connection_timeout",
                )
            else:
                self.logger.error(
                    "Failed to update review status",
                    extra={"review_id": review_id, "status": status.value, "error": str(e)},
                )
            raise TransactionError(f"update_status({review_id})", str(e))

    def atomic_claim_for_processing(
        self,
        review_id: str,
        allowed_from_statuses: List[ReviewStatus],
    ) -> bool:
        """
        Atomically claim a review for processing using UPDATE ... WHERE.

        Uses a single UPDATE statement with WHERE clause to atomically check
        and update status, preventing TOCTOU race conditions.

        Args:
            review_id: Review identifier to claim
            allowed_from_statuses: List of statuses that allow claiming

        Returns:
            True if claimed successfully, False otherwise
        """
        try:
            from sqlalchemy import update

            current_time = int(time.time())
            allowed_values = [s.value for s in allowed_from_statuses]

            # Single atomic UPDATE with WHERE clause
            # Only updates if status is in allowed list - prevents race condition
            result = self.session.execute(
                update(PRReview)
                .where(PRReview.id == review_id)
                .where(PRReview.status.in_(allowed_values))
                .values(
                    status=ReviewStatus.RUNNING.value,
                    started_at=current_time,
                    updated_at=current_time,
                )
            )

            self.session.commit()

            claimed = result.rowcount > 0

            if claimed:
                self.logger.info(
                    f"Atomically claimed review {review_id} for processing",
                    extra={"review_id": review_id, "from_statuses": allowed_values},
                )
            else:
                self.logger.info(
                    f"Review {review_id} not claimed - already processing or completed",
                    extra={"review_id": review_id, "allowed_statuses": allowed_values},
                )

            return claimed

        except SQLAlchemyError as e:
            self.logger.error(
                "Failed to atomically claim review",
                extra={"review_id": review_id, "error": str(e)},
            )
            raise TransactionError(f"atomic_claim_for_processing({review_id})", str(e))

    def get_recent_reviews(self, limit: int = 10) -> List[PRReview]:
        """Get recent reviews using SQLAlchemy."""
        try:
            return (
                self.session.query(PRReview)
                .order_by(PRReview.created_at.desc())
                .limit(limit)
                .all()
            )
        except SQLAlchemyError as e:
            self.logger.error(
                "Failed to get recent reviews", extra={"limit": limit, "error": str(e)}
            )
            raise QueryExecutionError(f"get_recent_reviews(limit={limit})", str(e))

    def get_by_id(self, review_id: str) -> Optional[PRReview]:
        """Override to add error handling and connection timeout detection."""
        try:
            return super().get_by_id(review_id)
        except SQLAlchemyError as e:
            error_str = str(e).lower()
            if "lost connection" in error_str or "2013" in error_str:
                self.logger.error(
                    "Database connection lost while getting review by ID",
                    review_id=review_id,
                    error=str(e),
                    error_type="connection_timeout",
                )
            else:
                self.logger.error(
                    "Failed to get review by ID", review_id=review_id, error=str(e)
                )
            raise QueryExecutionError(f"get_by_id({review_id})", str(e))

    def create(self, review: PRReview) -> PRReview:
        """Override to add error handling and validation."""
        try:
            # Set timestamps if not set
            current_time = int(time.time())
            if not review.created_at:
                review.created_at = current_time
            if not review.updated_at:
                review.updated_at = current_time

            return super().create(review)
        except SQLAlchemyError as e:
            self.logger.error("Failed to create review", extra={"error": str(e)})
            raise TransactionError("create_review", str(e))

    def get_all(
        self, limit: Optional[int] = None, offset: Optional[int] = None
    ) -> List[PRReview]:
        """Get all reviews with proper ordering: running/queued first, then by created_at DESC."""
        try:
            from sqlalchemy import case, desc

            # Create ordering: running/queued reviews first, then by created_at DESC
            status_priority = case(
                (PRReview.status == ReviewStatus.RUNNING.value, 1),
                (PRReview.status == ReviewStatus.QUEUED.value, 2),
                (PRReview.status == ReviewStatus.ACCEPTED.value, 3),
                else_=4,
            )

            query = self.session.query(PRReview).order_by(
                status_priority, desc(PRReview.created_at)
            )

            if offset:
                query = query.offset(offset)
            if limit:
                query = query.limit(limit)

            return query.all()
        except SQLAlchemyError as e:
            self.logger.error(
                "Failed to get all reviews with ordering",
                extra={"limit": limit, "offset": offset, "error": str(e)},
            )
            raise QueryExecutionError(f"get_all(limit={limit}, offset={offset})", str(e))
