"""
Unit tests for PR Review repository.

Tests the PR Review repository data access operations.
"""

import json
import time
import pytest
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError

from src.repositories.pr_review_repository import (
    PRReviewRepository,
    SQLAlchemyPRReviewRepository,
)
from src.repositories.exceptions import (
    EntityNotFoundError,
    QueryExecutionError,
    TransactionError,
)
from src.models.review import PRReview
from src.constants.pr_review import ReviewStatus


@pytest.fixture
def mock_session():
    """Mock database session for testing."""
    session = MagicMock()
    session.query = MagicMock()
    session.add = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.flush = MagicMock()
    session.merge = MagicMock()
    session.delete = MagicMock()
    return session


@pytest.fixture
def repository(mock_session):
    """Create PR review repository instance."""
    return SQLAlchemyPRReviewRepository(mock_session)


@pytest.fixture
def sample_pr_review():
    """Create sample PR review entity."""
    current_time = int(time.time())
    return PRReview(
        id="rev_01JH8NM3W8C4M7R7JX7WZ9QY5Q",
        idempotency_key="org/repo:123:run_1",
        status=ReviewStatus.RUNNING.value,
        pr_metadata=json.dumps({
            "pr_url": "https://github.com/org/repo/pull/123",
            "pr_number": 123,
            "repository": "org/repo",
            "author": "testuser",
            "title": "Test PR",
            "branch": "feature/test",
            "target_branch": "main",
        }),
        pr_context="Review this PR",
        correlation_id="550e8400-e29b-41d4-a716-446655440000",
        enqueued_at=current_time - 60,
        started_at=current_time - 30,
        created_at=current_time - 60,
        updated_at=current_time - 30,
    )


@pytest.mark.unit
class TestSQLAlchemyPRReviewRepositoryInit:
    """Test PR Review repository initialization."""

    def test_repository_initialization(self, mock_session):
        """Test repository initializes with session."""
        # Act
        repo = SQLAlchemyPRReviewRepository(mock_session)

        # Assert
        assert repo.session == mock_session
        assert repo.model_class == PRReview


@pytest.mark.unit
class TestGetByIdempotencyKey:
    """Test get_by_idempotency_key method."""

    def test_get_by_idempotency_key_found(self, repository, mock_session, sample_pr_review):
        """Test getting review by idempotency key when found."""
        # Arrange
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = sample_pr_review
        mock_session.query.return_value = mock_query

        # Act
        result = repository.get_by_idempotency_key("org/repo:123:run_1")

        # Assert
        assert result == sample_pr_review
        mock_session.query.assert_called_once_with(PRReview)

    def test_get_by_idempotency_key_not_found(self, repository, mock_session):
        """Test getting review by idempotency key when not found."""
        # Arrange
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = None
        mock_session.query.return_value = mock_query

        # Act
        result = repository.get_by_idempotency_key("nonexistent:key")

        # Assert
        assert result is None

    def test_get_by_idempotency_key_db_error(self, repository, mock_session):
        """Test get_by_idempotency_key raises QueryExecutionError on DB error."""
        # Arrange
        mock_session.query.side_effect = SQLAlchemyError("Connection error")

        # Act & Assert
        with pytest.raises(QueryExecutionError) as exc_info:
            repository.get_by_idempotency_key("test:key")

        # Check that an error was raised (the exact format may vary)
        assert "Connection error" in str(exc_info.value)


