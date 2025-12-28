# Competitive Monitor Agent

## Purpose

Continuously tracks competitors and:
1. Detects new/changed/removed features
2. Generates alerts for significant changes
3. Creates anonymized ideas from competitor features for customer voting
4. Maintains competitive landscape history

## Trigger

- **Scheduled**: Per product configuration (daily, weekly, etc.)
- **On-demand**: PM requests immediate scan
- **Product update**: When product definition changes (re-discover competitors)

## Sub-Agents

The Competitive Monitor orchestrates several sub-agents:

```
Competitive Monitor (Orchestrator)
├── Competitor Discovery Agent (find new competitors)
├── Feature Extractor Agent (per competitor, parallel)
├── Differential Analysis Agent (compare to previous scan)
└── Idea Generator Agent (convert features to votable ideas)
```

## Orchestration Flow

```python
async def run_competitive_monitor(
    product_id: UUID,
    config: MonitorConfig
) -> MonitorResult:
    
    # 1. Load previous state
    previous_scan = await get_latest_scan(product_id)
    
    # 2. Discover competitors (if enabled or first run)
    if config.rediscover_competitors or not previous_scan:
        competitors = await competitor_discovery_agent.run(product_id)
        new_competitors = diff_competitors(competitors, previous_scan.competitors)
    else:
        competitors = previous_scan.competitors
        new_competitors = []
    
    # 3. Extract features (parallel)
    feature_tasks = [
        feature_extractor_agent.run(
            competitor=c,
            previous_features=get_previous_features(c, previous_scan)
        )
        for c in competitors
    ]
    feature_results = await asyncio.gather(*feature_tasks)
    
    # 4. Analyze changes
    changes = await differential_analysis_agent.run(
        current=feature_results,
        previous=previous_scan
    )
    
    # 5. Generate alerts
    alerts = generate_alerts(changes, config.alert_thresholds)
    
    # 6. Queue ideas for PM review (if significant features found)
    ideas_queued = await queue_feature_ideas(
        features=changes.new_features + changes.modified_features,
        product_id=product_id
    )
    
    # 7. Store scan results
    await store_scan_results(product_id, feature_results, changes)
    
    return MonitorResult(
        competitors_scanned=len(competitors),
        new_competitors=new_competitors,
        changes=changes,
        alerts=alerts,
        ideas_queued=ideas_queued
    )
```

---

## Sub-Agent: Competitor Discovery

### Purpose
Find competitors for a product based on its definition.

### Input
```python
class DiscoveryInput:
    product_id: UUID
    product_name: str
    product_description: str
    product_category: str
    core_features: List[str]
    search_keywords: List[str]  # From product analyzer
```

### Prompt
```
You are a competitive research agent. Find competitors for this product.

Product: {product_name}
Category: {product_category}
Description: {product_description}
Key Features: {core_features}

Tasks:
1. Identify 10-15 direct competitors
2. For each, provide:
   - Company/product name
   - Website URL
   - 2-3 sentence summary
   - Relevance score (0.0-1.0)

Focus on:
- Direct competitors (same category, similar features)
- Active products with recent updates
- Mix of established players and emerging alternatives

Output JSON:
{
  "competitors": [
    {
      "name": "...",
      "url": "...",
      "summary": "...",
      "relevance_score": 0.0
    }
  ]
}
```

### Output
```python
class DiscoveryResult:
    competitors: List[Competitor]
    search_queries_used: List[str]
    discovery_timestamp: datetime
```

---

## Sub-Agent: Feature Extractor

### Purpose
Extract features from a single competitor, with optional comparison to previous scan.

### Input
```python
class ExtractionInput:
    competitor_name: str
    competitor_url: str
    previous_features: Optional[List[Feature]]  # For differential mode
```

