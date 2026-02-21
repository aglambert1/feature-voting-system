# RAG Implementation Requirements

**Status**: Future Enhancement
**Priority**: Medium
**Dependencies**: Vector similarity search (completed)

## Overview

This document outlines requirements for implementing Retrieval-Augmented Generation (RAG) capabilities to enhance the feature voting system with AI-generated insights and analysis.

**Current State**: The system has vector similarity search using Voyage AI embeddings (voyage-3.5-lite, 1024 dims) and sqlite-vec/pgvector for duplicate detection during idea submission.

**Future State**: Extend vector search with LLM-powered generation to provide context-aware insights, analysis, and recommendations for product owners and users.

## What is RAG?

RAG combines vector similarity search with large language model (LLM) generation:

1. **Retrieve**: Use vector search to find relevant context (ideas, comments, votes, etc.)
2. **Augment**: Provide retrieved context to an LLM
3. **Generate**: LLM produces insights, explanations, or recommendations based on the context

**Key Difference from Current Implementation**:
- Current: Vector search returns similar ideas with scores
- RAG: Vector search + LLM generates human-readable insights and recommendations

## Use Cases (Prioritized)

### High Priority

#### 1. Product Owner Idea Analysis
**User Story**: As a product owner, I want AI-generated analysis of new ideas so I can quickly understand context and make informed decisions.

**Functionality**:
- Button/tab on idea detail page: "AI Analysis"
- Retrieves: Similar ideas, related comments, voting patterns, roadmap status
- Generates: Summary of similarity, user sentiment, suggested actions

**Example Output**:
```
AI Analysis:

SIMILARITY & CONTEXT
This idea is similar to Ideas #42 and #67, which have received 156 combined votes.
The key difference is that this proposal includes mobile-specific features.

USER SENTIMENT
Based on 23 comments across related ideas, users prioritize:
• Offline functionality (mentioned 12 times)
• Cross-device sync (mentioned 8 times)
• Performance on older devices (mentioned 5 times)

RECOMMENDATIONS
1. Consider merging with Idea #42 which already has technical specs
2. Tag as "mobile-UX" - aligns with Q3 roadmap item "Mobile Experience Improvements"
3. Estimated effort: Medium (similar to previously implemented Idea #18)
```

**Technical Requirements**:
- New endpoint: `GET /ideas/{id}/analysis`
- Vector search for top 10 similar ideas
- Retrieve comments, votes, related tags
- Claude API integration for generation
- Cache results (24 hours) to reduce costs
- Product Owner role required

**Cost Estimate**: $0.01-0.05 per analysis (depending on context size)

#### 2. Enhanced Duplicate Detection with Explanations
**User Story**: As a user submitting an idea, I want to understand WHY similar ideas exist so I can decide whether to proceed or vote for existing ideas.

**Functionality**:
- Enhance current similarity warning during submission
- Instead of just showing similar ideas, explain the relationship

**Current Display**:
```
⚠️ Similar ideas found:
• Customizable Kettle Color Options - 92% similar
```

**Enhanced Display**:
```
⚠️ Similar ideas found:

"Customizable Kettle Color Options" (92% similar)
Your idea and this existing idea both focus on allowing users to choose
product colors. The main difference is that your idea also mentions texture
customization, which isn't covered in the existing idea.

Consider: Add your texture idea as a comment on Idea #42, or proceed with
submission if you believe it's substantially different.
```

**Technical Requirements**:
- Modify existing `GET /ideas/similar` endpoint or add `?explain=true` param
- Lightweight generation (keep latency <2s)
- Use mini prompt to keep costs low
- No authentication required (public feature)

**Cost Estimate**: $0.001-0.005 per search (much cheaper, smaller context)

### Medium Priority

#### 3. Automated Idea Triage & Categorization
**User Story**: As a product owner, I want new ideas automatically categorized and prioritized so I can focus on high-value reviews.

**Functionality**:
- Runs automatically when new idea is submitted (async job)
- Analyzes idea content against existing categories, roadmap, patterns
- Suggests category, tags, priority level
- PO can accept/reject suggestions

**Example Output**:
```
Suggested Triage:
• Category: User Experience > Mobile
• Tags: mobile-UX, offline-mode, Q3-roadmap
• Priority: High (related to strategic initiative "Mobile First")
• Related Epic: #12 "Mobile App Redesign"
```

**Technical Requirements**:
- Background job after idea creation
- Vector search across categories, tags, roadmap docs
- Store suggestions in `idea_triage_suggestions` table
- UI in PO dashboard to review/apply suggestions
- Metrics: track acceptance rate to improve prompts

