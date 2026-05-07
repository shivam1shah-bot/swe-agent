"""
Mock GitHub service for testing.
"""
from unittest.mock import Mock, MagicMock, AsyncMock
from datetime import datetime, timezone, timedelta
import json


class MockGitHubService:
    """Mock GitHub service for testing."""
    
    def __init__(self):
        self.repositories = {}
        self.pull_requests = {}
        self.issues = {}
    
    def get_repository(self, repo_name):
        """Mock get repository."""
        return self.repositories.get(repo_name, {
            "id": 123456,
            "name": repo_name,
            "full_name": f"test-user/{repo_name}",
            "private": False,
            "default_branch": "main"
        })
    
    def get_pull_request(self, repo_name, pr_number):
        """Mock get pull request."""
        key = f"{repo_name}#{pr_number}"
        return self.pull_requests.get(key, {
            "id": 789,
            "number": pr_number,
            "title": "Test PR",
            "state": "open",
            "head": {"sha": "abc123def456"}
        })
    
    def create_pull_request_comment(self, repo_name, pr_number, comment):
        """Mock create PR comment."""
        return {
            "id": 999,
            "body": comment,
            "created_at": "2023-01-01T00:00:00Z"
        }





def create_mock_github_client():
    """Create a mock GitHub client."""
    client = Mock()
    service = MockGitHubService()
    
    client.get_repo.side_effect = service.get_repository
    client.get_pull_request.side_effect = service.get_pull_request
    client.create_comment.side_effect = service.create_pull_request_comment
    
    return client


 