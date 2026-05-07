"""
Unit tests for DevRev webhook source and router.

Covers:
  - DevRevWebhookSource.verify_signature — HMAC-SHA256 validation
  - DevRevWebhookSource.handle_verification — challenge/echo handshake
  - DevRevWebhookSource.validate_timestamp — replay protection
  - DevRevWebhookSource.parse_event — payload normalization
  - receive_webhook router — end-to-end request routing
"""

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_secret_and_header(body: bytes, secret_plaintext: str = "test-secret") -> tuple[str, str]:
    """Return (base64-encoded secret, valid X-DevRev-Signature value) for a body."""
    key_bytes = secret_plaintext.encode("utf-8")
    b64_secret = base64.b64encode(key_bytes).decode("ascii")
    digest = hmac.new(key_bytes, msg=body, digestmod=hashlib.sha256).digest()
    signature = base64.b64encode(digest).decode("utf-8")
    return b64_secret, signature


def _make_devrev_source(secret: str = ""):
    """Instantiate DevRevWebhookSource with a patched config."""
    from src.webhooks.devrev import DevRevWebhookSource

    config = {"webhooks": {"devrev": {"webhook_secret": secret, "max_timestamp_age_seconds": 300}}}
    with patch("src.webhooks.devrev.get_config", return_value=config):
        return DevRevWebhookSource()


# ---------------------------------------------------------------------------
# verify_signature
# ---------------------------------------------------------------------------


class TestVerifySignature:
    def test_no_secret_skips_verification(self):
        source = _make_devrev_source(secret="")
        # No secret → always True (warn and skip)
        assert source.verify_signature(b"any body", {}) is True

    def test_missing_signature_header(self):
        _, _ = _make_secret_and_header(b"body")
        b64_secret, _ = _make_secret_and_header(b"body")
        source = _make_devrev_source(secret=b64_secret)
        assert source.verify_signature(b"body", {}) is False

    def test_valid_signature(self):
        body = b'{"type":"work_created"}'
        b64_secret, signature = _make_secret_and_header(body)
        source = _make_devrev_source(secret=b64_secret)
        assert source.verify_signature(body, {"x-devrev-signature": signature}) is True

    def test_invalid_signature(self):
        body = b'{"type":"work_created"}'
        b64_secret, _ = _make_secret_and_header(body)
        source = _make_devrev_source(secret=b64_secret)
        assert source.verify_signature(body, {"x-devrev-signature": "bad-sig"}) is False

    def test_signature_header_case_insensitive(self):
        body = b'{"type":"work_created"}'
        b64_secret, signature = _make_secret_and_header(body)
        source = _make_devrev_source(secret=b64_secret)
        # Header passed with mixed case — should still match
        assert source.verify_signature(body, {"X-DevRev-Signature": signature}) is True

    def test_body_mismatch_fails(self):
        body = b'{"type":"work_created"}'
        b64_secret, signature = _make_secret_and_header(body)
        source = _make_devrev_source(secret=b64_secret)
        # Tampered body
        assert source.verify_signature(b'{"type":"tampered"}', {"x-devrev-signature": signature}) is False

    def test_raw_bytes_secret_fallback(self):
        """If base64 decoding fails, falls back to UTF-8 bytes of the secret string."""
        # "not-base64!!!" is not valid base64 → fallback path
        raw_secret = "not-base64!!!"
        body = b"hello"
        digest = hmac.new(raw_secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256).digest()
        signature = base64.b64encode(digest).decode("utf-8")

        config = {"webhooks": {"devrev": {"webhook_secret": raw_secret}}}
        with patch("src.webhooks.devrev.get_config", return_value=config):
            from src.webhooks.devrev import DevRevWebhookSource
            source = DevRevWebhookSource()

        assert source.verify_signature(body, {"x-devrev-signature": signature}) is True


# ---------------------------------------------------------------------------
# handle_verification
# ---------------------------------------------------------------------------


