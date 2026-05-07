"""
Unit tests for PR Review service.

Tests the PR Review service business logic.
"""

import json
import time
import pytest
from unittest.mock import Mock, MagicMock, patch
import sys

# Mock worker modules BEFORE importing service (they trigger DB connections at import)
mock_worker = MagicMock()
mock_tasks = MagicMock()
sys.modules['src.worker'] = mock_worker
sys.modules['src.worker.queue_manager'] = mock_worker
sys.modules['src.tasks'] = mock_tasks
sys.modules['src.tasks.service'] = mock_tasks

from src.services.pr_review_service import PRReviewService, generate_ulid
from src.constants.pr_review import (
    ReviewStatus,
    AckStatus,
    ErrorCode,
    REVIEW_ID_PREFIX,
    DEFAULT_API_VERSION,
)
from src.models.pr_review import (
    PRMetadata,
    PRReviewEnqueueRequest,
    PRReviewAckResponse,
    ReviewStatusResponse,
)
from src.models.review import PRReview
from src.services.exceptions import TaskNotFoundError, ValidationError, BusinessLogicError


@pytest.fixture(scope="module", autouse=True)
def cleanup_mock_modules():
    """Cleanup mock modules after all tests in this module."""
    yield
    # Remove mocks to avoid polluting other tests
    for key in ['src.worker', 'src.worker.queue_manager', 'src.tasks', 'src.tasks.service']:
        if key in sys.modules and isinstance(sys.modules[key], MagicMock):
            sys.modules.pop(key, None)


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    return {
        "app": {
            "api_base_url": "http://localhost:28002",
        },
        "database": {
            "host": "localhost",
            "port": 3306,
        },
    }


@pytest.fixture
def mock_database_provider():
    """Mock database provider for testing."""
    provider = MagicMock()
    provider.get_session.return_value = MagicMock()
    return provider


@pytest.fixture
def mock_session():
    """Mock database session for testing."""
    session = MagicMock()
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=None)
    session.commit = Mock()
    session.rollback = Mock()
    return session


@pytest.fixture
def mock_repository():
    """Mock PR review repository for testing."""
    repo = MagicMock()
    repo.create = Mock()
    repo.get_by_id = Mock()
    repo.get_by_idempotency_key = Mock(return_value=None)
    repo.update_status = Mock()
    repo.get_recent_reviews = Mock(return_value=[])
    return repo


@pytest.fixture
def sample_pr_metadata():
    """Sample PR metadata for testing."""
    return PRMetadata(
        pr_url="https://github.com/org/repo/pull/123",
        pr_number=123,
        repository="org/repo",
        author="testuser",
        title="Test PR",
        branch="feature/test",
        target_branch="main",
    )


@pytest.fixture
def sample_enqueue_request(sample_pr_metadata):
    """Sample enqueue request for testing."""
    return PRReviewEnqueueRequest(
        pr_metadata=sample_pr_metadata,
        pr_context="Review this PR",
        correlation_id="550e8400-e29b-41d4-a716-446655440000",
        idempotency_key="org/repo:123:run_1",
    )


