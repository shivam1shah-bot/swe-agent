"""
Review Task Processor for Code Review Worker.
Handles code review task processing with placeholder for future Review Main Agent.
"""

import logging
from typing import Dict, Any, Optional
from .tasks import TaskProcessor
from src.constants.github_bots import GitHubBot
from src.constants.pr_review import ReviewStatus, ErrorCode
from src.providers.context import ContextManager, WORKER_CONTEXT, TASK_ID
from src.providers.database.session import get_session
from src.repositories.pr_review_repository import SQLAlchemyPRReviewRepository
import asyncio

logger = logging.getLogger(__name__)


class ReviewTaskProcessor(TaskProcessor):
    """Processes code review tasks."""

    def __init__(self):
        super().__init__()

        # Add review-specific task handler
        self.task_handlers.update({
            "code_review": self._handle_code_review,
        })

        logger.info("ReviewTaskProcessor initialized")

    def _update_review_status(
        self,
        review_id: str,
        status: ReviewStatus,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        session=None,
    ) -> None:
        """
        Update PR review status in database.

        Args:
            review_id: Review identifier
            status: New status to set
            error_code: Error code for failed status
            error_message: Error message for failed status
            session: Optional existing database session to reuse (avoids N+1 pattern)
        """
        if not review_id:
            return

        def do_update(sess):
            repo = SQLAlchemyPRReviewRepository(sess)
            error_info = None
            if status == ReviewStatus.FAILED and error_code:
                error_info = {
                    "code": error_code,
                    "message": error_message or "Unknown error",
                }
            repo.update_status(review_id, status, error_info)
            logger.info(f"Updated review {review_id} status to {status.value}")

        try:
            if session is not None:
                # Reuse provided session (caller manages commit)
                do_update(session)
            else:
                # Create new session (backward compatible)
                with get_session() as new_session:
                    do_update(new_session)
                    # Session auto-commits via context manager
        except Exception as e:
            logger.error(f"Failed to update review {review_id} status to {status.value}: {e}")
            # Don't raise - status update failure shouldn't fail the review

    async def _handle_code_review(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle code review task.

        Processes PR review requests from PRReviewService and invokes ReviewMainAgent.

        Args:
            task_data: Task data containing pr_metadata and review_id

        Returns:
            Dict containing success status and result data
        """
        # Extract data from PRReviewService format
        review_id = task_data.get('review_id')
        pr_metadata = task_data.get('pr_metadata', {})

        logger.info(f"Processing code review task {review_id}")

        # Validate required PR metadata fields first (no DB needed)
        required_fields = ['repository', 'pr_number']
        missing = [f for f in required_fields if not pr_metadata.get(f)]
        if missing:
            logger.error(f"Missing required pr_metadata fields: {missing}")
            self._update_review_status(
                review_id,
                ReviewStatus.FAILED,
                error_code=ErrorCode.VALIDATION_ERROR.value,
                error_message=f"Missing required pr_metadata fields: {missing}",
            )
            return {
                'success': False,
                'error': f'Missing required pr_metadata fields: {missing}',
                'task_id': review_id
            }

        # ATOMIC IDEMPOTENCY CHECK: Use atomic claim to prevent TOCTOU race condition
        # This combines the check and status update into a single atomic operation
        # Only one worker can successfully claim a review, even if duplicates arrive
        if review_id:
            try:
                with get_session() as db_session:
                    repo = SQLAlchemyPRReviewRepository(db_session)

                    # Atomically claim the review for processing
                    # Allowed statuses: QUEUED (normal), ACCEPTED (webhook), FAILED (retry),
                    # RUNNING (crashed worker recovery)
                    claimed = repo.atomic_claim_for_processing(
                        review_id,
                        allowed_from_statuses=[
                            ReviewStatus.QUEUED,
                            ReviewStatus.ACCEPTED,
                            ReviewStatus.FAILED,
                            ReviewStatus.RUNNING,  # Allow recovery from crashed workers
                        ],
                    )

                    if not claimed:
                        # Review is already COMPLETED or was claimed by another worker
                        logger.info(
                            f"Review {review_id} not claimed - already completed or being processed"
                        )
                        return {
                            'success': True,  # Return success to delete SQS message
                            'result': {
                                'status': 'already_processed',
                                'skipped': True,
                                'message': 'Review was already completed or is being processed'
                            },
                            'task_id': review_id
                        }

                    logger.info(f"Successfully claimed review {review_id} for processing")

            except Exception as e:
                logger.warning(f"Failed to atomically claim review: {e}")
                # Continue processing - fail open to avoid blocking legitimate reviews
                # The review might still work if it's a transient DB error

        # Create context with CODE_REVIEW bot
        task_data_with_id = {**task_data, 'task_id': review_id}
        ctx = ContextManager.create_task_context(task_data_with_id)
        enhanced_context = ctx.get(WORKER_CONTEXT, {})
        enhanced_context.update({
            "worker_instance": self.worker_instance,
            "github_bot": GitHubBot.CODE_REVIEW.value
        })
        ctx = ctx.with_value(WORKER_CONTEXT, enhanced_context)

        # Add 1 hour timeout for code reviews
        ctx, cancel = ctx.with_timeout(3600.0).with_cancel()

        # VALIDATION: Fetch PR info using gh CLI
        try:
            pr_number = pr_metadata['pr_number']
            repo = pr_metadata['repository']

            logger.info(f"Validating PR access for {repo}#{pr_number}")

            # Ensure gh auth with CODE_REVIEW bot
            from src.providers.github.auth_service import GitHubAuthService
            auth_service = GitHubAuthService()
            await auth_service.ensure_gh_auth(bot_name=GitHubBot.CODE_REVIEW)

            logger.info(f"GitHub CLI authenticated with {GitHubBot.CODE_REVIEW.value}")

            # Fetch PR details to validate bot access
            process = await asyncio.create_subprocess_exec(
                "gh", "pr", "view", str(pr_number),
                "--repo", repo,
                "--json", "title,state,author,files",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode()
                logger.error(f"Failed to fetch PR info: {error_msg}")
                self._update_review_status(
                    review_id,
                    ReviewStatus.FAILED,
                    error_code=ErrorCode.UPSTREAM_ERROR.value,
                    error_message=f"Failed to fetch PR info: {error_msg}"
                )
                return {
                    'success': False,
                    'error': f'Failed to fetch PR info: {error_msg}',
                    'task_id': review_id
                }

            import json
            pr_info = json.loads(stdout.decode())

            logger.info(f"PR validation successful: {pr_info.get('title')}")

            # Note: Status already set to RUNNING by atomic_claim_for_processing()

            # Execute Review Main Agent
            from src.agents.review_agents.review_main_agent import ReviewMainAgent

            agent = ReviewMainAgent(
                github_bot=GitHubBot.CODE_REVIEW,
                confidence_threshold=0.6,
                filter_min_score=5,
                filter_pre_threshold=3,
            )

            review_result = await agent.execute_review(
                repository=repo,
                pr_number=pr_number,
            )

            # CRITICAL: If review was posted, we MUST return success to delete SQS message
            # This prevents duplicates even if status update or other operations fail
            if review_result.review_posted:
                # Try to update status, but don't fail if it doesn't work
                try:
                    self._update_review_status(review_id, ReviewStatus.COMPLETED)
                except Exception as status_error:
                    logger.warning(
                        f"Status update failed after review posted for {review_id}: {status_error}. "
                        "Review was posted successfully - returning success to prevent duplicate."
                    )

                # Build result response
                result = {
                    'status': 'completed',
                    'review_posted': review_result.review_posted,
                    'review_id': review_result.review_id,
                    'suggestions_count': review_result.total_suggestions,
                    'errors': review_result.errors if review_result.has_errors else None,
                }

                logger.info(
                    f"Code review task {review_id} completed: "
                    f"posted={review_result.review_posted}, "
                    f"suggestions={review_result.total_suggestions}"
                )

                # ALWAYS return success if review was posted - prevents SQS retry duplicates
                return {
                    'success': True,
                    'result': result,
                    'task_id': review_id
                }

            # If review was NOT posted, check if it was due to errors
            if review_result.has_errors:
                # Review failed due to error (e.g., DiffTooLargeError)
                error_message = "; ".join(review_result.errors)
                logger.warning(
                    f"Code review task {review_id} failed with errors: {error_message}"
                )
                self._update_review_status(
                    review_id,
                    ReviewStatus.FAILED,
                    error_code=ErrorCode.UPSTREAM_ERROR.value,
                    error_message=error_message
                )
                return {
                    'success': True,  # True = don't retry (permanent condition like large diff)
                    'result': {
                        'status': 'failed',
                        'review_posted': False,
                        'errors': review_result.errors,
                    },
                    'task_id': review_id
                }

            # Legitimate skip (PR closed, empty diff, etc.) - mark as completed
            result = {
                'status': 'completed',
                'review_posted': False,
                'review_id': review_result.review_id,
                'suggestions_count': review_result.total_suggestions,
            }

            logger.info(
                f"Code review task {review_id} completed (no review posted): "
                f"suggestions={review_result.total_suggestions}"
            )

            self._update_review_status(review_id, ReviewStatus.COMPLETED)

            return {
                'success': True,
                'result': result,
                'task_id': review_id
            }

        except Exception as e:
            logger.error(f"Code review failed: {e}", exc_info=True)
            self._update_review_status(
                review_id,
                ReviewStatus.FAILED,
                error_code=ErrorCode.UPSTREAM_ERROR.value,
                error_message=str(e)
            )
            return {
                'success': False,
                'error': str(e),
                'task_id': review_id
            }