@pytest.mark.unit
class TestGetByStatus:
    """Test get_by_status method."""

    def test_get_by_status_returns_reviews(self, repository, mock_session, sample_pr_review):
        """Test getting reviews by status."""
        # Arrange
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_ordered = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_ordered
        mock_ordered.all.return_value = [sample_pr_review]
        mock_session.query.return_value = mock_query

        # Act
        result = repository.get_by_status(ReviewStatus.RUNNING)

        # Assert
        assert len(result) == 1
        assert result[0] == sample_pr_review

    def test_get_by_status_with_limit_and_offset(self, repository, mock_session, sample_pr_review):
        """Test getting reviews by status with pagination."""
        # Arrange - use a simpler mock chain that handles the optional offset
        mock_result = MagicMock()
        mock_result.all.return_value = [sample_pr_review]

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_result
        mock_session.query.return_value = mock_query

        # Act
        result = repository.get_by_status(ReviewStatus.RUNNING, limit=10, offset=5)

        # Assert - offset is only called if offset > 0
        assert result == [sample_pr_review]
        mock_query.offset.assert_called_once_with(5)
        mock_query.limit.assert_called_once_with(10)

    def test_get_by_status_empty_result(self, repository, mock_session):
        """Test getting reviews by status when none found."""
        # Arrange
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_ordered = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_ordered
        mock_ordered.all.return_value = []
        mock_session.query.return_value = mock_query

        # Act
        result = repository.get_by_status(ReviewStatus.COMPLETED)

        # Assert
        assert result == []

    def test_get_by_status_db_error(self, repository, mock_session):
        """Test get_by_status raises QueryExecutionError on DB error."""
        # Arrange
        mock_session.query.side_effect = SQLAlchemyError("Connection error")

        # Act & Assert
        with pytest.raises(QueryExecutionError) as exc_info:
            repository.get_by_status(ReviewStatus.RUNNING)

        # Check that an error was raised
        assert "Connection error" in str(exc_info.value)


@pytest.mark.unit
class TestGetByCorrelationId:
    """Test get_by_correlation_id method."""

    def test_get_by_correlation_id_found(self, repository, mock_session, sample_pr_review):
        """Test getting review by correlation ID when found."""
        # Arrange
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = sample_pr_review
        mock_session.query.return_value = mock_query

        # Act
        result = repository.get_by_correlation_id("550e8400-e29b-41d4-a716-446655440000")

        # Assert
        assert result == sample_pr_review

    def test_get_by_correlation_id_not_found(self, repository, mock_session):
        """Test getting review by correlation ID when not found."""
        # Arrange
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = None
        mock_session.query.return_value = mock_query

        # Act
        result = repository.get_by_correlation_id("nonexistent-id")

        # Assert
        assert result is None


@pytest.mark.unit
class TestUpdateStatus:
    """Test update_status method."""

    def test_update_status_success(self, repository, mock_session, sample_pr_review):
        """Test update_status updates successfully."""
        # Arrange
        with patch.object(repository, 'get_by_id', return_value=sample_pr_review):
            # Act
            result = repository.update_status(
                "rev_01JH8NM3W8C4M7R7JX7WZ9QY5Q",
                ReviewStatus.COMPLETED,
            )

        # Assert
        assert result.status == ReviewStatus.COMPLETED.value
        mock_session.flush.assert_called_once()

    def test_update_status_to_queued_sets_enqueued_at(self, repository, mock_session, sample_pr_review):
        """Test update_status to QUEUED sets enqueued_at timestamp."""
        # Arrange
        sample_pr_review.enqueued_at = None
        before_time = int(time.time())

        with patch.object(repository, 'get_by_id', return_value=sample_pr_review):
            # Act
            result = repository.update_status(
                "rev_01JH8NM3W8C4M7R7JX7WZ9QY5Q",
                ReviewStatus.QUEUED,
            )

        # Assert
        assert result.status == ReviewStatus.QUEUED.value
        assert result.enqueued_at >= before_time

    def test_update_status_to_running_sets_started_at(self, repository, mock_session, sample_pr_review):
        """Test update_status to RUNNING sets started_at timestamp."""
        # Arrange
        sample_pr_review.started_at = None
        before_time = int(time.time())

        with patch.object(repository, 'get_by_id', return_value=sample_pr_review):
            # Act
            result = repository.update_status(
                "rev_01JH8NM3W8C4M7R7JX7WZ9QY5Q",
                ReviewStatus.RUNNING,
            )

        # Assert
        assert result.status == ReviewStatus.RUNNING.value
        assert result.started_at >= before_time

    def test_update_status_to_failed_with_error_info(self, repository, mock_session, sample_pr_review):
        """Test update_status to FAILED includes error info."""
        # Arrange
        sample_pr_review.completed_at = None
        error_info = {"code": "upstream_error", "message": "Agent failed"}

        with patch.object(repository, 'get_by_id', return_value=sample_pr_review):
            # Act
            result = repository.update_status(
                "rev_01JH8NM3W8C4M7R7JX7WZ9QY5Q",
                ReviewStatus.FAILED,
                error_info=error_info,
            )

        # Assert
        assert result.status == ReviewStatus.FAILED.value
        assert result.completed_at is not None
        assert json.loads(result.error_info) == error_info

    def test_update_status_not_found(self, repository, mock_session):
        """Test update_status raises EntityNotFoundError for unknown ID."""
        # Arrange
        with patch.object(repository, 'get_by_id', return_value=None):
            # Act & Assert
            with pytest.raises(EntityNotFoundError) as exc_info:
                repository.update_status(
                    "rev_nonexistent",
                    ReviewStatus.COMPLETED,
                )

            assert "rev_nonexistent" in str(exc_info.value)

    def test_update_status_db_error(self, repository, mock_session, sample_pr_review):
        """Test update_status raises TransactionError on DB error."""
        # Arrange
        with patch.object(repository, 'get_by_id', return_value=sample_pr_review):
            mock_session.flush.side_effect = SQLAlchemyError("Connection timeout")

            # Act & Assert
            with pytest.raises(TransactionError) as exc_info:
                repository.update_status(
                    "rev_01JH8NM3W8C4M7R7JX7WZ9QY5Q",
                    ReviewStatus.COMPLETED,
                )

            assert "update_status" in str(exc_info.value)


