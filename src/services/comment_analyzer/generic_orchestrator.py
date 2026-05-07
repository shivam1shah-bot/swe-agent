#!/usr/bin/env python3
"""
Generic Comment Analyzer Framework

Configuration-driven framework that orchestrates comment analysis
using registered sub-agents.
"""

import os
import sys
import json
import logging
import requests
from typing import List, Dict, Any, Optional

# Import sub-agent infrastructure
from src.services.comment_analyzer.sub_agent_registry import SubAgentRegistry
from src.services.comment_analyzer.sub_agent_base import SubAgentResult, Comment

# Import and register all sub-agents
import src.services.comment_analyzer.agents  # Triggers registration

# Import action executor
from src.services.comment_analyzer.action_executor import ActionExecutor

logger = logging.getLogger(__name__)


class GenericOrchestrator:
    """
    Generic framework orchestrator.

    Configuration-driven - delegates all sub-agent specific logic
    to registered sub-agent implementations.
    """

    def __init__(self):
        # Load and validate required environment variables
        self.github_token = os.environ.get("GITHUB_TOKEN")
        if not self.github_token:
            raise ValueError("Required environment variable GITHUB_TOKEN is not set")

        pr_number_str = os.environ.get("PR_NUMBER")
        if not pr_number_str:
            raise ValueError("Required environment variable PR_NUMBER is not set")
        try:
            self.pr_number = int(pr_number_str)
        except ValueError as e:
            raise ValueError(f"PR_NUMBER must be a valid integer, got: {pr_number_str}") from e

        self.repository = os.environ.get("REPOSITORY")
        if not self.repository:
            raise ValueError("Required environment variable REPOSITORY is not set")

        # Optional environment variables with defaults
        self.commit_sha = os.environ.get("GITHUB_SHA", "HEAD")
        self.run_url = os.environ.get("RUN_URL", "")

        # Sub-agent configuration
        self.sub_agent_type = os.environ.get("SUB_AGENT_TYPE", "i18n")  # Which sub-agent to use
        self.sub_agent_identifier = os.environ.get("SUB_AGENT_IDENTIFIER", "rcore-v2")

        # Parse integer configuration with validation
        try:
            self.severity_threshold = int(os.environ.get("SEVERITY_THRESHOLD", "9"))
        except ValueError as e:
            raise ValueError(f"SEVERITY_THRESHOLD must be a valid integer, got: {os.environ.get('SEVERITY_THRESHOLD')}") from e

        try:
            self.fail_on_critical_count = int(os.environ.get("FAIL_ON_CRITICAL_COUNT", "1"))
        except ValueError as e:
            raise ValueError(f"FAIL_ON_CRITICAL_COUNT must be a valid integer, got: {os.environ.get('FAIL_ON_CRITICAL_COUNT')}") from e

        self.blocking_enabled = os.environ.get("BLOCKING_ENABLED", "false").lower() == "true"

        # GitHub API setup
        self.headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
        }
        self.base_url = f"https://api.github.com/repos/{self.repository}"

        # Action executor
        self.action_executor = ActionExecutor(self.github_token, self.repository, self.commit_sha)

    def fetch_all_reviews(self) -> List[Dict[str, Any]]:
        """Fetch all reviews from the PR"""
        logger.info(f"\n[Framework] Fetching all reviews for PR #{self.pr_number}...")

        url = f"{self.base_url}/pulls/{self.pr_number}/reviews"
        all_reviews = []
        page = 1

        while True:
            response = requests.get(
                url,
                headers=self.headers,
                params={"page": page, "per_page": 100}
            )

            if response.status_code != 200:
                logger.error(f"[Framework] Error fetching reviews: {response.status_code}")
                return all_reviews

            reviews = response.json()
            if not reviews:
                break

            all_reviews.extend(reviews)
            page += 1

        logger.info(f"[Framework] Fetched {len(all_reviews)} total reviews")
        return all_reviews

    def create_sub_agent_config(self) -> Dict[str, Any]:
        """
        Create sub-agent configuration from environment variables.

        Each sub-agent can have its own specific configuration.
        """
        # Get file filtering configuration from environment
        include_ext_str = os.environ.get("INCLUDE_FILE_EXTENSIONS", "")
        exclude_ext_str = os.environ.get("EXCLUDE_FILE_EXTENSIONS", "")
        exclude_patterns_str = os.environ.get("EXCLUDE_FILE_PATTERNS", "")

        # Parse extensions and patterns
        include_extensions = [ext.strip() for ext in include_ext_str.split(",") if ext.strip()] if include_ext_str else []
        exclude_extensions = [ext.strip() for ext in exclude_ext_str.split(",") if ext.strip()] if exclude_ext_str else self._get_default_exclude_extensions()
        exclude_patterns = [p.strip() for p in exclude_patterns_str.split(",") if p.strip()] if exclude_patterns_str else self._get_default_exclude_patterns()

        # Get authorized team for TP/FP feedback (per sub-agent) - OPTIONAL
        # Environment variable format: {SUB_AGENT_TYPE}_AUTHORIZED_TEAM
        # Example: I18N_AUTHORIZED_TEAM=razorpay/atlas-admins
        # NOTE: Sub-agents have their own default config. This is only for runtime overrides.
        env_var_name = f"{self.sub_agent_type.upper()}_AUTHORIZED_TEAM"
        authorized_team = os.environ.get(env_var_name)

        # Build config dict - only include authorized_team if explicitly set
        config = {
            "name": self.sub_agent_type,
            "identifier": self.sub_agent_identifier,
            "severity_threshold": self.severity_threshold,
            "thresholds": {
                "fail_on_critical_count": self.fail_on_critical_count
            },
            "filter": {
                "include_extensions": include_extensions,
                "exclude_extensions": exclude_extensions,
                "exclude_patterns": exclude_patterns
            }
        }

        # Only add authorized_team if provided via environment (for override)
        if authorized_team:
            config["authorized_team"] = authorized_team

        return config

    def _get_default_exclude_extensions(self) -> List[str]:
        """Get default file extensions to exclude"""
        return [
            ".md", ".txt", ".json", ".yml", ".yaml", ".xml",
            ".svg", ".png", ".jpg", ".jpeg", ".gif", ".ico",
            ".woff", ".woff2", ".ttf", ".eot"
        ]

    def _get_default_exclude_patterns(self) -> List[str]:
        """Get default file patterns to exclude"""
        return [
            "**/test/**", "**/tests/**", "**/__tests__/**",
            "**/vendor/**", "**/node_modules/**",
            "**/dist/**", "**/build/**"
        ]

    def run(self) -> int:
        """
        Execute the generic framework workflow.

        Returns:
            int: Exit code (0 for success, 1 for failure)
        """
        logger.info("Generic Comment Analyzer Framework")
        logger.info(f"Repository: {self.repository}")
        logger.info(f"PR Number: {self.pr_number}")
        logger.info(f"Commit SHA: {self.commit_sha}")
        logger.info(f"Sub-Agent Type: {self.sub_agent_type}")
        logger.info(f"Severity Threshold: {self.severity_threshold}")
        logger.info(f"Blocking Enabled: {self.blocking_enabled}")

        # Fetch all reviews from GitHub
        all_reviews = self.fetch_all_reviews()

        if not all_reviews:
            logger.info("\n[Framework] No reviews found on PR")
            self._handle_no_reviews()
            return 0

        # Create sub-agent configuration
        sub_agent_config = self.create_sub_agent_config()

        # Create sub-agent instance from registry
        logger.info(f"\n[Framework] Creating sub-agent: {self.sub_agent_type}")
        sub_agent = SubAgentRegistry.create(
            name=self.sub_agent_type,
            config=sub_agent_config,
            github_token=self.github_token,
            repository=self.repository,
            pr_number=self.pr_number
        )

        if not sub_agent:
            logger.error(f"[Framework] Failed to create sub-agent: {self.sub_agent_type}")
            logger.error(f"[Framework] Available sub-agents: {SubAgentRegistry.list_available()}")
            return 1

        # Execute sub-agent workflow
        logger.info(f"\n[Framework] Executing {self.sub_agent_type} workflow")
        result = sub_agent.execute(all_reviews)

        # Execute framework-level actions (may raise RuntimeError in critical failure cases)
        try:
            self._execute_actions(result)
        except RuntimeError as e:
            # Critical failure (e.g., commit status creation failed in blocking mode)
            logger.error(f"[Framework] Critical error during action execution: {e}")
            return 1

        # Output results
        self._output_results(result)

        # Return appropriate exit code
        if result.status == "FAIL" and self.blocking_enabled:
            logger.info("\n❌ PR BLOCKED: Critical issues found")
            return 1
        else:
            logger.info("\n✅ Analysis complete")
            return 0

    def _execute_actions(self, result: SubAgentResult):
        """Execute framework-level actions (commit status, summary, resolution)"""
        logger.info(f"\n[Framework] Executing actions for {result.sub_agent_name}")

        # Action 1: Commit status (CRITICAL - must succeed)
        status_action = self.action_executor.execute_commit_status(
            result=result,
            status_name=f"rcore-v2/comments/{result.sub_agent_name}",
            blocking_enabled=self.blocking_enabled,
            run_url=self.run_url
        )
        result.actions_executed.append(status_action)

        # Check if commit status succeeded - this is critical
        if not status_action.get("success"):
            logger.error(f"\n[Framework] ❌ CRITICAL: Failed to create commit status")
            logger.error(f"[Framework] Error: {status_action.get('error')}")
            logger.error(f"[Framework] This could allow PRs to be merged when they should be blocked!")
            # Raise exception if commit status fails in blocking mode (caller will convert to exit code)
            if self.blocking_enabled and result.status == "FAIL":
                logger.error(f"[Framework] Critical commit status failure in blocking mode")
                raise RuntimeError(f"Failed to create commit status: {status_action.get('error')}")
            else:
                logger.warning(f"[Framework] Continuing despite commit status failure (non-blocking mode)")

        # Action 2: Analysis summary
        summary_action = self.action_executor.post_analysis_summary(
            result=result,
            pr_number=self.pr_number,
            blocking_enabled=self.blocking_enabled
        )
        result.actions_executed.append(summary_action)

        # Check if summary succeeded (non-critical, just warn)
        if not summary_action.get("success"):
            logger.warning(f"[Framework] ⚠️ Failed to post analysis summary: {summary_action.get('error')}")

        # Action 3: Resolve addressed comments
        if result.addressed_comments:
            logger.info(f"\n[Framework] Marking {len(result.addressed_comments)} comments as resolved")
            resolve_actions = self.action_executor.resolve_addressed_comments(
                addressed_comments=result.addressed_comments,
                pr_number=self.pr_number
            )
            result.actions_executed.extend(resolve_actions)

            # Check resolution success rate (non-critical, just warn)
            failed_resolutions = sum(1 for a in resolve_actions if not a.get("success"))
            if failed_resolutions > 0:
                logger.warning(f"[Framework] ⚠️ Failed to resolve {failed_resolutions}/{len(resolve_actions)} comments")
        else:
            logger.info(f"\n[Framework] No addressed comments to mark as resolved")

    def _handle_no_reviews(self):
        """Handle case when no reviews are found"""
        result = SubAgentResult(
            sub_agent_name=self.sub_agent_type,
            status="PASS",
            total_comments=0,
            addressed=0,
            not_addressed=0,
            unaddressed_by_severity={"critical": 0, "high": 0, "medium": 0, "low": 0},
            critical_issues=[],
            addressed_comments=[],
            actions_executed=[]
        )

        status_action = self.action_executor.execute_commit_status(
            result=result,
            status_name=f"rcore-v2/comments/{self.sub_agent_type}",
            blocking_enabled=False,
            run_url=self.run_url
        )
        result.actions_executed.append(status_action)

        # Check if commit status succeeded
        if not status_action.get("success"):
            logger.error(f"[Framework] ❌ Failed to create commit status: {status_action.get('error')}")
            logger.warning(f"[Framework] Continuing despite commit status failure (no reviews found)")

        self._output_results(result)

    def _output_results(self, result: SubAgentResult):
        """Output results for GitHub Actions"""
        logger.info("FINAL RESULTS")
        logger.info(f"Sub-Agent: {result.sub_agent_name}")
        logger.info(f"Status: {result.status}")
        logger.info(f"Total Comments: {result.total_comments}")
        logger.info(f"Addressed: {result.addressed}")
        logger.info(f"Not Addressed: {result.not_addressed}")
        logger.info(f"Resolved: {len(result.addressed_comments)}")
        logger.info(f"Critical Issues: {result.unaddressed_by_severity['critical']}")
        logger.info(f"Actions Executed: {len(result.actions_executed)}")

        # Save to file
        output = {
            "sub_agent": result.sub_agent_name,
            "status": result.status,
            "total_comments": result.total_comments,
            "addressed": result.addressed,
            "not_addressed": result.not_addressed,
            "resolved_count": len(result.addressed_comments),
            "critical_count": result.unaddressed_by_severity["critical"],
            "critical_issues": [
                {
                    "id": c.id,
                    "body": c.body,
                    "severity": c.severity,
                    "category": c.category,
                    "file_path": c.file_path
                }
                for c in result.critical_issues
            ],
            "addressed_comments": [
                {
                    "id": c.id,
                    "file_path": c.file_path,
                    "line": c.line,
                    "category": c.category
                }
                for c in result.addressed_comments
            ],
            "actions_executed": result.actions_executed,
            "blocking_enabled": self.blocking_enabled
        }

        with open("/tmp/analysis_result.json", "w") as f:
            json.dump(output, f, indent=2)

        # Set GitHub Actions outputs
        if "GITHUB_OUTPUT" in os.environ:
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"status={result.status}\n")
                f.write(f"total_comments={result.total_comments}\n")
                f.write(f"addressed={result.addressed}\n")
                f.write(f"not_addressed={result.not_addressed}\n")
                f.write(f"resolved_count={len(result.addressed_comments)}\n")
                f.write(f"critical_count={result.unaddressed_by_severity['critical']}\n")


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    orchestrator = GenericOrchestrator()
    exit_code = orchestrator.run()
    sys.exit(exit_code)
