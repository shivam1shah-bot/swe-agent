"""
Action Executor for Comment Analyzer

Executes actions based on sub-agent results:
- Commit status
- Analysis summary comment
- Comment resolution
"""

import json
import logging
import requests
from typing import List, Dict, Any

from src.services.comment_analyzer.sub_agent_base import SubAgentResult, Comment

logger = logging.getLogger(__name__)


class ActionExecutor:
    """Executes actions based on sub-agent results"""

    def __init__(self, github_token: str, repository: str, commit_sha: str):
        self.github_token = github_token
        self.repository = repository
        self.commit_sha = commit_sha
        self.headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json",
        }
        self.base_url = f"https://api.github.com/repos/{repository}"

    def execute_commit_status(self,
                             result: SubAgentResult,
                             status_name: str,
                             blocking_enabled: bool,
                             run_url: str) -> Dict[str, Any]:
        """Execute commit status action"""
        logger.info(f"[Action] Creating commit status for {result.sub_agent_name}")

        # Determine state based on result and blocking setting
        if result.status == "PASS":
            state = "success"
            description = "All comment checks passed"
        else:
            # FAIL status
            if blocking_enabled:
                state = "failure"
                description = f"{result.unaddressed_by_severity['critical']} critical issue(s) - PR blocked"
            else:
                state = "success"  # Advisory mode: don't fail the status
                description = f"{result.unaddressed_by_severity['critical']} critical issue(s) found (advisory)"

        # Create commit status
        url = f"{self.base_url}/statuses/{self.commit_sha}"
        payload = {
            "state": state,
            "target_url": run_url,
            "description": description,
            "context": status_name
        }

        response = requests.post(url, headers=self.headers, json=payload)

        success = response.status_code == 201
        if success:
            logger.info(f"[Action] ✅ Commit status created: {state}")
        else:
            logger.error(f"[Action] ❌ Failed to create commit status: {response.status_code}")
            logger.error(f"[Action] Response: {response.text}")

        return {
            "type": "commit_status",
            "status_name": status_name,
            "state": state,
            "description": description,
            "success": success,
            "response_code": response.status_code,
            "error": None if success else f"HTTP {response.status_code}: {response.text}"
        }

    def post_analysis_summary(self,
                              result: SubAgentResult,
                              pr_number: int,
                              blocking_enabled: bool) -> Dict[str, Any]:
        """
        Post a summary comment (not a review) about the analysis results.

        This is posted as an issue comment, clearly separate from PR reviews.
        """
        logger.info(f"[Action] Posting analysis summary comment for {result.sub_agent_name}")

        # Build summary body with clear distinction from reviews
        body = f"## 📊 Comment Analysis Summary - {result.sub_agent_name.upper()}\n\n"

        # Status badge
        if result.status == "PASS":
            status_badge = "✅ **PASS**"
        else:
            status_badge = "❌ **FAIL**" if blocking_enabled else "⚠️ **ADVISORY**"

        body += f"**Analysis Status:** {status_badge}\n\n"

        # Summary table
        body += "### 📈 Analysis Results\n\n"
        body += "| Metric | Count |\n"
        body += "|--------|-------|\n"
        body += f"| Total Comments Analyzed | {result.total_comments} |\n"
        body += f"| ✅ Addressed | {result.addressed} |\n"
        body += f"| ❌ Not Addressed | {result.not_addressed} |\n"
        body += f"| 🔄 Auto-Resolved | {len(result.addressed_comments)} |\n\n"

        # Breakdown by severity
        body += "### 🎯 Unaddressed by Severity\n\n"
        body += "| Severity | Count |\n"
        body += "|----------|-------|\n"
        body += f"| 🔴 Critical | {result.unaddressed_by_severity['critical']} |\n"
        body += f"| 🟠 High | {result.unaddressed_by_severity['high']} |\n"
        body += f"| 🟡 Medium | {result.unaddressed_by_severity['medium']} |\n"
        body += f"| 🔵 Low | {result.unaddressed_by_severity['low']} |\n\n"

        # Critical issues details (if any)
        if result.critical_issues:
            body += "### ⚠️ Critical Issues Requiring Attention\n\n"
            for i, issue in enumerate(result.critical_issues[:5], 1):  # Show max 5
                body += f"{i}. **[{issue.category}]** Severity: {issue.severity}\n"
                body += f"   - File: `{issue.file_path or 'N/A'}`:{issue.line or 'N/A'}\n"
                body += f"   - Preview: {issue.body[:100]}...\n\n"

            if len(result.critical_issues) > 5:
                body += f"_... and {len(result.critical_issues) - 5} more critical issue(s)_\n\n"

        # Addressed comments summary
        if result.addressed_comments:
            body += f"### ✅ Resolved Comments ({len(result.addressed_comments)})\n\n"
            body += "The following comments have been verified as addressed and marked as resolved:\n\n"

            # Group by category
            by_category = {}
            for comment in result.addressed_comments:
                category = comment.category or "other"
                if category not in by_category:
                    by_category[category] = []
                by_category[category].append(comment)

            for category, comments in sorted(by_category.items()):
                body += f"- **{category}**: {len(comments)} comment(s)\n"
            body += "\n"

        # Final status notice
        body += "\n---\n\n"
        if result.status == "FAIL" and blocking_enabled:
            body += "### ⛔ PR Status: BLOCKED\n\n"
            body += f"**{result.unaddressed_by_severity['critical']} critical issue(s)** must be resolved before this PR can be merged.\n\n"
            body += "Please address the critical issues listed above and push your changes. "
            body += "The comment analyzer will automatically re-verify when new commits are pushed.\n"
        elif result.status == "FAIL" and not blocking_enabled:
            body += "### ⚠️ PR Status: ADVISORY MODE\n\n"
            body += f"**{result.unaddressed_by_severity['critical']} critical issue(s)** were found, but blocking is not enabled.\n\n"
            body += "While this PR can be merged, we recommend addressing the critical issues for code quality.\n"
        else:
            body += "### ✅ All Comment Checks Passed!\n\n"
            body += "All flagged issues have been verified as addressed. Great work! 🎉\n"

        body += "\n---\n"
        body += "_🤖 This is an automated analysis summary. "
        body += "Addressed comments have been automatically marked as resolved._\n"

        # Post as issue comment (not a review)
        url = f"{self.base_url}/issues/{pr_number}/comments"
        payload = {
            "body": body
        }

        logger.info(f"[Action] Posting analysis summary as issue comment")
        response = requests.post(url, headers=self.headers, json=payload)

        success = response.status_code == 201
        if success:
            logger.info(f"[Action] ✅ Analysis summary posted successfully")
        else:
            logger.error(f"[Action] ❌ Failed to post analysis summary: {response.status_code}")
            logger.error(f"[Action] Response: {response.text}")
            logger.error(f"[Action] Payload: {json.dumps(payload, indent=2)}")

        return {
            "type": "analysis_summary",
            "success": success,
            "response_code": response.status_code,
            "error": None if success else f"HTTP {response.status_code}: {response.text}"
        }

    def resolve_addressed_comments(self,
                                   addressed_comments: List[Comment],
                                   pr_number: int) -> List[Dict[str, Any]]:
        """
        Mark addressed comments as resolved to close the conversation.

        Uses GitHub GraphQL API to resolve review comment threads.

        Args:
            addressed_comments: List of comments that have been addressed
            pr_number: PR number

        Returns:
            List of action results
        """
        if not addressed_comments:
            logger.info(f"[Action] No comments to resolve")
            return []

        logger.info(f"\n{'='*80}")
        logger.info(f"[Action] Resolving {len(addressed_comments)} addressed comments")
        logger.info(f"{'='*80}")

        actions_executed = []

        for i, comment in enumerate(addressed_comments):
            logger.info(f"\n--- Resolving Comment #{i+1}/{len(addressed_comments)} ---")
            logger.info(f"Comment ID: {comment.id}")
            logger.info(f"File: {comment.file_path}:{comment.line}")
            logger.info(f"Category: {comment.category}")

            try:
                # Use a reply to indicate resolution
                result = self._post_resolution_reply(comment.id, pr_number)

                actions_executed.append(result)

                if result.get("success"):
                    logger.info(f"[Action] ✅ Comment {comment.id} marked as resolved")
                else:
                    logger.warning(f"[Action] ⚠️ Failed to resolve comment {comment.id}: {result.get('error')}")

            except Exception as e:
                logger.exception(f"[Action] ❌ Error resolving comment {comment.id}: {e}")
                actions_executed.append({
                    "type": "resolve_comment",
                    "comment_id": comment.id,
                    "success": False,
                    "error": str(e)
                })

        logger.info(f"\n{'='*80}")
        logger.info(f"[Action] Resolved {sum(1 for a in actions_executed if a.get('success'))} of {len(addressed_comments)} comments")
        logger.info(f"{'='*80}\n")

        return actions_executed

    def _post_resolution_reply(self, comment_id: int, pr_number: int) -> Dict[str, Any]:
        """
        Post a reply to the comment indicating it has been resolved.

        This is a workaround since GitHub REST API v3 doesn't support resolving threads.
        The reply serves as a clear signal to developers that the issue was addressed.
        """
        try:
            # Post a reply to the comment
            url = f"{self.base_url}/pulls/{pr_number}/comments/{comment_id}/replies"

            reply_body = (
                "✅ **Automated Analysis**: This comment has been marked as **RESOLVED**.\n\n"
                "The code review analysis determined that the flagged issue has been addressed "
                "in the current PR state. The violation is no longer present in the code.\n\n"
                "_This is an automated message from the comment analyzer. "
                "If you believe this is incorrect, please reopen the discussion._"
            )

            payload = {
                "body": reply_body
            }

            response = requests.post(url, headers=self.headers, json=payload)

            if response.status_code == 201:
                logger.info(f"[Action] Posted resolution reply to comment {comment_id}")
                return {
                    "type": "resolve_comment",
                    "comment_id": comment_id,
                    "success": True,
                    "method": "reply",
                    "response_code": response.status_code
                }
            else:
                logger.error(f"[Action] Failed to post resolution reply: {response.status_code}")
                logger.error(f"[Action] Response: {response.text}")
                return {
                    "type": "resolve_comment",
                    "comment_id": comment_id,
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "response_code": response.status_code
                }

        except Exception as e:
            logger.exception(f"Error posting resolution reply for comment {comment_id}: {e}")
            return {
                "type": "resolve_comment",
                "comment_id": comment_id,
                "success": False,
                "error": str(e)
            }
