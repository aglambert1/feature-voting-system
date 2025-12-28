# Idea Triage Agent

## Purpose

Automatically processes new idea submissions to:
1. Send immediate acknowledgment to submitter
2. Find similar/duplicate ideas
3. Enrich with competitive context
4. Recommend actions to PM

## Trigger

- New idea submitted by customer or internal user
- Batch processing of backlog (on-demand)

## Inputs

```python
class IdeaTriageInput:
    idea_id: UUID
    product_id: UUID
    idea_what: str
    idea_why: str
    idea_use_case: str
    submitter_id: UUID
    submitter_type: str  # 'customer', 'internal'
```

## Processing Steps

### Step 1: Generate Embedding

```python
async def generate_embedding(idea_text: str) -> Vector:
    """
    Combine what/why/use_case into single text
    Generate embedding via LLM service
    Store in ideas.embedding column
    """
```

### Step 2: Find Similar Ideas

```python
async def find_similar_ideas(
    embedding: Vector, 
    product_id: UUID,
    threshold: float = 0.85
) -> List[SimilarIdea]:
    """
    Query pgvector for similar ideas within same product
    Return ranked list with similarity scores
    Flag potential duplicates (score > 0.95)
    """
    
class SimilarIdea:
    idea_id: UUID
    similarity_score: float
    idea_what: str
    vote_count: int
    status: str
    is_potential_duplicate: bool
```

### Step 3: Check Competitive Context

```python
async def check_competitive_context(
    idea_text: str,
    product_id: UUID
) -> CompetitiveContext:
    """
    Search competitor features for similar capabilities
    Return matches with competitor names (for PM view only)
    """
    
class CompetitiveContext:
    matching_competitor_features: List[FeatureMatch]
    competitors_with_feature: List[str]
    first_detected_date: Optional[datetime]
    
class FeatureMatch:
    competitor_name: str
    feature_name: str
    feature_description: str
    similarity_score: float
    detected_at: datetime
```

### Step 4: Generate Auto-Response

```python
async def generate_auto_response(
    idea: IdeaTriageInput,
    similar_ideas: List[SimilarIdea],
    competitive_context: CompetitiveContext,
    product_config: ProductConfig
) -> AutoResponse:
    """
    Use LLM to generate contextual acknowledgment
    Tone configurable per product
    Include: thanks, similar ideas mention (if any), next steps
    """

class AutoResponse:
    response_text: str
    mentions_similar: bool
    similar_idea_refs: List[UUID]
```

**Auto-Response Prompt Template:**

```
You are responding to a product idea submission. Generate a brief, friendly acknowledgment.

Product: {product_name}
Idea submitted: {idea_what}

Context:
- Similar ideas found: {similar_count}
- This capability exists at competitors: {yes/no}

Tone: {configured_tone}  # e.g., "professional", "friendly", "startup casual"

Generate a 2-3 sentence response that:
1. Thanks the submitter
2. If similar ideas exist, mention "we've seen related requests" (don't list specifics)
3. Set expectation for review timeline

Do NOT mention competitors. Do NOT promise implementation.
```

### Step 5: Generate PM Recommendation

```python
async def generate_recommendation(
    idea: IdeaTriageInput,
    similar_ideas: List[SimilarIdea],
    competitive_context: CompetitiveContext
) -> TriageRecommendation:
    """
    Determine recommended action for PM
    """

class TriageRecommendation:
    recommended_action: str  # 'approve', 'merge', 'needs_review', 'reject_duplicate'
    confidence: float
    reasoning: str
    merge_target_id: Optional[UUID]  # If recommending merge
    
# Logic:
# - If duplicate (similarity > 0.95): recommend merge with existing
# - If similar (0.85-0.95): recommend review, show related
# - If competitor has it: flag "competitive parity request"
# - Otherwise: recommend approve for voting
```

## Output

```python
class IdeaTriageResult:
    idea_id: UUID
    
    # Enrichment
    embedding: Vector
    similar_ideas: List[SimilarIdea]
    competitive_context: CompetitiveContext
    
    # Actions taken
    auto_response_sent: bool
    auto_response_text: str
    
    # PM queue item
    recommendation: TriageRecommendation
    queued_for_review: bool
    
    # Metadata
    processed_at: datetime
    processing_time_ms: int
```

## PM Review Queue Item

When PM views the Ideas queue, they see:

```
┌─────────────────────────────────────────────────────────────────┐
│ "Dark mode support"                          Submitted: 2h ago  │
│                                                                 │
│ Submitter: customer@example.com                                 │
│                                                                 │
│ Agent Assessment:                                               │
│ ├─ Similar to 2 existing ideas [view]                          │
│ ├─ Competitor X has this feature (detected 3 months ago)       │
│ └─ 4 previous requests mention "dark mode"                     │
│                                                                 │
│ Auto-Response Sent: ✓                                          │
│ "Thanks for your suggestion! We've received similar feedback   │
│  and your input helps us prioritize..."                        │
│                                                                 │
│ Recommendation: MERGE with idea #42 "Theme customization"      │
│ Confidence: 87%                                                 │
│                                                                 │
│ [Approve as New] [Merge with #42] [Edit Response] [Dismiss]    │
└─────────────────────────────────────────────────────────────────┘
```

## Configuration (Per Product)

```python
class IdeaTriageConfig:
    product_id: UUID
    
    # Auto-response settings
    auto_response_enabled: bool = True
    response_tone: str = "professional"  # 'professional', 'friendly', 'casual'
    
    # Similarity thresholds
    duplicate_threshold: float = 0.95
    similar_threshold: float = 0.85
    
    # Behavior
    auto_approve_below_similar_threshold: bool = False
    always_queue_for_review: bool = True
```

## Database Updates

```sql
-- Add to ideas table
ALTER TABLE ideas ADD COLUMN IF NOT EXISTS
    triage_status VARCHAR(50) DEFAULT 'pending',
    triage_recommendation JSONB,
    triage_processed_at TIMESTAMP,
    auto_response_sent_at TIMESTAMP,
    auto_response_text TEXT;

-- Triage queue view
CREATE VIEW idea_triage_queue AS
SELECT 
    i.*,
    i.triage_recommendation->>'recommended_action' as recommended_action,
    i.triage_recommendation->>'confidence' as recommendation_confidence
FROM ideas i
WHERE i.triage_status = 'pending_review'
ORDER BY i.created_at DESC;
```

## Error Handling

- If LLM fails: Queue for manual review, skip auto-response
- If similarity search fails: Proceed without similar ideas, flag for review
- If competitive context fails: Proceed without, note in recommendation

## Metrics

- Ideas processed per day
- Average processing time
- Auto-response sent rate
- Recommendation accuracy (PM agreement rate)
- Merge recommendation accuracy