class TestHandleVerification:
    def test_non_verify_type_returns_none(self):
        source = _make_devrev_source()
        result = source.handle_verification({"type": "work_created"})
        assert result is None

    def test_verify_type_echoes_challenge(self):
        source = _make_devrev_source()
        payload = {"type": "verify", "verify": {"challenge": "abc123"}}
        result = source.handle_verification(payload)
        assert result is not None
        assert result.challenge == "abc123"

    def test_verify_type_missing_challenge_returns_none(self):
        source = _make_devrev_source()
        payload = {"type": "verify", "verify": {}}
        result = source.handle_verification(payload)
        assert result is None

    def test_verify_missing_verify_key_returns_none(self):
        source = _make_devrev_source()
        result = source.handle_verification({"type": "verify"})
        assert result is None


# ---------------------------------------------------------------------------
# validate_timestamp
# ---------------------------------------------------------------------------


class TestValidateTimestamp:
    def test_no_timestamp_passes(self):
        source = _make_devrev_source()
        assert source.validate_timestamp({}) is True

    def test_fresh_timestamp_passes(self):
        source = _make_devrev_source()
        ts = datetime.now(timezone.utc).isoformat()
        assert source.validate_timestamp({"timestamp": ts}) is True

    def test_stale_timestamp_rejected(self):
        source = _make_devrev_source()
        stale = (datetime.now(timezone.utc) - timedelta(seconds=400)).isoformat()
        assert source.validate_timestamp({"timestamp": stale}) is False

    def test_z_suffix_timestamp_parsed(self):
        source = _make_devrev_source()
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        assert source.validate_timestamp({"timestamp": ts}) is True

    def test_invalid_timestamp_format_passes(self):
        """Malformed timestamps should not reject the event (fail open)."""
        source = _make_devrev_source()
        assert source.validate_timestamp({"timestamp": "not-a-date"}) is True

    def test_exactly_at_boundary_passes(self):
        source = _make_devrev_source()
        # 299 seconds old — within 300s window
        ts = (datetime.now(timezone.utc) - timedelta(seconds=299)).isoformat()
        assert source.validate_timestamp({"timestamp": ts}) is True


# ---------------------------------------------------------------------------
# parse_event
# ---------------------------------------------------------------------------


class TestParseEvent:
    def test_basic_event_parsed(self):
        source = _make_devrev_source()
        payload = {
            "type": "work_created",
            "id": "evt-001",
            "timestamp": "2024-01-01T12:00:00Z",
            "webhook_id": "wh-123",
        }
        event = source.parse_event(payload)
        assert event.event_id == "evt-001"
        assert event.source == "devrev"
        assert event.event_type == "work_created"
        assert event.applies_to_part == ""
        assert event.metadata["webhook_id"] == "wh-123"

    def test_applies_to_part_extracted_from_work(self):
        source = _make_devrev_source()
        part_id = "don:core:dvrv-in-1:devo/2sRI6Hepzz:runnable/277"
        payload = {
            "type": "work_created",
            "id": "evt-002",
            "work_created": {
                "work": {
                    "applies_to_part": {"id": part_id},
                }
            },
        }
        event = source.parse_event(payload)
        assert event.applies_to_part == part_id

    def test_applies_to_part_extracted_from_old_work(self):
        source = _make_devrev_source()
        part_id = "don:core:dvrv-in-1:devo/2sRI6Hepzz:runnable/277"
        payload = {
            "type": "work_updated",
            "id": "evt-003",
            "work_updated": {
                "old_work": {
                    "applies_to_part": {"id": part_id},
                }
            },
        }
        event = source.parse_event(payload)
        assert event.applies_to_part == part_id

    def test_missing_timestamp_defaults_to_now(self):
        source = _make_devrev_source()
        before = datetime.now(timezone.utc)
        event = source.parse_event({"type": "work_created", "id": "evt-004"})
        after = datetime.now(timezone.utc)
        assert before <= event.timestamp <= after

    def test_invalid_timestamp_defaults_to_now(self):
        source = _make_devrev_source()
        before = datetime.now(timezone.utc)
        event = source.parse_event({"type": "work_created", "id": "evt-005", "timestamp": "bad"})
        after = datetime.now(timezone.utc)
        assert before <= event.timestamp <= after

    def test_raw_payload_preserved(self):
        source = _make_devrev_source()
        payload = {"type": "work_created", "id": "evt-006", "extra": "data"}
        event = source.parse_event(payload)
        assert event.raw_payload == payload


