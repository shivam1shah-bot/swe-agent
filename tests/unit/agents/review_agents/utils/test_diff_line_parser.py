"""
Unit tests for diff_line_parser utility.

Tests parsing of unified diff format and line validation.
"""

import pytest

from src.agents.review_agents.utils.diff_line_parser import (
    DiffHunk,
    FileDiffInfo,
    is_line_in_diff,
    parse_unified_diff,
)


class TestDiffHunk:
    """Tests for DiffHunk dataclass."""

    def test_valid_lines_normal_hunk(self):
        """Test valid_lines for a normal hunk."""
        hunk = DiffHunk(new_start=10, new_count=5)
        expected = {10, 11, 12, 13, 14}
        assert hunk.valid_lines == expected

    def test_valid_lines_single_line(self):
        """Test valid_lines for single line hunk."""
        hunk = DiffHunk(new_start=42, new_count=1)
        assert hunk.valid_lines == {42}

    def test_valid_lines_zero_count(self):
        """Test valid_lines for zero count (pure deletion)."""
        hunk = DiffHunk(new_start=10, new_count=0)
        assert hunk.valid_lines == set()


class TestFileDiffInfo:
    """Tests for FileDiffInfo dataclass."""

    @pytest.fixture
    def file_diff_with_hunks(self):
        """Create a FileDiffInfo with multiple hunks."""
        return FileDiffInfo(
            file_path="src/main.py",
            hunks=[
                DiffHunk(new_start=10, new_count=5),   # Lines 10-14
                DiffHunk(new_start=50, new_count=10),  # Lines 50-59
                DiffHunk(new_start=100, new_count=3),  # Lines 100-102
            ],
        )

    def test_is_line_valid_in_first_hunk(self, file_diff_with_hunks):
        """Test line validation for line in first hunk."""
        assert file_diff_with_hunks.is_line_valid(10) is True
        assert file_diff_with_hunks.is_line_valid(12) is True
        assert file_diff_with_hunks.is_line_valid(14) is True

    def test_is_line_valid_in_second_hunk(self, file_diff_with_hunks):
        """Test line validation for line in second hunk."""
        assert file_diff_with_hunks.is_line_valid(50) is True
        assert file_diff_with_hunks.is_line_valid(55) is True
        assert file_diff_with_hunks.is_line_valid(59) is True

    def test_is_line_invalid_between_hunks(self, file_diff_with_hunks):
        """Test line validation for line between hunks."""
        assert file_diff_with_hunks.is_line_valid(15) is False
        assert file_diff_with_hunks.is_line_valid(30) is False
        assert file_diff_with_hunks.is_line_valid(49) is False

    def test_is_line_invalid_before_first_hunk(self, file_diff_with_hunks):
        """Test line validation for line before first hunk."""
        assert file_diff_with_hunks.is_line_valid(1) is False
        assert file_diff_with_hunks.is_line_valid(9) is False

    def test_is_line_invalid_after_last_hunk(self, file_diff_with_hunks):
        """Test line validation for line after last hunk."""
        assert file_diff_with_hunks.is_line_valid(103) is False
        assert file_diff_with_hunks.is_line_valid(200) is False

    def test_is_line_valid_deleted_file(self):
        """Test that deleted files have no valid lines."""
        file_diff = FileDiffInfo(
            file_path="deleted.py",
            hunks=[DiffHunk(new_start=10, new_count=5)],
            is_deleted=True,
        )
        assert file_diff.is_line_valid(10) is False
        assert file_diff.is_line_valid(12) is False

    def test_is_range_valid_fully_within_hunk(self, file_diff_with_hunks):
        """Test range validation when fully within a hunk."""
        assert file_diff_with_hunks.is_range_valid(10, 14) is True
        assert file_diff_with_hunks.is_range_valid(51, 55) is True

    def test_is_range_valid_partial_overlap(self, file_diff_with_hunks):
        """Test range validation when partially overlapping a hunk."""
        # Range starts in hunk but extends beyond
        assert file_diff_with_hunks.is_range_valid(12, 16) is False
        # Range starts before hunk
        assert file_diff_with_hunks.is_range_valid(8, 12) is False

    def test_is_range_valid_spanning_gap(self, file_diff_with_hunks):
        """Test range validation when spanning gap between hunks."""
        # Range spans from first hunk to second hunk
        assert file_diff_with_hunks.is_range_valid(14, 50) is False

    def test_is_range_valid_invalid_range(self, file_diff_with_hunks):
        """Test range validation with inverted range."""
        assert file_diff_with_hunks.is_range_valid(14, 10) is False

    def test_is_range_valid_deleted_file(self):
        """Test range validation on deleted file."""
        file_diff = FileDiffInfo(
            file_path="deleted.py",
            hunks=[DiffHunk(new_start=10, new_count=5)],
            is_deleted=True,
        )
        assert file_diff.is_range_valid(10, 14) is False

    def test_get_valid_ranges(self, file_diff_with_hunks):
        """Test getting valid ranges for logging."""
        ranges = file_diff_with_hunks.get_valid_ranges()
        assert ranges == [(10, 14), (50, 59), (100, 102)]

    def test_get_valid_ranges_empty(self):
        """Test getting valid ranges when no hunks."""
        file_diff = FileDiffInfo(file_path="empty.py", hunks=[])
        assert file_diff.get_valid_ranges() == []


