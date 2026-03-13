"""
Default scoring weights and merge logic for synthesis priority scoring.

Products can override these weights via CIProduct.scoring_weights.
When a product has partial overrides, missing keys fall back to defaults.
"""

DEFAULT_SCORING_WEIGHTS = {
    "source_count": {"four": 50, "three": 40, "two": 25, "one": 10},
    "competitive_prevalence": {"table_stakes": 20, "emerging": 15, "differentiator": 10},
    "customer_votes": {"high": 20, "medium": 15, "low": 10},
    "internal_signal": {"high": 20, "medium": 10},
    "evidence_research": {"strong": 15, "moderate": 10},
    "confidence_bonus": 10,
}

# Thresholds for customer vote buckets
VOTE_THRESHOLDS = {"high": 50, "medium": 20, "low": 10}


def get_weights_for_product(product) -> dict:
    """
    Return scoring weights for a product, merging overrides with defaults.

    Args:
        product: CIProduct instance (or any object with scoring_weights attribute)

    Returns:
        Complete weights dict with all keys populated.
    """
    if not product.scoring_weights:
        return DEFAULT_SCORING_WEIGHTS.copy()

    merged = {}
    for key, default_val in DEFAULT_SCORING_WEIGHTS.items():
        if key in product.scoring_weights:
            if isinstance(default_val, dict):
                # Merge nested dict: product overrides take precedence
                merged[key] = {**default_val, **product.scoring_weights[key]}
            else:
                merged[key] = product.scoring_weights[key]
        else:
            merged[key] = default_val if not isinstance(default_val, dict) else default_val.copy()
    return merged


def format_scoring_prompt(weights: dict) -> str:
    """
    Format scoring weights into a prompt section for the synthesis agent.

    Args:
        weights: Complete weights dict (from get_weights_for_product)

    Returns:
        Formatted string for injection into the system prompt.
    """
    sc = weights["source_count"]
    cp = weights["competitive_prevalence"]
    cv = weights["customer_votes"]
    is_ = weights["internal_signal"]
    er = weights.get("evidence_research", {"strong": 15, "moderate": 10})
    cb = weights["confidence_bonus"]

    return f"""## Priority Scoring Guidelines (0-100)

Calculate priority_score using these factors:
- **Source count**: 4 sources = +{sc['four']}, 3 sources = +{sc['three']}, 2 sources = +{sc['two']}, 1 source = +{sc['one']}
- **Competitive prevalence**: Table Stakes = +{cp['table_stakes']}, Emerging = +{cp['emerging']}, Differentiator = +{cp['differentiator']}
- **Customer votes**: {VOTE_THRESHOLDS['high']}+ votes = +{cv['high']}, {VOTE_THRESHOLDS['medium']}-{VOTE_THRESHOLDS['high'] - 1} = +{cv['medium']}, {VOTE_THRESHOLDS['low']}-{VOTE_THRESHOLDS['medium'] - 1} = +{cv['low']}
- **Internal signal**: Lost deals OR high urgency support = +{is_['high']}, medium = +{is_['medium']}
- **Evidence/research signal**: Multiple corroborating evidence items = +{er['strong']}, single evidence item = +{er['moderate']}
- **Internal confidence**: High confidence (structured + activity agree) = +{cb} bonus"""
