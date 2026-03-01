"""
Landscape Opportunity Synthesizer Agent.

This agent synthesizes multiple competitor functional audits into a
comprehensive market landscape analysis, identifying opportunities
for product development.

The agent uses an external prompt template (Landscape_Opportunity_Synthesizer_Prompt.md)
for flexibility in production environments.
"""

from typing import Dict, Any, Type, List

from pydantic import BaseModel

from app.agents.base_agent import BaseAgent
from app.schemas.competitive_reports import (
    LandscapeSynthesisOutput,
    FunctionalAuditOutput
)
from app.services.prompt_loader import get_prompt_loader


class LandscapeOpportunitySynthesizerAgent(BaseAgent):
    """
    Cross-competitor landscape synthesis agent.

    Aggregates multiple competitor functional audits to produce:
    - Feature cluster matrix (prevalence across landscape)
    - Feature opportunities (JSON export for voting systems)
    - High-impact gaps (top features with market gravity)

    Usage:
        agent = LandscapeOpportunitySynthesizerAgent(db=db, llm_service=llm_service)
        result = agent.execute({
            'product_context': {...},  # Our product info
            'competitor_reports': [  # List of FunctionalAuditOutput dicts
                {'competitor_name': 'Acme', 'audit': {...}},
                {'competitor_name': 'Beta', 'audit': {...}},
            ]
        })
    """

    PROMPT_FILENAME = "Landscape_Opportunity_Synthesizer_Prompt.md"

    def get_stage(self) -> str:
        """Return the pipeline stage for this agent."""
        return "landscape_synthesis"

    def get_output_schema(self) -> Type[BaseModel]:
        """Return the Pydantic schema for output validation."""
        return LandscapeSynthesisOutput

    def get_system_prompt(self) -> str:
        """
        Build system prompt with JSON output instructions.

        The role and task context come from the external prompt template.
        We append JSON formatting instructions here.
        """
        return """You are a Principal Product Strategist specializing in competitive landscape analysis.

Your task is to synthesize individual competitor functional audits into a market-wide
"Opportunity Map" that identifies where the market is moving and where the greatest
opportunities exist.

## Output Format

You MUST respond with a valid JSON object matching this exact structure:

```json
{
  "feature_cluster_matrix": [
    {
      "feature_category": "Feature or category name",
      "prevalence": "Table Stakes",
      "our_status": "Gap",
      "competitors_with_feature": ["Competitor A", "Competitor B"],
      "notes": "Optional notes"
    }
  ],
  "feature_opportunities": [
    {
      "feature_name": "Concise feature name",
      "summary": "1-2 sentence description",
      "user_value": "Primary benefit to customer",
      "market_context": "Which competitors have it, Table Stakes vs Innovation",
      "priority_score": 0.85,
      "competitors_with_feature": ["Competitor A"],
      "source_evidence": ["Competitor Name (source type): Evidence quote or description"]
    }
  ],
  "high_impact_gaps": [
    {
      "rank": 1,
      "feature_name": "Feature name",
      "market_gravity": "Why this has high market importance",
      "competitors_with_feature": ["Competitor A", "Competitor B"],
      "user_demand_evidence": "Evidence of user demand"
    }
  ],
  "innovation_whitespace": "Persistent unsolved problem found across competitors",
  "analysis_summary": "Brief summary of the landscape analysis"
}
```

## Prevalence Definitions

- **Table Stakes**: 80%+ of competitors have this feature
- **Common**: 50-79% of competitors have this feature
- **Emerging**: 25-49% of competitors have this feature
- **Frontier**: Less than 25% of competitors (1-2 only)

## Our Status Definitions

- **Have**: We have this feature fully implemented
- **Gap**: We don't have this feature
- **Partial**: We have partial implementation

## Source Evidence Format

Each entry in `source_evidence` MUST include attribution in this format:
  "Competitor Name (source type): evidence description or quote"

Where source type is one of: product documentation, user reviews, feature page, pricing page, API docs, marketing site, or other descriptive label.

Example: "Coupa (product documentation): Self-service portal where suppliers manage profiles, view POs, submit invoices"

## Important Guidelines

1. Analyze patterns across ALL competitor reports provided
2. Prioritize features by market gravity (demand + competition)
3. Include attributed evidence for each opportunity (see Source Evidence Format above)
4. Identify the "Innovation Whitespace" - unsolved problems across all competitors
5. Generate 5-15 feature opportunities, prioritized by importance
6. Rank top 3-5 high-impact gaps
7. Only output valid JSON - no explanatory text outside the JSON object"""

    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        """
        Build the user prompt with aggregated competitor data.

        Args:
            input_data: Must contain:
                - product_context: Dict with our product info
                - competitor_reports: List of dicts with competitor_name and audit data
        """
        product_context = input_data.get('product_context', {})
        competitor_reports = input_data.get('competitor_reports', [])

        # Format product context
        product_info = self._format_product_context(product_context)

        # Format aggregated competitor reports
        competitor_info = self._format_competitor_reports(competitor_reports)

        # Count competitors
        competitor_count = len(competitor_reports)

        # Try to load external prompt template for additional context
        prompt_loader = get_prompt_loader()
        try:
            external_prompt = prompt_loader.load_prompt(self.PROMPT_FILENAME)
            task_context = self._extract_task_context(external_prompt)
        except FileNotFoundError:
            task_context = ""

        prompt = f"""# Landscape Opportunity Synthesis Request

## Our Product Context
{product_info}

## Number of Competitors Analyzed: {competitor_count}

## Individual Competitor Audits
{competitor_info}

{task_context}

## Your Task

Synthesize these {competitor_count} competitor audits into a comprehensive landscape analysis.
Identify:
1. **Table Stakes** features (80%+ of competitors have)
2. **Emerging trends** (Frontier features only 1-2 competitors have)
3. **Innovation whitespace** (unsolved problems across competitors)
4. **Prioritized opportunities** for our product roadmap

Focus on features where we have GAPS - these are the opportunities.
Provide evidence-based reasoning for prioritization.

Respond with ONLY a valid JSON object following the schema in the system prompt."""

        return prompt

    def _format_product_context(self, product_context: Dict[str, Any]) -> str:
        """Format our product context for the prompt."""
        if not product_context:
            return "No product context provided."

        parts = []

        if product_context.get('product_name'):
            parts.append(f"**Product Name:** {product_context['product_name']}")

        if product_context.get('product_category'):
            parts.append(f"**Category:** {product_context['product_category']}")

        if product_context.get('core_features'):
            features = product_context['core_features']
            if isinstance(features, list):
                feature_list = "\n".join(f"  - {f}" for f in features[:15])
                parts.append(f"**Our Core Features:**\n{feature_list}")

        if product_context.get('target_users'):
            parts.append(f"**Target Users:** {product_context['target_users']}")

        return "\n".join(parts) if parts else "No product context provided."

    def _format_competitor_reports(self, reports: List[Dict[str, Any]]) -> str:
        """
        Format competitor audit reports for the prompt.

        Each report should have:
        - competitor_name: str
        - audit: FunctionalAuditOutput dict or similar structure
        """
        if not reports:
            return "No competitor reports provided."

        formatted_reports = []

        for i, report in enumerate(reports, 1):
            competitor_name = report.get('competitor_name', f'Competitor {i}')
            audit = report.get('audit', {})

            lines = [
                f"### {competitor_name}",
                "",
            ]

            # Competitor context summary
            context = audit.get('competitor_context', {})
            if context:
                if context.get('positioning'):
                    lines.append(f"**Positioning:** {context['positioning']}")
                if context.get('core_differentiation'):
                    lines.append(f"**Differentiation:** {context['core_differentiation']}")
                if context.get('target_customer'):
                    lines.append(f"**Target Customer:** {context['target_customer']}")
                lines.append("")

            # Feature comparison summary (focus on gaps)
            comparisons = audit.get('functional_comparison', [])
            if comparisons:
                gaps = [c for c in comparisons if c.get('mapping_status') == 'Gap']
                advantages = [c for c in comparisons if c.get('mapping_status') == 'Advantage']
                parity = [c for c in comparisons if c.get('mapping_status') == 'Parity']
                differentiators = [c for c in comparisons if c.get('mapping_status') == 'Differentiator']

                lines.append(f"**Feature Summary:** {len(comparisons)} features analyzed")
                lines.append(f"- Parity: {len(parity)}")
                lines.append(f"- Gaps (they have, we don't): {len(gaps)}")
                lines.append(f"- Advantages (we have, they don't): {len(advantages)}")
                lines.append(f"- Differentiators: {len(differentiators)}")
                lines.append("")

                # List gap features
                if gaps:
                    lines.append("**Gap Features:**")
                    for gap in gaps[:10]:  # Limit to 10
                        lines.append(f"- {gap.get('competitor_feature_name', 'Unknown')}: {gap.get('functional_description', '')[:100]}")
                    if len(gaps) > 10:
                        lines.append(f"- ... and {len(gaps) - 10} more")
                    lines.append("")

            # Gaps deep-dive summary
            gaps_deep_dive = audit.get('gaps_deep_dive', [])
            if gaps_deep_dive:
                lines.append("**Gap Deep-Dive:**")
                for gap in gaps_deep_dive[:5]:
                    lines.append(f"- **{gap.get('feature_name', 'Unknown')}**: {gap.get('user_problem', '')[:150]}")
                lines.append("")

            formatted_reports.append("\n".join(lines))

        return "\n---\n".join(formatted_reports)

    def _extract_task_context(self, external_prompt: str) -> str:
        """
        Extract task context from external prompt template.

        This extracts the instructions section to supplement the user prompt.
        """
        if "# Instructions" in external_prompt:
            start = external_prompt.find("# Instructions")
            next_section = external_prompt.find("\n# ", start + 1)
            if next_section > start:
                return external_prompt[start:next_section].strip()
            return external_prompt[start:].strip()

        return ""

    def _validate_input(self, input_data: Dict[str, Any]) -> None:
        """Validate required input fields."""
        super()._validate_input(input_data)

        competitor_reports = input_data.get('competitor_reports', [])
        if not competitor_reports:
            raise ValueError("competitor_reports is required and cannot be empty")

        if len(competitor_reports) < 1:
            raise ValueError("At least one competitor report is required")


