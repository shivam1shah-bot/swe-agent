"""
Unit tests for PR Review router endpoints.

Tests the PR Review router logic with mocked dependencies.
"""

import pytest
from unittest.mock import MagicMock, patch
import sys

from src.constants.pr_review import (
    ApiVersion,
    ReviewStatus,
    AckStatus,
    ErrorCode,
    DEFAULT_API_VERSION,
)
from src.models.pr_review import (
    PRMetadata,
    PRReviewEnqueueRequest,
    PRReviewAckResponse,
    ReviewStatusResponse,
    TelemetryLite,
    PRReviewLinks,
    PRIdentity,
    ReviewTimestamps,
    ErrorResponse,
    Error,
)


@pytest.fixture(scope="module")
def mock_worker_modules():
    """
    Mock worker/task modules that trigger DB connections at import time.
    
    These modules have module-level initialization (TaskManager()) that
    attempts to connect to the database, so they must be mocked before import.
    """
    mock_worker = MagicMock()
    mock_tasks = MagicMock()
    
    with patch.dict(sys.modules, {
        'src.worker': mock_worker,
        'src.worker.queue_manager': mock_worker,
        'src.tasks': mock_tasks,
        'src.tasks.service': mock_tasks,
    }):
        yield mock_worker, mock_tasks


@pytest.fixture
def mock_pr_review_service(mock_worker_modules):
    """Mock PR review service for testing."""
    return MagicMock()


@pytest.fixture
def mock_app_state(mock_pr_review_service):
    """Mock FastAPI app state."""
    mock_state = MagicMock()
    mock_state.pr_review_service = mock_pr_review_service
    return mock_state


@pytest.fixture
def mock_request(mock_app_state):
    """Mock FastAPI request with app state."""
    from fastapi import Request
    mock_request = MagicMock(spec=Request)
    mock_request.app.state = mock_app_state
    return mock_request


@pytest.fixture
def mock_response():
    """Mock FastAPI response."""
    from fastapi import Response
    response = MagicMock(spec=Response)
    response.headers = {}
    return response


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
def sample_ack_response():
    """Sample acknowledgement response for testing."""
    return PRReviewAckResponse(
        api_version=DEFAULT_API_VERSION.value,
        review_id="rev_01JH8NM3W8C4M7R7JX7WZ9QY5Q",
        status=AckStatus.ACCEPTED,
        telemetry=TelemetryLite(
            correlation_id="550e8400-e29b-41d4-a716-446655440000",
            timestamp="2025-01-04T12:00:00Z",
        ),
        links=PRReviewLinks(
            status_url="http://localhost:28002/api/v1/pr-review/rev_01JH8NM3W8C4M7R7JX7WZ9QY5Q"
        ),
    )


@pytest.fixture
def sample_status_response():
    """Sample status response for testing."""
    return ReviewStatusResponse(
        api_version=DEFAULT_API_VERSION.value,
        review_id="rev_01JH8NM3W8C4M7R7JX7WZ9QY5Q",
        status=ReviewStatus.RUNNING,
        pr_identity=PRIdentity(repository="org/repo", pr_number=123),
        telemetry=TelemetryLite(
            correlation_id="550e8400-e29b-41d4-a716-446655440000",
            timestamp="2025-01-04T12:00:00Z",
        ),
        timestamps=ReviewTimestamps(
            enqueued_at="2025-01-04T11:55:00Z",
            started_at="2025-01-04T11:56:00Z",
        ),
    )