**Cost Estimate**: $0.02-0.05 per idea (runs once per submission)

#### 4. Competitive Analysis Integration
**User Story**: As a product owner importing competitor features, I want to understand how they relate to existing user-submitted ideas and our roadmap.

**Functionality**:
- When PO submits competitor-extracted feature
- RAG analyzes against: existing ideas, user votes, roadmap, other competitor features
- Generates competitive positioning insight

**Example Output**:
```
Competitive Analysis:

MARKET CONTEXT
• This feature exists in 3/5 top competitors (Competitor A, B, C)
• Competitor A has more advanced implementation (includes X and Y)

USER DEMAND
• 2 similar user-submitted ideas exist (#34, #78) with 89 combined votes
• Users specifically requested features X and Y which competitors don't offer
• 12 comments mention frustration with current workflow

STRATEGIC RECOMMENDATION
• High priority - users are actively requesting this
• Opportunity to differentiate by adding X and Y features
• Consider implementing before Q4 when Competitor D is rumored to launch similar feature
```

**Technical Requirements**:
- Extend idea submission flow for `source_type = "competitor_automated"`
- Vector search across: user ideas, competitor features, roadmap docs
- Store competitor feature metadata (source, URL, screenshots)
- New table: `competitive_insights`
- Product Owner role required

**Cost Estimate**: $0.05-0.10 per analysis (larger context)

### Lower Priority

#### 5. Trend Analysis & Insights
**User Story**: As a product owner, I want periodic AI-generated trend reports so I can identify emerging user needs.

**Functionality**:
- Weekly/monthly automated reports
- Analyzes: new ideas, voting patterns, comment sentiment, user segments
- Generates: trend summary, emerging themes, recommendations

**Example Output**:
```
Weekly Trend Report (Dec 11-18, 2025)

KEY TRENDS
• Mobile features up 45% this quarter (18 new ideas vs 12 last quarter)
• "Offline mode" mentioned in 12 different ideas across 3 products
• Enterprise users (identified by email domain) vote 3x more for security features

EMERGING THEMES
• Dark mode requests increasing (4 ideas this week, 156 total votes)
• Integration requests focused on Slack and Microsoft Teams
• Performance concerns on Android devices (mentioned 8 times in comments)

RECOMMENDATIONS
1. Consider prioritizing offline mobile functionality
2. Create "Dark Mode" epic to consolidate 6 related ideas
3. Investigate Android performance issues
```

**Technical Requirements**:
- Scheduled job (weekly/monthly)
- Vector clustering to identify themes
- Time-series analysis of voting/submission patterns
- Email report to product owners
- Dashboard view for historical reports

**Cost Estimate**: $0.50-1.00 per report (large context, complex analysis)

#### 6. Smart Idea Merger Suggestions
**User Story**: As a product owner, I want AI to suggest how to merge similar ideas so I can efficiently consolidate duplicates.

**Functionality**:
- PO selects 2+ similar ideas
- RAG analyzes all descriptions, comments, votes
- Generates merged idea description that captures all user needs

**Example Output**:
```
Merge Suggestions for Ideas #23, #45, #67:

MERGED TITLE
"Advanced Product Customization Suite"

MERGED DESCRIPTION
What: Allow users to customize product appearance with:
• Choose from 15+ colors (from Idea #23)
• Create and save custom color presets (from Idea #45)
• Preview customizations in AR (from Idea #67)
• Export/share customization configs (from comments on #45)

Why: Users want more control over product aesthetics to match their brand or
personal preferences. Current 3-color limit is frequently mentioned as limiting.

Use Case: Enterprise customers can match corporate branding, individual users
can express personal style, retailers can preview products for customers.

MIGRATION PLAN
• Primary idea: #45 (highest votes - 89)
• Link #23 and #67 as "merged into #45"
• Notify 47 unique voters across all three ideas
• Preserve all comments (78 total) with source idea labels
```

**Technical Requirements**:
- UI: Multi-select ideas, "Suggest Merge" button
- Endpoint: `POST /ideas/merge-suggestions`
- Vector search to validate similarity
- Retrieve all comments, votes, metadata
- Generate comprehensive merged description
- Preview before executing merge

**Cost Estimate**: $0.05-0.10 per merge suggestion

#### 7. User Response Templates
**User Story**: As a product owner, I want AI-generated response templates when communicating with idea submitters.

