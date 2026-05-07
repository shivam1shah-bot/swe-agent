#!/usr/bin/env python3
"""
pricing.py — Single source of truth for Claude model pricing and cost calculation.

Used by:
  - client/lib/parse_transcript.py (hook-time cost estimation)
  - backend/app/ (dashboard API, via sys.path injection in config.py)
  - analytics/analyze.py (CLI analytics)
"""

from typing import Optional

# (input, output, cache_read, cache_create) per 1M tokens
MODEL_PRICING = {
    "claude-opus-4-6":   (15.00, 75.00, 1.50,  18.75),
    "claude-opus-4":     (15.00, 75.00, 1.50,  18.75),
    "claude-sonnet-4-6": ( 3.00, 15.00, 0.30,   3.75),
    "claude-sonnet-4-5": ( 3.00, 15.00, 0.30,   3.75),
    "claude-sonnet-4":   ( 3.00, 15.00, 0.30,   3.75),
    "claude-haiku-4-5":  ( 0.80,  4.00, 0.08,   1.00),
    "claude-haiku-4":    ( 0.80,  4.00, 0.08,   1.00),
    "default":           ( 3.00, 15.00, 0.30,   3.75),
}

_SORTED_PREFIXES = sorted(
    (k for k in MODEL_PRICING if k != "default"), key=len, reverse=True
)


def get_model_rates(model_name: Optional[str] = None) -> tuple:
    """Longest-prefix match on model name -> (input, output, cache_read, cache_create) rates."""
    if model_name:
        for prefix in _SORTED_PREFIXES:
            if model_name.startswith(prefix):
                return MODEL_PRICING[prefix]
    return MODEL_PRICING["default"]


def cost_from_tokens(tokens: dict, model: Optional[str] = None) -> float:
    """
    Total cost from a normalized tokens dict.
    Keys: input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens.
    """
    r = get_model_rates(model)
    return (
        (tokens.get("input_tokens",          0) / 1_000_000) * r[0] +
        (tokens.get("output_tokens",         0) / 1_000_000) * r[1] +
        (tokens.get("cache_read_tokens",     0) / 1_000_000) * r[2] +
        (tokens.get("cache_creation_tokens", 0) / 1_000_000) * r[3]
    )


def cost_breakdown_from_usage(usage: dict, model: Optional[str] = None) -> dict:
    """
    Cost with per-category breakdown from raw API usage dict.
    Keys: input_tokens, output_tokens, cache_read_input_tokens, cache_creation_input_tokens.
    """
    r = get_model_rates(model)
    inp = usage.get("input_tokens", 0)
    out = usage.get("output_tokens", 0)
    cr  = usage.get("cache_read_input_tokens", 0)
    cc  = usage.get("cache_creation_input_tokens", 0)
    return {
        "input":          round((inp / 1_000_000) * r[0], 6),
        "output":         round((out / 1_000_000) * r[1], 6),
        "cache_read":     round((cr  / 1_000_000) * r[2], 6),
        "cache_creation": round((cc  / 1_000_000) * r[3], 6),
        "total":          round(
            (inp / 1_000_000) * r[0] + (out / 1_000_000) * r[1] +
            (cr  / 1_000_000) * r[2] + (cc  / 1_000_000) * r[3],
            6
        ),
    }


def sum_token_count(tokens: dict) -> int:
    """Sum all token categories from a normalized tokens dict."""
    return (
        tokens.get("input_tokens",          0) +
        tokens.get("output_tokens",         0) +
        tokens.get("cache_read_tokens",     0) +
        tokens.get("cache_creation_tokens", 0)
    )


def cache_savings(tokens: dict, model: Optional[str] = None) -> float:
    """Savings from cache reads vs full input pricing."""
    r = get_model_rates(model)
    cr = tokens.get("cache_read_tokens", 0)
    return (cr / 1_000_000) * (r[0] - r[2])
