#!/usr/bin/env python3
"""
API Command - Main entry point for the SWE Agent FastAPI application.

This script starts the FastAPI server using uvicorn for production deployment.
"""

import sys
import logging
import argparse
from pathlib import Path

# Add the project root and src directory to the path so we can import our modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

def setup_logging(level: str = "INFO"):
    """Setup logging configuration."""
    # Clear any existing handlers to prevent conflicts
    # This ensures clean logging setup for the main API server
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )


def main():
    """Main entry point."""
    # Load configuration to get default port
    try:
        from src.providers.config_loader import get_config
        config = get_config()
        default_port = config.get('app', {}).get('api_port', 8002)
        default_host = config.get('app', {}).get('host', '0.0.0.0')
    except Exception:
        # Fallback to hardcoded defaults if config loading fails
        default_port = 8002
        default_host = '0.0.0.0'
    
    parser = argparse.ArgumentParser(description='SWE Agent FastAPI Server')
    parser.add_argument('--host', default=default_host, help='Host to bind to')
    parser.add_argument('--port', type=int, default=default_port, help=f'Port to bind to (default: {default_port})')
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload for development')
    parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], help='Log level')

    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)

    logger = logging.getLogger(__name__)
    
    logger.info("Starting SWE Agent FastAPI server...")
    logger.info(f"Host: {args.host}, Port: {args.port}")
    logger.info(f"Reload: {args.reload}")
    
    try:
        import uvicorn
        
        # Run the server with the correct import path
        uvicorn.run(
            "src.api.api:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level=args.log_level.lower(),
            access_log=True
        )
        
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 