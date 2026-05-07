"""
GitHub PR Comment Publisher for PR Review Agent.

Publishes filtered code review suggestions as GitHub PR review with inline
comments that select specific lines in the diff using gh CLI.
"""

import asyncio
import json
import logging
import os
import subprocess
from typing import Any, Dict, List, Optional, Set

from src.constants.github_bots import GitHubBot
from src.providers.github.auth_service import GitHubAuthService
from src.utils.output_filter import redact_secrets

from .models import PublishResult


class GitHubPRCommentPublisher:
    """Publishes filtered suggestions as GitHub PR review comments via gh CLI."""

    def __init__(self, github_bot: GitHubBot = GitHubBot.CODE_REVIEW):
        """
        Initialize GitHub PR Comment Publisher.

        Args:
            github_bot: GitHub bot to use for authentication (default: CODE_REVIEW)
        """
        self._github_bot = github_bot
        self._auth_service = GitHubAuthService()
        self._logger = logging.getLogger(__name__)

    def _has_committable_code(self, suggestion_code: Optional[str]) -> bool:
        """
        Safety net: detect obviously non-committable code patterns.

        This is a FALLBACK for when prompts fail to produce clean output.
        Only catches obvious patterns - not meant to be comprehensive.

        Args:
            suggestion_code: The code from suggestion_code field

        Returns:
            True if code appears committable, False if obviously not
        """
        if not suggestion_code or not suggestion_code.strip():
            return False

        code = suggestion_code.strip()
        lines = code.split('\n')

        # Check first non-empty line for obvious patterns
        first_line = ""
        for line in lines:
            if line.strip():
                first_line = line.strip().lower()
                break

        if not first_line:
            return False

        # Obvious non-committable patterns (safety net only)
        non_committable_patterns = [
            # Comments that are instructions, not code
            first_line.startswith('//') and any(
                kw in first_line for kw in ['delete', 'remove', 'todo', 'fixme']
            ),
            first_line.startswith('#') and any(
                kw in first_line for kw in ['delete', 'remove', 'todo', 'fixme']
            ),
            # Pure instruction text
            first_line.startswith('todo'),
            first_line.startswith('fixme'),
            # Delete instructions
            'delete this' in first_line,
            'remove this' in first_line,
        ]

        if any(non_committable_patterns):
            self._logger.info(
                f"Safety net: detected non-committable pattern: {first_line[:50]}"
            )
            return False

        return True

    async def publish(
        self,
        repository: str,
        pr_number: int,
        suggestions: List[Dict[str, Any]],
        review_event: str = "COMMENT",
        mcp_calls: Optional[List[Dict[str, Any]]] = None,
        skills_used: Optional[List[str]] = None,
        severity_assessment: Optional[Any] = None,
        subagent_results: Optional[List["SubAgentResult"]] = None,
    ) -> PublishResult:
        """
        Post suggestions as GitHub review via gh api.

        Args:
            repository: Repository in "owner/repo" format
            pr_number: Pull request number
            suggestions: List of suggestion dictionaries
            review_event: Review event type ("COMMENT", "APPROVE", "REQUEST_CHANGES")
            mcp_calls: Optional list of MCP tool invocations made during review
            skills_used: Optional list of skill names used during review
            severity_assessment: Optional SeverityAssessment to post as separate comment

        Returns:
            PublishResult with success status, review ID, and metrics
        """
        try:
            # 1. Set GITHUB_TOKEN env var from GitHubAuthService
            token = await self._auth_service.get_token(self._github_bot)
            env = os.environ.copy()
            env["GITHUB_TOKEN"] = token

            # 2. Get PR info (commit SHA, files)
            pr_info = await self._get_pr_info(repository, pr_number, env)
            commit_sha = pr_info["head_sha"]
            pr_files = set(pr_info["files"])

            # 3. Build review payload
            payload = self._build_review_payload(
                commit_sha, suggestions, pr_files, review_event,
                mcp_calls=mcp_calls, skills_used=skills_used,
            )

            # 4. Post review via gh api
            review = await self._post_review(repository, pr_number, payload, env)

            # 4.5 Post severity assessment as separate comment
            if severity_assessment:
                try:
                    await self._post_severity_comment(
                        repository, pr_number, severity_assessment, env,
                        subagent_results=subagent_results
                    )
                except Exception as sev_error:
                    self._logger.warning(
                        f"Failed to post severity comment: {sev_error}. "
                        "Review was posted successfully."
                    )

            # 5. Return result
            comments_count = len(payload.get("comments", []))
            skipped_count = len(suggestions) - comments_count

            return PublishResult(
                success=True,
                review_id=review.get("id"),
                comments_posted=comments_count,
                comments_skipped=skipped_count,
            )

        except FileNotFoundError as e:
            self._logger.error(f"gh CLI not found: {e}")
            return PublishResult(success=False, error="gh CLI not found")
        except subprocess.CalledProcessError as e:
            # Log detailed error info for debugging 422 errors
            self._logger.error(f"gh api failed with return code {e.returncode}")
            self._logger.error(f"stderr: {e.stderr}")
            self._logger.error(f"stdout: {e.stdout}")

            # Log payload details to help debug which comment caused the issue
            if 'payload' in locals():
                self._logger.error(f"commit_id: {payload.get('commit_id', 'N/A')}")
                comments = payload.get("comments", [])
                self._logger.error(f"Total comments in payload: {len(comments)}")
                # Log each comment's details for debugging
                for i, c in enumerate(comments):
                    self._logger.error(
                        f"Comment[{i}]: path={c.get('path')}, "
                        f"line={c.get('line')}, start_line={c.get('start_line', 'N/A')}, "
                        f"side={c.get('side')}"
                    )

            return PublishResult(success=False, error=str(e.stderr))
        except json.JSONDecodeError as e:
            self._logger.error(f"Invalid API response: {e}")
            return PublishResult(success=False, error="Invalid API response")
        except Exception as e:
            self._logger.error(f"Publish failed: {e}")
            return PublishResult(success=False, error=str(e))

    async def _get_pr_info(
        self, repository: str, pr_number: int, env: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Get PR head commit SHA and changed files via gh api (async).

        Args:
            repository: Repository in "owner/repo" format
            pr_number: Pull request number
            env: Environment variables with GITHUB_TOKEN

        Returns:
            Dictionary with head_sha and files list
        """
        # Get head SHA from PR (async - doesn't block event loop)
        process = await asyncio.create_subprocess_exec(
            "gh", "api",
            f"repos/{repository}/pulls/{pr_number}",
            "--jq", ".head.sha",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise subprocess.CalledProcessError(
                process.returncode, "gh api",
                output=stdout.decode(), stderr=stderr.decode()
            )

        head_sha = stdout.decode().strip().strip('"')

        # Get files from PR files endpoint (async)
        process = await asyncio.create_subprocess_exec(
            "gh", "api",
            f"repos/{repository}/pulls/{pr_number}/files",
            "--jq", "map(.filename)",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise subprocess.CalledProcessError(
                process.returncode, "gh api",
                output=stdout.decode(), stderr=stderr.decode()
            )

        files = json.loads(stdout.decode())

        return {"head_sha": head_sha, "files": files}

    def _build_review_payload(
        self,
        commit_sha: str,
        suggestions: List[Dict[str, Any]],
        pr_files: Set[str],
        review_event: str,
        mcp_calls: Optional[List[Dict[str, Any]]] = None,
        skills_used: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Build GitHub review API payload.

        Separates suggestions into:
        - inline: files in PR → posted as inline comments
        - general: files NOT in PR → shown in review body

        Args:
            commit_sha: Commit SHA to attach review to
            suggestions: List of suggestion dictionaries with comment_type field
            pr_files: Set of files in the PR
            review_event: Review event type
            mcp_calls: Optional list of MCP tool invocations made during review
            skills_used: Optional list of skill names used during review

        Returns:
            GitHub review API payload dictionary
        """
        # Handle empty suggestions
        if not suggestions:
            return {
                "commit_id": commit_sha,
                "body": "## AI Code Review\n\nNo issues found in this PR.",
                "event": review_event,
                "comments": [],
            }

        # Separate by comment_type
        inline_suggestions = [
            s for s in suggestions
            if s.get("comment_type", "inline") == "inline"
        ]
        general_suggestions = [
            s for s in suggestions
            if s.get("comment_type") == "general"
        ]

        # Build inline comments (only for files in PR)
        comments = self._build_comments(inline_suggestions, pr_files)

        # Build body with correct inline count + general suggestions + tool usage
        body = self._build_body(
            len(comments),
            general_suggestions,
            mcp_calls=mcp_calls,
            skills_used=skills_used,
        )

        return {
            "commit_id": commit_sha,
            "body": body,
            "event": review_event,
            "comments": comments,
        }

    def _build_comments(
        self, suggestions: List[Dict[str, Any]], pr_files: Set[str]
    ) -> List[Dict[str, Any]]:
        """
        Build inline comment objects from suggestions.

        Args:
            suggestions: List of suggestion dictionaries
            pr_files: Set of files in the PR

        Returns:
            List of GitHub review comment objects
        """
        comments = []

        for suggestion in suggestions:
            file_path = suggestion.get("file", "")

            # Skip files not in PR
            if file_path not in pr_files:
                self._logger.warning(f"Skipping {file_path} - not in PR")
                continue

            comment = {
                "path": file_path,
                "line": suggestion.get("line", 1),
                "side": "RIGHT",  # Comments on new/modified lines (right side of diff)
                "body": self._format_comment(suggestion),
            }

            # Multi-line comment support
            line_end = suggestion.get("line_end")
            if line_end and line_end > comment["line"]:
                comment["start_line"] = comment["line"]
                comment["line"] = line_end
                self._logger.debug(
                    f"Multi-line comment: {file_path} lines {comment['start_line']}-{comment['line']}"
                )

            # Log comment being added for debugging
            self._logger.info(
                f"Adding comment: path={file_path}, line={comment['line']}, "
                f"start_line={comment.get('start_line', 'N/A')}"
            )

            comments.append(comment)

        return comments

    def _build_body(
        self,
        inline_count: int,
        general_suggestions: List[Dict[str, Any]],
        mcp_calls: Optional[List[Dict[str, Any]]] = None,
        skills_used: Optional[List[str]] = None,
    ) -> str:
        """
        Build review body with inline count, general suggestions, and tool usage.

        Args:
            inline_count: Number of inline comments posted
            general_suggestions: Suggestions for files not in PR
            mcp_calls: Optional list of MCP tool invocations made during review
            skills_used: Optional list of skill names used during review

        Returns:
            Formatted review body text
        """
        parts = ["## AI Code Review\n"]

        # Inline suggestions summary
        if inline_count > 0:
            parts.append(f"Found **{inline_count}** inline suggestion(s).\n")

        # General suggestions section (files not in PR)
        if general_suggestions:
            parts.append("\n---\n")
            parts.append("### Related Suggestions\n")
            parts.append("_These files are not part of this PR but may need attention:_\n")

            for s in general_suggestions:
                file_path = s.get("file", "unknown")
                line = s.get("line", "N/A")
                desc = s.get("description", "")
                category = s.get("category", "GENERAL")
                importance = s.get("importance", 5)

                parts.append(f"\n**`{file_path}:{line}`** [{category}, importance: {importance}]")
                parts.append(f"\n> {desc}\n")

        # Tool usage section
        tool_usage_section = self._build_tool_usage_section(mcp_calls, skills_used)
        if tool_usage_section:
            parts.append("\n---\n")
            parts.append(tool_usage_section)

        # No suggestions case
        if inline_count == 0 and not general_suggestions:
            return "## AI Code Review\n\nNo issues found in this PR."

        # Redact any secrets that may have leaked into the review body
        body_text = "\n".join(parts)
        return redact_secrets(body_text)

    def _build_tool_usage_section(
        self,
        mcp_calls: Optional[List[Dict[str, Any]]],
        skills_used: Optional[List[str]],
    ) -> str:
        """
        Build tool usage section for the review body.

        Extracts unique MCP server names from tool calls and formats them
        along with skills used into a collapsible details section.

        Args:
            mcp_calls: List of MCP tool invocations with tool_name field
            skills_used: List of skill names used during review

        Returns:
            Formatted tool usage section string, or empty string if no tools used
        """
        # Extract unique MCP server names from tool calls
        mcp_servers: Set[str] = set()
        if mcp_calls:
            for call in mcp_calls:
                tool_name = call.get("tool_name", "")
                # MCP tools follow pattern: mcp__server-name__tool_name
                if tool_name.startswith("mcp__"):
                    parts = tool_name.split("__")
                    if len(parts) >= 2:
                        server_name = parts[1]
                        mcp_servers.add(server_name)

        # Build section only if we have tool usage
        if not mcp_servers and not skills_used:
            return ""

        section_parts = ["### Tools Used\n"]

        if mcp_servers:
            servers_list = ", ".join(sorted(mcp_servers))
            section_parts.append(f"**MCP Servers:** {servers_list}\n")

        if skills_used:
            skills_list = ", ".join(sorted(skills_used))
            section_parts.append(f"**Skills:** {skills_list}\n")

        return "\n".join(section_parts)

    def _format_comment(self, suggestion: Dict[str, Any]) -> str:
        """
        Format single comment body with category and importance.

        Formats suggestions as:
        **Suggestion:** description [CATEGORY, importance: X]

        <details>
        <summary>💡 View suggested fix (click to expand)</summary>

        ```suggestion
        code fix here
        ```
        </details>

        Args:
            suggestion: Suggestion dictionary with fields:
                - description: Text description of the issue/fix
                - category: Category label (BUG, SECURITY, CODE_QUALITY, etc.)
                - importance: Importance score (1-10)
                - suggestion_code: Optional code fix

        Returns:
            Formatted comment body with category and importance tags
        """
        description = suggestion.get("description", "No description provided")
        category = suggestion.get("category", "GENERAL")
        importance = suggestion.get("importance")
        source_subagent = suggestion.get("source_subagent")
        source_skill = suggestion.get("source_skill")

        # Redact any secrets that may have leaked into description
        description = redact_secrets(description)

        # Format: **Suggestion:** description [CATEGORY, importance: X]
        if importance is not None:
            body = f"**Suggestion:** {description} [{category}, importance: {importance}]"
        else:
            body = f"**Suggestion:** {description} [{category}]"

        # Source attribution line
        if source_subagent:
            source_parts = [f"sub-agent: `{source_subagent}`"]
            if source_skill:
                source_parts.append(f"skill: `{source_skill}`")
            body += f"\n_Source: {' | '.join(source_parts)}_"

        # Append suggestion code block if present AND committable
        # Wrap in collapsible <details> tag for cleaner UI
        suggestion_code = suggestion.get("suggestion_code")
        if suggestion_code and self._has_committable_code(suggestion_code):
            # Redact secrets in code suggestions too
            suggestion_code = redact_secrets(suggestion_code)
            body += "\n\n<details>\n"
            body += "<summary>💡 View suggested fix (click to expand)</summary>\n\n"
            body += f"```suggestion\n{suggestion_code}\n```\n"
            body += "</details>"

        return body

    async def _post_review(
        self,
        repository: str,
        pr_number: int,
        payload: Dict[str, Any],
        env: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Post review via gh api subprocess call (async).

        Args:
            repository: Repository in "owner/repo" format
            pr_number: Pull request number
            payload: Review payload dictionary
            env: Environment variables with GITHUB_TOKEN

        Returns:
            GitHub review response dictionary
        """
        # Use async subprocess to avoid blocking the event loop
        process = await asyncio.create_subprocess_exec(
            "gh", "api",
            f"repos/{repository}/pulls/{pr_number}/reviews",
            "--method", "POST",
            "--input", "-",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        stdout, stderr = await process.communicate(input=json.dumps(payload).encode())

        if process.returncode != 0:
            raise subprocess.CalledProcessError(
                process.returncode, "gh api",
                output=stdout.decode(), stderr=stderr.decode()
            )

        return json.loads(stdout.decode())

    async def _post_severity_comment(
        self,
        repository: str,
        pr_number: int,
        assessment: Any,
        env: Dict[str, str],
        subagent_results: Optional[List["SubAgentResult"]] = None,
        filtered_suggestions: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        Post severity assessment as a separate PR comment.

        Optionally includes pre-mortem analysis if PreMortemSubAgent ran.
        Uses <!-- pr-severity-bot --> marker for idempotent updates.
        Finds existing comment and updates it, or creates a new one.

        Args:
            repository: Repository in "owner/repo" format
            pr_number: Pull request number
            assessment: SeverityAssessment instance
            env: Environment variables with GITHUB_TOKEN
            subagent_results: Optional list of all subagent results
        """
        from src.agents.review_agents.constants import SEVERITY_BOT_MARKER, SubAgentCategory

        # Extract pre-mortem summary if available
        pre_mortem_summary = None
        if subagent_results:
            pre_mortem_result = next(
                (r for r in subagent_results
                 if r.category == SubAgentCategory.PRE_MORTEM.value),
                None
            )
            if pre_mortem_result and pre_mortem_result.summary_data:
                pre_mortem_summary = pre_mortem_result.summary_data
                self._logger.info(
                    f"Including pre-mortem analysis in severity comment "
                    f"({pre_mortem_summary.get('total_issues', 0)} issues found)"
                )

        comment_body = self._build_severity_comment_body(
            assessment, pre_mortem_summary, subagent_results=subagent_results,
        )

        # Find existing severity comment
        existing_id = await self._find_comment_by_marker(
            repository, pr_number, SEVERITY_BOT_MARKER, env
        )

        if existing_id:
            self._logger.info(
                f"Updating existing severity comment {existing_id} "
                f"on {repository}#{pr_number}"
            )
            await self._update_comment(repository, existing_id, comment_body, env)
        else:
            self._logger.info(
                f"Creating new severity comment on {repository}#{pr_number}"
            )
            process = await asyncio.create_subprocess_exec(
                "gh", "pr", "comment", str(pr_number),
                "--repo", repository,
                "--body", comment_body,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                raise RuntimeError(
                    f"Failed to post severity comment: {stderr.decode().strip()}"
                )

        self._logger.info(
            f"Severity comment posted on {repository}#{pr_number}: "
            f"{assessment.severity.upper()}"
        )

    async def _find_comment_by_marker(
        self,
        repository: str,
        pr_number: int,
        marker: str,
        env: Dict[str, str],
    ) -> Optional[int]:
        """
        Find existing PR comment by HTML marker string.

        Args:
            repository: Repository in "owner/repo" format
            pr_number: Pull request number
            marker: HTML comment marker to search for
            env: Environment variables with GITHUB_TOKEN

        Returns:
            Comment ID if found, None otherwise
        """
        jq_filter = (
            f'.[] | select(.body | contains("{marker}")) | .id'
        )
        process = await asyncio.create_subprocess_exec(
            "gh", "api",
            f"repos/{repository}/issues/{pr_number}/comments",
            "--jq", jq_filter,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            self._logger.warning(f"Failed to fetch comments: {stderr.decode()}")
            return None

        output = stdout.decode().strip()
        if output:
            first_id = output.split('\n')[0].strip()
            if first_id.isdigit():
                return int(first_id)
        return None

    async def _update_comment(
        self,
        repository: str,
        comment_id: int,
        body: str,
        env: Dict[str, str],
    ) -> None:
        """
        Update an existing comment via GitHub API.

        Args:
            repository: Repository in "owner/repo" format
            comment_id: Comment ID to update
            body: New comment body
            env: Environment variables with GITHUB_TOKEN
        """
        process = await asyncio.create_subprocess_exec(
            "gh", "api",
            f"repos/{repository}/issues/comments/{comment_id}",
            "--method", "PATCH",
            "--field", f"body={body}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise RuntimeError(f"Failed to update comment: {stderr.decode()}")

        self._logger.info(f"Updated existing comment {comment_id}")

    def _build_severity_comment_body(
        self,
        assessment: Any,
        pre_mortem_summary: Optional[Dict[str, Any]] = None,
        subagent_results: Optional[List["SubAgentResult"]] = None,
    ) -> str:
        """
        Build the full severity comment body with bot marker.

        Optionally includes pre-mortem analysis section if PreMortemSubAgent ran,
        and sub-agent attribution table for skill transparency.

        Args:
            assessment: SeverityAssessment instance
            pre_mortem_summary: Optional summary_data from PreMortemSubAgent
            subagent_results: Optional list of all subagent results for attribution

        Returns:
            Formatted markdown comment body with severity badge,
            reasoning, attribution, and optional pre-mortem analysis
        """
        from src.agents.review_agents.constants import SEVERITY_BOT_MARKER

        severity_upper = assessment.severity.upper()
        badge = {"LOW": "\U0001f7e2", "MEDIUM": "\U0001f7e1", "HIGH": "\U0001f534"}.get(
            severity_upper, "\u26aa"
        )

        # Format rule source display
        if assessment.rule_source == "generated_context":
            if assessment.repo_skill_name:
                rule_source_display = (
                    f"Generated Context (`{assessment.repo_skill_name}` skill, "
                    "auto-generated from repo structure)"
                )
            else:
                rule_source_display = "Generated Context (auto-generated from repo structure)"
        elif assessment.rule_source == "repo_skill" and assessment.repo_skill_name:
            rule_source_display = f"{assessment.rule_source} (`{assessment.repo_skill_name}` skill)"
        else:
            rule_source_display = assessment.rule_source

        lines = [
            SEVERITY_BOT_MARKER,
            f"## PR Risk Assessment: {badge} {severity_upper}\n",
            f"**Rule Source:** {rule_source_display}",
        ]

        # Auto-generated skill verdict: show when the skill would have
        # auto-approved but was blocked because it's auto-generated.
        # Actual review stays COMMENT — this is informational only.
        if (assessment.auto_approve_raw
                and assessment.rule_source == "generated_context"):
            lines.append(
                "\n> \u2705 **Auto-approved by RCoRe V2++** "
                "(verdict only — auto-generated skill, not applied)\n"
            )

        lines.append(
            f"**Confidence:** {int(assessment.confidence * 100)}%\n"
        )

        # Reasoning
        lines.append("### Reasoning\n")
        lines.append(f"{assessment.reasoning}\n")

        # Pre-mortem analysis section (if available)
        if pre_mortem_summary:
            lines.append("---\n")
            lines.append("## \U0001f50d Pre-Mortem Analysis\n")  # 🔍 emoji

            # Categories checked
            categories = pre_mortem_summary.get("categories_checked", [])
            if categories:
                lines.append("**Categories Checked:**")
                for cat in categories:
                    # Format: infrastructure-database → Database
                    display_name = (cat.replace("infrastructure-", "")
                                       .replace("services-", "")
                                       .replace("quality-", "")
                                       .replace("observability-", "")
                                       .replace("domain-", "")
                                       .replace("-", " ")
                                       .title())
                    lines.append(f"- \u2705 {display_name}")  # ✅ emoji
                lines.append("")

            # Severity breakdown
            severity = pre_mortem_summary.get("severity_breakdown", {})
            if any(severity.values()):
                lines.append("**Issues by Severity:**")
                if severity.get("critical", 0) > 0:
                    lines.append(f"- \U0001f6a8 Critical (importance 9-10): {severity['critical']} issues")  # 🚨
                if severity.get("high", 0) > 0:
                    lines.append(f"- \u26a0\ufe0f High (importance 7-8): {severity['high']} issues")  # ⚠️
                if severity.get("medium", 0) > 0:
                    lines.append(f"- \U0001f4cb Medium (importance 5-6): {severity['medium']} issues")  # 📋
                if severity.get("low", 0) > 0:
                    lines.append(f"- \u2139\ufe0f Low (importance 1-4): {severity['low']} issues")  # ℹ️
                lines.append("")

            # Files affected
            files = pre_mortem_summary.get("files_affected", [])
            if files:
                lines.append("**Files Affected:**")
                for item in files[:5]:  # Top 5 files
                    lines.append(f"- `{item['file']}` ({item['issue_count']} issues)")
                if len(files) > 5:
                    lines.append(f"- *...and {len(files) - 5} more*")
                lines.append("")

            # Statistics
            total = pre_mortem_summary.get("total_issues", 0)
            checks_run = pre_mortem_summary.get("total_checks_run", 0)
            checks_passed = pre_mortem_summary.get("total_checks_passed", 0)
            exec_time = pre_mortem_summary.get("execution_time_ms", 0) / 1000.0

            lines.append("**Analysis Summary:**")
            lines.append(f"- Total Checks Run: {checks_run} out of 181 available")
            lines.append(f"- Issues Found: {total}")
            lines.append(f"- Checks Passed: {checks_passed}")
            lines.append(f"- Analysis Time: {exec_time:.1f}s\n")

            # Reference files (collapsible)
            ref_files = pre_mortem_summary.get("reference_files_loaded", [])
            if ref_files:
                lines.append("<details>")
                lines.append("<summary>\U0001f4da Reference Files Used</summary>\n")  # 📚
                for ref in ref_files:
                    lines.append(f"- {ref}")
                lines.append("</details>\n")

        # Sub-agent attribution table
        if subagent_results:
            contributing = [
                r for r in subagent_results
                if r.success and not r.was_skipped and r.suggestion_count > 0
            ]
            if contributing:
                lines.append("---\n")
                lines.append("<details>")
                lines.append("<summary>Sub-Agent Attribution</summary>\n")
                lines.append("| Sub-Agent | Suggestions | Skills Used |")
                lines.append("|-----------|-------------|-------------|")
                for r in sorted(contributing, key=lambda x: x.category):
                    skills = ", ".join(r.skills_used) if r.skills_used else "-"
                    lines.append(
                        f"| `{r.category}` | {r.suggestion_count} | {skills} |"
                    )
                lines.append("\n</details>\n")

        # Footer
        lines.append("---")
        lines.append("*Assessed by rCoRe*")

        body = "\n".join(lines)
        return redact_secrets(body)
