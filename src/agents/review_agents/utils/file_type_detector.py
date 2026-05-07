"""
File type detection utilities for conditional sub-agent execution.

Provides functions to detect file types from unified diffs, enabling
sub-agents to run only when relevant file types are present.
"""

import re
from typing import Set, List


# Common frontend file extensions
FRONTEND_EXTENSIONS: Set[str] = {
    ".js", ".jsx", ".ts", ".tsx",  # JavaScript/TypeScript
    ".css", ".scss", ".sass", ".less",  # Stylesheets
    ".vue", ".svelte",  # Framework-specific
}

# Common backend file extensions
BACKEND_EXTENSIONS: Set[str] = {
    ".py", ".pyx", ".pyi",  # Python
    ".go",  # Go
    ".java",  # Java
    ".rb",  # Ruby
    ".php",  # PHP
    ".rs",  # Rust
}


def extract_file_extensions_from_diff(diff: str) -> Set[str]:
    """
    Extract unique file extensions from a unified diff.

    Parses the diff for file paths and extracts their extensions.
    Uses both +++ and diff --git patterns for robustness.

    Args:
        diff: Unified diff content

    Returns:
        Set of file extensions including the dot (e.g., {".py", ".tsx"})

    Example:
        >>> diff = "+++ b/src/App.tsx\\n+++ b/utils/helper.py"
        >>> extract_file_extensions_from_diff(diff)
        {'.tsx', '.py'}
    """
    files = set()

    # Match +++ b/path/to/file patterns
    plus_pattern = re.compile(r'^\+\+\+ [ab]/(.+)$', re.MULTILINE)
    for match in plus_pattern.finditer(diff):
        files.add(match.group(1))

    # Also match diff --git patterns for robustness
    git_pattern = re.compile(r'^diff --git a/(.+?) b/', re.MULTILINE)
    for match in git_pattern.finditer(diff):
        files.add(match.group(1))

    # Extract extensions
    extensions = set()
    for file_path in files:
        if '.' in file_path:
            # Get the last extension (handles .test.tsx, .config.js, etc.)
            ext = '.' + file_path.rsplit('.', 1)[-1].lower()
            extensions.add(ext)

    return extensions


def extract_files_from_diff(diff: str) -> List[str]:
    """
    Extract file paths from a unified diff.

    Args:
        diff: Unified diff content

    Returns:
        List of file paths found in the diff
    """
    files = set()

    # Match +++ b/path/to/file patterns
    plus_pattern = re.compile(r'^\+\+\+ [ab]/(.+)$', re.MULTILINE)
    for match in plus_pattern.finditer(diff):
        files.add(match.group(1))

    # Also match diff --git patterns for robustness
    git_pattern = re.compile(r'^diff --git a/(.+?) b/', re.MULTILINE)
    for match in git_pattern.finditer(diff):
        files.add(match.group(1))

    return list(files)


def has_files_with_extensions(diff: str, extensions: Set[str]) -> bool:
    """
    Check if a diff contains files with any of the given extensions.

    Args:
        diff: Unified diff content
        extensions: Set of extensions to check for (e.g., {".py", ".go"})

    Returns:
        True if any file in the diff has one of the specified extensions

    Example:
        >>> diff = "+++ b/src/App.tsx"
        >>> has_files_with_extensions(diff, {".tsx", ".jsx"})
        True
    """
    found = extract_file_extensions_from_diff(diff)
    return bool(found & extensions)


def has_frontend_files(diff: str, extensions: Set[str] | None = None) -> bool:
    """
    Check if a diff contains frontend files.

    Uses the default FRONTEND_EXTENSIONS if none specified.

    Args:
        diff: Unified diff content
        extensions: Optional custom set of frontend extensions

    Returns:
        True if any file in the diff is a frontend file

    Example:
        >>> diff = "+++ b/src/components/Button.tsx"
        >>> has_frontend_files(diff)
        True
    """
    if extensions is None:
        extensions = FRONTEND_EXTENSIONS
    return has_files_with_extensions(diff, extensions)


def has_backend_files(diff: str, extensions: Set[str] | None = None) -> bool:
    """
    Check if a diff contains backend files.

    Uses the default BACKEND_EXTENSIONS if none specified.

    Args:
        diff: Unified diff content
        extensions: Optional custom set of backend extensions

    Returns:
        True if any file in the diff is a backend file

    Example:
        >>> diff = "+++ b/src/main.py"
        >>> has_backend_files(diff)
        True
    """
    if extensions is None:
        extensions = BACKEND_EXTENSIONS
    return has_files_with_extensions(diff, extensions)


def get_file_type_summary(diff: str) -> dict:
    """
    Get a summary of file types present in a diff.

    Useful for debugging and logging which file types are detected.

    Args:
        diff: Unified diff content

    Returns:
        Dictionary with file type information

    Example:
        >>> diff = "+++ b/App.tsx\\n+++ b/main.py"
        >>> get_file_type_summary(diff)
        {
            'extensions': {'.tsx', '.py'},
            'has_frontend': True,
            'has_backend': True,
            'file_count': 2
        }
    """
    extensions = extract_file_extensions_from_diff(diff)
    files = extract_files_from_diff(diff)

    return {
        "extensions": extensions,
        "has_frontend": bool(extensions & FRONTEND_EXTENSIONS),
        "has_backend": bool(extensions & BACKEND_EXTENSIONS),
        "file_count": len(files),
    }
