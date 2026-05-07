"""
Slack Web API client.

Uses the existing requests-based HTTP client for outbound calls.
Implements HMAC-SHA256 signature verification for inbound Slack requests.
No external Slack SDK — only stdlib + requests (already in requirements.txt).
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any, Dict, List, Optional

import requests as _requests

from src.providers.http.client import http_request
from src.providers.logger import Logger
from .exceptions import SlackAPIError, SlackAuthError

logger = Logger("SlackClient")

_SLACK_API_BASE = "https://slack.com/api"


class SlackClient:
    """Thin wrapper around the Slack Web API."""

    def __init__(self, bot_token: str, signing_secret: str) -> None:
        if not bot_token:
            raise SlackAuthError("Slack bot_token is required")
        if not signing_secret:
            raise SlackAuthError("Slack signing_secret is required")
        self._bot_token = bot_token
        self._signing_secret = signing_secret

    def _auth_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._bot_token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    def send_message(
        self,
        channel: str,
        text: str,
        *,
        blocks: Optional[List[Dict[str, Any]]] = None,
        thread_ts: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Post a message to a Slack channel.

        Args:
            channel: Channel ID or name (e.g. "#swe-agent-notifications").
            text: Plain-text fallback (required by Slack even when using blocks).
            blocks: Optional Block Kit block dicts.
            thread_ts: If set, posts as a threaded reply.

        Returns:
            Slack API response dict.

        Raises:
            SlackAPIError: If Slack returns ok=false.
        """
        payload: Dict[str, Any] = {"channel": channel, "text": text}
        if blocks:
            payload["blocks"] = blocks
        if thread_ts:
            payload["thread_ts"] = thread_ts

        resp = http_request(
            service="slack",
            operation="send-message",
            endpoint_template="/chat.postMessage",
            method="POST",
            url=f"{_SLACK_API_BASE}/chat.postMessage",
            headers=self._auth_headers(),
            json=payload,
            timeout=10.0,
        )
        data = resp.json()
        if not data.get("ok"):
            raise SlackAPIError(
                f"Slack API error: {data.get('error', 'unknown')}",
                status_code=resp.status_code,
                response=data,
            )

        logger.info("Slack message sent", extra={"channel": channel, "ts": data.get("ts")})
        return data

    def post_to_response_url(
        self,
        response_url: str,
        text: str,
        *,
        blocks: Optional[List[Dict[str, Any]]] = None,
        response_type: str = "in_channel",
    ) -> None:
        """
        Post an async reply to a Slack slash-command response_url.

        No auth header needed — response_url webhooks are self-contained.
        Supports up to 5 replies and expire after 30 minutes.
        """
        payload: Dict[str, Any] = {"text": text, "response_type": response_type}
        if blocks:
            payload["blocks"] = blocks

        try:
            _requests.post(response_url, json=payload, timeout=10.0)
            logger.info("Posted to Slack response_url")
        except Exception as exc:
            logger.warning(f"Failed to post to Slack response_url: {exc}")

    def verify_signature(
        self,
        body: str,
        timestamp: str,
        signature: str,
        *,
        max_age_seconds: int = 300,
    ) -> bool:
        """
        Verify that an inbound request genuinely came from Slack (HMAC-SHA256).

        See: https://api.slack.com/authentication/verifying-requests-from-slack

        Args:
            body: Raw request body as UTF-8 string.
            timestamp: X-Slack-Request-Timestamp header value.
            signature: X-Slack-Signature header value (format: "v0=<hex>").
            max_age_seconds: Reject requests older than this (replay attack prevention).

        Returns:
            True if valid and fresh.
        """
        try:
            request_age = abs(time.time() - float(timestamp))
        except (ValueError, TypeError):
            logger.warning("Invalid X-Slack-Request-Timestamp header")
            return False

        if request_age > max_age_seconds:
            logger.warning(f"Slack request too old: {request_age:.0f}s")
            return False

        base_string = f"v0:{timestamp}:{body}"
        expected = "v0=" + hmac.new(
            self._signing_secret.encode("utf-8"),
            base_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)
