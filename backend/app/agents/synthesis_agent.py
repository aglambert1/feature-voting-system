"""
Opportunity Synthesis Agent.

This agent analyzes the intersection of up to four data sources to identify
prioritized product opportunities:
1. Competitive intelligence (features from landscape analysis)
2. Customer feedback (highly voted ideas)
3. Internal feedback (win/loss themes and support themes)
4. Evidence/research (factbase evidence: market signals, interviews, research, etc.)

Internal feedback comes from two sub-sources, merged by InternalThemeMergerService:
- Structured: Direct win/loss reasons and support ticket categories
- Activity: CRM activity streams (call notes, emails, meeting logs)

When both structured and activity sources agree on a theme, confidence is "high".
This represents validated internal evidence.

Evidence/research uses hybrid routing:
- Competitive-typed evidence enriches competitive intelligence input
- Non-competitive evidence (interviews, research, market signals) is a 4th source

The agent identifies:
- Four-way matches (critical - validated across all sources)
- Three-way matches (highest priority - validated across three sources)
- Two-way matches (moderate priority - corroborated by two sources)
- Single-source highlights (notable signals from one source)
"""

from typing import Dict, Any, Type, List, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.base_agent import BaseAgent
from app.schemas.synthesis import OpportunitySynthesisOutput
from app.services.scoring_defaults import (
    DEFAULT_SCORING_WEIGHTS,
    format_scoring_prompt,
)


