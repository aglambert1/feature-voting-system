# API Modularity Analysis

## Overview

This document analyzes how the feature-voting-system can be made more modular for external API consumption by agents or services, separate from the frontend UI.

---

## Functional Domains

The system provides 7 distinct functional domains:

| # | Domain | Description |
|---|--------|-------------|
| 1 | **Idea Submission & Voting** | Users submit feature ideas, vote on them |
| 2 | **Idea Triage** | AI-powered structuring and prioritization of ideas |
| 3 | **Product Analysis** | Parse product documentation to extract features |
| 4 | **Market Analysis** | Discover competitors in a market |
| 5 | **Competitor Analysis** | Analyze competitor features, identify gaps |
| 6 | **Internal Feedback** | Import and theme CRM/support data |
| 7 | **Opportunity Synthesis** | Combine all signals into prioritized opportunities |

---

## Modularity Assessment

### Tier 1: Ready for Independent API Use (Low Coupling)

These can be exposed as standalone APIs with minimal changes:

#### 1. Idea Submission & Voting
**Current endpoints:**
- `POST /ideas` - Create idea
- `GET /ideas` - List ideas
- `POST /ideas/{id}/vote` - Vote on idea
- `DELETE /ideas/{id}/vote` - Remove vote

**Dependencies:** User authentication only

**Changes needed:**
- Add API key authentication (in addition to JWT)
- Add rate limiting
- Document OpenAPI spec for external consumers

#### 6. Internal Feedback Import
**Current endpoints:**
- `POST /internal-feedback/win-loss` - Import win/loss data
- `POST /internal-feedback/support-tickets` - Import support themes

**Dependencies:** User authentication, product context

**Changes needed:**
- Add API key authentication
- Allow product context via header or parameter (not just session)

---

### Tier 2: Usable with Minor Refactoring (Medium Coupling)

#### 2. Idea Triage
**Current endpoints:**
- `GET /ideas/triage/queue` - Get triage queue
- `POST /ideas/triage/{id}/recommend` - Get AI recommendation
- `POST /ideas/triage/{id}/decide` - Accept/reject idea

**Why medium coupling:** Operations are async/long-running (10-60+ seconds). External callers need job tracking or callbacks, unlike UI which shows spinners.

**Changes needed:**
- Extract triage as standalone service
- Add webhook support for async completion
- Return structured response (not just UI-formatted)

#### 3. Product Analysis
**Current endpoints:**
- `POST /products` - Create product
- `POST /products/{id}/analyze` - Analyze from URL/document
- `GET /products/{id}/features` - Get extracted features

**Why medium coupling:** Long-running operations go through job queue. Response format is UI-optimized, not agent-friendly.

**Changes needed:**
- Add async job status endpoint for long-running analysis
- Support callback URL for completion notification
- Return machine-readable feature format (not just display text)

#### 4. Market Analysis (Competitor Discovery)
**Current endpoints:**
- `POST /products/{id}/competitors/discover` - Find competitors

**Why medium coupling:** Async operation, response shaped for UI display.

**Changes needed:**
- Add pagination for large result sets
- Support filtering by criteria
- Webhook/callback for completion

---

### Tier 3: Requires Significant Refactoring (High Coupling)

#### 5. Competitor Analysis
**Current state:** Tightly coupled workflow with multiple stages (Stage 0-3)

**Current endpoints:**
- `POST /products/{id}/competitors/{comp_id}/extract-features`
- `GET /competitive-agents/v2/{product_id}/functional-audit`
- `POST /competitive-agents/v2/{product_id}/cluster-features`

**Dependencies:** Product context, LLM service, vector service, feature clustering, session management

**Issues for external API use:**
- Workflow assumes sequential UI-driven steps
- State management tied to CompetitorAnalysisSession
- Complex job orchestration

**Changes needed:**
- Create stateless "analyze competitor" endpoint that runs full workflow
- Or: Expose each step as independent idempotent operation
- Add correlation ID for tracking multi-step workflows
- Support both sync (small competitors) and async (large) modes

#### 7. Opportunity Synthesis
**Current state:** Aggregates data from all other modules

**Current endpoints:**
- `POST /synthesis/{product_id}/run` - Trigger synthesis
- `GET /synthesis/{product_id}/opportunities` - Get results

**Dependencies:** All other modules (ideas, competitors, internal feedback)

