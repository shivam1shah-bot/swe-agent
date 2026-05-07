"""Unit tests for rCoRe v2++ feature gate."""

from unittest.mock import patch

import pytest

from src.agents.review_agents.feature_gate import is_rcore_v2_plus_enabled


GATE_CONFIG_PATH = "src.agents.review_agents.feature_gate.get_config"


class TestIsRcoreV2PlusEnabled:

    def test_enabled_repo_returns_true(self):
        config = {"rcore_v2_plus": {"enabled": True, "enabled_repos": ["razorpay/api"]}}
        with patch(GATE_CONFIG_PATH, return_value=config):
            assert is_rcore_v2_plus_enabled("razorpay/api") is True

    def test_disabled_globally(self):
        config = {"rcore_v2_plus": {"enabled": False, "enabled_repos": ["razorpay/api"]}}
        with patch(GATE_CONFIG_PATH, return_value=config):
            assert is_rcore_v2_plus_enabled("razorpay/api") is False

    def test_repo_not_in_list(self):
        config = {"rcore_v2_plus": {"enabled": True, "enabled_repos": ["razorpay/api"]}}
        with patch(GATE_CONFIG_PATH, return_value=config):
            assert is_rcore_v2_plus_enabled("razorpay/checkout") is False

    def test_case_insensitive_match(self):
        config = {"rcore_v2_plus": {"enabled": True, "enabled_repos": ["razorpay/api"]}}
        with patch(GATE_CONFIG_PATH, return_value=config):
            assert is_rcore_v2_plus_enabled("Razorpay/API") is True

    def test_missing_config_section(self):
        with patch(GATE_CONFIG_PATH, return_value={}):
            assert is_rcore_v2_plus_enabled("razorpay/api") is False

    def test_wildcard_star(self):
        config = {"rcore_v2_plus": {"enabled": True, "enabled_repos": ["*"]}}
        with patch(GATE_CONFIG_PATH, return_value=config):
            assert is_rcore_v2_plus_enabled("any/repo") is True

    def test_empty_enabled_repos(self):
        config = {"rcore_v2_plus": {"enabled": True, "enabled_repos": []}}
        with patch(GATE_CONFIG_PATH, return_value=config):
            assert is_rcore_v2_plus_enabled("razorpay/api") is False

    def test_multiple_repos_in_list(self):
        config = {
            "rcore_v2_plus": {
                "enabled": True,
                "enabled_repos": ["razorpay/api", "razorpay/checkout", "razorpay/x"],
            }
        }
        with patch(GATE_CONFIG_PATH, return_value=config):
            assert is_rcore_v2_plus_enabled("razorpay/checkout") is True
            assert is_rcore_v2_plus_enabled("razorpay/settlements") is False
