"""
Pre-mortem sub-agent for proactive reliability and quality checks.

This sub-agent specializes in detecting production-readiness issues using
the pre-mortem skill. It analyzes code changes for infrastructure patterns,
service contracts, domain logic, quality standards, and observability.

The pre-mortem skill performs 181 automated checks across:
- Infrastructure: Database, Kafka, Redis, SQS, error handling, config
- Services: API contracts, Splitz, Stork, Passport, ASV, Router integrations
- Domain: Constraints, flows, business rules
- Quality: Unit tests, integration tests, feature flags
- Observability: Monitoring, logging
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Template
from pr_prompt_kit import RenderedPrompt, parse_yaml

from src.agents.review_agents.constants import CATEGORY_LABELS, SubAgentCategory
from src.agents.review_agents.models import SubAgentResult
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


class PreMortemSubAgent(ReviewSubAgentBase):
    """
    Sub-agent specialized in pre-mortem analysis for production readiness.

    Analyzes code changes for:
    - Database transaction handling, indexes, N+1 queries
    - Kafka consumer patterns, idempotency, error handling
    - Redis TTL, lock management, stampede protection
    - SQS DLQ setup, visibility timeout, polling
    - Service integration patterns (Splitz, Stork, Passport, etc.)
    - Domain constraint violations, critical flow steps
    - Test coverage, feature flags, CI integration
    - Monitoring metrics, logging trace codes

    Uses the pre-mortem skill from agent-skills repository.
    The skill is baked into the Docker image at build time via Dockerfile.
    See: build/docker/prod/Dockerfile.worker.code_review
    """

    @property
    def category(self) -> str:
        """Return the category identifier for this sub-agent."""
        return SubAgentCategory.PRE_MORTEM.value

    @property
    def category_label(self) -> str:
        """Return the label for GitHub comments."""
        return CATEGORY_LABELS[SubAgentCategory.PRE_MORTEM.value]

    def _verify_skill_exists(self) -> None:
        """
        Verify that the pre-mortem skill exists.

        The skill should be baked into the Docker image at build time.
        If it's missing, this indicates a build-time installation failure
        that must be fixed in the Dockerfile.

        Raises:
            RuntimeError: If the skill is not found (build-time installation failed)
        """
        import os

        # In test environments, skip verification (tests mock the skill)
        if os.getenv("PYTEST_CURRENT_TEST"):
            logger.debug(
                "PreMortemSubAgent: Skipping skill verification in test environment"
            )
            return

        # Expected skill paths (installed during Docker build at WORKDIR /app)
        app_root = Path(__file__).resolve().parents[4]
        skill_path = app_root / ".agents" / "skills" / "pre-mortem"
        review_helpers_link = app_root / ".claude" / "skills" / "review-helpers" / "pre-mortem"

        # Check if skill exists
        if not skill_path.exists():
            error_msg = (
                f"Pre-mortem skill not found at {skill_path}. "
                f"The skill should be installed during Docker build. "
                f"Check Dockerfile.worker.code_review for 'npx skills add' command."
            )
            logger.error(f"PreMortemSubAgent: {error_msg}")
            raise RuntimeError(error_msg)

        if not review_helpers_link.exists():
            error_msg = (
                f"Pre-mortem skill symlink not found at {review_helpers_link}. "
                f"The symlink should be created during Docker build. "
                f"Check Dockerfile.worker.code_review for symlink creation."
            )
            logger.error(f"PreMortemSubAgent: {error_msg}")
            raise RuntimeError(error_msg)

        logger.debug(
            f"PreMortemSubAgent: Skill verified at {skill_path}"
        )

    def _get_skill_references_path(self) -> Path:
        """Return the path to the pre-mortem skill's references directory."""
        app_root = Path(__file__).resolve().parents[4]
        return app_root / ".agents" / "skills" / "pre-mortem" / "references"

    async def _execute_claude(self, rendered_prompt: RenderedPrompt) -> tuple[str, list, list]:
        """
        Execute the pre-mortem analysis by directly applying skill reference checks.

        The pre-mortem SKILL.md is an interactive skill designed for human-in-the-loop
        workflows. When invoked via the Skill tool, Claude loads SKILL.md but cannot
        complete the interactive steps (it simulates the interaction instead).

        Instead, we instruct Claude to directly:
        1. Read the relevant reference check files from the skill's references/ directory
        2. Apply those checks against the PR diff and cloned repo
        3. Return findings in standard YAML format

        This bypasses the interactive SKILL.md wrapper and goes straight to the
        actual check definitions in references/*.md.

        Args:
            rendered_prompt: The rendered prompt with diff and PR context

        Returns:
            Tuple of (result_text, mcp_calls, skills_used)

        Raises:
            RuntimeError: If Claude execution fails or skill is missing
        """
        # Verify skill exists before attempting to invoke it
        self._verify_skill_exists()

        references_path = self._get_skill_references_path()

        # Build a prompt that directly runs the checks using the reference files.
        # The skill's reference files contain the actual check definitions.
        # We instruct Claude to read relevant ones and apply them to the diff.
        skill_invocation_prompt = f"""You are a code review sub-agent performing pre-mortem analysis.

The PR has been cloned to: {self._working_directory}
The pre-mortem check definitions are in: {references_path}

## Your Task

Run automated pre-mortem checks on this PR by following these steps:

### Step 1: Identify changed file types
Look at the diff below and categorize which types of files changed:
- Database/repo files (repo.go, db/, migrations/)
- Kafka consumer/producer files
- Redis/cache files
- SQS/queue files
- Event files (events/, event_*)
- HTTP client / resilience files (httpclient/, retry, circuit breaker)
- Error handling code
- Config files (*.toml, configs/)
- Service client files (mozart/, service clients)
- Domain entity files
- Test files (*_test.go)
- SLIT/integration test files (slit/)

### Step 2: Load relevant check definitions
For each category of changed files, Read the corresponding reference file:
- Database changes → Read {references_path}/infrastructure-database.md
- Kafka changes → Read {references_path}/infrastructure-kafka.md
- Redis changes → Read {references_path}/infrastructure-redis.md
- SQS changes → Read {references_path}/infrastructure-sqs.md
- Event changes → Read {references_path}/infrastructure-eventing.md
- Resilience changes → Read {references_path}/infrastructure-resilience.md
- Error handling → Read {references_path}/infrastructure-error-handling.md
- Config changes → Read {references_path}/infrastructure-config.md
- Service clients → Read {references_path}/services-api-contracts.md
- Event contracts → Read {references_path}/services-event-contracts.md
- Domain files → Read {references_path}/domain-constraints.md and {references_path}/domain-flows.md
- Test files → Read {references_path}/quality-unit-tests.md
- SLIT files → Read {references_path}/quality-integration-tests.md
- ALL PRs → Read {references_path}/observability-monitoring-logging.md

### Step 3: Check for repo-level context
Look for repo-level patterns in the cloned repo:
- Check if {self._working_directory}/CLAUDE.md exists (Read it for codebase patterns)
- Check if {self._working_directory}/.claude/skills/ has any skill directories (load domain knowledge)
- Check if {self._working_directory}/.agents/skills/ has any skill directories

### Step 4: Apply checks against the diff
For each check definition you loaded, examine the PR diff to determine if the
check passes or fails. Use the actual code in the diff — do NOT simulate or guess.

You may use Bash to run commands in the repo if needed (e.g., grep for patterns).

### Step 5: Return findings AND summary in YAML

Return BOTH a summary section and suggestions section:

```yaml
summary:
  categories_checked:
    - "infrastructure-database"
    - "infrastructure-error-handling"
    - "infrastructure-config"
    - "observability-monitoring-logging"
  severity_breakdown:
    critical: 4
    high: 5
    medium: 8
    low: 2
  total_checks_run: 32
  total_checks_passed: 13
  total_issues: 19
  files_affected:
    - file: "config/default-live.toml"
      issue_count: 3
    - file: "internal/config/handler.go"
      issue_count: 8
  reference_files_used:
    - "infrastructure-database.md"
    - "infrastructure-error-handling.md"
    - "infrastructure-config.md"
    - "observability-monitoring-logging.md"

suggestions:
  - file: "path/to/file"
    line: 42
    importance: 9
    confidence: 0.9
    description: "Precise description of the issue found"
    suggestion_code: |
      optional code fix
    category: PRE_MORTEM
```

For the summary section:
- categories_checked: List of reference file base names that were analyzed (simple strings)
- severity_breakdown: Group by importance: critical (9-10), high (7-8), medium (5-6), low (1-4)
- total_checks_run: Total number of checks executed
- total_checks_passed: Number of checks that passed
- total_issues: Total number of issues found (count of suggestions)
- files_affected: Files with issue counts
- reference_files_used: Full reference file names loaded

Only include real findings from the actual diff. Do NOT fabricate issues.
If no issues are found, return empty suggestions list but still include summary with checks_run info.

---

{rendered_prompt.user}"""

        import os
        import tempfile

        # Create temp file for stream-json output (enables skill tracking)
        fd, output_file = tempfile.mkstemp(
            prefix=f"subagent-{self.category}-",
            suffix=".jsonl",
            dir=self._working_directory,
        )
        os.close(fd)

        try:
            params = {
                "action": "run_prompt",
                "prompt": skill_invocation_prompt,
                "system_prompt": rendered_prompt.system,
                # Read: load reference check files from skill directory
                # Bash: run grep/find for pattern matching in the cloned repo
                # Glob: find repo context files
                "additional_allowed_tools": "Read,Bash,Glob,Grep",
                "working_directory": self._working_directory,
                "output_file": output_file,
            }

            logger.info(
                f"PreMortemSubAgent executing reference-based checks in {self._working_directory}"
            )

            response = await self._claude_tool.execute(params)
        finally:
            # Cleanup temp output file
            try:
                if os.path.exists(output_file):
                    os.unlink(output_file)
            except OSError as cleanup_err:
                logger.warning(
                    f"PreMortemSubAgent failed to cleanup output file: {cleanup_err}"
                )

        # Check for errors
        if "error" in response:
            error_msg = response.get("message", response.get("error", "Unknown error"))
            raise RuntimeError(f"Claude execution failed: {error_msg}")

        # Extract the result text
        result = response.get("result", "")
        if not result:
            logger.warning(f"PreMortemSubAgent received empty response from Claude")

        mcp_calls = response.get("mcp_calls", [])
        skills_used = response.get("skills_used", [])

        logger.info(
            f"PreMortemSubAgent tool usage: {len(mcp_calls)} MCP calls, "
            f"{len(skills_used)} skills used"
        )

        return result, mcp_calls, skills_used

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
        Render the pre-mortem analysis prompt.

        Unlike other subagents that load prompts from TOML files,
        the pre-mortem subagent uses a meta-prompt that instructs
        Claude to invoke the pre-mortem skill.

        The skill itself (in SKILL.md) contains all the check logic.

        Args:
            diff: The PR diff content
            pr_number: Pull request number
            repository: Repository in owner/name format
            title: PR title
            description: PR description/body
            branch: Source branch name
            **kwargs: Additional variables

        Returns:
            RenderedPrompt with meta-prompt for skill invocation
        """
        system_prompt = """You are PreMortem-Analyzer, a specialized code review sub-agent.

