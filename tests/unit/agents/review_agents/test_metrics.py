"""
Unit tests for the metrics module.

Tests cover:
- MCP call recording with proper label extraction
- Skills usage recording
- User activity recording
- Execution completion recording
- Backward compatibility aliases
- Edge cases (empty inputs, malformed data)
"""

import pytest
from unittest.mock import patch, MagicMock

from src.agents.review_agents.metrics import (
    record_mcp_calls,
    record_skills_usage,
    record_user_activity,
    record_execution_completion,
    record_review_completion,
    record_auto_approve_decision,
    record_tool_usage,
    initialize_plugin_metrics,
    initialize_review_metrics,
)


class TestRecordMcpCalls:
    """Tests for record_mcp_calls function."""

    def test_records_valid_mcp_calls(self):
        """Test recording valid MCP tool calls."""
        mcp_calls = [
            {"tool_name": "mcp__github__get_pr"},
            {"tool_name": "mcp__github__list_files"},
            {"tool_name": "mcp__coralogix__search_logs"},
        ]

        with patch(
            "src.agents.review_agents.metrics.MCP_TOOL_CALLS_TOTAL"
        ) as mock_tool_counter, patch(
            "src.agents.review_agents.metrics.MCP_SERVER_USAGE_TOTAL"
        ) as mock_server_counter:
            mock_tool_labels = MagicMock()
            mock_server_labels = MagicMock()
            mock_tool_counter.labels.return_value = mock_tool_labels
            mock_server_counter.labels.return_value = mock_server_labels

            record_mcp_calls(mcp_calls, "razorpay/api")

            # Should have 3 tool calls recorded
            assert mock_tool_counter.labels.call_count == 3
            assert mock_tool_labels.inc.call_count == 3

            # Should have 3 server usage calls (one per call)
            assert mock_server_counter.labels.call_count == 3

    def test_parses_mcp_tool_name_correctly(self):
        """Test that MCP tool names are parsed into server and tool."""
        mcp_calls = [{"tool_name": "mcp__blade-mcp__get_component_docs"}]

        with patch(
            "src.agents.review_agents.metrics.MCP_TOOL_CALLS_TOTAL"
        ) as mock_counter:
            mock_labels = MagicMock()
            mock_counter.labels.return_value = mock_labels

            record_mcp_calls(mcp_calls, "razorpay/api", plugin_name="code-review")

            mock_counter.labels.assert_called_with(
                mcp_server="blade-mcp",
                tool_name="get_component_docs",
                repository="razorpay/api",
                plugin_name="code-review",
            )

    def test_skips_non_mcp_tools(self):
        """Test that non-MCP tools are skipped."""
        mcp_calls = [
            {"tool_name": "regular_tool"},
            {"tool_name": "Bash"},
            {"tool_name": "Read"},
        ]

        with patch(
            "src.agents.review_agents.metrics.MCP_TOOL_CALLS_TOTAL"
        ) as mock_counter:
            record_mcp_calls(mcp_calls, "razorpay/api")

            # None should be recorded
            mock_counter.labels.assert_not_called()

    def test_handles_empty_list(self):
        """Test handling of empty MCP calls list."""
        with patch(
            "src.agents.review_agents.metrics.MCP_TOOL_CALLS_TOTAL"
        ) as mock_counter:
            record_mcp_calls([], "razorpay/api")

            mock_counter.labels.assert_not_called()

    def test_handles_none_input(self):
        """Test handling of None input."""
        with patch(
            "src.agents.review_agents.metrics.MCP_TOOL_CALLS_TOTAL"
        ) as mock_counter:
            # Should not raise
            record_mcp_calls(None, "razorpay/api")

            mock_counter.labels.assert_not_called()

    def test_handles_malformed_tool_name(self):
        """Test handling of malformed MCP tool names."""
        mcp_calls = [
            {"tool_name": "mcp__"},  # Missing parts
            {"tool_name": "mcp__server"},  # Only server, no tool
            {},  # No tool_name key
        ]

        with patch(
            "src.agents.review_agents.metrics.MCP_TOOL_CALLS_TOTAL"
        ) as mock_counter:
            record_mcp_calls(mcp_calls, "razorpay/api")

            # None should be recorded (all malformed)
            mock_counter.labels.assert_not_called()