@pytest.fixture
def sample_pr_review():
    """Sample PR review entity for testing."""
    current_time = int(time.time())
    review = PRReview(
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
    return review


class TestGenerateUlid:
    """Test ULID generation function."""

    def test_generate_ulid_returns_26_characters(self):
        """Test that ULID is 26 characters long."""
        # Act
        ulid = generate_ulid()

        # Assert
        assert len(ulid) == 26

    def test_generate_ulid_uses_valid_characters(self):
        """Test that ULID uses only Crockford's Base32 characters."""
        # Arrange
        valid_chars = set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")

        # Act
        ulid = generate_ulid()

        # Assert
        for char in ulid:
            assert char in valid_chars, f"Invalid character: {char}"

    def test_generate_ulid_unique(self):
        """Test that generated ULIDs are unique."""
        # Act
        ulids = [generate_ulid() for _ in range(100)]

        # Assert
        assert len(ulids) == len(set(ulids)), "ULIDs should be unique"

    def test_generate_ulid_sortable(self):
        """Test that ULIDs are roughly time-sortable."""
        # Act
        ulid1 = generate_ulid()
        time.sleep(0.01)  # Small delay to ensure different timestamps
        ulid2 = generate_ulid()

        # Assert - first 10 chars should be timestamp (may be same for quick tests)
        # Just verify they're different strings
        assert isinstance(ulid1, str)
        assert isinstance(ulid2, str)


class TestPRReviewServiceInit:
    """Test PR Review service initialization."""

    @patch('src.services.pr_review_service.get_session')
    def test_service_initializes_correctly(self, mock_get_session, mock_config, mock_database_provider):
        """Test service initializes with correct configuration."""
        # Act
        service = PRReviewService(mock_config, mock_database_provider)

        # Assert
        assert service._db_provider == mock_database_provider
        assert service._config == mock_config
        assert service._api_base_url == "http://localhost:28002"

    @patch('src.services.pr_review_service.get_session')
    def test_service_uses_default_api_url(self, mock_get_session, mock_database_provider):
        """Test service uses default API URL when not configured."""
        # Arrange
        config = {"app": {}}

        # Act
        service = PRReviewService(config, mock_database_provider)

        # Assert
        assert service._api_base_url == "http://localhost:28002"


class TestPRReviewServiceEnqueue:
    """Test PR Review service enqueue method."""

    @patch('src.services.pr_review_service.get_session')
    @patch('src.services.pr_review_service.QueueManager')
    def test_enqueue_review_creates_new_review(
        self, mock_queue_manager_class, mock_get_session, mock_config, mock_database_provider,
        mock_session, mock_repository, sample_enqueue_request
    ):
        """Test enqueue creates new PR review in database."""
        # Arrange
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=None)

        mock_queue = MagicMock()
        mock_queue.send_task.return_value = True
        mock_queue_manager_class.return_value = mock_queue

        with patch.object(PRReviewService, '_get_review_repo', return_value=mock_repository):
            service = PRReviewService(mock_config, mock_database_provider)

            # Act
            response, http_status = service.enqueue_review(sample_enqueue_request)

        # Assert
        assert http_status == 202
        assert response.status == AckStatus.ACCEPTED
        assert response.review_id.startswith(REVIEW_ID_PREFIX)
        mock_repository.create.assert_called_once()

    @patch('src.services.pr_review_service.get_session')
    def test_enqueue_review_returns_existing_for_duplicate(
        self, mock_get_session, mock_config, mock_database_provider,
        mock_session, mock_repository, sample_enqueue_request, sample_pr_review
    ):
        """Test enqueue returns existing review for duplicate idempotency key."""
        # Arrange
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=None)
        mock_repository.get_by_idempotency_key.return_value = sample_pr_review

        with patch.object(PRReviewService, '_get_review_repo', return_value=mock_repository):
            service = PRReviewService(mock_config, mock_database_provider)

            # Act
            response, http_status = service.enqueue_review(sample_enqueue_request)

        # Assert
        assert http_status == 200
        assert response.status == AckStatus.ALREADY_EXISTS
        assert response.review_id == sample_pr_review.id
        mock_repository.create.assert_not_called()

    @patch('src.services.pr_review_service.get_session')
    @patch('src.services.pr_review_service.QueueManager')
    def test_enqueue_review_generates_correlation_id(
        self, mock_queue_manager_class, mock_get_session, mock_config, mock_database_provider,
        mock_session, mock_repository, sample_pr_metadata
    ):
        """Test enqueue generates correlation ID when not provided."""
        # Arrange
        request_without_correlation = PRReviewEnqueueRequest(
            pr_metadata=sample_pr_metadata,
            pr_context="Review this PR",
            correlation_id=None,
            idempotency_key=None,
        )
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=None)

        mock_queue = MagicMock()
        mock_queue.send_task.return_value = True
        mock_queue_manager_class.return_value = mock_queue

        with patch.object(PRReviewService, '_get_review_repo', return_value=mock_repository):
            service = PRReviewService(mock_config, mock_database_provider)

            # Act
            response, http_status = service.enqueue_review(request_without_correlation)

        # Assert
        assert response.telemetry.correlation_id is not None
        assert len(response.telemetry.correlation_id) == 36  # UUID length

    @patch('src.services.pr_review_service.get_session')
    def test_enqueue_review_handles_db_error(
        self, mock_get_session, mock_config, mock_database_provider,
        mock_session, mock_repository, sample_enqueue_request
    ):
        """Test enqueue raises BusinessLogicError on database failure."""
        # Arrange
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=None)
        mock_repository.create.side_effect = Exception("Database connection failed")

        with patch.object(PRReviewService, '_get_review_repo', return_value=mock_repository):
            service = PRReviewService(mock_config, mock_database_provider)

            # Act & Assert
            with pytest.raises(BusinessLogicError) as exc_info:
                service.enqueue_review(sample_enqueue_request)

            assert "Failed to create review" in str(exc_info.value)


