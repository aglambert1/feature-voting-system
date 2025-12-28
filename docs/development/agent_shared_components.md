# Shared Agent Components

## Idea Normalizer

### Purpose
Convert any insight source into the unified idea format.

### Interface

```python
class IdeaNormalizer:
    async def normalize(
        self,
        source_type: str,
        source_data: dict,
        product_context: ProductContext
    ) -> NormalizedIdea:
        """
        Convert source-specific data to unified idea format
        """

class NormalizedIdea:
    idea_what: str
    idea_why: str
    idea_use_case: str
    source_type: str
    source_metadata: dict
    confidence: float
    needs_review: bool
```

### Source-Specific Normalization

#### Customer Submission
```python
# Input already structured, minimal transformation
def normalize_customer_submission(data: dict) -> NormalizedIdea:
    return NormalizedIdea(
        idea_what=data['description'],
        idea_why=data.get('why', ''),  # May need LLM to generate
        idea_use_case=data.get('use_case', ''),  # May need LLM to generate
        source_type='customer_submission',
        source_metadata={
            'submitter_id': data['user_id'],
            'submitted_at': data['created_at']
        },
        confidence=1.0,
        needs_review=False
    )
```

#### Competitor Feature
```python
# Requires anonymization and reframing
async def normalize_competitor_feature(
    data: dict, 
    product_context: ProductContext
) -> NormalizedIdea:
    
    prompt = f"""
    Convert this competitor feature to a product-agnostic idea.
    
    Feature: {data['feature_name']}
    Description: {data['feature_description']}
    
    Your product: {product_context.name}
    Your features: {product_context.features}
    
    Generate:
    - what: Feature description (no competitor names)
    - why: Business value
    - use_case: Concrete scenario
    
    Output JSON only.
    """
    
    result = await llm.generate(prompt)
    
    return NormalizedIdea(
        idea_what=result['what'],
        idea_why=result['why'],
        idea_use_case=result['use_case'],
        source_type='competitor_feature',
        source_metadata={
            'competitor_id': data['competitor_id'],
            'feature_id': data['feature_id'],
            'detected_at': data['detected_at'],
            'change_type': data.get('change_type', 'new')
        },
        confidence=0.85,
        needs_review=True  # PM should review before voting
    )
```

#### Future: Sales Lost Deal
```python
async def normalize_sales_lost(data: dict) -> NormalizedIdea:
    
    prompt = f"""
    Convert this lost deal reason to a product idea.
    
    Lost reason: {data['lost_reason']}
    Competitor mentioned: {data.get('competitor', 'None')}
    Deal context: {data.get('notes', '')}
    
    Generate:
    - what: Feature that would have won the deal
    - why: Business value
    - use_case: How prospect would use it
    
    Output JSON only.
    """
    
    result = await llm.generate(prompt)
    
    return NormalizedIdea(
        idea_what=result['what'],
        idea_why=result['why'],
        idea_use_case=result['use_case'],
        source_type='sales_lost',
        source_metadata={
            'opportunity_id': data['opportunity_id'],
            'deal_value': data.get('deal_value'),
            'competitor': data.get('competitor'),
            'lost_date': data['close_date']
        },
        confidence=0.75,
        needs_review=True
    )
```

---

## Similarity Detector

### Purpose
Find similar/duplicate ideas using vector embeddings.

### Interface

```python
class SimilarityDetector:
    async def find_similar(
        self,
        idea_text: str,
        product_id: UUID,
        threshold: float = 0.85,
        limit: int = 10
    ) -> List[SimilarIdea]:
        """Find ideas similar to the given text"""
    
    async def check_duplicate(
        self,
        idea_text: str,
        product_id: UUID,
        threshold: float = 0.95
    ) -> Optional[DuplicateResult]:
        """Check if idea is duplicate of existing"""
    
    async def cluster_ideas(
        self,
        product_id: UUID,
        min_cluster_size: int = 3
    ) -> List[IdeaCluster]:
        """Group similar ideas into clusters"""

class SimilarIdea:
    idea_id: UUID
    idea_what: str
    similarity_score: float
    vote_count: int
    status: str

class DuplicateResult:
    is_duplicate: bool
    duplicate_of: Optional[UUID]
    similarity_score: float
    recommendation: str  # 'merge', 'keep_separate', 'review'
```

### Implementation

