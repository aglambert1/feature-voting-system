"""
Activity Insight Agent.

This agent analyzes CRM activity data (call notes, emails, meeting notes)
to extract product-relevant themes from conversational/unstructured content.

Unlike the InternalDiscoveryAgent which processes structured win/loss reasons,
this agent processes the raw activity streams to find:
- Authentic customer voice (verbatim quotes)
- Implicit feature requests hidden in conversations
- Themes correlated with deal outcomes
- Support issues that indicate product gaps

Two-phase analysis:
1. Per-deal analysis: Extract themes from each deal's activities, correlated to outcome
2. Aggregate analysis: Cluster themes across all deals and support activities
"""

from typing import Dict, Any, Type, List, Optional

from pydantic import BaseModel, Field

from app.agents.base_agent import BaseAgent


class DealInsightSchema(BaseModel):
    """Schema for a single deal insight."""
    deal_id: Optional[str] = None
    deal_name: Optional[str] = None
    deal_outcome: str = "unknown"
    deal_value: Optional[float] = None
    competitor_mentioned: Optional[str] = None
    theme_name: str
    category: str = "feature_gap"
    sentiment: str = "neutral"
    urgency_level: str = "medium"
    sample_quotes: List[str] = Field(default_factory=list)
    activity_count: int = 1
    feature_keywords: List[str] = Field(default_factory=list)


class SupportInsightSchema(BaseModel):
    """Schema for an aggregated support insight."""
    theme_name: str
    category: str = "feature_gap"
    ticket_count: int = 0
    urgency_level: str = "medium"
    sample_quotes: List[str] = Field(default_factory=list)
    accounts_affected: List[str] = Field(default_factory=list)
    feature_keywords: List[str] = Field(default_factory=list)


class ActivityInsightOutput(BaseModel):
    """Output schema for ActivityInsightAgent."""
    deal_insights: List[DealInsightSchema] = Field(default_factory=list)
    support_insights: List[SupportInsightSchema] = Field(default_factory=list)
    deals_analyzed: int = 0
    activities_analyzed: int = 0
    top_loss_themes: List[str] = Field(default_factory=list)
    top_win_themes: List[str] = Field(default_factory=list)
    competitor_patterns: Dict[str, List[str]] = Field(default_factory=dict)
    analysis_summary: str = ""


