# Report Generator Agent

## Purpose

Generate configurable reports that synthesize:
- Competitive intelligence
- Customer feedback (votes, comments)
- Customer validation of competitor features
- Feature gaps and trends

Reports are scheduled or on-demand, with editable output formats.

## Trigger

- **Scheduled**: Per report configuration (weekly, monthly, etc.)
- **On-demand**: PM requests immediate generation
- **Event-based**: After significant competitive scan or voting milestone

## Report Sections (Building Blocks)

PMs configure reports by selecting sections:

| Section | Description | Data Source |
|---------|-------------|-------------|
| `competitive_changes` | New/modified/removed features | Competitive Monitor |
| `top_voted_ideas` | Highest priority from voting | Ideas + Votes |
| `feature_gap_analysis` | What competitors have that you lack | Comparison engine |
| `customer_feedback_on_competitor_features` | Votes/comments on competitor-sourced ideas | Ideas (source_type='competitor_feature') |
| `voting_trends` | Changes in vote patterns over time | Votes (time series) |
| `new_ideas_summary` | Ideas submitted this period | Ideas |
| `competitor_overview` | Summary of monitored competitors | Competitors |

## Configuration

```python
class ReportConfig:
    report_id: UUID
    product_id: UUID
    name: str  # "Monthly Competitive Summary"
    
    # Sections to include (ordered)
    sections: List[ReportSection]
    
    # Schedule
    schedule_type: str  # 'manual', 'weekly', 'monthly'
    schedule_day: Optional[int]  # Day of week (0-6) or month (1-31)
    schedule_time: str  # "09:00" UTC
    
    # Time range for data
    lookback_period: str  # '7d', '30d', '90d', 'since_last_report'
    
    # Output
    output_formats: List[str]  # ['pdf', 'google_doc', 'markdown']
    
    # Distribution
    auto_email: bool = False
    email_recipients: List[str] = []

class ReportSection:
    section_type: str  # From section types above
    title_override: Optional[str]  # Custom title
    config: dict  # Section-specific config
```

## Section Specifications

### Section: `competitive_changes`

**Purpose**: Show what changed in the competitive landscape

**Config**:
```python
class CompetitiveChangesConfig:
    include_new_features: bool = True
    include_modified_features: bool = True
    include_removed_features: bool = False
    include_new_competitors: bool = True
    competitors_filter: List[UUID] = []  # Empty = all
    min_significance: str = "low"  # 'low', 'medium', 'high'
```

**Output Structure**:
```markdown
## Competitive Changes (Last 30 Days)

### New Competitors Detected
- **NewCo** - AI-powered analytics platform targeting SMB market

### Feature Changes

#### CompetitorX
| Feature | Change | Description |
|---------|--------|-------------|
| AI Insights | NEW | Auto-generates dashboard summaries |
| Natural Language Query | NEW | Ask questions in plain English |
| Export Options | MODIFIED | Added PDF export, removed CSV |

#### CompetitorY
| Feature | Change | Description |
|---------|--------|-------------|
| Real-time Collaboration | NEW | Multiple users edit simultaneously |

### Summary
- 5 new features detected across 3 competitors
- AI/ML features trending (3 competitors added)
```

---

### Section: `top_voted_ideas`

**Purpose**: Show highest priority ideas from customer voting

**Config**:
```python
class TopVotedConfig:
    count: int = 10
    include_vote_count: bool = True
    include_comment_summary: bool = True
    include_source_type: bool = True  # Show if customer or competitor-sourced
    filter_status: List[str] = ['voting', 'under_review']
```

**Output Structure**:
```markdown
## Top Voted Ideas

| Rank | Idea | Votes | Source | Status |
|------|------|-------|--------|--------|
| 1 | Real-time collaboration on dashboards | 47 | Competitor | Voting |
| 2 | Dark mode support | 42 | Customer | Voting |
| 3 | Slack integration for alerts | 38 | Customer | Under Review |
| 4 | Natural language query builder | 31 | Competitor | Voting |
| 5 | Mobile app improvements | 28 | Customer | Voting |

### Comment Highlights
- "Real-time collaboration" - 12 comments, 85% positive sentiment
- "Dark mode" - 8 comments, mentions accessibility needs
```

---

### Section: `feature_gap_analysis`

**Purpose**: Compare your features vs competitors

**Config**:
```python
class GapAnalysisConfig:
    competitors: List[UUID]  # Which to compare
    show_your_advantages: bool = True
    show_competitor_advantages: bool = True
    group_by: str = "category"  # 'category', 'competitor'
```

