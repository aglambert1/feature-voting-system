# Module 1: Database Schema & Models

## Objective
Create the complete database schema for the competitor intelligence system with SQLAlchemy models and Pydantic schemas for API validation.

## Dependencies
- Existing: PostgreSQL database, Alembic migrations, SQLAlchemy, users table
- None (this is the foundation module)

## Scope
- Create 8 new database tables
- Create SQLAlchemy ORM models
- Create Pydantic schemas for API requests/responses
- Create and test Alembic migration

## Database Tables to Create

### 1. ci_products
```sql
CREATE TABLE ci_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_name VARCHAR(255) NOT NULL,
    product_description TEXT NOT NULL,
    product_category VARCHAR(100),
    structured_product_data JSONB,
    last_analyzed_at TIMESTAMP,
    analysis_count INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_user_product UNIQUE(user_id, product_name)
);

CREATE INDEX idx_ci_products_user ON ci_products(user_id);
CREATE INDEX idx_ci_products_status ON ci_products(status);
CREATE INDEX idx_ci_products_last_analyzed ON ci_products(last_analyzed_at);
```

### 2. competitor_analysis_sessions
```sql
CREATE TABLE competitor_analysis_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES ci_products(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id),
    session_number INTEGER NOT NULL,
    session_name VARCHAR(255),
    analysis_type VARCHAR(50) NOT NULL DEFAULT 'full',
    comparison_to_session_id UUID REFERENCES competitor_analysis_sessions(id),
    product_source_type VARCHAR(50) NOT NULL,
    product_source_data JSONB,
    analyzed_product_structure JSONB,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX idx_ci_sessions_product ON competitor_analysis_sessions(product_id);
CREATE INDEX idx_ci_sessions_user ON competitor_analysis_sessions(user_id);
CREATE INDEX idx_ci_sessions_status ON competitor_analysis_sessions(status);
CREATE INDEX idx_ci_sessions_comparison ON competitor_analysis_sessions(comparison_to_session_id);
```

### 3. product_competitors
```sql
CREATE TABLE product_competitors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES ci_products(id) ON DELETE CASCADE,
    competitor_name VARCHAR(255) NOT NULL,
    competitor_url VARCHAR(500),
    first_discovered_session_id UUID NOT NULL REFERENCES competitor_analysis_sessions(id),
    last_seen_session_id UUID REFERENCES competitor_analysis_sessions(id),
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_product_competitor UNIQUE(product_id, competitor_name)
);

CREATE INDEX idx_product_competitors_product ON product_competitors(product_id);
CREATE INDEX idx_product_competitors_status ON product_competitors(status);
```

### 4. session_competitors
```sql
CREATE TABLE session_competitors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES competitor_analysis_sessions(id) ON DELETE CASCADE,
    product_competitor_id UUID REFERENCES product_competitors(id),
    competitor_name VARCHAR(255) NOT NULL,
    competitor_url VARCHAR(500),
    ai_summary TEXT,
    discovery_source VARCHAR(50) NOT NULL,
    is_new_discovery BOOLEAN DEFAULT FALSE,
    selected_by_user BOOLEAN DEFAULT FALSE,
    discovery_rank INTEGER,
    status_change VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_session_competitors_session ON session_competitors(session_id);
CREATE INDEX idx_session_competitors_product_comp ON session_competitors(product_competitor_id);
CREATE INDEX idx_session_competitors_new ON session_competitors(is_new_discovery);
CREATE INDEX idx_session_competitors_selected ON session_competitors(selected_by_user);
```

### 5. product_competitor_features
```sql
CREATE TABLE product_competitor_features (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_competitor_id UUID NOT NULL REFERENCES product_competitors(id) ON DELETE CASCADE,
    feature_name VARCHAR(255) NOT NULL,
    feature_description TEXT,
    feature_category VARCHAR(100),
    first_discovered_session_id UUID NOT NULL REFERENCES competitor_analysis_sessions(id),
    last_seen_session_id UUID REFERENCES competitor_analysis_sessions(id),
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_product_features_competitor ON product_competitor_features(product_competitor_id);
CREATE INDEX idx_product_features_status ON product_competitor_features(status);
```

### 6. competitor_features
```sql
CREATE TABLE competitor_features (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_competitor_id UUID NOT NULL REFERENCES session_competitors(id) ON DELETE CASCADE,
    product_feature_id UUID REFERENCES product_competitor_features(id),
    feature_name VARCHAR(255) NOT NULL,
    feature_description TEXT,
    feature_category VARCHAR(100),
    extraction_confidence DECIMAL(3,2),
    source_url VARCHAR(500),
    raw_context TEXT,
    change_type VARCHAR(50),
    change_description TEXT,
    comparison_to_feature_id UUID REFERENCES competitor_features(id),
    selected_by_user BOOLEAN DEFAULT FALSE,
    detail_requested BOOLEAN DEFAULT FALSE,
    expanded_description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_features_session_competitor ON competitor_features(session_competitor_id);
CREATE INDEX idx_features_product_feature ON competitor_features(product_feature_id);
CREATE INDEX idx_features_change_type ON competitor_features(change_type);
CREATE INDEX idx_features_selected ON competitor_features(selected_by_user);
```

