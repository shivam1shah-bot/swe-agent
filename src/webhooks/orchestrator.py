"""
Event orchestrator - routes webhook events to registered handlers.
"""

import asyncio
import logging
from typing import List

from .handlers import AgenticSDLCHandler, BaseEventHandler, LoggingHandler
from .models import HandlerResult, WebhookEvent

logger = logging.getLogger(__name__)


class EventOrchestrator:
    """Routes events to registered handlers."""

    def __init__(self):
        self._handlers: List[BaseEventHandler] = []
        self._register_defaults()

    def _register_defaults(self):
        self._handlers.append(AgenticSDLCHandler())
        self._handlers.append(LoggingHandler())

    def register(self, handler: BaseEventHandler):
        """Add an event handler to the dispatch chain."""
        self._handlers.append(handler)

    async def dispatch(self, event: WebhookEvent) -> List[HandlerResult]:
        """Dispatch an event to all accepting handlers concurrently."""
        active = [h for h in self._handlers if h.accepts(event)]
        if not active:
            return []

        async def _run(handler: BaseEventHandler) -> HandlerResult:
            try:
                return await handler.handle(event)
            except Exception as e:
                logger.error(
                    f"Handler {handler.name} failed for "
                    f"{event.source}/{event.event_type}: {e}"
                )
                return HandlerResult(
                    handler_name=handler.name,
                    success=False,
                    message=str(e),
                )

        return list(await asyncio.gather(*(_run(h) for h in active)))
