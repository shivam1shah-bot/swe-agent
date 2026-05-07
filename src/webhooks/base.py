"""
Base webhook source interface - all webhook sources must implement this.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional

from .models import WebhookEvent, WebhookVerificationResponse


class BaseWebhookSource(ABC):
    """Abstract base class for webhook event sources."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Unique name identifying this source (e.g., 'devrev', 'github')."""
        ...

    @abstractmethod
    def verify_signature(self, raw_body: bytes, headers: Dict[str, str]) -> bool:
        """
        Verify the authenticity of an incoming webhook request.

        Args:
            raw_body: Raw request body bytes.
            headers: HTTP request headers.

        Returns:
            True if signature is valid, False otherwise.
        """
        ...

    @abstractmethod
    def handle_verification(
        self, payload: dict
    ) -> Optional[WebhookVerificationResponse]:
        """
        Handle verification/challenge handshake if the payload is a verification request.

        Args:
            payload: Parsed JSON payload.

        Returns:
            WebhookVerificationResponse if this is a verification request, None otherwise.
        """
        ...

    @abstractmethod
    def parse_event(self, payload: dict) -> WebhookEvent:
        """
        Parse raw payload into a normalized WebhookEvent.

        Args:
            payload: Parsed JSON payload.

        Returns:
            Normalized WebhookEvent.
        """
        ...

    def validate_timestamp(self, payload: dict) -> bool:
        """
        Validate event timestamp to prevent replay attacks.
        Override in subclasses for source-specific timestamp validation.

        Args:
            payload: Parsed JSON payload.

        Returns:
            True if timestamp is fresh, False if stale.
        """
        return True
