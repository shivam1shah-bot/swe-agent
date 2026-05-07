#!/usr/bin/env python3
"""
Start the MCP service.

This command starts the standalone MCP (Model Context Protocol) service
that provides a protocol wrapper around the SWE Agent API service.
"""

import asyncio
import uvicorn
import sys
import os
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from src.mcp_server.app import app
from src.mcp_server.config.settings import get_mcp_settings
from src.providers.logger import get_logger

# Initialize logger
logger = get_logger(__name__)

def _init_telemetry(settings) -> None:
    """Initialise telemetry before the ASGI server starts.

    Running this here (instead of inside the ASGI startup event) ensures the
    import/init cost is paid *before* ``uvicorn.run()`` binds the socket.
    Once uvicorn starts, the startup event is lightweight and port 8003 opens
    immediately — well within the K8s liveness-probe deadline.

    Errors propagate (``setup_telemetry`` raises on failure) so the process
    exits before accepting traffic if metrics infrastructure is broken.
    """
    from src.providers.telemetry import setup_telemetry

    config = settings.config
    telemetry_config = config.get("telemetry", {})
    telemetry_config["service_name"] = "swe-agent-mcp"
    labels = telemetry_config.get("labels", {})
    labels["service"] = "mcp"
    telemetry_config["labels"] = labels
    telemetry_config["enabled"] = True

    setup_telemetry(telemetry_config)
    logger.info("Telemetry initialized")


def main():
    """Main entry point for MCP service."""
    logger.info("SWE Agent MCP Server")

    # Get settings
    settings = get_mcp_settings()

    logger.info(f"Starting MCP server on {settings.host}:{settings.port}")
    logger.info(f"API service: {settings.api_base_url}")
    logger.info(f"Environment: {settings.environment_name}")
    logger.info(f"Debug mode: {settings.debug}")

    # Initialise telemetry synchronously before the ASGI server starts.
    # This keeps the startup event lightweight so port 8003 opens fast.
    _init_telemetry(settings)

    # Run the FastAPI app
    try:
        uvicorn.run(
            "src.mcp_server.app:app",
            host=settings.host,
            port=settings.port,
            reload=settings.debug,
            log_level=settings.log_level.lower(),
            access_log=True,
            reload_excludes=["*.pyc", "__pycache__", ".git", "node_modules", "venv", ".venv"]
        )
    except KeyboardInterrupt:
        logger.info("MCP Server stopped by user")
    except Exception as e:
        logger.error(f"Error starting MCP server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 