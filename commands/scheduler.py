#!/usr/bin/env python3
"""
Scheduler process — runs APScheduler for cron-based skill execution.

This is the entry point for the dedicated swe-agent-scheduler pod.
It does NOT run inside the API pods — only one scheduler process exists at a time.
"""

import asyncio
import logging
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class _HealthHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler for Kubernetes liveness/readiness probes."""

    def do_GET(self) -> None:
        if self.path in ("/health", "/ready"):
            body = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args) -> None:  # suppress access logs
        pass


def _start_health_server(port: int = 8080) -> None:
    """Start a background HTTP server for health probes on the given port."""
    server = HTTPServer(("", port), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Health probe server listening on :{port}")


async def main():
    """Main entry point for the scheduler pod."""
    from src.providers.config_loader import get_config
    from src.providers.database.provider import DatabaseProvider
    from src.services.scheduler_service import SchedulerService

    config = get_config()

    db = DatabaseProvider()
    db.initialize(config)

    # Run migrations so the schedules table is guaranteed to exist
    try:
        from src.migrations.manager import MigrationManager
        from src.providers.database.connection import get_engine
        engine = get_engine()
        migration_manager = MigrationManager(engine)
        migration_manager.run_migrations()
        logger.info("Migrations completed")
    except Exception as e:
        logger.warning(f"Migration step failed (continuing): {e}")

    # Initialize cache (Redis) so the reload listener can subscribe
    try:
        from src.providers.cache import cache_provider
        cache_provider.initialize(config)
        logger.info("Cache provider initialized")
    except Exception as e:
        logger.warning(f"Cache provider initialization failed (reload signals unavailable): {e}")

    scheduler_svc = SchedulerService(config, db)

    # Start health probe server so Kubernetes can detect liveness/readiness
    _start_health_server(port=8080)

    try:
        await scheduler_svc.start()

        # Subscribe to Redis reload signals in background.
        # Add a done callback to log if the task dies unexpectedly.
        _listener_task = asyncio.create_task(_redis_reload_listener(scheduler_svc))

        def _on_listener_done(t: asyncio.Task) -> None:
            if t.cancelled():
                logger.warning("Redis reload listener was cancelled")
            elif t.exception():
                logger.error(f"Redis reload listener died: {t.exception()}")

        _listener_task.add_done_callback(_on_listener_done)

        logger.info("Scheduler is running. Press Ctrl+C to stop.")
        while True:
            await asyncio.sleep(3600)

    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler interrupted — shutting down...")
        await scheduler_svc.shutdown()
    except Exception as e:
        logger.error(f"Scheduler failed: {e}")
        await scheduler_svc.shutdown()
        sys.exit(1)


async def _redis_reload_listener(scheduler_svc):
    """
    Subscribe to the 'scheduler:reload' Redis channel.

    When the API pod creates/updates/deletes a schedule, it publishes a message
    here so the scheduler pod can react immediately without restarting.
    Reconnects automatically on transient failures so live-reload never silently dies.
    """
    import json

    while True:
        try:
            from src.providers.cache import cache_provider
            redis_client = getattr(getattr(cache_provider, "_client", None), "client", None)
            if not redis_client:
                logger.warning("Redis client unavailable — retrying in 30s")
                await asyncio.sleep(30)
                continue

            pubsub = redis_client.pubsub()
            pubsub.subscribe("scheduler:reload")
            logger.info("Subscribed to 'scheduler:reload' Redis channel")

            loop = asyncio.get_event_loop()
            while True:
                # get_message is non-blocking; run it in executor to avoid blocking the loop
                message = await loop.run_in_executor(None, lambda: pubsub.get_message(timeout=1))
                if message and message.get("type") == "message":
                    try:
                        payload = json.loads(message["data"])
                        action = payload.get("action", "upsert")
                        schedule_id = payload.get("schedule_id")
                        if not schedule_id:
                            continue

                        logger.info(f"Received reload signal: action={action} schedule_id={schedule_id}")

                        if action in ("upsert",):
                            await loop.run_in_executor(None, scheduler_svc.upsert_schedule, schedule_id)
                        elif action == "remove":
                            await loop.run_in_executor(None, scheduler_svc.remove_schedule, schedule_id)
                    except Exception as e:
                        logger.error(f"Error processing reload message: {e}")

                await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Redis reload listener failed — reconnecting in 30s: {e}")
            await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(main())