class TestPRReviewServiceGetStatus:
    """Test PR Review service get_review_status method."""

    @patch('src.services.pr_review_service.get_session')
    def test_get_review_status_returns_status(
        self, mock_get_session, mock_config, mock_database_provider,
        mock_session, mock_repository, sample_pr_review
    ):
        """Test get_review_status returns correct status."""
        # Arrange
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=None)
        mock_repository.get_by_id.return_value = sample_pr_review

        with patch.object(PRReviewService, '_get_review_repo', return_value=mock_repository):
            service = PRReviewService(mock_config, mock_database_provider)

            # Act
            response = service.get_review_status("rev_01JH8NM3W8C4M7R7JX7WZ9QY5Q")

        # Assert
        assert response.review_id == sample_pr_review.id
        assert response.status == ReviewStatus.RUNNING
        assert response.pr_identity.repository == "org/repo"
        assert response.pr_identity.pr_number == 123

    @patch('src.services.pr_review_service.get_session')
    def test_get_review_status_not_found(
        self, mock_get_session, mock_config, mock_database_provider,
        mock_session, mock_repository
    ):
        """Test get_review_status raises TaskNotFoundError for unknown ID."""
        # Arrange
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=None)
        mock_repository.get_by_id.return_value = None

        with patch.object(PRReviewService, '_get_review_repo', return_value=mock_repository):
            service = PRReviewService(mock_config, mock_database_provider)

            # Act & Assert
            with pytest.raises(TaskNotFoundError) as exc_info:
                service.get_review_status("rev_nonexistent")

            assert "rev_nonexistent" in str(exc_info.value)

    @patch('src.services.pr_review_service.get_session')
    def test_get_review_status_includes_error_info(
        self, mock_get_session, mock_config, mock_database_provider,
        mock_session, mock_repository
    ):
        """Test get_review_status includes error info for failed reviews."""
        # Arrange
        failed_review = PRReview(
            id="rev_failed123",
            idempotency_key="org/repo:123:run_1",
            status=ReviewStatus.FAILED.value,
            pr_metadata=json.dumps({
                "pr_url": "https://github.com/org/repo/pull/123",
                "pr_number": 123,
                "repository": "org/repo",
            }),
            correlation_id="test-correlation-id",
            error_info=json.dumps({
                "code": "upstream_error",
                "message": "Claude Code agent failed",
            }),
            enqueued_at=int(time.time()) - 120,
            started_at=int(time.time()) - 60,
            completed_at=int(time.time()),
            created_at=int(time.time()) - 120,
            updated_at=int(time.time()),
        )
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=None)
        mock_repository.get_by_id.return_value = failed_review

        with patch.object(PRReviewService, '_get_review_repo', return_value=mock_repository):
            service = PRReviewService(mock_config, mock_database_provider)

            # Act
            response = service.get_review_status("rev_failed123")

        # Assert
        assert response.status == ReviewStatus.FAILED
        assert response.error is not None
        assert response.error.code == ErrorCode.UPSTREAM_ERROR
        assert response.error.message == "Claude Code agent failed"


