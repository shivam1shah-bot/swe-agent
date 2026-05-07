"""
Language detection from file extensions for style guide selection.

Maps file extensions to pr-prompt-kit supported style guide languages.
"""

from typing import Dict, Set, List

from src.agents.review_agents.utils.file_type_detector import extract_files_from_diff

# Mapping of file extensions to pr-prompt-kit language names
EXTENSION_TO_LANGUAGE: Dict[str, str] = {
    # Python
    ".py": "python",
    ".pyx": "python",
    ".pyi": "python",

    # JavaScript
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",

    # Go
    ".go": "go",

    # React (TypeScript/JavaScript with JSX)
    ".jsx": "react",
    ".tsx": "react",
    ".ts": "javascript",  # Plain TS uses JS guidelines
}

# Languages supported by pr-prompt-kit style guides
SUPPORTED_LANGUAGES: Set[str] = {"python", "go", "javascript", "react"}


def detect_languages_from_diff(diff: str) -> Set[str]:
    """
    Detect programming languages from file extensions in a diff.

    Args:
        diff: Unified diff content

    Returns:
        Set of detected language names supported by pr-prompt-kit
    """
    files = extract_files_from_diff(diff)
    languages = set()

    for file_path in files:
        # Get file extension (including the dot)
        if '.' in file_path:
            ext = '.' + file_path.rsplit('.', 1)[-1].lower()
            language = EXTENSION_TO_LANGUAGE.get(ext)
            if language and language in SUPPORTED_LANGUAGES:
                languages.add(language)

    return languages


def detect_languages_from_files(file_paths: List[str]) -> Set[str]:
    """
    Detect programming languages from a list of file paths.

    Args:
        file_paths: List of file paths

    Returns:
        Set of detected language names supported by pr-prompt-kit
    """
    languages = set()

    for file_path in file_paths:
        if '.' in file_path:
            ext = '.' + file_path.rsplit('.', 1)[-1].lower()
            language = EXTENSION_TO_LANGUAGE.get(ext)
            if language and language in SUPPORTED_LANGUAGES:
                languages.add(language)

    return languages
