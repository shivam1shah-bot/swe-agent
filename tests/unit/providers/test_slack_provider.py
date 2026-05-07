"""
Unit tests for Slack provider utilities.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestMdToSlack:
    def test_converts_headers(self):
        from src.providers.slack.provider import md_to_slack
        result = md_to_slack("# Header")
        assert "#" not in result
        assert "Header" in result

    def test_converts_bold(self):
        from src.providers.slack.provider import md_to_slack
        result = md_to_slack("**bold text**")
        assert "*bold text*" in result

    def test_converts_links(self):
        from src.providers.slack.provider import md_to_slack
        result = md_to_slack("[click here](https://example.com)")
        assert "https://example.com" in result

    def test_plain_text_unchanged(self):
        from src.providers.slack.provider import md_to_slack
        result = md_to_slack("hello world")
        assert "hello world" in result

    def test_empty_string(self):
        from src.providers.slack.provider import md_to_slack
        result = md_to_slack("")
        assert result == ""

    def test_code_block_preserved(self):
        from src.providers.slack.provider import md_to_slack
        result = md_to_slack("```python\ncode\n```")
        assert "code" in result


class TestIsSlackEnabled:
    def test_disabled_when_no_token(self):
        with patch("src.providers.config_loader.get_config", return_value={"slack": {"bot_token": "", "signing_secret": ""}}):
            from src.providers.slack.provider import is_slack_enabled
            assert is_slack_enabled() is False

    def test_is_slack_enabled_returns_bool(self):
        from src.providers.slack.provider import is_slack_enabled
        assert isinstance(is_slack_enabled(), bool)


class TestSlackExceptions:
    def test_slack_not_configured_error(self):
        from src.providers.slack.exceptions import SlackNotConfiguredError
        err = SlackNotConfiguredError("not configured")
        assert "not configured" in str(err)

    def test_slack_error_base(self):
        from src.providers.slack.exceptions import SlackError
        err = SlackError("base error")
        assert "base error" in str(err)
