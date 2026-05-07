"""
Webhook receiver router - re-exported from src.webhooks.router.

The router lives in src/webhooks/router.py so the standalone webhook receiver
container can import it without pulling in the full API router package
(which triggers heavy dependencies like prometheus_client via plugin_metrics).
"""

from src.webhooks.router import router

__all__ = ["router"]
