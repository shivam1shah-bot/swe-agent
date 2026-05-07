"""
Unit tests for PR Review models.

Tests both SQLAlchemy and Pydantic models for PR Review.
"""

import json
import time
import pytest
from pydantic import ValidationError as PydanticValidationError

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
    FieldError,
    ErrorResponse,
    Agent,
    HealthResponse,
)
from src.constants.pr_review import (
    ReviewStatus,
    AckStatus,
    ErrorCode,
    AgentStatus,
    DEFAULT_API_VERSION,
)


class TestPRReviewSQLAlchemyModel:
    """Test PRReview SQLAlchemy model."""

    def test_pr_review_model_creation(self):
        """Test PRReview model creates with explicit values."""
        # Arrange & Act - Note: SQLAlchemy defaults only apply when persisting to DB
        # For unit tests, we set values explicitly
        review = PRReview(
            id="rev_01JH8NM3W8C4M7R7JX7WZ9QY5Q",
            status=ReviewStatus.ACCEPTED.value,  # Set explicitly for unit test
            pr_metadata=json.dumps({
                "pr_url": "https://github.com/org/repo/pull/123",
                "pr_number": 123,
                "repository": "org/repo",
            }),
            correlation_id="550e8400-e29b-41d4-a716-446655440000",
        )

        # Assert
        assert review.id == "rev_01JH8NM3W8C4M7R7JX7WZ9QY5Q"
        assert review.status == ReviewStatus.ACCEPTED.value
        assert review.idempotency_key is None
        assert review.pr_context is None
        assert review.error_info is None
        assert review.enqueued_at is None
        assert review.started_at is None
        assert review.completed_at is None

    def test_pr_review_model_with_all_fields(self):
        """Test PRReview model with all fields populated."""
        # Arrange
        current_time = int(time.time())
        pr_metadata = {
            "pr_url": "https://github.com/org/repo/pull/123",
            "pr_number": 123,
            "repository": "org/repo",
            "author": "testuser",
            "title": "Test PR",
            "branch": "feature/test",
            "target_branch": "main",
        }

        # Act
        review = PRReview(
            id="rev_01JH8NM3W8C4M7R7JX7WZ9QY5Q",
            idempotency_key="org/repo:123:run_1",
            status=ReviewStatus.RUNNING.value,
            pr_metadata=json.dumps(pr_metadata),
            pr_context="Additional context",
            correlation_id="550e8400-e29b-41d4-a716-446655440000",
            enqueued_at=current_time - 60,
            started_at=current_time - 30,
            created_at=current_time - 60,
            updated_at=current_time - 30,
        )

        # Assert
        assert review.status == ReviewStatus.RUNNING.value
        assert review.idempotency_key == "org/repo:123:run_1"
        assert review.pr_context == "Additional context"

    def test_pr_metadata_dict_property(self):
        """Test pr_metadata_dict property parses JSON correctly."""
        # Arrange
        pr_metadata = {
            "pr_url": "https://github.com/org/repo/pull/123",
            "pr_number": 123,
            "repository": "org/repo",
        }
        review = PRReview(
            id="rev_test",
            pr_metadata=json.dumps(pr_metadata),
            correlation_id="test-id",
        )

        # Act
        result = review.pr_metadata_dict

        # Assert
        assert result == pr_metadata

    def test_pr_metadata_dict_handles_invalid_json(self):
        """Test pr_metadata_dict returns empty dict for invalid JSON."""
        # Arrange
        review = PRReview(
            id="rev_test",
            pr_metadata="invalid json",
            correlation_id="test-id",
        )

        # Act
        result = review.pr_metadata_dict

        # Assert
        assert result == {}

    def test_pr_metadata_dict_handles_none(self):
        """Test pr_metadata_dict returns empty dict for None."""
        # Arrange
        review = PRReview(
            id="rev_test",
            pr_metadata=None,
            correlation_id="test-id",
        )

        # Act
        result = review.pr_metadata_dict

        # Assert
        assert result == {}

    def test_error_info_dict_property(self):
        """Test error_info_dict property parses JSON correctly."""
        # Arrange
        error_info = {"code": "upstream_error", "message": "Test error"}
        review = PRReview(
            id="rev_test",
            pr_metadata="{}",
            correlation_id="test-id",
            error_info=json.dumps(error_info),
        )

        # Act
        result = review.error_info_dict

        # Assert
        assert result == error_info

    def test_error_info_dict_handles_none(self):
        """Test error_info_dict returns None for None."""
        # Arrange
        review = PRReview(
            id="rev_test",
            pr_metadata="{}",
            correlation_id="test-id",
        )

        # Act
        result = review.error_info_dict

        # Assert
        assert result is None

    def test_set_enqueued(self):
        """Test set_enqueued sets status and timestamp."""
        # Arrange
        review = PRReview(
            id="rev_test",
            pr_metadata="{}",
            correlation_id="test-id",
        )
        before_time = int(time.time())

        # Act
        review.set_enqueued()

        # Assert
        assert review.status == ReviewStatus.QUEUED.value
        assert review.enqueued_at >= before_time
        assert review.updated_at >= before_time

    def test_set_running(self):
        """Test set_running sets status and timestamp."""
        # Arrange
        review = PRReview(
            id="rev_test",
            pr_metadata="{}",
            correlation_id="test-id",
        )
        before_time = int(time.time())

        # Act
        review.set_running()

        # Assert
        assert review.status == ReviewStatus.RUNNING.value
        assert review.started_at >= before_time
        assert review.updated_at >= before_time

    def test_set_completed(self):
        """Test set_completed sets status and timestamp."""
        # Arrange
        review = PRReview(
            id="rev_test",
            pr_metadata="{}",
            correlation_id="test-id",
        )
        before_time = int(time.time())

        # Act
        review.set_completed()

        # Assert
        assert review.status == ReviewStatus.COMPLETED.value
        assert review.completed_at >= before_time
        assert review.updated_at >= before_time

    def test_set_failed(self):
        """Test set_failed sets status, error info, and timestamp."""
        # Arrange
        review = PRReview(
            id="rev_test",
            pr_metadata="{}",
            correlation_id="test-id",
        )
        before_time = int(time.time())

        # Act
        review.set_failed("upstream_error", "Agent crashed")

        # Assert
        assert review.status == ReviewStatus.FAILED.value
        assert review.completed_at >= before_time
        assert review.error_info_dict["code"] == "upstream_error"
        assert review.error_info_dict["message"] == "Agent crashed"
        assert review.updated_at >= before_time

    def test_get_repository(self):
        """Test get_repository returns repository from metadata."""
        # Arrange
        review = PRReview(
            id="rev_test",
            pr_metadata=json.dumps({"repository": "org/repo", "pr_number": 123}),
            correlation_id="test-id",
        )

        # Act
        result = review.get_repository()

        # Assert
        assert result == "org/repo"

    def test_get_pr_number(self):
        """Test get_pr_number returns PR number from metadata."""
        # Arrange
        review = PRReview(
            id="rev_test",
            pr_metadata=json.dumps({"repository": "org/repo", "pr_number": 123}),
            correlation_id="test-id",
        )

        # Act
        result = review.get_pr_number()

        # Assert
        assert result == 123