Your role: Perform comprehensive production-readiness checks by reading pre-mortem
reference check files and applying them to the PR diff.

You check for issues across:
- Infrastructure: Database transactions, Kafka consumers, Redis, SQS, error handling
- Services: API contracts, Splitz, Stork, Passport, ASV, Router integrations
- Domain: Business constraints, critical flows, validation rules
- Quality: Test coverage, feature flags, CI integration
- Observability: Monitoring metrics, logging trace codes

You have access to:
- Read: to load check definitions from the skill's references/ directory
- Bash: to grep/search patterns in the cloned repo
- Glob: to find files in the repo

Output Format:
Return ONLY a YAML block with summary AND suggestions. No prose, no markdown headers — just:
```yaml
summary:
  categories_checked:
    - "infrastructure-database"
    - "infrastructure-error-handling"
  severity_breakdown:
    critical: 4
    high: 5
    medium: 8
    low: 2
  total_checks_run: 32
  total_checks_passed: 13
  total_issues: 19
  files_affected:
    - file: "path/to/file"
      issue_count: 3
  reference_files_used:
    - "infrastructure-database.md"
    - "infrastructure-error-handling.md"

suggestions:
  - file: "path/to/file"
    line: 42
    importance: 9
    confidence: 0.9
    description: "Precise description of the issue"
    suggestion_code: |
      optional fix code
    category: PRE_MORTEM
```

