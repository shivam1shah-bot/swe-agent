"""
Test-specific configuration settings.
"""
import os
from pathlib import Path

# Test directories
TEST_ROOT = Path(__file__).parent.parent
FIXTURES_DIR = TEST_ROOT / "fixtures"
MOCK_DATA_DIR = TEST_ROOT / "fixtures" / "mock_responses"

# Test database settings
TEST_DATABASE_URL = "sqlite:///:memory:"

# Mock service URLs
MOCK_GITHUB_API_URL = "https://api.github.com"
MOCK_WORKER_URL = "http://localhost:8080"

# Test timeouts
TEST_TIMEOUT = 30
INTEGRATION_TEST_TIMEOUT = 60
E2E_TEST_TIMEOUT = 120

# Feature flags for tests
ENABLE_GITHUB_TESTS = os.getenv("ENABLE_GITHUB_TESTS", "false").lower() == "true"
ENABLE_PERFORMANCE_TESTS = os.getenv("ENABLE_PERFORMANCE_TESTS", "false").lower() == "true" 