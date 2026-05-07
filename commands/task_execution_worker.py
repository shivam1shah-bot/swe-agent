#!/usr/bin/env python3
"""
Worker Command - Initialize and start the SQS worker.
"""

import logging
import sys
from src.worker.worker import SWEAgentWorker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for the worker."""
    try:
        worker = SWEAgentWorker()
        # Accepted task types now loaded from config automatically
        # via worker.profiles.task_execution.accepted_task_types
        worker.start()
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    except Exception as e:
        logger.error(f"Worker failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 