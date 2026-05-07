"""
Unit tests for FilterLayer.

Tests the AI-powered filtering of PR review suggestions.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.review_agents.filter_layer import FilterLayer


@pytest.fixture
def filter_layer(tmp_path):
    """Create a FilterLayer instance."""
    return FilterLayer(
        working_directory=str(tmp_path),
        min_score_threshold=5,
        pre_filter_threshold=3,
    )


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
            "description": "Potential null pointer exception",
        },
        {
            "file": "src/api.py",
            "line": 10,
            "category": "PERFORMANCE",
            "importance": 6,
            "confidence": 0.8,
            "description": "N+1 query detected",
        },
        {
            "file": "src/utils.py",
            "line": 20,
            "category": "SECURITY",
            "importance": 2,  # Will be filtered by pre-filter
            "confidence": 0.5,
            "description": "Minor style issue",
        },
    ]


@pytest.fixture
def pr_context():
    """Sample PR context."""
    return {
        "title": "Add user authentication",
        "description": "Implements OAuth2 login",
        "repository": "owner/repo",
        "pr_number": 123,
    }


class TestFilterLayer:
    """Test suite for FilterLayer."""

    @pytest.mark.asyncio
    async def test_apply_empty_suggestions(self, filter_layer, pr_context):
        """Test that empty suggestions list returns empty list."""
        result = await filter_layer.apply([], "diff content", pr_context)

        assert result == []

    def test_pre_filter_removes_low_importance(self, filter_layer):
        """Test pre-filter removes suggestions with importance < 3."""
        suggestions = [
            {"file": "a.py", "importance": 5},
            {"file": "b.py", "importance": 2},  # Should be filtered
            {"file": "c.py", "importance": 3},
            {"file": "d.py", "importance": 1},  # Should be filtered
        ]

        filtered = filter_layer._pre_filter(suggestions)

        assert len(filtered) == 2
        assert filtered[0]["file"] == "a.py"
        assert filtered[1]["file"] == "c.py"

    @pytest.mark.asyncio
    async def test_evaluate_with_llm_success(
        self, filter_layer, sample_suggestions, pr_context
    ):
        """Test successful LLM evaluation with scores added."""
        # Mock PRAgentKit.prompts.render()
        mock_rendered = MagicMock()
        mock_rendered.system = "System prompt"
        mock_rendered.user = "User prompt"

        with patch.object(
            filter_layer._kit.prompts, "render", return_value=mock_rendered
        ):
            # Mock ClaudeCodeTool.execute()
            with patch.object(
                filter_layer._claude_tool, "execute", new_callable=AsyncMock
            ) as mock_execute:
                mock_execute.return_value = {
                    "result": """evaluations:
  - index: 0
    score: 8
    reason: "Critical null pointer"
  - index: 1
    score: 6
    reason: "Performance issue"
