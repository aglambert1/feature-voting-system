# Source Adapter Pattern

## Purpose

Define a consistent pattern for integrating external data sources (CRM, support tools, etc.) into the unified product insight system.

All sources normalize to the same idea format, enabling:
- Unified customer voting across all insight types
- Consistent PM review experience
- Cross-source analytics and reporting

---

## Adapter Interface

```python
from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime

class SourceAdapter(ABC):
    """Base class for all insight source adapters"""
    
    source_type: str  # Unique identifier for this source
    display_name: str  # Human-readable name
    
    @abstractmethod
    async def connect(self, credentials: dict) -> bool:
        """Establish connection to external system"""
        pass
    
    @abstractmethod
    async def test_connection(self) -> ConnectionStatus:
        """Verify connection is working"""
        pass
    
    @abstractmethod
    async def fetch_insights(
        self,
        since: Optional[datetime] = None,
        filters: Optional[dict] = None
    ) -> List[RawInsight]:
        """Fetch raw data from source"""
        pass
    
    @abstractmethod
    async def normalize(
        self,
        raw_insight: RawInsight,
        product_context: ProductContext
    ) -> NormalizedIdea:
        """Convert source-specific data to unified idea format"""
        pass
    
    async def sync(
        self,
        product_id: UUID,
        since: Optional[datetime] = None
    ) -> SyncResult:
        """Full sync: fetch + normalize + store"""
        
        # Fetch from source
        raw_insights = await self.fetch_insights(since=since)
        
        # Get product context for normalization
        product_context = await self.get_product_context(product_id)
        
        # Normalize each insight
        normalized = []
        for raw in raw_insights:
            try:
                idea = await self.normalize(raw, product_context)
                normalized.append(idea)
            except NormalizationError as e:
                # Log and continue
                pass
        
        # Dedupe against existing ideas
        unique_ideas = await self.dedupe(normalized, product_id)
        
        # Store in ideas table
        stored = await self.store_ideas(unique_ideas, product_id)
        
        return SyncResult(
            source_type=self.source_type,
            fetched=len(raw_insights),
            normalized=len(normalized),
            stored=len(stored),
            duplicates_skipped=len(normalized) - len(unique_ideas)
        )

class RawInsight:
    """Source-specific raw data"""
    source_id: str  # ID in source system
    source_type: str
    raw_data: dict
    fetched_at: datetime

class NormalizedIdea:
    """Unified idea format"""
    idea_what: str
    idea_why: str
    idea_use_case: str
    source_type: str
    source_metadata: dict
    confidence: float
    needs_review: bool

class SyncResult:
    source_type: str
    fetched: int
    normalized: int
    stored: int
    duplicates_skipped: int
    errors: List[str]
```

---

## Implemented Adapters

### 1. Customer Submission Adapter (Built-in)

```python
class CustomerSubmissionAdapter(SourceAdapter):
    source_type = "customer_submission"
    display_name = "Customer Ideas"
    
    async def fetch_insights(self, since=None, filters=None):
        # Already in system - no external fetch needed
        pass
    
    async def normalize(self, raw_insight, product_context):
        # Minimal transformation - already structured
        return NormalizedIdea(
            idea_what=raw_insight.raw_data['description'],
            idea_why=raw_insight.raw_data.get('why', await self.generate_why(raw_insight)),
            idea_use_case=raw_insight.raw_data.get('use_case', await self.generate_use_case(raw_insight)),
            source_type=self.source_type,
            source_metadata={
                'submitter_id': raw_insight.raw_data['user_id'],
                'submitted_at': raw_insight.raw_data['created_at']
            },
            confidence=1.0,
            needs_review=False
        )
```

### 2. Competitor Feature Adapter (Built-in)

```python
class CompetitorFeatureAdapter(SourceAdapter):
    source_type = "competitor_feature"
    display_name = "Competitive Intelligence"
    
    async def fetch_insights(self, since=None, filters=None):
        # Fetched by Competitive Monitor agent
        # This adapter normalizes already-extracted features
        pass
    
    async def normalize(self, raw_insight, product_context):
        # Anonymize and reframe competitor feature
        prompt = self.build_anonymization_prompt(raw_insight, product_context)
        result = await self.llm.generate(prompt)
        
        return NormalizedIdea(
            idea_what=result['what'],
            idea_why=result['why'],
            idea_use_case=result['use_case'],
            source_type=self.source_type,
            source_metadata={
                'competitor_id': raw_insight.raw_data['competitor_id'],
                'feature_id': raw_insight.raw_data['feature_id'],
                'detected_at': raw_insight.raw_data['detected_at'],
                'change_type': raw_insight.raw_data.get('change_type', 'new')
            },
            confidence=0.85,
            needs_review=True
        )
```

---

## Future Adapters (Templates)

### 3. Salesforce Adapter (CRM - Lost Deals)