class TestPRMetadataPydanticModel:
    """Test PRMetadata Pydantic model."""

    def test_pr_metadata_valid(self):
        """Test PRMetadata with valid data."""
        # Act
        metadata = PRMetadata(
            pr_url="https://github.com/org/repo/pull/123",
            pr_number=123,
            repository="org/repo",
            author="testuser",
            title="Test PR",
            branch="feature/test",
            target_branch="main",
        )

        # Assert
        assert metadata.pr_url == "https://github.com/org/repo/pull/123"
        assert metadata.pr_number == 123
        assert metadata.repository == "org/repo"

    def test_pr_metadata_requires_pr_number_positive(self):
        """Test PRMetadata requires positive pr_number."""
        # Act & Assert
        with pytest.raises(PydanticValidationError) as exc_info:
            PRMetadata(
                pr_url="https://github.com/org/repo/pull/0",
                pr_number=0,
                repository="org/repo",
                author="testuser",
                title="Test PR",
                branch="feature/test",
                target_branch="main",
            )

        assert "greater than or equal to 1" in str(exc_info.value)

    def test_pr_metadata_validates_repository_format(self):
        """Test PRMetadata validates repository format (owner/name)."""
        # Act & Assert
        with pytest.raises(PydanticValidationError) as exc_info:
            PRMetadata(
                pr_url="https://github.com/invalid/pull/123",
                pr_number=123,
                repository="invalid-repo-format",  # Missing owner/name format
                author="testuser",
                title="Test PR",
                branch="feature/test",
                target_branch="main",
            )

        assert "String should match pattern" in str(exc_info.value)

    def test_pr_metadata_description_optional(self):
        """Test PRMetadata description is optional."""
        # Act
        metadata = PRMetadata(
            pr_url="https://github.com/org/repo/pull/123",
            pr_number=123,
            repository="org/repo",
            author="testuser",
            title="Test PR",
            branch="feature/test",
            target_branch="main",
        )

        # Assert
        assert metadata.description is None


class TestPRReviewEnqueueRequestModel:
    """Test PRReviewEnqueueRequest Pydantic model."""

    def test_enqueue_request_valid(self):
        """Test PRReviewEnqueueRequest with valid data."""
        # Arrange
        pr_metadata = PRMetadata(
            pr_url="https://github.com/org/repo/pull/123",
            pr_number=123,
            repository="org/repo",
            author="testuser",
            title="Test PR",
            branch="feature/test",
            target_branch="main",
        )

        # Act
        request = PRReviewEnqueueRequest(
            pr_metadata=pr_metadata,
            pr_context="Additional context",
            correlation_id="550e8400-e29b-41d4-a716-446655440000",
            idempotency_key="org/repo:123:run_1",
        )

        # Assert
        assert request.pr_metadata == pr_metadata
        assert request.pr_context == "Additional context"

    def test_enqueue_request_optional_fields(self):
        """Test PRReviewEnqueueRequest optional fields."""
        # Arrange
        pr_metadata = PRMetadata(
            pr_url="https://github.com/org/repo/pull/123",
            pr_number=123,
            repository="org/repo",
            author="testuser",
            title="Test PR",
            branch="feature/test",
            target_branch="main",
        )

        # Act
        request = PRReviewEnqueueRequest(
            pr_metadata=pr_metadata,
        )

        # Assert
        assert request.pr_context is None
        assert request.correlation_id is None
        assert request.idempotency_key is None