"""
                }

                result = await filter_layer._evaluate_with_llm(
                    sample_suggestions[:2], "diff", pr_context
                )

                assert len(result) == 2
                assert result[0]["llm_score"] == 8
                assert result[0]["llm_reasoning"] == "Critical null pointer"
                assert result[1]["llm_score"] == 6
                assert result[1]["llm_reasoning"] == "Performance issue"

    @pytest.mark.asyncio
    async def test_evaluate_with_llm_failure(
        self, filter_layer, sample_suggestions, pr_context
    ):
        """Test LLM error fallback to importance scores."""
        # Mock PRAgentKit.prompts.render()
        mock_rendered = MagicMock()
        mock_rendered.system = "System prompt"
        mock_rendered.user = "User prompt"

        with patch.object(
            filter_layer._kit.prompts, "render", return_value=mock_rendered
        ):
            # Mock ClaudeCodeTool.execute() with error
            with patch.object(
                filter_layer._claude_tool, "execute", new_callable=AsyncMock
            ) as mock_execute:
                mock_execute.return_value = {
                    "error": True,
                    "message": "LLM execution failed",
                }

                result = await filter_layer._evaluate_with_llm(
                    sample_suggestions[:2], "diff", pr_context
                )

                # Should fallback to importance scores
                assert result[0]["llm_score"] == 8  # Original importance
                assert "failed" in result[0]["llm_reasoning"].lower()
                assert result[1]["llm_score"] == 6
                assert "failed" in result[1]["llm_reasoning"].lower()

    def test_merge_scores_parse_error(self, filter_layer):
        """Test handling of YAML parse error."""
        suggestions = [{"file": "a.py", "importance": 7}]

        # Invalid YAML response
        response = {"result": "invalid yaml{{{"}

        result = filter_layer._merge_scores(suggestions, response)

        # Should set score to 0 on parse error
        assert result[0]["llm_score"] == 0
        assert "parse error" in result[0]["llm_reasoning"].lower()

    def test_post_filter_by_threshold(self, filter_layer):
        """Test post-filter keeps only llm_score >= 5."""
        suggestions = [
            {"file": "a.py", "llm_score": 8, "importance": 8},
            {"file": "b.py", "llm_score": 3, "importance": 6},  # Filtered
            {"file": "c.py", "llm_score": 5, "importance": 5},
            {"file": "d.py", "llm_score": 0, "importance": 2},  # Filtered
        ]

        filtered = filter_layer._post_filter(suggestions)

        assert len(filtered) == 2
        # Should keep scores >= 5
        assert all(s["llm_score"] >= 5 for s in filtered)

    def test_post_filter_sorts_by_score(self, filter_layer):
        """Test post-filter sorts by llm_score descending."""
        suggestions = [
            {"file": "a.py", "llm_score": 5, "importance": 5},
            {"file": "b.py", "llm_score": 9, "importance": 9},
            {"file": "c.py", "llm_score": 7, "importance": 7},
        ]

        filtered = filter_layer._post_filter(suggestions)

        # Should be sorted by llm_score descending
        assert filtered[0]["llm_score"] == 9
        assert filtered[1]["llm_score"] == 7
        assert filtered[2]["llm_score"] == 5

    @pytest.mark.asyncio
    async def test_apply_end_to_end(
        self, filter_layer, sample_suggestions, pr_context
    ):
        """Test full pipeline: pre-filter → LLM → post-filter."""
        # Mock LLM evaluation
        mock_rendered = MagicMock()
        mock_rendered.system = "System prompt"
        mock_rendered.user = "User prompt"

        with patch.object(
            filter_layer._kit.prompts, "render", return_value=mock_rendered
        ):
            with patch.object(
                filter_layer._claude_tool, "execute", new_callable=AsyncMock
            ) as mock_execute:
                # Return scores for first 2 suggestions (third filtered by pre-filter)
                mock_execute.return_value = {
                    "result": """evaluations:
  - index: 0
    score: 8
    reason: "Critical bug"
  - index: 1
    score: 4
    reason: "Minor issue"
"""
                }

                result = await filter_layer.apply(
                    sample_suggestions, "diff content", pr_context
                )

                # Stage 1: Pre-filter removes importance < 3 (third suggestion)
                # Stage 2: LLM evaluates remaining 2
                # Stage 3: Post-filter removes llm_score < 5 (second suggestion)
                assert len(result) == 1
                assert result[0]["file"] == "src/main.py"
                assert result[0]["llm_score"] == 8

    @pytest.mark.asyncio
    async def test_pre_filter_returns_empty(self, filter_layer, pr_context):
        """Test that pre-filter returning empty stops pipeline."""
        # All suggestions have importance < 3
        low_importance = [
            {"file": "a.py", "importance": 1},
            {"file": "b.py", "importance": 2},
        ]

        result = await filter_layer.apply(low_importance, "diff", pr_context)

        # Should return empty without calling LLM
        assert result == []

    def test_merge_scores_index_mismatch(self, filter_layer):
        """Test handling when LLM returns fewer evaluations than suggestions."""
        suggestions = [
            {"file": "a.py", "importance": 7},
            {"file": "b.py", "importance": 6},
            {"file": "c.py", "importance": 5},
        ]

        # LLM only returned 2 evaluations for 3 suggestions
        response = {
            "result": """evaluations:
  - index: 0
    score: 7
    reason: "Good"
  - index: 1
    score: 6
    reason: "Ok"