class TestRecordSkillsUsage:
    """Tests for record_skills_usage function."""

    def test_records_skills_usage(self):
        """Test recording skills usage."""
        skills = ["security-review", "code-quality", "testing"]

        with patch(
            "src.agents.review_agents.metrics.SKILLS_INVOCATIONS_TOTAL"
        ) as mock_counter:
            mock_labels = MagicMock()
            mock_counter.labels.return_value = mock_labels

            record_skills_usage(skills, "razorpay/api")

            assert mock_counter.labels.call_count == 3
            assert mock_labels.inc.call_count == 3

    def test_records_with_custom_plugin_name(self):
        """Test recording with custom plugin name."""
        skills = ["blade-review"]

        with patch(
            "src.agents.review_agents.metrics.SKILLS_INVOCATIONS_TOTAL"
        ) as mock_counter:
            mock_labels = MagicMock()
            mock_counter.labels.return_value = mock_labels

            record_skills_usage(skills, "razorpay/dashboard", plugin_name="discover")

            mock_counter.labels.assert_called_with(
                skill_name="blade-review",
                repository="razorpay/dashboard",
                plugin_name="discover",
            )

    def test_handles_empty_list(self):
        """Test handling of empty skills list."""
        with patch(
            "src.agents.review_agents.metrics.SKILLS_INVOCATIONS_TOTAL"
        ) as mock_counter:
            record_skills_usage([], "razorpay/api")

            mock_counter.labels.assert_not_called()

    def test_handles_none_input(self):
        """Test handling of None input."""
        with patch(
            "src.agents.review_agents.metrics.SKILLS_INVOCATIONS_TOTAL"
        ) as mock_counter:
            record_skills_usage(None, "razorpay/api")

            mock_counter.labels.assert_not_called()


class TestRecordUserActivity:
    """Tests for record_user_activity function."""

    def test_records_user_activity(self):
        """Test recording user activity."""
        with patch(
            "src.agents.review_agents.metrics.USER_ACTIVITY_TOTAL"
        ) as mock_counter:
            mock_labels = MagicMock()
            mock_counter.labels.return_value = mock_labels

            record_user_activity("richesh.gupta", "code-review")

            mock_counter.labels.assert_called_with(
                user="richesh.gupta",
                plugin_name="code-review",
            )
            mock_labels.inc.assert_called_once()

    def test_handles_empty_user(self):
        """Test handling of empty user string."""
        with patch(
            "src.agents.review_agents.metrics.USER_ACTIVITY_TOTAL"
        ) as mock_counter:
            record_user_activity("", "code-review")

            mock_counter.labels.assert_not_called()

    def test_handles_none_user(self):
        """Test handling of None user."""
        with patch(
            "src.agents.review_agents.metrics.USER_ACTIVITY_TOTAL"
        ) as mock_counter:
            record_user_activity(None, "code-review")

            mock_counter.labels.assert_not_called()


