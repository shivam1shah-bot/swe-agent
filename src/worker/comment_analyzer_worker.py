"""
Comment Analyzer Worker - Dedicated worker for processing comment analysis tasks.
Inherits from SWEAgentWorker with comment analyzer-specific configuration.
"""

import logging
import time
from typing import Optional
from .worker import SWEAgentWorker
from .tasks import TaskProcessor
from src.constants.github_bots import GitHubBot, DEFAULT_BOT
from src.providers.config_loader import get_config

logger = logging.getLogger(__name__)


class CommentAnalyzerWorker(SWEAgentWorker):
    """
    Worker for processing comment analysis tasks from dedicated queue.

    This worker:
    - Polls from comment_analysis queue (or default_task_execution)
    - Uses DEFAULT_BOT for authentication
    - Processes comment_analysis tasks with TaskProcessor
    - Scales independently from other workers
    """

    def __init__(self, worker_id: Optional[str] = None, max_tasks_per_run: int = 1):
        """
        Initialize the Comment Analyzer Worker.

        Args:
            worker_id: Unique identifier for this worker instance
            max_tasks_per_run: Maximum number of tasks to process per polling cycle
        """
        # Set worker ID with comment analyzer prefix
        if worker_id is None:
            worker_id = f"comment-analyzer-worker-{int(time.time())}"

        # Set comment analyzer-specific configuration BEFORE calling super().__init__
        # Queue alias is config-driven - reads from queue.task_routing.comment_analysis
        config = get_config()
        task_routing = config.get('queue', {}).get('task_routing', {})
        self.queue_alias = task_routing.get('comment_analysis', 'default_task_execution')
        self.github_bot = DEFAULT_BOT  # Use default bot for comment analysis

        # Initialize base worker
        super().__init__(worker_id=worker_id, max_tasks_per_run=max_tasks_per_run)

        # Use standard TaskProcessor (comment_analysis handler already registered)
        self.task_processor = TaskProcessor()
        self.task_processor.set_worker_instance(self)

        logger.info(f"CommentAnalyzerWorker {self.worker_id} initialized for queue: {self.queue_alias}")
        logger.info(f"Using GitHub bot: {self.github_bot.value}")

    def _get_worker_profile_name(self) -> str:
        """Return comment_analyzer profile for this worker."""
        return "comment_analyzer"

    def _setup_github_auth(self):
        """Setup GitHub authentication for default bot."""
        try:
            logger.info(f"Initializing GitHub authentication for {self.github_bot.value}")

            from src.providers.github.auth_service import GitHubAuthService
            import asyncio

            auth_service = GitHubAuthService()

            # Try to setup CLI with default bot token
            try:
                token_info = asyncio.run(auth_service.get_token_info(bot_name=self.github_bot))
                if token_info.get("authenticated", False):
                    asyncio.run(auth_service.ensure_gh_auth(bot_name=self.github_bot))
                    logger.info(f"GitHub CLI setup completed for {self.github_bot.value}")
                else:
                    logger.info(f"No token for {self.github_bot.value} yet - worker ready for tasks")
            except Exception as e:
                logger.warning(f"Failed to setup GitHub CLI: {e}")

        except Exception as e:
            logger.warning(f"GitHub authentication setup failed: {e}")
            logger.info("Worker will attempt to use environment token when processing tasks")


if __name__ == "__main__":
    """Allow running worker directly for testing."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        worker = CommentAnalyzerWorker()
        worker.start()
    except KeyboardInterrupt:
        logger.info("Comment analyzer worker interrupted by user")
    except Exception as e:
        logger.error(f"Comment analyzer worker failed: {e}", exc_info=True)
