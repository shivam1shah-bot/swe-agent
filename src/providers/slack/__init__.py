"""
Slack Provider package.

Outbound messaging via Slack Web API + inbound request signature verification.
"""

from .client import SlackClient
from .provider import initialize_slack, get_slack_client, is_slack_enabled
from .exceptions import SlackError, SlackAuthError, SlackAPIError, SlackNotConfiguredError

__all__ = [
    "SlackClient",
    "initialize_slack",
    "get_slack_client",
    "is_slack_enabled",
    "SlackError",
    "SlackAuthError",
    "SlackAPIError",
    "SlackNotConfiguredError",
]
