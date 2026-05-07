"""
Unit tests for GitHubPRCommentPublisher.

Tests the GitHub PR comment publishing functionality with inline comments.
"""

import json
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.review_agents.github_pr_comment_publisher import (
    GitHubPRCommentPublisher,
)
from src.agents.review_agents.models import PublishResult
from src.constants.github_bots import GitHubBot


@pytest.fixture
def publisher():
    """Create a GitHubPRCommentPublisher instance."""
    return GitHubPRCommentPublisher(github_bot=GitHubBot.CODE_REVIEW)


@pytest.fixture
def sample_suggestions():
    """Sample suggestions for testing."""
    return [
        {
            "file": "src/main.py",
            "line": 42,
            "category": "BUG",
            "importance": 8,
            "confidence": 0.9,
            "description": "🐛 **Bug**: Potential null pointer exception",
            "suggestion_code": "if obj is not None:\n    result = obj.value",
            "existing_code": "result = obj.value",
        },
        {
            "file": "src/api.py",
            "line": 10,
            "line_end": 15,
            "category": "PERFORMANCE",
            "importance": 6,
            "confidence": 0.8,
            "description": "⚡ **Performance**: N+1 query detected",
        },
        {
            "file": "src/utils.py",
            "line": 20,
            "category": "SECURITY",
            "importance": 9,
            "confidence": 0.95,
            "description": "🔒 **Security**: SQL injection vulnerability",
            "suggestion_code": "query = db.execute(sql, (user_input,))",
        },
    ]


@pytest.fixture
def pr_info_response():
    """Mock PR info response from gh api."""
    return {
        "head_sha": "abc123def456",
        "files": ["src/main.py", "src/api.py", "src/utils.py", "README.md"],
    }


def create_mock_process(stdout: bytes, returncode: int = 0, stderr: bytes = b""):
    """Create a mock async subprocess for testing."""
    mock_process = MagicMock()
    mock_process.returncode = returncode
    mock_process.communicate = AsyncMock(return_value=(stdout, stderr))
    return mock_process


