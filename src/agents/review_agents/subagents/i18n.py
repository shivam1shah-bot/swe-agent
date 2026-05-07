"""
I18n sub-agent for detecting internationalization issues in PR code changes.

This sub-agent specializes in detecting i18n/l10n violations using
the i18n-anomaly-detection skill. It analyzes code for hardcoded locale-specific
values that should use localization utilities.
"""

import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Template
from pr_prompt_kit import RenderedPrompt, parse_yaml

from src.agents.review_agents.constants import CATEGORY_LABELS, SubAgentCategory
from src.agents.review_agents.subagent_base import ReviewSubAgentBase
from src.agents.review_agents.subagent_registry import SubAgentRegistry

# Handle TOML parsing for different Python versions
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        import toml as tomllib

logger = logging.getLogger(__name__)


class I18nSubAgent(ReviewSubAgentBase):
    """
    Sub-agent specialized in detecting internationalization issues.

    Analyzes code changes for:
    - Hardcoded currency symbols ($, EUR, etc.) without locale-aware formatting
    - Hardcoded date/time formats (MM/DD/YYYY) without localization
    - Hardcoded timezone assumptions (UTC, IST)
    - Hardcoded phone number formats without country code handling
    - Hardcoded postal code validation for specific countries
    - Hardcoded country/region codes or assumptions
    - Missing localization keys (hardcoded strings)
    - Hardcoded address formats
    - Hardcoded measurement units (metric vs imperial)
    - Missing UTF-8/encoding support

    Uses the i18n-anomaly-detection skill with prompt template from:
    .claude/skills/review-helpers/i18n-anomaly-detection/references/prompt.toml
    """

    @property
    def category(self) -> str:
        """Return the category identifier for this sub-agent."""
        return SubAgentCategory.I18N.value

    @property
    def category_label(self) -> str:
        """Return the label for GitHub comments."""
        return CATEGORY_LABELS[SubAgentCategory.I18N.value]

    def _render_prompt(
        self,
        diff: str,
        pr_number: int,
        repository: str,
        title: str,
        description: str,
        branch: str,
        **kwargs: Any,
    ) -> RenderedPrompt:
        """
        Render the i18n detection prompt using the skill prompt template.

        Reads the prompt from .claude/skills/review-helpers/i18n-anomaly-detection/references/prompt.toml
        and renders Jinja2 templates with PR variables.

        Args:
            diff: The PR diff content
            pr_number: Pull request number
            repository: Repository in owner/name format
            title: PR title
            description: PR description/body
            branch: Source branch name
            **kwargs: Additional variables (e.g., confidence_threshold, context_enabled, context_blob)

        Returns:
            RenderedPrompt with i18n system and user prompts
        """
        # Locate the skill prompt template
        # This file is at: /app/src/agents/review_agents/subagents/i18n.py
        # We need to go up to /app (the project root)
        current_file = Path(__file__)
        swe_agent_root = current_file.parent.parent.parent.parent.parent
        skill_prompt_path = (
            swe_agent_root
            / ".claude"
            / "skills"
            / "review-helpers"
            / "i18n-anomaly-detection"
            / "references"
            / "prompt.toml"
        )

        if not skill_prompt_path.exists():
            logger.error(f"Skill prompt not found at {skill_prompt_path}")
            raise FileNotFoundError(f"i18n skill prompt not found: {skill_prompt_path}")

        # Read and parse TOML file
        try:
            with open(skill_prompt_path, "rb") as f:
                prompt_config = tomllib.load(f)
        except Exception as e:
            logger.error(f"Failed to parse TOML file: {e}")
            raise ValueError(f"Invalid TOML format in {skill_prompt_path}: {e}")

        # Extract i18n_analysis_prompt section
        if "i18n_analysis_prompt" not in prompt_config:
            raise ValueError("TOML file missing [i18n_analysis_prompt] section")

        analysis_prompt = prompt_config["i18n_analysis_prompt"]
        system_template_str = analysis_prompt.get("system", "")
        user_template_str = analysis_prompt.get("user", "")

        if not system_template_str or not user_template_str:
            raise ValueError("TOML file missing 'system' or 'user' prompts")

        # Prepare variables for Jinja2 template rendering
        language = self._detect_primary_language(diff)
        template_vars = {
            "repository": repository,
            "pr_number": pr_number,
            "title": title,
            "description": description or "",
            "branch": branch,
            "diff": diff,
            "language": language,
            "confidence_threshold": kwargs.get("confidence_threshold", 0.8),
            "context_enabled": kwargs.get("context_enabled", False),
            "context_blob": kwargs.get("context_blob", ""),
        }

        # Render Jinja2 templates
        try:
            system_template = Template(system_template_str)
            user_template = Template(user_template_str)

            system_prompt = system_template.render(**template_vars)
            user_prompt = user_template.render(**template_vars)
        except Exception as e:
            logger.error(f"Failed to render Jinja2 templates: {e}")
            raise ValueError(f"Template rendering error: {e}")

        logger.info(
            f"I18nSubAgent using skill prompt template for {repository}#{pr_number}"
        )

        return RenderedPrompt(
            system=system_prompt,
            user=user_prompt,
            name="i18n_skill_prompt",
        )

    def _detect_primary_language(self, diff: str) -> str:
        """
        Detect the primary programming language from diff file extensions.

        Scans file paths in the diff and counts extensions to determine
        the most common language being modified.

        Args:
            diff: The PR diff content

        Returns:
            Primary language name (defaults to "javascript" if not detected)
        """
        # Extract file paths from diff headers
        file_paths = re.findall(r'\+\+\+ b/(.+)', diff)

        extension_counts: Dict[str, int] = {}
        extension_to_lang = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".jsx": "javascript",
            ".go": "go",
            ".java": "java",
            ".rb": "ruby",
            ".rs": "rust",
            ".php": "php",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
            ".cs": "csharp",
        }

        for path in file_paths:
            for ext, lang in extension_to_lang.items():
                if path.endswith(ext):
                    extension_counts[lang] = extension_counts.get(lang, 0) + 1
                    break

        if not extension_counts:
            return "javascript"

        return max(extension_counts, key=extension_counts.get)

    def _parse_response(self, response_text: str) -> List[Dict[str, Any]]:
        """
        Parse the i18n response into standard suggestion format.

        Expected output format from skill prompt:
        suggestions:
          - file: "path/to/file"
            line: 5
            line_end: 10 (optional)
            description: "Clear description of the issue"
            existing_code: |
              <code>
            suggestion_code: |
              <fixed code>
            importance: 10
            confidence: 0.95

        The description should be a clear, concise explanation without any suffix.
        The [CATEGORY, importance: X] suffix is added by the PR comment formatter.

        Args:
            response_text: Raw YAML response from Claude

        Returns:
            List of suggestion dictionaries in standard format
        """
        if not response_text or not response_text.strip():
            logger.warning("I18nSubAgent received empty response")
            return []

        try:
            parsed = parse_yaml(response_text)

            if parsed is None:
                logger.warning("I18nSubAgent parse_yaml returned None")
                return []

            # Parse standard format: suggestions: [...]
            suggestions = parsed.get("suggestions", [])

            if not isinstance(suggestions, list):
                logger.warning(
                    f"I18nSubAgent expected suggestions list, got {type(suggestions).__name__}"
                )
                return []

            # Process each suggestion
            for s in suggestions:
                if not isinstance(s, dict):
                    continue

                # Add category label if missing
                if "category" not in s:
                    s["category"] = self.category_label

            logger.info(f"I18nSubAgent parsed {len(suggestions)} suggestions")
            return suggestions

        except Exception as e:
            logger.warning(f"I18nSubAgent failed to parse response: {e}")
            preview = response_text[:500] if len(response_text) > 500 else response_text
            logger.debug(f"Response preview: {preview}")
            return []


# Auto-register on module import
SubAgentRegistry.register(SubAgentCategory.I18N.value, I18nSubAgent)
