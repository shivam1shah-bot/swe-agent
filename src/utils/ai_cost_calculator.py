"""
AI Cost Calculator utility.

This module provides functionality to calculate and estimate costs for AI model usage
across different providers (OpenAI, Anthropic, Google) for code review operations.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class ModelProvider(str, Enum):
    """Enum for AI model providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OTHER = "other"


@dataclass
class ModelPricing:
    """Pricing information for an AI model."""
    model_name: str
    provider: ModelProvider
    input_cost_per_1k_tokens: float  # Cost in USD per 1K input tokens
    output_cost_per_1k_tokens: float  # Cost in USD per 1K output tokens
    max_context_length: int
    typical_response_time_ms: float


class AICostCalculator:
    """
    Calculator for AI model usage costs and token consumption.
    
    Provides methods to estimate and calculate costs based on different
    AI models and usage patterns for code review operations.
    """
    
    def __init__(self):
        """Initialize the cost calculator with current model pricing."""
        self.model_pricing = {
            # OpenAI Models (as of 2024)
            "gpt-4-turbo": ModelPricing(
                model_name="gpt-4-turbo",
                provider=ModelProvider.OPENAI,
                input_cost_per_1k_tokens=0.01,  # $0.01 per 1K input tokens
                output_cost_per_1k_tokens=0.03,  # $0.03 per 1K output tokens
                max_context_length=128000,
                typical_response_time_ms=1500.0
            ),
            "gpt-4": ModelPricing(
                model_name="gpt-4",
                provider=ModelProvider.OPENAI,
                input_cost_per_1k_tokens=0.03,  # $0.03 per 1K input tokens
                output_cost_per_1k_tokens=0.06,  # $0.06 per 1K output tokens
                max_context_length=8192,
                typical_response_time_ms=2000.0
            ),
            "gpt-3.5-turbo": ModelPricing(
                model_name="gpt-3.5-turbo",
                provider=ModelProvider.OPENAI,
                input_cost_per_1k_tokens=0.0015,  # $0.0015 per 1K input tokens
                output_cost_per_1k_tokens=0.002,  # $0.002 per 1K output tokens
                max_context_length=16385,
                typical_response_time_ms=800.0
            ),
            
            # Anthropic Models (as of 2024)
            "claude-3-opus": ModelPricing(
                model_name="claude-3-opus",
                provider=ModelProvider.ANTHROPIC,
                input_cost_per_1k_tokens=0.015,  # $0.015 per 1K input tokens
                output_cost_per_1k_tokens=0.075,  # $0.075 per 1K output tokens
                max_context_length=200000,
                typical_response_time_ms=1800.0
            ),
            "claude-3-sonnet": ModelPricing(
                model_name="claude-3-sonnet", 
                provider=ModelProvider.ANTHROPIC,
                input_cost_per_1k_tokens=0.003,  # $0.003 per 1K input tokens
                output_cost_per_1k_tokens=0.015,  # $0.015 per 1K output tokens
                max_context_length=200000,
                typical_response_time_ms=1400.0
            ),
            "claude-3-haiku": ModelPricing(
                model_name="claude-3-haiku",
                provider=ModelProvider.ANTHROPIC,
                input_cost_per_1k_tokens=0.00025,  # $0.00025 per 1K input tokens
                output_cost_per_1k_tokens=0.00125,  # $0.00125 per 1K output tokens
                max_context_length=200000,
                typical_response_time_ms=1200.0
            ),
            
        }
    
    def calculate_cost(
        self, 
        model_name: str, 
        input_tokens: int, 
        output_tokens: int
    ) -> Tuple[float, Optional[ModelPricing]]:
        """
        Calculate the cost for a specific model and token usage.
        
        Args:
            model_name: Name of the AI model
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Tuple of (total_cost_usd, model_pricing_info)
        """
        if model_name not in self.model_pricing:
            # Default to GPT-4 Turbo pricing for unknown models
            model_pricing = self.model_pricing["gpt-4-turbo"]
        else:
            model_pricing = self.model_pricing[model_name]
            
        input_cost = (input_tokens / 1000) * model_pricing.input_cost_per_1k_tokens
        output_cost = (output_tokens / 1000) * model_pricing.output_cost_per_1k_tokens
        total_cost = input_cost + output_cost
        
        return total_cost, model_pricing
    
    def estimate_tokens_from_activity(
        self, 
        ai_reviewed_prs: int, 
        total_comments: int,
        lines_reviewed: int = 0
    ) -> int:
        """
        Estimate token consumption based on code review activity.
        
        Args:
            ai_reviewed_prs: Number of PRs reviewed by AI
            total_comments: Total number of AI comments
            lines_reviewed: Total lines of code reviewed (optional)
            
        Returns:
            Estimated total tokens consumed
        """
        # Estimation logic based on typical code review patterns
        
        # Average tokens per PR review (input + output)
        avg_tokens_per_pr = 8000  # ~5K input (code) + 3K output (review)
        
        # Average tokens per comment 
        avg_tokens_per_comment = 500  # ~300 input + 200 output
        
        # Base estimation
        pr_tokens = ai_reviewed_prs * avg_tokens_per_pr
        comment_tokens = total_comments * avg_tokens_per_comment
        
        # Adjust based on lines reviewed if available
        if lines_reviewed > 0:
            # Rough estimate: 1 token per 4 characters, ~80 chars per line
            line_tokens = lines_reviewed * 20  # ~20 tokens per line of code
            # Use the higher of line-based or activity-based estimation
            pr_tokens = max(pr_tokens, line_tokens)
        
        total_estimated_tokens = pr_tokens + comment_tokens
        
        return total_estimated_tokens
    
    def calculate_estimated_cost(self, estimated_tokens: int, model_name: str = "gpt-4-turbo") -> float:
        """
        Calculate estimated cost based on total tokens and default model.
        
        Args:
            estimated_tokens: Total estimated tokens
            model_name: Model to use for cost calculation
            
        Returns:
            Estimated cost in USD
        """
        # Assume 70% input tokens, 30% output tokens (typical for code review)
        input_tokens = int(estimated_tokens * 0.7)
        output_tokens = int(estimated_tokens * 0.3)
        
        cost, _ = self.calculate_cost(model_name, input_tokens, output_tokens)
        return cost
    
    def get_model_recommendations(self, use_case: str = "code_review") -> List[str]:
        """
        Get model recommendations based on use case.
        
        Args:
            use_case: The intended use case (code_review, documentation, etc.)
            
        Returns:
            List of recommended model names sorted by cost-effectiveness
        """
        if use_case == "code_review":
            # For code review, balance cost and quality
            return [
                "claude-3-haiku",      # Most cost-effective
                "gpt-3.5-turbo",       # Good balance
                "claude-3-sonnet",     # Better quality
                "gpt-4-turbo",         # High quality
                "claude-3-opus"        # Premium quality
            ]
        elif use_case == "documentation":
            # For documentation, prioritize cost
            return [
                "claude-3-haiku",
                "gpt-3.5-turbo",
            ]
        else:
            # Default recommendation
            return ["gpt-4-turbo", "claude-3-sonnet", "claude-3-haiku"]
    
    def generate_cost_optimization_suggestions(
        self, 
        total_cost: float, 
        repository_breakdown: List[Dict]
    ) -> List[str]:
        """
        Generate cost optimization suggestions based on usage patterns.
        
        Args:
            total_cost: Total cost across all repositories
            repository_breakdown: Per-repository cost breakdown
            
        Returns:
            List of optimization suggestions
        """
        suggestions = []
        
        # High cost threshold
        if total_cost > 1000:
            suggestions.append(
                f"High monthly cost detected (${total_cost:.2f}). Consider using "
                "more cost-effective models like Claude-3-Haiku for initial reviews."
            )
        
        # Find expensive repositories
        if repository_breakdown:
            high_cost_repos = [
                repo for repo in repository_breakdown 
                if repo.get("cost_per_pr", 0) > 10
            ]
            
            if high_cost_repos:
                repo_names = [repo["repository"] for repo in high_cost_repos[:3]]
                suggestions.append(
                    f"Repositories with high cost per PR: {', '.join(repo_names)}. "
                    "Consider optimizing prompts or using tiered model approach."
                )
        
        # Model efficiency suggestions
        if total_cost > 100:
            suggestions.append(
                "Consider implementing a tiered model approach: Use Claude-3-Haiku for "
                "initial screening and GPT-4-Turbo only for complex reviews."
            )
            
            suggestions.append(
                "Implement caching for similar code patterns to reduce redundant API calls."
            )
        
        # General optimization tips
        suggestions.extend([
            "Use batch processing for multiple files in the same PR to reduce API overhead.",
            "Implement token counting and limits to prevent unexpectedly expensive operations.",
            "Consider fine-tuning models on your codebase patterns for better efficiency."
        ])
        
        return suggestions
    
    def get_cost_breakdown_by_provider(self, models_used: List[Dict]) -> Dict[str, float]:
        """
        Get cost breakdown by provider.
        
        Args:
            models_used: List of model usage data
            
        Returns:
            Dictionary mapping provider to total cost
        """
        provider_costs = {}
        
        for model_data in models_used:
            model_name = model_data.get("model_name", "")
            total_cost = model_data.get("total_cost", 0.0)
            
            if model_name in self.model_pricing:
                provider = self.model_pricing[model_name].provider.value
            else:
                provider = "unknown"
                
            provider_costs[provider] = provider_costs.get(provider, 0.0) + total_cost
            
        return provider_costs
    
    def simulate_cost_with_different_models(
        self, 
        estimated_tokens: int
    ) -> Dict[str, float]:
        """
        Simulate costs with different model choices.
        
        Args:
            estimated_tokens: Total estimated tokens
            
        Returns:
            Dictionary mapping model names to estimated costs
        """
        model_costs = {}
        
        for model_name in self.model_pricing.keys():
            cost = self.calculate_estimated_cost(estimated_tokens, model_name)
            model_costs[model_name] = cost
            
        return model_costs
