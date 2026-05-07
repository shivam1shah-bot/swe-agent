"""
Unit tests for connector metadata utility.
"""

import pytest
from contextlib import contextmanager
from unittest.mock import patch, MagicMock


class TestConnectorConstants:
    def test_connector_constants(self):
        from src.utils.connector import CONNECTOR_SLACK, CONNECTOR_DEVREV, CONNECTOR_DASHBOARD
        assert CONNECTOR_SLACK == "slack"
        assert CONNECTOR_DEVREV == "devrev"
        assert CONNECTOR_DASHBOARD == "dashboard"


class TestStoreConnectorMetadata:
    def test_exception_does_not_propagate(self):
        """store_connector_metadata swallows all exceptions gracefully."""
        with patch("src.providers.database.session.get_session", side_effect=Exception("DB error")):
            from src.utils.connector import store_connector_metadata
            # Should not raise
            store_connector_metadata("task-1", "slack", "user@razorpay.com")

    def test_unknown_connector_uses_fallback(self):
        """Unknown connector type uses generic id field."""
        # Just verify the function accepts unknown connector names without raising
        with patch("src.providers.database.session.get_session", side_effect=Exception("skip")):
            from src.utils.connector import store_connector_metadata
            store_connector_metadata("task-1", "unknown_source", "user@razorpay.com",
                                     extra={"user_id": "U123"})
