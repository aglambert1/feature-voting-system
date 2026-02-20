# Cost Instrumentation Implementation

## Goal
Add tracking to measure LLM costs per user, per operation, so you can price correctly and identify heavy users.

---

## Overview

Add a lightweight cost tracking layer that:
1. Logs every LLM call with token counts and estimated cost
2. Tags by user and operation type
3. Stores in database for querying
4. Provides simple reporting endpoints

---

## Step 1: Create Cost Tracking Model

**File:** `backend/app/models/cost_tracking.py` (new file)

```python
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base


class OperationType(str, enum.Enum):
    IDEA_TRIAGE = "idea_triage"
    IDEA_STRUCTURING = "idea_structuring"
    PRODUCT_ANALYSIS = "product_analysis"
    COMPETITOR_DISCOVERY = "competitor_discovery"
    COMPETITOR_FEATURE_EXTRACTION = "competitor_feature_extraction"
    GAP_ANALYSIS = "gap_analysis"
    OPPORTUNITY_SYNTHESIS = "opportunity_synthesis"
    OTHER = "other"


class LLMUsageLog(Base):
    __tablename__ = "llm_usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    operation_type = Column(Enum(OperationType), nullable=False, index=True)

    # Token counts
    input_tokens = Column(Integer, nullable=False)
    output_tokens = Column(Integer, nullable=False)

    # Cost calculation
    model = Column(String, nullable=False)
    estimated_cost_usd = Column(Float, nullable=False)

    # Context
    product_id = Column(Integer, ForeignKey("ci_products.id"), nullable=True)
    job_id = Column(String, nullable=True)  # Link to QueueJob if applicable

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", backref="llm_usage_logs")
```

**Add to models/__init__.py:**
```python
from app.models.cost_tracking import LLMUsageLog, OperationType
```

---

## Step 2: Create Cost Calculation Utility

**File:** `backend/app/services/cost_calculator.py` (new file)

```python
from typing import Optional
from datetime import datetime

# Pricing as of Jan 2025 - update as needed
# https://www.anthropic.com/pricing
MODEL_PRICING = {
    "claude-sonnet-4-20250514": {
        "input_per_1m": 3.00,
        "output_per_1m": 15.00,
    },
    "claude-haiku-3-5-20241022": {
        "input_per_1m": 0.80,
        "output_per_1m": 4.00,
    },
    # Add other models as needed
}

# Default fallback for unknown models
DEFAULT_PRICING = {
    "input_per_1m": 3.00,
    "output_per_1m": 15.00,
}


def calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int
) -> float:
    """Calculate estimated cost in USD for an LLM call."""
    pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)

    input_cost = (input_tokens / 1_000_000) * pricing["input_per_1m"]
    output_cost = (output_tokens / 1_000_000) * pricing["output_per_1m"]

    return round(input_cost + output_cost, 6)


def format_cost(cost_usd: float) -> str:
    """Format cost for display."""
    if cost_usd < 0.01:
        return f"${cost_usd:.4f}"
    return f"${cost_usd:.2f}"
```

---

## Step 3: Create Cost Tracking Service

**File:** `backend/app/services/cost_tracking_service.py` (new file)

