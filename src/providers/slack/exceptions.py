"""Slack provider exceptions."""


class SlackError(Exception):
    """Base exception for Slack provider errors."""


class SlackAuthError(SlackError):
    """Raised when Slack credentials are missing or invalid."""


class SlackAPIError(SlackError):
    """Raised when the Slack Web API returns ok=false."""

    def __init__(self, message: str, status_code: int = None, response: dict = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response = response or {}


class SlackNotConfiguredError(SlackError):
    """Raised when get_slack_client() is called before initialization."""