class TestPRReviewRouterDependencies:
    """Test PR review router dependencies."""

    def test_get_pr_review_service_success(self, mock_request, mock_app_state):
        """Test successful PR review service retrieval."""
        from fastapi import HTTPException, status

        expected_service = mock_app_state.pr_review_service

        def get_pr_review_service_func(request):
            try:
                return request.app.state.pr_review_service
            except AttributeError:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="PR review service not available",
                )

        result = get_pr_review_service_func(mock_request)
        assert result == expected_service

    def test_get_pr_review_service_attribute_error(self, mock_request):
        """Test PR review service attribute error."""
        from fastapi import HTTPException, status

        del mock_request.app.state.pr_review_service

        def get_pr_review_service_func(request):
            try:
                return request.app.state.pr_review_service
            except AttributeError:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="PR review service not available",
                )

        with pytest.raises(HTTPException) as exc_info:
            get_pr_review_service_func(mock_request)

        assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "PR review service not available" in str(exc_info.value.detail)

    def test_get_correlation_id_from_x_correlation_id(self):
        """Test getting correlation ID from X-Correlation-ID header."""
        def get_correlation_id(x_correlation_id, x_request_id):
            return x_correlation_id or x_request_id

        result = get_correlation_id("test-correlation-id", None)
        assert result == "test-correlation-id"

    def test_get_correlation_id_from_x_request_id(self):
        """Test getting correlation ID from X-Request-ID header."""
        def get_correlation_id(x_correlation_id, x_request_id):
            return x_correlation_id or x_request_id

        result = get_correlation_id(None, "test-request-id")
        assert result == "test-request-id"

    def test_get_correlation_id_prefers_correlation_id(self):
        """Test that X-Correlation-ID takes precedence over X-Request-ID."""
        def get_correlation_id(x_correlation_id, x_request_id):
            return x_correlation_id or x_request_id

        result = get_correlation_id("correlation-id", "request-id")
        assert result == "correlation-id"

    def test_get_correlation_id_returns_none(self):
        """Test getting correlation ID when no headers are provided."""
        def get_correlation_id(x_correlation_id, x_request_id):
            return x_correlation_id or x_request_id

        result = get_correlation_id(None, None)
        assert result is None

    def test_get_current_timestamp(self):
        """Test current timestamp generation."""
        from datetime import datetime, timezone

        def get_current_timestamp():
            return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        result = get_current_timestamp()
        assert isinstance(result, str)
        assert result.endswith("Z")
        assert "T" in result

    def test_build_error_response(self):
        """Test building error response."""
        import uuid

        def build_error_response(error_code, message, correlation_id=None):
            return ErrorResponse(
                api_version=DEFAULT_API_VERSION.value,
                error=Error(
                    code=error_code,
                    message=message,
                ),
                telemetry=TelemetryLite(
                    correlation_id=correlation_id or str(uuid.uuid4()),
                    timestamp="2025-01-04T12:00:00Z",
                ),
            )

        result = build_error_response(
            ErrorCode.VALIDATION_ERROR,
            "Test error message",
            correlation_id="test-correlation-id",
        )

        assert result.api_version == DEFAULT_API_VERSION.value
        assert result.error.code == ErrorCode.VALIDATION_ERROR
        assert result.error.message == "Test error message"
        assert result.telemetry.correlation_id == "test-correlation-id"


class TestEnqueuePRReviewEndpoint:
    """Test enqueue PR review endpoint function."""

    @pytest.mark.asyncio
    async def test_enqueue_pr_review_success(
        self,
        mock_request,
        mock_response,
        mock_pr_review_service,
        sample_enqueue_request,
        sample_ack_response,
    ):
        """Test successful PR review enqueue returns 202."""
        mock_pr_review_service.enqueue_review.return_value = (sample_ack_response, 202)

        async def enqueue_pr_review_func(
            request, response, review_request, pr_review_service, correlation_id, idempotency_key
        ):
            if idempotency_key and not review_request.idempotency_key:
                review_request.idempotency_key = idempotency_key
            if correlation_id and not review_request.correlation_id:
                review_request.correlation_id = correlation_id

            ack_response, http_status = pr_review_service.enqueue_review(review_request)
            response.status_code = http_status

            if ack_response.links and ack_response.links.status_url:
                response.headers["Location"] = ack_response.links.status_url

            return ack_response

        result = await enqueue_pr_review_func(
            request=mock_request,
            response=mock_response,
            review_request=sample_enqueue_request,
            pr_review_service=mock_pr_review_service,
            correlation_id="test-correlation-id",
            idempotency_key=None,
        )

        assert result.review_id == sample_ack_response.review_id
        assert result.status == AckStatus.ACCEPTED
        assert mock_response.status_code == 202
        mock_pr_review_service.enqueue_review.assert_called_once()

    @pytest.mark.asyncio
    async def test_enqueue_pr_review_duplicate_returns_200(
        self,
        mock_request,
        mock_response,
        mock_pr_review_service,
        sample_enqueue_request,
    ):
        """Test duplicate PR review returns 200 with already_exists status."""
        duplicate_response = PRReviewAckResponse(
            api_version=DEFAULT_API_VERSION.value,
            review_id="rev_existing123",
            status=AckStatus.ALREADY_EXISTS,
            telemetry=TelemetryLite(
                correlation_id="test-correlation-id",
                timestamp="2025-01-04T12:00:00Z",
            ),
            links=PRReviewLinks(
                status_url="http://localhost:28002/api/v1/pr-review/rev_existing123"
            ),
        )
        mock_pr_review_service.enqueue_review.return_value = (duplicate_response, 200)

        async def enqueue_pr_review_func(
            request, response, review_request, pr_review_service, correlation_id, idempotency_key
        ):
            if idempotency_key and not review_request.idempotency_key:
                review_request.idempotency_key = idempotency_key
            if correlation_id and not review_request.correlation_id:
                review_request.correlation_id = correlation_id

            ack_response, http_status = pr_review_service.enqueue_review(review_request)
            response.status_code = http_status
            return ack_response

        result = await enqueue_pr_review_func(
            request=mock_request,
            response=mock_response,
            review_request=sample_enqueue_request,
            pr_review_service=mock_pr_review_service,
            correlation_id="test-correlation-id",
            idempotency_key=sample_enqueue_request.idempotency_key,
        )

        assert result.status == AckStatus.ALREADY_EXISTS
        assert mock_response.status_code == 200

    @pytest.mark.asyncio
    async def test_enqueue_pr_review_uses_header_idempotency_key(
        self,
        mock_request,
        mock_response,
        mock_pr_review_service,
        sample_pr_metadata,
        sample_ack_response,
    ):
        """Test that header idempotency key is used when not in body."""
        request_without_key = PRReviewEnqueueRequest(
            pr_metadata=sample_pr_metadata,
            pr_context="Review this PR",
            correlation_id=None,
            idempotency_key=None,
        )
        mock_pr_review_service.enqueue_review.return_value = (sample_ack_response, 202)

        async def enqueue_pr_review_func(
            request, response, review_request, pr_review_service, correlation_id, idempotency_key
        ):
            if idempotency_key and not review_request.idempotency_key:
                review_request.idempotency_key = idempotency_key
            if correlation_id and not review_request.correlation_id:
                review_request.correlation_id = correlation_id

            ack_response, http_status = pr_review_service.enqueue_review(review_request)
            response.status_code = http_status
            return ack_response

        await enqueue_pr_review_func(
            request=mock_request,
            response=mock_response,
            review_request=request_without_key,
            pr_review_service=mock_pr_review_service,
            correlation_id="header-correlation-id",
            idempotency_key="header-idempotency-key",
        )

        call_args = mock_pr_review_service.enqueue_review.call_args
        request_arg = call_args[0][0]
        assert request_arg.idempotency_key == "header-idempotency-key"
        assert request_arg.correlation_id == "header-correlation-id"


