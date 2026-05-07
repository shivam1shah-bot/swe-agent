"""
GitHub Provider exceptions.
"""


class GitHubError(Exception):
    """Base exception for GitHub-related errors."""
    pass


class GitHubAuthenticationError(GitHubError):
    """Exception raised when GitHub authentication fails."""
    pass


class GitHubCLIError(GitHubError):
    """Exception raised when GitHub CLI command fails."""
    
    def __init__(self, message: str, command: str = None, returncode: int = None, stderr: str = None):
        super().__init__(message)
        self.command = command
        self.returncode = returncode
        self.stderr = stderr


class GitHubTokenError(GitHubError):
    """Exception raised when GitHub token operations fail."""
    pass


class GitHubSessionExpiredError(GitHubError):
    """Exception raised when GitHub session token has expired."""
    pass


class GitHubAppError(GitHubError):
    """Exception raised when GitHub App authentication fails."""
    pass 