class OpportunitySynthesisAgent(BaseAgent):
    """
    Synthesizes opportunities from competitive, customer, and internal sources.

    Input:
        - competitive_opportunities: Features from landscape analysis
        - customer_ideas: Top-voted ideas from the voting system
        - winloss_themes: Themes extracted from win/loss data
        - support_themes: Themes extracted from support tickets

    Output:
        - opportunities: Prioritized list of synthesized opportunities
        - analysis_summary: Overview of key findings
        - source_stats: Statistics about source usage

    Usage:
        agent = OpportunitySynthesisAgent(
            db=db, llm_service=llm_service,
            scoring_weights=weights  # optional, defaults to DEFAULT_SCORING_WEIGHTS
        )
        result = agent.execute({
            'competitive_opportunities': [...],
            'customer_ideas': [...],
            'winloss_themes': [...],
            'support_themes': [...]
        })
    """

    def __init__(self, scoring_weights: Optional[dict] = None, **kwargs):
        super().__init__(**kwargs)
        self.scoring_weights = scoring_weights or DEFAULT_SCORING_WEIGHTS

    def get_stage(self) -> str:
        """Return the pipeline stage for this agent."""
        return "opportunity_synthesis"

    def get_output_schema(self) -> Type[BaseModel]:
        """Return the Pydantic schema for output validation."""
        return OpportunitySynthesisOutput

    def get_system_prompt(self) -> str:
        """Build system prompt with dynamic scoring weights."""
        scoring_section = format_scoring_prompt(self.scoring_weights)

        return (
            """You are a Product Intelligence Synthesizer specializing in identifying high-value product opportunities by analyzing the intersection of multiple data sources.

Your task is to synthesize insights from up to four data sources:
1. **Competitive Intelligence**: Features competitors have that represent gaps in the product (may include enriching factbase evidence about competitors)
2. **Customer Feedback**: Ideas submitted and voted on by customers
3. **Internal Feedback**: Themes from sales win/loss data and support tickets
4. **Evidence/Research**: Factbase evidence including customer interviews, market signals, research notes, and analyst reports

## Your Objective

Find opportunities where multiple sources AGREE. The highest-priority opportunities are those validated by multiple independent signals:
- **Four-way match**: All sources agree = Critical priority (strongest signal)
- **Three-way match**: Three sources agree = High priority
- **Two-way match**: Any two sources agree = Moderate priority
- **Single source**: Strong signal from one source = Worth noting

## Output Format

You MUST respond with a valid JSON object matching this exact structure:

```json
{
  "opportunities": [
    {
      "opportunity_name": "Clear, actionable name (e.g., 'Time Tracking Integration')",
      "opportunity_summary": "Brief explanation of why this opportunity is valuable and urgent",
      "priority_score": 85,
      "source_count": 3,
      "sources": ["competitive", "customer", "internal", "evidence_research"],
      "competitive_evidence": {
        "feature_name": "Time Tracking",
        "prevalence": "Table Stakes",
        "competitors": ["Competitor A", "Competitor B"],
        "competitor_count": 4,
        "our_status": "Gap",
        "priority_score": 78
      },
      "customer_evidence": {
        "idea_id": 42,
        "idea_title": "Add time tracking feature",
        "vote_count": 85,
        "status": "under_review"
      },
      "internal_evidence": {
        "winloss": {
          "theme_id": 5,
          "theme_name": "Time Tracking Capability",
          "outcome": "lost",
          "deal_count": 8,
          "total_value": 340000,
          "competitor_correlation": "Competitor A"
        },
        "support": {
          "theme_id": 12,
          "theme_name": "Time Tracking Requests",
          "ticket_count": 23,
          "category": "feature_request",
          "urgency_indicator": "high"
        }
      },
      "evidence_signals": {
        "items": [
          {
            "evidence_id": 7,
            "title": "Customer interview - Acme Corp needs time tracking",
            "evidence_type": "customer_interview",
            "source_url": null,
            "source_description": "Customer interview - Acme Corp",
            "relevance": "Direct customer request for time tracking during sales call"
          }
        ]
      },
      "recommended_action": "high_priority",
      "feature_keywords": ["time tracking", "billable hours", "timesheet"],
      "jtbd_statement": "When [situation], I want to [motivation], so I can [outcome]"
    }
  ],
  "analysis_summary": "2-3 sentence summary of the most critical findings",
  "source_stats": {
    "competitive_opportunities_analyzed": 12,
    "customer_ideas_analyzed": 45,
    "winloss_themes_analyzed": 8,
    "support_themes_analyzed": 10,
    "evidence_items_analyzed": 6,
    "four_way_matches": 1,
    "three_way_matches": 2,
    "two_way_matches": 5,
    "single_source": 8
  }
}
```

"""
            + scoring_section
            + """

## Internal Feedback Confidence Levels

Internal themes may have different confidence levels:
- **High confidence**: Theme appears in BOTH structured data (CRM reasons) AND activity analysis (call notes, emails). This is the strongest internal signal.
- **Medium confidence**: Theme appears in only one internal source. Still valuable but single-validated.

When an internal theme has "high" confidence, it means multiple independent signals within your organization confirm this issue. Prioritize these themes.

## Jobs-to-be-Done Synthesis

For each opportunity, synthesize a unified JTBD statement capturing the underlying customer job across all contributing sources.
- Format: "When [situation], I want to [motivation], so I can [outcome]"
- If competitive features, customer ideas, and internal themes all point to the same need, the JTBD should capture that converged need
- Focus on the UNDERLYING customer job, not the specific feature implementation

## Matching Guidelines

Use SEMANTIC matching, not exact string matching:
- "Time Tracking" ≈ "Timesheet" ≈ "Billable Hours" ≈ "Time Entry"
- "API" ≈ "Integration" ≈ "REST API" ≈ "Developer Tools"
- "Export" ≈ "PDF Export" ≈ "Reporting" ≈ "Data Export"

Match based on the underlying CAPABILITY, not specific wording.

## Recommended Actions

- **high_priority**: 3-way match OR 2-way match with high scores
- **investigate**: Strong single signal that needs validation
- **monitor**: Worth tracking but not immediately actionable
- **quick_win**: Low effort, moderate signal (customer votes but no competitor pressure)

## Important Rules

1. DO NOT create duplicate opportunities - consolidate similar signals
2. Include ALL relevant evidence - if internal has both winloss AND support, include both
3. Set evidence fields to null if that source has no relevant signal
4. For evidence_signals, include matching items with their evidence_id, title, evidence_type, source_url, source_description, and a brief relevance explanation
5. Sort opportunities by priority_score descending
6. Limit to top 15 opportunities maximum
7. Only output valid JSON - no explanatory text outside the JSON object"""
        )

    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        """Build user prompt from up to four data sources."""
        competitive = input_data.get('competitive_opportunities', [])
        ideas = input_data.get('customer_ideas', [])
        winloss = input_data.get('winloss_themes', [])
        support = input_data.get('support_themes', [])
        research_signals = input_data.get('research_signals', [])

        # Format each section
        competitive_section = self._format_competitive(competitive)
        ideas_section = self._format_ideas(ideas)
        winloss_section = self._format_winloss(winloss)
        support_section = self._format_support(support)
        research_section = self._format_research(research_signals)

        prompt = f"""# Opportunity Synthesis Request

## Source Data Summary

- Competitive Opportunities: {len(competitive)} items
- Customer Ideas: {len(ideas)} items
- Win/Loss Themes: {len(winloss)} items
- Support Themes: {len(support)} items
- Evidence/Research: {len(research_signals)} items

---

## Source 1: Competitive Intelligence

{competitive_section}

---

## Source 2: Customer Feedback (Voted Ideas)

{ideas_section}

---

## Source 3: Internal Feedback - Win/Loss Themes

{winloss_section}

---

## Source 4: Internal Feedback - Support Themes

{support_section}

---

## Source 5: Evidence/Research (Factbase)

{research_section}

---

## Your Task

1. **Identify intersections**: Find opportunities where 2+ sources point to the same underlying need
2. **Calculate priorities**: Score each opportunity based on signal strength and source count
3. **Include evidence**: For each opportunity, include specific evidence from each contributing source (including evidence_signals when relevant)
4. **Summarize findings**: Provide a brief analysis summary highlighting the most critical gaps

Focus on SEMANTIC matching - look for opportunities addressing the same underlying capability, even if worded differently.

Respond with ONLY a valid JSON object following the schema in the system prompt."""

        return prompt

    def _format_competitive(self, opportunities: List[Dict[str, Any]]) -> str:
        """Format competitive opportunities for the prompt."""
        if not opportunities:
            return "No competitive opportunities available."

        lines = []
        for opp in opportunities:
            name = opp.get('feature_name', opp.get('name', 'Unknown'))
            prevalence = opp.get('prevalence', 'Unknown')
            our_status = opp.get('our_status', 'Unknown')
            competitors = opp.get('competitors_with_feature', opp.get('competitors', []))
            priority = opp.get('priority_score', 0)

            lines.append(f"**{name}**")
            lines.append(f"  - Prevalence: {prevalence} ({len(competitors)} competitors)")
            lines.append(f"  - Our Status: {our_status}")
            lines.append(f"  - Priority Score: {priority}")
            if competitors:
                lines.append(f"  - Competitors: {', '.join(competitors[:5])}")
            lines.append("")

        return "\n".join(lines)

    def _format_ideas(self, ideas: List[Dict[str, Any]]) -> str:
        """Format customer ideas for the prompt."""
        if not ideas:
            return "No customer ideas available."

        lines = []
        for idea in sorted(ideas, key=lambda x: x.get('vote_count', 0), reverse=True):
            idea_id = idea.get('id', 0)
            title = idea.get('title', 'Unknown')
            votes = idea.get('vote_count', 0)
            status = idea.get('status', 'unknown')
            description = idea.get('description', '')

            lines.append(f"**[ID:{idea_id}] {title}** ({votes} votes)")
            lines.append(f"  - Status: {status}")
            if description:
                lines.append(f"  - Description: {description[:200]}...")
            lines.append("")

        return "\n".join(lines)

    def _format_winloss(self, themes: List[Dict[str, Any]]) -> str:
        """Format win/loss themes for the prompt.

        Themes now come from merged sources (structured + activity) and include:
        - sources: List of ["structured", "activity"] indicating where theme was found
        - confidence: "high" if both sources agree, "medium" otherwise
        - sample_quotes: Verbatim customer voice from activity analysis
        """
        if not themes:
            return "No win/loss themes available."

        lines = []
        # Group by outcome
        lost_themes = [t for t in themes if t.get('outcome') == 'lost']
        won_themes = [t for t in themes if t.get('outcome') == 'won']

        if lost_themes:
            # Sort by confidence (high first) then by deal count
            lost_themes = sorted(
                lost_themes,
                key=lambda x: (0 if x.get('confidence') == 'high' else 1, -x.get('deal_count', 0))
            )
            lines.append("**Lost Deal Themes:**")
            for theme in lost_themes:
                name = theme.get('theme_name', 'Unknown')
                deal_count = theme.get('deal_count', 0)
                total_value = theme.get('total_value', 0)
                competitor = theme.get('competitor_name', theme.get('competitor_correlation'))
                keywords = theme.get('feature_keywords', [])
                confidence = theme.get('confidence', 'medium')
                sources = theme.get('sources', [])
                sample_quotes = theme.get('sample_quotes', [])

                confidence_indicator = "★ HIGH CONFIDENCE" if confidence == 'high' else "MEDIUM"
                source_str = " + ".join(sources) if sources else "unknown"

                lines.append(f"  - **{name}** [{confidence_indicator}]")
                lines.append(f"    Sources: {source_str}")
                lines.append(f"    Deals: {deal_count}, Value: ${total_value:,.0f}")
                if competitor:
                    lines.append(f"    Competitor: {competitor}")
                if keywords:
                    lines.append(f"    Keywords: {', '.join(keywords[:5])}")
                if sample_quotes:
                    lines.append(f"    Customer Voice: \"{sample_quotes[0][:150]}...\"")
            lines.append("")

        if won_themes:
            won_themes = sorted(
                won_themes,
                key=lambda x: (0 if x.get('confidence') == 'high' else 1, -x.get('deal_count', 0))
            )
            lines.append("**Won Deal Themes (Differentiators):**")
            for theme in won_themes:
                name = theme.get('theme_name', 'Unknown')
                deal_count = theme.get('deal_count', 0)
                total_value = theme.get('total_value', 0)
                confidence = theme.get('confidence', 'medium')
                sources = theme.get('sources', [])

                confidence_indicator = "★" if confidence == 'high' else ""
                source_str = " + ".join(sources) if sources else "unknown"

                lines.append(f"  - **{name}** {confidence_indicator}")
                lines.append(f"    Sources: {source_str}, Deals: {deal_count}, Value: ${total_value:,.0f}")
            lines.append("")

        return "\n".join(lines) if lines else "No win/loss themes available."

    def _format_support(self, themes: List[Dict[str, Any]]) -> str:
        """Format support themes for the prompt.

        Themes now come from merged sources (structured + activity) and include:
        - sources: List of ["structured", "activity"] indicating where theme was found
        - confidence: "high" if both sources agree, "medium" otherwise
        - sample_quotes: Verbatim customer voice from activity analysis
        - accounts_affected: List of account names affected
        """
        if not themes:
            return "No support themes available."

        lines = []
        # Group by category
        by_category = {}
        for theme in themes:
            cat = theme.get('category', 'other')
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(theme)

        for category, cat_themes in by_category.items():
            lines.append(f"**{category.replace('_', ' ').title()}:**")
            # Sort by confidence first, then by ticket count
            sorted_themes = sorted(
                cat_themes,
                key=lambda x: (0 if x.get('confidence') == 'high' else 1, -x.get('ticket_count', 0))
            )
            for theme in sorted_themes:
                name = theme.get('theme_name', 'Unknown')
                ticket_count = theme.get('ticket_count', 0)
                urgency = theme.get('urgency_level', theme.get('urgency_indicator', 'medium'))
                keywords = theme.get('feature_keywords', [])
                confidence = theme.get('confidence', 'medium')
                sources = theme.get('sources', [])
                sample_quotes = theme.get('sample_quotes', [])
                accounts = theme.get('accounts_affected', [])

                confidence_indicator = "★ HIGH CONFIDENCE" if confidence == 'high' else "MEDIUM"
                source_str = " + ".join(sources) if sources else "unknown"

                lines.append(f"  - **{name}** ({ticket_count} tickets) [{confidence_indicator}]")
                lines.append(f"    Sources: {source_str}, Urgency: {urgency}")
                if keywords:
                    lines.append(f"    Keywords: {', '.join(keywords[:5])}")
                if sample_quotes:
                    lines.append(f"    Customer Voice: \"{sample_quotes[0][:150]}...\"")
                if accounts:
                    lines.append(f"    Accounts Affected: {', '.join(accounts[:3])}")
            lines.append("")

        return "\n".join(lines) if lines else "No support themes available."

    def _format_research(self, evidence_items: List[Dict[str, Any]]) -> str:
        """Format evidence/research items from the factbase for the prompt."""
        if not evidence_items:
            return "No evidence/research available."

        lines = []
        for item in evidence_items:
            title = item.get('title', 'Unknown')
            ev_type = item.get('evidence_type', 'unknown')
            content = item.get('content', '')
            source_url = item.get('source_url', '')
            source_desc = item.get('source_description', '')
            jtbd = item.get('jtbd_statement', '')
            ev_id = item.get('id', item.get('evidence_id', 0))

            lines.append(f"**[ID:{ev_id}] {title}** (type: {ev_type})")
            if source_desc:
                lines.append(f"  - Source: {source_desc}")
            if source_url:
                lines.append(f"  - URL: {source_url}")
            if content:
                lines.append(f"  - Content: {content[:300]}...")
            if jtbd:
                lines.append(f"  - JTBD: {jtbd}")
            lines.append("")

        return "\n".join(lines)

    def _validate_input(self, input_data: Dict[str, Any]) -> None:
        """Validate required input fields."""
        super()._validate_input(input_data)

        # Check that at least one source has data
        competitive = input_data.get('competitive_opportunities', [])
        ideas = input_data.get('customer_ideas', [])
        winloss = input_data.get('winloss_themes', [])
        support = input_data.get('support_themes', [])
        research = input_data.get('research_signals', [])

        if not any([competitive, ideas, winloss, support, research]):
            raise ValueError("At least one data source must be provided for synthesis")