"""
        }

        result = filter_layer._merge_scores(suggestions, response)

        # First two should have scores
        assert result[0]["llm_score"] == 7
        assert result[1]["llm_score"] == 6
        # Third should have score 0 (mismatch)
        assert result[2]["llm_score"] == 0
        assert "No evaluation" in result[2]["llm_reasoning"]

    @pytest.mark.asyncio
    async def test_prompt_not_found_error(
        self, filter_layer, sample_suggestions, pr_context
    ):
        """Test handling when suggestion_filter_prompt not found."""
        # Mock prompt render to raise KeyError
        with patch.object(
            filter_layer._kit.prompts,
            "render",
            side_effect=KeyError("suggestion_filter_prompt"),
        ):
            result = await filter_layer._evaluate_with_llm(
                sample_suggestions[:2], "diff", pr_context
            )

            # Should fallback to importance
            assert result[0]["llm_score"] == 8
            assert "not available" in result[0]["llm_reasoning"].lower()

    def test_post_filter_with_empty_suggestions(self, filter_layer):
        """Test post-filter handles empty list."""
        result = filter_layer._post_filter([])
        assert result == []

    def test_merge_scores_empty_evaluations(self, filter_layer):
        """Test handling when LLM returns empty evaluations list."""
        suggestions = [{"file": "a.py", "importance": 7}]

        response = {"result": "evaluations: []"}

        result = filter_layer._merge_scores(suggestions, response)

        # Should fallback to importance
        assert result[0]["llm_score"] == 7
        assert "No evaluations" in result[0]["llm_reasoning"]

    def test_assign_comment_types_file_in_pr_and_line_in_diff(self, filter_layer):
        """Test that files in PR with lines in diff get comment_type='inline'."""
        suggestions = [
            {"file": "src/main.py", "line": 10, "suggestion_code": "code"},
            {"file": "src/api.py", "line": 20, "suggestion_code": "code"},
        ]
        pr_files = {"src/main.py", "src/api.py"}
        diff = """diff --git a/src/main.py b/src/main.py
--- a/src/main.py
+++ b/src/main.py
@@ -8,5 +8,7 @@ def main():
     code
diff --git a/src/api.py b/src/api.py
--- a/src/api.py
+++ b/src/api.py
@@ -18,5 +18,7 @@ def api():
     code
"""
        result = filter_layer._assign_comment_types(suggestions, pr_files, diff)

        assert result[0]["comment_type"] == "inline"
        assert result[1]["comment_type"] == "inline"
        # suggestion_code should be preserved for inline
        assert result[0]["suggestion_code"] == "code"
        assert result[1]["suggestion_code"] == "code"

    def test_assign_comment_types_file_not_in_pr(self, filter_layer):
        """Test that files NOT in PR get comment_type='general'."""
        suggestions = [
            {"file": "tests/test_main.py", "line": 50, "suggestion_code": "test code"},
        ]
        pr_files = {"src/main.py"}  # test file not in PR
        diff = """diff --git a/src/main.py b/src/main.py
--- a/src/main.py
+++ b/src/main.py
@@ -8,5 +8,7 @@ def main():
     code
"""
        result = filter_layer._assign_comment_types(suggestions, pr_files, diff)

        assert result[0]["comment_type"] == "general"

    def test_assign_comment_types_clears_code_for_general(self, filter_layer):
        """Test that suggestion_code is cleared for general suggestions."""
        suggestions = [
            {
                "file": "tests/test_main.py",
                "line": 50,
                "suggestion_code": "# some test code",
                "description": "Update test",
            },
        ]
        pr_files = {"src/main.py"}  # test file not in PR
        diff = """diff --git a/src/main.py b/src/main.py
--- a/src/main.py
+++ b/src/main.py
@@ -8,5 +8,7 @@ def main():
     code
"""
        result = filter_layer._assign_comment_types(suggestions, pr_files, diff)

        # suggestion_code should be cleared for general
        assert result[0]["suggestion_code"] is None
        # description should be preserved
        assert result[0]["description"] == "Update test"

    def test_assign_comment_types_mixed(self, filter_layer):
        """Test mixed inline and general suggestions."""
        suggestions = [
            {"file": "src/main.py", "line": 10, "suggestion_code": "code1"},
            {"file": "tests/test_main.py", "line": 50, "suggestion_code": "code2"},
            {"file": "src/api.py", "line": 20, "suggestion_code": "code3"},
        ]
        pr_files = {"src/main.py", "src/api.py"}
        diff = """diff --git a/src/main.py b/src/main.py
--- a/src/main.py
+++ b/src/main.py
@@ -8,5 +8,7 @@ def main():
     code
diff --git a/src/api.py b/src/api.py
--- a/src/api.py
+++ b/src/api.py
@@ -18,5 +18,7 @@ def api():
     code
