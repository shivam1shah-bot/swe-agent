"""
GitHub Bot Constants.

Defines constants for GitHub bot names to ensure consistent usage across codebase.
"""

from enum import Enum


class GitHubBot(str, Enum):
    """GitHub bot identifiers."""

    SWE_AGENT = "rzp_swe_agent_app"
    CODE_REVIEW = "rzp_code_review"


# Default bot for backward compatibility
DEFAULT_BOT = GitHubBot.SWE_AGENT


def get_all_bots() -> list[GitHubBot]:
    """
    Get list of all registered GitHub bots.

    Returns:
        List of all GitHubBot enum members

    Example:
        >>> bots = get_all_bots()
        >>> for bot in bots:
        ...     print(bot.value)
        rzp_swe_agent_app
        rzp_code_review
    """
    return list(GitHubBot)


def get_bot_values() -> list[str]:
    """
    Get list of all registered bot value strings.

    Returns:
        List of bot identifier strings

    Example:
        >>> get_bot_values()
        ['rzp_swe_agent_app', 'rzp_code_review']
    """
    return [bot.value for bot in GitHubBot]
