"""
Webhook receiver router - generic endpoint that routes to pluggable webhook sources.
"""

import json
import logging

from fastapi import APIRouter, HTTPException, Request, Response

from src.webhooks.orchestrator import EventOrchestrator
from src.webhooks.registry import WebhookSourceRegistry

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Singletons initialized on first request
_registry: WebhookSourceRegistry | None = None
_orchestrator: EventOrchestrator | None = None


def _get_registry() -> WebhookSourceRegistry:
    global _registry
    if _registry is None:
        _registry = WebhookSourceRegistry()
    return _registry


def _get_orchestrator() -> EventOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = EventOrchestrator()
    return _orchestrator


@router.get("/health")
async def webhook_health():
    """Health check for the webhook receiver service."""
    registry = _get_registry()
    return {
        "status": "ok",
        "sources": registry.list_sources(),
    }


@router.post("/{source}")
async def receive_webhook(source: str, request: Request):
    """
    Receive a webhook event from any registered source.

    DevRev requirement: must respond within 3 seconds.
    """
    registry = _get_registry()
    webhook_source = registry.get(source)

    if not webhook_source:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown webhook source: {source}. Available: {registry.list_sources()}",
        )

    # Read raw body for signature verification
    raw_body = await request.body()

    # 1. Verify signature (on ALL requests, including challenge handshakes)
    headers = dict(request.headers)
    if not webhook_source.verify_signature(raw_body, headers):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # 2. Parse payload
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # 3. Handle verification/challenge handshake
    verification = webhook_source.handle_verification(payload)
    if verification is not None:
        return verification.model_dump(exclude_none=True)

    # 4. Validate timestamp (replay protection)
    if not webhook_source.validate_timestamp(payload):
        raise HTTPException(status_code=401, detail="Stale event")

    # 5. Parse and dispatch event
    event = webhook_source.parse_event(payload)

    orchestrator = _get_orchestrator()
    results = await orchestrator.dispatch(event)

    failed = [r for r in results if not r.success]
    if failed:
        logger.warning(
            f"Event {event.event_id}: {len(failed)}/{len(results)} handlers failed"
        )

    return Response(status_code=200)