```python
class SimilarityDetector:
    def __init__(self, llm_service: LLMService, db: Database):
        self.llm = llm_service
        self.db = db
    
    async def get_embedding(self, text: str) -> List[float]:
        """Generate embedding for text"""
        return await self.llm.embed(text)
    
    async def find_similar(
        self,
        idea_text: str,
        product_id: UUID,
        threshold: float = 0.85,
        limit: int = 10
    ) -> List[SimilarIdea]:
        
        # Generate embedding
        embedding = await self.get_embedding(idea_text)
        
        # Query pgvector
        query = """
            SELECT 
                id,
                idea_what,
                1 - (embedding <=> $1::vector) as similarity,
                vote_count,
                status
            FROM ideas
            WHERE product_id = $2
              AND 1 - (embedding <=> $1::vector) > $3
            ORDER BY similarity DESC
            LIMIT $4
        """
        
        results = await self.db.fetch(query, embedding, product_id, threshold, limit)
        
        return [SimilarIdea(**r) for r in results]
    
    async def check_duplicate(
        self,
        idea_text: str,
        product_id: UUID,
        threshold: float = 0.95
    ) -> Optional[DuplicateResult]:
        
        similar = await self.find_similar(idea_text, product_id, threshold, limit=1)
        
        if not similar:
            return DuplicateResult(
                is_duplicate=False,
                duplicate_of=None,
                similarity_score=0.0,
                recommendation='create_new'
            )
        
        top_match = similar[0]
        
        return DuplicateResult(
            is_duplicate=top_match.similarity_score >= threshold,
            duplicate_of=top_match.idea_id,
            similarity_score=top_match.similarity_score,
            recommendation='merge' if top_match.similarity_score >= threshold else 'review'
        )
```

---

## Product Analyzer Agent

### Purpose
Structure product descriptions from any input format.

### Interface

```python
class ProductAnalyzer:
    async def analyze(
        self,
        input_type: str,  # 'text', 'document', 'url'
        input_data: Union[str, bytes],
        existing_product: Optional[Product] = None  # For updates
    ) -> ProductAnalysis

class ProductAnalysis:
    product_name: str
    category: str
    description: str
    core_features: List[str]
    target_users: str
    value_propositions: List[str]
    competitor_search_keywords: List[str]
    confidence: float
```

### Prompt

```
You are a Product Analyzer. Structure this product information for competitive analysis.

Input: {input_content}

{if existing_product}
This is an UPDATE to an existing product:
Current name: {existing_product.name}
Current description: {existing_product.description}

Identify what has CHANGED vs. the existing definition.
{/if}

Extract:
1. product_name: Official product name
2. category: Industry/market category
3. description: 2-3 sentence summary
4. core_features: 5-7 key capabilities (list)
5. target_users: Who uses this product
6. value_propositions: 2-3 unique selling points
7. competitor_search_keywords: 5-10 terms to find competitors

Output JSON only.
```

---

## Comparison Engine

### Purpose
Generate feature comparisons between your product and competitors.

### Interface

```python
class ComparisonEngine:
    async def generate_comparison(
        self,
        product_id: UUID,
        competitor_ids: List[UUID]
    ) -> FeatureComparison

class FeatureComparison:
    your_advantages: List[FeatureGap]  # Features you have, they lack
    their_advantages: List[FeatureGap]  # Features they have, you lack
    parity_features: List[str]  # Features both have
    
class FeatureGap:
    feature_name: str
    feature_description: str
    your_product: bool
    competitors: Dict[str, bool]  # competitor_name -> has_feature
    customer_interest: Optional[int]  # Vote count if idea exists
```

### Implementation

```python
async def generate_comparison(
    self,
    product_id: UUID,
    competitor_ids: List[UUID]
) -> FeatureComparison:
    
    # Get your product's features
    your_features = await self.get_product_features(product_id)
    
    # Get competitor features
    competitor_features = {}
    for comp_id in competitor_ids:
        competitor_features[comp_id] = await self.get_competitor_features(comp_id)
    
    # Build comparison matrix
    all_features = set(your_features.keys())
    for comp_features in competitor_features.values():
        all_features.update(comp_features.keys())
    
    your_advantages = []
    their_advantages = []
    parity = []
    
    for feature in all_features:
        you_have = feature in your_features
        they_have = any(
            feature in comp_features 
            for comp_features in competitor_features.values()
        )
        
        if you_have and not they_have:
            your_advantages.append(feature)
        elif they_have and not you_have:
            # Check customer interest
            interest = await self.get_customer_interest(product_id, feature)
            their_advantages.append(FeatureGap(
                feature_name=feature,
                customer_interest=interest
            ))
        elif you_have and they_have:
            parity.append(feature)
    
    return FeatureComparison(
        your_advantages=your_advantages,
        their_advantages=their_advantages,
        parity_features=parity
    )
```

