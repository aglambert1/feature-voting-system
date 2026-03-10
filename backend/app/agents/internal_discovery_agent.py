"""
Internal Discovery Agent.

This agent analyzes imported internal feedback data (sales win/loss records
and support tickets) to extract themes that can be synthesized with
competitive intelligence and customer feedback.

The agent identifies:
- Win/loss themes with competitor correlation
- Support ticket themes by category
- Feature keywords for semantic matching
"""

from typing import Dict, Any, Type, List

from pydantic import BaseModel

from app.agents.base_agent import BaseAgent
from app.schemas.internal_feedback import (
    InternalDiscoveryOutput,
    DealInput,
    SupportTicketInput
)


class InternalDiscoveryAgent(BaseAgent):
    """
    Analyzes internal feedback data to extract themes.

    Input:
        - deals: List of win/loss deal records
        - support_tickets: List of support ticket records

    Output:
        - winloss_themes: Grouped themes from deal data
        - support_themes: Grouped themes from ticket data
        - analysis_summary: Brief overview of findings

    Usage:
        agent = InternalDiscoveryAgent(db=db, llm_service=llm_service)
        result = agent.execute({
            'deals': [...],
            'support_tickets': [...]
        })
    """

    def get_stage(self) -> str:
        """Return the pipeline stage for this agent."""
        return "internal_discovery"

    def get_output_schema(self) -> Type[BaseModel]:
        """Return the Pydantic schema for output validation."""
        return InternalDiscoveryOutput

    def get_system_prompt(self) -> str:
        """Build system prompt with JSON output instructions."""
        return """You are a Product Intelligence Analyst specializing in extracting actionable themes from internal sales and support data.

Your task is to analyze win/loss deal records and support tickets to identify recurring themes that represent:
1. Features or capabilities mentioned in lost deals (especially when losing to competitors)
2. Features or capabilities that helped win deals
3. Common feature requests from support tickets
4. Pain points and bugs reported by customers

## Output Format

You MUST respond with a valid JSON object matching this exact structure:

```json
{
  "winloss_themes": [
    {
      "theme_name": "Clear, concise theme name (e.g., 'Time Tracking Capability')",
      "outcome": "lost",
      "competitor_correlation": "Competitor A",
      "deal_count": 3,
      "total_value": 205000,
      "sample_reasons": ["Quote 1", "Quote 2"],
      "feature_keywords": ["time tracking", "billable hours", "timesheet"],
      "jtbd_statement": "When [situation], I want to [motivation], so I can [outcome]"
    }
  ],
  "support_themes": [
    {
      "theme_name": "Clear, concise theme name",
      "category": "feature_request",
      "ticket_count": 47,
      "sample_subjects": ["Subject 1", "Subject 2"],
      "feature_keywords": ["export", "pdf", "reporting"],
      "urgency_indicator": "high",
      "jtbd_statement": "When [situation], I want to [motivation], so I can [outcome]"
    }
  ],
  "analysis_summary": "Brief 2-3 sentence summary of key findings",
  "deals_analyzed": 18,
  "tickets_analyzed": 15
}
```

## Theme Extraction Guidelines

### Win/Loss Themes:
1. Group similar reasons together (e.g., "time tracking", "billable hours", "timesheet" → "Time Tracking Capability")
2. Identify competitor correlation when a specific competitor is mentioned repeatedly
3. Calculate total deal value for each theme
4. Include 2-5 sample quotes from the original reasons
5. Generate 3-5 feature keywords that could match competitive features
6. Set outcome to "lost", "won", or "both" if theme appears in both

### Support Themes:
1. Group tickets by underlying feature or capability
2. Preserve the category (feature_request, bug, support, other)
3. Include 2-5 sample ticket subjects
4. Generate 3-5 feature keywords for matching
5. Set urgency: "high" (30+ tickets), "medium" (15-29), "low" (<15)

### Feature Keywords:
- Keywords should be specific enough for semantic matching
- Include synonyms and related terms
- Focus on the functional capability, not the problem description

### Jobs-to-be-Done (JTBD):
For each theme, extract the underlying customer job:
- Format: "When [situation/circumstance], I want to [motivation/action], so I can [expected outcome/benefit]"
- Focus on the UNDERLYING NEED, not the specific feature
- Example: Theme "Missing Time Tracking" → "When I'm managing billable client work, I want to track time spent on each project, so I can invoice accurately and monitor profitability."

## Important Guidelines

1. Focus on ACTIONABLE themes that represent product opportunities
2. Combine similar themes even if worded differently
3. Prioritize themes that appear in BOTH lost deals AND support tickets
4. Always generate feature keywords to enable synthesis with competitive data
5. Only output valid JSON - no explanatory text outside the JSON object"""

    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        """Build user prompt from imported data."""
        deals = input_data.get('deals', [])
        support_tickets = input_data.get('support_tickets', [])

        # Format deals section
        deals_section = self._format_deals(deals)

        # Format support tickets section
        tickets_section = self._format_tickets(support_tickets)

        prompt = f"""# Internal Feedback Analysis Request

## Deal Records ({len(deals)} total)

{deals_section}

## Support Tickets ({len(support_tickets)} total)

{tickets_section}

## Your Task

Analyze the above data and extract themes:

1. **Win/Loss Themes**: Group deal reasons into 5-10 themes. Focus on feature-related reasons, especially for lost deals.

2. **Support Themes**: Group support tickets into 5-10 themes. Focus on feature requests and recurring issues.

3. **Feature Keywords**: For each theme, generate keywords that could match features in competitive analysis.

4. **Summary**: Provide a brief summary highlighting the most critical gaps and opportunities.

Respond with ONLY a valid JSON object following the schema in the system prompt."""

        return prompt

    def _format_deals(self, deals: List[Dict[str, Any]]) -> str:
        """Format deal records for the prompt."""
        if not deals:
            return "No deal records provided."

        lines = []
        lost_deals = [d for d in deals if d.get('outcome') == 'lost']
        won_deals = [d for d in deals if d.get('outcome') == 'won']

        lines.append(f"**Lost Deals: {len(lost_deals)}**")
        for deal in lost_deals:
            competitor = deal.get('competitor_name', 'Unknown')
            value = deal.get('deal_value', 0)
            reason = deal.get('reason', 'No reason provided')
            notes = deal.get('notes', '')
            lines.append(f"- [{competitor}] ${value:,.0f} - {reason}")
            if notes:
                lines.append(f"  Notes: {notes[:200]}")

        lines.append(f"\n**Won Deals: {len(won_deals)}**")
        for deal in won_deals:
            competitor = deal.get('competitor_name', 'N/A')
            value = deal.get('deal_value', 0)
            reason = deal.get('reason', 'No reason provided')
            lines.append(f"- [vs {competitor}] ${value:,.0f} - {reason}")

        return "\n".join(lines)

    def _format_tickets(self, tickets: List[Dict[str, Any]]) -> str:
        """Format support tickets for the prompt."""
        if not tickets:
            return "No support tickets provided."

        lines = []

        # Group by category
        by_category = {}
        for ticket in tickets:
            cat = ticket.get('category', 'other')
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(ticket)

        for category, cat_tickets in by_category.items():
            total_count = sum(t.get('ticket_count', 1) for t in cat_tickets)
            lines.append(f"\n**{category.replace('_', ' ').title()} ({total_count} tickets)**")

            for ticket in cat_tickets:
                subject = ticket.get('subject', 'No subject')
                count = ticket.get('ticket_count', 1)
                tags = ticket.get('tags', [])
                lines.append(f"- [{count}x] {subject}")
                if tags:
                    lines.append(f"  Tags: {', '.join(tags)}")

        return "\n".join(lines)

    def _validate_input(self, input_data: Dict[str, Any]) -> None:
        """Validate required input fields."""
        super()._validate_input(input_data)

        deals = input_data.get('deals', [])
        tickets = input_data.get('support_tickets', [])

        if not deals and not tickets:
            raise ValueError("At least one deal or support ticket is required")
