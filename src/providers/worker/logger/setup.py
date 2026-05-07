"""
Logging setup for SWE-Agent Worker System
"""
import logging
import sys
from typing import Optional

from ..config.settings import WorkerConfig


def setup_logger(config: Optional[WorkerConfig] = None) -> logging.Logger:
    """Setup and configure logger for the worker system."""
    if config is None:
        from ..config.settings import get_config
        config = get_config()
    
    # Create logger
    logger = logging.getLogger('swe-agent-task-execution-worker')
    logger.setLevel(getattr(logging, config.log_level.upper()))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, config.log_level.upper()))
    
    # Create formatter
    formatter = logging.Formatter(config.log_format)
    console_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(console_handler)
    
    # Prevent duplicate logs
    logger.propagate = False
    
    return logger


def get_logger(name: str = 'swe-agent-task-execution-worker') -> logging.Logger:
    """Get logger instance."""
    return logging.getLogger(name) 