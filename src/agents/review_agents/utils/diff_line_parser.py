"""
Utility for parsing unified diff and extracting valid line ranges.

This module parses git unified diff format to determine which lines
are valid for posting inline GitHub review comments.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class DiffHunk:
    """Represents a single hunk in a unified diff.

    A hunk defines a contiguous section of changes in a file.
    The new_start and new_count define which lines in the new version
    are part of this hunk.
    """

    new_start: int  # Starting line in new file
    new_count: int  # Number of lines in hunk

    @property
    def valid_lines(self) -> Set[int]:
        """Get the set of valid line numbers for this hunk.

        Returns:
            Set of line numbers that are part of this hunk.
        """
        if self.new_count == 0:
            return set()
        return set(range(self.new_start, self.new_start + self.new_count))


@dataclass
class FileDiffInfo:
    """Represents diff information for a single file.

    Tracks all hunks for a file and provides methods to check
    if specific lines are valid for inline comments.
    """

    file_path: str
    hunks: List[DiffHunk] = field(default_factory=list)
    is_new_file: bool = False
    is_deleted: bool = False

    def is_line_valid(self, line: int) -> bool:
        """Check if a line number is valid for inline comments.

        Args:
            line: The line number to check.

        Returns:
            True if the line is within any hunk, False otherwise.
        """
        if self.is_deleted:
            return False
        return any(line in hunk.valid_lines for hunk in self.hunks)

    def is_range_valid(self, start: int, end: int) -> bool:
        """Check if a line range is valid for inline comments.

        For a range to be valid, ALL lines in the range must be
        within valid hunks. This ensures multi-line comments
        don't reference lines outside the diff.

        Args:
            start: Start line number (inclusive).
            end: End line number (inclusive).

        Returns:
            True if all lines in range are valid, False otherwise.
        """
        if self.is_deleted:
            return False
        if start > end:
            return False

        # All lines in range must be valid
        for line in range(start, end + 1):
            if not self.is_line_valid(line):
                return False
        return True

    def get_valid_ranges(self) -> List[tuple]:
        """Get list of valid line ranges for this file.

        Returns:
            List of (start, end) tuples representing valid ranges.
        """
        ranges = []
        for hunk in self.hunks:
            if hunk.new_count > 0:
                ranges.append((hunk.new_start, hunk.new_start + hunk.new_count - 1))
        return ranges


# Regex patterns for parsing unified diff
# Matches: diff --git a/path/to/file b/path/to/file
DIFF_GIT_PATTERN = re.compile(r"^diff --git a/(.*) b/(.*)$")

# Matches: +++ b/path/to/file
NEW_FILE_PATTERN = re.compile(r"^\+\+\+ b/(.*)$")

# Matches: @@ -old_start,old_count +new_start,new_count @@
# or: @@ -old_start +new_start,new_count @@ (single line removal)
# or: @@ -old_start,old_count +new_start @@ (single line addition)
HUNK_HEADER_PATTERN = re.compile(
    r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@"
)

# Matches: new file mode
NEW_FILE_MODE_PATTERN = re.compile(r"^new file mode")

# Matches: deleted file mode
DELETED_FILE_MODE_PATTERN = re.compile(r"^deleted file mode")

# Matches: Binary files differ
BINARY_FILE_PATTERN = re.compile(r"^Binary files .* differ$")


def parse_unified_diff(diff: str) -> Dict[str, FileDiffInfo]:
    """Parse a unified diff and extract file/line information.

    Parses git unified diff format to identify:
    - Which files are in the diff
    - Which line ranges are valid for inline comments
    - Whether files are new, deleted, or binary

    Args:
        diff: The unified diff content as a string.

    Returns:
        Dictionary mapping file paths to FileDiffInfo objects.
    """
    if not diff:
        return {}

    result: Dict[str, FileDiffInfo] = {}
    current_file: Optional[str] = None
    current_file_info: Optional[FileDiffInfo] = None

    lines = diff.split("\n")

    for line in lines:
        # Check for new diff section (new file in diff)
        git_match = DIFF_GIT_PATTERN.match(line)
        if git_match:
            # Save previous file if exists
            if current_file and current_file_info:
                result[current_file] = current_file_info

            # Extract the new filename (after rename, b/ version)
            current_file = git_match.group(2)
            current_file_info = FileDiffInfo(file_path=current_file)
            continue

        # Check for new file mode
        if NEW_FILE_MODE_PATTERN.match(line):
            if current_file_info:
                current_file_info.is_new_file = True
            continue

        # Check for deleted file mode
        if DELETED_FILE_MODE_PATTERN.match(line):
            if current_file_info:
                current_file_info.is_deleted = True
            continue

        # Check for binary file
        if BINARY_FILE_PATTERN.match(line):
            # Binary files have no valid lines for inline comments
            continue

        # Check for +++ line (confirms new filename, handles renames)
        new_file_match = NEW_FILE_PATTERN.match(line)
        if new_file_match:
            new_path = new_file_match.group(1)
            # Update file path if different (handles renames)
            if current_file_info and new_path != current_file:
                current_file = new_path
                current_file_info.file_path = new_path
            continue

        # Parse hunk header
        hunk_match = HUNK_HEADER_PATTERN.match(line)
        if hunk_match and current_file_info:
            # Parse new file start and count
            new_start = int(hunk_match.group(3))
            # If count is not specified, it defaults to 1
            new_count_str = hunk_match.group(4)
            new_count = int(new_count_str) if new_count_str else 1

            hunk = DiffHunk(new_start=new_start, new_count=new_count)
            current_file_info.hunks.append(hunk)
            continue

    # Save the last file
    if current_file and current_file_info:
        result[current_file] = current_file_info

    return result


def is_line_in_diff(
    diff: str,
    file_path: str,
    line: int,
    line_end: Optional[int] = None,
) -> bool:
    """Check if a line (or range) is valid for inline comments.

    This is a convenience function that parses the diff and checks
    if the specified line(s) are within valid hunks.

    Args:
        diff: The unified diff content.
        file_path: The file path to check.
        line: The line number to check.
        line_end: Optional end line for range check.

    Returns:
        True if the line(s) are valid for inline comments.
    """
    if not diff:
        return False

    diff_info = parse_unified_diff(diff)
    file_diff = diff_info.get(file_path)

    if not file_diff:
        return False

    if line_end and line_end > line:
        return file_diff.is_range_valid(line, line_end)
    else:
        return file_diff.is_line_valid(line)
