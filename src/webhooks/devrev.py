"""
DevRev webhook source - handles DevRev webhook signature verification,
challenge handshake, and event parsing.
"""

import base64
import hashlib
import hmac
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from src.providers.config_loader import get_config

from .base import BaseWebhookSource
from .models import WebhookEvent, WebhookVerificationResponse

logger = logging.getLogger(__name__)

SIGNATURE_HEADER = "x-devrev-signature"


def _parse_iso_timestamp(ts: str) -> datetime:
    """Parse an ISO 8601 timestamp string (with optional Z suffix) to a UTC datetime."""
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


class DevRevWebhookSource(BaseWebhookSource):
    """Webhook source for DevRev platform events."""

    def __init__(self):
        config = get_config()
        devrev_config = config.get("webhooks", {}).get("devrev", {})
        self._webhook_secret: str = devrev_config.get("webhook_secret", "")
        self._max_timestamp_age: int = devrev_config.get(
            "max_timestamp_age_seconds", 300
        )

    @property
    def source_name(self) -> str:
        return "devrev"

    def verify_signature(self, raw_body: bytes, headers: Dict[str, str]) -> bool:
        """
        Verify DevRev webhook HMAC-SHA256 signature.

        Key:     base64-decoded webhook secret (raw bytes)
        Message: raw request body (bytes)
        Compare: base64-encoded HMAC-SHA256 vs X-DevRev-Signature header
        """
        if not self._webhook_secret:
            logger.warning("DevRev webhook secret not configured, skipping verification")
            return True

        # Normalize header keys to lowercase for lookup
        normalized = {k.lower(): v for k, v in headers.items()}
        signature = normalized.get(SIGNATURE_HEADER, "")

        if not signature:
            logger.warning("Missing X-DevRev-Signature header")
            return False

        # DevRev webhook secret is base64-encoded; decode to get raw key bytes
        try:
            key_bytes = base64.b64decode(self._webhook_secret)
        except Exception:
            key_bytes = self._webhook_secret.encode("utf-8")

        expected = base64.b64encode(
            hmac.new(
                key=key_bytes,
                msg=raw_body,
                digestmod=hashlib.sha256,
            ).digest()
        ).decode("utf-8")

        is_valid = hmac.compare_digest(expected, signature)
        if not is_valid:
            logger.warning("DevRev webhook signature mismatch")
        return is_valid

    def handle_verification(
        self, payload: dict
    ) -> Optional[WebhookVerificationResponse]:
        """
        Handle DevRev verification challenge.
        DevRev sends {"type": "verify", "verify": {"challenge": "..."}}
        and expects {"challenge": "..."} echoed back within 3 minutes.
        """
        if payload.get("type") != "verify":
            return None

        challenge = payload.get("verify", {}).get("challenge", "")
        if not challenge:
            logger.warning("DevRev verify event missing challenge field")
            return None

        logger.info("Responding to DevRev verification challenge")
        return WebhookVerificationResponse(challenge=challenge)

    def validate_timestamp(self, payload: dict) -> bool:
        """Reject events older than max_timestamp_age_seconds to prevent replay."""
        timestamp_str = payload.get("timestamp")
        if not timestamp_str:
            return True  # No timestamp to validate

        try:
            event_time = _parse_iso_timestamp(timestamp_str)
            age = datetime.now(timezone.utc) - event_time
            if age > timedelta(seconds=self._max_timestamp_age):
                logger.warning(
                    f"DevRev event timestamp too old: {age.total_seconds():.0f}s "
                    f"(max {self._max_timestamp_age}s)"
                )
                return False
            return True
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse DevRev event timestamp: {e}")
            return True  # Don't reject on parse failure

    def parse_event(self, payload: dict) -> WebhookEvent:
        """Parse DevRev webhook payload into normalized WebhookEvent."""
        event_type = payload.get("type", "unknown")
        event_id = payload.get("id", "")
        timestamp_str = payload.get("timestamp")

        timestamp = datetime.now(timezone.utc)
        if timestamp_str:
            try:
                timestamp = _parse_iso_timestamp(timestamp_str)
            except (ValueError, TypeError):
                pass

        # Extract metadata
        metadata: Dict[str, Any] = {}
        if "webhook_id" in payload:
            metadata["webhook_id"] = payload["webhook_id"]

        # Extract applies_to_part from nested event data
        applies_to_part = ""
        event_data = payload.get(event_type, {})
        work = event_data.get("work", {}) or event_data.get("old_work", {})
        if work:
            applies_to_part = (work.get("applies_to_part") or {}).get("id", "")

        return WebhookEvent(
            event_id=event_id,
            source=self.source_name,
            event_type=event_type,
            applies_to_part=applies_to_part,
            timestamp=timestamp,
            raw_payload=payload,
            metadata=metadata,
        )