class ActivityInsightAgent(BaseAgent):
    """
    Analyzes CRM activity data to extract product insights.

    Input:
        - deals: List of deals with their activities
        - support_tickets: List of support tickets with their activities

    Output:
        - deal_insights: Per-deal themes with outcome correlation
        - support_insights: Aggregated support themes
        - top_loss_themes: Themes most correlated with deal losses
        - top_win_themes: Themes in won deals (differentiators)
        - analysis_summary: Overview of findings

    Usage:
        agent = ActivityInsightAgent(db=db, llm_service=llm_service)
        result = agent.execute(parsed_activity_data)
    """

    def get_stage(self) -> str:
        """Return the pipeline stage for this agent."""
        return "activity_insight"

    def get_output_schema(self) -> Type[BaseModel]:
        """Return the Pydantic schema for output validation."""
        return ActivityInsightOutput

    def get_system_prompt(self) -> str:
        """Build system prompt with JSON output instructions."""
        return """You are a Product Intelligence Analyst specializing in extracting actionable insights from CRM activity data.

Your task is to analyze customer interactions (call notes, emails, meeting notes) to identify product-relevant themes that may not be captured in structured CRM fields like "close reason". You are looking for:

1. **Feature gaps** - capabilities customers explicitly or implicitly requested
2. **UX friction** - usability issues or confusion mentioned in conversations
3. **Competitive pressure** - competitor mentions and comparisons
4. **Use case gaps** - workflows or scenarios the product doesn't support well
5. **Integration needs** - requests for connections with other tools

## Output Format

You MUST respond with a valid JSON object matching this exact structure:

```json
{
  "deal_insights": [
    {
      "deal_id": "deal-123",
      "deal_name": "Acme Corp",
      "deal_outcome": "lost",
      "deal_value": 50000,
      "competitor_mentioned": "Competitor X",
      "theme_name": "Salesforce Integration Gap",
      "category": "integration_need",
      "sentiment": "negative",
      "urgency_level": "high",
      "sample_quotes": [
        "We need native Salesforce sync, manual data entry is killing productivity",
        "Our team spends 2 hours per week on manual CRM updates"
      ],
      "activity_count": 3,
      "feature_keywords": ["salesforce", "crm integration", "sync", "automation"]
    }
  ],
  "support_insights": [
    {
      "theme_name": "Manual Export Workarounds",
      "category": "feature_gap",
      "ticket_count": 15,
      "urgency_level": "high",
      "sample_quotes": [
        "We've been manually exporting to Excel because there's no bulk export",
        "Can you add a way to export all records at once?"
      ],
      "accounts_affected": ["Beta Inc", "Gamma Corp"],
      "feature_keywords": ["export", "bulk export", "csv", "data extraction"]
    }
  ],
  "deals_analyzed": 10,
  "activities_analyzed": 45,
  "top_loss_themes": ["Salesforce Integration Gap", "Missing SSO"],
  "top_win_themes": ["Ease of Use", "Responsive Support"],
  "competitor_patterns": {
    "Competitor X": ["Better integrations", "Lower price"],
    "Competitor Y": ["More features"]
  },
  "analysis_summary": "Analysis of 10 deals and 45 activities reveals that integration gaps, particularly with Salesforce, are the primary driver of lost deals. Support conversations indicate significant demand for bulk export functionality."
}
```

## Analysis Guidelines

### Deal Activity Analysis (Per-Deal):
1. For each deal, analyze ALL activities together in context of the deal outcome
2. Extract themes that represent product-related topics discussed
3. Capture VERBATIM quotes - these are more valuable than paraphrasing
4. Look for urgency signals: frustrated language, escalation mentions, deadline pressure
5. Note competitor mentions and what was said about them
6. Categories: feature_gap, ux_friction, competitive_pressure, use_case_gap, integration_need
7. Sentiment: positive (praise), negative (complaint/concern), neutral (informational)
8. Urgency: high (explicit urgency, deal blocker), medium (concern), low (nice-to-have)

### Support Activity Analysis (Aggregate):
1. Group similar themes across all support tickets
2. Look for "hidden feature requests" - tickets about bugs or confusion that indicate product gaps
3. Identify workarounds customers are using (indicates automation opportunity)
4. Count affected accounts for each theme
5. Urgency based on volume (15+ high, 5-14 medium, <5 low) AND language intensity

### Quote Extraction:
- Prioritize direct customer language over rep summaries
- Look for text in quotes, after "Customer said:", or in email replies
- Extract 2-5 of the most impactful quotes per theme
- Quotes should illustrate the pain point or need

### Feature Keywords:
- Generate 3-5 keywords per theme for semantic matching
- Include synonyms and related terms
- Focus on the capability, not the complaint
- Keywords will be used to match themes with competitive analysis

### Aggregate Patterns:
- top_loss_themes: Themes appearing most frequently in lost deals
- top_win_themes: Themes appearing positively in won deals
- competitor_patterns: What themes/issues are associated with each competitor

## Important Guidelines

1. Extract insights from the CONTENT of activities, not just metadata
2. VERBATIM quotes are critical - preserve actual customer language
3. One deal may have MULTIPLE themes - create separate insight entries
4. Support themes should be AGGREGATED across tickets, not per-ticket
5. Focus on ACTIONABLE insights that inform product decisions
6. Only output valid JSON - no explanatory text outside the JSON object"""

    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        """Build user prompt from parsed activity data."""
        deals = input_data.get('deals', [])
        support_tickets = input_data.get('support_tickets', [])

        # Format deals section
        deals_section = self._format_deals(deals)

        # Format support tickets section
        tickets_section = self._format_support_tickets(support_tickets)

        # Count activities
        deal_activity_count = sum(len(d.get('activities', [])) for d in deals)
        support_activity_count = sum(len(t.get('activities', [])) for t in support_tickets)

        prompt = f"""# CRM Activity Analysis Request

## Sales Deal Activities ({len(deals)} deals, {deal_activity_count} activities)

{deals_section}

## Support Ticket Activities ({len(support_tickets)} tickets, {support_activity_count} activities)

{tickets_section}

## Your Task

Analyze the activity content above and extract product insights:

1. **Deal Insights**: For each deal, identify product-relevant themes from the activity content. Correlate with deal outcome. Extract verbatim customer quotes.

2. **Support Insights**: Aggregate themes across support tickets. Look for hidden feature requests in bug reports and confusion tickets.

3. **Loss Patterns**: Identify which themes appear most in lost deals.

4. **Win Patterns**: Identify themes associated with won deals (differentiators).

5. **Competitor Patterns**: Note what issues/themes are associated with specific competitors.

Respond with ONLY a valid JSON object following the schema in the system prompt."""

        return prompt

    def _format_deals(self, deals: List[Dict[str, Any]]) -> str:
        """Format deal records with their activities for the prompt."""
        if not deals:
            return "No deal records provided."

        lines = []

        # Group by outcome
        lost_deals = [d for d in deals if d.get('outcome', '').lower() == 'lost']
        won_deals = [d for d in deals if d.get('outcome', '').lower() == 'won']
        other_deals = [d for d in deals if d.get('outcome', '').lower() not in ('lost', 'won')]

        # Format lost deals first (most important for identifying gaps)
        if lost_deals:
            lines.append("### Lost Deals")
            for deal in lost_deals:
                lines.append(self._format_single_deal(deal))

        # Then won deals
        if won_deals:
            lines.append("\n### Won Deals")
            for deal in won_deals:
                lines.append(self._format_single_deal(deal))

        # Then other deals
        if other_deals:
            lines.append("\n### Other Deals (Open/Unknown)")
            for deal in other_deals:
                lines.append(self._format_single_deal(deal))

        return "\n".join(lines)

    def _format_single_deal(self, deal: Dict[str, Any]) -> str:
        """Format a single deal with its activities."""
        lines = []

        deal_name = deal.get('deal_name', deal.get('deal_id', 'Unknown'))
        outcome = deal.get('outcome', 'unknown')
        value = deal.get('deal_value')
        competitor = deal.get('competitor')
        close_date = deal.get('close_date')

        # Deal header
        header_parts = [f"**{deal_name}**"]
        if value:
            header_parts.append(f"${value:,.0f}")
        if competitor:
            header_parts.append(f"vs {competitor}")
        if close_date:
            header_parts.append(f"closed {close_date}")

        lines.append(" | ".join(header_parts))

        # Activities
        activities = deal.get('activities', [])
        if activities:
            for activity in activities:
                lines.append(self._format_activity(activity))
        else:
            lines.append("  No activities recorded")

        lines.append("")  # Blank line between deals
        return "\n".join(lines)

    def _format_activity(self, activity: Dict[str, Any]) -> str:
        """Format a single activity."""
        activity_type = activity.get('type', 'note')
        timestamp = activity.get('timestamp', '')
        subject = activity.get('subject', '')
        body = activity.get('body', '')

        # Truncate long bodies
        if len(body) > 500:
            body = body[:500] + "..."

        parts = [f"  [{activity_type}]"]
        if timestamp:
            parts.append(f"{timestamp[:10]}")
        if subject:
            parts.append(f"- {subject}")

        header = " ".join(parts)

        if body:
            # Indent body content
            body_lines = body.split('\n')
            formatted_body = '\n'.join(f"    {line}" for line in body_lines if line.strip())
            return f"{header}\n{formatted_body}"
        else:
            return header

    def _format_support_tickets(self, tickets: List[Dict[str, Any]]) -> str:
        """Format support tickets with their activities."""
        if not tickets:
            return "No support tickets provided."

        lines = []

        for ticket in tickets:
            ticket_id = ticket.get('ticket_id', 'Unknown')
            account = ticket.get('account_name', 'Unknown')
            subject = ticket.get('subject', '')

            lines.append(f"**Ticket {ticket_id}** - {account}")
            if subject:
                lines.append(f"  Subject: {subject}")

            activities = ticket.get('activities', [])
            for activity in activities:
                lines.append(self._format_activity(activity))

            lines.append("")  # Blank line between tickets

        return "\n".join(lines)

    def _validate_input(self, input_data: Dict[str, Any]) -> None:
        """Validate required input fields."""
        super()._validate_input(input_data)

        deals = input_data.get('deals', [])
        tickets = input_data.get('support_tickets', [])

        if not deals and not tickets:
            raise ValueError("At least one deal or support ticket with activities is required")

        # Check that there's at least some activity content
        has_activities = False
        for deal in deals:
            if deal.get('activities'):
                has_activities = True
                break
        if not has_activities:
            for ticket in tickets:
                if ticket.get('activities'):
                    has_activities = True
                    break

        if not has_activities:
            raise ValueError("At least one activity with content is required")