class TestGitHubPRCommentPublisher:
    """Test suite for GitHubPRCommentPublisher."""

    @pytest.mark.asyncio
    async def test_publish_success(self, publisher, sample_suggestions):
        """Test successful review creation with inline comments."""
        # Mock GitHubAuthService
        with patch.object(
            publisher._auth_service, "get_token", new_callable=AsyncMock
        ) as mock_get_token:
            mock_get_token.return_value = "ghp_test_token"

            # Mock async subprocess calls
            with patch("asyncio.create_subprocess_exec") as mock_exec:
                # Setup mock responses (3 calls: SHA, files, post review)
                mock_exec.side_effect = [
                    # First call: get PR head SHA
                    create_mock_process(b'"abc123def456"'),
                    # Second call: get PR files
                    create_mock_process(
                        json.dumps(["src/main.py", "src/api.py", "src/utils.py", "README.md"]).encode()
                    ),
                    # Third call: post review
                    create_mock_process(
                        json.dumps({
                            "id": 12345,
                            "state": "COMMENTED",
                            "comments": [{"id": 1}, {"id": 2}, {"id": 3}],
                        }).encode()
                    ),
                ]

                # Execute
                result = await publisher.publish(
                    repository="owner/repo",
                    pr_number=123,
                    suggestions=sample_suggestions,
                )

                # Verify result
                assert result.success is True
                assert result.review_id == 12345
                assert result.comments_posted == 3
                assert result.comments_skipped == 0
                assert result.error is None

                # Verify 3 async subprocess calls were made
                assert mock_exec.call_count == 3

    @pytest.mark.asyncio
    async def test_publish_empty_suggestions(self, publisher):
        """Test posting review with no suggestions."""
        with patch.object(
            publisher._auth_service, "get_token", new_callable=AsyncMock
        ) as mock_get_token:
            mock_get_token.return_value = "ghp_test_token"

            with patch("asyncio.create_subprocess_exec") as mock_exec:
                mock_exec.side_effect = [
                    # Get PR head SHA
                    create_mock_process(b'"abc123def456"'),
                    # Get PR files
                    create_mock_process(
                        json.dumps(["src/main.py", "src/api.py"]).encode()
                    ),
                    # Post review
                    create_mock_process(
                        json.dumps({"id": 99999, "state": "COMMENTED"}).encode()
                    ),
                ]

                result = await publisher.publish(
                    repository="owner/repo",
                    pr_number=123,
                    suggestions=[],
                )

                assert result.success is True
                assert result.comments_posted == 0
                assert result.comments_skipped == 0

    @pytest.mark.asyncio
    async def test_get_pr_info(self, publisher):
        """Test fetching PR info via gh api."""
        env = {"GITHUB_TOKEN": "ghp_test_token"}

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            # Now makes 2 calls: one for SHA, one for files
            mock_exec.side_effect = [
                create_mock_process(b'"abc123def456"'),
                create_mock_process(
                    json.dumps(["src/main.py", "src/api.py", "src/utils.py", "README.md"]).encode()
                ),
            ]

            result = await publisher._get_pr_info("owner/repo", 123, env)

            assert result["head_sha"] == "abc123def456"
            assert len(result["files"]) == 4
            assert "src/main.py" in result["files"]

            # Verify 2 calls were made
            assert mock_exec.call_count == 2

    def test_build_comments_multi_line(self, publisher):
        """Test building comments with multi-line ranges."""
        suggestions = [
            {
                "file": "src/api.py",
                "line": 10,
                "line_end": 15,
                "description": "Multi-line issue",
            }
        ]
        pr_files = {"src/api.py"}

        comments = publisher._build_comments(suggestions, pr_files)

        assert len(comments) == 1
        assert comments[0]["path"] == "src/api.py"
        assert comments[0]["start_line"] == 10
        assert comments[0]["line"] == 15
        assert comments[0]["side"] == "RIGHT"

    def test_build_comments_single_line(self, publisher):
        """Test building comments for single line."""
        suggestions = [
            {
                "file": "src/main.py",
                "line": 42,
                "description": "Single line issue",
            }
        ]
        pr_files = {"src/main.py"}

        comments = publisher._build_comments(suggestions, pr_files)

        assert len(comments) == 1
        assert comments[0]["path"] == "src/main.py"
        assert comments[0]["line"] == 42
        assert comments[0]["side"] == "RIGHT"
        assert "start_line" not in comments[0]

    def test_build_comments_skip_file(self, publisher):
        """Test skipping files not in PR."""
        suggestions = [
            {
                "file": "src/main.py",
                "line": 42,
                "description": "Issue in main",
            },
            {
                "file": "src/external.py",
                "line": 10,
                "description": "Issue in external file",
            },
        ]
        pr_files = {"src/main.py"}  # external.py not in PR

        comments = publisher._build_comments(suggestions, pr_files)

        # Only one comment should be created (external.py skipped)
        assert len(comments) == 1
        assert comments[0]["path"] == "src/main.py"
        assert comments[0]["side"] == "RIGHT"

    def test_format_comment_with_suggestion_code(self, publisher):
        """Test formatting comment with suggestion code block in collapsible details."""
        suggestion = {
            "description": "🐛 **Bug**: Fix null pointer",
            "suggestion_code": "if obj:\n    result = obj.value",
        }

        body = publisher._format_comment(suggestion)

        assert "🐛 **Bug**: Fix null pointer" in body
        # Code should be wrapped in collapsible details tag
        assert "<details>" in body
        assert "<summary>" in body
        assert "View suggested fix" in body
        assert "```suggestion" in body
        assert "if obj:\n    result = obj.value" in body
        assert "</details>" in body

    def test_format_comment_without_suggestion_code(self, publisher):
        """Test formatting comment with description only."""
        suggestion = {
            "description": "Performance: Optimize query",
            "category": "PERFORMANCE",
        }

        body = publisher._format_comment(suggestion)

        assert "Performance: Optimize query" in body
        assert "```suggestion" not in body

    def test_format_comment_with_non_committable_code(self, publisher):
        """Test that non-committable code is not included in comment."""
        suggestion = {
            "description": "Remove this duplicate line",
            "category": "CODE_QUALITY",
            "importance": 7,
            "suggestion_code": "// delete this line\n// remove the duplicate",
        }

        body = publisher._format_comment(suggestion)

        # Should NOT include code block because it's non-committable
        assert "```suggestion" not in body
        assert "Remove this duplicate line" in body

    def test_format_comment_redacts_secrets(self, publisher):
        """Test that secrets in description are redacted."""
        suggestion = {
            "description": "Found hardcoded token: ghp_1234567890abcdefghijklmnopqrstuvwxyz12",
            "category": "SECURITY",
            "importance": 10,
        }

        body = publisher._format_comment(suggestion)

        # Secret should be redacted
        assert "ghp_1234567890" not in body
        assert "REDACTED" in body

    def test_format_comment_redacts_secrets_in_code(self, publisher):
        """Test that secrets in suggestion_code are redacted."""
        suggestion = {
            "description": "Use environment variable instead",
            "category": "SECURITY",
            "importance": 9,
            "suggestion_code": 'api_key = "sk_live_FAKE_KEY_FOR_TESTING_ONLY"',
        }

        body = publisher._format_comment(suggestion)

        # Secret should be redacted in code
        assert "sk_live_" not in body
        assert "REDACTED" in body

    def test_has_committable_code_with_valid_code(self, publisher):
        """Test _has_committable_code returns True for real code."""
        assert publisher._has_committable_code("if obj:\n    return obj.value") is True
        assert publisher._has_committable_code("return fmt.Errorf('error: %w', err)") is True
        assert publisher._has_committable_code("def foo():\n    pass") is True

    def test_has_committable_code_with_delete_comment(self, publisher):
        """Test _has_committable_code returns False for delete instructions."""
        assert publisher._has_committable_code("// delete this line") is False
        assert publisher._has_committable_code("// Remove this duplicate") is False
        assert publisher._has_committable_code("# TODO: fix this") is False
        assert publisher._has_committable_code("# FIXME: remove later") is False

    def test_has_committable_code_with_empty(self, publisher):
        """Test _has_committable_code returns False for empty/None."""
        assert publisher._has_committable_code(None) is False
        assert publisher._has_committable_code("") is False
        assert publisher._has_committable_code("   ") is False

    def test_build_body_inline_only(self, publisher):
        """Test building review body with inline suggestions only."""
        body = publisher._build_body(inline_count=3, general_suggestions=[])

        assert "## AI Code Review" in body
        assert "Found **3** inline suggestion(s)" in body
        assert "Related Suggestions" not in body

    def test_build_body_general_only(self, publisher):
        """Test building review body with general suggestions only."""
        general = [
            {
                "file": "tests/test_utils.py",
                "line": 50,
                "description": "Test file needs updating",
                "category": "TESTING",
                "importance": 6,
            }
        ]

        body = publisher._build_body(inline_count=0, general_suggestions=general)

        assert "## AI Code Review" in body
        assert "Related Suggestions" in body
        assert "tests/test_utils.py:50" in body
        assert "Test file needs updating" in body
        assert "TESTING" in body

    def test_build_body_mixed(self, publisher):
        """Test building review body with both inline and general suggestions."""
        general = [
            {
                "file": "related_file.py",
                "line": 10,
                "description": "Related issue",
                "category": "BUG",
                "importance": 7,
            }
        ]

        body = publisher._build_body(inline_count=2, general_suggestions=general)

        assert "Found **2** inline suggestion(s)" in body
        assert "Related Suggestions" in body
        assert "related_file.py:10" in body

    def test_build_body_no_suggestions(self, publisher):
        """Test building review body with no suggestions."""
        body = publisher._build_body(inline_count=0, general_suggestions=[])

        assert "No issues found" in body

    def test_build_body_redacts_secrets(self, publisher):
        """Test that secrets in review body are redacted."""
        general = [
            {
                "file": "config.py",
                "line": 10,
                "description": "Found AWS key: AKIAIOSFODNN7EXAMPLE in config",
                "category": "SECURITY",
                "importance": 10,
            }
        ]

        body = publisher._build_body(inline_count=0, general_suggestions=general)

        # AWS key should be redacted
        assert "AKIAIOSFODNN7EXAMPLE" not in body
        assert "REDACTED" in body

    @pytest.mark.asyncio
    async def test_publish_subprocess_error(self, publisher, sample_suggestions):
        """Test handling gh api subprocess error."""
        with patch.object(
            publisher._auth_service, "get_token", new_callable=AsyncMock
        ) as mock_get_token:
            mock_get_token.return_value = "ghp_test_token"

            with patch("asyncio.create_subprocess_exec") as mock_exec:
                # Return a process with non-zero exit code
                mock_exec.return_value = create_mock_process(
                    b"", returncode=1, stderr=b"API error: rate limit exceeded"
                )

                result = await publisher.publish(
                    repository="owner/repo",
                    pr_number=123,
                    suggestions=sample_suggestions,
                )

                assert result.success is False
                assert result.error is not None
                assert result.comments_posted == 0

    @pytest.mark.asyncio
    async def test_publish_auth_error(self, publisher, sample_suggestions):
        """Test handling authentication failure."""
        with patch.object(
            publisher._auth_service, "get_token", new_callable=AsyncMock
        ) as mock_get_token:
            mock_get_token.side_effect = Exception("Auth failed")

            result = await publisher.publish(
                repository="owner/repo",
                pr_number=123,
                suggestions=sample_suggestions,
            )

            assert result.success is False
            assert "Auth failed" in result.error

    @pytest.mark.asyncio
    async def test_publish_gh_not_found(self, publisher, sample_suggestions):
        """Test handling gh CLI not installed."""
        with patch.object(
            publisher._auth_service, "get_token", new_callable=AsyncMock
        ) as mock_get_token:
            mock_get_token.return_value = "ghp_test_token"

            with patch("asyncio.create_subprocess_exec") as mock_exec:
                mock_exec.side_effect = FileNotFoundError("gh command not found")

                result = await publisher.publish(
                    repository="owner/repo",
                    pr_number=123,
                    suggestions=sample_suggestions,
                )

                assert result.success is False
                assert result.error == "gh CLI not found"

    @pytest.mark.asyncio
    async def test_publish_json_parse_error(self, publisher, sample_suggestions):
        """Test handling invalid JSON response."""
        with patch.object(
            publisher._auth_service, "get_token", new_callable=AsyncMock
        ) as mock_get_token:
            mock_get_token.return_value = "ghp_test_token"

            with patch("asyncio.create_subprocess_exec") as mock_exec:
                mock_exec.return_value = create_mock_process(b"invalid json{{{")

                result = await publisher.publish(
                    repository="owner/repo",
                    pr_number=123,
                    suggestions=sample_suggestions,
                )

                assert result.success is False
                assert result.error == "Invalid API response"

    def test_build_review_payload_with_suggestions(self, publisher, sample_suggestions):
        """Test building review payload with inline suggestions."""
        pr_files = {"src/main.py", "src/api.py", "src/utils.py"}

        # Add comment_type to sample suggestions (all inline since files are in PR)
        for s in sample_suggestions:
            s["comment_type"] = "inline"

        payload = publisher._build_review_payload(
            commit_sha="abc123",
            suggestions=sample_suggestions,
            pr_files=pr_files,
            review_event="COMMENT",
        )

        assert payload["commit_id"] == "abc123"
        assert payload["event"] == "COMMENT"
        assert "## AI Code Review" in payload["body"]
        assert "inline suggestion" in payload["body"]
        assert len(payload["comments"]) == 3

    def test_build_review_payload_separates_types(self, publisher):
        """Test that payload correctly separates inline and general suggestions."""
        suggestions = [
            {
                "file": "src/main.py",
                "line": 42,
                "description": "Bug in main",
                "category": "BUG",
                "importance": 8,
                "comment_type": "inline",
            },
            {
                "file": "tests/test_main.py",
                "line": 50,
                "description": "Test needs updating",
                "category": "TESTING",
                "importance": 6,
                "comment_type": "general",  # File not in PR
            },
        ]
        pr_files = {"src/main.py"}

        payload = publisher._build_review_payload(
            commit_sha="abc123",
            suggestions=suggestions,
            pr_files=pr_files,
            review_event="COMMENT",
        )

        # Only 1 inline comment should be created
        assert len(payload["comments"]) == 1
        assert payload["comments"][0]["path"] == "src/main.py"

        # Body should mention 1 inline and show general suggestion
        assert "1** inline" in payload["body"]
        assert "Related Suggestions" in payload["body"]
        assert "tests/test_main.py" in payload["body"]

    def test_build_review_payload_empty_suggestions(self, publisher):
        """Test building review payload with no suggestions."""
        payload = publisher._build_review_payload(
            commit_sha="abc123",
            suggestions=[],
            pr_files=set(),
            review_event="COMMENT",
        )

        assert payload["commit_id"] == "abc123"
        assert payload["event"] == "COMMENT"
        assert "No issues found" in payload["body"]
        assert payload["comments"] == []

    def test_review_event_extensibility(self, publisher):
        """Test that review_event parameter is extensible."""
        pr_files = {"src/main.py"}
        suggestions = [{"file": "src/main.py", "line": 1, "description": "Test"}]

        # Test COMMENT (default)
        payload_comment = publisher._build_review_payload(
            "abc123", suggestions, pr_files, "COMMENT"
        )
        assert payload_comment["event"] == "COMMENT"

        # Test APPROVE
        payload_approve = publisher._build_review_payload(
            "abc123", suggestions, pr_files, "APPROVE"
        )
        assert payload_approve["event"] == "APPROVE"

        # Test REQUEST_CHANGES
        payload_request = publisher._build_review_payload(
            "abc123", suggestions, pr_files, "REQUEST_CHANGES"
        )
        assert payload_request["event"] == "REQUEST_CHANGES"


