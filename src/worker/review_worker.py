"""
Code Review Worker - Dedicated worker for processing PR code review tasks.
Inherits from SWEAgentWorker with review-specific configuration.
"""

import logging
import time
from typing import Optional
from .worker import SWEAgentWorker
from .review_tasks import ReviewTaskProcessor
from src.constants.github_bots import GitHubBot
from src.providers.config_loader import get_config

logger = logging.getLogger(__name__)


class CodeReviewWorker(SWEAgentWorker):
    """
    Worker for processing code review tasks from dedicated review queue.

    This worker:
    - Polls from code_review_execution queue
    - Uses GitHubBot.CODE_REVIEW for authentication
    - Processes code review tasks with ReviewTaskProcessor
    - Scales independently from task execution workers
    """

    def __init__(self, worker_id: Optional[str] = None, max_tasks_per_run: int = 1):
        """
        Initialize the Code Review Worker.

        Args:
            worker_id: Unique identifier for this worker instance
            max_tasks_per_run: Maximum number of tasks to process per polling cycle
        """
        # Set worker ID with review prefix
        if worker_id is None:
            worker_id = f"review-worker-{int(time.time())}"

        # Set review-specific configuration BEFORE calling super().__init__
        # (parent's __init__ calls _setup_github_auth which needs self.github_bot)
        # Queue alias is now config-driven - reads from queue.task_routing.code_review
        config = get_config()
        task_routing = config.get('queue', {}).get('task_routing', {})
        self.queue_alias = task_routing.get('code_review', 'code_review_execution')
        self.github_bot = GitHubBot.CODE_REVIEW

        # Initialize base worker
        super().__init__(worker_id=worker_id, max_tasks_per_run=max_tasks_per_run)

        # Override task processor with review-specific processor
        self.task_processor = ReviewTaskProcessor()
        self.task_processor.set_worker_instance(self)

        logger.info(f"CodeReviewWorker {self.worker_id} initialized for queue: {self.queue_alias}")
        logger.info(f"Using GitHub bot: {self.github_bot.value}")

    def _get_worker_profile_name(self) -> str:
        """Return code_review profile for this worker."""
        return "code_review"

    def _setup_github_auth(self):
        """Setup GitHub authentication for CODE_REVIEW bot."""
        try:
            logger.info(f"Initializing GitHub authentication for {self.github_bot.value}")

            from src.providers.github.auth_service import GitHubAuthService
            import asyncio

            auth_service = GitHubAuthService()

            # Try to setup CLI with CODE_REVIEW bot token
            try:
                token_info = asyncio.run(auth_service.get_token_info(bot_name=self.github_bot))
                if token_info.get("authenticated", False):
                    asyncio.run(auth_service.ensure_gh_auth(bot_name=self.github_bot))
                    logger.info(f"GitHub CLI setup completed for {self.github_bot.value}")
                else:
                    logger.info(f"No token for {self.github_bot.value} yet - worker ready for refresh tasks")
            except Exception as e:
                logger.warning(f"GitHub auth setup: {e}")

        except Exception as e:
            logger.error(f"Failed to setup GitHub auth: {e}")

    def _main_loop(self):
        """
        Main polling loop - polls from code_review_execution queue.

        This overrides the base worker's main loop to:
        - Poll from the code_review_execution queue
        - Use review-specific queue configuration
        - Maintain independent worker lifecycle
        """
        logger.info(f"Starting main loop for {self.queue_alias} queue")
        logger.info(f"Polling with max_tasks_per_run={self.max_tasks_per_run}, wait_time=20s")

        while not self.should_stop.is_set():
            try:
                # Poll from review queue
                tasks = self.queue_manager.receive_tasks(
                    queue_alias=self.queue_alias,
                    max_messages=self.max_tasks_per_run,
                    wait_time=20
                )

                if tasks:
                    logger.info(f"Received {len(tasks)} review task(s) from {self.queue_alias}")
                    for task_data in tasks:
                        if self.should_stop.is_set():
                            logger.info("Stop signal received, breaking task processing loop")
                            break
                        self._process_single_task(task_data)
                else:
                    logger.debug(f"No tasks received from {self.queue_alias}")

            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received in main loop")
                self.should_stop.set()
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(5)  # Brief pause before retrying

        logger.info("Main loop exited")