**Functionality**:
- When changing idea status or merging ideas
- Generates personalized notification/response
- PO can edit before sending

**Example Output**:
```
Suggested Response (Idea Status: Planned → In Development):

Hi Sarah,

Thank you for suggesting "Dark Mode for Mobile App"!

We're excited to let you know that this idea has moved into active development.
Your suggestion aligns perfectly with our Q1 mobile experience improvements,
and we've incorporated feedback from your idea and 3 similar suggestions
(#89, #102, #156).

Based on community input, we're prioritizing:
• System-level dark mode detection (auto-switch)
• Customizable color themes (you mentioned this in your comment)
• Smooth transition animations

Expected release: Q1 2026

We'll keep you updated as development progresses. Thanks for helping us build
a better product!

Best regards,
[Product Team]
```

**Technical Requirements**:
- Triggered by status changes, merges, milestone updates
- Context: idea details, user's comments, roadmap status
- Generate draft, allow editing
- Send via email or in-app notification
- Track which templates get used (improve prompts)

**Cost Estimate**: $0.01-0.02 per response

## Technical Architecture

### Components

```
┌─────────────────────────────────────────────────────────┐
│                    User Request                          │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│              RAG Orchestration Service                   │
│  • Request validation                                    │
│  • Context retrieval coordination                        │
│  • Prompt engineering                                    │
│  • Response formatting                                   │
└─────────────────┬───────────────────────┬───────────────┘
                  │                       │
                  ▼                       ▼
┌────────────────────────────┐  ┌──────────────────────┐
│  Vector Search Service     │  │   LLM Service        │
│  (existing)                │  │   • Claude API       │
│  • find_similar()          │  │   • Prompt templates │
│  • Embeddings              │  │   • Response parsing │
│  • Similarity ranking      │  │   • Error handling   │
└────────────────────────────┘  └──────────────────────┘
```

### New Backend Services

**`backend/app/services/rag_service.py`**
```python
class RAGService:
    """RAG orchestration for idea analysis and insights."""

    @staticmethod
    async def analyze_idea(
        db: Session,
        idea_id: int,
        analysis_type: str
    ) -> Dict[str, Any]:
        """
        Generate AI analysis for an idea.

        Args:
            db: Database session
            idea_id: ID of idea to analyze
            analysis_type: Type of analysis (full, duplicate, triage, competitive)

        Returns:
            Analysis results with retrieved context and generated insights
        """
        pass

    @staticmethod
    async def explain_similarity(
        db: Session,
        idea_text: str,
        similar_ideas: List[SimilarIdea]
    ) -> List[str]:
        """Generate explanations for why ideas are similar."""
        pass
```

**`backend/app/services/llm_service.py`**
```python
class LLMService:
    """Interface to LLM providers (Claude, OpenAI)."""

    @staticmethod
    async def generate(
        prompt: str,
        context: Dict[str, Any],
        model: str = "claude-3-5-sonnet",
        max_tokens: int = 1000
    ) -> str:
        """Generate text using LLM."""
        pass

    @staticmethod
    def build_prompt(
        template_name: str,
        variables: Dict[str, Any]
    ) -> str:
        """Build prompt from template."""
        pass
```

**`backend/app/services/cache_service.py`**
```python
class CacheService:
    """Cache for expensive RAG operations."""

    @staticmethod
    async def get_cached_analysis(
        cache_key: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve cached analysis if exists and not expired."""
        pass

    @staticmethod
    async def cache_analysis(
        cache_key: str,
        result: Dict[str, Any],
        ttl: int = 86400  # 24 hours
    ) -> None:
        """Cache analysis result."""
        pass
```

### New Database Tables