### 7. competitor_generated_ideas
```sql
CREATE TABLE competitor_generated_ideas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feature_id UUID NOT NULL REFERENCES competitor_features(id) ON DELETE CASCADE,
    session_id UUID NOT NULL REFERENCES competitor_analysis_sessions(id),
    product_id UUID NOT NULL REFERENCES ci_products(id),
    idea_what TEXT NOT NULL,
    idea_why TEXT NOT NULL,
    idea_use_case TEXT NOT NULL,
    is_differential BOOLEAN DEFAULT FALSE,
    user_edited BOOLEAN DEFAULT FALSE,
    user_approved BOOLEAN DEFAULT FALSE,
    submitted_to_ideas BOOLEAN DEFAULT FALSE,
    final_idea_id UUID REFERENCES ideas(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    edited_at TIMESTAMP
);

CREATE INDEX idx_ci_ideas_feature ON competitor_generated_ideas(feature_id);
CREATE INDEX idx_ci_ideas_session ON competitor_generated_ideas(session_id);
CREATE INDEX idx_ci_ideas_product ON competitor_generated_ideas(product_id);
CREATE INDEX idx_ci_ideas_submitted ON competitor_generated_ideas(submitted_to_ideas);
```

### 8. agent_execution_logs
```sql
CREATE TABLE agent_execution_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES competitor_analysis_sessions(id),
    product_id UUID REFERENCES ci_products(id),
    agent_name VARCHAR(100) NOT NULL,
    stage VARCHAR(50) NOT NULL,
    input_data JSONB,
    output_data JSONB,
    llm_tokens_used INTEGER,
    execution_time_ms INTEGER,
    status VARCHAR(50) NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_agent_logs_session ON agent_execution_logs(session_id);
CREATE INDEX idx_agent_logs_product ON agent_execution_logs(product_id);
CREATE INDEX idx_agent_logs_agent_name ON agent_execution_logs(agent_name);
CREATE INDEX idx_agent_logs_status ON agent_execution_logs(status);
```

## SQLAlchemy Models to Create

Location: `app/models/competitor_intelligence.py`

```python
from sqlalchemy import (
    Column, String, Text, Integer, Boolean, DateTime, ForeignKey, 
    DECIMAL, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base
import uuid
from datetime import datetime

class CIProduct(Base):
    __tablename__ = "ci_products"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    product_name = Column(String(255), nullable=False)
    product_description = Column(Text, nullable=False)
    product_category = Column(String(100))
    structured_product_data = Column(JSONB)
    last_analyzed_at = Column(DateTime)
    analysis_count = Column(Integer, default=0)
    status = Column(String(50), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sessions = relationship("CompetitorAnalysisSession", back_populates="product", cascade="all, delete-orphan")
    competitors = relationship("ProductCompetitor", back_populates="product", cascade="all, delete-orphan")
    generated_ideas = relationship("CompetitorGeneratedIdea", back_populates="product")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'product_name', name='unique_user_product'),
    )

class CompetitorAnalysisSession(Base):
    __tablename__ = "competitor_analysis_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("ci_products.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    session_number = Column(Integer, nullable=False)
    session_name = Column(String(255))
    analysis_type = Column(String(50), nullable=False, default="full")
    comparison_to_session_id = Column(UUID(as_uuid=True), ForeignKey("competitor_analysis_sessions.id"))
    product_source_type = Column(String(50), nullable=False)
    product_source_data = Column(JSONB)
    analyzed_product_structure = Column(JSONB)
    status = Column(String(50), nullable=False, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime)
    
    # Relationships
    product = relationship("CIProduct", back_populates="sessions")
    session_competitors = relationship("SessionCompetitor", back_populates="session", cascade="all, delete-orphan")
    generated_ideas = relationship("CompetitorGeneratedIdea", back_populates="session")
    agent_logs = relationship("AgentExecutionLog", back_populates="session")

# Add remaining model classes: ProductCompetitor, SessionCompetitor, 
# ProductCompetitorFeature, CompetitorFeature, CompetitorGeneratedIdea, 
# AgentExecutionLog (follow same pattern)
```

## Pydantic Schemas to Create

Location: `app/schemas/competitor_intelligence.py`