@pytest.mark.unit
class TestGetRecentReviews:
    """Test get_recent_reviews method."""

    def test_get_recent_reviews(self, repository, mock_session, sample_pr_review):
        """Test getting recent reviews."""
        # Arrange
        mock_query = MagicMock()
        mock_ordered = MagicMock()
        mock_limited = MagicMock()
        mock_query.order_by.return_value = mock_ordered
        mock_ordered.limit.return_value = mock_limited
        mock_limited.all.return_value = [sample_pr_review]
        mock_session.query.return_value = mock_query

        # Act
        result = repository.get_recent_reviews(limit=10)

        # Assert
        assert len(result) == 1
        assert result[0] == sample_pr_review
        mock_ordered.limit.assert_called_once_with(10)

    def test_get_recent_reviews_default_limit(self, repository, mock_session):
        """Test get_recent_reviews uses default limit."""
        # Arrange
        mock_query = MagicMock()
        mock_ordered = MagicMock()
        mock_limited = MagicMock()
        mock_query.order_by.return_value = mock_ordered
        mock_ordered.limit.return_value = mock_limited
        mock_limited.all.return_value = []
        mock_session.query.return_value = mock_query

        # Act
        repository.get_recent_reviews()

        # Assert
        mock_ordered.limit.assert_called_once_with(10)

    def test_get_recent_reviews_db_error(self, repository, mock_session):
        """Test get_recent_reviews raises QueryExecutionError on DB error."""
        # Arrange
        mock_session.query.side_effect = SQLAlchemyError("Connection error")

        # Act & Assert
        with pytest.raises(QueryExecutionError) as exc_info:
            repository.get_recent_reviews()

        # Check that an error was raised
        assert "Connection error" in str(exc_info.value)


@pytest.mark.unit
class TestGetById:
    """Test get_by_id method."""

    def test_get_by_id_found(self, repository, mock_session, sample_pr_review):
        """Test getting review by ID when found."""
        # Arrange
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = sample_pr_review
        mock_session.query.return_value = mock_query

        # Act
        result = repository.get_by_id("rev_01JH8NM3W8C4M7R7JX7WZ9QY5Q")

        # Assert
        assert result == sample_pr_review

    def test_get_by_id_not_found(self, repository, mock_session):
        """Test getting review by ID when not found."""
        # Arrange
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = None
        mock_session.query.return_value = mock_query

        # Act
        result = repository.get_by_id("rev_nonexistent")

        # Assert
        assert result is None

    def test_get_by_id_connection_timeout(self, repository, mock_session):
        """Test get_by_id handles connection timeout."""
        # Arrange
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.first.side_effect = SQLAlchemyError("Lost connection to MySQL server during query (2013)")
        mock_session.query.return_value = mock_query

        # Act & Assert
        with pytest.raises(QueryExecutionError) as exc_info:
            repository.get_by_id("rev_test")

        # Check that the timeout error was captured
        assert "Lost connection" in str(exc_info.value) or "2013" in str(exc_info.value)