```sql
-- Store RAG analysis results
CREATE TABLE rag_analyses (
    id SERIAL PRIMARY KEY,
    idea_id INTEGER NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
    analysis_type VARCHAR(50) NOT NULL,  -- 'full', 'triage', 'competitive', etc.
    context_ids TEXT[],  -- Array of idea IDs used as context
    prompt_template VARCHAR(100),
    generated_output TEXT NOT NULL,
    model_used VARCHAR(50),
    tokens_used INTEGER,
    cost_usd DECIMAL(10, 6),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(id),
    invalidated_at TIMESTAMP,  -- Set when idea changes materially

    INDEX idx_idea_analysis (idea_id, analysis_type),
    INDEX idx_created_at (created_at)
);

-- Store triage suggestions
CREATE TABLE idea_triage_suggestions (
    id SERIAL PRIMARY KEY,
    idea_id INTEGER NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
    suggested_category VARCHAR(100),
    suggested_tags TEXT[],
    suggested_priority VARCHAR(20),
    reasoning TEXT,
    confidence_score DECIMAL(3, 2),  -- 0.0 to 1.0
    accepted BOOLEAN,
    reviewed_by INTEGER REFERENCES users(id),
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_pending (idea_id) WHERE accepted IS NULL
);

-- Store competitive insights
CREATE TABLE competitive_insights (
    id SERIAL PRIMARY KEY,
    idea_id INTEGER NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
    competitor_name VARCHAR(200),
    competitor_feature_url TEXT,
    similar_user_ideas INTEGER[],  -- Array of related user-submitted idea IDs
    market_prevalence TEXT,  -- "3/5 competitors have this"
    user_demand_summary TEXT,
    strategic_recommendation TEXT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_idea_competitive (idea_id)
);

-- Track RAG usage and costs
CREATE TABLE rag_usage_metrics (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    analysis_type VARCHAR(50),
    request_count INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    total_cost_usd DECIMAL(10, 4) DEFAULT 0,
    avg_latency_ms INTEGER,
    cache_hit_rate DECIMAL(3, 2),

    UNIQUE (date, analysis_type)
);
```

### New API Endpoints

```python
# Idea analysis
GET  /api/ideas/{id}/analysis                    # Get cached or generate new
POST /api/ideas/{id}/analysis/regenerate         # Force regeneration

# Similarity explanations
POST /api/ideas/explain-similarity               # Explain why ideas are similar
GET  /api/ideas/{id}/similar?explain=true        # Enhanced similarity with explanations

# Triage suggestions
GET  /api/ideas/{id}/triage-suggestion           # Get AI triage suggestion
POST /api/ideas/{id}/triage-suggestion/accept    # Accept suggestion
POST /api/ideas/{id}/triage-suggestion/reject    # Reject suggestion

# Competitive analysis
POST /api/ideas/{id}/competitive-analysis        # Generate competitive insights
GET  /api/ideas/{id}/competitive-analysis        # Get latest analysis

# Merge suggestions
POST /api/ideas/merge-suggestions                # Generate merge suggestion
     Body: { idea_ids: [23, 45, 67] }

# Trend reports
GET  /api/reports/trends?period=week|month       # Get trend report
GET  /api/reports/trends/history                 # Historical reports

# Usage metrics (admin only)
GET  /api/admin/rag/metrics                      # RAG usage and costs
```

### Configuration

**`backend/app/config.py`** additions:
```python
class Settings(BaseSettings):
    # Existing settings...

    # RAG settings
    rag_enabled: bool = False
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None  # Alternative
    default_llm_model: str = "claude-3-5-sonnet-20241022"
    rag_cache_ttl_seconds: int = 86400  # 24 hours
    rag_max_context_ideas: int = 10
    rag_similarity_threshold: float = 0.7

    # Cost controls
    rag_monthly_budget_usd: float = 100.0
    rag_cost_alert_threshold: float = 0.8  # Alert at 80% of budget
```

**Environment variables**:
```bash
RAG_ENABLED=true
ANTHROPIC_API_KEY=sk-ant-...
DEFAULT_LLM_MODEL=claude-3-5-sonnet-20241022
RAG_CACHE_TTL_SECONDS=86400
RAG_MONTHLY_BUDGET_USD=100.0
```

### Prompt Templates

**`backend/app/prompts/idea_analysis.txt`**:
```
You are analyzing a feature idea for a product voting system.

IDEA TO ANALYZE:
Title: {{idea.title}}
Description: {{idea.what_description}}
Why: {{idea.why_description}}
Use Case: {{idea.use_case_description}}

SIMILAR IDEAS (context):
{{#similar_ideas}}
- Idea #{{id}}: {{title}} ({{similarity_score}}% similar)
  Description: {{what_description}}
  Votes: {{vote_count}}
  Status: {{status}}
{{/similar_ideas}}

RELATED COMMENTS:
{{#comments}}
- {{author}}: {{text}}
{{/comments}}

Please provide:
1. SIMILARITY & CONTEXT: How this relates to existing ideas
2. USER SENTIMENT: Key themes from comments and votes
3. RECOMMENDATIONS: Specific actions for product owner (merge, tag, prioritize, etc.)

Be concise and actionable. Focus on insights that help decision-making.
```

## Implementation Phases

### Phase 1: Foundation (2-3 weeks)
**Goal**: Basic RAG infrastructure and one high-value use case