class TestBuildToolUsageSection:
    """Tests for _build_tool_usage_section method."""

    def test_build_tool_usage_section_with_mcp_calls(self, publisher):
        """Test building tool usage section with MCP calls."""
        mcp_calls = [
            {"tool_name": "mcp__blade-mcp__get_blade_component_docs"},
            {"tool_name": "mcp__blade-mcp__get_blade_pattern_docs"},
            {"tool_name": "mcp__memory__search_nodes"},
        ]

        section = publisher._build_tool_usage_section(mcp_calls, None)

        assert "### Tools Used" in section
        assert "**MCP Servers:**" in section
        assert "blade-mcp" in section
        assert "memory" in section

    def test_build_tool_usage_section_with_skills(self, publisher):
        """Test building tool usage section with skills used."""
        skills_used = ["i18n-anomaly-detection", "code-review", "security-scan"]

        section = publisher._build_tool_usage_section(None, skills_used)

        assert "### Tools Used" in section
        assert "**Skills:**" in section
        assert "i18n-anomaly-detection" in section
        assert "code-review" in section
        assert "security-scan" in section

    def test_build_tool_usage_section_with_both(self, publisher):
        """Test building tool usage section with both MCP calls and skills."""
        mcp_calls = [
            {"tool_name": "mcp__devrev__create_ticket"},
            {"tool_name": "mcp__slack__send_message"},
        ]
        skills_used = ["blade-review", "performance-analysis"]

        section = publisher._build_tool_usage_section(mcp_calls, skills_used)

        assert "### Tools Used" in section
        assert "**MCP Servers:**" in section
        assert "devrev" in section
        assert "slack" in section
        assert "**Skills:**" in section
        assert "blade-review" in section
        assert "performance-analysis" in section

    def test_build_tool_usage_section_empty(self, publisher):
        """Test building tool usage section with no tools."""
        section = publisher._build_tool_usage_section(None, None)
        assert section == ""

        section = publisher._build_tool_usage_section([], [])
        assert section == ""

    def test_build_tool_usage_section_deduplicates_mcp_servers(self, publisher):
        """Test that MCP server names are deduplicated."""
        mcp_calls = [
            {"tool_name": "mcp__blade-mcp__get_blade_component_docs"},
            {"tool_name": "mcp__blade-mcp__get_blade_pattern_docs"},
            {"tool_name": "mcp__blade-mcp__hi_blade"},
        ]

        section = publisher._build_tool_usage_section(mcp_calls, None)

        # Should only appear once
        assert section.count("blade-mcp") == 1

    def test_build_tool_usage_section_handles_non_mcp_tools(self, publisher):
        """Test that non-MCP tools are ignored."""
        mcp_calls = [
            {"tool_name": "Read"},
            {"tool_name": "Write"},
            {"tool_name": "mcp__memory__read_graph"},
        ]

        section = publisher._build_tool_usage_section(mcp_calls, None)

        assert "memory" in section
        assert "Read" not in section
        assert "Write" not in section

    def test_build_tool_usage_section_sorts_output(self, publisher):
        """Test that MCP servers and skills are sorted."""
        mcp_calls = [
            {"tool_name": "mcp__zebra__tool1"},
            {"tool_name": "mcp__alpha__tool2"},
        ]
        skills_used = ["z-skill", "a-skill"]

        section = publisher._build_tool_usage_section(mcp_calls, skills_used)

        # Find positions - alpha should come before zebra
        alpha_pos = section.find("alpha")
        zebra_pos = section.find("zebra")
        assert alpha_pos < zebra_pos

        # a-skill should come before z-skill
        a_skill_pos = section.find("a-skill")
        z_skill_pos = section.find("z-skill")
        assert a_skill_pos < z_skill_pos

    def test_build_tool_usage_section_handles_missing_tool_name(self, publisher):
        """Test handling of MCP calls without tool_name."""
        mcp_calls = [
            {"tool_name": "mcp__valid-server__tool"},
            {},  # Missing tool_name
            {"other_field": "value"},  # Missing tool_name
        ]

        section = publisher._build_tool_usage_section(mcp_calls, None)

        assert "valid-server" in section