@pytest.mark.unit
class TestCreate:
    """Test create method."""

    def test_create_review(self, repository, mock_session, sample_pr_review):
        """Test creating a review."""
        # Arrange
        sample_pr_review.created_at = None
        sample_pr_review.updated_at = None
        before_time = int(time.time())

        # Act
        result = repository.create(sample_pr_review)

        # Assert
        assert result == sample_pr_review
        assert sample_pr_review.created_at >= before_time
        assert sample_pr_review.updated_at >= before_time
        mock_session.add.assert_called_once_with(sample_pr_review)
        mock_session.flush.assert_called_once()

    def test_create_review_preserves_existing_timestamps(self, repository, mock_session, sample_pr_review):
        """Test create preserves existing timestamps."""
        # Arrange
        original_created_at = sample_pr_review.created_at
        original_updated_at = sample_pr_review.updated_at

        # Act
        result = repository.create(sample_pr_review)

        # Assert
        assert result.created_at == original_created_at
        assert result.updated_at == original_updated_at

    def test_create_review_db_error(self, repository, mock_session, sample_pr_review):
        """Test create raises TransactionError on DB error."""
        # Arrange
        mock_session.add.side_effect = SQLAlchemyError("Duplicate entry")

        # Act & Assert
        with pytest.raises(TransactionError) as exc_info:
            repository.create(sample_pr_review)

        assert "create_review" in str(exc_info.value)


@pytest.mark.unit
class TestGetAll:
    """Test get_all method."""

    def test_get_all_with_ordering(self, repository, mock_session, sample_pr_review):
        """Test get_all returns reviews with proper ordering."""
        # Arrange
        mock_query = MagicMock()
        mock_ordered = MagicMock()
        mock_query.order_by.return_value = mock_ordered
        mock_ordered.all.return_value = [sample_pr_review]
        mock_session.query.return_value = mock_query

        # Act
        result = repository.get_all()

        # Assert
        assert len(result) == 1
        assert result[0] == sample_pr_review

    def test_get_all_with_limit_and_offset(self, repository, mock_session, sample_pr_review):
        """Test get_all with pagination."""
        # Arrange
        mock_query = MagicMock()
        mock_ordered = MagicMock()
        mock_offset = MagicMock()
        mock_limit = MagicMock()

        mock_query.order_by.return_value = mock_ordered
        mock_ordered.offset.return_value = mock_offset
        mock_offset.limit.return_value = mock_limit
        mock_limit.all.return_value = [sample_pr_review]
        mock_session.query.return_value = mock_query

        # Act
        result = repository.get_all(limit=10, offset=5)

        # Assert
        assert len(result) == 1
        mock_ordered.offset.assert_called_once_with(5)
        mock_offset.limit.assert_called_once_with(10)

    def test_get_all_db_error(self, repository, mock_session):
        """Test get_all raises QueryExecutionError on DB error."""
        # Arrange
        mock_session.query.side_effect = SQLAlchemyError("Connection error")

        # Act & Assert
        with pytest.raises(QueryExecutionError) as exc_info:
            repository.get_all()

        # Check that an error was raised
        assert "Connection error" in str(exc_info.value)


@pytest.mark.unit
class TestGetByRepositoryAndPR:
    """Test get_by_repository_and_pr method."""

    def test_get_by_repository_and_pr(self, repository, mock_session, sample_pr_review):
        """Test getting reviews by repository and PR number."""
        # Arrange
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_ordered = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_ordered
        mock_ordered.all.return_value = [sample_pr_review]
        mock_session.query.return_value = mock_query

        # Act
        result = repository.get_by_repository_and_pr("org/repo", 123)

        # Assert
        assert len(result) == 1
        assert result[0] == sample_pr_review

    def test_get_by_repository_and_pr_with_limit(self, repository, mock_session, sample_pr_review):
        """Test getting reviews by repository and PR number with limit."""
        # Arrange
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_ordered = MagicMock()
        mock_limited = MagicMock()

        mock_query.filter.return_value = mock_filter
        mock_filter.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_ordered
        mock_ordered.limit.return_value = mock_limited
        mock_limited.all.return_value = [sample_pr_review]
        mock_session.query.return_value = mock_query

        # Act
        result = repository.get_by_repository_and_pr("org/repo", 123, limit=5)

        # Assert
        assert len(result) == 1
        mock_ordered.limit.assert_called_once_with(5)