- [ ] Set up LLM service integration (Claude API)
- [ ] Create RAG service architecture
- [ ] Implement caching layer
- [ ] Create database tables
- [ ] Build prompt templates system
- [ ] Add cost tracking and budgets
- [ ] **Deliver**: Product Owner Idea Analysis (Use Case #1)
- [ ] Admin dashboard for monitoring usage/costs

### Phase 2: User-Facing Features (2 weeks)
**Goal**: Enhance user experience during idea submission

- [ ] Enhanced duplicate detection with explanations (Use Case #2)
- [ ] Update frontend UI for explanations
- [ ] Optimize prompts for low latency (<2s)
- [ ] A/B test impact on duplicate submissions

### Phase 3: Automation (2-3 weeks)
**Goal**: Reduce manual PO work

- [ ] Automated triage and categorization (Use Case #3)
- [ ] Background job system
- [ ] PO dashboard for reviewing suggestions
- [ ] Track acceptance rates, iterate on prompts

### Phase 4: Strategic Tools (3-4 weeks)
**Goal**: High-value PO workflows

- [ ] Competitive analysis integration (Use Case #4)
- [ ] Smart merge suggestions (Use Case #6)
- [ ] Response template generation (Use Case #7)

### Phase 5: Analytics (2 weeks)
**Goal**: Strategic insights

- [ ] Trend analysis and reports (Use Case #5)
- [ ] Scheduled report generation
- [ ] Email notifications
- [ ] Historical report dashboard

## Cost Management

### Budget Planning

**Estimated Monthly Costs** (assuming 100 active product owners, 500 ideas/month):

| Use Case | Requests/Month | Cost/Request | Monthly Cost |
|----------|----------------|--------------|--------------|
| PO Idea Analysis | 200 | $0.03 | $6.00 |
| Duplicate Explanations | 1,000 | $0.003 | $3.00 |
| Auto Triage | 500 | $0.04 | $20.00 |
| Competitive Analysis | 50 | $0.08 | $4.00 |
| Trend Reports | 4 | $0.75 | $3.00 |
| Merge Suggestions | 20 | $0.08 | $1.60 |
| Response Templates | 100 | $0.015 | $1.50 |
| **TOTAL** | | | **$39.10/month** |

### Cost Controls

1. **Caching**: 24-hour cache for expensive analyses (reduces costs by ~70%)
2. **Rate Limiting**: Per-user quotas for expensive operations
3. **Budget Alerts**: Email alerts at 80% and 100% of monthly budget
4. **Auto-Throttling**: Disable non-critical features if budget exceeded
5. **Model Selection**: Use cheaper models for simple tasks
   - Claude 3.5 Sonnet: Complex analysis
   - Claude 3.5 Haiku: Simple explanations (5x cheaper)

### Monitoring Queries

```sql
-- Daily cost tracking
SELECT
    DATE(created_at) as date,
    analysis_type,
    COUNT(*) as request_count,
    SUM(cost_usd) as daily_cost,
    AVG(tokens_used) as avg_tokens
FROM rag_analyses
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY date, analysis_type
ORDER BY date DESC;

-- Budget status
SELECT
    SUM(cost_usd) as month_to_date_cost,
    100.0 - (SUM(cost_usd) / 100.0 * 100) as budget_remaining_pct
FROM rag_analyses
WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE);

-- Cache effectiveness
SELECT
    date,
    cache_hit_rate,
    (cache_hit_rate * request_count * 0.03) as estimated_savings_usd
FROM rag_usage_metrics
WHERE date >= CURRENT_DATE - INTERVAL '7 days';
```

## Success Metrics

### Primary KPIs

1. **PO Time Savings**
   - Target: 30% reduction in time spent reviewing ideas
   - Measure: Time from submission to first PO action

2. **Duplicate Reduction**
   - Target: 25% reduction in duplicate idea submissions
   - Measure: % of submissions with high similarity scores that proceed

3. **Triage Accuracy**
   - Target: 70% acceptance rate for AI categorization suggestions
   - Measure: % of suggestions accepted without modification

4. **User Satisfaction**
   - Target: 4.0+ rating on duplicate explanation helpfulness
   - Measure: Optional feedback survey

### Secondary KPIs

5. **Cost Efficiency**
   - Target: Stay within $50/month budget
   - Measure: Monthly RAG costs

6. **Response Time**
   - Target: <2s for user-facing features, <10s for PO features
   - Measure: p95 latency by use case

7. **Feature Adoption**
   - Target: 60% of POs use analysis feature within 3 months
   - Measure: % of POs who've used RAG features

## Security & Privacy

### Data Handling

1. **PII Protection**: Never send user email addresses or personal info to LLM
2. **Data Minimization**: Only include necessary context (idea text, not full user profiles)
3. **Audit Trail**: Log all RAG requests with user ID and timestamp
4. **Access Control**: Require appropriate roles (PO for analysis features)

### LLM Provider Considerations

**Claude (Anthropic)**:
- ✅ Does not train on customer data
- ✅ Enterprise tier available
- ✅ SOC 2 Type II certified
- ✅ GDPR compliant

**Recommended**: Start with Claude API, evaluate alternatives later

### Prompt Injection Protection

1. **Input Sanitization**: Escape user input in prompts
2. **Output Validation**: Validate LLM responses match expected format
3. **Rate Limiting**: Prevent abuse of expensive operations
4. **Monitoring**: Alert on unusual patterns (excessive tokens, strange outputs)

## Testing Strategy

### Unit Tests

```python
# Test RAG service
def test_analyze_idea_with_context():
    """Test idea analysis with similar ideas as context."""
    pass

def test_explain_similarity():
    """Test similarity explanation generation."""
    pass

def test_cache_hit():
    """Test that cached analysis is returned."""
    pass

def test_budget_exceeded():
    """Test behavior when monthly budget exceeded."""
    pass
```

### Integration Tests

```python
def test_full_analysis_flow():
    """Test end-to-end: retrieve context -> generate -> cache -> return."""
    pass

def test_triage_suggestion_acceptance():
    """Test PO accepting triage suggestion applies changes."""
    pass
```

### Manual QA Checklist

- [ ] Analysis quality is useful and accurate
- [ ] Explanations help users understand similarity
- [ ] Latency is acceptable (<2s for user features)
- [ ] Cost tracking is accurate
- [ ] Budget alerts trigger correctly
- [ ] Cached results are returned when appropriate
- [ ] Error handling gracefully degrades

## Migration from Vector Search Only

The current system already has vector search infrastructure. RAG adds a generation layer on top:

**No Breaking Changes**:
- Current `/ideas/similar` endpoint continues to work
- Vector search functionality unchanged
- New RAG features are additive

**Backward Compatibility**:
- `GET /ideas/similar` - Current behavior (no explanations)
- `GET /ideas/similar?explain=true` - New behavior (with explanations)
- `RAG_ENABLED=false` - System works exactly as before

## Open Questions

1. **Model Selection**: Claude 3.5 Sonnet vs Haiku vs OpenAI GPT-4?
   - Decision needed: Cost vs quality tradeoff
   - Recommendation: Start with Sonnet, A/B test Haiku for simple tasks

2. **Context Window**: How many similar ideas to include?
   - Current default: 10 similar ideas
   - Need to test: Does more context improve quality or add noise?

3. **Feedback Loop**: How to improve prompts over time?
   - Proposal: Track PO edits to generated text, use to refine prompts
   - Proposal: Optional thumbs up/down on analyses

4. **Multi-language Support**: Handle ideas in multiple languages?
   - Current: Assumes English
   - Future: Embedding models support multi-language, prompts need localization

5. **Real-time vs Batch**: Which analyses should be real-time vs pre-generated?
   - Proposal: User-facing real-time, PO features can be async (job queue)

## References

**External Documentation**:
- [Claude API Docs](https://docs.anthropic.com/claude/reference/getting-started-with-the-api)
- [RAG Best Practices](https://www.anthropic.com/index/contextual-retrieval)
- [Prompt Engineering Guide](https://docs.anthropic.com/claude/docs/prompt-engineering)

**Internal Documentation**:
- [Vector Search Setup](../backend/VECTOR_SEARCH_SETUP.md)
- [Original Requirements](ORIGINAL_REQUIREMENTS.md)
- [Database Schema](DATABASE_SCHEMA.md)

## Approval & Next Steps

**Before Implementation**:
1. [ ] Review and approve use case priorities
2. [ ] Confirm budget allocation ($50-100/month)
3. [ ] Choose LLM provider (recommend: Claude)
4. [ ] Decide on Phase 1 timeline
5. [ ] Set up Anthropic API account

**Ready to Start?**
When ready to implement, begin with Phase 1 (Foundation + PO Idea Analysis).
Estimated effort: 2-3 weeks for one developer.

---

**Document Version**: 1.0
**Last Updated**: 2025-12-18
**Next Review**: Before Phase 1 implementation begins