**Issues for external API use:**
- Requires data from multiple domains to be populated first
- Long-running operation (minutes)
- Output format optimized for UI display

**Changes needed:**
- Accept external data sources (not just internal DB)
- Support incremental synthesis (add new signal, re-synthesize)
- Webhook/callback for completion
- Structured output format (JSON schema)

---

## Recommended Architecture Changes

### 1. Add API Key Authentication

Currently, all endpoints use JWT (OAuth2 password flow) designed for UI login. For external API access:

```python
# New: app/api/deps.py
from fastapi import Security
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_api_client(
    api_key: str = Security(api_key_header),
    db: Session = Depends(get_db)
) -> Optional[APIClient]:
    """Validate API key and return client context."""
    if not api_key:
        return None
    client = db.query(APIClient).filter(APIClient.key == api_key).first()
    if client and client.is_active:
        return client
    return None

async def require_auth(
    user: User = Depends(get_current_user_optional),
    api_client: APIClient = Depends(get_api_client)
):
    """Accept either JWT user or API key."""
    if user:
        return {"type": "user", "entity": user}
    if api_client:
        return {"type": "api_client", "entity": api_client}
    raise HTTPException(401, "Authentication required")
```

**New model needed:**
```python
class APIClient(Base):
    id: int
    name: str  # "Agent-ProductAnalyzer", "Integration-Salesforce"
    key: str  # hashed API key
    permissions: List[str]  # ["ideas:read", "products:analyze"]
    rate_limit: int  # requests per minute
    created_by: int  # FK to User
    is_active: bool
```

### 2. Add Webhook/Callback Support for Async Operations

Long-running operations (analysis, synthesis) should support callbacks:

```python
# New: Webhook callback on job completion
class JobCallbackRequest(BaseModel):
    callback_url: Optional[str] = None  # POST results here when done
    callback_headers: Optional[Dict[str, str]] = None  # Auth headers for callback

@router.post("/products/{id}/analyze")
async def analyze_product(
    id: int,
    request: AnalyzeRequest,
    callback: Optional[JobCallbackRequest] = None,
    auth = Depends(require_auth)
):
    job = queue_service.create_job(
        job_type=JobType.PRODUCT_ANALYSIS,
        payload={"product_id": id, ...},
        callback_url=callback.callback_url if callback else None,
        callback_headers=callback.callback_headers if callback else None
    )
    return {"job_id": job.id, "status": "queued"}
```

### 3. Create Domain-Specific API Routers

Separate internal (UI) and external (API) concerns:

```
app/api/
├── internal/           # UI-optimized endpoints (current)
│   ├── ideas.py
│   ├── products.py
│   └── ...
├── external/           # Agent/integration-optimized endpoints (new)
│   ├── v1/
│   │   ├── ideas.py        # Simplified CRUD + voting
│   │   ├── analysis.py     # Product + competitor analysis
│   │   ├── synthesis.py    # Opportunity synthesis
│   │   └── feedback.py     # Internal data import
│   └── webhooks.py         # Incoming webhooks from integrations
```

### 4. Standardize Response Formats

Current responses mix UI concerns with data. External API should use consistent envelope:

```python
# Standard API response
class APIResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[APIError] = None
    meta: Optional[APIMeta] = None

class APIMeta(BaseModel):
    request_id: str
    timestamp: datetime
    pagination: Optional[Pagination] = None
    job_id: Optional[str] = None  # For async operations

# Example response
{
    "success": true,
    "data": {
        "product_id": 123,
        "features": [...],
        "analysis_version": "2026-01-27T10:00:00Z"
    },
    "meta": {
        "request_id": "req_abc123",
        "timestamp": "2026-01-27T10:30:00Z"
    }
}
```

### 5. Decouple Synthesis from Internal Data

Allow synthesis to accept external data, not just DB queries:

```python
# Current: Synthesis pulls from internal DB only
@router.post("/synthesis/{product_id}/run")
async def run_synthesis(product_id: int):
    # Fetches ideas, competitors, feedback from DB
    ...

# New: Accept external signals
class SynthesisInput(BaseModel):
    # Option A: Use internal data
    product_id: Optional[int] = None

    # Option B: Provide external data directly
    competitive_signals: Optional[List[CompetitiveSignal]] = None
    customer_signals: Optional[List[CustomerSignal]] = None
    internal_signals: Optional[List[InternalSignal]] = None

@router.post("/v1/synthesis/run")
async def run_synthesis_v1(input: SynthesisInput):
    """Run synthesis with internal data, external data, or both."""
    ...
```