---

## Agent Execution Logger

### Purpose
Track all agent executions for debugging, monitoring, and cost analysis.

### Interface

```python
class AgentLogger:
    async def log_execution(
        self,
        agent_name: str,
        product_id: UUID,
        input_data: dict,
        output_data: dict,
        llm_tokens: int,
        execution_time_ms: int,
        status: str,
        error: Optional[str] = None
    ) -> UUID

    async def get_execution_history(
        self,
        product_id: UUID,
        agent_name: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> List[ExecutionLog]
```

### Schema

```sql
CREATE TABLE agent_execution_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name VARCHAR(100) NOT NULL,
    product_id UUID REFERENCES products(id),
    session_id UUID,  -- If part of larger session
    
    -- Execution details
    input_data JSONB,
    output_data JSONB,
    
    -- Metrics
    llm_tokens_input INTEGER,
    llm_tokens_output INTEGER,
    llm_cost_usd DECIMAL(10, 6),
    execution_time_ms INTEGER,
    
    -- Status
    status VARCHAR(50),  -- 'success', 'error', 'partial'
    error_message TEXT,
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_agent_logs_product ON agent_execution_logs(product_id);
CREATE INDEX idx_agent_logs_agent ON agent_execution_logs(agent_name);
CREATE INDEX idx_agent_logs_created ON agent_execution_logs(created_at);
```

---

## Base Agent Class

### Pattern for All Agents

```python
from abc import ABC, abstractmethod
from typing import TypeVar, Generic

InputT = TypeVar('InputT')
OutputT = TypeVar('OutputT')

class BaseAgent(ABC, Generic[InputT, OutputT]):
    def __init__(
        self,
        llm_service: LLMService,
        db: Database,
        logger: AgentLogger
    ):
        self.llm = llm_service
        self.db = db
        self.logger = logger
        self.agent_name = self.__class__.__name__
    
    @abstractmethod
    async def _execute(self, input_data: InputT) -> OutputT:
        """Agent-specific execution logic"""
        pass
    
    @abstractmethod
    def _build_prompt(self, input_data: InputT) -> str:
        """Build LLM prompt from input"""
        pass
    
    async def run(
        self,
        input_data: InputT,
        product_id: UUID
    ) -> OutputT:
        """Execute agent with logging"""
        
        start_time = time.time()
        tokens_used = 0
        
        try:
            # Execute
            result = await self._execute(input_data)
            
            # Log success
            execution_time = int((time.time() - start_time) * 1000)
            await self.logger.log_execution(
                agent_name=self.agent_name,
                product_id=product_id,
                input_data=input_data.__dict__,
                output_data=result.__dict__,
                llm_tokens=tokens_used,
                execution_time_ms=execution_time,
                status='success'
            )
            
            return result
            
        except Exception as e:
            # Log error
            execution_time = int((time.time() - start_time) * 1000)
            await self.logger.log_execution(
                agent_name=self.agent_name,
                product_id=product_id,
                input_data=input_data.__dict__,
                output_data={},
                llm_tokens=tokens_used,
                execution_time_ms=execution_time,
                status='error',
                error=str(e)
            )
            raise
```

---

## Queue Manager

### Purpose
Manage PM review queues across all agents.

### Interface

```python
class QueueManager:
    async def add_to_queue(
        self,
        queue_type: str,  # 'ideas', 'competitive_alerts', 'reports'
        product_id: UUID,
        item_id: UUID,
        priority: str = 'normal',
        metadata: dict = {}
    ) -> None
    
    async def get_queue(
        self,
        queue_type: str,
        product_id: UUID,
        status: str = 'pending'
    ) -> List[QueueItem]
    
    async def mark_reviewed(
        self,
        queue_type: str,
        item_id: UUID,
        action_taken: str,
        reviewed_by: UUID
    ) -> None

class QueueItem:
    item_id: UUID
    queue_type: str
    priority: str
    created_at: datetime
    metadata: dict
```

### Queue Types

| Queue | Item Source | PM Actions |
|-------|-------------|------------|
| `ideas` | Idea Triage Agent | Approve, Merge, Dismiss |
| `competitive_alerts` | Competitive Monitor | Create Ideas, Dismiss, Snooze |
| `reports` | Report Generator | View, Download, Regenerate |
