"""MCP Prompts for Feature-IQ."""

from mcp_server import mcp


@mcp.prompt()
def weekly_update(product_id: int) -> str:
    """Generate a weekly competitive and customer feedback update."""
    return f"""Generate a weekly competitive and customer feedback update for product {product_id}.

Steps:
1. Use ci_get_alerts to check for recent competitive changes
2. Use ideas_get_top_voted to see what customers care about most
3. Use synthesis_get_opportunities to get prioritized opportunities

Present findings as structured evidence. Note any data gaps."""


@mcp.prompt()
def feature_evidence_review(product_id: int, feature_description: str) -> str:
    """Gather all evidence about a feature capability."""
    return f"""Gather all evidence about "{feature_description}" for product {product_id}.

Steps:
1. Use evaluate_feature_evidence to search competitive, customer, and internal data
2. Present findings organized by source type
3. Note what evidence is available and what gaps exist

Do NOT make build/don't-build recommendations. Present the evidence and let the PM decide."""
