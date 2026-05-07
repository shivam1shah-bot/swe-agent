#!/usr/bin/env python3
"""
Webhook Receiver Entry Point

Starts the webhook receiver FastAPI service that ingests events
from external sources (DevRev, GitHub, etc.).
"""

import sys
import logging
import argparse
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))


def setup_logging(level: str = "INFO"):
    """Setup logging configuration."""
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def main():
    """Main entry point."""
    try:
        from src.providers.config_loader import get_config

        config = get_config()
        default_port = config.get("webhooks", {}).get("port", 8004)
        default_host = config.get("app", {}).get("host", "0.0.0.0")
    except Exception:
        default_port = 8004
        default_host = "0.0.0.0"

    parser = argparse.ArgumentParser(description="SWE Agent Webhook Receiver")
    parser.add_argument("--host", default=default_host, help="Host to bind to")
    parser.add_argument(
        "--port",
        type=int,
        default=default_port,
        help=f"Port to bind to (default: {default_port})",
    )
    parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reload for development"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level",
    )

    args = parser.parse_args()

    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    logger.info("Starting Webhook Receiver...")
    logger.info(f"Host: {args.host}, Port: {args.port}")

    try:
        import uvicorn

        uvicorn.run(
            "src.webhooks.app:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level=args.log_level.lower(),
            access_log=True,
        )
    except KeyboardInterrupt:
        logger.info("Webhook receiver stopped by user")
    except Exception as e:
        logger.error(f"Failed to start webhook receiver: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