### Prompt (Differential Mode)
```
You are a feature extraction agent analyzing a competitor product.

Competitor: {competitor_name}
URL: {competitor_url}

Previous features from last scan ({previous_scan_date}):
{previous_features_list}

Tasks:
1. Research the competitor's current product features
2. Extract 15-25 distinct features
3. Compare with previous features to identify:
   - NEW: Features not in previous scan
   - MODIFIED: Features that changed
   - REMOVED: Previous features no longer found
   - UNCHANGED: Features that remain the same

For each feature provide:
- name: Concise name (2-5 words)
- description: 1-2 sentences
- category: e.g., "Core", "Integration", "Analytics", "Pricing"
- source_url: Specific page where found
- change_type: "new" | "modified" | "removed" | "unchanged"
- change_description: What changed (for modified features)

Output JSON:
{
  "competitor_name": "...",
  "features": [...],
  "summary": {
    "total": 0,
    "new": 0,
    "modified": 0,
    "removed": 0,
    "unchanged": 0
  }
}
```

### Output
```python
class ExtractionResult:
    competitor_id: UUID
    features: List[ExtractedFeature]
    change_summary: ChangeSummary
    extraction_timestamp: datetime
    
class ExtractedFeature:
    name: str
    description: str
    category: str
    source_url: str
    change_type: str  # 'new', 'modified', 'removed', 'unchanged'
    change_description: Optional[str]
    previous_feature_id: Optional[UUID]
    confidence: float
```

---

## Sub-Agent: Differential Analysis

### Purpose
Synthesize changes across all competitors into actionable summary.

### Input
```python
class DifferentialInput:
    product_id: UUID
    current_scan: List[ExtractionResult]
    previous_scan: Optional[ScanRecord]
```

### Output
```python
class DifferentialResult:
    # Competitor changes
    new_competitors: List[Competitor]
    removed_competitors: List[Competitor]
    
    # Feature changes (aggregated)
    new_features: List[FeatureChange]
    modified_features: List[FeatureChange]
    removed_features: List[FeatureChange]
    
    # Analysis
    significant_changes: List[SignificantChange]
    competitive_trends: List[str]  # e.g., "3 competitors added AI features"
    
class SignificantChange:
    change_type: str
    description: str
    competitors_involved: List[str]
    urgency: str  # 'high', 'medium', 'low'
    
class FeatureChange:
    competitor_name: str
    feature_name: str
    feature_description: str
    change_type: str
    change_description: Optional[str]
    detected_at: datetime
```

---

## Sub-Agent: Idea Generator

### Purpose
Convert competitor features into anonymized, votable ideas.

### Input
```python
class IdeaGenInput:
    feature: ExtractedFeature
    competitor_name: str  # For source tracking, not included in output
    product_context: ProductContext  # Your product's features for framing
```

### Prompt
```
Convert this competitor feature into an anonymized product idea.

Feature: {feature_name}
Description: {feature_description}

Your product context:
- Name: {product_name}
- Current features: {product_features}

Generate a structured idea:
- What: Clear description (2-3 sentences). Frame as a new capability, not a copy.
- Why: Business value or user benefit (2-3 sentences)
- Use Case: Concrete scenario (2-3 sentences)

Rules:
- Remove ALL competitor branding and product names
- Generalize to be product-agnostic
- Focus on user value, not implementation
- Make it sound like an original idea

Output JSON:
{
  "what": "...",
  "why": "...",
  "use_case": "..."
}
```

### Output
```python
class GeneratedIdea:
    idea_what: str
    idea_why: str
    idea_use_case: str
    
    # Source tracking (hidden from customers)
    source_type: str = "competitor_feature"
    source_metadata: dict  # { competitor_id, feature_id, detected_at }
    
    # Status
    status: str = "pending_pm_review"
```

---

## Alerts

### Alert Types

```python
class AlertType(Enum):
    NEW_COMPETITOR = "new_competitor"
    COMPETITOR_REMOVED = "competitor_removed"
    MAJOR_FEATURE_LAUNCH = "major_feature_launch"
    FEATURE_REMOVED = "feature_removed"
    PRICING_CHANGE = "pricing_change"
    TREND_DETECTED = "trend_detected"

class Alert:
    alert_type: AlertType
    severity: str  # 'high', 'medium', 'low'
    title: str
    description: str
    competitors_involved: List[str]
    features_involved: List[str]
    recommended_action: str
    created_at: datetime
```

### Alert Thresholds (Configurable)

