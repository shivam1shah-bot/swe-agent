"""
Tests for GitHub Auth Service Repository Visibility Function
"""

import pytest
from unittest.mock import patch


class TestGitHubAuthRepositoryVisibility:
    """Test repository visibility checking in GitHub auth service."""

    @pytest.fixture
    def mock_github_auth_service(self):
        """Create a mocked GitHub auth service for testing."""
        with patch('src.providers.github.auth_service.get_redis_client'), \
             patch('src.providers.github.auth_service.get_config'):
            from src.providers.github.auth_service import GitHubAuthService
            return GitHubAuthService()

    def test_parse_github_url_https_format(self, mock_github_auth_service):
        """Test parsing HTTPS GitHub URLs."""
        owner, repo = mock_github_auth_service._parse_github_url("https://github.com/owner/repo")
        assert owner == "owner"
        assert repo == "repo"
        
        # Test with .git suffix
        owner, repo = mock_github_auth_service._parse_github_url("https://github.com/owner/repo.git")
        assert owner == "owner"
        assert repo == "repo"
        
        # Test with trailing slash
        owner, repo = mock_github_auth_service._parse_github_url("https://github.com/owner/repo/")
        assert owner == "owner"
        assert repo == "repo"

    def test_parse_github_url_ssh_format(self, mock_github_auth_service):
        """Test parsing SSH GitHub URLs."""
        owner, repo = mock_github_auth_service._parse_github_url("git@github.com:owner/repo.git")
        assert owner == "owner"
        assert repo == "repo"
        
        # Test without .git suffix
        owner, repo = mock_github_auth_service._parse_github_url("git@github.com:owner/repo")
        assert owner == "owner"
        assert repo == "repo"

    def test_parse_github_url_invalid_format(self, mock_github_auth_service):
        """Test parsing invalid GitHub URLs."""
        owner, repo = mock_github_auth_service._parse_github_url("invalid-url")
        assert owner is None
        assert repo is None
        
        owner, repo = mock_github_auth_service._parse_github_url("https://gitlab.com/owner/repo")
        assert owner is None
        assert repo is None
        
        owner, repo = mock_github_auth_service._parse_github_url("https://github.com")
        assert owner is None
        assert repo is None

    def test_parse_github_url_real_examples(self, mock_github_auth_service):
        """Test parsing real GitHub repository URLs."""
        # Microsoft VS Code
        owner, repo = mock_github_auth_service._parse_github_url("https://github.com/microsoft/vscode")
        assert owner == "microsoft"
        assert repo == "vscode"
        
        # Facebook React
        owner, repo = mock_github_auth_service._parse_github_url("git@github.com:facebook/react.git")
        assert owner == "facebook"
        assert repo == "react"

    @pytest.mark.asyncio
    async def test_check_repository_visibility_invalid_url(self, mock_github_auth_service):
        """Test checking visibility with invalid URL format."""
        result = await mock_github_auth_service.check_repository_visibility("invalid-url-format")
        
        assert result["success"] is False
        assert "Invalid GitHub repository URL format" in result["error"]

    @pytest.mark.asyncio
    async def test_check_repository_visibility_empty_url(self, mock_github_auth_service):
        """Test checking visibility with empty URL."""
        result = await mock_github_auth_service.check_repository_visibility("")
        
        assert result["success"] is False
        assert "Invalid GitHub repository URL format" in result["error"]

    @pytest.mark.asyncio  
    async def test_check_repository_visibility_gitlab_url(self, mock_github_auth_service):
        """Test checking visibility with non-GitHub URL."""
        result = await mock_github_auth_service.check_repository_visibility("https://gitlab.com/owner/repo")
        
        assert result["success"] is False
        assert "Invalid GitHub repository URL format" in result["error"]