"""
        result = filter_layer._assign_comment_types(suggestions, pr_files, diff)

        # First and third should be inline
        assert result[0]["comment_type"] == "inline"
        assert result[0]["suggestion_code"] == "code1"

        assert result[2]["comment_type"] == "inline"
        assert result[2]["suggestion_code"] == "code3"

        # Second should be general with cleared code (file not in PR)
        assert result[1]["comment_type"] == "general"
        assert result[1]["suggestion_code"] is None

    @pytest.mark.asyncio
    async def test_apply_with_pr_files(self, filter_layer, pr_context):
        """Test that apply() uses pr_files for routing."""
        suggestions = [
            {"file": "src/main.py", "line": 10, "importance": 8},
            {"file": "tests/test_main.py", "line": 50, "importance": 7},
        ]
        pr_files = {"src/main.py"}
        diff = """diff --git a/src/main.py b/src/main.py
--- a/src/main.py
+++ b/src/main.py
@@ -8,5 +8,7 @@ def main():
     code
"""
        # Mock LLM evaluation
        mock_rendered = MagicMock()
        mock_rendered.system = "System prompt"
        mock_rendered.user = "User prompt"

        with patch.object(
            filter_layer._kit.prompts, "render", return_value=mock_rendered
        ):
            with patch.object(
                filter_layer._claude_tool, "execute", new_callable=AsyncMock
            ) as mock_execute:
                mock_execute.return_value = {
                    "result": """evaluations:
  - index: 0
    score: 8
    reason: "Good"
  - index: 1
    score: 7
    reason: "Test issue"
"""
                }

                result = await filter_layer.apply(
                    suggestions, diff, pr_context, pr_files=pr_files
                )

                # Both should pass filter (score >= 5)
                assert len(result) == 2

                # Check routing
                inline = [s for s in result if s["comment_type"] == "inline"]
                general = [s for s in result if s["comment_type"] == "general"]

                assert len(inline) == 1
                assert inline[0]["file"] == "src/main.py"

                assert len(general) == 1
                assert general[0]["file"] == "tests/test_main.py"

    def test_assign_comment_types_line_not_in_diff(self, filter_layer):
        """Test that lines NOT in diff hunks get comment_type='general'."""
        suggestions = [
            {"file": "src/main.py", "line": 261, "suggestion_code": "code"},
        ]
        pr_files = {"src/main.py"}
        # Diff only covers lines 42-51
        diff = """diff --git a/src/main.py b/src/main.py
--- a/src/main.py
+++ b/src/main.py
@@ -42,6 +42,10 @@ func NewRequest():
     return &Request{}
+    // Added
+    // lines
+    // here
"""
        result = filter_layer._assign_comment_types(suggestions, pr_files, diff)

        # Line 261 is not in the diff hunk (42-51), should be general
        assert result[0]["comment_type"] == "general"
        assert result[0]["suggestion_code"] is None

    def test_assign_comment_types_line_in_diff(self, filter_layer):
        """Test that lines IN diff hunks get comment_type='inline'."""
        suggestions = [
            {"file": "src/main.py", "line": 45, "suggestion_code": "code"},
        ]
        pr_files = {"src/main.py"}
        # Diff covers lines 42-51
        diff = """diff --git a/src/main.py b/src/main.py
--- a/src/main.py
+++ b/src/main.py
@@ -42,6 +42,10 @@ func NewRequest():
     return &Request{}
+    // Added
+    // lines
+    // here
"""
        result = filter_layer._assign_comment_types(suggestions, pr_files, diff)

        # Line 45 is in the diff hunk (42-51), should be inline
        assert result[0]["comment_type"] == "inline"
        assert result[0]["suggestion_code"] == "code"

    def test_assign_comment_types_multiline_range_valid(self, filter_layer):
        """Test multi-line suggestion with valid range."""
        suggestions = [
            {"file": "src/main.py", "line": 42, "line_end": 45, "suggestion_code": "code"},
        ]
        pr_files = {"src/main.py"}
        diff = """diff --git a/src/main.py b/src/main.py
--- a/src/main.py
+++ b/src/main.py
@@ -42,6 +42,10 @@ func NewRequest():
     return &Request{}
