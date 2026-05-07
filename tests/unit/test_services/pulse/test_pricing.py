"""
Tests for src/utils/pricing.py — cost calculation single source of truth.
"""

from src.utils.pricing import (
    get_model_rates,
    cost_from_tokens,
    cost_breakdown_from_usage,
    sum_token_count,
    cache_savings,
    MODEL_PRICING,
)


class TestGetModelRates:

    def test_exact_match(self):
        assert get_model_rates("claude-opus-4") == MODEL_PRICING["claude-opus-4"]

    def test_prefix_match_versioned(self):
        rates = get_model_rates("claude-sonnet-4-6-20260310")
        assert rates == MODEL_PRICING["claude-sonnet-4-6"]

    def test_longest_prefix_wins(self):
        rates = get_model_rates("claude-opus-4-6")
        assert rates == MODEL_PRICING["claude-opus-4-6"]

    def test_unknown_model_returns_default(self):
        assert get_model_rates("gpt-4o") == MODEL_PRICING["default"]

    def test_none_returns_default(self):
        assert get_model_rates(None) == MODEL_PRICING["default"]

    def test_empty_string_returns_default(self):
        assert get_model_rates("") == MODEL_PRICING["default"]


class TestCostFromTokens:

    def test_known_model_cost(self):
        tokens = {
            "input_tokens": 1_000_000,
            "output_tokens": 1_000_000,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
        }
        cost = cost_from_tokens(tokens, "claude-sonnet-4")
        # 3.00 + 15.00 = 18.00
        assert abs(cost - 18.00) < 0.001

    def test_zero_tokens(self):
        tokens = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
        }
        assert cost_from_tokens(tokens, "claude-opus-4") == 0.0

    def test_empty_dict_defaults_to_zero(self):
        assert cost_from_tokens({}, "claude-opus-4") == 0.0

    def test_cache_tokens_included(self):
        tokens = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 1_000_000,
            "cache_creation_tokens": 1_000_000,
        }
        cost = cost_from_tokens(tokens, "claude-sonnet-4")
        # 0.30 + 3.75 = 4.05
        assert abs(cost - 4.05) < 0.001

    def test_default_model(self):
        tokens = {"input_tokens": 1_000_000, "output_tokens": 0,
                  "cache_read_tokens": 0, "cache_creation_tokens": 0}
        cost_explicit = cost_from_tokens(tokens, "claude-sonnet-4")
        cost_default = cost_from_tokens(tokens)
        # default is same as sonnet-4 rates
        assert abs(cost_explicit - cost_default) < 0.001


class TestCostBreakdownFromUsage:

    def test_returns_all_categories_and_total(self):
        usage = {
            "input_tokens": 1_000_000,
            "output_tokens": 500_000,
            "cache_read_input_tokens": 200_000,
            "cache_creation_input_tokens": 100_000,
        }
        result = cost_breakdown_from_usage(usage, "claude-sonnet-4")
        assert "input" in result
        assert "output" in result
        assert "cache_read" in result
        assert "cache_creation" in result
        assert "total" in result
        expected_total = result["input"] + result["output"] + result["cache_read"] + result["cache_creation"]
        assert abs(result["total"] - expected_total) < 0.000002

    def test_empty_usage(self):
        result = cost_breakdown_from_usage({})
        assert result["total"] == 0.0


class TestSumTokenCount:

    def test_sums_all_categories(self):
        tokens = {
            "input_tokens": 100,
            "output_tokens": 200,
            "cache_read_tokens": 300,
            "cache_creation_tokens": 400,
        }
        assert sum_token_count(tokens) == 1000

    def test_empty_dict(self):
        assert sum_token_count({}) == 0

    def test_missing_keys_default_to_zero(self):
        assert sum_token_count({"input_tokens": 500}) == 500


class TestCacheSavings:

    def test_savings_calculation(self):
        tokens = {
            "cache_read_tokens": 1_000_000,
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_tokens": 0,
        }
        saved = cache_savings(tokens, "claude-sonnet-4")
        # (1M / 1M) * (3.00 - 0.30) = 2.70
        assert abs(saved - 2.70) < 0.001

    def test_no_cache_reads_no_savings(self):
        tokens = {"cache_read_tokens": 0}
        assert cache_savings(tokens, "claude-opus-4") == 0.0

    def test_empty_dict_no_savings(self):
        assert cache_savings({}) == 0.0