# ---------------------------------------------------------------------------
# receive_webhook router
# ---------------------------------------------------------------------------


def _build_test_app(secret: str = ""):
    """Build a FastAPI test app with the webhook router and a patched devrev source."""
    import src.webhooks.router as wh_router

    config = {"webhooks": {"devrev": {"webhook_secret": secret, "max_timestamp_age_seconds": 300}, "enabled_sources": ["devrev"]}}

    with patch("src.webhooks.devrev.get_config", return_value=config), \
         patch("src.webhooks.registry.get_config", return_value=config):
        from src.webhooks.registry import WebhookSourceRegistry
        registry = WebhookSourceRegistry()

    app = FastAPI()
    # Reset module-level singletons so each test gets a fresh state
    wh_router._registry = registry
    wh_router._orchestrator = None

    app.include_router(wh_router.router)
    return app


class TestReceiveWebhookRouter:
    def test_unknown_source_returns_404(self):
        app = _build_test_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/webhooks/unknown", json={"type": "work_created"})
        assert resp.status_code == 404

    def test_invalid_signature_returns_401(self):
        app = _build_test_app(secret=base64.b64encode(b"real-secret").decode())
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/webhooks/devrev",
            content=b'{"type":"work_created","id":"e1"}',
            headers={"Content-Type": "application/json", "x-devrev-signature": "badsig"},
        )
        assert resp.status_code == 401

    def test_invalid_json_returns_400(self):
        app = _build_test_app()  # no secret → skip sig check
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/webhooks/devrev",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    def test_challenge_handshake_echoed(self):
        app = _build_test_app()
        client = TestClient(app, raise_server_exceptions=False)
        payload = {"type": "verify", "verify": {"challenge": "xyz789"}}
        resp = client.post("/webhooks/devrev", json=payload)
        assert resp.status_code == 200
        assert resp.json()["challenge"] == "xyz789"

    def test_stale_event_returns_401(self):
        app = _build_test_app()
        client = TestClient(app, raise_server_exceptions=False)
        stale_ts = (datetime.now(timezone.utc) - timedelta(seconds=400)).isoformat()
        payload = {"type": "work_created", "id": "e2", "timestamp": stale_ts}
        resp = client.post("/webhooks/devrev", json=payload)
        assert resp.status_code == 401

    def test_successful_dispatch_returns_200(self):
        import src.webhooks.router as wh_router

        app = _build_test_app()
        mock_orchestrator = MagicMock()
        mock_orchestrator.dispatch = AsyncMock(return_value=[])
        wh_router._orchestrator = mock_orchestrator

        client = TestClient(app, raise_server_exceptions=False)
        ts = datetime.now(timezone.utc).isoformat()
        payload = {"type": "work_created", "id": "e3", "timestamp": ts}
        resp = client.post("/webhooks/devrev", json=payload)
        assert resp.status_code == 200
        mock_orchestrator.dispatch.assert_awaited_once()

    def test_partial_handler_failure_still_returns_200(self):
        """A failing handler should log but not break the response."""
        import src.webhooks.router as wh_router
        from src.webhooks.models import HandlerResult

        app = _build_test_app()
        mock_orchestrator = MagicMock()
        mock_orchestrator.dispatch = AsyncMock(return_value=[
            HandlerResult(handler_name="h1", success=True),
            HandlerResult(handler_name="h2", success=False, message="boom"),
        ])
        wh_router._orchestrator = mock_orchestrator

        client = TestClient(app, raise_server_exceptions=False)
        ts = datetime.now(timezone.utc).isoformat()
        resp = client.post("/webhooks/devrev", json={"type": "work_created", "id": "e4", "timestamp": ts})
        assert resp.status_code == 200

    def test_webhook_health_endpoint(self):
        app = _build_test_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/webhooks/health")
        assert resp.status_code == 200
        assert "devrev" in resp.json()["sources"]
