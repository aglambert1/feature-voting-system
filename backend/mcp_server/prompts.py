"""MCP Prompts for Feature-IQ."""

from mcp_server import mcp


@mcp.prompt()
def weekly_update(product_id: int) -> str:
    """Generate a weekly competitive and customer feedback update."""
    return f"""Generate a weekly competitive and customer feedback update for product {product_id}.

Steps:
1. Use ci_get_alerts to check for recent competitive changes
2. Use ideas_get_top_voted to see what customers care about most
3. Use synthesis_get_unified_report to get prioritized opportunities (the `opportunities` section)

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


@mcp.prompt()
def empathy_validation_gate(product_id: int) -> str:
    """Walk the Discovery-stage empathy validation gate: review synthesized customer signals against the PM's direct customer knowledge."""
    return f"""Prepare the empathy validation gate for product {product_id}. This gate asks the PM: "Does this synthesis match my direct experience of these customers as people with real problems?"

Steps:
1. Use internal_get_signals and ideas_get_top_voted to pull the strongest customer signals, and evidence_list for recent factbase evidence
2. Use synthesis_get_sources to check fact-base freshness — flag any stale sources explicitly
3. Present the synthesized picture organized by customer problem / JTBD, with source links for every claim
4. Surface gaps: segments with thin evidence, themes resting on few data points, signals without a home in the job map

Then STOP and ask the PM directly:
- Which of these synthesized problems match what you hear from customers first-hand?
- What do you know from direct customer conversations that this synthesis misses or gets wrong?

Do NOT let the gate pass on agent output alone — the PM must add independent customer knowledge. If the PM can only cite the synthesis itself, say so and recommend customer contact before the gate passes."""


@mcp.prompt()
def prioritization_gate(product_id: int) -> str:
    """Walk the Prioritization-stage gate: present scored opportunities and tradeoffs, then elicit and record the PM's decision and reasoning."""
    return f"""Prepare the prioritization gate for product {product_id}. This gate asks the PM: "Can I defend this prioritization — and am I willing to hold it under pressure?"

Steps:
1. Use synthesis_get_investment_recommendations and synthesis_get_job_scorecard to pull the current scored opportunities
2. Use synthesis_get_sources to verify the synthesis isn't stale — if synthesis_stale is true, say so prominently before presenting anything
3. Present the top opportunities with: the evidence behind each, the jobs they serve, and the explicit tradeoffs (choosing X implies not doing Y)
4. Note assumptions that, if wrong, would change the ranking

Then STOP and elicit the PM's decision:
- Which opportunities are you committing to, in what order?
- What is your reasoning, and what did you trade off?
- What would cause you to reprioritize?

Echo the PM's decision and reasoning back VERBATIM as a decision record they can save. Do not synthesize or improve their reasoning — the decision log is PM-authored."""