---

## Implementation Phases

### Phase 1: API Key Auth + Rate Limiting (1-2 days)
- Add APIClient model
- Create API key management endpoints (admin only)
- Add rate limiting middleware
- Update auth dependencies to accept both JWT and API key

### Phase 2: External API Router for Tier 1 (2-3 days)
- Create `/api/v1/` router structure
- Expose ideas and internal-feedback endpoints
- Add OpenAPI documentation
- Add request/response logging for API clients

### Phase 3: Webhook Support (1-2 days)
- Add callback_url support to job creation
- Implement webhook delivery in Celery worker
- Add retry logic for failed callbacks
- Create webhook event log

### Phase 4: Refactor Tier 2 Endpoints (3-5 days)
- Extract triage as standalone operations
- Simplify product analysis API
- Add market analysis as independent endpoint
- Standardize response formats

### Phase 5: Refactor Tier 3 Endpoints (5-8 days)
- Create stateless competitor analysis workflow
- Decouple synthesis from internal data sources
- Add correlation IDs for multi-step workflows
- Comprehensive testing

---

## Quick Wins (Can Do Now)

Without major refactoring, you can immediately:

1. **Document existing API** - Generate OpenAPI spec, share with agents
2. **Add API key auth** - 1 day of work, unlocks programmatic access
3. **Expose Tier 1 endpoints** - Ideas and feedback are ready now
4. **Add job status polling** - External clients poll `/jobs/{id}` instead of webhooks

---

## Dependency Graph for Modularity

```
┌─────────────────────────────────────────────────────────────┐
│                    EXTERNAL API LAYER                       │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────┐ │
│  │ Ideas   │  │Analysis │  │Synthesis│  │Internal Feedback│ │
│  │ Module  │  │ Module  │  │ Module  │  │    Module       │ │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────────┬────────┘ │
└───────┼────────────┼────────────┼────────────────┼──────────┘
        │            │            │                │
        ▼            ▼            ▼                ▼
┌───────────────────────────────────────────────────────────┐
│                    CORE SERVICES                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │ Auth &   │  │   LLM    │  │  Vector  │  │   Queue   │  │
│  │ Perms    │  │ Service  │  │ Service  │  │  Service  │  │
│  └──────────┘  └──────────┘  └──────────┘  └───────────┘  │
└───────────────────────────────────────────────────────────┘
        │            │            │                │
        ▼            ▼            ▼                ▼
┌───────────────────────────────────────────────────────────┐
│                    DATA LAYER                             │
│         PostgreSQL + pgvector + Redis (jobs)              │
└───────────────────────────────────────────────────────────┘
```

**Module Independence Score:**

| Module | Can Run Standalone? | External Dependencies |
|--------|--------------------|-----------------------|
| Ideas | ✅ Yes | Auth only |
| Internal Feedback | ✅ Yes | Auth only |
| Product Analysis | ⚠️ Partial | LLM, Document Parser |
| Market Analysis | ⚠️ Partial | LLM, Web Search |
| Competitor Analysis | ❌ No | Full stack |
| Synthesis | ❌ No | All modules |

---

## Recommended Next Steps

1. **Decide on API versioning strategy** (`/api/v1/` vs header-based)
2. **Define which modules you want to expose first** (recommend: Ideas + Internal Feedback)
3. **Choose webhook vs polling for async operations**
4. **Create API key management UI or CLI**

---

## Proposed External Competitive Analysis API

Two new endpoints to expose competitive analysis as a service to external systems.

### Design Decisions
- **Stateful:** Requires product to exist in database (caller creates product first via API)
- **Async:** Both operations are long-running; return job ID immediately, deliver results via webhook

---

### Endpoint 1: Single Competitor Analysis

Analyze one competitor against your product.

```
POST /api/v1/products/{product_id}/competitors/analyze
```

