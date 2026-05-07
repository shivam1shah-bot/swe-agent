"""
Unit tests for file type detection utilities.

Tests the file_type_detector module used for conditional sub-agent execution
based on file types present in PR diffs.
"""

import pytest

from src.agents.review_agents.utils.file_type_detector import (
    BACKEND_EXTENSIONS,
    FRONTEND_EXTENSIONS,
    extract_file_extensions_from_diff,
    extract_files_from_diff,
    get_file_type_summary,
    has_backend_files,
    has_files_with_extensions,
    has_frontend_files,
)


class TestExtractFileExtensionsFromDiff:
    """Test extract_file_extensions_from_diff function."""

    def test_extracts_single_extension(self):
        """Test extraction of a single file extension."""
        diff = "+++ b/src/App.tsx"
        result = extract_file_extensions_from_diff(diff)
        assert result == {".tsx"}

    def test_extracts_multiple_extensions(self):
        """Test extraction of multiple file extensions."""
        diff = """+++ b/src/App.tsx
+++ b/utils/helper.py
+++ b/styles/main.css"""
        result = extract_file_extensions_from_diff(diff)
        assert result == {".tsx", ".py", ".css"}

    def test_handles_git_diff_pattern(self):
        """Test extraction from diff --git pattern."""
        diff = "diff --git a/src/index.js b/src/index.js"
        result = extract_file_extensions_from_diff(diff)
        assert result == {".js"}

    def test_handles_both_patterns(self):
        """Test extraction from both +++ and diff --git patterns."""
        diff = """diff --git a/src/main.py b/src/main.py
+++ b/src/main.py
diff --git a/utils/helper.go b/utils/helper.go
+++ b/utils/helper.go"""
        result = extract_file_extensions_from_diff(diff)
        assert result == {".py", ".go"}

    def test_returns_empty_for_no_files(self):
        """Test empty set when no files in diff."""
        diff = "some random text without file patterns"
        result = extract_file_extensions_from_diff(diff)
        assert result == set()

    def test_handles_nested_extensions(self):
        """Test handling of files with multiple dots like .test.tsx."""
        diff = "+++ b/src/App.test.tsx"
        result = extract_file_extensions_from_diff(diff)
        assert result == {".tsx"}  # Should get last extension

    def test_lowercases_extensions(self):
        """Test that extensions are lowercased."""
        diff = "+++ b/src/Component.TSX"
        result = extract_file_extensions_from_diff(diff)
        assert result == {".tsx"}

    def test_handles_files_without_extensions(self):
        """Test handling of files without extensions like Makefile."""
        diff = "+++ b/Makefile"
        result = extract_file_extensions_from_diff(diff)
        assert result == set()


class TestExtractFilesFromDiff:
    """Test extract_files_from_diff function."""

    def test_extracts_file_paths(self):
        """Test extraction of file paths."""
        diff = """+++ b/src/App.tsx
+++ b/utils/helper.py"""
        result = extract_files_from_diff(diff)
        assert set(result) == {"src/App.tsx", "utils/helper.py"}

    def test_deduplicates_files(self):
        """Test that duplicate files are deduplicated."""
        diff = """diff --git a/src/main.py b/src/main.py
+++ b/src/main.py"""
        result = extract_files_from_diff(diff)
        assert len(result) == 1
        assert "src/main.py" in result


class TestHasFilesWithExtensions:
    """Test has_files_with_extensions function."""

    def test_returns_true_when_extension_present(self):
        """Test returns True when matching extension is present."""
        diff = "+++ b/src/App.tsx"
        assert has_files_with_extensions(diff, {".tsx"}) is True

    def test_returns_true_when_any_extension_matches(self):
        """Test returns True when any extension matches."""
        diff = "+++ b/src/App.tsx"
        assert has_files_with_extensions(diff, {".js", ".jsx", ".tsx"}) is True

    def test_returns_false_when_no_extension_matches(self):
        """Test returns False when no extension matches."""
        diff = "+++ b/src/main.py"
        assert has_files_with_extensions(diff, {".tsx", ".jsx"}) is False

    def test_returns_false_for_empty_diff(self):
        """Test returns False for empty diff."""
        diff = ""
        assert has_files_with_extensions(diff, {".py"}) is False


class TestHasFrontendFiles:
    """Test has_frontend_files function."""

    def test_detects_tsx_files(self):
        """Test detection of .tsx files."""
        diff = "+++ b/src/components/Button.tsx"
        assert has_frontend_files(diff) is True

    def test_detects_jsx_files(self):
        """Test detection of .jsx files."""
        diff = "+++ b/src/App.jsx"
        assert has_frontend_files(diff) is True

    def test_detects_js_files(self):
        """Test detection of .js files."""
        diff = "+++ b/src/utils/helpers.js"
        assert has_frontend_files(diff) is True

    def test_detects_ts_files(self):
        """Test detection of .ts files."""
        diff = "+++ b/src/types/index.ts"
        assert has_frontend_files(diff) is True

    def test_detects_css_files(self):
        """Test detection of .css files."""
        diff = "+++ b/styles/main.css"
        assert has_frontend_files(diff) is True

    def test_detects_scss_files(self):
        """Test detection of .scss files."""
        diff = "+++ b/styles/theme.scss"
        assert has_frontend_files(diff) is True

    def test_returns_false_for_backend_only(self):
        """Test returns False for backend-only files."""
        diff = """+++ b/src/main.py
+++ b/pkg/handler.go"""
        assert has_frontend_files(diff) is False

    def test_returns_true_for_mixed_files(self):
        """Test returns True when mixed frontend and backend files."""
        diff = """+++ b/src/main.py
+++ b/ui/App.tsx"""
        assert has_frontend_files(diff) is True

    def test_uses_custom_extensions(self):
        """Test using custom frontend extensions."""
        diff = "+++ b/src/main.py"
        custom_extensions = {".py"}  # Treat Python as "frontend" for this test
        assert has_frontend_files(diff, custom_extensions) is True

    def test_default_extensions_include_expected(self):
        """Test that default FRONTEND_EXTENSIONS includes expected values."""
        assert ".js" in FRONTEND_EXTENSIONS
        assert ".jsx" in FRONTEND_EXTENSIONS
        assert ".ts" in FRONTEND_EXTENSIONS
        assert ".tsx" in FRONTEND_EXTENSIONS
        assert ".css" in FRONTEND_EXTENSIONS
        assert ".scss" in FRONTEND_EXTENSIONS