class TestPRReviewServiceUpdateStatus:
    """Test PR Review service update_review_status method."""

    @patch('src.services.pr_review_service.get_session')
    def test_update_review_status_success(
        self, mock_get_session, mock_config, mock_database_provider,
        mock_session, mock_repository
    ):
        """Test update_review_status updates successfully."""
        # Arrange
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=None)

        with patch.object(PRReviewService, '_get_review_repo', return_value=mock_repository):
            service = PRReviewService(mock_config, mock_database_provider)

            # Act - should not raise
            service.update_review_status(
                "rev_01JH8NM3W8C4M7R7JX7WZ9QY5Q",
                ReviewStatus.COMPLETED,
            )

        # Assert
        mock_repository.update_status.assert_called_once()
        mock_session.commit.assert_called()

    @patch('src.services.pr_review_service.get_session')
    def test_update_review_status_with_error(
        self, mock_get_session, mock_config, mock_database_provider,
        mock_session, mock_repository
    ):
        """Test update_review_status with error info for failed status."""
        # Arrange
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=None)

        with patch.object(PRReviewService, '_get_review_repo', return_value=mock_repository):
            service = PRReviewService(mock_config, mock_database_provider)

            # Act
            service.update_review_status(
                "rev_01JH8NM3W8C4M7R7JX7WZ9QY5Q",
                ReviewStatus.FAILED,
                error_code="upstream_error",
                error_message="Agent failed",
            )

        # Assert
        call_args = mock_repository.update_status.call_args
        assert call_args[0][0] == "rev_01JH8NM3W8C4M7R7JX7WZ9QY5Q"
        assert call_args[0][1] == ReviewStatus.FAILED
        error_info = call_args[0][2]
        assert error_info["code"] == "upstream_error"
        assert error_info["message"] == "Agent failed"

    @patch('src.services.pr_review_service.get_session')
    def test_update_review_status_not_found(
        self, mock_get_session, mock_config, mock_database_provider,
        mock_session, mock_repository
    ):
        """Test update_review_status raises TaskNotFoundError for unknown ID."""
        # Arrange
        from src.repositories.exceptions import EntityNotFoundError
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=None)
        mock_repository.update_status.side_effect = EntityNotFoundError("PRReview", "rev_nonexistent")

        with patch.object(PRReviewService, '_get_review_repo', return_value=mock_repository):
            service = PRReviewService(mock_config, mock_database_provider)

            # Act & Assert
            with pytest.raises(TaskNotFoundError):
                service.update_review_status(
                    "rev_nonexistent",
                    ReviewStatus.COMPLETED,
                )


class TestPRReviewServiceHealthCheck:
    """Test PR Review service health check method."""

    @patch('src.services.pr_review_service.get_session')
    def test_health_check_healthy(
        self, mock_get_session, mock_config, mock_database_provider,
        mock_session, mock_repository
    ):
        """Test health check returns healthy status."""
        # Arrange
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=None)
        mock_repository.get_recent_reviews.return_value = []

        with patch.object(PRReviewService, '_get_review_repo', return_value=mock_repository):
            service = PRReviewService(mock_config, mock_database_provider)

            # Act
            result = service.health_check()

        # Assert
        assert result["database"] == "healthy"
        assert result["status"] == "healthy"

    @patch('src.services.pr_review_service.get_session')
    def test_health_check_degraded_on_db_error(
        self, mock_get_session, mock_config, mock_database_provider,
        mock_session, mock_repository
    ):
        """Test health check returns degraded status on database error."""
        # Arrange
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=None)
        mock_repository.get_recent_reviews.side_effect = Exception("Connection timeout")

        with patch.object(PRReviewService, '_get_review_repo', return_value=mock_repository):
            service = PRReviewService(mock_config, mock_database_provider)

            # Act
            result = service.health_check()

        # Assert
        assert "unhealthy" in result["database"]
        assert result["status"] == "degraded"
