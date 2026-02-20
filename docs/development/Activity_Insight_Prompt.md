# Activity Insight Agent Prompt

## Purpose

This agent analyzes CRM activity data (call notes, emails, meeting notes) to extract product-relevant insights from conversational/unstructured content. Unlike structured win/loss reasons, activity data contains authentic customer voice and often reveals implicit feature requests.

## Input

```json
{
  "deals": [
    {
      "deal_id": "opp-123",
      "deal_name": "Acme Corp",
      "outcome": "lost",
      "close_date": "2025-01-15",
      "competitor": "Competitor X",
      "deal_value": 50000,
      "activities": [
        {
          "type": "call",
          "timestamp": "2025-01-10T14:30:00Z",
          "subject": "Discovery call",
          "body": "Customer mentioned they need better Salesforce integration...",
          "direction": "outbound",
          "duration_minutes": 45
        }
      ]
    }
  ],
  "support_tickets": [
    {
      "ticket_id": "ticket-456",
      "account_name": "Beta Inc",
      "activities": [
        {
          "type": "comment",
          "timestamp": "2025-01-12T09:00:00Z",
          "author": "customer",
          "body": "We've been manually exporting data to Excel because..."
        }
      ]
    }
  ]
}
```

## Output Schema

```json
{
  "deal_insights": [
    {
      "deal_id": "opp-123",
      "deal_name": "Acme Corp",
      "deal_outcome": "lost",
      "deal_value": 50000,
      "competitor_mentioned": "Competitor X",
      "theme_name": "Salesforce Integration Gap",
      "category": "integration_need",
      "sentiment": "negative",
      "urgency_level": "high",
      "sample_quotes": [
        "We need native Salesforce sync, manual data entry takes 2 hours per week"
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
        "We've been manually exporting to Excel because there's no bulk export"
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
    "Competitor X": ["Better integrations", "Lower price"]
  },
  "analysis_summary": "Analysis of 10 deals reveals integration gaps as primary loss driver..."
}
```

## Analysis Methodology

### Phase 1: Per-Deal Analysis

For each deal, analyze all activities together in context of the deal outcome:

1. **Read all activities** - understand the full conversation arc
2. **Extract themes** - identify product-related topics discussed
3. **Capture quotes** - preserve verbatim customer language
4. **Detect signals**:
   - Urgency: frustrated language, escalation, deadline pressure
   - Sentiment: praise, complaint, concern, neutral
   - Competitors: mentions and comparisons
5. **Categorize**: feature_gap, ux_friction, competitive_pressure, use_case_gap, integration_need

### Phase 2: Aggregate Analysis

Across all deals and support tickets:

1. **Cluster themes** - group similar themes even if worded differently
2. **Correlate with outcomes** - which themes appear in lost vs won deals?
3. **Calculate urgency** - combine frequency, volume, and language intensity
4. **Identify patterns**:
   - top_loss_themes: Most common themes in lost deals
   - top_win_themes: Themes associated with wins (differentiators)
   - competitor_patterns: Themes linked to specific competitors

### Quote Extraction Guidelines

- **Prioritize customer voice** over rep summaries
- Look for:
  - Text in quotation marks
  - After "Customer said:" or similar
  - Email replies (customer responses)
  - Meeting transcript excerpts
- Extract 2-5 most impactful quotes per theme
- Preserve original language - don't paraphrase

### Feature Keywords

Generate 3-5 keywords per theme for semantic matching with competitive analysis:

- Include synonyms and related terms
- Focus on the capability, not the complaint
- Example: "We can't export data easily" → keywords: ["export", "bulk export", "csv", "data extraction"]

## Category Definitions

| Category | Description | Example |
|----------|-------------|---------|
| feature_gap | Missing capability | "We need Salesforce integration" |
| ux_friction | Usability/UX issues | "The interface is confusing" |
| competitive_pressure | Competitor advantage | "Competitor X has better reporting" |
| use_case_gap | Workflow not supported | "We can't handle multi-currency" |
| integration_need | Third-party connection | "Need to connect with Slack" |

## Urgency Levels

| Level | Deal Signals | Support Volume |
|-------|--------------|----------------|
| high | Deal blocker, explicit urgency | 15+ tickets |
| medium | Concern, negotiation point | 5-14 tickets |
| low | Nice-to-have, mentioned once | <5 tickets |

## Integration with Synthesis

Activity insights feed into the OpportunitySynthesisAgent alongside:
- Structured win/loss themes (InternalDiscoveryAgent)
- Competitive analysis (LandscapeOpportunitySynthesizer)
- Customer votes (Ideas with votes)

When activity insights align with these sources, confidence increases:
- Activity + Structured agree → High confidence
- Activity + Competitive agree → Very high confidence
- Activity + Customer votes agree → Validated demand
