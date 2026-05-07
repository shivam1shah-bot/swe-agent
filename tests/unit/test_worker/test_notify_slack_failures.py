"""
Unit tests for silent-failure detection in TaskProcessor.

Covers two levels:
1. _extract_inner_failure — pure unit tests on the helper, no I/O
2. _notify_slack — integration-style tests verifying the Slack text
   that would be posted, with all external I/O mocked.
"""

import sys
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Inject a mock `requests` module before any test imports tasks.py
# (tasks.py imports `requests` locally inside _notify_slack)
# ---------------------------------------------------------------------------
_mock_requests = MagicMock()
sys.modules.setdefault("requests", _mock_requests)


# ---------------------------------------------------------------------------
# Unit tests for _extract_inner_failure (no I/O, pure logic)
# ---------------------------------------------------------------------------

class TestExtractInnerFailure:
    """Direct unit tests for the _extract_inner_failure static method."""

    def _extract(self, result):
        from src.worker.tasks import TaskProcessor
        return TaskProcessor._extract_inner_failure(result)

    # --- genuine successes → None ---

    def test_returns_none_for_genuine_success(self):
        assert self._extract({"success": True, "result": {"success": True}}) is None

    def test_returns_none_when_result_key_missing(self):
        assert self._extract({"success": True}) is None

    def test_returns_none_when_inner_result_not_a_dict(self):
        assert self._extract({"success": True, "result": "text"}) is None

    def test_returns_none_when_no_success_key_in_inner(self):
        # missing 'success' key defaults to True
        assert self._extract({"success": True, "result": {"status": "ok"}}) is None

    # --- Path 1: result['result']['success'] == False ---

    def test_path1_returns_message(self):
        result = {"success": True, "result": {"success": False, "message": "Auth failed"}}
        assert self._extract(result) == "Auth failed"

    def test_path1_falls_back_to_error_key(self):
        result = {"success": True, "result": {"success": False, "error": "Timeout"}}
        assert self._extract(result) == "Timeout"

    def test_path1_generic_fallback(self):
        result = {"success": True, "result": {"success": False}}
        assert self._extract(result) == "Task failed internally"

    # --- Path 2: result['result']['agent_result']['success'] == False ---

    def test_path2_agent_result_error(self):
        result = {
            "success": True,
            "result": {
                "status": "completed",
                "message": "Clean slate completed",
                "agent_result": {
                    "success": False,
                    "error": "Prompt injection detected",
                },
            },
        }
        assert self._extract(result) == "Prompt injection detected"

    def test_path2_agent_result_falls_back_to_message(self):
        result = {
            "success": True,
            "result": {
                "message": "Parent message",
                "agent_result": {"success": False},  # no error/message
            },
        }
        assert self._extract(result) == "Parent message"

    def test_path2_exact_task_727dd1f2_structure(self):
        """Regression test for the real failing task structure."""
        result = {
            "success": True,
            "result": {
                "status": "completed",
                "message": "Clean slate autonomous agent task completed",
                "agent_result": {
                    "success": False,
                    "error": "Invalid prompt: Potential prompt injection detected. Request blocked for security.",
                },
            },
        }
        msg = self._extract(result)
        assert msg is not None
        assert "prompt injection" in msg.lower()

    def test_path2_agent_result_success_not_flagged(self):
        result = {
            "success": True,
            "result": {"agent_result": {"success": True}},
        }
        assert self._extract(result) is None

    # --- Path 3: Claude Code is_error in raw_response ---

    def test_path3_is_error_true(self):
        result = {
            "success": True,
            "result": {
                "success": True,
                "result": {
                    "result": "context limit exceeded",
                    "raw_response": {"is_error": True, "result": "context limit exceeded"},
                },
            },
        }
        assert self._extract(result) == "context limit exceeded"

    def test_path3_is_error_false_not_flagged(self):
        result = {
            "success": True,
            "result": {
                "success": True,
                "result": {"raw_response": {"is_error": False}},
            },
        }
        assert self._extract(result) is None

    def test_path3_truncates_long_message(self):
        long_msg = "x" * 600
        result = {
            "success": True,
            "result": {
                "success": True,
                "result": {
                    "result": long_msg,
                    "raw_response": {"is_error": True, "result": long_msg},
                },
            },
        }
        msg = self._extract(result)
        assert msg is not None
        assert len(msg) <= 500


# ---------------------------------------------------------------------------
# Helpers for _notify_slack integration tests
# ---------------------------------------------------------------------------