```python
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID

# Product Schemas
class ProductBase(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=255)
    product_description: str = Field(..., min_length=10)

class ProductCreate(ProductBase):
    product_source_type: str = Field(..., regex="^(text|document|url)$")
    product_source_data: Optional[Dict[str, Any]] = None

class ProductUpdate(BaseModel):
    product_name: Optional[str] = Field(None, min_length=1, max_length=255)
    product_description: Optional[str] = Field(None, min_length=10)
    status: Optional[str] = None

class ProductResponse(ProductBase):
    id: UUID
    user_id: UUID
    product_category: Optional[str]
    structured_product_data: Optional[Dict[str, Any]]
    last_analyzed_at: Optional[datetime]
    analysis_count: int
    status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# Session Schemas
class SessionCreate(BaseModel):
    product_id: UUID
    session_name: Optional[str] = None
    analysis_type: str = Field(default="full", regex="^(full|differential)$")
    product_source_type: str = Field(..., regex="^(text|document|url)$")
    product_source_data: Optional[Dict[str, Any]] = None

class SessionResponse(BaseModel):
    id: UUID
    product_id: UUID
    user_id: UUID
    session_number: int
    session_name: Optional[str]
    analysis_type: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True

# Add remaining schemas for Competitors, Features, Ideas, etc.
```

## Implementation Steps

### Step 1: Create Alembic Migration
```bash
alembic revision -m "add_competitor_intelligence_tables"
```

Edit the generated migration file in `alembic/versions/` with all CREATE TABLE statements above.

### Step 2: Create SQLAlchemy Models
Create `app/models/competitor_intelligence.py` with all model classes.

### Step 3: Create Pydantic Schemas
Create `app/schemas/competitor_intelligence.py` with all schema classes.

### Step 4: Run Migration
```bash
alembic upgrade head
```

## Testing Requirements

### Unit Tests
Create `tests/test_models.py`:

```python
import pytest
from app.models.competitor_intelligence import CIProduct, CompetitorAnalysisSession
from app.database import get_db

def test_create_product(db_session, test_user):
    """Test creating a CI product"""
    product = CIProduct(
        user_id=test_user.id,
        product_name="Test Product",
        product_description="A test product description"
    )
    db_session.add(product)
    db_session.commit()
    
    assert product.id is not None
    assert product.product_name == "Test Product"
    assert product.analysis_count == 0
    assert product.status == "active"

def test_unique_product_name_per_user(db_session, test_user):
    """Test that product names must be unique per user"""
    product1 = CIProduct(
        user_id=test_user.id,
        product_name="Same Name",
        product_description="First product"
    )
    db_session.add(product1)
    db_session.commit()
    
    product2 = CIProduct(
        user_id=test_user.id,
        product_name="Same Name",
        product_description="Second product"
    )
    db_session.add(product2)
    
    with pytest.raises(Exception):  # Should raise IntegrityError
        db_session.commit()

def test_product_session_relationship(db_session, test_user):
    """Test relationship between products and sessions"""
    product = CIProduct(
        user_id=test_user.id,
        product_name="Test Product",
        product_description="Description"
    )
    db_session.add(product)
    db_session.commit()
    
    session = CompetitorAnalysisSession(
        product_id=product.id,
        user_id=test_user.id,
        session_number=1,
        product_source_type="text",
        status="active"
    )
    db_session.add(session)
    db_session.commit()
    
    assert len(product.sessions) == 1
    assert product.sessions[0].session_number == 1

def test_cascade_delete(db_session, test_user):
    """Test that deleting a product cascades to sessions"""
    product = CIProduct(
        user_id=test_user.id,
        product_name="Test Product",
        product_description="Description"
    )
    db_session.add(product)
    db_session.commit()
    
    session = CompetitorAnalysisSession(
        product_id=product.id,
        user_id=test_user.id,
        session_number=1,
        product_source_type="text",
        status="active"
    )
    db_session.add(session)
    db_session.commit()
    
    product_id = product.id
    db_session.delete(product)
    db_session.commit()
    
    # Session should be deleted
    assert db_session.query(CompetitorAnalysisSession).filter_by(product_id=product_id).first() is None
```

### Manual Testing
```bash
# 1. Run migration
alembic upgrade head

# 2. Verify tables exist
psql -d your_database -c "\dt"

# 3. Check indexes
psql -d your_database -c "\di"

# 4. Test constraints
# Try inserting duplicate product name for same user (should fail)
# Try inserting with valid foreign keys (should succeed)
```

## Acceptance Criteria

- [ ] All 8 tables created successfully
- [ ] All indexes created
- [ ] Unique constraints work (can't duplicate product names per user)
- [ ] Foreign keys work correctly
- [ ] Cascade deletes work (deleting product deletes sessions)
- [ ] SQLAlchemy models can query all tables
- [ ] Pydantic schemas validate input/output correctly
- [ ] All unit tests pass
- [ ] Migration can be rolled back cleanly (`alembic downgrade -1`)

## Files to Create/Modify

**New Files:**
- `alembic/versions/XXXX_add_competitor_intelligence_tables.py`
- `app/models/competitor_intelligence.py`
- `app/schemas/competitor_intelligence.py`
- `tests/test_ci_models.py`
- `tests/test_ci_schemas.py`

**Modified Files:**
- `app/models/__init__.py` (import new models)
- `app/schemas/__init__.py` (import new schemas)

## Estimated Time
**1-2 days** including testing

## Next Module
After completing this module, proceed to **Module 2: Product Management API**