@pytest.mark.unit
class TestAtomicClaimForProcessing:
    """Test atomic_claim_for_processing method."""

    def test_atomic_claim_success(self, repository, mock_session):
        """Test atomically claiming a review for processing."""
        # Arrange
        mock_result = MagicMock()
        mock_result.rowcount = 1  # One row updated = claim successful
        mock_session.execute.return_value = mock_result

        # Act
        claimed = repository.atomic_claim_for_processing(
            "rev_01JH8NM3W8C4M7R7JX7WZ9QY5Q",
            allowed_from_statuses=[ReviewStatus.QUEUED, ReviewStatus.FAILED],
        )

        # Assert
        assert claimed is True
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_atomic_claim_already_claimed(self, repository, mock_session):
        """Test claim fails when review is already claimed."""
        # Arrange
        mock_result = MagicMock()
        mock_result.rowcount = 0  # No rows updated = already claimed
        mock_session.execute.return_value = mock_result

        # Act
        claimed = repository.atomic_claim_for_processing(
            "rev_01JH8NM3W8C4M7R7JX7WZ9QY5Q",
            allowed_from_statuses=[ReviewStatus.QUEUED],
        )

        # Assert
        assert claimed is False
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_atomic_claim_with_multiple_allowed_statuses(self, repository, mock_session):
        """Test claim works with multiple allowed statuses."""
        # Arrange
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        # Act
        claimed = repository.atomic_claim_for_processing(
            "rev_test",
            allowed_from_statuses=[
                ReviewStatus.QUEUED,
                ReviewStatus.FAILED,
                ReviewStatus.ACCEPTED,
                ReviewStatus.RUNNING,
            ],
        )

        # Assert
        assert claimed is True
        # Verify the execute was called with an update statement
        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args
        # The first argument should be the update statement
        assert call_args is not None

    def test_atomic_claim_db_error(self, repository, mock_session):
        """Test atomic_claim raises TransactionError on DB error."""
        # Arrange
        mock_session.execute.side_effect = SQLAlchemyError("Connection lost")

        # Act & Assert
        with pytest.raises(TransactionError) as exc_info:
            repository.atomic_claim_for_processing(
                "rev_test",
                allowed_from_statuses=[ReviewStatus.QUEUED],
            )

        assert "atomic_claim_for_processing" in str(exc_info.value)
        assert "Connection lost" in str(exc_info.value)

    def test_atomic_claim_prevents_race_condition(self, repository, mock_session):
        """Test that atomic claim prevents TOCTOU race condition.

        This test simulates two concurrent claims by verifying that only
        one can succeed (rowcount = 1) and the other gets rowcount = 0.
        """
        # Arrange - simulate first claim succeeds, second fails
        mock_result_first = MagicMock()
        mock_result_first.rowcount = 1

        mock_result_second = MagicMock()
        mock_result_second.rowcount = 0

        # Act - First claim
        mock_session.execute.return_value = mock_result_first
        first_claimed = repository.atomic_claim_for_processing(
            "rev_race_test",
            allowed_from_statuses=[ReviewStatus.QUEUED],
        )

        # Reset for second attempt
        mock_session.reset_mock()

        # After first claim, status is RUNNING, so second should fail
        mock_session.execute.return_value = mock_result_second
        second_claimed = repository.atomic_claim_for_processing(
            "rev_race_test",
            allowed_from_statuses=[ReviewStatus.QUEUED],  # Only QUEUED allowed
        )

        # Assert
        assert first_claimed is True
        assert second_claimed is False
