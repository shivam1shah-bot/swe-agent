#!/usr/bin/env python3
"""
Comment Analyzer Worker Entry Point

This script starts the comment analyzer worker that processes comment analysis tasks
from the comment_analysis queue.
"""

import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.worker.comment_analyzer_worker import CommentAnalyzerWorker

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Start the comment analyzer worker."""
    try:
        logger.info("=" * 80)
        logger.info("Starting Comment Analyzer Worker...")
        logger.info("=" * 80)

        worker = CommentAnalyzerWorker()
        # Accepted task types loaded from config automatically
        # via worker.profiles.comment_analyzer.accepted_task_types
        worker.start()

    except KeyboardInterrupt:
        logger.info("Comment analyzer worker interrupted by user")
    except Exception as e:
        logger.error(f"Comment analyzer worker failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