class TestSkillTransparency:
    """Tests for skill transparency in comment formatting."""

    def test_format_comment_with_source_subagent(self, publisher):
        """Test that source sub-agent is shown in the comment."""
        suggestion = {
            "description": "Missing error handling",
            "category": "BUG",
            "importance": 7,
            "source_subagent": "bug",
        }

        body = publisher._format_comment(suggestion)

        assert "sub-agent: `bug`" in body
        assert "_Source:" in body
        # No skill line since source_skill is not set
        assert "skill:" not in body

    def test_format_comment_with_source_subagent_and_skill(self, publisher):
        """Test that both sub-agent and skill are shown."""
        suggestion = {
            "description": "SQL injection risk",
            "category": "SECURITY",
            "importance": 9,
            "source_subagent": "security",
            "source_skill": "code-review",
        }

        body = publisher._format_comment(suggestion)

        assert "sub-agent: `security`" in body
        assert "skill: `code-review`" in body
        assert "_Source:" in body

    def test_format_comment_without_source_backward_compat(self, publisher):
        """Test that comments without source fields still work."""
        suggestion = {
            "description": "Old style suggestion",
            "category": "GENERAL",
            "importance": 5,
        }

        body = publisher._format_comment(suggestion)

        assert "Old style suggestion" in body
        assert "_Source:" not in body
        assert "sub-agent:" not in body

    def test_severity_comment_includes_attribution_table(self, publisher):
        """Test that severity comment includes sub-agent attribution table."""
        from src.agents.review_agents.models import SeverityAssessment, SubAgentResult

        assessment = SeverityAssessment(
            severity="medium",
            confidence=0.85,
            rule_source="repo_skill",
            reasoning="PR modifies payment logic.",
            category_breakdown={},
            repo_skill_name="code-review",
        )

        subagent_results = [
            SubAgentResult(
                category="bug",
                suggestions=[{"d": 1}, {"d": 2}],
                success=True,
                skills_used=["code-review"],
            ),
            SubAgentResult(
                category="security",
                suggestions=[{"d": 1}],
                success=True,
            ),
            SubAgentResult(
                category="i18n",
                suggestions=[],
                success=True,
                skipped=True,
                skip_reason="No frontend files",
            ),
        ]

        body = publisher._build_severity_comment_body(
            assessment, subagent_results=subagent_results,
        )

        assert "Sub-Agent Attribution" in body
        assert "| `bug` | 2 | code-review |" in body
        assert "| `security` | 1 | - |" in body
        # Skipped agent with 0 suggestions should NOT appear
        assert "i18n" not in body

    def test_severity_comment_no_attribution_without_results(self, publisher):
        """Test that attribution table is omitted when no subagent_results."""
        from src.agents.review_agents.models import SeverityAssessment

        assessment = SeverityAssessment(
            severity="low",
            confidence=0.9,
            rule_source="standard_rules",
            reasoning="Only test changes.",
            category_breakdown={},
        )

        body = publisher._build_severity_comment_body(assessment)

        assert "Sub-Agent Attribution" not in body
        assert "Assessed by rCoRe" in body

    def test_severity_comment_shows_auto_gen_approve_verdict(self, publisher):
        """Test that auto-generated skill approve verdict appears in comment."""
        from src.agents.review_agents.models import SeverityAssessment

        assessment = SeverityAssessment(
            severity="low",
            confidence=0.92,
            rule_source="generated_context",
            reasoning="No issues found.",
            category_breakdown={},
            repo_skill_name="risk-assessment",
            auto_approve=False,
            auto_approve_raw=True,
        )

        body = publisher._build_severity_comment_body(assessment)

        assert "Auto-approved by RCoRe V2++" in body
        assert "verdict only" in body
        assert "not applied" in body

    def test_severity_comment_no_auto_gen_text_for_hand_crafted_skill(self, publisher):
        """Test that hand-crafted repo skills don't show auto-gen verdict text."""
        from src.agents.review_agents.models import SeverityAssessment

        assessment = SeverityAssessment(
            severity="low",
            confidence=0.9,
            rule_source="repo_skill",
            reasoning="All good.",
            category_breakdown={},
            repo_skill_name="risk-assessment",
            auto_approve=True,
            auto_approve_raw=True,
        )

        body = publisher._build_severity_comment_body(assessment)

        assert "Auto-approved by RCoRe V2++" not in body

    def test_severity_comment_no_auto_gen_text_when_not_approved(self, publisher):
        """Test that auto-gen text doesn't show when LLM said auto_approve=false."""
        from src.agents.review_agents.models import SeverityAssessment

        assessment = SeverityAssessment(
            severity="medium",
            confidence=0.8,
            rule_source="generated_context",
            reasoning="Some issues found.",
            category_breakdown={},
            repo_skill_name="risk-assessment",
            auto_approve=False,
            auto_approve_raw=False,
        )

        body = publisher._build_severity_comment_body(assessment)

        assert "Auto-approved by RCoRe V2++" not in body