class TestParseUnifiedDiff:
    """Tests for parse_unified_diff function."""

    def test_parse_simple_single_file(self):
        """Test parsing a simple single-file diff."""
        diff = """diff --git a/src/main.py b/src/main.py
index abc123..def456 100644
--- a/src/main.py
+++ b/src/main.py
@@ -10,5 +10,7 @@ def main():
     print("hello")
+    print("new line 1")
+    print("new line 2")
     print("world")
"""
        result = parse_unified_diff(diff)

        assert "src/main.py" in result
        file_info = result["src/main.py"]
        assert len(file_info.hunks) == 1
        assert file_info.hunks[0].new_start == 10
        assert file_info.hunks[0].new_count == 7

    def test_parse_multiple_hunks(self):
        """Test parsing diff with multiple hunks in one file."""
        diff = """diff --git a/src/main.py b/src/main.py
index abc123..def456 100644
--- a/src/main.py
+++ b/src/main.py
@@ -10,3 +10,5 @@ def first():
     pass
+    added
+    lines
@@ -50,4 +52,6 @@ def second():
     code
+    more
+    lines
"""
        result = parse_unified_diff(diff)

        assert "src/main.py" in result
        file_info = result["src/main.py"]
        assert len(file_info.hunks) == 2
        assert file_info.hunks[0].new_start == 10
        assert file_info.hunks[0].new_count == 5
        assert file_info.hunks[1].new_start == 52
        assert file_info.hunks[1].new_count == 6

    def test_parse_multiple_files(self):
        """Test parsing diff with multiple files."""
        diff = """diff --git a/src/main.py b/src/main.py
index abc123..def456 100644
--- a/src/main.py
+++ b/src/main.py
@@ -10,3 +10,5 @@ def main():
     pass
diff --git a/src/api.py b/src/api.py
index 111111..222222 100644
--- a/src/api.py
+++ b/src/api.py
@@ -20,4 +20,8 @@ def api():
     code
"""
        result = parse_unified_diff(diff)

        assert len(result) == 2
        assert "src/main.py" in result
        assert "src/api.py" in result
        assert result["src/main.py"].hunks[0].new_start == 10
        assert result["src/api.py"].hunks[0].new_start == 20

    def test_parse_new_file(self):
        """Test parsing diff for a new file."""
        diff = """diff --git a/src/new_file.py b/src/new_file.py
new file mode 100644
index 0000000..abc1234
--- /dev/null
+++ b/src/new_file.py
@@ -0,0 +1,10 @@
+def new_function():
+    pass
"""
        result = parse_unified_diff(diff)

        assert "src/new_file.py" in result
        file_info = result["src/new_file.py"]
        assert file_info.is_new_file is True
        assert len(file_info.hunks) == 1
        assert file_info.hunks[0].new_start == 1
        assert file_info.hunks[0].new_count == 10

    def test_parse_deleted_file(self):
        """Test parsing diff for a deleted file."""
        diff = """diff --git a/src/old_file.py b/src/old_file.py
deleted file mode 100644
index abc1234..0000000
--- a/src/old_file.py
+++ /dev/null
@@ -1,10 +0,0 @@
-def old_function():
-    pass
"""
        result = parse_unified_diff(diff)

        assert "src/old_file.py" in result
        file_info = result["src/old_file.py"]
        assert file_info.is_deleted is True

    def test_parse_renamed_file(self):
        """Test parsing diff for a renamed file."""
        diff = """diff --git a/old_name.py b/new_name.py
similarity index 95%
rename from old_name.py
rename to new_name.py
index abc123..def456 100644
--- a/old_name.py
+++ b/new_name.py
@@ -10,3 +10,5 @@ def func():
     pass
"""
        result = parse_unified_diff(diff)

        # Should use the new name (from +++ line)
        assert "new_name.py" in result

    def test_parse_single_line_hunk_format(self):
        """Test parsing hunk header without count (defaults to 1)."""
        diff = """diff --git a/src/main.py b/src/main.py
index abc123..def456 100644
--- a/src/main.py
+++ b/src/main.py
@@ -5 +5,3 @@ context
     line
+    added1
+    added2
"""
        result = parse_unified_diff(diff)

        assert "src/main.py" in result
        file_info = result["src/main.py"]
        assert file_info.hunks[0].new_start == 5
        assert file_info.hunks[0].new_count == 3

    def test_parse_empty_diff(self):
        """Test parsing empty diff."""
        result = parse_unified_diff("")
        assert result == {}

    def test_parse_none_diff(self):
        """Test parsing None diff."""
        result = parse_unified_diff(None)
        assert result == {}

    def test_parse_binary_file(self):
        """Test parsing diff with binary file."""
        diff = """diff --git a/image.png b/image.png
new file mode 100644
index 0000000..abc1234
Binary files /dev/null and b/image.png differ
"""
        result = parse_unified_diff(diff)

        # Binary files should have entry but no hunks
        assert "image.png" in result
        assert len(result["image.png"].hunks) == 0


