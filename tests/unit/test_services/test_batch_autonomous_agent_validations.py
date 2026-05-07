"""
Unit tests for Autonomous Agent Batch Service validation logic.

Tests focus on batch-specific validations including repository count limits,
parameter validation, and boundary conditions for the maximum batch size.
"""

import pytest
from unittest.mock import MagicMock, patch
from src.services.agents.batch import AutonomousAgentBatchService


@pytest.fixture
def batch_service():
    """Fixture to provide a fresh batch service instance."""
    return AutonomousAgentBatchService()


def test_batch_missing_prompt_raises(batch_service):
    """Test that missing prompt raises ValueError."""
    parameters = {
        "repositories": [{"repository_url": "https://github.com/razorpay/test-repo"}]
    }

    with pytest.raises(ValueError) as exc:
        batch_service._validate_batch_parameters(parameters)

    assert "prompt" in str(exc.value).lower()


def test_batch_empty_prompt_raises(batch_service):
    """Test that empty/whitespace prompt raises ValueError."""
    parameters = {
        "prompt": "   ",
        "repositories": [{"repository_url": "https://github.com/razorpay/test-repo"}]
    }

    with pytest.raises(ValueError) as exc:
        batch_service._validate_batch_parameters(parameters)

    assert "prompt" in str(exc.value).lower()


def test_batch_missing_repositories_raises(batch_service):
    """Test that missing repositories parameter raises ValueError."""
    parameters = {
        "prompt": "Test task"
    }

    with pytest.raises(ValueError) as exc:
        batch_service._validate_batch_parameters(parameters)

    assert "repositories" in str(exc.value).lower()


def test_batch_empty_repositories_raises(batch_service):
    """Test that empty repositories list raises ValueError."""
    parameters = {
        "prompt": "Test task",
        "repositories": []
    }

    with pytest.raises(ValueError) as exc:
        batch_service._validate_batch_parameters(parameters)

    # Empty list is falsy in Python, so triggers the "not repositories" condition
    # which raises "Missing required parameter: repositories (must be a list)"
    assert "repositories" in str(exc.value).lower()
    assert "must be a list" in str(exc.value).lower()


def test_batch_repositories_not_list_raises(batch_service):
    """Test that non-list repositories parameter raises ValueError."""
    parameters = {
        "prompt": "Test task",
        "repositories": "not-a-list"
    }

    with pytest.raises(ValueError) as exc:
        batch_service._validate_batch_parameters(parameters)

    assert "must be a list" in str(exc.value).lower()


def test_batch_exactly_one_repository_passes(batch_service):
    """Test that exactly 1 repository passes validation."""
    parameters = {
        "prompt": "Test task",
        "repositories": [{"repository_url": "https://github.com/razorpay/test-repo"}]
    }

    # Should not raise
    batch_service._validate_batch_parameters(parameters)


def test_batch_exactly_fifty_repositories_passes(batch_service):
    """Test that exactly 50 repositories passes validation (boundary test)."""
    repositories = [
        {"repository_url": f"https://github.com/razorpay/repo-{i}"}
        for i in range(50)
    ]

    parameters = {
        "prompt": "Test task",
        "repositories": repositories
    }

    # Should not raise
    batch_service._validate_batch_parameters(parameters)


def test_batch_forty_nine_repositories_passes(batch_service):
    """Test that 49 repositories passes validation (below boundary)."""
    repositories = [
        {"repository_url": f"https://github.com/razorpay/repo-{i}"}
        for i in range(49)
    ]

    parameters = {
        "prompt": "Test task",
        "repositories": repositories
    }

    # Should not raise
    batch_service._validate_batch_parameters(parameters)


def test_batch_fifty_one_repositories_raises(batch_service):
    """Test that 51 repositories raises ValueError (above boundary)."""
    repositories = [
        {"repository_url": f"https://github.com/razorpay/repo-{i}"}
        for i in range(51)
    ]

    parameters = {
        "prompt": "Test task",
        "repositories": repositories
    }

    with pytest.raises(ValueError) as exc:
        batch_service._validate_batch_parameters(parameters)

    error_msg = str(exc.value).lower()
    assert "too many repositories" in error_msg
    assert "51" in str(exc.value)
    assert "maximum allowed: 50" in str(exc.value).lower()


def test_batch_hundred_repositories_raises(batch_service):
    """Test that 100 repositories raises ValueError (well above limit)."""
    repositories = [
        {"repository_url": f"https://github.com/razorpay/repo-{i}"}
        for i in range(100)
    ]

    parameters = {
        "prompt": "Test task",
        "repositories": repositories
    }

    with pytest.raises(ValueError) as exc:
        batch_service._validate_batch_parameters(parameters)

    error_msg = str(exc.value).lower()
    assert "too many repositories" in error_msg
    assert "100" in str(exc.value)
    assert "maximum allowed: 50" in str(exc.value).lower()