def generate_markdown_report(
    product_name: str,
    output: LandscapeSynthesisOutput,
    competitor_count: int
) -> str:
    """
    Generate a markdown report from the agent output.

    Args:
        product_name: Name of our product
        output: Validated LandscapeSynthesisOutput
        competitor_count: Number of competitors analyzed

    Returns:
        Formatted markdown string
    """
    lines = [
        f"# Landscape Opportunity Analysis: {product_name}",
        "",
        f"*Analysis based on {competitor_count} competitors*",
        "",
    ]

    if output.analysis_summary:
        lines.extend([
            "## Executive Summary",
            "",
            output.analysis_summary,
            "",
        ])

    lines.extend([
        "## 1. Feature Cluster Matrix",
        "",
        "| Feature | Prevalence | Our Status | Competitors |",
        "|---------|------------|------------|-------------|",
    ])

    for entry in output.feature_cluster_matrix:
        competitors = ", ".join(entry.competitors_with_feature[:3])
        if len(entry.competitors_with_feature) > 3:
            competitors += f" +{len(entry.competitors_with_feature) - 3}"
        lines.append(
            f"| {entry.feature_category} | {entry.prevalence} | "
            f"**{entry.our_status}** | {competitors} |"
        )

    lines.extend(["", "## 2. Feature Opportunities", ""])

    for opp in output.feature_opportunities:
        lines.extend([
            f"### {opp.feature_name}",
            "",
            f"**Summary:** {opp.summary}",
            "",
            f"**User Value:** {opp.user_value}",
            "",
            f"**Market Context:** {opp.market_context}",
            "",
        ])
        if opp.priority_score is not None:
            lines.append(f"**Priority Score:** {opp.priority_score:.2f}")
            lines.append("")
        if opp.competitors_with_feature:
            lines.append(f"**Competitors:** {', '.join(opp.competitors_with_feature)}")
            lines.append("")
        if opp.source_evidence:
            lines.append("**Evidence:**")
            for evidence in opp.source_evidence[:3]:
                lines.append(f"> {evidence}")
            lines.append("")

    lines.extend(["## 3. High-Impact Gaps", ""])

    if output.high_impact_gaps:
        for gap in output.high_impact_gaps:
            lines.extend([
                f"### #{gap.rank}: {gap.feature_name}",
                "",
                f"**Market Gravity:** {gap.market_gravity}",
                "",
                f"**Competitors:** {', '.join(gap.competitors_with_feature)}",
                "",
                f"**User Demand Evidence:** {gap.user_demand_evidence}",
                "",
            ])
    else:
        lines.append("*No high-impact gaps identified.*")
        lines.append("")

    if output.innovation_whitespace:
        lines.extend([
            "## Innovation Whitespace",
            "",
            output.innovation_whitespace,
            "",
        ])

    return "\n".join(lines)