**Output Structure**:
```markdown
## Feature Gap Analysis

### Your Competitive Advantages
Features you have that competitors lack:

| Feature | Your Product | CompetitorX | CompetitorY |
|---------|--------------|-------------|-------------|
| Embedded Analytics | ✓ | ✗ | ✗ |
| Custom Branding | ✓ | ✗ | ✓ |
| SOC2 Compliance | ✓ | ✗ | ✗ |

### Competitive Gaps
Features competitors have that you lack:

| Feature | CompetitorX | CompetitorY | Customer Interest |
|---------|-------------|-------------|-------------------|
| AI-powered insights | ✓ | ✓ | 47 votes |
| Real-time collaboration | ✓ | ✗ | 31 votes |
| Mobile app | ✓ | ✓ | 28 votes |

### Gap Prioritization
Based on customer voting, top gaps to address:
1. AI-powered insights (47 votes) - 2 competitors have this
2. Real-time collaboration (31 votes) - 1 competitor has this
```

---

### Section: `customer_feedback_on_competitor_features`

**Purpose**: THE KEY DIFFERENTIATOR - Show how customers validate competitor features

**Config**:
```python
class CompetitorFeedbackConfig:
    min_votes: int = 5  # Only show features with sufficient votes
    include_comments: bool = True
    include_sentiment: bool = True
    sort_by: str = "votes"  # 'votes', 'sentiment', 'recency'
```

**Output Structure**:
```markdown
## Customer Feedback on Competitor Features

Ideas sourced from competitive intelligence, validated by your customers:

### High Customer Interest
| Feature (from competitor) | Votes | Sentiment | Comments |
|---------------------------|-------|-----------|----------|
| Real-time collaboration (CompetitorX) | 47 | 85% positive | 12 |
| Natural language queries (CompetitorX) | 31 | 72% positive | 8 |
| AI-powered insights (CompetitorY) | 28 | 68% positive | 6 |

### Low Customer Interest
| Feature (from competitor) | Votes | Sentiment | Comments |
|---------------------------|-------|-----------|----------|
| Blockchain audit trail (CompetitorZ) | 3 | 45% positive | 1 |
| AR visualization (CompetitorY) | 2 | 50% positive | 0 |

### Key Insight
**Customers validate collaboration and query features, not AI/blockchain hype.**

Competitor features your customers actually want:
- Real-time collaboration: "Essential for our distributed team" (top comment)
- Natural language: "Would save hours of SQL writing"

Competitor features your customers don't care about:
- Blockchain: Low interest despite competitor marketing
- AR visualization: No traction with your user base
```

---

### Section: `voting_trends`

**Purpose**: Show how voting patterns change over time

**Config**:
```python
class VotingTrendsConfig:
    period: str = "30d"
    show_rising_ideas: bool = True
    show_falling_ideas: bool = True
    show_category_trends: bool = True
```

**Output Structure**:
```markdown
## Voting Trends

### Rising Ideas (Gaining Momentum)
| Idea | Votes (30d ago) | Votes (now) | Change |
|------|-----------------|-------------|--------|
| AI-powered insights | 12 | 28 | +133% |
| Mobile app | 15 | 28 | +87% |

### Category Trends
| Category | Votes (30d ago) | Votes (now) | Trend |
|----------|-----------------|-------------|-------|
| AI/Automation | 45 | 89 | ↑ Strong growth |
| Integrations | 67 | 72 | → Stable |
| UI/UX | 34 | 28 | ↓ Declining |
```

---

## Generation Pipeline

```python
async def generate_report(
    report_config: ReportConfig
) -> GeneratedReport:
    
    # 1. Determine time range
    start_date, end_date = calculate_time_range(report_config)
    
    # 2. Generate each section
    sections_content = []
    for section in report_config.sections:
        content = await generate_section(
            section=section,
            product_id=report_config.product_id,
            start_date=start_date,
            end_date=end_date
        )
        sections_content.append(content)
    
    # 3. Assemble report
    report_markdown = assemble_report(
        title=report_config.name,
        period=f"{start_date} to {end_date}",
        sections=sections_content
    )
    
    # 4. Convert to requested formats
    outputs = {}
    for format in report_config.output_formats:
        outputs[format] = await convert_report(report_markdown, format)
    
    # 5. Store and return
    report_record = await store_report(report_config, outputs)
    
    return GeneratedReport(
        report_id=report_record.id,
        outputs=outputs,
        generated_at=datetime.now()
    )
```

## Section Generator Pattern