def test_batch_parse_repositories_with_branches(batch_service):
    """Test parsing repositories with branch specifications."""
    repositories_data = [
        {"repository_url": "https://github.com/razorpay/repo1", "branch": "feature-1"},
        {"repository_url": "https://github.com/razorpay/repo2", "branch": "develop"},
        {"repository_url": "https://github.com/razorpay/repo3"}  # No branch
    ]

    parsed = batch_service._parse_repositories(repositories_data)

    assert len(parsed) == 3
    assert parsed[0].repository_url == "https://github.com/razorpay/repo1"
    assert parsed[0].branch == "feature-1"
    assert parsed[1].repository_url == "https://github.com/razorpay/repo2"
    assert parsed[1].branch == "develop"
    assert parsed[2].repository_url == "https://github.com/razorpay/repo3"
    assert parsed[2].branch is None


def test_batch_parse_repositories_missing_url_raises(batch_service):
    """Test that missing repository_url in repository data raises ValueError."""
    repositories_data = [
        {"repository_url": "https://github.com/razorpay/repo1"},
        {"branch": "feature-1"}  # Missing repository_url
    ]

    with pytest.raises(ValueError) as exc:
        batch_service._parse_repositories(repositories_data)

    assert "repository 2" in str(exc.value).lower()
    assert "repository_url" in str(exc.value).lower()


def test_batch_parse_repositories_not_dict_raises(batch_service):
    """Test that non-dict repository entry raises ValueError."""
    repositories_data = [
        {"repository_url": "https://github.com/razorpay/repo1"},
        "not-a-dict"
    ]

    with pytest.raises(ValueError) as exc:
        batch_service._parse_repositories(repositories_data)

    assert "repository 2" in str(exc.value).lower()
    assert "must be a dictionary" in str(exc.value).lower()


def test_batch_valid_parameters_all_checks(batch_service):
    """Test that valid parameters pass all validation checks."""
    parameters = {
        "prompt": "Update dependencies to latest versions",
        "repositories": [
            {"repository_url": "https://github.com/razorpay/api", "branch": "feature-update"},
            {"repository_url": "https://github.com/razorpay/web"},
            {"repository_url": "https://github.com/razorpay/mobile", "branch": "develop"}
        ]
    }

    # Should not raise
    batch_service._validate_batch_parameters(parameters)

    # Parse should work
    parsed = batch_service._parse_repositories(parameters["repositories"])
    assert len(parsed) == 3


def test_batch_description_property(batch_service):
    """Test that service has proper description."""
    description = batch_service.description
    assert isinstance(description, str)
    assert len(description) > 0
    assert "batch" in description.lower()


def test_batch_service_initialization():
    """Test that batch service initializes correctly."""
    service = AutonomousAgentBatchService()
    assert service is not None
    assert hasattr(service, '_validate_batch_parameters')
    assert hasattr(service, '_parse_repositories')
    assert hasattr(service, 'execute')


# Boundary tests for the new 50-repository limit
class TestBatchLimit50Boundary:
    """Comprehensive boundary tests for the new 50-repository limit."""

    @pytest.fixture
    def service(self):
        return AutonomousAgentBatchService()

    def test_limit_minus_two(self, service):
        """Test 48 repositories (limit - 2)."""
        params = {
            "prompt": "Test",
            "repositories": [{"repository_url": f"https://github.com/razorpay/r{i}"} for i in range(48)]
        }
        service._validate_batch_parameters(params)  # Should not raise

    def test_limit_minus_one(self, service):
        """Test 49 repositories (limit - 1)."""
        params = {
            "prompt": "Test",
            "repositories": [{"repository_url": f"https://github.com/razorpay/r{i}"} for i in range(49)]
        }
        service._validate_batch_parameters(params)  # Should not raise

    def test_exact_limit(self, service):
        """Test exactly 50 repositories (at limit)."""
        params = {
            "prompt": "Test",
            "repositories": [{"repository_url": f"https://github.com/razorpay/r{i}"} for i in range(50)]
        }
        service._validate_batch_parameters(params)  # Should not raise

    def test_limit_plus_one(self, service):
        """Test 51 repositories (limit + 1)."""
        params = {
            "prompt": "Test",
            "repositories": [{"repository_url": f"https://github.com/razorpay/r{i}"} for i in range(51)]
        }
        with pytest.raises(ValueError) as exc:
            service._validate_batch_parameters(params)
        assert "maximum allowed: 50" in str(exc.value).lower()

    def test_limit_plus_two(self, service):
        """Test 52 repositories (limit + 2)."""
        params = {
            "prompt": "Test",
            "repositories": [{"repository_url": f"https://github.com/razorpay/r{i}"} for i in range(52)]
        }
        with pytest.raises(ValueError) as exc:
            service._validate_batch_parameters(params)
        assert "maximum allowed: 50" in str(exc.value).lower()