class TestRecordExecutionCompletion:
    """Tests for record_execution_completion function."""

    def test_records_completion_without_duration(self):
        """Test recording completion without duration."""
        with patch(
            "src.agents.review_agents.metrics.EXECUTIONS_COMPLETED_TOTAL"
        ) as mock_counter, patch(
            "src.agents.review_agents.metrics.EXECUTION_DURATION_SECONDS"
        ) as mock_histogram:
            mock_labels = MagicMock()
            mock_counter.labels.return_value = mock_labels

            record_execution_completion("razorpay/api", "success")

            mock_counter.labels.assert_called_with(
                repository="razorpay/api",
                status="success",
                plugin_name="swe-agent",
            )
            mock_labels.inc.assert_called_once()

            # Duration histogram should not be called
            mock_histogram.labels.assert_not_called()

    def test_records_completion_with_duration(self):
        """Test recording completion with duration."""
        with patch(
            "src.agents.review_agents.metrics.EXECUTIONS_COMPLETED_TOTAL"
        ) as mock_counter, patch(
            "src.agents.review_agents.metrics.EXECUTION_DURATION_SECONDS"
        ) as mock_histogram:
            mock_counter_labels = MagicMock()
            mock_histogram_labels = MagicMock()
            mock_counter.labels.return_value = mock_counter_labels
            mock_histogram.labels.return_value = mock_histogram_labels

            record_execution_completion(
                "razorpay/api", "success", duration_seconds=45.5
            )

            mock_histogram.labels.assert_called_with(
                repository="razorpay/api",
                status="success",
                plugin_name="swe-agent",
            )
            mock_histogram_labels.observe.assert_called_with(45.5)

    def test_records_failure_status(self):
        """Test recording failure status."""
        with patch(
            "src.agents.review_agents.metrics.EXECUTIONS_COMPLETED_TOTAL"
        ) as mock_counter:
            mock_labels = MagicMock()
            mock_counter.labels.return_value = mock_labels

            record_execution_completion("razorpay/api", "failed")

            mock_counter.labels.assert_called_with(
                repository="razorpay/api",
                status="failed",
                plugin_name="swe-agent",
            )


class TestRecordReviewCompletion:
    """Tests for backward compatibility alias record_review_completion."""

    def test_calls_record_execution_completion(self):
        """Test that it delegates to record_execution_completion."""
        with patch(
            "src.agents.review_agents.metrics.record_execution_completion"
        ) as mock_fn:
            record_review_completion("razorpay/api", "success", duration_seconds=30.0)

            mock_fn.assert_called_with(
                "razorpay/api", "success", 30.0, "swe-agent"
            )


class TestRecordToolUsage:
    """Tests for record_tool_usage convenience function."""

    def test_records_both_mcp_and_skills(self):
        """Test recording both MCP calls and skills."""
        mcp_calls = [{"tool_name": "mcp__github__get_pr"}]
        skills = ["security-review"]

        with patch(
            "src.agents.review_agents.metrics.record_mcp_calls"
        ) as mock_mcp, patch(
            "src.agents.review_agents.metrics.record_skills_usage"
        ) as mock_skills:
            record_tool_usage(mcp_calls, skills, "razorpay/api")

            mock_mcp.assert_called_once_with(mcp_calls, "razorpay/api")
            mock_skills.assert_called_once_with(skills, "razorpay/api")

    def test_handles_none_mcp_calls(self):
        """Test handling None MCP calls."""
        skills = ["security-review"]

        with patch(
            "src.agents.review_agents.metrics.record_mcp_calls"
        ) as mock_mcp, patch(
            "src.agents.review_agents.metrics.record_skills_usage"
        ) as mock_skills:
            record_tool_usage(None, skills, "razorpay/api")

            mock_mcp.assert_not_called()
            mock_skills.assert_called_once()

    def test_handles_none_skills(self):
        """Test handling None skills."""
        mcp_calls = [{"tool_name": "mcp__github__get_pr"}]

        with patch(
            "src.agents.review_agents.metrics.record_mcp_calls"
        ) as mock_mcp, patch(
            "src.agents.review_agents.metrics.record_skills_usage"
        ) as mock_skills:
            record_tool_usage(mcp_calls, None, "razorpay/api")

            mock_mcp.assert_called_once()
            mock_skills.assert_not_called()