"""
        result = filter_layer._assign_comment_types(suggestions, pr_files, diff)

        assert result[0]["comment_type"] == "inline"

    def test_assign_comment_types_multiline_range_invalid(self, filter_layer):
        """Test multi-line suggestion with end line outside diff."""
        suggestions = [
            {"file": "src/main.py", "line": 45, "line_end": 60, "suggestion_code": "code"},
        ]
        pr_files = {"src/main.py"}
        # Diff only covers lines 42-51
        diff = """diff --git a/src/main.py b/src/main.py
--- a/src/main.py
+++ b/src/main.py
@@ -42,6 +42,10 @@ func NewRequest():
     return &Request{}
"""
        result = filter_layer._assign_comment_types(suggestions, pr_files, diff)

        # Line 60 is outside the diff, so should be general
        assert result[0]["comment_type"] == "general"
        assert result[0]["suggestion_code"] is None

    def test_assign_comment_types_empty_diff(self, filter_layer):
        """Test that empty diff routes all to general."""
        suggestions = [
            {"file": "src/main.py", "line": 10, "suggestion_code": "code"},
        ]
        pr_files = {"src/main.py"}

        result = filter_layer._assign_comment_types(suggestions, pr_files, "")

        assert result[0]["comment_type"] == "general"
        assert result[0]["suggestion_code"] is None

    def test_assign_comment_types_file_in_pr_but_no_diff_info(self, filter_layer):
        """Test file in PR but not in diff (binary file or similar)."""
        suggestions = [
            {"file": "image.png", "line": 1, "suggestion_code": "code"},
        ]
        pr_files = {"image.png"}
        # Binary files have no hunks
        diff = """diff --git a/image.png b/image.png
new file mode 100644
Binary files /dev/null and b/image.png differ
"""
        result = filter_layer._assign_comment_types(suggestions, pr_files, diff)

        # Binary file has no valid lines for inline comments
        assert result[0]["comment_type"] == "general"
        assert result[0]["suggestion_code"] is None

    def test_assign_comment_types_file_identical_to_base(self, filter_layer):
        """Test file in PR but identical to base branch (no hunks).

        This happens when a PR is raised but the files are already
        present in the base branch with identical content.
        """
        suggestions = [
            {"file": "src/already_exists.py", "line": 50, "suggestion_code": "code"},
        ]
        pr_files = {"src/already_exists.py"}
        # Diff has file header but no hunks (files are identical)
        diff = """diff --git a/src/already_exists.py b/src/already_exists.py
index abc123..abc123 100644
"""
        result = filter_layer._assign_comment_types(suggestions, pr_files, diff)

        # File is in diff but has no hunks, so all lines route to general
        assert result[0]["comment_type"] == "general"
        assert result[0]["suggestion_code"] is None

    def test_assign_comment_types_mixed_identical_and_changed_files(self, filter_layer):
        """Test mix of identical files and files with actual changes."""
        suggestions = [
            {"file": "src/unchanged.py", "line": 10, "suggestion_code": "code1"},
            {"file": "src/changed.py", "line": 15, "suggestion_code": "code2"},
        ]
        pr_files = {"src/unchanged.py", "src/changed.py"}
        diff = """diff --git a/src/unchanged.py b/src/unchanged.py
index abc123..abc123 100644
diff --git a/src/changed.py b/src/changed.py
index def456..ghi789 100644
--- a/src/changed.py
+++ b/src/changed.py
@@ -10,5 +10,8 @@ def func():
     pass
"""
        result = filter_layer._assign_comment_types(suggestions, pr_files, diff)

        # First file has no hunks (identical) - routes to general
        assert result[0]["comment_type"] == "general"
        assert result[0]["suggestion_code"] is None

        # Second file has hunks and line 15 is valid - routes to inline
        assert result[1]["comment_type"] == "inline"
        assert result[1]["suggestion_code"] == "code2"

    def test_assign_comment_types_pr_with_no_actual_changes(self, filter_layer):
        """Test PR where all files are identical to base (empty diff)."""
        suggestions = [
            {"file": "src/file1.py", "line": 10, "suggestion_code": "code1"},
            {"file": "src/file2.py", "line": 20, "suggestion_code": "code2"},
        ]
        pr_files = {"src/file1.py", "src/file2.py"}
        # Empty diff - no actual changes
        diff = ""

        result = filter_layer._assign_comment_types(suggestions, pr_files, diff)

        # All suggestions should route to general
        assert result[0]["comment_type"] == "general"
        assert result[0]["suggestion_code"] is None
        assert result[1]["comment_type"] == "general"
        assert result[1]["suggestion_code"] is None
