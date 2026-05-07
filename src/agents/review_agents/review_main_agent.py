"""
Review Main Agent - Orchestrator for PR Code Reviews.

Coordinates the complete PR review pipeline:
1. Fetches PR metadata and diff from GitHub
2. Clones repository to working directory
3. Runs specialized sub-agents in parallel
4. Filters suggestions via AI-powered FilterLayer
5. Posts review comments to GitHub
"""

import asyncio
import json
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Set

from pr_prompt_kit import PRAgentKit

from src.agents.review_agents.filter_layer import FilterLayer
from src.agents.review_agents.pr_description_generator import PRDescriptionGenerator
from src.agents.review_agents.github_pr_comment_publisher import (
    GitHubPRCommentPublisher,
)
from src.agents.review_agents.constants import (
    DEFAULT_SEVERITY_ACTIONS, ACTION_TO_REVIEW_EVENT,
    DEFAULT_APPROVE_BLOCK_THRESHOLD,
    DEFAULT_REVIEW_MODE, VALID_REVIEW_MODES, REVIEW_MODE_COMMENT_ONLY,
)
from src.agents.review_agents.feature_gate import (
    is_rcore_v2_plus_enabled,
    is_skill_auto_generation_enabled,
)
from src.agents.review_agents.metrics import (
    record_tool_usage, record_review_completion, record_severity_assessment,
    record_auto_approve_decision,
)
from src.agents.review_agents.models import ReviewResult, SubAgentResult
from src.agents.review_agents.severity_assessment import SeverityAssessmentLayer
from src.providers.config_loader import get_config
from src.agents.review_agents.subagent_registry import SubAgentRegistry
from src.constants.github_bots import GitHubBot
from src.providers.github.auth_service import GitHubAuthService

logger = logging.getLogger(__name__)


class DiffTooLargeError(Exception):
    """Raised when PR diff exceeds GitHub's line limit."""
    pass