```python
class AlertConfig:
    # Severity thresholds
    major_feature_keywords: List[str] = ["AI", "automation", "real-time"]
    high_severity_if_multiple_competitors: int = 3  # Same feature at 3+ competitors
    
    # Alert generation
    alert_on_new_competitor: bool = True
    alert_on_removed_competitor: bool = True
    alert_on_new_features: bool = True
    alert_on_pricing_changes: bool = True
    
    # Notification
    email_on_high_severity: bool = True
    digest_frequency: str = "daily"  # 'immediate', 'daily', 'weekly'
```

---

## PM Review Queue: Competitive Alerts

```
┌─────────────────────────────────────────────────────────────────┐
│ 🔴 HIGH: CompetitorX launched AI features          Detected: 4h │
│                                                                 │
│ Changes Found:                                                  │
│ • NEW: "AI-powered insights" - Auto-generates dashboard...     │
│ • NEW: "Natural language queries" - Users can ask questions... │
│ • MODIFIED: Pricing restructured (new AI tier added)           │
│                                                                 │
│ Competitive Context:                                            │
│ • CompetitorY also added AI features last month                │
│ • 2 customer ideas mention "AI" or "automation"                │
│                                                                 │
│ Recommended Actions:                                            │
│ • Create ideas for customer voting                              │
│ • Review pricing positioning                                    │
│                                                                 │
│ [Create Ideas] [Add to Comparison] [Dismiss] [Snooze 1 week]   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Configuration

```python
class MonitorConfig:
    product_id: UUID
    
    # Schedule
    scan_frequency: str = "weekly"  # 'daily', 'weekly', 'monthly'
    scan_day: Optional[int] = 1  # Day of week (0=Mon) or month
    scan_time: str = "02:00"  # UTC
    
    # Scope
    competitors_to_monitor: List[UUID]  # Empty = all discovered
    rediscover_competitors: bool = False  # Re-run discovery each scan
    max_competitors: int = 15
    
    # Feature extraction
    categories_to_track: List[str] = []  # Empty = all
    
    # Alerts
    alert_config: AlertConfig
    
    # Idea generation
    auto_generate_ideas: bool = True
    idea_generation_filter: str = "new_only"  # 'new_only', 'new_and_modified', 'all'
```

---

## Database Schema Additions

```sql
-- Competitive scans (historical record)
CREATE TABLE competitive_scans (
    id UUID PRIMARY KEY,
    product_id UUID REFERENCES products(id),
    scan_type VARCHAR(50),  -- 'scheduled', 'manual', 'product_update'
    status VARCHAR(50),  -- 'running', 'completed', 'failed'
    competitors_scanned INTEGER,
    new_features_found INTEGER,
    modified_features_found INTEGER,
    alerts_generated INTEGER,
    ideas_queued INTEGER,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT
);

-- Competitive alerts
CREATE TABLE competitive_alerts (
    id UUID PRIMARY KEY,
    product_id UUID REFERENCES products(id),
    scan_id UUID REFERENCES competitive_scans(id),
    alert_type VARCHAR(50),
    severity VARCHAR(20),
    title TEXT,
    description TEXT,
    competitors_involved JSONB,
    features_involved JSONB,
    recommended_action TEXT,
    status VARCHAR(50) DEFAULT 'pending',  -- 'pending', 'reviewed', 'dismissed', 'snoozed'
    reviewed_at TIMESTAMP,
    reviewed_by UUID REFERENCES users(id),
    snoozed_until TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Monitor configuration
CREATE TABLE competitive_monitor_config (
    product_id UUID PRIMARY KEY REFERENCES products(id),
    config JSONB NOT NULL,
    enabled BOOLEAN DEFAULT true,
    last_scan_at TIMESTAMP,
    next_scan_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

## Error Handling

- **Competitor website unreachable**: Skip, log, continue with others
- **Feature extraction fails**: Retry once, then skip competitor for this scan
- **LLM rate limit**: Queue remaining work, resume later
- **Partial scan completion**: Store partial results, alert PM, schedule retry

## Metrics

- Scans completed per product
- Average features extracted per competitor
- Change detection accuracy (manual validation sample)
- Alert-to-action conversion rate
- Ideas generated from competitor features
- Customer votes on competitor-sourced ideas