class TestPRReviewAckResponseModel:
    """Test PRReviewAckResponse Pydantic model."""

    def test_ack_response_valid(self):
        """Test PRReviewAckResponse with valid data."""
        # Act
        response = PRReviewAckResponse(
            api_version="v1",
            review_id="rev_01JH8NM3W8C4M7R7JX7WZ9QY5Q",
            status=AckStatus.ACCEPTED,
            telemetry=TelemetryLite(
                correlation_id="test-id",
                timestamp="2025-01-04T12:00:00Z",
            ),
            links=PRReviewLinks(
                status_url="http://localhost:28002/api/v1/pr-review/rev_01JH8NM3"
            ),
        )

        # Assert
        assert response.review_id == "rev_01JH8NM3W8C4M7R7JX7WZ9QY5Q"
        assert response.status == AckStatus.ACCEPTED

    def test_ack_response_already_exists_status(self):
        """Test PRReviewAckResponse with already_exists status."""
        # Act
        response = PRReviewAckResponse(
            api_version="v1",
            review_id="rev_existing",
            status=AckStatus.ALREADY_EXISTS,
        )

        # Assert
        assert response.status == AckStatus.ALREADY_EXISTS


class TestReviewStatusResponseModel:
    """Test ReviewStatusResponse Pydantic model."""

    def test_status_response_valid(self):
        """Test ReviewStatusResponse with valid data."""
        # Act
        response = ReviewStatusResponse(
            api_version="v1",
            review_id="rev_01JH8NM3W8C4M7R7JX7WZ9QY5Q",
            status=ReviewStatus.RUNNING,
            pr_identity=PRIdentity(repository="org/repo", pr_number=123),
            telemetry=TelemetryLite(
                correlation_id="test-id",
                timestamp="2025-01-04T12:00:00Z",
            ),
            timestamps=ReviewTimestamps(
                enqueued_at="2025-01-04T11:55:00Z",
                started_at="2025-01-04T11:56:00Z",
            ),
        )

        # Assert
        assert response.status == ReviewStatus.RUNNING
        assert response.pr_identity.repository == "org/repo"

    def test_status_response_with_error(self):
        """Test ReviewStatusResponse with error for failed status."""
        # Act
        response = ReviewStatusResponse(
            api_version="v1",
            review_id="rev_failed",
            status=ReviewStatus.FAILED,
            pr_identity=PRIdentity(repository="org/repo", pr_number=123),
            error=Error(
                code=ErrorCode.UPSTREAM_ERROR,
                message="Agent failed",
            ),
        )

        # Assert
        assert response.status == ReviewStatus.FAILED
        assert response.error.code == ErrorCode.UPSTREAM_ERROR


class TestErrorResponseModel:
    """Test ErrorResponse Pydantic model."""

    def test_error_response_valid(self):
        """Test ErrorResponse with valid data."""
        # Act
        response = ErrorResponse(
            api_version="v1",
            error=Error(
                code=ErrorCode.VALIDATION_ERROR,
                message="Invalid field",
                field_errors=[
                    FieldError(field="pr_metadata.pr_number", message="must be positive")
                ],
            ),
        )

        # Assert
        assert response.error.code == ErrorCode.VALIDATION_ERROR
        assert len(response.error.field_errors) == 1

    def test_error_response_with_retry_after(self):
        """Test ErrorResponse with retry_after_s for rate limiting."""
        # Act
        response = ErrorResponse(
            api_version="v1",
            error=Error(
                code=ErrorCode.RATE_LIMITED,
                message="Too many requests",
                retry_after_s=30,
            ),
        )

        # Assert
        assert response.error.code == ErrorCode.RATE_LIMITED
        assert response.error.retry_after_s == 30


class TestHealthResponseModel:
    """Test HealthResponse Pydantic model."""

    def test_health_response_valid(self):
        """Test HealthResponse with valid data."""
        # Act
        response = HealthResponse(
            agents=[
                Agent(
                    name="Claude Code",
                    type="claude_code",
                    status=AgentStatus.ACTIVE,
                    description="AI-powered code generation",
                )
            ],
            total_count=1,
            active_count=1,
            timestamp="2025-01-04T12:00:00Z",
        )

        # Assert
        assert len(response.agents) == 1
        assert response.agents[0].status == AgentStatus.ACTIVE
        assert response.total_count == 1
        assert response.active_count == 1