```python
class SalesforceAdapter(SourceAdapter):
    source_type = "salesforce_lost_deal"
    display_name = "Salesforce Lost Deals"
    
    async def connect(self, credentials: dict) -> bool:
        """
        credentials = {
            'instance_url': 'https://company.salesforce.com',
            'access_token': '...',
            'refresh_token': '...'
        }
        """
        self.client = SalesforceClient(
            instance_url=credentials['instance_url'],
            access_token=credentials['access_token']
        )
        return await self.test_connection()
    
    async def fetch_insights(self, since=None, filters=None):
        # Query closed-lost opportunities with competitor/feature mentions
        query = """
            SELECT Id, Name, CloseDate, Amount, 
                   Loss_Reason__c, Competitor__c, 
                   Feature_Requests__c, Account.Name
            FROM Opportunity
            WHERE StageName = 'Closed Lost'
            AND CloseDate >= {since}
            AND (Loss_Reason__c LIKE '%feature%' 
                 OR Loss_Reason__c LIKE '%competitor%'
                 OR Feature_Requests__c != null)
        """
        
        results = await self.client.query(query.format(since=since))
        
        return [
            RawInsight(
                source_id=r['Id'],
                source_type=self.source_type,
                raw_data=r,
                fetched_at=datetime.now()
            )
            for r in results
        ]
    
    async def normalize(self, raw_insight, product_context):
        data = raw_insight.raw_data
        
        # Use LLM to extract feature request from loss reason
        prompt = f"""
        Extract a product feature idea from this lost deal.
        
        Loss reason: {data.get('Loss_Reason__c', '')}
        Feature requests mentioned: {data.get('Feature_Requests__c', '')}
        Competitor: {data.get('Competitor__c', '')}
        Account: {data.get('Account', {}).get('Name', '')}
        
        Generate:
        - what: The feature that would have won this deal
        - why: Business value
        - use_case: How the prospect would use it
        
        Output JSON only.
        """
        
        result = await self.llm.generate(prompt)
        
        return NormalizedIdea(
            idea_what=result['what'],
            idea_why=result['why'],
            idea_use_case=result['use_case'],
            source_type=self.source_type,
            source_metadata={
                'opportunity_id': data['Id'],
                'opportunity_name': data['Name'],
                'deal_value': data.get('Amount'),
                'account_name': data.get('Account', {}).get('Name'),
                'competitor_mentioned': data.get('Competitor__c'),
                'close_date': data['CloseDate']
            },
            confidence=0.75,
            needs_review=True
        )
```

### 4. Zendesk Adapter (Support Tickets)

```python
class ZendeskAdapter(SourceAdapter):
    source_type = "zendesk_ticket"
    display_name = "Zendesk Support Tickets"
    
    async def connect(self, credentials: dict) -> bool:
        """
        credentials = {
            'subdomain': 'company',
            'email': 'admin@company.com',
            'api_token': '...'
        }
        """
        self.client = ZendeskClient(
            subdomain=credentials['subdomain'],
            email=credentials['email'],
            api_token=credentials['api_token']
        )
        return await self.test_connection()
    
    async def fetch_insights(self, since=None, filters=None):
        # Fetch tickets tagged as feature requests
        tickets = await self.client.search(
            query=f'type:ticket tags:feature_request created>{since}',
            sort_by='created_at',
            sort_order='desc'
        )
        
        return [
            RawInsight(
                source_id=str(t['id']),
                source_type=self.source_type,
                raw_data=t,
                fetched_at=datetime.now()
            )
            for t in tickets
        ]
    
    async def normalize(self, raw_insight, product_context):
        data = raw_insight.raw_data
        
        prompt = f"""
        Extract a product feature idea from this support ticket.
        
        Subject: {data['subject']}
        Description: {data['description'][:1000]}
        Tags: {data.get('tags', [])}
        
        Generate:
        - what: The feature being requested
        - why: Why the customer needs it
        - use_case: Specific scenario
        
        Output JSON only.
        """
        
        result = await self.llm.generate(prompt)
        
        return NormalizedIdea(
            idea_what=result['what'],
            idea_why=result['why'],
            idea_use_case=result['use_case'],
            source_type=self.source_type,
            source_metadata={
                'ticket_id': data['id'],
                'subject': data['subject'],
                'requester_id': data.get('requester_id'),
                'organization': data.get('organization', {}).get('name'),
                'priority': data.get('priority'),
                'created_at': data['created_at']
            },
            confidence=0.70,
            needs_review=True
        )
```

### 5. Intercom Adapter (Conversations)

```python
class IntercomAdapter(SourceAdapter):
    source_type = "intercom_conversation"
    display_name = "Intercom Conversations"
    
    # Similar pattern to Zendesk
    # Fetch conversations tagged as feedback
    # Extract feature requests using LLM
```

### 6. Gong Adapter (Call Intelligence)