class TestIsLineInDiff:
    """Tests for is_line_in_diff convenience function."""

    @pytest.fixture
    def sample_diff(self):
        """Sample diff for testing."""
        return """diff --git a/src/main.py b/src/main.py
index abc123..def456 100644
--- a/src/main.py
+++ b/src/main.py
@@ -10,5 +10,7 @@ def main():
     print("hello")
+    print("added")
     print("world")
@@ -50,3 +52,5 @@ def other():
     pass
"""

    def test_line_in_diff(self, sample_diff):
        """Test checking valid line."""
        assert is_line_in_diff(sample_diff, "src/main.py", 10) is True
        assert is_line_in_diff(sample_diff, "src/main.py", 14) is True

    def test_line_not_in_diff(self, sample_diff):
        """Test checking invalid line."""
        assert is_line_in_diff(sample_diff, "src/main.py", 20) is False
        assert is_line_in_diff(sample_diff, "src/main.py", 261) is False

    def test_file_not_in_diff(self, sample_diff):
        """Test checking line in file not in diff."""
        assert is_line_in_diff(sample_diff, "other_file.py", 10) is False

    def test_range_valid(self, sample_diff):
        """Test checking valid range."""
        assert is_line_in_diff(sample_diff, "src/main.py", 10, 14) is True

    def test_range_invalid(self, sample_diff):
        """Test checking invalid range."""
        # Range extends beyond hunk
        assert is_line_in_diff(sample_diff, "src/main.py", 14, 20) is False

    def test_empty_diff(self):
        """Test with empty diff."""
        assert is_line_in_diff("", "src/main.py", 10) is False

    def test_none_line_end(self, sample_diff):
        """Test with None line_end."""
        assert is_line_in_diff(sample_diff, "src/main.py", 10, None) is True