class TestRecordAutoApproveDecision:
    """Tests for record_auto_approve_decision function."""

    def test_records_approved_outcome(self):
        """Test recording a successful auto-approve."""
        with patch(
            "src.agents.review_agents.metrics.PR_AUTO_APPROVE_TOTAL"
        ) as mock_counter:
            mock_labels = MagicMock()
            mock_counter.labels.return_value = mock_labels

            record_auto_approve_decision(
                outcome="approved",
                rule_source="repo_skill",
                repository="razorpay/api",
                repo_skill_name="risk-assessment",
            )

            mock_counter.labels.assert_called_with(
                outcome="approved",
                rule_source="repo_skill",
                repository="razorpay/api",
                repo_skill_name="risk-assessment",
            )
            mock_labels.inc.assert_called_once()

    def test_records_overridden_outcome(self):
        """Test recording an overridden auto-approve."""
        with patch(
            "src.agents.review_agents.metrics.PR_AUTO_APPROVE_TOTAL"
        ) as mock_counter:
            mock_labels = MagicMock()
            mock_counter.labels.return_value = mock_labels

            record_auto_approve_decision(
                outcome="overridden",
                rule_source="repo_skill",
                repository="razorpay/api",
                repo_skill_name="risk-assessment",
            )

            mock_counter.labels.assert_called_with(
                outcome="overridden",
                rule_source="repo_skill",
                repository="razorpay/api",
                repo_skill_name="risk-assessment",
            )
            mock_labels.inc.assert_called_once()

    def test_records_config_approved_outcome(self):
        """Test recording a config-driven approve."""
        with patch(
            "src.agents.review_agents.metrics.PR_AUTO_APPROVE_TOTAL"
        ) as mock_counter:
            mock_labels = MagicMock()
            mock_counter.labels.return_value = mock_labels

            record_auto_approve_decision(
                outcome="config_approved",
                rule_source="standard_rules",
                repository="razorpay/api",
            )

            mock_counter.labels.assert_called_with(
                outcome="config_approved",
                rule_source="standard_rules",
                repository="razorpay/api",
                repo_skill_name="none",
            )
            mock_labels.inc.assert_called_once()

    def test_records_not_eligible_outcome(self):
        """Test recording not_eligible when skill says auto_approve=false."""
        with patch(
            "src.agents.review_agents.metrics.PR_AUTO_APPROVE_TOTAL"
        ) as mock_counter:
            mock_labels = MagicMock()
            mock_counter.labels.return_value = mock_labels

            record_auto_approve_decision(
                outcome="not_eligible",
                rule_source="standard_rules",
                repository="razorpay/api",
            )

            mock_counter.labels.assert_called_with(
                outcome="not_eligible",
                rule_source="standard_rules",
                repository="razorpay/api",
                repo_skill_name="none",
            )
            mock_labels.inc.assert_called_once()

    def test_records_auto_gen_would_approve_outcome(self):
        """Test recording auto_gen_would_approve when auto-generated skill wanted to approve."""
        with patch(
            "src.agents.review_agents.metrics.PR_AUTO_APPROVE_TOTAL"
        ) as mock_counter:
            mock_labels = MagicMock()
            mock_counter.labels.return_value = mock_labels

            record_auto_approve_decision(
                outcome="auto_gen_would_approve",
                rule_source="generated_context",
                repository="razorpay/partnerships",
                repo_skill_name="risk-assessment",
            )

            mock_counter.labels.assert_called_with(
                outcome="auto_gen_would_approve",
                rule_source="generated_context",
                repository="razorpay/partnerships",
                repo_skill_name="risk-assessment",
            )
            mock_labels.inc.assert_called_once()

    def test_none_skill_name_defaults_to_none_string(self):
        """Test that None repo_skill_name is stored as 'none'."""
        with patch(
            "src.agents.review_agents.metrics.PR_AUTO_APPROVE_TOTAL"
        ) as mock_counter:
            mock_labels = MagicMock()
            mock_counter.labels.return_value = mock_labels

            record_auto_approve_decision(
                outcome="approved",
                rule_source="repo_skill",
                repository="razorpay/api",
                repo_skill_name=None,
            )

            _, kwargs = mock_counter.labels.call_args
            assert kwargs["repo_skill_name"] == "none"


class TestInitializeFunctions:
    """Tests for initialization functions."""

    def test_initialize_plugin_metrics_logs(self):
        """Test that initialization logs properly."""
        with patch("src.agents.review_agents.metrics.logger") as mock_logger:
            initialize_plugin_metrics()

            mock_logger.info.assert_called_once()
            assert "Plugin metrics initialized" in mock_logger.info.call_args[0][0]

    def test_initialize_review_metrics_alias(self):
        """Test backward compatibility alias."""
        with patch(
            "src.agents.review_agents.metrics.initialize_plugin_metrics"
        ) as mock_fn:
            initialize_review_metrics()

            mock_fn.assert_called_once()
