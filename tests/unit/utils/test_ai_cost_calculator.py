"""
Unit tests for AI Cost Calculator.

Tests cost calculation, token estimation, and optimization suggestions.
"""

import pytest
from src.utils.ai_cost_calculator import (
    AICostCalculator,
    ModelProvider,
    ModelPricing
)


class TestModelProvider:
    """Test suite for ModelProvider enum."""

    def test_model_provider_values(self):
        """Test that ModelProvider has expected values."""
        assert ModelProvider.OPENAI == "openai"
        assert ModelProvider.ANTHROPIC == "anthropic"
        assert ModelProvider.OTHER == "other"

    def test_model_provider_is_string_enum(self):
        """Test that ModelProvider values are strings."""
        assert isinstance(ModelProvider.OPENAI.value, str)
        assert isinstance(ModelProvider.ANTHROPIC.value, str)


class TestModelPricing:
    """Test suite for ModelPricing dataclass."""

    def test_model_pricing_creation(self):
        """Test creating ModelPricing instance."""
        pricing = ModelPricing(
            model_name="test-model",
            provider=ModelProvider.OPENAI,
            input_cost_per_1k_tokens=0.01,
            output_cost_per_1k_tokens=0.02,
            max_context_length=8192,
            typical_response_time_ms=1500.0
        )

        assert pricing.model_name == "test-model"
        assert pricing.provider == ModelProvider.OPENAI
        assert pricing.input_cost_per_1k_tokens == 0.01
        assert pricing.output_cost_per_1k_tokens == 0.02
        assert pricing.max_context_length == 8192
        assert pricing.typical_response_time_ms == 1500.0