If no issues are found, return:
```yaml
summary:
  categories_checked: [...]
  severity_breakdown:
    critical: 0
    high: 0
    medium: 0
    low: 0
  total_checks_run: X
  total_checks_passed: X
  reference_files_used: [...]
suggestions: []
```

Base findings ONLY on actual code in the diff. Do NOT fabricate issues.
Track which checks you ran and how many passed for the summary section."""

        user_prompt = f"""<pr_info>
Repository: {repository}
PR Number: {pr_number}
Title: {title}
Branch: {branch}
</pr_info>

{f"<description>{description}</description>" if description else ""}

<diff>
{diff}
</diff>

Invoke the "pre-mortem" skill now to analyze this PR."""

        return RenderedPrompt(
            system=system_prompt,
            user=user_prompt,
            name="pre_mortem_skill_invocation",
        )

    async def execute(
        self,
        diff: str,
        pr_number: int,
        repository: str,
        title: str = "",
        description: str = "",
        branch: str = "",
        **kwargs: Any,
    ) -> SubAgentResult:
        """
        Execute pre-mortem analysis and extract skill-generated summary.

        Overrides parent execute() to extract summary from skill's YAML response.
        The skill generates both suggestions and a summary section with accurate
        check counts, categories, and statistics.

        Args:
            diff: PR diff content
            pr_number: PR number
            repository: Repository name
            title: PR title
            description: PR description
            branch: Branch name
            **kwargs: Additional context

        Returns:
            SubAgentResult with suggestions and skill-generated summary_data
        """
        import time

        start_time = time.time()

        try:
            # Check if should execute (inherited from base class)
            should_run, skip_reason = self.should_execute(diff, **kwargs)
            if not should_run:
                return SubAgentResult(
                    category=self.category,
                    suggestions=[],
                    success=True,
                    skipped=True,
                    skip_reason=skip_reason,
                )

            # Render prompt
            rendered_prompt = self._render_prompt(
                diff=diff,
                pr_number=pr_number,
                repository=repository,
                title=title,
                description=description,
                branch=branch,
                **kwargs
            )

            # Execute Claude to get YAML response
            result_text, mcp_calls, skills_used = await self._execute_claude(rendered_prompt)

            # Parse YAML to extract BOTH summary and suggestions
            parsed = parse_yaml(result_text)
            suggestions = parsed.get("suggestions", [])
            summary = parsed.get("summary", None)

            execution_time_ms = int((time.time() - start_time) * 1000)

            # Log summary stats if available
            if summary:
                total_checks = summary.get("total_checks_run", 0)
                total_issues = len(suggestions)
                logger.info(
                    f"PreMortemSubAgent: {total_checks} checks run, "
                    f"{total_issues} issues found (skill-generated summary)"
                )

            # Add execution time to summary for display
            if summary:
                summary["execution_time_ms"] = execution_time_ms

            return SubAgentResult(
                category=self.category,
                suggestions=suggestions,
                success=True,
                execution_time_ms=execution_time_ms,
                mcp_calls=mcp_calls,
                skills_used=skills_used,
                summary_data=summary,  # Skill-generated summary
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"PreMortemSubAgent execution failed: {e}")
            return SubAgentResult(
                category=self.category,
                suggestions=[],
                success=False,
                error=str(e),
                execution_time_ms=execution_time_ms,
            )


# Auto-register on module import
SubAgentRegistry.register(SubAgentCategory.PRE_MORTEM.value, PreMortemSubAgent)
