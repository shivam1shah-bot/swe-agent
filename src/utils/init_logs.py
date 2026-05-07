"""
Utility module for initializing log directories.
"""

import os
import logging

# Configure logging
logger = logging.getLogger(__name__)

def init_log_dirs():
    """Create the structured log directory hierarchy."""
    # Define the base directories
    tmp_dir = "tmp"
    logs_dir = os.path.join(tmp_dir, "logs")
    
    # Define subdirectories for different types of logs
    log_subdirs = [
        os.path.join(logs_dir, "agent-logs"),
        os.path.join(logs_dir, "system"),
        os.path.join(logs_dir, "workflow-logs")
    ]
    
    # Create base tmp directory
    os.makedirs(tmp_dir, exist_ok=True)
    logger.debug(f"Created or verified base tmp directory: {tmp_dir}")
    
    # Create logs directory
    os.makedirs(logs_dir, exist_ok=True)
    logger.debug(f"Created or verified logs directory: {logs_dir}")
    
    # Create each log subdirectory
    for subdir in log_subdirs:
        os.makedirs(subdir, exist_ok=True)
        logger.debug(f"Created or verified log subdirectory: {subdir}")
    
    # Create a .gitignore in tmp if it doesn't exist yet
    gitignore_path = os.path.join(tmp_dir, ".gitignore")
    if not os.path.exists(gitignore_path):
        with open(gitignore_path, "w") as f:
            f.write("# Ignore all files in this directory except .gitignore\n")
            f.write("*\n")
            f.write("!.gitignore\n")
        logger.debug(f"Created .gitignore in {tmp_dir} to prevent logs from being committed")

    logger.info("Log directory structure initialization complete") 