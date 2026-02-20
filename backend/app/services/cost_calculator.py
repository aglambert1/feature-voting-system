"""
Cost calculation utility for LLM usage.

Provides pricing data and cost calculation functions for various Claude models.
Pricing should be updated as Anthropic updates their pricing.
"""

# Pricing as of Jan 2025 - update as needed
# https://www.anthropic.com/pricing
MODEL_PRICING = {
    # Claude 4 models
    "claude-sonnet-4-20250514": {
        "input_per_1m": 3.00,
        "output_per_1m": 15.00,
    },
    "claude-sonnet-4-5-20250929": {
        "input_per_1m": 3.00,
        "output_per_1m": 15.00,
    },
    # Claude 3.5 models
    "claude-3-5-sonnet-20241022": {
        "input_per_1m": 3.00,
        "output_per_1m": 15.00,
    },
    "claude-3-5-sonnet-20240620": {
        "input_per_1m": 3.00,
        "output_per_1m": 15.00,
    },
    "claude-3-5-haiku-20241022": {
        "input_per_1m": 0.80,
        "output_per_1m": 4.00,
    },
    # Claude 3 models
    "claude-3-opus-20240229": {
        "input_per_1m": 15.00,
        "output_per_1m": 75.00,
    },
    "claude-3-sonnet-20240229": {
        "input_per_1m": 3.00,
        "output_per_1m": 15.00,
    },
    "claude-3-haiku-20240307": {
        "input_per_1m": 0.25,
        "output_per_1m": 1.25,
    },
}

# Default fallback for unknown models (uses Sonnet pricing as safe default)
DEFAULT_PRICING = {
    "input_per_1m": 3.00,
    "output_per_1m": 15.00,
}


def calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int
) -> float:
    """
    Calculate estimated cost in USD for an LLM call.

    Args:
        model: The model identifier (e.g., "claude-3-haiku-20240307")
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Estimated cost in USD (rounded to 6 decimal places)
    """
    pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)

    input_cost = (input_tokens / 1_000_000) * pricing["input_per_1m"]
    output_cost = (output_tokens / 1_000_000) * pricing["output_per_1m"]

    return round(input_cost + output_cost, 6)


def format_cost(cost_usd: float) -> str:
    """
    Format cost for display.

    Args:
        cost_usd: Cost in USD

    Returns:
        Formatted string (e.g., "$0.0012" or "$1.23")
    """
    if cost_usd < 0.01:
        return f"${cost_usd:.4f}"
    return f"${cost_usd:.2f}"


def get_model_pricing(model: str) -> dict:
    """
    Get pricing info for a model.

    Args:
        model: The model identifier

    Returns:
        Dict with input_per_1m and output_per_1m pricing
    """
    return MODEL_PRICING.get(model, DEFAULT_PRICING)