def _make_processor():
    """Return a TaskProcessor with heavy deps mocked."""
    with (
        patch("src.worker.tasks.AutonomousAgentTool"),
        patch("src.worker.tasks.task_manager"),
        patch("src.worker.tasks.get_config", return_value={"slack": {"bot_token": "xoxb-test"}}),
        patch("src.worker.tasks.DEFAULT_BOT", MagicMock()),
    ):
        from src.worker.tasks import TaskProcessor

        proc = TaskProcessor.__new__(TaskProcessor)
        proc.config = {"slack": {"bot_token": "xoxb-test"}}
        proc.autonomous_agent_tool = MagicMock()
        proc.worker_instance = None
        return proc


def _task_data(channel="C123"):
    return {
        "task_id": "task-001",
        "metadata": {
            "slack_channel_id": channel,
            "slack_thread_ts": "111.000",  # required for post_channel condition
            "slack_thinking_ts": "",
        },
    }


def _run_notify(proc, task_data, result):
    """
    Execute _notify_slack with all I/O mocked; returns list of texts posted.
    """
    posted_texts = []

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": True, "ts": "111.222"}

    def capture_post(url, headers=None, json=None, timeout=None):
        if json and "text" in json:
            posted_texts.append(json["text"])
        return mock_resp

    # Patch requests at sys.modules so the local `import requests` inside _notify_slack sees it
    mock_req_mod = MagicMock()
    mock_req_mod.post.side_effect = capture_post

    # Patch the DB engine used to read slack_notify_channel
    mock_engine = MagicMock()
    mock_conn_ctx = MagicMock()
    mock_conn_ctx.__enter__ = lambda s: mock_conn_ctx
    mock_conn_ctx.__exit__ = MagicMock(return_value=False)
    mock_conn_ctx.execute.return_value.fetchone.return_value = None  # no slack_notify_channel
    mock_engine.connect.return_value = mock_conn_ctx

    with (
        patch.dict(sys.modules, {"requests": mock_req_mod}),
        patch("src.providers.database.connection.get_engine", return_value=mock_engine),
        patch("src.providers.slack.provider.md_to_slack", side_effect=lambda t: t),
    ):
        proc._notify_slack(task_data, result)

    return posted_texts


# ---------------------------------------------------------------------------
# Tests: genuine success → "Task completed!"
# ---------------------------------------------------------------------------

class TestNotifySlackSuccessPath:
    def test_genuine_success_shows_completed_header(self):
        proc = _make_processor()
        result = {
            "success": True,
            "result": {
                "success": True,
                "result": {"content": "All done."},
            },
            "message": "Autonomous agent task completed",
        }
        texts = _run_notify(proc, _task_data(), result)
        assert any(":white_check_mark:" in t for t in texts), (
            f"Expected green header. Got: {texts}"
        )
        assert not any(":x:" in t for t in texts)

    def test_inner_result_without_success_key_is_not_failure(self):
        """Inner dict missing 'success' key defaults True — no false alarm."""
        proc = _make_processor()
        result = {
            "success": True,
            "result": {"result": {"content": "Work done"}},  # no 'success' key
        }
        texts = _run_notify(proc, _task_data(), result)
        assert any(":white_check_mark:" in t for t in texts)


# ---------------------------------------------------------------------------
# Tests: inner failure (success=False inside result['result'])
# ---------------------------------------------------------------------------

class TestNotifySlackInnerFailure:
    def test_inner_success_false_with_message(self):
        proc = _make_processor()
        result = {
            "success": True,
            "result": {
                "success": False,
                "message": "Repository not found: razorpay/unknown-repo",
            },
            "message": "Autonomous agent task completed",
        }
        texts = _run_notify(proc, _task_data(), result)
        assert any(":x:" in t for t in texts), f"Expected failure. Got: {texts}"
        assert any("Repository not found" in t for t in texts), (
            f"Inner message not surfaced: {texts}"
        )

    def test_inner_success_false_with_error_key(self):
        proc = _make_processor()
        result = {
            "success": True,
            "result": {"success": False, "error": "GitHub token expired"},
        }
        texts = _run_notify(proc, _task_data(), result)
        assert any(":x:" in t for t in texts)
        assert any("GitHub token expired" in t for t in texts)

    def test_inner_success_false_generic_fallback(self):
        proc = _make_processor()
        result = {
            "success": True,
            "result": {"success": False},  # no message or error
        }
        texts = _run_notify(proc, _task_data(), result)
        assert any(":x:" in t for t in texts)
        assert any("Task failed internally" in t for t in texts)

    def test_message_prefers_inner_over_outer(self):
        """inner_failure_msg should take precedence over outer result['message']."""
        proc = _make_processor()
        result = {
            "success": True,
            "result": {
                "success": False,
                "message": "Inner specific failure",
            },
            "message": "Generic task message",
        }
        texts = _run_notify(proc, _task_data(), result)
        assert any("Inner specific failure" in t for t in texts)
        assert not any("Generic task message" in t for t in texts)