class TestAICostCalculator:
    """Test suite for AICostCalculator."""

    @pytest.fixture
    def calculator(self):
        """Create an AICostCalculator instance."""
        return AICostCalculator()

    def test_init_loads_model_pricing(self, calculator):
        """Test that calculator initializes with model pricing data."""
        assert len(calculator.model_pricing) > 0
        assert "gpt-4-turbo" in calculator.model_pricing
        assert "claude-3-opus" in calculator.model_pricing

    def test_all_models_have_correct_structure(self, calculator):
        """Test that all models have required pricing fields."""
        for model_name, pricing in calculator.model_pricing.items():
            assert isinstance(pricing, ModelPricing)
            assert pricing.model_name == model_name
            assert isinstance(pricing.provider, ModelProvider)
            assert pricing.input_cost_per_1k_tokens >= 0
            assert pricing.output_cost_per_1k_tokens >= 0
            assert pricing.max_context_length > 0
            assert pricing.typical_response_time_ms > 0

    def test_calculate_cost_gpt4_turbo(self, calculator):
        """Test cost calculation for GPT-4 Turbo."""
        cost, pricing = calculator.calculate_cost("gpt-4-turbo", 1000, 500)

        # Cost should be: (1000/1000 * 0.01) + (500/1000 * 0.03)
        expected_cost = (1.0 * 0.01) + (0.5 * 0.03)
        assert abs(cost - expected_cost) < 0.0001
        assert pricing.model_name == "gpt-4-turbo"

    def test_calculate_cost_claude_haiku(self, calculator):
        """Test cost calculation for Claude-3 Haiku."""
        cost, pricing = calculator.calculate_cost("claude-3-haiku", 2000, 1000)

        # Cost should be: (2000/1000 * 0.00025) + (1000/1000 * 0.00125)
        expected_cost = (2.0 * 0.00025) + (1.0 * 0.00125)
        assert abs(cost - expected_cost) < 0.0001
        assert pricing.model_name == "claude-3-haiku"

    def test_calculate_cost_unknown_model_uses_default(self, calculator):
        """Test that unknown models default to GPT-4 Turbo pricing."""
        cost, pricing = calculator.calculate_cost("unknown-model", 1000, 500)

        # Should use gpt-4-turbo pricing as default
        expected_cost = (1.0 * 0.01) + (0.5 * 0.03)
        assert abs(cost - expected_cost) < 0.0001
        assert pricing.model_name == "gpt-4-turbo"

    def test_calculate_cost_zero_tokens(self, calculator):
        """Test cost calculation with zero tokens."""
        cost, pricing = calculator.calculate_cost("gpt-4-turbo", 0, 0)

        assert cost == 0.0
        assert pricing is not None

    def test_calculate_cost_large_numbers(self, calculator):
        """Test cost calculation with large token counts."""
        cost, pricing = calculator.calculate_cost("gpt-4-turbo", 100000, 50000)

        # Cost should be: (100000/1000 * 0.01) + (50000/1000 * 0.03)
        expected_cost = (100.0 * 0.01) + (50.0 * 0.03)
        assert abs(cost - expected_cost) < 0.0001

    def test_estimate_tokens_from_activity_basic(self, calculator):
        """Test basic token estimation from activity."""
        estimated = calculator.estimate_tokens_from_activity(
            ai_reviewed_prs=10,
            total_comments=50
        )

        # Should be: (10 * 8000) + (50 * 500) = 105000
        expected = (10 * 8000) + (50 * 500)
        assert estimated == expected

    def test_estimate_tokens_from_activity_with_lines(self, calculator):
        """Test token estimation with lines reviewed."""
        estimated = calculator.estimate_tokens_from_activity(
            ai_reviewed_prs=5,
            total_comments=10,
            lines_reviewed=1000
        )

        # With lines: max(5 * 8000, 1000 * 20) + 10 * 500
        # = max(40000, 20000) + 5000 = 45000
        expected = (5 * 8000) + (10 * 500)
        assert estimated == expected

    def test_estimate_tokens_from_activity_lines_override(self, calculator):
        """Test that lines reviewed can override PR-based estimation."""
        estimated = calculator.estimate_tokens_from_activity(
            ai_reviewed_prs=1,
            total_comments=5,
            lines_reviewed=10000  # Large number of lines
        )

        # With many lines: max(1 * 8000, 10000 * 20) + 5 * 500
        # = max(8000, 200000) + 2500 = 202500
        expected = (10000 * 20) + (5 * 500)
        assert estimated == expected

    def test_estimate_tokens_zero_activity(self, calculator):
        """Test token estimation with zero activity."""
        estimated = calculator.estimate_tokens_from_activity(
            ai_reviewed_prs=0,
            total_comments=0
        )

        assert estimated == 0

    def test_calculate_estimated_cost(self, calculator):
        """Test estimated cost calculation."""
        estimated_tokens = 10000
        cost = calculator.calculate_estimated_cost(estimated_tokens, "gpt-4-turbo")

        # With 70% input, 30% output: 7000 input, 3000 output
        # Cost: (7 * 0.01) + (3 * 0.03) = 0.16
        expected_cost = (7.0 * 0.01) + (3.0 * 0.03)
        assert abs(cost - expected_cost) < 0.0001

    def test_calculate_estimated_cost_different_model(self, calculator):
        """Test estimated cost with different model."""
        estimated_tokens = 10000
        cost = calculator.calculate_estimated_cost(estimated_tokens, "claude-3-haiku")

        # With 70% input, 30% output: 7000 input, 3000 output
        # Cost: (7 * 0.00025) + (3 * 0.00125) = 0.00175 + 0.00375 = 0.0055
        expected_cost = (7.0 * 0.00025) + (3.0 * 0.00125)
        assert abs(cost - expected_cost) < 0.00001

    def test_get_model_recommendations_code_review(self, calculator):
        """Test model recommendations for code review use case."""
        recommendations = calculator.get_model_recommendations("code_review")

        assert isinstance(recommendations, list)
        assert len(recommendations) > 0
        # Should recommend cost-effective model first
        assert recommendations[0] in ["claude-3-haiku", "gpt-3.5-turbo"]
        # Premium models should be last
        assert "claude-3-opus" in recommendations

    def test_get_model_recommendations_documentation(self, calculator):
        """Test model recommendations for documentation use case."""
        recommendations = calculator.get_model_recommendations("documentation")

        assert isinstance(recommendations, list)
        assert len(recommendations) > 0
        # Should prioritize cost for documentation
        assert recommendations[0] in ["claude-3-haiku", "gpt-3.5-turbo"]

    def test_get_model_recommendations_default(self, calculator):
        """Test model recommendations for unknown use case."""
        recommendations = calculator.get_model_recommendations("unknown_use_case")

        assert isinstance(recommendations, list)
        assert len(recommendations) > 0

    def test_generate_cost_optimization_suggestions_high_cost(self, calculator):
        """Test optimization suggestions for high cost."""
        suggestions = calculator.generate_cost_optimization_suggestions(
            total_cost=1500.0,
            repository_breakdown=[]
        )

        assert isinstance(suggestions, list)
        assert len(suggestions) > 0
        # Should mention high cost
        assert any("high" in s.lower() or "1500" in s for s in suggestions)

    def test_generate_cost_optimization_suggestions_expensive_repos(self, calculator):
        """Test optimization suggestions for expensive repositories."""
        repo_breakdown = [
            {"repository": "repo1", "cost_per_pr": 15.0},
            {"repository": "repo2", "cost_per_pr": 12.0},
            {"repository": "repo3", "cost_per_pr": 5.0}
        ]

        suggestions = calculator.generate_cost_optimization_suggestions(
            total_cost=500.0,
            repository_breakdown=repo_breakdown
        )

        assert isinstance(suggestions, list)
        # Should mention expensive repos
        assert any("repo1" in s or "high cost per pr" in s.lower() for s in suggestions)

    def test_generate_cost_optimization_suggestions_moderate_cost(self, calculator):
        """Test optimization suggestions for moderate cost."""
        suggestions = calculator.generate_cost_optimization_suggestions(
            total_cost=150.0,
            repository_breakdown=[]
        )

        assert isinstance(suggestions, list)
        # Should still provide general optimization tips
        assert any("batch" in s.lower() or "cache" in s.lower() for s in suggestions)

    def test_generate_cost_optimization_suggestions_low_cost(self, calculator):
        """Test optimization suggestions for low cost."""
        suggestions = calculator.generate_cost_optimization_suggestions(
            total_cost=50.0,
            repository_breakdown=[]
        )

        assert isinstance(suggestions, list)
        # Should still provide general tips
        assert len(suggestions) >= 3

    def test_get_cost_breakdown_by_provider(self, calculator):
        """Test cost breakdown by provider."""
        models_used = [
            {"model_name": "gpt-4-turbo", "total_cost": 10.0},
            {"model_name": "claude-3-opus", "total_cost": 20.0},
            {"model_name": "gpt-3.5-turbo", "total_cost": 5.0},
        ]

        breakdown = calculator.get_cost_breakdown_by_provider(models_used)

        assert isinstance(breakdown, dict)
        assert breakdown["openai"] == 15.0  # 10 + 5
        assert breakdown["anthropic"] == 20.0

    def test_get_cost_breakdown_by_provider_unknown_model(self, calculator):
        """Test cost breakdown with unknown models."""
        models_used = [
            {"model_name": "unknown-model", "total_cost": 10.0}
        ]

        breakdown = calculator.get_cost_breakdown_by_provider(models_used)

        assert "unknown" in breakdown
        assert breakdown["unknown"] == 10.0

    def test_get_cost_breakdown_by_provider_empty_list(self, calculator):
        """Test cost breakdown with empty list."""
        breakdown = calculator.get_cost_breakdown_by_provider([])

        assert isinstance(breakdown, dict)
        assert len(breakdown) == 0

    def test_simulate_cost_with_different_models(self, calculator):
        """Test cost simulation across different models."""
        estimated_tokens = 10000
        simulation = calculator.simulate_cost_with_different_models(estimated_tokens)

        assert isinstance(simulation, dict)
        assert len(simulation) > 0
        # All known models should be in simulation
        assert "gpt-4-turbo" in simulation
        assert "claude-3-haiku" in simulation
        # Costs should be different
        assert simulation["claude-3-haiku"] < simulation["gpt-4-turbo"]
        assert simulation["claude-3-haiku"] < simulation["claude-3-opus"]

    def test_simulate_cost_with_different_models_ordering(self, calculator):
        """Test that cheaper models have lower costs in simulation."""
        estimated_tokens = 10000
        simulation = calculator.simulate_cost_with_different_models(estimated_tokens)

        # Claude Haiku should be cheapest
        haiku_cost = simulation["claude-3-haiku"]
        gpt4_cost = simulation["gpt-4-turbo"]
        opus_cost = simulation["claude-3-opus"]

        assert haiku_cost < gpt4_cost < opus_cost

    def test_model_pricing_has_all_openai_models(self, calculator):
        """Test that OpenAI models are included."""
        assert "gpt-4-turbo" in calculator.model_pricing
        assert "gpt-4" in calculator.model_pricing
        assert "gpt-3.5-turbo" in calculator.model_pricing

    def test_model_pricing_has_all_anthropic_models(self, calculator):
        """Test that Anthropic models are included."""
        assert "claude-3-opus" in calculator.model_pricing
        assert "claude-3-sonnet" in calculator.model_pricing
        assert "claude-3-haiku" in calculator.model_pricing

    def test_model_pricing_has_all_providers(self, calculator):
        """Test that OpenAI and Anthropic models are included."""
        assert "gpt-4-turbo" in calculator.model_pricing
        assert "claude-3-opus" in calculator.model_pricing

    def test_anthropic_models_have_large_context(self, calculator):
        """Test that Anthropic models have 200k context length."""
        assert calculator.model_pricing["claude-3-opus"].max_context_length == 200000
        assert calculator.model_pricing["claude-3-sonnet"].max_context_length == 200000
        assert calculator.model_pricing["claude-3-haiku"].max_context_length == 200000

    def test_cost_calculation_precision(self, calculator):
        """Test that cost calculations maintain precision for small values."""
        # Small token counts should still calculate correctly
        cost, _ = calculator.calculate_cost("claude-3-haiku", 10, 5)

        # Cost: (0.01 * 0.00025) + (0.005 * 0.00125)
        expected_cost = (0.01 * 0.00025) + (0.005 * 0.00125)
        assert abs(cost - expected_cost) < 0.000001