**Request:**
```json
{
  "competitor_url": "https://competitor.com",
  "competitor_name": "Competitor Inc",
  "analysis_depth": "standard",
  "callback_url": "https://your-system.com/webhook"
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `competitor_url` | Yes | URL to analyze |
| `competitor_name` | No | Will be discovered if omitted |
| `analysis_depth` | No | `"standard"` (default) or `"detailed"` |
| `callback_url` | No | Webhook URL for results; otherwise poll job status |

**Immediate Response:**
```json
{
  "job_id": "job_abc123",
  "status": "queued",
  "estimated_duration_seconds": 60
}
```

**Webhook Payload (on completion):**
```json
{
  "job_id": "job_abc123",
  "status": "completed",
  "data": {
    "competitor": {
      "id": 456,
      "name": "Competitor Inc",
      "url": "https://competitor.com",
      "features": [
        { "name": "Feature A", "description": "...", "category": "..." },
        ...
      ]
    },
    "gap_analysis": {
      "your_advantages": [
        { "feature": "...", "details": "..." }
      ],
      "their_advantages": [
        { "feature": "...", "details": "...", "priority": "high" }
      ],
      "feature_parity": [...],
      "recommendations": [
        { "action": "...", "rationale": "...", "effort": "medium" }
      ]
    }
  }
}
```

---

### Endpoint 2: Full Market Analysis

Discover competitors and analyze the full competitive landscape.

```
POST /api/v1/products/{product_id}/market/analyze
```

**Request:**
```json
{
  "max_competitors": 5,
  "include_landscape": true,
  "callback_url": "https://your-system.com/webhook"
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `max_competitors` | No | Cap competitor count (default: 5, max: 10) |
| `include_landscape` | No | Include synthesis/landscape analysis (default: true) |
| `callback_url` | No | Webhook URL for results |

**Immediate Response:**
```json
{
  "job_id": "job_xyz789",
  "status": "queued",
  "estimated_duration_seconds": 300
}
```

**Webhook Payload (on completion):**
```json
{
  "job_id": "job_xyz789",
  "status": "completed",
  "data": {
    "competitors_discovered": 5,
    "competitor_reports": [
      {
        "id": 456,
        "name": "Competitor A",
        "url": "https://...",
        "features": [...],
        "gap_analysis": {
          "your_advantages": [...],
          "their_advantages": [...],
          "feature_parity": [...]
        }
      },
      ...
    ],
    "landscape_analysis": {
      "market_positioning": "Your product leads in X, trails in Y...",
      "common_features": [
        { "feature": "...", "adoption": "4/5 competitors" }
      ],
      "differentiators": [
        { "feature": "...", "unique_to": "your_product" }
      ],
      "white_space_opportunities": [
        { "opportunity": "...", "rationale": "..." }
      ],
      "strategic_recommendations": [
        { "priority": "high", "action": "...", "rationale": "..." }
      ]
    }
  }
}
```

---

### Implementation Components

| Current Component | Role in New API |
|-------------------|-----------------|
| `competitor_intelligence_service.discover_competitors()` | Endpoint 2: find competitors |
| `competitor_intelligence_service.extract_features()` | Both: get competitor features |
| `feature_clustering_service` | Endpoint 2: landscape analysis |
| `product_service.get_features()` | Both: your product features for comparison |
| Functional audit gap analysis logic | Both: compare features |

**New code needed:**
1. **Orchestrator service** — chains discovery → extraction → gap analysis → landscape
2. **New API router** — `/api/v1/products/.../competitors/analyze`, `/api/v1/products/.../market/analyze`
3. **Webhook delivery** — in Celery worker (retry logic, event logging)
4. **Response formatters** — structured JSON output (not UI-shaped)

**Estimated effort:** 3-5 days for both endpoints with error handling and testing.

---

### Job Status Polling (Alternative to Webhooks)

If caller doesn't provide `callback_url`, they can poll:

```
GET /api/v1/jobs/{job_id}
```

**Response:**
```json
{
  "job_id": "job_abc123",
  "status": "running",
  "progress": 0.6,
  "started_at": "2026-01-27T10:00:00Z",
  "estimated_completion": "2026-01-27T10:01:00Z"
}
```

When complete:
```json
{
  "job_id": "job_abc123",
  "status": "completed",
  "completed_at": "2026-01-27T10:00:45Z",
  "result_url": "/api/v1/jobs/job_abc123/result"
}
```

Fetch results:
```
GET /api/v1/jobs/{job_id}/result
```

Returns the same payload as the webhook would deliver.