class TestHasBackendFiles:
    """Test has_backend_files function."""

    def test_detects_python_files(self):
        """Test detection of .py files."""
        diff = "+++ b/src/main.py"
        assert has_backend_files(diff) is True

    def test_detects_go_files(self):
        """Test detection of .go files."""
        diff = "+++ b/pkg/handler.go"
        assert has_backend_files(diff) is True

    def test_returns_false_for_frontend_only(self):
        """Test returns False for frontend-only files."""
        diff = """+++ b/src/App.tsx
+++ b/styles/main.css"""
        assert has_backend_files(diff) is False

    def test_default_extensions_include_expected(self):
        """Test that default BACKEND_EXTENSIONS includes expected values."""
        assert ".py" in BACKEND_EXTENSIONS
        assert ".go" in BACKEND_EXTENSIONS
        assert ".java" in BACKEND_EXTENSIONS


class TestGetFileTypeSummary:
    """Test get_file_type_summary function."""

    def test_returns_complete_summary(self):
        """Test that summary includes all expected fields."""
        diff = """+++ b/src/App.tsx
+++ b/src/main.py"""
        result = get_file_type_summary(diff)

        assert "extensions" in result
        assert "has_frontend" in result
        assert "has_backend" in result
        assert "file_count" in result

    def test_detects_frontend_and_backend(self):
        """Test detection of both frontend and backend files."""
        diff = """+++ b/src/App.tsx
+++ b/src/main.py"""
        result = get_file_type_summary(diff)

        assert result["has_frontend"] is True
        assert result["has_backend"] is True
        assert result["file_count"] == 2
        assert ".tsx" in result["extensions"]
        assert ".py" in result["extensions"]

    def test_frontend_only_summary(self):
        """Test summary for frontend-only diff."""
        diff = "+++ b/src/App.tsx"
        result = get_file_type_summary(diff)

        assert result["has_frontend"] is True
        assert result["has_backend"] is False
        assert result["file_count"] == 1

    def test_backend_only_summary(self):
        """Test summary for backend-only diff."""
        diff = "+++ b/src/main.py"
        result = get_file_type_summary(diff)

        assert result["has_frontend"] is False
        assert result["has_backend"] is True
        assert result["file_count"] == 1

    def test_empty_diff_summary(self):
        """Test summary for empty diff."""
        diff = ""
        result = get_file_type_summary(diff)

        assert result["has_frontend"] is False
        assert result["has_backend"] is False
        assert result["file_count"] == 0
        assert result["extensions"] == set()


class TestRealWorldDiffScenarios:
    """Test with realistic PR diff scenarios."""

    def test_typical_frontend_pr_diff(self):
        """Test detection in a typical frontend PR diff."""
        diff = """diff --git a/ui/src/components/Button/Button.tsx b/ui/src/components/Button/Button.tsx
index 1234567..abcdefg 100644
--- a/ui/src/components/Button/Button.tsx
+++ b/ui/src/components/Button/Button.tsx
@@ -1,5 +1,10 @@
 import React from 'react';
+import { Button as BladeButton } from '@razorpay/blade/components';

 export const Button = () => {
-  return <button>Click me</button>;
+  return <BladeButton>Click me</BladeButton>;
 };
diff --git a/ui/src/components/Button/Button.test.tsx b/ui/src/components/Button/Button.test.tsx
+++ b/ui/src/components/Button/Button.test.tsx
@@ -0,0 +1,10 @@
+import { render } from '@testing-library/react';
+import { Button } from './Button';
"""
        assert has_frontend_files(diff) is True
        assert has_backend_files(diff) is False

        summary = get_file_type_summary(diff)
        assert summary["has_frontend"] is True
        assert summary["file_count"] == 2

    def test_typical_backend_pr_diff(self):
        """Test detection in a typical backend PR diff."""
        diff = """diff --git a/src/handlers/user.py b/src/handlers/user.py
--- a/src/handlers/user.py
+++ b/src/handlers/user.py
@@ -1,5 +1,10 @@
 from fastapi import APIRouter

 router = APIRouter()

 @router.get("/users")
-def get_users():
+async def get_users():
     return []
"""
        assert has_backend_files(diff) is True
        assert has_frontend_files(diff) is False

    def test_full_stack_pr_diff(self):
        """Test detection in a full-stack PR diff."""
        diff = """diff --git a/api/src/main.py b/api/src/main.py
+++ b/api/src/main.py
@@ -1 +1 @@
-old
+new
diff --git a/ui/src/App.tsx b/ui/src/App.tsx
+++ b/ui/src/App.tsx
@@ -1 +1 @@
-old
+new
"""
        assert has_frontend_files(diff) is True
        assert has_backend_files(diff) is True

        summary = get_file_type_summary(diff)
        assert summary["has_frontend"] is True
        assert summary["has_backend"] is True
        assert summary["file_count"] == 2
