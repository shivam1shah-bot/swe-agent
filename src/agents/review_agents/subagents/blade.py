"""
Blade Design System sub-agent for reviewing React component usage.

This sub-agent specializes in detecting Blade Design System violations
in frontend code. It only executes when the PR contains frontend files
(.js, .jsx, .ts, .tsx, .css, .scss).

Blade is Razorpay's design system library providing React components
with specific prop constraints, patterns, and accessibility requirements.

Prompts are managed in pr-prompt-kit (blade_design_system_prompt.toml).
"""

import logging
import re
from typing import Any, Dict, List, Set

from pr_prompt_kit import RenderedPrompt, parse_yaml

from src.agents.review_agents.constants import CATEGORY_LABELS, SubAgentCategory
from src.agents.review_agents.subagent_base import ReviewSubAgentBase
from src.agents.review_agents.subagent_registry import SubAgentRegistry
from src.agents.review_agents.utils.file_type_detector import (
    has_files_with_extensions,
    has_frontend_files,
)

logger = logging.getLogger(__name__)


class BladeSubAgent(ReviewSubAgentBase):
    """
    Sub-agent specialized in Blade Design System compliance review.

    Analyzes frontend code changes for:
    - Component prop constraint violations (e.g., Button tertiary variant)
    - Pattern compliance (ListView, FormGroup, Dashboard layouts)
    - Accessibility requirements (aria labels, focus management)
    - Import hygiene (proper component imports from @razorpay/blade)
    - Semantic component usage (PasswordInput vs TextInput type="password")

    This sub-agent only executes when the PR diff contains frontend files.
    It uses the should_execute() hook to skip execution for backend-only PRs.

    Prompts are loaded from pr-prompt-kit's blade_design_system_prompt.toml.
    """

    # Frontend file extensions that trigger Blade review
    FRONTEND_EXTENSIONS: Set[str] = {
        ".js", ".jsx", ".ts", ".tsx",
        ".css", ".scss", ".sass", ".less",
    }

    @property
    def category(self) -> str:
        """Return the category identifier for this sub-agent."""
        return SubAgentCategory.BLADE.value

    @property
    def category_label(self) -> str:
        """Return the label for GitHub comments."""
        return CATEGORY_LABELS[SubAgentCategory.BLADE.value]

    def should_execute(self, diff: str, **context) -> tuple[bool, str | None]:
        """
        Determine if Blade review should run based on frontend file presence.

        Only executes when the diff contains frontend files (.tsx, .jsx, etc.).
        This prevents unnecessary execution for backend-only PRs.

        Args:
            diff: The PR diff content
            **context: Additional context (unused)

        Returns:
            Tuple of (should_run, skip_reason)
        """
        if not has_frontend_files(diff, self.FRONTEND_EXTENSIONS):
            return False, "No frontend files detected in diff"

        # Skip if this is a Svelte project — Blade is React-specific
        if has_files_with_extensions(diff, {".svelte"}):
            return False, "Svelte project detected — Blade review not applicable"

        return True, None

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
        Render the Blade Design System review prompt using pr-prompt-kit.

        Extracts Blade components from the diff and passes them as a
        template variable for targeted review instructions.

        Args:
            diff: The PR diff content
            pr_number: Pull request number
            repository: Repository in owner/name format
            title: PR title
            description: PR description/body
            branch: Source branch name
            **kwargs: Additional variables

        Returns:
            RenderedPrompt from pr-prompt-kit's blade_design_system_prompt
        """
        # Extract Blade components used in the diff for targeted review
        blade_components = self._extract_blade_components(diff)

        if not blade_components:
            logger.info(
                f"BladeSubAgent[{repository}#{pr_number}] no Blade imports detected, "
                "but frontend files present - will review for potential Blade usage"
            )
        else:
            logger.info(
                f"BladeSubAgent[{repository}#{pr_number}] detected components: "
                f"{', '.join(blade_components)}"
            )

        # Build variables for pr-prompt-kit template
        variables = {
            "diff": diff,
            "pr_number": pr_number,
            "repository": repository,
            "title": title,
            "description": description,
            "branch": branch,
            "confidence_threshold": self._confidence_threshold,
            "blade_components": blade_components,  # Blade-specific variable
            **kwargs,
        }

        # Use pr-prompt-kit's render_subagent for consistent prompt handling
        return self._kit.render_subagent(self.category, variables=variables)

    def _extract_blade_components(self, diff: str) -> List[str]:
        """
        Extract Blade component names from imports in the diff.

        Parses import statements like:
        - import { Button, Card } from '@razorpay/blade/components'
        - import { Amount } from '@razorpay/blade'

        Args:
            diff: The PR diff content

        Returns:
            List of unique Blade component names found in imports
        """
        components: Set[str] = set()

        # Match named imports from @razorpay/blade
        import_pattern = re.compile(
            r"import\s*\{([^}]+)\}\s*from\s*['\"]@razorpay/blade[^'\"]*['\"]"
        )

        for match in import_pattern.finditer(diff):
            imports = match.group(1)
            # Split by comma and clean up whitespace
            for comp in imports.split(','):
                comp = comp.strip()
                # Handle aliased imports: Button as Btn
                if ' as ' in comp:
                    comp = comp.split(' as ')[0].strip()
                if comp and comp[0].isupper():  # Components start with uppercase
                    components.add(comp)

        return sorted(components)

    def _parse_response(self, response_text: str) -> List[Dict[str, Any]]:
        """
        Parse the Blade review response into standard suggestion format.

        Args:
            response_text: Raw YAML response from Claude

        Returns:
            List of suggestion dictionaries in standard format
        """
        if not response_text or not response_text.strip():
            logger.warning("BladeSubAgent received empty response")
            return []

        try:
            parsed = parse_yaml(response_text)

            if parsed is None:
                logger.warning("BladeSubAgent parse_yaml returned None")
                return []

            suggestions = parsed.get("suggestions", [])

            if not isinstance(suggestions, list):
                logger.warning(
                    f"BladeSubAgent expected suggestions list, got {type(suggestions).__name__}"
                )
                return []

            # Add category label to each suggestion
            for s in suggestions:
                if isinstance(s, dict) and "category" not in s:
                    s["category"] = self.category_label

            logger.info(f"BladeSubAgent parsed {len(suggestions)} suggestions")
            return suggestions

        except Exception as e:
            logger.warning(f"BladeSubAgent failed to parse response: {e}")
            preview = response_text[:500] if len(response_text) > 500 else response_text
            logger.debug(f"Response preview: {preview}")
            return []


# Auto-register on module import
SubAgentRegistry.register(SubAgentCategory.BLADE.value, BladeSubAgent)
