"""
Severity Assessment Layer for PR Reviews.

Assesses overall PR severity (LOW/MEDIUM/HIGH) by having the LLM read the
actual PR diff and understand the nature of the change. When a repo has a
code-review skill (via .claude/skills/), the LLM uses the repo's own standards
to understand what's critical vs trivial. Without a skill, generic risk
indicators are used.

Uses stream-json mode with output_file to enable multi-turn tool invocation,
allowing Claude Code to actually execute the Skill tool for progressive
disclosure of repo-specific code-review skills.
"""

import logging
import os
import re
import tempfile
from collections import defaultdict
from typing import Any, Dict, List, Optional

from pr_prompt_kit.parser import parse_yaml

from src.agents.review_agents.models import SeverityAssessment
from src.agents.terminal_agents.claude_code import ClaudeCodeTool


class SeverityAssessmentLayer:
    """
    Assesses PR-level severity using the full diff + repo skill context.

    The LLM reads the actual diff to understand what the PR changes, then
    uses the repo's code-review skill (if present) to understand what the
    repo considers critical vs trivial. The severity is based on the nature
    of the change, not on suggestion score thresholds.

    Uses stream-json mode (via output_file) to enable multi-turn tool
    invocation. This allows Claude Code to actually execute the Skill tool
    for progressive disclosure of repo-specific code-review skills.

    Usage:
        layer = SeverityAssessmentLayer(working_directory="/tmp/pr-review-...")
        assessment = await layer.assess(
            filtered_suggestions=filtered,
            diff=diff,
            pr_context={"title": ..., "repository": ..., ...},
        )
    """

    SYSTEM_PROMPT = """\
<role>
You are PR-Risk-Assessor, a specialized agent that classifies the overall severity \
of a Pull Request as LOW, MEDIUM, or HIGH.

Your assessment is based on understanding WHAT the PR actually changes and HOW \
critical those changes are in the repository's specific context. You do NOT rely \
on suggestion counts or importance scores alone — you read the diff and reason \
about the nature of the change.
</role>

<skill_discovery>
MANDATORY FIRST STEP: You MUST attempt to load the repository's risk assessment \
and code review skills. Execute these actions BEFORE analyzing the diff.

**Skill loading order (try in this order):**

1. **Try "risk-assessment" skill first** — Use the Skill tool to invoke a skill \
named "risk-assessment". This skill contains explicit definitions of what LOW, \
MEDIUM, and HIGH risk mean for this specific repository, including file path risk \
maps, domain-specific risk patterns, and concrete criteria.

2. **Try "code-review" skill second** — If no risk-assessment skill exists, use \
the Skill tool to invoke "code-review". This skill provides domain context about \
what the repository considers important (critical paths, conventions, patterns) \
which helps inform risk assessment even though it doesn't define risk tiers directly.

3. **Fall back to generic indicators** — If neither skill exists, use the Generic \
Risk Indicators defined below.

**How to use the loaded skill:**
- If "risk-assessment" was loaded: follow its severity definitions, file path risk \
map, and criteria exactly. Cite specific rules from the skill in your reasoning.
- If only "code-review" was loaded: use its domain knowledge (which paths are \
critical, which patterns matter) to inform your assessment, but apply the generic \
risk indicators for the actual LOW/MEDIUM/HIGH classification.
- If neither was loaded: state in your reasoning that no repo-specific skill was \
found and you used generic indicators.

**Auto-Approval Policy:**
- If the loaded skill defines an **Auto-Approval Policy** section, evaluate the PR \
against those criteria and set `auto_approve` accordingly in your output. The skill's \
auto-approval criteria are authoritative for that repository — follow them exactly.
- If the skill has no auto-approval policy, or if no skill was loaded, set \
`auto_approve: false`.
</skill_discovery>

<assessment_framework>
After loading the skill (or confirming none exists), analyze the diff by tracing \
the code flow around the changes:

1. **Identify the nature of the change:**
   - Is this a new feature, bug fix, refactor, config change, log addition, \
test update, or documentation change?
   - Which layers does it touch? (API handlers, business logic, data access, \
infrastructure, tests, config)

2. **Trace the impact of the change:**
   - Read the changed functions and trace their callers using the codebase tools \
(Grep, Read, Glob). Understand who calls the modified code and what depends on it.
   - For modified functions: check if the change affects return values, error paths, \
or side effects that callers rely on.
   - For new code: check if it's wired into existing flows or standalone.
   - For removed code: verify nothing still references it.

3. **Evaluate criticality through the repo's lens:**
   - If a repo skill was loaded: map the changes against the skill's severity scale \
and project rules. A change that violates a HIGH-severity rule (e.g., missing error \
codes, raw HTTP clients) makes the PR HIGH risk.
   - If no skill: use the generic indicators below.

4. **Consider structural risk:**
   - Does the PR modify critical paths? (payments, auth, data persistence)
   - Does it remove or rename public APIs, exported functions, or struct fields?
   - Are there changes without corresponding test updates?
   - Is it additive (new code) or subtractive (removing/changing existing behavior)?

5. **Assess your own confidence:**
   - HIGH confidence (0.85-1.0): You fully traced the code flow, understood the \
impact, and the change clearly maps to a severity level (e.g., a log addition is \
obviously LOW, a payment logic change is obviously HIGH).
   - MODERATE confidence (0.65-0.84): You understood the change but couldn't fully \
trace all callers or the impact is ambiguous (e.g., a utility function change where \
you're unsure how widely it's used).
   - LOW confidence (0.5-0.64): The change is complex, you couldn't trace the full \
impact, or the repo skill didn't cover the area being changed.
</assessment_framework>

<generic_risk_indicators>
Use these ONLY when no code-review skill exists in the repository.

**LOW** — The change is inherently low-risk by nature:
- Adding or modifying log lines for debugging or observability
- Test-only changes (new tests, fixing flaky tests, improving coverage)
- Documentation updates, comment changes, README edits
- Config file tweaks that don't affect runtime behavior
- Dependency version bumps with no API change
- Formatting, linting, or whitespace-only changes
- Adding new constants or enum values that aren't consumed yet

**MEDIUM** — The change touches production code in understood patterns:
- Adding a new API endpoint with corresponding tests
- Extending existing functionality with additional parameters or options
- Bug fixes in non-critical paths with test coverage
- Refactoring that preserves behavior with test coverage
- Adding new internal utility functions or helpers
- Modifying non-critical middleware (logging, metrics, tracing)

**HIGH** — The change carries significant risk:
- Modifying payment, billing, or financial transaction logic
- Changes to authentication, authorization, or security middleware
- Database schema changes or data model modifications
- Removing or renaming public APIs, exported functions, or struct fields
- Modifying core routing or request processing pipelines
- Changes to error handling in critical paths
- Infrastructure changes (connection pools, timeouts, circuit breakers)
- Changes without corresponding test updates in critical areas
</generic_risk_indicators>

<output_format>
Your FINAL output MUST be ONLY the YAML below. No preamble, no explanation, no markdown \
fences, no text before or after the YAML. Start your response with "severity:" as the \
very first characters.

severity: LOW | MEDIUM | HIGH
confidence: <float between 0.5 and 1.0 — see assessment_framework step 5>
rule_source: "<Which skill did you actually use for this assessment? State the skill \
name if a skill was successfully loaded and its definitions were applied (e.g., \
'risk-assessment skill' or 'code-review skill'). If you attempted to load a skill \
but it was not found or had no relevant risk definitions, do NOT claim you used it. \
If no skill was found or applicable, state 'standard_rules'.>"
reasoning: "<Your reasoning as a single-line string in quotes. MUST be 2-4 sentences \
and MUST include: (1) what the PR changes and which code paths are affected, \
(2) which rules or indicators you applied — cite specific repo skill rules by name \
if a skill was loaded, or state 'generic risk indicators' if not, \
(3) why the severity is what it is based on the traced impact.>"
auto_approve: <true if the loaded risk-assessment skill defines an Auto-Approval Policy \
AND all its criteria are satisfied for this PR. false in all other cases: no skill loaded, \
skill has no auto-approval policy, skill criteria not met, or you are uncertain. \
When in doubt, set false.>

RULES:
- Start output with "severity:" — no other text before it
- Use double-quoted string for reasoning, NOT block scalar (|)
- Do NOT wrap in markdown fences
- Do NOT add any explanation outside the YAML
- confidence MUST reflect how thoroughly you traced the code flow and understood \
the impact — NOT a generic guess. If you read callers and verified impact, use 0.85+. \
If you only read the diff without tracing, use 0.6-0.7.
- auto_approve MUST be false unless a repo skill with an explicit Auto-Approval Policy \
was loaded AND all its criteria are satisfied. Generic risk indicators do NOT grant auto_approve.
</output_format>
"""

    USER_PROMPT_TEMPLATE = """\
<pr_info>
Repository: {repository}
PR: #{pr_number}
Title: {title}
Branch: {branch}
Description: {description}
</pr_info>

<diff>
{diff}
</diff>

<review_findings>
These are issues identified by automated review sub-agents. Use them as a supporting \
signal — they highlight specific problems, but the overall PR severity should be based \
on the nature of the change itself, not just the count or scores of these findings.

{suggestions_summary}
</review_findings>

<task>
1. FIRST: Invoke the Skill tool with skill name "risk-assessment" to load this \
repository's explicit risk definitions.
2. If "risk-assessment" was not found: invoke the Skill tool with skill name \
"code-review" to get domain context about this repository.
3. Read the diff above to understand what this PR actually changes.
4. Trace the impact of changed functions using codebase tools (Grep, Read) to \
understand callers and blast radius.
5. Apply the loaded skill's criteria (or generic indicators if no skill found) to \
classify the PR as LOW, MEDIUM, or HIGH.
6. If the loaded skill defines an Auto-Approval Policy, evaluate the PR against those \
criteria and determine auto_approve (true/false). If no policy exists, set auto_approve: false.
7. Output your assessment as YAML per the output_format specification. Your reasoning \
MUST cite which skill was used and which specific rules or criteria drove the classification.
</task>
"""

    def __init__(self, working_directory: str):
        """
        Initialize SeverityAssessmentLayer.

        Args:
            working_directory: Path to cloned repository (used as cwd for Claude Code,
                enabling progressive disclosure of .claude/skills/)
        """
        self._working_directory = working_directory
        self._claude_tool = ClaudeCodeTool.get_instance()
        self._logger = logging.getLogger(__name__)

    async def assess(
        self,
        filtered_suggestions: List[Dict[str, Any]],
        diff: str,
        pr_context: Dict[str, Any],
        available_skills: Optional[List[str]] = None,
        auto_generated_skills: Optional[List[str]] = None,
    ) -> SeverityAssessment:
        """
        Assess PR severity by having the LLM read the diff and repo skill.

        Uses stream-json mode (via output_file) to enable multi-turn tool
        invocation, allowing Claude Code to execute the Skill tool for
        progressive disclosure of repo-specific code-review skills.

        Args:
            filtered_suggestions: Suggestions after filter layer (supporting signal)
            diff: Full PR diff content
            pr_context: PR metadata dict with keys: title, description,
                repository, pr_number, branch
            available_skills: List of skill names verified to exist in the repo's
                .claude/skills/ directory (e.g. ["code-review", "risk-assessment"]).
                Used to validate the LLM's self-reported rule_source.
            auto_generated_skills: List of skill names that were auto-generated
                (not hand-crafted). Used to set rule_source to "generated_context".

        Returns:
            SeverityAssessment with severity, confidence, rule_source, reasoning,
            and category_breakdown

        Raises:
            RuntimeError: If LLM call or response parsing fails
        """
        # Build inputs
        diff = diff or ""

        category_breakdown = self._build_category_breakdown(filtered_suggestions)
        suggestions_summary = self._build_suggestions_summary(filtered_suggestions)

        # Build user prompt with full diff
        user_prompt = self.USER_PROMPT_TEMPLATE.format(
            diff=diff or "No diff available.",
            suggestions_summary=suggestions_summary,
            title=pr_context.get("title", ""),
            description=pr_context.get("description", ""),
            repository=pr_context.get("repository", ""),
            pr_number=pr_context.get("pr_number", ""),
            branch=pr_context.get("branch", ""),
        )

        # Create temp file for stream-json output (enables multi-turn tool invocation)
        fd, output_file = tempfile.mkstemp(
            prefix="severity-assessment-",
            suffix=".jsonl",
            dir=self._working_directory,
        )
        os.close(fd)

        try:
            # Execute via ClaudeCodeTool with output_file for stream-json mode
            # This enables --verbose --output-format stream-json which supports
            # multi-turn tool invocation (required for Skill tool to work)
            self._logger.info(
                f"Running severity assessment for "
                f"{pr_context.get('repository')}#{pr_context.get('pr_number')} "
                f"(diff: {len(diff)} bytes, "
                f"{len(filtered_suggestions)} suggestions, "
                f"mode: stream-json)"
            )
            response = await self._claude_tool.execute({
                "action": "run_prompt",
                "prompt": user_prompt,
                "system_prompt": self.SYSTEM_PROMPT,
                "working_directory": self._working_directory,
                "additional_allowed_tools": "Skill",
                "output_file": output_file,
            })
        finally:
            # Cleanup temp output file
            try:
                if os.path.exists(output_file):
                    os.unlink(output_file)
            except OSError as cleanup_err:
                self._logger.warning(
                    f"Failed to cleanup severity output file: {cleanup_err}"
                )

        # Log skill usage (progressive disclosure observability)
        skills_used = response.get("skills_used", [])
        if skills_used:
            self._logger.info(
                f"Severity assessment used repo skill(s): "
                f"{', '.join(skills_used)} (rule_source=repo_skill)"
            )
        else:
            self._logger.info(
                "Severity assessment: no repo skill found "
                "(rule_source=standard_rules)"
            )

        # Parse response with available skills for verification
        return self._parse_response(
            response, category_breakdown,
            available_skills=available_skills,
            auto_generated_skills=auto_generated_skills,
        )

    def _build_suggestions_summary(
        self, suggestions: List[Dict[str, Any]]
    ) -> str:
        """
        Build compact text summary of suggestions grouped by category.

        Args:
            suggestions: List of suggestion dictionaries

        Returns:
            Formatted summary string for prompt injection
        """
        if not suggestions:
            return "No issues found by review agents."

        # Group by category
        by_category: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for s in suggestions:
            cat = s.get("category", "GENERAL")
            by_category[cat].append(s)

        lines = []
        for category, items in sorted(by_category.items()):
            max_importance = max(s.get("importance", 0) for s in items)
            max_llm_score = max(s.get("llm_score", 0) for s in items)
            lines.append(
                f"Category: {category} | Count: {len(items)} | "
                f"Max Importance: {max_importance} | Max LLM Score: {max_llm_score}"
            )
            for s in items:
                file_path = s.get("file", "unknown")
                line = s.get("line", "?")
                importance = s.get("importance", 0)
                llm_score = s.get("llm_score", 0)
                desc = s.get("description", "")
                # Truncate long descriptions
                if len(desc) > 120:
                    desc = desc[:117] + "..."
                lines.append(
                    f"  - {file_path}:{line} "
                    f"[importance:{importance}, llm_score:{llm_score}] {desc}"
                )
            lines.append("")  # Blank line between categories

        return "\n".join(lines)

    def _build_category_breakdown(
        self, suggestions: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Aggregate suggestions by category.

        Args:
            suggestions: List of suggestion dictionaries

        Returns:
            Dict mapping category to {count, max_importance, max_llm_score}
        """
        breakdown: Dict[str, Dict[str, Any]] = {}
        for s in suggestions:
            cat = s.get("category", "GENERAL")
            if cat not in breakdown:
                breakdown[cat] = {
                    "count": 0,
                    "max_importance": 0,
                    "max_llm_score": 0,
                }
            breakdown[cat]["count"] += 1
            breakdown[cat]["max_importance"] = max(
                breakdown[cat]["max_importance"],
                s.get("importance", 0),
            )
            breakdown[cat]["max_llm_score"] = max(
                breakdown[cat]["max_llm_score"],
                s.get("llm_score", 0),
            )
        return breakdown

    def _parse_response(
        self,
        response: Dict[str, Any],
        category_breakdown: Dict[str, Dict[str, Any]],
        available_skills: Optional[List[str]] = None,
        auto_generated_skills: Optional[List[str]] = None,
    ) -> SeverityAssessment:
        """
        Parse LLM YAML response and verify rule_source against available skills.

        Args:
            response: Response dict from ClaudeCodeTool.execute()
            category_breakdown: Pre-computed category breakdown
            available_skills: Skills verified to exist in the repo (for validation)
            auto_generated_skills: Skills that were auto-generated (not hand-crafted)

        Returns:
            SeverityAssessment populated from LLM response

        Raises:
            RuntimeError: If LLM returned an error or response cannot be parsed
        """
        if "error" in response:
            error_msg = response.get("message", "LLM error")
            raise RuntimeError(f"Severity assessment LLM error: {error_msg}")

        result_text = response.get("result", "")
        skills_used = response.get("skills_used", [])

        # Log raw result for debugging
        self._logger.info(
            f"Severity assessment raw result ({len(result_text)} chars): "
            f"{result_text[:500]}"
        )

        # Strip preamble text before YAML — find first line starting with "severity:"
        cleaned_text = self._strip_yaml_preamble(result_text)

        parsed = parse_yaml(cleaned_text)

        if not parsed:
            self._logger.warning(
                f"parse_yaml returned empty dict. "
                f"Cleaned text preview: {cleaned_text[:300]}"
            )

        severity = parsed.get("severity", "medium")
        if isinstance(severity, str):
            severity = severity.strip().lower()
        else:
            severity = "medium"
        if severity not in ("low", "medium", "high"):
            self._logger.warning(
                f"Invalid severity '{severity}', clamping to 'medium'"
            )
            severity = "medium"

        confidence = float(parsed.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        reasoning = parsed.get("reasoning", "No reasoning provided.")
        if isinstance(reasoning, str):
            reasoning = reasoning.strip()
        else:
            reasoning = str(reasoning)

        # Read rule_source from LLM output — the LLM reports which skill
        # it actually loaded and applied, not just which it attempted to invoke
        rule_source_raw = parsed.get("rule_source", "standard_rules")
        if isinstance(rule_source_raw, str):
            rule_source_raw = rule_source_raw.strip()
        else:
            rule_source_raw = str(rule_source_raw)

        # Determine rule_source and repo_skill_name from LLM's answer
        rule_source_lower = rule_source_raw.lower()
        is_auto_generated = (
            "auto-generated" in rule_source_lower
            or "auto_generated" in rule_source_lower
            or "generated context" in rule_source_lower
        )

        if "risk-assessment" in rule_source_lower:
            repo_skill_name = "risk-assessment"
            rule_source = "generated_context" if is_auto_generated else "repo_skill"
        elif "code-review" in rule_source_lower:
            repo_skill_name = "code-review"
            rule_source = "generated_context" if is_auto_generated else "repo_skill"
        elif is_auto_generated:
            rule_source = "generated_context"
            repo_skill_name = "risk-assessment"
        elif "standard" in rule_source_lower or "generic" in rule_source_lower:
            rule_source = "standard_rules"
            repo_skill_name = None
        else:
            # LLM reported something else — treat as repo skill
            rule_source = "repo_skill"
            repo_skill_name = rule_source_raw

        self._logger.info(
            f"Rule source from LLM: '{rule_source_raw}' -> "
            f"rule_source={rule_source}, repo_skill_name={repo_skill_name}"
        )

        # System-side verification: if the LLM claims it used a skill,
        # verify that skill actually exists in the repo. Override to
        # standard_rules if the LLM hallucinated.
        if available_skills is not None and repo_skill_name:
            if repo_skill_name not in available_skills:
                self._logger.warning(
                    f"LLM claimed rule_source='{repo_skill_name}' but "
                    f"available_skills={available_skills} — "
                    f"overriding to standard_rules (hallucination guard)"
                )
                rule_source = "standard_rules"
                repo_skill_name = None

        # Auto-generated skill check: if the skill was generated on-the-fly
        # (not hand-crafted), mark as generated_context regardless of what
        # the LLM reported.
        if (auto_generated_skills and repo_skill_name
                and repo_skill_name in auto_generated_skills):
            self._logger.info(
                f"Skill '{repo_skill_name}' was auto-generated — "
                f"setting rule_source=generated_context"
            )
            rule_source = "generated_context"

        # Extract auto_approve — only trust it when a repo skill was actually loaded
        auto_approve_raw = parsed.get("auto_approve", False)
        if isinstance(auto_approve_raw, str):
            auto_approve = auto_approve_raw.strip().lower() == "true"
        elif isinstance(auto_approve_raw, bool):
            auto_approve = auto_approve_raw
        else:
            auto_approve = False

        # Guard: auto_approve is only valid when backed by a hand-crafted repo skill.
        # Auto-generated skills must never auto-approve.
        # Preserve the raw LLM verdict for metrics before forcing false.
        auto_approve_before_guard = auto_approve
        if auto_approve and rule_source != "repo_skill":
            self._logger.warning(
                f"auto_approve=true but rule_source={rule_source} "
                f"(not repo_skill) — forcing false"
            )
            auto_approve = False

        self._logger.info(
            f"Auto-approve from LLM: {auto_approve_raw} -> "
            f"auto_approve={auto_approve} (rule_source={rule_source})"
        )

        return SeverityAssessment(
            severity=severity,
            confidence=confidence,
            rule_source=rule_source,
            reasoning=reasoning,
            category_breakdown=category_breakdown,
            repo_skill_name=repo_skill_name,
            auto_approve=auto_approve,
            auto_approve_raw=auto_approve_before_guard,
        )

    def _strip_yaml_preamble(self, text: str) -> str:
        """
        Strip non-YAML preamble text that the LLM may produce before the YAML output.

        Finds the first line starting with 'severity:' and returns everything from
        that line onward. Also strips markdown fences if present.

        Args:
            text: Raw LLM output text

        Returns:
            Cleaned text with only the YAML content
        """
        if not text:
            return text

        # Strip markdown code fences
        text = re.sub(r"```(?:yaml|yml)?\s*\n?", "", text)
        text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)

        # Find the first line starting with "severity:"
        lines = text.split("\n")
        start_idx = None
        for i, line in enumerate(lines):
            if line.strip().lower().startswith("severity:"):
                start_idx = i
                break

        if start_idx is not None and start_idx > 0:
            stripped_lines = "\n".join(lines[:start_idx]).strip()
            self._logger.info(
                f"Stripped {start_idx} preamble lines: "
                f"{stripped_lines[:100]}"
            )
            return "\n".join(lines[start_idx:])

        return text
