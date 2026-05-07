#!/usr/bin/env python3
"""
Seed data runner for SWE Agent.

This script runs all seed data files for local development setup.
"""

import logging
import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from src.migrations.seeds.agents_catalogue_items import seed_agents_catalogue_items
from src.providers.database.connection import initialize_engine


def run_all_seeds():
    """Run all seed data for local development."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    logger.info("Starting seed data process...")
    
    try:
        # Use proper configuration loader instead of hardcoded config
        from src.providers.config_loader import get_config
        config = get_config()
        
        # Initialize database engine
        engine = initialize_engine(config)
        
        logger.info("Running agents catalogue items seed...")
        seed_agents_catalogue_items(engine)
        
        # Add more seed functions here as needed
        # logger.info("Running user data seed...")
        # seed_users(engine)
        
        logger.info("All seed data completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Failed to run seed data: {e}")
        return False


if __name__ == "__main__":
    success = run_all_seeds()
    sys.exit(0 if success else 1) 