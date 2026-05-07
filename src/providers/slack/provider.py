"""
Slack provider singleton.

Call initialize_slack() once at startup. Use get_slack_client() everywhere else.
"""

from __future__ import annotations

import logging
from typing import Optional

from .client import SlackClient
from .exceptions import SlackNotConfiguredError

logger = logging.getLogger(__name__)

_client: Optional[SlackClient] = None


def initialize_slack(config: dict) -> bool:
    """
    Initialize the global Slack client from application config.

    Expected TOML shape:
        [slack]
        enabled = true
        bot_token = "xoxb-..."
        signing_secret = "abc123..."

    Returns:
        True if initialized, False if disabled or credentials missing (non-fatal).
    """
    global _client

    slack_cfg = config.get("slack", {})

    if not slack_cfg.get("enabled", False):
        logger.info("Slack integration disabled (slack.enabled = false)")
        return False

    bot_token = slack_cfg.get("bot_token", "").strip()
    signing_secret = slack_cfg.get("signing_secret", "").strip()

    if not bot_token or not signing_secret:
        logger.warning("Slack enabled but bot_token / signing_secret not set — skipping init")
        return False

    _client = SlackClient(bot_token=bot_token, signing_secret=signing_secret)
    logger.info("Slack client initialized")
    return True


def get_slack_client() -> SlackClient:
    """
    Return the initialized Slack client.

    Raises:
        SlackNotConfiguredError: If initialize_slack() was not called or Slack is disabled.
    """
    if _client is None:
        raise SlackNotConfiguredError(
            "Slack client not initialized. Set slack.enabled = true and provide credentials."
        )
    return _client


def is_slack_enabled() -> bool:
    """Return True if the Slack client has been successfully initialized."""
    return _client is not None


def md_to_slack(text: str) -> str:
    """
    Convert Markdown to Slack mrkdwn format.

    Handles patterns produced by Claude:
      ## Heading        → *Heading*
      **bold**          → *bold*
      [label](url)      → <url|label>
      * bullet          → • bullet
      ---               → (removed)
      :emoji:           → kept as-is
    """
    import re

    # Step 1: Bullet points "* item" → "• item" (do before bold conversion)
    text = re.sub(r'^\* ', '• ', text, flags=re.MULTILINE)

    # Step 2: Headers (h1–h4) → *bold*
    text = re.sub(r'^#{1,4}\s+(.+)$', r'*\1*', text, flags=re.MULTILINE)

    # Step 3a: Strip * wrappers from spans that contain a URL so the asterisks
    # never become part of the URL itself.
    # e.g. **PR: https://github.com/.../pull/8**  →  PR: https://github.com/.../pull/8
    #      *https://github.com/.../pull/8*        →  https://github.com/.../pull/8
    text = re.sub(r'\*{1,2}([^*\n]*?https://[^\s*>\)]+[^*\n]*?)\*{1,2}', r'\1', text)

    # Step 3: Bold **text** → *text*
    text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)

    # Step 4: Fix malformed patterns that Claude sometimes emits.
    # First remove trailing "**" artifacts e.g. "*3. *Git Operations**" → "*3. *Git Operations"
    text = text.replace('**', '')
    # Then remove any stray * that appears mid-sentence inside an existing bold span
    # e.g. "*3. *Git Operations" → "*3. Git Operations"
    text = re.sub(r'(\*[^*\n]+?)\*(?=[A-Za-z])', r'\1', text)

    # Step 5: Links [label](url) → <url|label>
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<\2|\1>', text)

    # Step 6: Horizontal rules
    text = re.sub(r'^-{3,}$', '', text, flags=re.MULTILINE)

    # Step 7: Per-line cleanup — remove unpaired * that Slack can't render as bold
    def fix_unpaired_bold(line: str) -> str:
        # Count non-adjacent * markers (bold boundaries)
        stars = [i for i, c in enumerate(line) if c == '*']
        if len(stars) % 2 != 0:
            # Odd count → find and remove the lone unpaired one
            # Prefer removing a leading * with no closing partner on this line
            if line.startswith('*') and not line.endswith('*'):
                return line[1:]
            # Otherwise remove the last stray *
            last = line.rfind('*')
            return line[:last] + line[last + 1:]
        return line

    text = '\n'.join(fix_unpaired_bold(l) for l in text.split('\n'))

    # Step 8: Collapse 3+ blank lines to 2
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()