```python
async def generate_section(
    section: ReportSection,
    product_id: UUID,
    start_date: datetime,
    end_date: datetime
) -> SectionContent:
    
    # Get section generator
    generator = SECTION_GENERATORS[section.section_type]
    
    # Fetch data
    data = await generator.fetch_data(
        product_id=product_id,
        start_date=start_date,
        end_date=end_date,
        config=section.config
    )
    
    # Generate content (may use LLM for summaries)
    content = await generator.generate_content(data, section.config)
    
    # Apply title override if present
    if section.title_override:
        content.title = section.title_override
    
    return content
```

## Output Formats

### Markdown (Editable)
- Raw markdown file
- Can be imported into any editor
- Version controllable

### Google Doc (Editable)
- Uses Google Docs API
- Creates new doc in configured folder
- PM can edit directly

### PDF (Final)
- Rendered from markdown
- Includes charts/visualizations
- For distribution

### PowerPoint (Future)
- For roadmap presentations
- Key insights as slides

## PM Interface: Report Configuration

```
┌─────────────────────────────────────────────────────────────────┐
│ Reports                                       [+ New Report]    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ 📊 Monthly Competitive Summary                               │ │
│ │ Schedule: Monthly, 1st day, 9:00 AM                         │ │
│ │ Sections: Competitive Changes, Customer Feedback, Gaps      │ │
│ │ Last generated: Dec 1, 2024                                 │ │
│ │                                                              │ │
│ │ [View Last Report] [Generate Now] [Edit Config] [Delete]    │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ 📊 Weekly Voting Digest                                      │ │
│ │ Schedule: Weekly, Monday, 9:00 AM                           │ │
│ │ Sections: Top Voted, Voting Trends, New Ideas               │ │
│ │ Last generated: Dec 23, 2024                                │ │
│ │                                                              │ │
│ │ [View Last Report] [Generate Now] [Edit Config] [Delete]    │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Report Configuration UI

```
┌─────────────────────────────────────────────────────────────────┐
│ Edit Report: Monthly Competitive Summary                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ Report Name: [Monthly Competitive Summary          ]            │
│                                                                 │
│ Schedule:                                                       │
│ ○ Manual only                                                   │
│ ○ Weekly  - Day: [Monday ▼]                                    │
│ ● Monthly - Day: [1st ▼]                                       │
│ Time: [09:00 ▼] UTC                                            │
│                                                                 │
│ Data Range: [Last 30 days ▼]                                   │
│                                                                 │
│ Sections (drag to reorder):                                     │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ ☰ ☑ Competitive Changes                        [Configure]  │ │
│ │ ☰ ☑ Customer Feedback on Competitor Features   [Configure]  │ │
│ │ ☰ ☑ Feature Gap Analysis                       [Configure]  │ │
│ │ ☰ ☑ Top Voted Ideas                            [Configure]  │ │
│ │ ☰ ☐ Voting Trends                              [Configure]  │ │
│ │ ☰ ☐ New Ideas Summary                          [Configure]  │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
│ Output Formats:                                                 │
│ ☑ PDF (final)                                                  │
│ ☑ Google Doc (editable)                                        │
│ ☐ Markdown                                                     │
│                                                                 │
│ Notifications:                                                  │
│ ☑ Email when ready: [pm@company.com                   ]        │
│                                                                 │
│                              [Cancel] [Save] [Save & Generate]  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Database Schema

```sql
-- Report configurations
CREATE TABLE report_configs (
    id UUID PRIMARY KEY,
    product_id UUID REFERENCES products(id),
    name VARCHAR(255) NOT NULL,
    sections JSONB NOT NULL,  -- Ordered list of section configs
    schedule_type VARCHAR(50),  -- 'manual', 'weekly', 'monthly'
    schedule_day INTEGER,
    schedule_time TIME,
    lookback_period VARCHAR(50),
    output_formats JSONB,
    email_recipients JSONB,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Generated reports
CREATE TABLE generated_reports (
    id UUID PRIMARY KEY,
    report_config_id UUID REFERENCES report_configs(id),
    product_id UUID REFERENCES products(id),
    period_start TIMESTAMP,
    period_end TIMESTAMP,
    sections_data JSONB,  -- Raw data used
    outputs JSONB,  -- { 'pdf': 'url', 'gdoc': 'url', 'markdown': 'content' }
    generation_time_ms INTEGER,
    generated_at TIMESTAMP DEFAULT NOW()
);
```

---

## Error Handling

- **Data fetch fails**: Include "Data unavailable" placeholder, continue with other sections
- **LLM summary fails**: Fall back to raw data presentation
- **Format conversion fails**: Retry once, then deliver available formats
- **Schedule missed**: Run on next available window, note delay in report

## Metrics

- Reports generated per product
- Average generation time
- Most used sections
- Format preferences
- Email open rates (if trackable)
