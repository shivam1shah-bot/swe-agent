"""
GitHub Provider package for simplified GitHub authentication.

This package provides simplified GitHub authentication using:
- GitHubAuthService: For token consumption by API pods
- GitHubAuthBootstrap: For application startup integration  
- Task-based token refresh: Handled by worker processes
"""

# Export main components
from .auth_service import GitHubAuthService
from .bootstrap import initialize_github_auth, get_bootstrap_status
from .exceptions import (
    GitHubError,
    GitHubAuthenticationError, 
    GitHubCLIError,
    GitHubTokenError,
    GitHubAppError
)

__all__ = [
    'GitHubAuthService',
    'initialize_github_auth', 
    'get_bootstrap_status',
    'GitHubError',
    'GitHubAuthenticationError',
    'GitHubCLIError', 
    'GitHubTokenError',
    'GitHubAppError'
] 