"""
Webhook receiver FastAPI application.

Lightweight standalone app that receives webhooks from external sources.
Runs as its own container, separate from the main API.
"""

import logging

from fastapi import FastAPI

from src.webhooks.router import router as webhooks_router

logger = logging.getLogger(__name__)

app = FastAPI(
    title="SWE Agent Webhook Receiver",
    description="Receives and processes webhook events from external sources (DevRev, GitHub, etc.)",
    version="1.0.0",
)

app.include_router(webhooks_router)


@app.get("/health")
async def root_health():
    """Root health check."""
    return {"status": "ok", "service": "webhook-receiver"}