class ReviewMainAgent:
    """
    Main orchestrator for PR code reviews.

    Coordinates multiple specialized sub-agents running in parallel,
    applies AI-based filtering, and posts inline comments to GitHub.

    Usage:
        agent = ReviewMainAgent(github_bot=GitHubBot.CODE_REVIEW)
        result = await agent.execute_review(
            repository="owner/repo",
            pr_number=123
        )
    """

    def __init__(
        self,
        github_bot: GitHubBot = GitHubBot.CODE_REVIEW,
        confidence_threshold: float = 0.6,
        filter_min_score: int = 5,
        filter_pre_threshold: int = 3,
    ):
        """
        Initialize ReviewMainAgent.

        Args:
            github_bot: GitHub bot for authentication (default: CODE_REVIEW)
            confidence_threshold: Minimum confidence for sub-agent suggestions (0-1)
            filter_min_score: Minimum LLM score to keep suggestions (0-10)
            filter_pre_threshold: Minimum importance for pre-filter (0-10)
        """
        self._github_bot = github_bot
        self._confidence_threshold = confidence_threshold
        self._filter_min_score = filter_min_score
        self._filter_pre_threshold = filter_pre_threshold

        # Shared components
        self._kit = PRAgentKit()  # Shared across all sub-agents
        self._auth_service = GitHubAuthService()
        self._logger = logging.getLogger(__name__)

        # Severity assessment configuration
        config = get_config()
        severity_config = config.get("severity_assessment", {})
        self._severity_enabled = severity_config.get("enabled", True)
        self._severity_actions = severity_config.get("actions", DEFAULT_SEVERITY_ACTIONS)
        self._approve_block_threshold = severity_config.get(
            "approve_block_threshold", DEFAULT_APPROVE_BLOCK_THRESHOLD
        )

        # Review mode: "full" or "comment_only"
        review_mode = severity_config.get("review_mode", DEFAULT_REVIEW_MODE)
        if review_mode not in VALID_REVIEW_MODES:
            self._logger.warning(
                f"Invalid review_mode '{review_mode}', falling back to '{DEFAULT_REVIEW_MODE}'"
            )
            review_mode = DEFAULT_REVIEW_MODE
        self._review_mode = review_mode
        # Tracks which skills were auto-generated (set during _generate_repo_context_skill)
        self._auto_generated_skills: list[str] = []

        # Lazy-initialized components
        self._filter = None
        self._publisher = None
        self._description_generator = None
        self._severity_assessor = None

    async def execute_review(
        self,
        repository: str,
        pr_number: int,
    ) -> ReviewResult:
        """
        Execute complete PR review pipeline.

        Args:
            repository: Repository in "owner/repo" format
            pr_number: Pull request number

        Returns:
            ReviewResult with suggestions, posting status, and metadata

        Raises:
            RuntimeError: If PR info fetch, diff fetch, or clone fails
        """
        result = ReviewResult()
        working_directory = None
        publish_result = None  # Initialize to prevent UnboundLocalError in post-publish block
        mcp_calls = []  # Initialize to prevent UnboundLocalError if subagents fail
        skills_used = []  # Initialize to prevent UnboundLocalError if subagents fail

        try:
            # 1. Ensure GitHub authentication
            self._logger.info(
                f"Starting review for {repository}#{pr_number} with {self._github_bot.value}"
            )
            await self._auth_service.ensure_gh_auth(bot_name=self._github_bot)

            # 2. Fetch PR metadata (title, description, branch, state)
            pr_info = await self._fetch_pr_info(repository, pr_number)

            # Skip if PR is not open
            if pr_info["state"].upper() != "OPEN":
                self._logger.warning(
                    f"PR {repository}#{pr_number} is {pr_info['state']}, skipping review"
                )
                return result

            # 3. Get merge base SHA (for accurate local diff generation)
            # This is the commit GitHub uses as the base for PR diffs
            merge_base_sha = await self._get_merge_base(
                repository, pr_info["base_branch"], pr_info["head_sha"]
            )

            # 4. Clone/prepare repository and fetch merge base commit
            working_directory = await self._prepare_working_directory(
                repository, pr_number, pr_info["branch"], merge_base_sha
            )

            # 5. Generate diff locally against merge base (no 20,000 line limit!)
            # Uses same semantics as GitHub's PR diff
            diff = await self._generate_local_diff(working_directory, merge_base_sha)

            if not diff or not diff.strip():
                self._logger.warning(
                    f"No diff found for {repository}#{pr_number}, skipping review"
                )
                await self._cleanup_working_directory(working_directory)
                return result

            # 6. Build PR context for sub-agents
            pr_context = {
                "title": pr_info["title"],
                "description": pr_info["description"],
                "repository": repository,
                "pr_number": pr_number,
                "branch": pr_info["branch"],
            }

            # 7. Run PR description and sub-agents IN PARALLEL
            self._logger.info(
                f"Running PR description + sub-agents in parallel for {repository}#{pr_number}"
            )

            # Launch both in parallel using asyncio.gather
            description_task = self._generate_pr_description(
                diff=diff,
                repository=repository,
                pr_number=pr_number,
                title=pr_info["title"],
                description=pr_info["description"],
                branch=pr_info["branch"],
                base_branch=pr_info["base_branch"],
                working_directory=working_directory,
            )
            subagent_task = self._run_subagents_parallel(
                working_directory, diff, pr_context
            )

            # Gather results (description generation runs alongside sub-agents)
            description_result, subagent_results = await asyncio.gather(
                description_task,
                subagent_task,
                return_exceptions=True,
            )

            # Handle description result
            if isinstance(description_result, Exception):
                self._logger.error(f"PR description generation failed: {description_result}")
                result.add_error(f"Description generation failed: {str(description_result)}")
            elif description_result and description_result.posted:
                result.description_posted = True
                self._logger.info(
                    f"PR description posted for {repository}#{pr_number}"
                )

            # Handle sub-agent results exceptions
            if isinstance(subagent_results, Exception):
                self._logger.error(f"Sub-agents failed: {subagent_results}")
                raise subagent_results

            # 8. Merge all suggestions from sub-agents
            all_suggestions = self._merge_suggestions(subagent_results)

            # 8.1 Aggregate tool usage from sub-agents
            mcp_calls, skills_used = self._aggregate_tool_usage(subagent_results)

            # 9. Apply filter layer (only if we have suggestions to filter)
            filtered = []
            if all_suggestions:
                # Get PR files for routing
                pr_files = await self._get_pr_files(repository, pr_number)

                # Initialize filter layer if needed
                if self._filter is None:
                    self._filter = FilterLayer(
                        working_directory=working_directory,
                        kit=self._kit,
                        min_score_threshold=self._filter_min_score,
                        pre_filter_threshold=self._filter_pre_threshold,
                    )

                self._logger.info(
                    f"Applying AI-based filter to {len(all_suggestions)} suggestions"
                )
                filtered = await self._filter.apply(
                    all_suggestions, diff, pr_context, pr_files=pr_files
                )

                # Add filter layer tool usage
                if self._filter.mcp_calls:
                    mcp_calls.extend(self._filter.mcp_calls)
                if self._filter.skills_used:
                    skills_used.extend(self._filter.skills_used)
                    skills_used = list(set(skills_used))  # Deduplicate

            # Log filtering results
            self._logger.info(
                f"Review for {repository}#{pr_number}: "
                f"{len(all_suggestions)} found, {len(filtered)} after filter"
            )

            # 9.5 Severity Assessment
            assessment = None
            if self._severity_enabled:
                try:
                    if self._severity_assessor is None:
                        self._severity_assessor = SeverityAssessmentLayer(
                            working_directory=working_directory,
                        )

                    # Scan which skills actually exist for verification
                    available_skills = self._scan_available_skills(working_directory)
                    self._logger.info(
                        f"Assessing PR severity for {repository}#{pr_number} "
                        f"({len(filtered)} filtered suggestions, "
                        f"available_skills={available_skills})"
                    )
                    assessment = await self._severity_assessor.assess(
                        filtered_suggestions=filtered,
                        diff=diff,
                        pr_context=pr_context,
                        available_skills=available_skills,
                        auto_generated_skills=self._auto_generated_skills,
                    )
                    result.severity_assessment = assessment
                    self._logger.info(
                        f"PR severity for {repository}#{pr_number}: "
                        f"{assessment.severity} (source: {assessment.rule_source}, "
                        f"confidence: {assessment.confidence})"
                    )
                except Exception as assess_error:
                    self._logger.error(
                        f"Severity assessment failed for {repository}#{pr_number}: "
                        f"{assess_error}. Proceeding with default COMMENT review."
                    )
                    result.add_error(f"Severity assessment failed: {str(assess_error)}")
            else:
                self._logger.info(
                    f"Severity assessment disabled by config for {repository}#{pr_number}"
                )

            # Resolve review_event: skill-driven auto-approve or config-driven fallback
            review_event = "COMMENT"
            skill_driven_approve = False
            if assessment:
                if assessment.auto_approve and assessment.rule_source == "repo_skill":
                    if is_rcore_v2_plus_enabled(repository):
                        # Repo skill explicitly approved this PR (v2++ enabled)
                        review_event = "APPROVE"
                        skill_driven_approve = True

                        self._logger.info(
                            f"Auto-approve granted by repo skill "
                            f"'{assessment.repo_skill_name}' for "
                            f"{repository}#{pr_number} "
                            f"(severity={assessment.severity}, "
                            f"confidence={assessment.confidence})"
                        )
                    else:
                        # Skill says auto-approve but repo not in v2++ whitelist
                        action = self._severity_actions.get(
                            assessment.severity, "comment"
                        )
                        review_event = ACTION_TO_REVIEW_EVENT.get(action, "COMMENT")
                        self._logger.info(
                            f"Skill auto-approve available but repo not in v2++ whitelist "
                            f"for {repository}#{pr_number} — "
                            f"falling back to config-driven: {review_event}"
                        )
                else:
                    # No skill-driven approval — use config-driven action mapping
                    action = self._severity_actions.get(
                        assessment.severity, "comment"
                    )
                    review_event = ACTION_TO_REVIEW_EVENT.get(action, "COMMENT")
                    self._logger.info(
                        f"Config-driven action for {repository}#{pr_number}: "
                        f"severity={assessment.severity} -> action={action} "
                        f"-> review_event={review_event}"
                    )

                # Gate config-driven approve behind whitelist
                if review_event == "APPROVE" and not skill_driven_approve:
                    if not is_rcore_v2_plus_enabled(repository):
                        review_event = "COMMENT"
                        self._logger.info(
                            f"Config-driven approve blocked for "
                            f"{repository}#{pr_number}: "
                            f"repo not in v2++ whitelist — "
                            f"downgrading to COMMENT"
                        )

                # Safety net: CRITICAL suggestions override any APPROVE
                if review_event == "APPROVE" and filtered:
                    blocking = [
                        s for s in filtered
                        if s.get("importance", 0)
                        >= self._approve_block_threshold
                    ]
                    if blocking:
                        review_event = "COMMENT"
                        self._logger.warning(
                            f"Auto-approve overridden for "
                            f"{repository}#{pr_number}: "
                            f"{len(blocking)} suggestion(s) with importance "
                            f">= {self._approve_block_threshold}"
                        )
                        record_auto_approve_decision(
                            outcome="overridden",
                            rule_source=assessment.rule_source,
                            repository=repository,
                            repo_skill_name=assessment.repo_skill_name,
                        )
                    elif skill_driven_approve:
                        record_auto_approve_decision(
                            outcome="approved",
                            rule_source=assessment.rule_source,
                            repository=repository,
                            repo_skill_name=assessment.repo_skill_name,
                        )
                elif review_event == "APPROVE" and skill_driven_approve:
                    # Skill-driven approve with no filtered suggestions
                    record_auto_approve_decision(
                        outcome="approved",
                        rule_source=assessment.rule_source,
                        repository=repository,
                        repo_skill_name=assessment.repo_skill_name,
                    )
                elif review_event == "APPROVE" and not skill_driven_approve:
                    # Auto-generated skill would have approved — record
                    # distinct metric instead of generic config_approved.
                    if (assessment.auto_approve_raw
                            and assessment.rule_source == "generated_context"):
                        record_auto_approve_decision(
                            outcome="auto_gen_would_approve",
                            rule_source=assessment.rule_source,
                            repository=repository,
                            repo_skill_name=assessment.repo_skill_name,
                        )
                    else:
                        record_auto_approve_decision(
                            outcome="config_approved",
                            rule_source=assessment.rule_source,
                            repository=repository,
                            repo_skill_name=assessment.repo_skill_name,
                        )
                elif not assessment.auto_approve:
                    if (assessment.auto_approve_raw
                            and assessment.rule_source == "generated_context"):
                        record_auto_approve_decision(
                            outcome="auto_gen_would_approve",
                            rule_source=assessment.rule_source,
                            repository=repository,
                            repo_skill_name=assessment.repo_skill_name,
                        )
                    else:
                        record_auto_approve_decision(
                            outcome="not_eligible",
                            rule_source=assessment.rule_source,
                            repository=repository,
                            repo_skill_name=assessment.repo_skill_name,
                        )
            else:
                # Severity assessment disabled or failed — bot made no approval decision
                record_auto_approve_decision(
                    outcome="not_eligible",
                    rule_source="standard_rules",
                    repository=repository,
                    repo_skill_name=None,
                )
            # Review mode clamp: comment_only forces everything to COMMENT
            if self._review_mode == REVIEW_MODE_COMMENT_ONLY and review_event != "COMMENT":
                self._logger.info(
                    f"review_mode=comment_only: clamping {review_event} → COMMENT "
                    f"for {repository}#{pr_number}"
                )
                review_event = "COMMENT"

            # 10. Post to GitHub (always post - publisher handles empty list)
            if self._publisher is None:
                self._publisher = GitHubPRCommentPublisher(
                    github_bot=self._github_bot
                )

            self._logger.info(
                f"Publishing {len(filtered)} suggestions to {repository}#{pr_number}"
            )
            publish_result = await self._publisher.publish(
                repository=repository,
                pr_number=pr_number,
                suggestions=filtered,
                review_event=review_event,
                mcp_calls=mcp_calls,
                skills_used=skills_used,
                severity_assessment=assessment,
                subagent_results=subagent_results,
            )

            # 11. Build result - set review_posted based on publish success
            result.review_posted = publish_result.success
            result.review_id = publish_result.review_id

            # Propagate publisher error to result for proper status tracking
            if not publish_result.success and publish_result.error:
                result.add_error(f"Publish failed: {publish_result.error}")

        except Exception as e:
            # Error BEFORE or DURING publish - safe to raise for retry
            self._logger.error(
                f"Review failed for {repository}#{pr_number}: {e}", exc_info=True
            )
            result.add_error(str(e))

            # Record failed review metric
            record_review_completion(repository, "failed")

            # Cleanup before raising
            if working_directory:
                try:
                    await self._cleanup_working_directory(working_directory)
                except Exception as cleanup_error:
                    self._logger.warning(f"Failed to cleanup working directory: {cleanup_error}")
            raise

        # POST-PUBLISH OPERATIONS: Wrap separately - errors here should NOT raise
        # because the review was already posted to GitHub
        try:
            # Convert filtered dicts to Suggestion objects
            from src.agents.review_agents.models import Suggestion

            result.suggestions = [Suggestion.from_dict(s) for s in filtered]

            # Record metrics for tool usage and review completion
            record_tool_usage(mcp_calls, skills_used, repository)
            status = "success" if publish_result and publish_result.success else "failed"
            record_review_completion(repository, status)

            # Record severity assessment metric
            if result.severity_assessment:
                sa = result.severity_assessment
                record_severity_assessment(
                    severity=sa.severity,
                    rule_source=sa.rule_source,
                    repository=repository,
                    generated_skill_name=(
                        sa.repo_skill_name or ""
                    ) if sa.rule_source == "generated_context" else "",
                )

            if publish_result:
                self._logger.info(
                    f"Review completed for {repository}#{pr_number}: "
                    f"posted={publish_result.success}, "
                    f"comments={publish_result.comments_posted}, "
                    f"review_id={publish_result.review_id}"
                )
        except Exception as post_publish_error:
            # Log error but DON'T raise - review was already posted successfully
            self._logger.warning(
                f"Post-publish operation failed for {repository}#{pr_number}: {post_publish_error}. "
                "Review was posted successfully - returning result to prevent duplicate."
            )
            result.add_error(f"Post-publish error: {str(post_publish_error)}")

        # Cleanup temp directory before returning
        if working_directory:
            try:
                await self._cleanup_working_directory(working_directory)
            except Exception as cleanup_error:
                self._logger.warning(f"Failed to cleanup working directory: {cleanup_error}")

        return result

    async def _fetch_pr_info(
        self, repository: str, pr_number: int
    ) -> Dict[str, Any]:
        """
        Fetch PR metadata via gh CLI.

        Args:
            repository: Repository in "owner/repo" format
            pr_number: Pull request number

        Returns:
            Dictionary with title, description, branch, state

        Raises:
            RuntimeError: If gh CLI command fails
        """
        process = await asyncio.create_subprocess_exec(
            "gh",
            "pr",
            "view",
            str(pr_number),
            "--repo",
            repository,
            "--json",
            "title,body,headRefName,baseRefName,state,headRefOid",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode().strip()
            raise RuntimeError(
                f"Failed to fetch PR info for {repository}#{pr_number}: {error_msg}"
            )

        data = json.loads(stdout.decode())

        return {
            "title": data.get("title", ""),
            "description": data.get("body", ""),
            "branch": data.get("headRefName", ""),
            "base_branch": data.get("baseRefName", "main"),
            "state": data.get("state", ""),
            "head_sha": data.get("headRefOid", ""),
        }

    async def _post_pr_comment(
        self, repository: str, pr_number: int, body: str
    ) -> bool:
        """
        Post a general comment on a PR.

        Args:
            repository: Repository in owner/name format
            pr_number: Pull request number
            body: Comment body (markdown supported)

        Returns:
            True if comment posted successfully, False otherwise
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "gh",
                "pr",
                "comment",
                str(pr_number),
                "--repo",
                repository,
                "--body",
                body,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                self._logger.error(
                    f"Failed to post comment on {repository}#{pr_number}: {error_msg}"
                )
                return False

            self._logger.info(f"Posted comment on {repository}#{pr_number}")
            return True

        except Exception as e:
            self._logger.error(f"Error posting comment: {e}")
            return False

    async def _get_pr_files(self, repository: str, pr_number: int) -> Set[str]:
        """
        Get set of file paths changed in the PR.

        Args:
            repository: Repository in "owner/repo" format
            pr_number: Pull request number

        Returns:
            Set of file paths in the PR (empty set on failure)
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "gh",
                "api",
                f"repos/{repository}/pulls/{pr_number}/files",
                "--jq",
                "[.[].filename]",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                self._logger.warning(
                    f"Failed to get PR files: {stderr.decode()}"
                )
                return set()

            files = json.loads(stdout.decode())
            self._logger.info(f"PR has {len(files)} changed files")
            return set(files)

        except Exception as e:
            self._logger.warning(f"Error getting PR files: {e}")
            return set()

    async def _get_merge_base(
        self, repository: str, base_branch: str, head_sha: str
    ) -> str:
        """
        Get the merge base SHA using GitHub's compare API.

        This is the commit that GitHub uses as the base for PR diffs.
        Using this ensures our local diff matches GitHub's line numbers exactly.

        Args:
            repository: Repository in "owner/repo" format
            base_branch: Base branch name (e.g., "main", "master")
            head_sha: HEAD commit SHA of the PR branch

        Returns:
            Merge base commit SHA

        Raises:
            RuntimeError: If API call fails
        """
        # Use compare API to get merge base between base branch and PR head
        process = await asyncio.create_subprocess_exec(
            "gh",
            "api",
            f"repos/{repository}/compare/{base_branch}...{head_sha}",
            "--jq",
            ".merge_base_commit.sha",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode().strip()
            raise RuntimeError(f"Failed to get merge base: {error_msg}")

        merge_base = stdout.decode().strip().strip('"')
        self._logger.info(
            f"Merge base for {repository} ({base_branch}...{head_sha[:8]}): {merge_base[:8]}..."
        )
        return merge_base

    async def _generate_local_diff(
        self, working_directory: str, merge_base_sha: str
    ) -> str:
        """
        Generate diff locally using git diff against merge base.

        This avoids GitHub's 20,000 line API limit while producing
        identical line numbers to GitHub's PR diff.

        Args:
            working_directory: Path to cloned repository
            merge_base_sha: Merge base commit SHA (from GitHub API)

        Returns:
            Unified diff string (same format as GitHub API)

        Raises:
            RuntimeError: If git diff command fails
        """
        # Diff against merge base - matches GitHub's PR diff semantics exactly
        # Use two-dot syntax (..) for shallow clones
        process = await asyncio.create_subprocess_exec(
            "git",
            "diff",
            f"{merge_base_sha}..HEAD",
            cwd=working_directory,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode().strip()
            raise RuntimeError(f"Failed to generate local diff: {error_msg}")

        diff = stdout.decode()
        line_count = diff.count('\n')
        self._logger.info(
            f"Generated local diff: {len(diff)} bytes, {line_count} lines"
        )

        return diff

    async def _prepare_working_directory(
        self, repository: str, pr_number: int, branch: str, merge_base_sha: str
    ) -> str:
        """
        Clone repository to temp directory and checkout PR branch.
        Also fetches merge base commit for accurate local diff generation.

        Args:
            repository: Repository in "owner/repo" format
            pr_number: Pull request number
            branch: PR head branch name to checkout
            merge_base_sha: Merge base commit SHA from GitHub API

        Returns:
            Path to cloned repository temp directory with PR branch checked out

        Raises:
            RuntimeError: If clone, fetch, or branch checkout fails
        """
        # Create temp directory
        repo_name = repository.replace("/", "-")
        temp_dir = tempfile.mkdtemp(
            prefix=f"pr-review-{repo_name}-{pr_number}-"
        )

        try:
            # Clone the specific PR branch directly with gh repo clone
            # This handles auth automatically and avoids separate fetch+checkout
            self._logger.info(f"Cloning {repository} branch {branch} to {temp_dir}")

            process = await asyncio.create_subprocess_exec(
                "gh",
                "repo",
                "clone",
                repository,
                temp_dir,
                "--",
                "--branch",
                branch,
                "--depth",
                "1",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                shutil.rmtree(temp_dir, ignore_errors=True)
                raise RuntimeError(
                    f"Failed to clone {repository} branch {branch}: {error_msg}"
                )

            self._logger.info(f"Successfully cloned {repository} branch {branch} to {temp_dir}")

            # Fetch merge base commit for accurate local diff generation
            # This ensures our diff matches GitHub's PR diff exactly
            self._logger.info(f"Fetching merge base commit: {merge_base_sha[:8]}...")

            fetch_process = await asyncio.create_subprocess_exec(
                "git",
                "fetch",
                "origin",
                merge_base_sha,
                "--depth",
                "1",
                cwd=temp_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            fetch_stdout, fetch_stderr = await fetch_process.communicate()

            if fetch_process.returncode != 0:
                error_msg = fetch_stderr.decode().strip()
                shutil.rmtree(temp_dir, ignore_errors=True)
                raise RuntimeError(
                    f"Failed to fetch merge base {merge_base_sha[:8]}: {error_msg}"
                )

            self._logger.info(f"Fetched merge base commit: {merge_base_sha[:8]}")

            # Copy .claude/skills to the cloned repository
            await self._copy_skills_to_repo(temp_dir)

            # Generate missing repo-specific skills (gated)
            if is_skill_auto_generation_enabled():
                await self._generate_repo_context_skill(temp_dir)
            else:
                self._logger.info("Skill auto-generation disabled — skipping")

            return temp_dir

        except Exception as e:
            # Cleanup on failure
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise

    async def _copy_skills_to_repo(self, repo_directory: str) -> None:
        """
        Copy review-helper skills from swe-agent to the cloned repository.

        This ensures that review-specific skills (like i18n-anomaly-detection)
        are available when running code reviews on the cloned PR repository.

        Copies only skills from .claude/skills/review-helpers/* to avoid
        copying unnecessary skills.

        Args:
            repo_directory: Path to the cloned repository
        """
        try:
            # Get the path to swe-agent's review-helpers directory
            # This file is located at: swe-agent/src/agents/review_agents/review_main_agent.py
            # So we need to go up to the project root
            current_file = Path(__file__)
            swe_agent_root = current_file.parent.parent.parent.parent
            source_review_helpers_dir = swe_agent_root / ".claude" / "skills" / "review-helpers"

            # Destination .claude/skills in cloned repo
            dest_claude_dir = Path(repo_directory) / ".claude"
            dest_skills_dir = dest_claude_dir / "skills"

            # Check if source review-helpers directory exists
            if not source_review_helpers_dir.exists():
                self._logger.warning(
                    f"Source review-helpers directory not found: {source_review_helpers_dir}"
                )
                return

            # Create .claude/skills directory in cloned repo if it doesn't exist
            dest_skills_dir.mkdir(parents=True, exist_ok=True)

            # Copy each skill from review-helpers/* to .claude/skills/* in cloned repo
            skills_copied = 0
            for skill_dir in source_review_helpers_dir.iterdir():
                if skill_dir.is_dir():
                    skill_name = skill_dir.name
                    dest_skill_dir = dest_skills_dir / skill_name

                    # Remove existing skill directory if it exists (non-blocking)
                    if dest_skill_dir.exists():
                        await asyncio.to_thread(shutil.rmtree, dest_skill_dir)

                    # Copy the skill directory (non-blocking)
                    await asyncio.to_thread(shutil.copytree, skill_dir, dest_skill_dir)
                    skills_copied += 1
                    self._logger.debug(f"Copied skill: {skill_name}")

            self._logger.info(
                f"Copied {skills_copied} review-helper skill(s) from {source_review_helpers_dir} to {dest_skills_dir}"
            )

        except Exception as e:
            # Log warning but don't fail the review if skills copy fails
            self._logger.warning(
                f"Failed to copy review-helper skills to {repo_directory}: {e}"
            )

    async def _generate_repo_context_skill(self, repo_directory: str) -> None:
        """
        Generate missing repo-specific skills based on REQUIRED_REVIEW_SKILLS registry.

        Checks which required skills are present in the cloned repo's
        .claude/skills/. For skills with source="generated" that are missing,
        invokes ClaudeCodeTool to generate them following skill-creator best
        practices. Skills with source="agent-skills" or "review-helpers" are
        expected to already be present (via agentfill or _copy_skills_to_repo).

        Generated skills live only in the temp clone and are cleaned up after
        review. They explicitly exclude Auto-Approval Policy.

        Args:
            repo_directory: Path to the cloned repository
        """
        from src.agents.review_agents.constants import REQUIRED_REVIEW_SKILLS

        try:
            skills_dir = Path(repo_directory) / ".claude" / "skills"

            # Check which required skills are present vs missing
            present = []
            missing_generated = []
            missing_external = []

            for skill_name, config in REQUIRED_REVIEW_SKILLS.items():
                if (skills_dir / skill_name).exists():
                    present.append(skill_name)
                elif config["source"] == "generated":
                    missing_generated.append(skill_name)
                else:
                    missing_external.append(skill_name)

            self._logger.info(
                f"Skill check: present={present}, "
                f"missing_generated={missing_generated}, "
                f"missing_external={missing_external}"
            )

            # Warn about missing external skills (should have been installed)
            for skill_name in missing_external:
                source = REQUIRED_REVIEW_SKILLS[skill_name]["source"]
                self._logger.warning(
                    f"Required skill '{skill_name}' missing "
                    f"(expected from {source})"
                )

            # Nothing to generate
            if not missing_generated:
                self._logger.info("All generated skills already present")
                return

            repo_path = Path(repo_directory)

            # Gather pre-context deterministically (fast, no LLM needed)
            language, framework = await asyncio.to_thread(
                self._detect_language_and_framework, repo_path
            )
            critical_paths = await asyncio.to_thread(
                self._detect_critical_paths, repo_path
            )
            test_info = await asyncio.to_thread(
                self._detect_test_patterns, repo_path
            )

            pre_context = self._build_pre_context(
                language, framework, critical_paths, test_info,
            )

            # Generate each missing repo-specific skill
            for skill_name in missing_generated:
                skill_content = await self._generate_skill_via_llm(
                    repo_directory, pre_context, skill_type=skill_name,
                )

                if not skill_content:
                    self._logger.warning(
                        f"LLM returned empty content for {skill_name}, skipping"
                    )
                    continue

                skill_dir = skills_dir / skill_name
                skill_dir.mkdir(parents=True, exist_ok=True)
                (skill_dir / "SKILL.md").write_text(skill_content)

                self._auto_generated_skills.append(skill_name)

                self._logger.info(
                    f"Generated on-the-fly {skill_name} skill via LLM: "
                    f"language={language}, framework={framework}, "
                    f"critical_paths={len(critical_paths)}"
                )

        except Exception as e:
            self._logger.warning(
                f"Failed to generate repo-context skill: {e}. "
                "Review will proceed with generic rules."
            )

    def _detect_language_and_framework(self, repo_path: Path) -> tuple[str, str]:
        """
        Detect primary language and framework from repo files.

        Args:
            repo_path: Path to the repository root

        Returns:
            Tuple of (language, framework) strings
        """
        language = "unknown"
        framework = "unknown"

        if (repo_path / "go.mod").exists():
            language = "Go"
            try:
                go_mod = (repo_path / "go.mod").read_text(errors="ignore")
                if "razorpay/goutils/foundation" in go_mod or "razorpay/go-foundation" in go_mod:
                    framework = "Foundation"
                elif "gin-gonic/gin" in go_mod:
                    framework = "Gin"
                elif "labstack/echo" in go_mod:
                    framework = "Echo"
                elif "grpc" in go_mod.lower():
                    framework = "gRPC"
            except Exception:
                pass
        elif (repo_path / "package.json").exists():
            language = "JavaScript/TypeScript"
            try:
                import json
                pkg = json.loads((repo_path / "package.json").read_text(errors="ignore"))
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                if "next" in deps:
                    framework = "Next.js"
                elif "react" in deps:
                    framework = "React"
                elif "express" in deps:
                    framework = "Express"
                elif "fastify" in deps:
                    framework = "Fastify"
            except Exception:
                pass
        elif (repo_path / "requirements.txt").exists() or (repo_path / "pyproject.toml").exists():
            language = "Python"
            for cfg_file in ["requirements.txt", "pyproject.toml", "setup.py"]:
                cfg_path = repo_path / cfg_file
                if cfg_path.exists():
                    try:
                        content = cfg_path.read_text(errors="ignore").lower()
                        if "fastapi" in content:
                            framework = "FastAPI"
                        elif "django" in content:
                            framework = "Django"
                        elif "flask" in content:
                            framework = "Flask"
                    except Exception:
                        pass
                    if framework != "unknown":
                        break
        elif (repo_path / "pom.xml").exists() or (repo_path / "build.gradle").exists():
            language = "Java"
            for cfg_file in ["pom.xml", "build.gradle", "build.gradle.kts"]:
                cfg_path = repo_path / cfg_file
                if cfg_path.exists():
                    try:
                        content = cfg_path.read_text(errors="ignore").lower()
                        if "spring" in content:
                            framework = "Spring Boot"
                    except Exception:
                        pass
                    if framework != "unknown":
                        break
        elif (repo_path / "composer.json").exists():
            language = "PHP"
            try:
                content = (repo_path / "composer.json").read_text(errors="ignore").lower()
                if "laravel" in content:
                    framework = "Laravel"
            except Exception:
                pass

        return language, framework

    def _detect_critical_paths(self, repo_path: Path) -> list[dict[str, str]]:
        """
        Detect directories that are likely critical based on naming patterns.

        Args:
            repo_path: Path to the repository root

        Returns:
            List of dicts with 'path' and 'reason' keys
        """
        critical_patterns = {
            "payment": "Payment processing logic",
            "billing": "Billing and invoicing",
            "auth": "Authentication and authorization",
            "migration": "Database schema changes",
            "middleware": "Request processing pipeline",
            "settlement": "Settlement processing",
            "ledger": "Financial ledger operations",
            "crypto": "Cryptographic operations",
            "security": "Security-sensitive code",
            "gateway": "External gateway integrations",
            "transaction": "Transaction handling",
            "payout": "Payout processing",
            "refund": "Refund processing",
        }

        detected = []
        try:
            for item in repo_path.rglob("*"):
                if not item.is_dir():
                    continue
                # Skip hidden dirs and vendor/node_modules
                rel = str(item.relative_to(repo_path))
                if any(part.startswith(".") for part in rel.split("/")):
                    continue
                if any(skip in rel for skip in ["vendor", "node_modules", "__pycache__", ".git"]):
                    continue

                dir_name = item.name.lower()
                for pattern, reason in critical_patterns.items():
                    if pattern in dir_name:
                        detected.append({"path": rel + "/", "reason": reason})
                        break
        except Exception:
            pass

        # Also check CODEOWNERS for ownership signals
        codeowners_path = repo_path / "CODEOWNERS"
        if not codeowners_path.exists():
            codeowners_path = repo_path / ".github" / "CODEOWNERS"

        if codeowners_path.exists():
            try:
                content = codeowners_path.read_text(errors="ignore")
                # If CODEOWNERS exists, note it as a signal
                if content.strip():
                    detected.append({
                        "path": "CODEOWNERS",
                        "reason": "Ownership rules defined (review for critical path hints)",
                    })
            except Exception:
                pass

        return detected[:20]  # Cap at 20 to avoid bloated skills

    def _detect_test_patterns(self, repo_path: Path) -> dict[str, str]:
        """
        Detect where tests live and their naming convention.

        Args:
            repo_path: Path to the repository root

        Returns:
            Dict with 'test_dir' and 'pattern' keys
        """
        info = {"test_dir": "", "pattern": ""}

        # Common test directory names
        for test_dir in ["tests", "test", "pkg", "internal", "spec", "__tests__"]:
            if (repo_path / test_dir).exists():
                info["test_dir"] = test_dir + "/"
                break

        # Detect naming pattern from a sample test file
        test_patterns = ["*_test.go", "test_*.py", "*.test.ts", "*.test.js", "*.spec.ts", "*Test.java"]
        for pattern in test_patterns:
            matches = list(repo_path.glob(f"**/{pattern}"))
            # Skip vendor/node_modules
            matches = [m for m in matches if "vendor" not in str(m) and "node_modules" not in str(m)]
            if matches:
                info["pattern"] = pattern
                break

        return info

    def _build_pre_context(
        self,
        language: str,
        framework: str,
        critical_paths: list[dict[str, str]],
        test_info: dict[str, str],
    ) -> str:
        """
        Build pre-context summary from detected repo signals.

        This is passed to the LLM as seed context so it doesn't have to
        rediscover what we already know deterministically.

        Args:
            language: Detected programming language
            framework: Detected framework
            critical_paths: List of critical path dicts
            test_info: Dict with test directory and pattern info

        Returns:
            Formatted pre-context string for the LLM prompt
        """
        lines = [
            f"Language: {language}",
            f"Framework: {framework}",
        ]

        if critical_paths:
            lines.append("\nDetected critical paths:")
            for cp in critical_paths:
                lines.append(f"  - {cp['path']} — {cp['reason']}")

        if test_info.get("test_dir"):
            lines.append(f"\nTest directory: {test_info['test_dir']}")
        if test_info.get("pattern"):
            lines.append(f"Test naming pattern: {test_info['pattern']}")

        return "\n".join(lines)

    SKILL_GENERATOR_SYSTEM_PROMPT = """\
You are a skill-creator agent. Your job is to generate a {skill_type} SKILL.md \
for a repository that doesn't have one yet.

Follow skill-creator best practices:
- YAML frontmatter with name and description (required)
- Concise — only include what an AI reviewer actually needs
- Progressive disclosure — keep SKILL.md under 200 lines
- Use imperative/infinitive form in instructions

The generated skill MUST:
1. Have frontmatter with: name: {skill_type}, description (comprehensive), auto_generated: true
2. Describe the repo's language, framework, and architecture
3. For risk-assessment: define explicit severity tiers (HIGH/MEDIUM/LOW) with concrete \
criteria and file path risk maps
4. For code-review: define domain context, conventions, critical patterns, and what \
matters most for reviewers in this repo
5. List critical paths that warrant careful review with reasons
6. Document test patterns and conventions
7. Include an "Auto-Approval Policy" section that explicitly states: \
"Not available. This skill was auto-generated. Auto-approve is disabled. \
Manual review is required."

The generated skill MUST NOT:
- Include an actual auto-approval policy that enables auto-approve
- Include information Claude already knows (general coding best practices)
- Exceed 200 lines
- Include README, changelog, or meta-documentation

Output ONLY the SKILL.md content. No explanation, no markdown fences, no preamble. \
Start directly with the --- frontmatter.
"""

    SKILL_GENERATOR_USER_PROMPT = """\
Generate a {skill_type} SKILL.md for this repository.

<pre_context>
{pre_context}
</pre_context>

<task>
1. Read the repository structure using Glob to understand the codebase layout
2. Read key config files (go.mod, package.json, CODEOWNERS, etc.) for deeper context
3. Identify the critical business logic paths beyond what pre_context detected
4. Generate a concise {skill_type} SKILL.md for this repo

Focus on repo-specific knowledge that a generic reviewer wouldn't know. \
Don't repeat generic coding advice.

Output ONLY the SKILL.md content starting with --- frontmatter.
</task>
"""

    async def _generate_skill_via_llm(
        self,
        repo_directory: str,
        pre_context: str,
        skill_type: str = "risk-assessment",
    ) -> str:
        """
        Generate a SKILL.md using ClaudeCodeTool.

        Invokes Claude Code with the repo as working directory, passing
        pre-detected context and skill-creator guidelines. Claude reads
        the repo for deeper context and generates a proper SKILL.md.

        Args:
            repo_directory: Path to cloned repository (working directory)
            pre_context: Pre-detected repo context summary
            skill_type: Type of skill to generate ("risk-assessment" or "code-review")

        Returns:
            Generated SKILL.md content string, or empty string on failure
        """
        from src.agents.terminal_agents.claude_code import ClaudeCodeTool

        claude_tool = ClaudeCodeTool.get_instance()

        system_prompt = self.SKILL_GENERATOR_SYSTEM_PROMPT.replace(
            "{skill_type}", skill_type
        )
        user_prompt = self.SKILL_GENERATOR_USER_PROMPT.replace(
            "{skill_type}", skill_type
        ).format(pre_context=pre_context)

        self._logger.info(
            f"Generating {skill_type} skill via LLM for {repo_directory}"
        )

        response = await claude_tool.execute({
            "action": "run_prompt",
            "prompt": user_prompt,
            "system_prompt": system_prompt,
            "working_directory": repo_directory,
        })

        if "error" in response:
            self._logger.error(
                f"Skill generation LLM error: {response.get('message', 'unknown')}"
            )
            return ""

        result = response.get("result", "")

        # Strip preamble text before frontmatter (LLM sometimes adds explanation)
        result = self._strip_skill_preamble(result)

        # Validate the output has frontmatter
        if not result.startswith("---"):
            self._logger.warning(
                f"Generated skill missing frontmatter, got: {result[:100]}"
            )
            return ""

        return result

    def _strip_skill_preamble(self, text: str) -> str:
        """
        Strip preamble text before YAML frontmatter in generated skill output.

        LLMs sometimes add explanation text like "Now I have enough context..."
        before the actual --- frontmatter. This finds the first --- and returns
        everything from there.

        Args:
            text: Raw LLM output

        Returns:
            Text starting from the first --- frontmatter delimiter
        """
        if not text:
            return text

        text = text.strip()

        # Already starts with frontmatter
        if text.startswith("---"):
            return text

        # Find first --- on its own line
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if line.strip() == "---":
                stripped = "\n".join(lines[i:])
                self._logger.info(
                    f"Stripped {i} preamble lines from generated skill"
                )
                return stripped

        return text

    def _scan_available_skills(self, repo_directory: str) -> list[str]:
        """
        Scan the cloned repo's .claude/skills/ for available skill directories.

        This provides ground truth for verifying the LLM's self-reported
        rule_source. Only skills with a SKILL.md file are counted.

        Args:
            repo_directory: Path to the cloned repository

        Returns:
            List of skill names that actually exist (e.g. ["code-review"])
        """
        skills_dir = Path(repo_directory) / ".claude" / "skills"
        available = []

        if not skills_dir.exists():
            return available

        try:
            for item in skills_dir.iterdir():
                if item.is_dir() and (item / "SKILL.md").exists():
                    available.append(item.name)
        except Exception as e:
            self._logger.warning(f"Failed to scan available skills: {e}")

        return available

    async def _run_subagents_parallel(
        self,
        working_directory: str,
        diff: str,
        pr_context: Dict[str, Any],
    ) -> List[SubAgentResult]:
        """
        Run all core sub-agents in parallel via SubAgentRegistry.

        Args:
            working_directory: Path to cloned repository
            diff: PR diff content
            pr_context: PR metadata (title, description, branch, etc.)

        Returns:
            List of SubAgentResult from all agents (including failures)
        """
        # Create all core agents via registry
        agents = SubAgentRegistry.create_core_agents(
            working_directory=working_directory,
            kit=self._kit,  # Share kit instance
            confidence_threshold=self._confidence_threshold,
        )

        if not agents:
            self._logger.warning("No sub-agents registered")
            return []

        self._logger.info(f"Created {len(agents)} sub-agents via registry")

        # Run all agents in parallel
        tasks = [
            agent.execute(
                diff=diff,
                pr_number=pr_context["pr_number"],
                repository=pr_context["repository"],
                title=pr_context["title"],
                description=pr_context["description"],
                branch=pr_context["branch"],
            )
            for agent in agents
        ]

        # Gather results (return_exceptions=True for graceful failure handling)
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to failed SubAgentResults
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self._logger.error(
                    f"Sub-agent {agents[i].category} failed: {result}",
                    exc_info=True,
                )
                # Create failed result
                processed_results.append(
                    SubAgentResult(
                        category=agents[i].category,
                        suggestions=[],
                        success=False,
                        error=str(result),
                    )
                )
            else:
                processed_results.append(result)

        return processed_results

    def _merge_suggestions(
        self, results: List[SubAgentResult]
    ) -> List[Dict[str, Any]]:
        """
        Merge suggestions from all successful sub-agents.

        Args:
            results: List of SubAgentResult from all agents

        Returns:
            Merged list of suggestion dictionaries
        """
        all_suggestions = []

        for result in results:
            if result.success:
                for suggestion in result.suggestions:
                    suggestion["source_subagent"] = result.category
                    if result.skills_used:
                        suggestion["source_skill"] = ", ".join(result.skills_used)
                all_suggestions.extend(result.suggestions)
                self._logger.info(
                    f"Sub-agent[{result.category}] contributed {result.suggestion_count} suggestions "
                    f"({result.execution_time_ms}ms)"
                )
            else:
                self._logger.warning(
                    f"Sub-agent[{result.category}] failed: {result.error}"
                )

        self._logger.info(
            f"Total suggestions before filtering: {len(all_suggestions)}"
        )
        return all_suggestions

    def _aggregate_tool_usage(
        self, subagent_results: List[SubAgentResult]
    ) -> tuple[List[Dict[str, Any]], List[str]]:
        """
        Aggregate MCP calls and skills used from all sub-agents.

        Args:
            subagent_results: List of SubAgentResult from all agents

        Returns:
            Tuple of (mcp_calls, skills_used):
            - mcp_calls: List of all MCP tool invocations
            - skills_used: List of all skill names used
        """
        all_mcp_calls = []
        all_skills_used = []

        for result in subagent_results:
            if result.mcp_calls:
                all_mcp_calls.extend(result.mcp_calls)
            if result.skills_used:
                all_skills_used.extend(result.skills_used)

        # Deduplicate skills (keep unique names)
        unique_skills = list(set(all_skills_used))

        self._logger.info(
            f"Aggregated tool usage: {len(all_mcp_calls)} MCP calls, "
            f"{len(unique_skills)} unique skills"
        )

        return all_mcp_calls, unique_skills

    async def _generate_pr_description(
        self,
        diff: str,
        repository: str,
        pr_number: int,
        title: str,
        description: str,
        branch: str,
        base_branch: str,
        working_directory: str,
    ):
        """
        Generate and post PR description using PR Description Generator.

        Args:
            diff: PR diff content
            repository: Repository in "owner/repo" format
            pr_number: Pull request number
            title: PR title
            description: PR description/body
            branch: Source branch name
            base_branch: Target branch name
            working_directory: Cloned repo directory

        Returns:
            PRDescriptionResult with generation status
        """
        from src.agents.review_agents.models import PRDescriptionResult

        try:
            # Lazy initialize description generator
            if self._description_generator is None:
                self._description_generator = PRDescriptionGenerator(
                    working_directory=working_directory,
                    kit=self._kit,
                    github_bot=self._github_bot,
                )

            # Generate and post description
            return await self._description_generator.generate_and_post(
                diff=diff,
                repository=repository,
                pr_number=pr_number,
                title=title,
                description=description,
                branch=branch,
                target_branch=base_branch,
            )

        except Exception as e:
            self._logger.error(
                f"PR description generation failed for {repository}#{pr_number}: {e}",
                exc_info=True,
            )
            return PRDescriptionResult(error=str(e))

    async def _cleanup_working_directory(self, working_directory: str) -> None:
        """
        Remove the cloned repository temp directory.

        Args:
            working_directory: Path to temp directory to remove
        """
        try:
            # Use asyncio.to_thread to avoid blocking the event loop
            await asyncio.to_thread(shutil.rmtree, working_directory, True)
            self._logger.info(
                f"Cleaned up working directory: {working_directory}"
            )
        except Exception as e:
            # Don't fail the whole review if cleanup fails
            self._logger.warning(
                f"Failed to cleanup {working_directory}: {e}"
            )