class TestEdgeCases:
    """Tests for edge cases and unusual diff formats."""

    def test_file_path_with_spaces(self):
        """Test parsing diff with spaces in file path."""
        diff = """diff --git a/src/my file.py b/src/my file.py
index abc123..def456 100644
--- a/src/my file.py
+++ b/src/my file.py
@@ -10,3 +10,5 @@ def func():
     pass
"""
        result = parse_unified_diff(diff)

        assert "src/my file.py" in result
        assert result["src/my file.py"].hunks[0].new_start == 10

    def test_mode_change_only(self):
        """Test diff with only mode change (no content changes)."""
        diff = """diff --git a/script.sh b/script.sh
old mode 100644
new mode 100755
"""
        result = parse_unified_diff(diff)

        # File should be in result but with no hunks
        assert "script.sh" in result
        assert len(result["script.sh"].hunks) == 0

    def test_no_newline_at_eof(self):
        """Test diff with 'No newline at end of file' marker."""
        diff = """diff --git a/src/main.py b/src/main.py
index abc123..def456 100644
--- a/src/main.py
+++ b/src/main.py
@@ -10,3 +10,4 @@ def main():
     pass
+    added
\\ No newline at end of file
"""
        result = parse_unified_diff(diff)

        assert "src/main.py" in result
        file_info = result["src/main.py"]
        assert file_info.hunks[0].new_start == 10
        assert file_info.hunks[0].new_count == 4

    def test_pure_deletion_hunk(self):
        """Test hunk that only removes lines (new_count=0)."""
        diff = """diff --git a/src/main.py b/src/main.py
index abc123..def456 100644
--- a/src/main.py
+++ b/src/main.py
@@ -10,5 +10,0 @@ def main():
-    line1
-    line2
-    line3
-    line4
-    line5
"""
        result = parse_unified_diff(diff)

        assert "src/main.py" in result
        file_info = result["src/main.py"]
        # Pure deletion has new_count=0, so no valid lines
        assert file_info.hunks[0].new_count == 0
        assert file_info.is_line_valid(10) is False

    def test_unicode_in_diff(self):
        """Test diff with unicode characters in content."""
        diff = """diff --git a/src/i18n.py b/src/i18n.py
index abc123..def456 100644
--- a/src/i18n.py
+++ b/src/i18n.py
@@ -5,3 +5,5 @@ translations = {
     "hello": "Hello",
+    "goodbye": "Goodbye",
+    "thanks": "ありがとう",
 }
"""
        result = parse_unified_diff(diff)

        assert "src/i18n.py" in result
        assert result["src/i18n.py"].hunks[0].new_start == 5

    def test_large_line_numbers(self):
        """Test diff with large line numbers."""
        diff = """diff --git a/large_file.py b/large_file.py
index abc123..def456 100644
--- a/large_file.py
+++ b/large_file.py
@@ -99995,3 +99995,5 @@ def func():
     code
"""
        result = parse_unified_diff(diff)

        assert "large_file.py" in result
        file_info = result["large_file.py"]
        assert file_info.hunks[0].new_start == 99995
        assert file_info.is_line_valid(99997) is True
        assert file_info.is_line_valid(100000) is False

    def test_adjacent_hunks(self):
        """Test hunks that are adjacent (no gap between them)."""
        file_diff = FileDiffInfo(
            file_path="test.py",
            hunks=[
                DiffHunk(new_start=10, new_count=5),   # Lines 10-14
                DiffHunk(new_start=15, new_count=5),   # Lines 15-19 (adjacent)
            ],
        )
        # Line 14 (end of first hunk)
        assert file_diff.is_line_valid(14) is True
        # Line 15 (start of second hunk)
        assert file_diff.is_line_valid(15) is True
        # Range spanning both adjacent hunks should work
        assert file_diff.is_range_valid(10, 19) is True

    def test_single_line_addition(self):
        """Test hunk with single line addition format."""
        diff = """diff --git a/src/main.py b/src/main.py
index abc123..def456 100644
--- a/src/main.py
+++ b/src/main.py
@@ -42 +42 @@ def func():
-    old_line
+    new_line
"""
        result = parse_unified_diff(diff)

        assert "src/main.py" in result
        # When count is omitted, it defaults to 1
        assert result["src/main.py"].hunks[0].new_count == 1

    def test_diff_with_headers_but_no_hunks(self):
        """Test diff where files are identical (headers only, no hunks).

        This happens when a PR is raised but the files are already
        present in the base branch with identical content.
        """
        diff = """diff --git a/src/already_exists.py b/src/already_exists.py
index abc123..abc123 100644
"""
        result = parse_unified_diff(diff)

        # File should be in result but with no hunks
        assert "src/already_exists.py" in result
        assert len(result["src/already_exists.py"].hunks) == 0
        # No lines should be valid
        assert result["src/already_exists.py"].is_line_valid(1) is False
        assert result["src/already_exists.py"].is_line_valid(100) is False

    def test_diff_with_multiple_identical_files(self):
        """Test diff with multiple files that have no changes."""
        diff = """diff --git a/src/file1.py b/src/file1.py
index abc123..abc123 100644
diff --git a/src/file2.py b/src/file2.py
index def456..def456 100644
diff --git a/src/file3.py b/src/file3.py
index 111111..222222 100644
--- a/src/file3.py
+++ b/src/file3.py
@@ -10,3 +10,5 @@ def func():
     pass
"""
        result = parse_unified_diff(diff)

        # All three files should be in result
        assert len(result) == 3
        assert "src/file1.py" in result
        assert "src/file2.py" in result
        assert "src/file3.py" in result

        # First two have no hunks (identical)
        assert len(result["src/file1.py"].hunks) == 0
        assert len(result["src/file2.py"].hunks) == 0

        # Third file has a hunk
        assert len(result["src/file3.py"].hunks) == 1
        assert result["src/file3.py"].is_line_valid(10) is True

    def test_empty_pr_no_changes(self):
        """Test completely empty diff (no files changed at all)."""
        # This is the case when PR has no changes whatsoever
        diff = ""
        result = parse_unified_diff(diff)
        assert result == {}

        # Also test with just whitespace
        diff_whitespace = "   \n\n  \t  \n"
        result_whitespace = parse_unified_diff(diff_whitespace)
        assert result_whitespace == {}


