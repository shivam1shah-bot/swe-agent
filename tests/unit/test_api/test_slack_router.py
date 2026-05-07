"""
Unit tests for the Slack router.
"""

import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# _help_text
# ---------------------------------------------------------------------------

class TestHelpText:
    def test_help_text_default_command(self):
        from src.api.routers.slack import _help_text
        text = _help_text()
        assert "/vyom" in text
        assert "run" in text
        assert "ticket" in text
        assert "status" in text

    def test_help_text_custom_command(self):
        from src.api.routers.slack import _help_text
        text = _help_text("/custom")
        assert "/custom" in text

    def test_help_text_contains_examples(self):
        from src.api.routers.slack import _help_text
        text = _help_text("/vyom")
        assert "repo:" in text
        assert "skills:" in text


# ---------------------------------------------------------------------------
# _parse_slash_command
# ---------------------------------------------------------------------------

class TestParseSlashCommand:
    def test_parse_run_with_repo(self):
        from src.api.routers.slack import _parse_slash_command
        result = _parse_slash_command("run fix bug repo:https://github.com/razorpay/api")
        assert result["action"] == "run"
        assert result["repository_url"] == "https://github.com/razorpay/api"
        assert "fix bug" in result["description"]

    def test_parse_help(self):
        from src.api.routers.slack import _parse_slash_command
        result = _parse_slash_command("help")
        assert result["action"] == "help"

    def test_parse_status(self):
        from src.api.routers.slack import _parse_slash_command
        result = _parse_slash_command("status abc-123")
        assert result["action"] == "status"
        assert result["task_id"] == "abc-123"

    def test_parse_ticket(self):
        from src.api.routers.slack import _parse_slash_command
        result = _parse_slash_command("ticket:ISS-123 skills:python-code-review")
        assert result["action"] == "ticket"
        assert result["ticket_id"] == "ISS-123"
        assert "python-code-review" in result["skills"]

    def test_parse_ticket_multiple_skills(self):
        from src.api.routers.slack import _parse_slash_command
        result = _parse_slash_command("ticket:ISS-456 skills:skill-a,skill-b")
        assert result["action"] == "ticket"
        assert "skill-a" in result["skills"]
        assert "skill-b" in result["skills"]

    def test_parse_unknown_command(self):
        from src.api.routers.slack import _parse_slash_command
        result = _parse_slash_command("invalidcmd")
        assert result["action"] == "unknown"

    def test_parse_empty_string(self):
        from src.api.routers.slack import _parse_slash_command
        result = _parse_slash_command("")
        assert result["action"] in ("help", "unknown", "run")


# ---------------------------------------------------------------------------
# _help_text alias
# ---------------------------------------------------------------------------

class TestHelpTextAlias:
    def test_help_text_alias_exists(self):
        from src.api.routers.slack import _HELP_TEXT
        assert isinstance(_HELP_TEXT, str)
        assert len(_HELP_TEXT) > 0
