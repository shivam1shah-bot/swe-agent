#!/usr/bin/env python3
"""
Code Review Worker Entry Point

This script starts the code review worker that processes code review tasks
from the code_review_execution queue using the rzp_code_review GitHub bot.
"""

import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.worker.review_worker import CodeReviewWorker

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Start the code review worker."""
    try:
        logger.info("=" * 80)
        logger.info("Starting Code Review Worker...")
        logger.info("=" * 80)

        worker = CodeReviewWorker()
        # Accepted task types now loaded from config automatically
        # via worker.profiles.code_review.accepted_task_types
        worker.start()

    except KeyboardInterrupt:
        logger.info("Code review worker interrupted by user")
    except Exception as e:
        logger.error(f"Code review worker failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