class TestRealWorldDiffExamples:
    """Tests using real-world diff patterns."""

    def test_go_file_diff(self):
        """Test parsing a Go file diff."""
        diff = """diff --git a/internal/request/request.go b/internal/request/request.go
index 7b8f9a1..c4d2e3f 100644
--- a/internal/request/request.go
+++ b/internal/request/request.go
@@ -42,6 +42,10 @@ func NewRequest(ctx context.Context) *Request {
     return &Request{
         ctx: ctx,
     }
+    // Added validation
+    if ctx == nil {
+        return nil
+    }
 }
"""
        result = parse_unified_diff(diff)

        assert "internal/request/request.go" in result
        file_info = result["internal/request/request.go"]
        assert file_info.hunks[0].new_start == 42
        assert file_info.hunks[0].new_count == 10

        # Line 42-51 should be valid
        for line in range(42, 52):
            assert file_info.is_line_valid(line) is True

        # Line 261 (from the original bug) should NOT be valid
        assert file_info.is_line_valid(261) is False

    def test_multi_hunk_python_diff(self):
        """Test parsing Python diff with multiple hunks."""
        diff = """diff --git a/src/service.py b/src/service.py
index abc123..def456 100644
--- a/src/service.py
+++ b/src/service.py
@@ -15,7 +15,9 @@ class Service:
     def __init__(self):
         self.config = {}
+        self.cache = {}
         self.initialized = False
+        self.logger = None

     def start(self):
@@ -100,4 +102,8 @@ class Service:
     def stop(self):
         self.initialized = False
+        self.cache.clear()
+        if self.logger:
+            self.logger.info("Service stopped")
"""
        result = parse_unified_diff(diff)

        file_info = result["src/service.py"]
        assert len(file_info.hunks) == 2

        # First hunk: lines 15-23
        assert file_info.is_line_valid(15) is True
        assert file_info.is_line_valid(23) is True
        assert file_info.is_line_valid(24) is False

        # Gap between hunks
        assert file_info.is_line_valid(50) is False

        # Second hunk: lines 102-109
        assert file_info.is_line_valid(102) is True
        assert file_info.is_line_valid(109) is True
        assert file_info.is_line_valid(110) is False