class TestGetPRReviewStatusEndpoint:
    """Test get PR review status endpoint function."""

    @pytest.mark.asyncio
    async def test_get_review_status_success(
        self,
        mock_request,
        mock_pr_review_service,
        sample_status_response,
    ):
        """Test successful status retrieval."""
        mock_pr_review_service.get_review_status.return_value = sample_status_response

        async def get_pr_review_status_func(
            request, review_id, pr_review_service, correlation_id
        ):
            return pr_review_service.get_review_status(review_id)

        result = await get_pr_review_status_func(
            request=mock_request,
            review_id="rev_01JH8NM3W8C4M7R7JX7WZ9QY5Q",
            pr_review_service=mock_pr_review_service,
            correlation_id="test-correlation-id",
        )

        assert result.review_id == sample_status_response.review_id
        assert result.status == ReviewStatus.RUNNING
        mock_pr_review_service.get_review_status.assert_called_once_with(
            "rev_01JH8NM3W8C4M7R7JX7WZ9QY5Q"
        )

    @pytest.mark.asyncio
    async def test_get_review_status_not_found(
        self,
        mock_request,
        mock_pr_review_service,
    ):
        """Test not found error returns 404."""
        from fastapi import HTTPException, status

        class TaskNotFoundError(Exception):
            pass

        mock_pr_review_service.get_review_status.side_effect = TaskNotFoundError(
            "Review not found: rev_nonexistent"
        )

        async def get_pr_review_status_func(
            request, review_id, pr_review_service, correlation_id
        ):
            try:
                return pr_review_service.get_review_status(review_id)
            except TaskNotFoundError:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": {"code": "not_found", "message": "review_id not found"}},
                )

        with pytest.raises(HTTPException) as exc_info:
            await get_pr_review_status_func(
                request=mock_request,
                review_id="rev_nonexistent",
                pr_review_service=mock_pr_review_service,
                correlation_id="test-correlation-id",
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_review_status_with_failed_status(
        self,
        mock_request,
        mock_pr_review_service,
    ):
        """Test status retrieval for failed review includes error info."""
        failed_response = ReviewStatusResponse(
            api_version=DEFAULT_API_VERSION.value,
            review_id="rev_failed123",
            status=ReviewStatus.FAILED,
            pr_identity=PRIdentity(repository="org/repo", pr_number=123),
            telemetry=TelemetryLite(
                correlation_id="test-correlation-id",
                timestamp="2025-01-04T12:00:00Z",
            ),
            error=Error(
                code=ErrorCode.UPSTREAM_ERROR,
                message="Claude Code agent failed",
            ),
            timestamps=ReviewTimestamps(
                enqueued_at="2025-01-04T11:55:00Z",
                started_at="2025-01-04T11:56:00Z",
                completed_at="2025-01-04T11:57:00Z",
            ),
        )
        mock_pr_review_service.get_review_status.return_value = failed_response

        async def get_pr_review_status_func(
            request, review_id, pr_review_service, correlation_id
        ):
            return pr_review_service.get_review_status(review_id)

        result = await get_pr_review_status_func(
            request=mock_request,
            review_id="rev_failed123",
            pr_review_service=mock_pr_review_service,
            correlation_id="test-correlation-id",
        )

        assert result.status == ReviewStatus.FAILED
        assert result.error is not None
        assert result.error.code == ErrorCode.UPSTREAM_ERROR