```python
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.cost_tracking import LLMUsageLog, OperationType
from app.services.cost_calculator import calculate_cost


class CostTrackingService:
    def __init__(self, db: Session):
        self.db = db

    def log_usage(
        self,
        operation_type: OperationType,
        model: str,
        input_tokens: int,
        output_tokens: int,
        user_id: Optional[int] = None,
        product_id: Optional[int] = None,
        job_id: Optional[str] = None,
    ) -> LLMUsageLog:
        """Log an LLM usage event."""
        estimated_cost = calculate_cost(model, input_tokens, output_tokens)

        log = LLMUsageLog(
            user_id=user_id,
            operation_type=operation_type,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimated_cost,
            product_id=product_id,
            job_id=job_id,
        )

        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)

        return log

    def get_user_costs(
        self,
        user_id: int,
        days: int = 30
    ) -> dict:
        """Get cost summary for a user over the last N days."""
        since = datetime.utcnow() - timedelta(days=days)

        logs = self.db.query(LLMUsageLog).filter(
            LLMUsageLog.user_id == user_id,
            LLMUsageLog.created_at >= since
        ).all()

        total_cost = sum(log.estimated_cost_usd for log in logs)
        by_operation = {}

        for log in logs:
            op = log.operation_type.value
            if op not in by_operation:
                by_operation[op] = {"count": 0, "cost": 0.0}
            by_operation[op]["count"] += 1
            by_operation[op]["cost"] += log.estimated_cost_usd

        return {
            "user_id": user_id,
            "period_days": days,
            "total_cost_usd": round(total_cost, 4),
            "total_requests": len(logs),
            "by_operation": by_operation,
        }

    def get_system_costs(
        self,
        days: int = 30
    ) -> dict:
        """Get system-wide cost summary."""
        since = datetime.utcnow() - timedelta(days=days)

        # Total costs
        result = self.db.query(
            func.count(LLMUsageLog.id).label("count"),
            func.sum(LLMUsageLog.estimated_cost_usd).label("total_cost"),
            func.sum(LLMUsageLog.input_tokens).label("input_tokens"),
            func.sum(LLMUsageLog.output_tokens).label("output_tokens"),
        ).filter(LLMUsageLog.created_at >= since).first()

        # By operation
        by_operation = self.db.query(
            LLMUsageLog.operation_type,
            func.count(LLMUsageLog.id).label("count"),
            func.sum(LLMUsageLog.estimated_cost_usd).label("cost"),
        ).filter(
            LLMUsageLog.created_at >= since
        ).group_by(LLMUsageLog.operation_type).all()

        # By user (top 10)
        by_user = self.db.query(
            LLMUsageLog.user_id,
            func.count(LLMUsageLog.id).label("count"),
            func.sum(LLMUsageLog.estimated_cost_usd).label("cost"),
        ).filter(
            LLMUsageLog.created_at >= since,
            LLMUsageLog.user_id.isnot(None)
        ).group_by(LLMUsageLog.user_id).order_by(
            func.sum(LLMUsageLog.estimated_cost_usd).desc()
        ).limit(10).all()

        return {
            "period_days": days,
            "total_requests": result.count or 0,
            "total_cost_usd": round(result.total_cost or 0, 4),
            "total_input_tokens": result.input_tokens or 0,
            "total_output_tokens": result.output_tokens or 0,
            "by_operation": {
                op.value: {"count": count, "cost": round(cost, 4)}
                for op, count, cost in by_operation
            },
            "top_users": [
                {"user_id": uid, "count": count, "cost": round(cost, 4)}
                for uid, count, cost in by_user
            ],
        }
```

---

## Step 4: Integrate with LLM Service

**File:** `backend/app/services/llm_service.py`

Find the main function that calls the Anthropic API (likely `call_claude`, `generate`, or similar). Wrap it to track usage.

**Add imports at top:**
```python
from app.models.cost_tracking import OperationType
from app.services.cost_tracking_service import CostTrackingService
```

**Add tracking context (class attribute or thread-local):**
```python
# Add to LLMService class or as module-level context
from contextvars import ContextVar

# Context for tracking - set before LLM calls
llm_context: ContextVar[dict] = ContextVar("llm_context", default={})

def set_llm_context(
    operation_type: OperationType,
    user_id: int = None,
    product_id: int = None,
    job_id: str = None
):
    """Set context for LLM cost tracking."""
    llm_context.set({
        "operation_type": operation_type,
        "user_id": user_id,
        "product_id": product_id,
        "job_id": job_id,
    })
```

**Modify the API call function to log usage:**
```python
async def call_claude(self, prompt: str, ...) -> str:
    """Call Claude API with cost tracking."""

    response = await self.client.messages.create(
        model=self.model,
        messages=[{"role": "user", "content": prompt}],
        ...
    )

    # Track costs
    ctx = llm_context.get()
    if ctx and self.db:
        tracker = CostTrackingService(self.db)
        tracker.log_usage(
            operation_type=ctx.get("operation_type", OperationType.OTHER),
            model=self.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            user_id=ctx.get("user_id"),
            product_id=ctx.get("product_id"),
            job_id=ctx.get("job_id"),
        )

    return response.content[0].text
```