# ---------------------------------------------------------------------------
# Tests: Claude Code is_error=True in raw_response
# ---------------------------------------------------------------------------

class TestNotifySlackAgentResultPath:
    """
    agents_catalogue tasks wrap the failure inside result['result']['agent_result'].
    This is the exact structure from task 727dd1f2.
    """

    def test_agent_result_failure_surfaced(self):
        proc = _make_processor()
        # Exact structure from task 727dd1f2-d252-4f72-a2cd-700072e692ef
        result = {
            "success": True,
            "result": {
                "status": "completed",
                "message": "Clean slate autonomous agent task completed",
                "agent_result": {
                    "success": False,
                    "error": "Invalid prompt: Potential prompt injection detected. Request blocked for security.",
                    "working_dir": "/tmp/workspace",
                },
                "metadata": {"task_id": "727dd1f2"},
            },
            "message": "Agents catalogue execution completed for autonomous-agent-clean-slate",
        }
        texts = _run_notify(proc, _task_data(), result)
        assert any(":x:" in t for t in texts), f"Expected failure header. Got: {texts}"
        assert any("prompt injection" in t.lower() for t in texts), (
            f"Expected error detail in Slack message. Got: {texts}"
        )

    def test_agent_result_success_not_flagged(self):
        proc = _make_processor()
        result = {
            "success": True,
            "result": {
                "status": "completed",
                "agent_result": {"success": True, "result": {"content": "Done."}},
            },
        }
        texts = _run_notify(proc, _task_data(), result)
        assert any(":white_check_mark:" in t for t in texts)

    def test_agent_result_missing_success_key_not_flagged(self):
        proc = _make_processor()
        result = {
            "success": True,
            "result": {
                "agent_result": {},  # no success key → defaults True
            },
        }
        texts = _run_notify(proc, _task_data(), result)
        assert any(":white_check_mark:" in t for t in texts)


class TestNotifySlackClaudeIsError:
    def test_is_error_true_triggers_failure(self):
        proc = _make_processor()
        result = {
            "success": True,
            "result": {
                "success": True,
                "result": {
                    "type": "claude_code_response",
                    "result": "Claude hit an error: context limit exceeded",
                    "raw_response": {
                        "type": "result",
                        "subtype": "error_during_execution",
                        "is_error": True,
                        "result": "Claude hit an error: context limit exceeded",
                    },
                },
            },
        }
        texts = _run_notify(proc, _task_data(), result)
        assert any(":x:" in t for t in texts), f"Expected failure. Got: {texts}"
        assert any("context limit exceeded" in t for t in texts)

    def test_is_error_false_no_failure(self):
        proc = _make_processor()
        result = {
            "success": True,
            "result": {
                "success": True,
                "result": {
                    "type": "claude_code_response",
                    "result": "Successfully completed all changes.",
                    "raw_response": {"is_error": False, "result": "Done."},
                },
            },
        }
        texts = _run_notify(proc, _task_data(), result)
        assert any(":white_check_mark:" in t for t in texts)

    def test_is_error_missing_means_no_failure(self):
        """raw_response without is_error key → no false positive."""
        proc = _make_processor()
        result = {
            "success": True,
            "result": {
                "success": True,
                "result": {
                    "type": "claude_code_response",
                    "result": "Done.",
                    "raw_response": {"type": "result"},  # no is_error key
                },
            },
        }
        texts = _run_notify(proc, _task_data(), result)
        assert any(":white_check_mark:" in t for t in texts)


# ---------------------------------------------------------------------------
# Tests: explicit outer failure (success=False)
# ---------------------------------------------------------------------------

class TestNotifySlackOuterFailure:
    def test_outer_failure_uses_error_key(self):
        proc = _make_processor()
        result = {
            "success": False,
            "error": "Missing required parameter: repository_url",
        }
        texts = _run_notify(proc, _task_data(), result)
        assert any(":x:" in t for t in texts)
        assert any("Missing required parameter" in t for t in texts)

    def test_outer_failure_falls_back_to_message_key(self):
        proc = _make_processor()
        result = {
            "success": False,
            "message": "Task cancelled by user",
        }
        texts = _run_notify(proc, _task_data(), result)
        assert any(":x:" in t for t in texts)
        assert any("Task cancelled by user" in t for t in texts)

    def test_outer_failure_unknown_error_fallback(self):
        proc = _make_processor()
        result = {"success": False}
        texts = _run_notify(proc, _task_data(), result)
        assert any(":x:" in t for t in texts)
        assert any("Unknown error" in t for t in texts)
