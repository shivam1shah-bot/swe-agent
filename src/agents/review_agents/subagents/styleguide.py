"""
StyleGuide sub-agent for reviewing code against language-specific style guidelines.

Uses pr-prompt-kit's style guides to analyze code for:
- Naming conventions
- Code formatting issues
- Idiomatic patterns
- Language-specific best practices
"""

import logging
from typing import Any, List, Set

from jinja2 import Template
from pr_prompt_kit import RenderedPrompt

from src.agents.review_agents.constants import CATEGORY_LABELS, SubAgentCategory
from src.agents.review_agents.subagent_base import ReviewSubAgentBase
from src.agents.review_agents.subagent_registry import SubAgentRegistry
from src.agents.review_agents.utils.language_detector import (
    detect_languages_from_diff,
    SUPPORTED_LANGUAGES,
)

logger = logging.getLogger(__name__)


class StyleGuideSubAgent(ReviewSubAgentBase):
    """
    Sub-agent specialized in style guide compliance review.

    Analyzes code changes for:
    - Naming convention violations (snake_case, camelCase, etc.)
    - Code formatting issues
    - Idiomatic pattern violations
    - Language-specific best practices
    - Documentation style compliance

    Detects languages from file extensions in the PR diff and applies
    the appropriate style guides from pr-prompt-kit. Each style guide
    is a complete, self-contained prompt with role, category enforcement,
    rules, and output format.
    """

    @property
    def category(self) -> str:
        """Return the category identifier for this sub-agent."""
        return SubAgentCategory.STYLE.value

    @property
    def category_label(self) -> str:
        """Return the label for GitHub comments."""
        return CATEGORY_LABELS[SubAgentCategory.STYLE.value]

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
        Build prompt using pr-prompt-kit style guides directly.

        Style guides are complete, self-contained prompts that define:
        - Role as a style guide sub-agent
        - Category enforcement (STYLE_VIOLATION only)
        - Language-specific style rules
        - Output format specification

        This method:
        1. Detects languages from file extensions in the diff
        2. Fetches style guides for detected languages
        3. Renders Jinja templates with confidence_threshold
        4. Builds system prompt from combined style guides
        5. Creates user prompt with PR context and diff

        Args:
            diff: The PR diff content
            pr_number: Pull request number
            repository: Repository in owner/name format
            title: PR title
            description: PR description/body
            branch: Source branch name
            **kwargs: Additional variables

        Returns:
            RenderedPrompt with style guide system prompt and diff user prompt
        """
        # Detect languages from file extensions in the diff
        detected_languages = detect_languages_from_diff(diff)

        # Log detected languages
        if detected_languages:
            logger.info(
                f"StyleGuide[{self.category}] detected languages: "
                f"{', '.join(sorted(detected_languages))}"
            )
        else:
            logger.warning(
                f"StyleGuide[{self.category}] no supported languages detected, "
                f"using fallback (python). Supported: {SUPPORTED_LANGUAGES}"
            )
            # Fallback to python if no languages detected
            detected_languages = {"python"}

        # Get style guides from pr-prompt-kit
        guides = self._get_style_guides(detected_languages)

        # Build system prompt from style guides
        system_prompt = self._build_system_prompt(detected_languages, guides)

        # Build user prompt with PR context
        user_prompt = self._build_user_prompt(
            diff=diff,
            pr_number=pr_number,
            repository=repository,
            title=title,
            description=description,
            branch=branch,
        )

        return RenderedPrompt(
            system=system_prompt,
            user=user_prompt,
            name=f"style_guide_{'-'.join(sorted(detected_languages))}",
        )

    def _get_style_guides(self, languages: Set[str]) -> List[Any]:
        """
        Get style guides from pr-prompt-kit for detected languages.

        Args:
            languages: Set of detected language names

        Returns:
            List of StyleGuide objects from pr-prompt-kit
        """
        guides: List[Any] = []

        for lang in sorted(languages):
            try:
                guide = self._kit.prompts.get_style_guide(lang)
                if guide:
                    guides.append(guide)
                    logger.debug(
                        f"StyleGuide[{self.category}] loaded {lang} style guide"
                    )
            except Exception as e:
                logger.warning(
                    f"StyleGuide[{self.category}] failed to load {lang} style guide: {e}"
                )

        return guides

    def _build_system_prompt(
        self, languages: Set[str], guides: List[Any]
    ) -> str:
        """
        Build system prompt by combining style guides for detected languages.

        Each style guide content is rendered with Jinja to substitute
        the confidence_threshold variable.

        Args:
            languages: Set of detected language names
            guides: List of StyleGuide objects from pr-prompt-kit

        Returns:
            Combined system prompt with all applicable style guides
        """
        if not guides:
            raise RuntimeError(
                f"StyleGuide[{self.category}] failed to load any style guides from "
                f"pr-prompt-kit. Check that the package is installed correctly."
            )

        style_guide_parts: List[str] = []

        for guide in guides:
            try:
                # Render Jinja template with confidence_threshold
                template = Template(guide.content)
                rendered_content = template.render(
                    confidence_threshold=self._confidence_threshold
                )
                style_guide_parts.append(
                    f"# {guide.language.upper()} STYLE GUIDE\n\n{rendered_content}"
                )
                logger.debug(
                    f"StyleGuide[{self.category}] rendered {guide.language} style guide "
                    f"({len(rendered_content)} chars)"
                )
            except Exception as e:
                logger.warning(
                    f"StyleGuide[{self.category}] failed to render "
                    f"{guide.language} style guide: {e}"
                )

        if not style_guide_parts:
            raise RuntimeError(
                f"StyleGuide[{self.category}] failed to render any style guides. "
                f"Check pr-prompt-kit style guide templates."
            )

        # Combine multiple style guides with separators
        if len(style_guide_parts) > 1:
            header = (
                "You are a multi-language Style Guide reviewer. "
                "Apply the appropriate style guide based on the file extension. "
                "Output all suggestions with category: STYLE_VIOLATION.\n\n"
                "---\n\n"
            )
            return header + "\n\n---\n\n".join(style_guide_parts)
        else:
            return style_guide_parts[0]

    def _build_user_prompt(
        self,
        diff: str,
        pr_number: int,
        repository: str,
        title: str,
        description: str,
        branch: str,
    ) -> str:
        """
        Build user prompt with PR context and diff.

        The user prompt presents PR data to the LLM for analysis. This is
        language-agnostic (same format for all languages) - the language-specific
        rules come from the system prompt (style guides from pr-prompt-kit).

        Args:
            diff: The PR diff content
            pr_number: Pull request number
            repository: Repository in owner/name format
            title: PR title
            description: PR description/body
            branch: Source branch name

        Returns:
            User prompt with PR context and diff
        """
        return f"""<pr_info>
Title: {title}
PR Number: {pr_number}
Repository: {repository}
Branch: {branch}
</pr_info>

{f"<description>{description}</description>" if description else ""}

<diff>
{diff}
</diff>

Analyze the above diff for style guide violations."""


# Auto-register on module import
SubAgentRegistry.register(SubAgentCategory.STYLE.value, StyleGuideSubAgent)