---

## Step 5: Set Context Before Operations

Update each service that uses the LLM to set context. Example:

**File:** `backend/app/services/idea_normalizer_service.py`
```python
from app.services.llm_service import set_llm_context
from app.models.cost_tracking import OperationType

async def normalize_idea(self, idea_text: str, user_id: int = None):
    # Set context before LLM call
    set_llm_context(
        operation_type=OperationType.IDEA_STRUCTURING,
        user_id=user_id
    )

    # Existing LLM call
    result = await self.llm_service.call_claude(...)
    return result
```

**File:** `backend/app/services/competitor_intelligence_service.py`
```python
async def extract_features(self, competitor_id: int, user_id: int = None, product_id: int = None):
    set_llm_context(
        operation_type=OperationType.COMPETITOR_FEATURE_EXTRACTION,
        user_id=user_id,
        product_id=product_id
    )

    result = await self.llm_service.call_claude(...)
    return result
```

**Apply similar pattern to:**
- `product_service.py` → `OperationType.PRODUCT_ANALYSIS`
- `competitor_intelligence_service.py` (discover) → `OperationType.COMPETITOR_DISCOVERY`
- Any synthesis/opportunity code → `OperationType.OPPORTUNITY_SYNTHESIS`
- Idea triage recommendations → `OperationType.IDEA_TRIAGE`

---

## Step 6: Add Admin Reporting Endpoint

**File:** `backend/app/api/admin.py` (new or existing admin router)

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_admin_user
from app.services.cost_tracking_service import CostTrackingService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/costs/summary")
async def get_cost_summary(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    """Get system-wide LLM cost summary. Admin only."""
    tracker = CostTrackingService(db)
    return tracker.get_system_costs(days=days)


@router.get("/costs/user/{user_id}")
async def get_user_costs(
    user_id: int,
    days: int = 30,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    """Get LLM costs for a specific user. Admin only."""
    tracker = CostTrackingService(db)
    return tracker.get_user_costs(user_id=user_id, days=days)
```

**Register router in main.py:**
```python
from app.api import admin
app.include_router(admin.router)
```

---

## Step 7: Run Migration

After creating the model, generate and run migration:

```bash
# If using Alembic
alembic revision --autogenerate -m "add llm usage tracking"
alembic upgrade head

# If not using Alembic yet, you can create table directly for now
# Add to database.py init or run manually:
# Base.metadata.create_all(bind=engine)
```

---

## Verification

After implementation, verify by:

1. **Make an LLM call** (e.g., triage an idea)
2. **Check the database:**
   ```sql
   SELECT * FROM llm_usage_logs ORDER BY created_at DESC LIMIT 10;
   ```
3. **Call the admin endpoint:**
   ```bash
   curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/admin/costs/summary
   ```

---

## Expected Output

After a week of usage, you'll have data like:

```json
{
  "period_days": 7,
  "total_requests": 156,
  "total_cost_usd": 12.34,
  "by_operation": {
    "competitor_feature_extraction": {"count": 45, "cost": 6.75},
    "product_analysis": {"count": 12, "cost": 2.40},
    "idea_structuring": {"count": 89, "cost": 2.67},
    "opportunity_synthesis": {"count": 10, "cost": 0.52}
  },
  "top_users": [
    {"user_id": 5, "count": 42, "cost": 4.20},
    {"user_id": 3, "count": 31, "cost": 3.10}
  ]
}
```

This tells you:
- Average cost per user: ~$1.76/week (extrapolate to ~$7/month)
- Most expensive operation: competitor feature extraction
- Power users vs casual users

---

## Optional: Real-time Alerts

Add a check for runaway costs:

```python
# In cost_tracking_service.py
def check_daily_limit(self, limit_usd: float = 50.0) -> bool:
    """Return True if daily spending exceeds limit."""
    today = datetime.utcnow().date()

    total = self.db.query(
        func.sum(LLMUsageLog.estimated_cost_usd)
    ).filter(
        func.date(LLMUsageLog.created_at) == today
    ).scalar() or 0

    return total > limit_usd
```

Call this before expensive operations to circuit-break if costs are spiking.