```python
class GongAdapter(SourceAdapter):
    source_type = "gong_call"
    display_name = "Gong Call Intelligence"
    
    async def fetch_insights(self, since=None, filters=None):
        # Fetch calls with feature request keywords
        # Or calls where competitors were mentioned
        calls = await self.client.get_calls(
            from_date=since,
            filters={
                'trackers': ['feature_request', 'competitor_mention']
            }
        )
        
        # Include transcript snippets where keywords appeared
        return [self.extract_relevant_snippets(call) for call in calls]
    
    async def normalize(self, raw_insight, product_context):
        # Extract feature ideas from call transcript
        pass
```

### 7. App Store Reviews Adapter

```python
class AppStoreAdapter(SourceAdapter):
    source_type = "app_store_review"
    display_name = "App Store Reviews"
    
    async def connect(self, credentials: dict) -> bool:
        """
        credentials = {
            'app_id': '123456789',
            'platform': 'ios'  # or 'android'
        }
        """
        self.app_id = credentials['app_id']
        self.platform = credentials['platform']
        return True
    
    async def fetch_insights(self, since=None, filters=None):
        # Use public API or scraping service
        reviews = await self.review_service.fetch(
            app_id=self.app_id,
            platform=self.platform,
            since=since,
            min_rating=1,  # Get all ratings
            max_rating=4   # Focus on feedback, not praise
        )
        
        return [
            RawInsight(
                source_id=r['id'],
                source_type=self.source_type,
                raw_data=r,
                fetched_at=datetime.now()
            )
            for r in reviews
        ]
    
    async def normalize(self, raw_insight, product_context):
        data = raw_insight.raw_data
        
        # Filter: Only normalize if it contains feature request
        if not await self.contains_feature_request(data['text']):
            raise NormalizationError("Review doesn't contain feature request")
        
        prompt = f"""
        Extract a product feature idea from this app review.
        
        Rating: {data['rating']}/5
        Review: {data['text']}
        
        Generate:
        - what: The feature being requested
        - why: Why the user wants it
        - use_case: How they would use it
        
        Output JSON only. If no clear feature request, return null.
        """
        
        result = await self.llm.generate(prompt)
        
        if result is None:
            raise NormalizationError("No feature request found")
        
        return NormalizedIdea(
            idea_what=result['what'],
            idea_why=result['why'],
            idea_use_case=result['use_case'],
            source_type=self.source_type,
            source_metadata={
                'review_id': data['id'],
                'rating': data['rating'],
                'platform': self.platform,
                'review_date': data['date']
            },
            confidence=0.60,
            needs_review=True
        )
```

---

## Source Configuration UI

```
┌─────────────────────────────────────────────────────────────────┐
│  Settings: Data Sources                          [+ Add Source] │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Connected Sources                                              │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ✓ Customer Ideas (built-in)                  Active     │   │
│  │   Last sync: Continuous                                 │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ✓ Competitive Intelligence (built-in)        Active     │   │
│  │   Last sync: 2 hours ago                    [Sync Now]  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ✓ Salesforce                                 Active     │   │
│  │   Connected as: admin@company.com                       │   │
│  │   Last sync: 1 day ago (47 insights)        [Sync Now]  │   │
│  │   [Configure] [Disconnect]                              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Available Sources                                              │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ○ Zendesk                                    [Connect]  │   │
│  │   Import feature requests from support tickets          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ○ Intercom                                   [Connect]  │   │
│  │   Import feedback from customer conversations           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ○ Gong                                       [Connect]  │   │
│  │   Import feature requests from sales calls              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Database Schema

```sql
-- Source configurations
CREATE TABLE source_configurations (
    id UUID PRIMARY KEY,
    product_id UUID REFERENCES products(id),
    source_type VARCHAR(100) NOT NULL,
    display_name VARCHAR(255),
    credentials_encrypted BYTEA,  -- Encrypted OAuth tokens, API keys
    config JSONB,  -- Source-specific settings
    enabled BOOLEAN DEFAULT true,
    last_sync_at TIMESTAMP,
    last_sync_result JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(product_id, source_type)
);

-- Sync history
CREATE TABLE source_sync_history (
    id UUID PRIMARY KEY,
    source_config_id UUID REFERENCES source_configurations(id),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    status VARCHAR(50),  -- 'success', 'partial', 'failed'
    insights_fetched INTEGER,
    insights_normalized INTEGER,
    insights_stored INTEGER,
    duplicates_skipped INTEGER,
    errors JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Extended ideas table for source tracking
ALTER TABLE ideas ADD COLUMN IF NOT EXISTS
    source_config_id UUID REFERENCES source_configurations(id),
    external_source_id VARCHAR(255),  -- ID in source system
    UNIQUE(source_config_id, external_source_id);
```

---

## Adding a New Source

1. **Create adapter class** implementing `SourceAdapter`
2. **Define credentials schema** for OAuth/API keys
3. **Implement fetch logic** for source's API
4. **Create normalization prompt** for LLM
5. **Add to UI** in available sources list
6. **Test thoroughly** with sample data
