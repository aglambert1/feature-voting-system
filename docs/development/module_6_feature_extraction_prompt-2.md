# Module 6: Feature Extraction with Parallel Processing

## Objective
Implement parallel feature extraction using Celery background tasks with AI agents that extract competitor features and detect changes when comparing with previous analyses.

## Dependencies
- **Requires**: 
  - Module 1 (Database Schema)
  - Module 2 (Product API)
  - Module 3 (Base Agent Infrastructure)
  - Module 4 (Product Analysis & Session Creation)
  - Module 5 (Competitor Discovery)
- **Uses**: Celery, Redis, LLMService, web scraping

## Scope
- Feature Extractor AI agent (with comparison mode)
- Feature Detail Expander AI agent
- Celery tasks for parallel processing
- Feature storage with change tracking
- Stage 3: Feature Extraction UI with real-time progress
- Change detection visualization

## What Users Can Do After Module 6

✅ AI extracts 15-25 features from each competitor in parallel (researching multiple pages per competitor)
✅ See extraction progress in real-time
✅ View features with change indicators (NEW/MODIFIED/UNCHANGED/REMOVED)
✅ Each feature tracked with specific source URL (pricing page, features page, docs, etc.)
✅ Filter features by change type
✅ Request detailed explanations for specific features
✅ Select features for idea generation
✅ Proceed to Stage 4 (idea generation - Module 7)

## Backend Implementation

### 1. Feature Extractor Agent

Location: `app/agents/feature_extractor.py`

```python
from typing import Dict, Any, Type, List, Optional
from pydantic import BaseModel, Field
from app.agents.base_agent import BaseAgent

class ExtractedFeature(BaseModel):
    """Single extracted feature"""
    name: str = Field(..., max_length=255, description="Feature name (2-5 words)")
    description: str = Field(..., description="Feature description (1-2 sentences)")
    category: str = Field(..., description="Feature category")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence")
    source_url: str = Field(..., description="URL where feature was found")
    raw_context: Optional[str] = Field(None, description="Raw text context")

class FeatureExtractionOutput(BaseModel):
    """Output schema for Feature Extractor Agent"""
    competitor_name: str
    features: List[ExtractedFeature] = Field(
        ..., 
        min_items=10,
        max_items=30,
        description="Extracted features"
    )
    extraction_summary: str = Field(
        ..., 
        description="Brief summary of extraction process"
    )

class FeatureWithComparison(BaseModel):
    """Feature with change detection"""
    name: str
    description: str
    category: str
    confidence: float
    source_url: str
    raw_context: Optional[str] = None
    change_type: str = Field(..., pattern="^(new|modified|unchanged|removed)$")
    change_description: Optional[str] = Field(None, description="What changed")
    previous_feature_id: Optional[str] = None

class ComparativeFeatureOutput(BaseModel):
    """Output schema for comparative feature extraction"""
    competitor_name: str
    analysis_mode: str = Field(..., pattern="^(fresh|comparative)$")
    features: List[FeatureWithComparison]
    summary: Dict[str, int] = Field(
        ...,
        description="Feature counts by change type"
    )

class FeatureExtractorAgent(BaseAgent):
    """
    Extracts product features from competitor websites.
    
    Researches multiple pages per competitor (homepage, features page, 
    pricing, documentation, etc.) to build comprehensive feature list.
    
    Can operate in two modes:
    1. Fresh extraction (no previous data)
    2. Comparative analysis (detects changes from previous analysis)
    """
    
    def get_system_prompt(self) -> str:
        return """You are a Feature Extraction agent specializing in competitive intelligence.

Your role is to thoroughly research a competitor's product and extract their features.

You can operate in two modes:

**FRESH EXTRACTION MODE:**
- Extract 15-25 distinct features or capabilities
- Focus on tangible features, not marketing language
- Categorize features logically
- Assign confidence scores based on information clarity

**COMPARATIVE ANALYSIS MODE:**
- Extract current features as above
- Compare with previous features to identify changes
- Categorize each feature as: NEW, MODIFIED, UNCHANGED, or REMOVED
- Explain what changed for modified features
- Be precise about actual changes vs. minor wording differences

Always respond with valid JSON matching the specified schema.
Focus on facts and capabilities, not subjective marketing claims."""
    
    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        competitor_name = input_data.get('competitor_name', '')
        competitor_url = input_data.get('competitor_url', '')
        previous_features = input_data.get('previous_features', None)
        
        if previous_features:
            # Comparative mode
            prompt = f"""COMPARATIVE ANALYSIS MODE

Research the competitor by exploring multiple pages and compare with previous analysis:

**Competitor:** {competitor_name}
**Starting URL:** {competitor_url}

**Previous Features (from last analysis):**
{self._format_previous_features(previous_features)}

**Your Research Process:**
1. Start at {competitor_url}
2. Visit key pages including:
   - Features/Product pages
   - Pricing page
   - Documentation/Help center
   - Blog/Release notes
   - Use cases or integrations pages
3. Extract current features from across these pages
4. Compare each current feature with the previous features list

**For Each Current Feature, Determine:**
- **NEW**: Feature not present in previous analysis
- **MODIFIED**: Feature changed (description, category, or capability shifted)
- **UNCHANGED**: Feature remains essentially the same
- **REMOVED**: Previous feature no longer found (include these in output too)

**For Each Feature, Provide:**
- name: Concise feature name (2-5 words)
- description: Clear description (1-2 sentences)
- category: Logical category (e.g., "Core Functionality", "Integration", "Analytics", "Collaboration", "Security")
- confidence: 0.0-1.0 based on information clarity
- source_url: **Specific page URL** where found (not just homepage)
- change_type: "new", "modified", "unchanged", or "removed"
- change_description: Brief explanation of what changed (for modified features) or why marked as removed
- previous_feature_id: ID of matching previous feature (if applicable)

**Provide Summary Counts:**
- total_features
- new_features
- modified_features
- unchanged_features
- removed_features

Return JSON format matching ComparativeFeatureOutput schema.

**Guidelines:**
- Research across multiple pages to ensure comprehensive coverage
- Be precise about actual changes vs. cosmetic differences
- "Modified" means substantive capability change, not just rewording
- Include removed features in output with change_type="removed"
- Track specific source_url for each feature (the actual page where documented)
- Note in change_description if a feature moved to a different page/section
"""
        else:
            # Fresh extraction mode
            prompt = f"""FRESH EXTRACTION MODE

Research and extract features from this competitor by exploring multiple pages:

**Competitor:** {competitor_name}
**Starting URL:** {competitor_url}

**Your Research Process:**
1. Start at the provided URL ({competitor_url})
2. Identify and visit key pages such as:
   - Features/Product pages
   - Pricing page
   - Documentation/Help center/Support pages
   - Blog posts or release notes about product updates
   - Use cases or customer stories pages
   - Integration/API pages
3. Research across ALL relevant pages to build comprehensive feature list
4. Extract 15-25 distinct features or capabilities from across these pages

**For Each Feature, Provide:**
- name: Concise feature name (2-5 words)
- description: Clear description (1-2 sentences)
- category: Logical category (e.g., "Core Functionality", "Integration", "Analytics", "Pricing Model", "Collaboration", "Security")
- confidence: 0.0-1.0 based on how clearly documented the feature is
- source_url: **Specific page URL** where you found this feature (not just homepage)
- raw_context: Optional snippet of relevant text from that page

**Also Provide:**
- extraction_summary: Brief summary of your research process and what you found (mention which pages you visited)

Return JSON format matching FeatureExtractionOutput schema.

**Guidelines:**
- Research thoroughly across multiple pages, not just the homepage
- Focus on tangible, verifiable features
- Avoid vague marketing terms
- Each feature should have its specific source_url (the actual page where it was documented)
- Categorize logically
- Be specific and factual
- Prioritize features that differentiate this product
"""
        
        return prompt
    
    def _format_previous_features(self, features: List[Dict]) -> str:
        """Format previous features for prompt"""
        if not features:
            return "(No previous features)"
        
        lines = []
        for i, feat in enumerate(features, 1):
            lines.append(f"{i}. {feat.get('name', 'Unknown')}: {feat.get('description', 'N/A')}")
        return '\n'.join(lines)
    
    def get_output_schema(self) -> Type[BaseModel]:
        # Return appropriate schema based on mode
        # This is determined at runtime based on input
        return FeatureExtractionOutput  # Default, will be overridden
    
    def get_stage(self) -> str:
        return "feature_extraction"
    
    async def execute(
        self, 
        input_data: Dict[str, Any],
        temperature: float = 0.7,
        max_tokens: int = 4000,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Override execute to handle dynamic schema selection.
        """
        # Determine mode and set appropriate schema
        has_previous = input_data.get('previous_features') is not None
        
        if has_previous:
            self._output_schema = ComparativeFeatureOutput
        else:
            self._output_schema = FeatureExtractionOutput
        
        return await super().execute(input_data, temperature, max_tokens, max_retries)
    
    def get_output_schema(self) -> Type[BaseModel]:
        return getattr(self, '_output_schema', FeatureExtractionOutput)


class FeatureDetailExpanderAgent(BaseAgent):
    """
    Expands details for a specific feature on user request.
    """
    
    def get_system_prompt(self) -> str:
        return """You are a Feature Detail Expander agent.

Your role is to provide expanded, detailed information about a specific product feature.

Include:
- Technical details and specifications
- Use cases and practical applications
- Benefits and value proposition
- Any limitations or requirements
- Related features or integrations

Be thorough but clear. Focus on helping users understand the feature deeply.

Always respond with valid JSON matching the specified schema."""
    
    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        feature_name = input_data.get('feature_name', '')
        feature_description = input_data.get('feature_description', '')
        competitor_name = input_data.get('competitor_name', '')
        competitor_url = input_data.get('competitor_url', '')
        
        prompt = f"""Provide detailed information about this feature:

**Feature:** {feature_name}
**Current Description:** {feature_description}
**Competitor:** {competitor_name}
**Source:** {competitor_url}

Expand on this feature with:
1. **Technical Details**: How it works, specifications, capabilities
2. **Use Cases**: Practical scenarios where this feature is valuable
3. **Benefits**: Value it provides to users
4. **Limitations**: Any constraints or requirements
5. **Related Features**: Other features that work with this

Return JSON format:
{{
  "expanded_description": "Detailed multi-paragraph description",
  "technical_details": "Technical information",
  "use_cases": ["Use case 1", "Use case 2", ...],
  "benefits": ["Benefit 1", "Benefit 2", ...],
  "limitations": ["Limitation 1", ...] or null,
  "related_features": ["Feature 1", ...] or null
}}
"""
        return prompt
    
    def get_output_schema(self) -> Type[BaseModel]:
        class ExpandedFeatureDetail(BaseModel):
            expanded_description: str
            technical_details: str
            use_cases: List[str]
            benefits: List[str]
            limitations: Optional[List[str]] = None
            related_features: Optional[List[str]] = None
        
        return ExpandedFeatureDetail
    
    def get_stage(self) -> str:
        return "feature_detail_expansion"
```

### 2. Celery Tasks

Location: `app/tasks/competitor_tasks.py`

```python
from celery import Celery, group
from typing import List, Optional, Dict
from uuid import UUID
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.competitor_intelligence import (
    SessionCompetitor,
    CompetitorFeature,
    ProductCompetitorFeature
)
from app.agents.feature_extractor import FeatureExtractorAgent
from app.services.llm_service import LLMService
from app.config import settings

# Initialize Celery
celery_app = Celery(
    'competitor_intelligence',
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

@celery_app.task(bind=True, max_retries=3)
def extract_competitor_features(
    self,
    session_competitor_id: str,
    session_id: str,
    compare_to_previous: bool = False
):
    """
    Extract features for a single competitor.
    
    Args:
        session_competitor_id: SessionCompetitor ID
        session_id: Session ID
        compare_to_previous: Whether to perform comparative analysis
    """
    db = SessionLocal()
    
    try:
        # Get competitor info
        session_competitor = db.query(SessionCompetitor).filter(
            SessionCompetitor.id == UUID(session_competitor_id)
        ).first()
        
        if not session_competitor:
            raise ValueError(f"SessionCompetitor {session_competitor_id} not found")
        
        # Load previous features if comparison enabled
        previous_features = None
        if compare_to_previous and session_competitor.product_competitor_id:
            previous_features = _load_previous_features(
                db, 
                session_competitor.product_competitor_id,
                UUID(session_id)
            )
        
        # Execute feature extraction agent
        llm_service = LLMService()
        agent = FeatureExtractorAgent(
            db=db,
            llm_service=llm_service,
            session_id=UUID(session_id),
            product_id=session_competitor.session.product_id
        )
        
        result = agent.execute({
            'competitor_name': session_competitor.competitor_name,
            'competitor_url': session_competitor.competitor_url,
            'previous_features': previous_features
        })
        
        # Store extracted features
        feature_ids = _store_features(
            db,
            session_competitor_id=UUID(session_competitor_id),
            session_id=UUID(session_id),
            features_data=result['features'],
            is_comparative=compare_to_previous
        )
        
        # Return summary
        return {
            'competitor_id': session_competitor_id,
            'competitor_name': session_competitor.competitor_name,
            'feature_count': len(feature_ids),
            'change_summary': result.get('summary', None),
            'status': 'completed'
        }
        
    except Exception as e:
        # Retry logic
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60)
        
        # Final failure
        return {
            'competitor_id': session_competitor_id,
            'status': 'failed',
            'error': str(e)
        }
        
    finally:
        db.close()

@celery_app.task
def parallel_feature_extraction(
    session_id: str,
    competitor_ids: List[str],
    compare_to_previous: bool = False
):
    """
    Coordinate parallel feature extraction for multiple competitors.
    
    Args:
        session_id: Session ID
        competitor_ids: List of SessionCompetitor IDs
        compare_to_previous: Whether to enable comparison mode
    """
    # Create group of parallel tasks
    job = group(
        extract_competitor_features.s(
            session_competitor_id=comp_id,
            session_id=session_id,
            compare_to_previous=compare_to_previous
        )
        for comp_id in competitor_ids
    )
    
    # Execute in parallel
    result = job.apply_async()
    
    return {
        'task_id': result.id,
        'status': 'processing',
        'total_competitors': len(competitor_ids)
    }

def _load_previous_features(
    db: Session, 
    product_competitor_id: UUID,
    current_session_id: UUID
) -> Optional[List[Dict]]:
    """Load features from previous analysis for comparison."""
    # Get most recent previous session for this competitor
    previous_features = db.query(CompetitorFeature).join(
        SessionCompetitor
    ).filter(
        SessionCompetitor.product_competitor_id == product_competitor_id,
        SessionCompetitor.session_id != current_session_id,
        SessionCompetitor.selected_by_user == True
    ).order_by(
        SessionCompetitor.created_at.desc()
    ).limit(50).all()  # Limit to most recent 50 features
    
    if not previous_features:
        return None
    
    return [
        {
            'id': str(feat.id),
            'name': feat.feature_name,
            'description': feat.feature_description,
            'category': feat.feature_category
        }
        for feat in previous_features
    ]

def _store_features(
    db: Session,
    session_competitor_id: UUID,
    session_id: UUID,
    features_data: List[Dict],
    is_comparative: bool
) -> List[UUID]:
    """Store extracted features in database."""
    feature_ids = []
    
    session_competitor = db.query(SessionCompetitor).filter(
        SessionCompetitor.id == session_competitor_id
    ).first()
    
    for feat_data in features_data:
        # Create or update product-level feature
        product_feature = None
        if session_competitor.product_competitor_id:
            product_feature = _get_or_create_product_feature(
                db,
                product_competitor_id=session_competitor.product_competitor_id,
                feature_name=feat_data['name'],
                feature_description=feat_data['description'],
                feature_category=feat_data['category'],
                session_id=session_id
            )
        
        # Create session-specific feature
        competitor_feature = CompetitorFeature(
            session_competitor_id=session_competitor_id,
            product_feature_id=product_feature.id if product_feature else None,
            feature_name=feat_data['name'],
            feature_description=feat_data['description'],
            feature_category=feat_data['category'],
            extraction_confidence=feat_data.get('confidence', 0.8),
            source_url=feat_data.get('source_url'),
            raw_context=feat_data.get('raw_context'),
            change_type=feat_data.get('change_type') if is_comparative else None,
            change_description=feat_data.get('change_description'),
            comparison_to_feature_id=UUID(feat_data['previous_feature_id']) if feat_data.get('previous_feature_id') else None,
            selected_by_user=False,
            detail_requested=False
        )
        
        db.add(competitor_feature)
        db.flush()
        
        feature_ids.append(competitor_feature.id)
    
    db.commit()
    return feature_ids

def _get_or_create_product_feature(
    db: Session,
    product_competitor_id: UUID,
    feature_name: str,
    feature_description: str,
    feature_category: str,
    session_id: UUID
) -> 'ProductCompetitorFeature':
    """Get or create product-level feature."""
    # Try to find existing by name
    existing = db.query(ProductCompetitorFeature).filter(
        ProductCompetitorFeature.product_competitor_id == product_competitor_id,
        ProductCompetitorFeature.feature_name == feature_name
    ).first()
    
    if existing:
        # Update last_seen
        existing.last_seen_session_id = session_id
        existing.feature_description = feature_description  # Update description
        existing.status = "active"
        db.commit()
        return existing
    
    # Create new
    product_feature = ProductCompetitorFeature(
        product_competitor_id=product_competitor_id,
        feature_name=feature_name,
        feature_description=feature_description,
        feature_category=feature_category,
        first_discovered_session_id=session_id,
        last_seen_session_id=session_id,
        status="active"
    )
    
    db.add(product_feature)
    db.commit()
    db.refresh(product_feature)
    
    return product_feature
```

### 3. Feature Extraction Service

Location: `app/services/feature_extraction_service.py`

```python
from typing import List, Dict, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.competitor_intelligence import (
    CompetitorAnalysisSession,
    SessionCompetitor,
    CompetitorFeature
)
from app.tasks.competitor_tasks import parallel_feature_extraction
from app.agents.feature_extractor import FeatureDetailExpanderAgent
from app.services.llm_service import LLMService
from celery.result import GroupResult

class FeatureExtractionService:
    """Service for managing feature extraction operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def start_extraction(
        self,
        session_id: UUID
    ) -> Dict:
        """
        Start parallel feature extraction for all selected competitors.
        """
        # Get session
        session = self.db.query(CompetitorAnalysisSession).filter(
            CompetitorAnalysisSession.id == session_id
        ).first()
        
        if not session:
            raise ValueError("Session not found")
        
        # Get selected competitors
        competitors = self.db.query(SessionCompetitor).filter(
            SessionCompetitor.session_id == session_id,
            SessionCompetitor.selected_by_user == True
        ).all()
        
        if not competitors:
            raise ValueError("No competitors selected")
        
        # Determine if comparison mode
        compare_to_previous = session.analysis_type == "differential"
        
        # Start parallel extraction (Celery tasks)
        competitor_ids = [str(comp.id) for comp in competitors]
        result = parallel_feature_extraction.delay(
            session_id=str(session_id),
            competitor_ids=competitor_ids,
            compare_to_previous=compare_to_previous
        )
        
        return {
            'task_id': result.id,
            'status': 'processing',
            'total_competitors': len(competitor_ids),
            'comparison_mode': compare_to_previous
        }
    
    def get_extraction_status(
        self,
        task_id: str
    ) -> Dict:
        """
        Get status of parallel extraction task.
        """
        result = GroupResult.restore(task_id)
        
        if result is None:
            return {
                'status': 'not_found',
                'completed_count': 0,
                'total_count': 0
            }
        
        completed = sum(1 for r in result.results if r.ready())
        total = len(result.results)
        
        # Get results that are ready
        features_by_competitor = {}
        for task_result in result.results:
            if task_result.ready():
                data = task_result.get()
                if data.get('status') == 'completed':
                    features_by_competitor[data['competitor_id']] = {
                        'competitor_name': data['competitor_name'],
                        'feature_count': data['feature_count'],
                        'change_summary': data.get('change_summary')
                    }
        
        status = 'completed' if completed == total else 'processing'
        
        return {
            'status': status,
            'completed_count': completed,
            'total_count': total,
            'features_by_competitor': features_by_competitor
        }
    
    async def get_session_features(
        self,
        session_id: UUID,
        include_unselected: bool = True
    ) -> Dict:
        """
        Get all features for a session, grouped by competitor.
        """
        query = self.db.query(CompetitorFeature).join(
            SessionCompetitor
        ).filter(
            SessionCompetitor.session_id == session_id
        )
        
        if not include_unselected:
            query = query.filter(SessionCompetitor.selected_by_user == True)
        
        features = query.all()
        
        # Group by competitor
        by_competitor = {}
        change_stats = {
            'new': 0,
            'modified': 0,
            'unchanged': 0,
            'removed': 0,
            'total': len(features)
        }
        
        for feature in features:
            comp_id = str(feature.session_competitor_id)
            
            if comp_id not in by_competitor:
                by_competitor[comp_id] = {
                    'competitor_name': feature.session_competitor.competitor_name,
                    'features': []
                }
            
            by_competitor[comp_id]['features'].append({
                'id': str(feature.id),
                'name': feature.feature_name,
                'description': feature.feature_description,
                'category': feature.feature_category,
                'confidence': float(feature.extraction_confidence) if feature.extraction_confidence else None,
                'source_url': feature.source_url,
                'change_type': feature.change_type,
                'change_description': feature.change_description,
                'selected': feature.selected_by_user,
                'has_details': feature.detail_requested and feature.expanded_description is not None
            })
            
            # Track change stats
            if feature.change_type:
                change_stats[feature.change_type] = change_stats.get(feature.change_type, 0) + 1
        
        return {
            'features_by_competitor': by_competitor,
            'change_stats': change_stats
        }
    
    async def expand_feature_details(
        self,
        feature_id: UUID,
        llm_service: LLMService
    ) -> Dict:
        """
        Get expanded details for a specific feature using AI.
        """
        feature = self.db.query(CompetitorFeature).filter(
            CompetitorFeature.id == feature_id
        ).first()
        
        if not feature:
            raise ValueError("Feature not found")
        
        # Check if already expanded
        if feature.expanded_description:
            return {
                'feature_id': str(feature_id),
                'expanded_description': feature.expanded_description,
                'cached': True
            }
        
        # Use agent to expand
        agent = FeatureDetailExpanderAgent(
            db=self.db,
            llm_service=llm_service,
            session_id=feature.session_competitor.session_id,
            product_id=feature.session_competitor.session.product_id
        )
        
        result = await agent.execute({
            'feature_name': feature.feature_name,
            'feature_description': feature.feature_description,
            'competitor_name': feature.session_competitor.competitor_name,
            'competitor_url': feature.session_competitor.competitor_url
        })
        
        # Store expanded description
        feature.expanded_description = result['expanded_description']
        feature.detail_requested = True
        self.db.commit()
        
        return {
            'feature_id': str(feature_id),
            **result,
            'cached': False
        }
    
    async def select_features(
        self,
        session_id: UUID,
        feature_ids: List[UUID]
    ) -> Dict:
        """
        User selects which features to use for idea generation.
        """
        # Reset all selections for this session
        self.db.query(CompetitorFeature).join(
            SessionCompetitor
        ).filter(
            SessionCompetitor.session_id == session_id
        ).update({"selected_by_user": False}, synchronize_session=False)
        
        # Set selected features
        if feature_ids:
            self.db.query(CompetitorFeature).filter(
                CompetitorFeature.id.in_(feature_ids)
            ).update({"selected_by_user": True}, synchronize_session=False)
        
        self.db.commit()
        
        return {
            'selected_count': len(feature_ids)
        }
```

### 4. API Endpoints

Location: `app/routers/competitor_intelligence.py` (extend existing)

```python
from app.services.feature_extraction_service import FeatureExtractionService

@router.post("/sessions/{session_id}/extract-features")
async def start_feature_extraction(
    session_id: UUID,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Start parallel feature extraction for all selected competitors.
    
    Returns task ID for polling status.
    """
    service = FeatureExtractionService(db)
    
    try:
        result = await service.start_extraction(session_id)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/sessions/{session_id}/extraction-status")
async def get_extraction_status(
    session_id: UUID,
    task_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Poll the status of feature extraction.
    """
    service = FeatureExtractionService(db)
    
    status = service.get_extraction_status(task_id)
    return status

@router.get("/sessions/{session_id}/features")
async def get_session_features(
    session_id: UUID,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all extracted features for a session.
    """
    service = FeatureExtractionService(db)
    
    result = await service.get_session_features(session_id)
    return result

@router.get("/features/{feature_id}/details")
async def get_feature_details(
    feature_id: UUID,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get expanded details for a specific feature.
    """
    service = FeatureExtractionService(db)
    llm_service = LLMService()
    
    try:
        result = await service.expand_feature_details(feature_id, llm_service)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

@router.post("/sessions/{session_id}/select-features")
async def select_features(
    session_id: UUID,
    feature_ids: List[UUID] = Body(...),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Select features for idea generation.
    """
    service = FeatureExtractionService(db)
    
    result = await service.select_features(session_id, feature_ids)
    return result
```

### 5. Celery Configuration

Location: `app/config.py` (add Celery settings)

```python
class Settings(BaseSettings):
    # Existing settings...
    
    # Celery/Redis Configuration
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    
    # Feature Extraction Settings
    PARALLEL_EXTRACTION_LIMIT: int = 5  # Max concurrent extractions
    FEATURE_EXTRACTION_TIMEOUT: int = 300  # seconds
```

### 6. Celery Worker Start Script

Location: `scripts/start_celery_worker.sh`

```bash
#!/bin/bash

# Start Celery worker for competitor intelligence tasks

celery -A app.tasks.competitor_tasks worker \
    --loglevel=info \
    --concurrency=5 \
    --pool=prefork \
    --queues=default
```

## Frontend Implementation

### 1. Stage 3: Feature Extraction

Location: `src/pages/CompetitorIntelligence/stages/Stage3_FeatureExtraction.tsx`

```typescript
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import FeatureTable from '../components/FeatureTable';
import ChangeSummaryDashboard from '../components/ChangeSummaryDashboard';
import FeatureDetailModal from '../components/FeatureDetailModal';

interface Stage3Props {
  sessionId: string;
  hasPreviousAnalysis: boolean;
  onComplete: () => void;
  onBack: () => void;
}

interface Feature {
  id: string;
  name: string;
  description: string;
  category: string;
  confidence?: number;
  source_url?: string;
  change_type?: 'new' | 'modified' | 'unchanged' | 'removed';
  change_description?: string;
  selected: boolean;
  has_details: boolean;
}

interface ChangeStats {
  new: number;
  modified: number;
  unchanged: number;
  removed: number;
  total: number;
}

type ViewMode = 'extracting' | 'reviewing' | 'error';

const Stage3_FeatureExtraction: React.FC<Stage3Props> = ({
  sessionId,
  hasPreviousAnalysis,
  onComplete,
  onBack,
}) => {
  const [mode, setMode] = useState<ViewMode>('extracting');
  const [taskId, setTaskId] = useState<string | null>(null);
  const [extractionProgress, setExtractionProgress] = useState({
    completed: 0,
    total: 0,
  });
  const [featuresByCompetitor, setFeaturesByCompetitor] = useState<Record<string, any>>({});
  const [changeStats, setChangeStats] = useState<ChangeStats | null>(null);
  const [showOnlyChanges, setShowOnlyChanges] = useState(hasPreviousAnalysis);
  const [selectedFeatureForDetail, setSelectedFeatureForDetail] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    startExtraction();
  }, []);

  useEffect(() => {
    if (taskId && mode === 'extracting') {
      const interval = setInterval(() => {
        pollExtractionStatus();
      }, 3000);

      return () => clearInterval(interval);
    }
  }, [taskId, mode]);

  const startExtraction = async () => {
    try {
      const response = await axios.post(
        `/api/competitor-intelligence/sessions/${sessionId}/extract-features`
      );

      setTaskId(response.data.task_id);
      setExtractionProgress({
        completed: 0,
        total: response.data.total_competitors,
      });
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to start extraction');
      setMode('error');
    }
  };

  const pollExtractionStatus = async () => {
    if (!taskId) return;

    try {
      const response = await axios.get(
        `/api/competitor-intelligence/sessions/${sessionId}/extraction-status?task_id=${taskId}`
      );

      setExtractionProgress({
        completed: response.data.completed_count,
        total: response.data.total_count,
      });

      if (response.data.status === 'completed') {
        await loadFeatures();
        setMode('reviewing');
      }
    } catch (err: any) {
      console.error('Polling error:', err);
    }
  };

  const loadFeatures = async () => {
    try {
      const response = await axios.get(
        `/api/competitor-intelligence/sessions/${sessionId}/features`
      );

      setFeaturesByCompetitor(response.data.features_by_competitor);
      setChangeStats(response.data.change_stats);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load features');
      setMode('error');
    }
  };

  const toggleFeatureSelection = (featureId: string, competitorId: string) => {
    setFeaturesByCompetitor((prev) => ({
      ...prev,
      [competitorId]: {
        ...prev[competitorId],
        features: prev[competitorId].features.map((f: Feature) =>
          f.id === featureId ? { ...f, selected: !f.selected } : f
        ),
      },
    }));
  };

  const handleRequestDetails = (featureId: string) => {
    setSelectedFeatureForDetail(featureId);
  };

  const handleConfirmSelection = async () => {
    // Collect all selected feature IDs
    const selectedIds: string[] = [];
    Object.values(featuresByCompetitor).forEach((comp: any) => {
      comp.features.forEach((f: Feature) => {
        if (f.selected) {
          selectedIds.push(f.id);
        }
      });
    });

    if (selectedIds.length === 0) {
      alert('Please select at least one feature');
      return;
    }

    try {
      await axios.post(
        `/api/competitor-intelligence/sessions/${sessionId}/select-features`,
        selectedIds
      );

      onComplete();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to confirm selection');
    }
  };

  if (mode === 'extracting') {
    const progress =
      extractionProgress.total > 0
        ? (extractionProgress.completed / extractionProgress.total) * 100
        : 0;

    return (
      <div className="text-center py-12">
        <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
        <h3 className="text-lg font-medium text-gray-900 mb-2">
          Extracting Features...
        </h3>
        <p className="text-gray-600 mb-4">
          AI is analyzing competitors in parallel
        </p>
        <div className="max-w-md mx-auto">
          <div className="bg-gray-200 rounded-full h-4 mb-2">
            <div
              className="bg-blue-600 h-4 rounded-full transition-all duration-500"
              style={{ width: `${progress}%` }}
            ></div>
          </div>
          <p className="text-sm text-gray-600">
            {extractionProgress.completed} of {extractionProgress.total} competitors
            completed
          </p>
        </div>
      </div>
    );
  }

  if (mode === 'error') {
    return (
      <div className="text-center py-12">
        <div className="text-red-600 mb-4">
          <svg
            className="mx-auto h-12 w-12"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </div>
        <h3 className="text-lg font-medium text-gray-900 mb-2">
          Extraction Failed
        </h3>
        <p className="text-gray-600 mb-4">{error}</p>
        <button
          onClick={startExtraction}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          Retry
        </button>
      </div>
    );
  }

  const totalSelected = Object.values(featuresByCompetitor).reduce(
    (sum: number, comp: any) =>
      sum + comp.features.filter((f: Feature) => f.selected).length,
    0
  );

  return (
    <div>
      <div className="flex justify-between items-start mb-6">
        <div>
          <h2 className="text-2xl font-bold mb-2">Feature Extraction</h2>
          <p className="text-gray-600">
            Review and select features for idea generation
          </p>
        </div>
        <div className="text-sm text-gray-600">{totalSelected} features selected</div>
      </div>

      {hasPreviousAnalysis && changeStats && (
        <ChangeSummaryDashboard changeStats={changeStats} />
      )}

      {hasPreviousAnalysis && (
        <div className="mb-4 flex items-center">
          <input
            type="checkbox"
            id="show_only_changes"
            checked={showOnlyChanges}
            onChange={(e) => setShowOnlyChanges(e.target.checked)}
            className="mr-2"
          />
          <label htmlFor="show_only_changes" className="text-sm text-gray-700">
            Show only new/modified features
          </label>
        </div>
      )}

      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-red-800">{error}</p>
        </div>
      )}

      <div className="space-y-6 mb-6">
        {Object.entries(featuresByCompetitor).map(([competitorId, data]: [string, any]) => (
          <div key={competitorId} className="bg-white rounded-lg shadow">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">
                {data.competitor_name}
              </h3>
              <p className="text-sm text-gray-600">
                {data.features.length} features extracted
              </p>
            </div>
            <div className="p-6">
              <FeatureTable
                features={data.features}
                showChangeType={hasPreviousAnalysis}
                showOnlyChanges={showOnlyChanges}
                onToggleSelection={(featureId) =>
                  toggleFeatureSelection(featureId, competitorId)
                }
                onRequestDetails={handleRequestDetails}
              />
            </div>
          </div>
        ))}
      </div>

      <div className="flex justify-between">
        <button
          onClick={onBack}
          className="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
        >
          ← Back
        </button>
        <button
          onClick={handleConfirmSelection}
          disabled={totalSelected === 0}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
        >
          Generate Ideas ({totalSelected}) →
        </button>
      </div>

      {selectedFeatureForDetail && (
        <FeatureDetailModal
          featureId={selectedFeatureForDetail}
          onClose={() => setSelectedFeatureForDetail(null)}
        />
      )}
    </div>
  );
};

export default Stage3_FeatureExtraction;
```

### 2. Feature Table Component

Location: `src/pages/CompetitorIntelligence/components/FeatureTable.tsx`

```typescript
import React from 'react';

interface Feature {
  id: string;
  name: string;
  description: string;
  category: string;
  confidence?: number;
  source_url?: string;
  change_type?: 'new' | 'modified' | 'unchanged' | 'removed';
  change_description?: string;
  selected: boolean;
  has_details: boolean;
}

interface FeatureTableProps {
  features: Feature[];
  showChangeType: boolean;
  showOnlyChanges: boolean;
  onToggleSelection: (featureId: string) => void;
  onRequestDetails: (featureId: string) => void;
}

const FeatureTable: React.FC<FeatureTableProps> = ({
  features,
  showChangeType,
  showOnlyChanges,
  onToggleSelection,
  onRequestDetails,
}) => {
  const getChangeTypeBadge = (changeType?: string) => {
    if (!showChangeType || !changeType) return null;

    const badges: Record<string, any> = {
      new: { bg: 'bg-green-100', text: 'text-green-800', label: 'NEW' },
      modified: { bg: 'bg-orange-100', text: 'text-orange-800', label: 'MODIFIED' },
      unchanged: { bg: 'bg-gray-100', text: 'text-gray-600', label: 'UNCHANGED' },
      removed: { bg: 'bg-red-100', text: 'text-red-800', label: 'REMOVED' },
    };

    const badge = badges[changeType];
    if (!badge) return null;

    return (
      <span
        className={`inline-block px-2 py-1 rounded-full text-xs font-medium ${badge.bg} ${badge.text}`}
      >
        {badge.label}
      </span>
    );
  };

  // Filter features if needed
  const filteredFeatures = showOnlyChanges
    ? features.filter(
        (f) => f.change_type === 'new' || f.change_type === 'modified'
      )
    : features;

  if (filteredFeatures.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        {showOnlyChanges
          ? 'No new or modified features'
          : 'No features extracted'}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
              <input
                type="checkbox"
                onChange={(e) => {
                  filteredFeatures.forEach((f) => {
                    if (f.change_type !== 'removed') {
                      onToggleSelection(f.id);
                    }
                  });
                }}
                className="rounded"
              />
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
              Feature
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
              Category
            </th>
            {showChangeType && (
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Change
              </th>
            )}
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
              Actions
            </th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {filteredFeatures.map((feature) => (
            <tr
              key={feature.id}
              className={
                feature.change_type === 'removed'
                  ? 'opacity-50 line-through'
                  : feature.selected
                  ? 'bg-blue-50'
                  : 'hover:bg-gray-50'
              }
            >
              <td className="px-4 py-3">
                <input
                  type="checkbox"
                  checked={feature.selected}
                  onChange={() => onToggleSelection(feature.id)}
                  disabled={feature.change_type === 'removed'}
                  className="rounded"
                />
              </td>
              <td className="px-4 py-3">
                <div className="font-medium text-gray-900">{feature.name}</div>
                <div className="text-sm text-gray-600 mt-1">
                  {feature.description}
                </div>
                {feature.change_description && (
                  <div className="text-xs text-gray-500 italic mt-1">
                    {feature.change_description}
                  </div>
                )}
              </td>
              <td className="px-4 py-3 text-sm text-gray-600">
                {feature.category}
              </td>
              {showChangeType && (
                <td className="px-4 py-3">
                  {getChangeTypeBadge(feature.change_type)}
                </td>
              )}
              <td className="px-4 py-3">
                <button
                  onClick={() => onRequestDetails(feature.id)}
                  className="text-sm text-blue-600 hover:text-blue-800"
                >
                  {feature.has_details ? 'View Details' : 'Request Details'}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default FeatureTable;
```

### 3. Change Summary Dashboard

Location: `src/pages/CompetitorIntelligence/components/ChangeSummaryDashboard.tsx`

```typescript
import React from 'react';

interface ChangeSummaryDashboardProps {
  changeStats: {
    new: number;
    modified: number;
    unchanged: number;
    removed: number;
    total: number;
  };
}

const ChangeSummaryDashboard: React.FC<ChangeSummaryDashboardProps> = ({
  changeStats,
}) => {
  return (
    <div className="mb-6 p-6 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        Feature Change Summary
      </h3>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="bg-white rounded-lg p-4 text-center">
          <div className="text-3xl font-bold text-gray-900">
            {changeStats.total}
          </div>
          <div className="text-xs text-gray-600 mt-1">Total Features</div>
        </div>
        <div className="bg-white rounded-lg p-4 text-center">
          <div className="text-3xl font-bold text-green-600">
            {changeStats.new}
          </div>
          <div className="text-xs text-gray-600 mt-1">New Features</div>
        </div>
        <div className="bg-white rounded-lg p-4 text-center">
          <div className="text-3xl font-bold text-orange-600">
            {changeStats.modified}
          </div>
          <div className="text-xs text-gray-600 mt-1">Modified</div>
        </div>
        <div className="bg-white rounded-lg p-4 text-center">
          <div className="text-3xl font-bold text-red-600">
            {changeStats.removed}
          </div>
          <div className="text-xs text-gray-600 mt-1">Removed</div>
        </div>
        <div className="bg-white rounded-lg p-4 text-center">
          <div className="text-3xl font-bold text-gray-600">
            {changeStats.unchanged}
          </div>
          <div className="text-xs text-gray-600 mt-1">Unchanged</div>
        </div>
      </div>
    </div>
  );
};

export default ChangeSummaryDashboard;
```

### 4. Feature Detail Modal

Location: `src/pages/CompetitorIntelligence/components/FeatureDetailModal.tsx`

```typescript
import React, { useState, useEffect } from 'react';
import axios from 'axios';

interface FeatureDetailModalProps {
  featureId: string;
  onClose: () => void;
}

const FeatureDetailModal: React.FC<FeatureDetailModalProps> = ({
  featureId,
  onClose,
}) => {
  const [loading, setLoading] = useState(true);
  const [details, setDetails] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadDetails();
  }, []);

  const loadDetails = async () => {
    try {
      setLoading(true);
      const response = await axios.get(
        `/api/competitor-intelligence/features/${featureId}/details`
      );
      setDetails(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load details');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto">
        <div className="flex justify-between items-start mb-4">
          <h3 className="text-xl font-bold">Feature Details</h3>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700"
          >
            <svg
              className="w-6 h-6"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {loading && (
          <div className="text-center py-8">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            <p className="text-gray-600 mt-2">Loading details...</p>
          </div>
        )}

        {error && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-red-800">{error}</p>
          </div>
        )}

        {details && !loading && (
          <div className="space-y-4">
            <div>
              <h4 className="font-semibold text-gray-900 mb-2">Description</h4>
              <p className="text-gray-700 whitespace-pre-wrap">
                {details.expanded_description}
              </p>
            </div>

            <div>
              <h4 className="font-semibold text-gray-900 mb-2">
                Technical Details
              </h4>
              <p className="text-gray-700">{details.technical_details}</p>
            </div>

            {details.use_cases && details.use_cases.length > 0 && (
              <div>
                <h4 className="font-semibold text-gray-900 mb-2">Use Cases</h4>
                <ul className="list-disc list-inside space-y-1">
                  {details.use_cases.map((useCase: string, idx: number) => (
                    <li key={idx} className="text-gray-700">
                      {useCase}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {details.benefits && details.benefits.length > 0 && (
              <div>
                <h4 className="font-semibold text-gray-900 mb-2">Benefits</h4>
                <ul className="list-disc list-inside space-y-1">
                  {details.benefits.map((benefit: string, idx: number) => (
                    <li key={idx} className="text-gray-700">
                      {benefit}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {details.limitations && details.limitations.length > 0 && (
              <div>
                <h4 className="font-semibold text-gray-900 mb-2">
                  Limitations
                </h4>
                <ul className="list-disc list-inside space-y-1">
                  {details.limitations.map((limitation: string, idx: number) => (
                    <li key={idx} className="text-gray-700">
                      {limitation}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {details.cached && (
              <p className="text-xs text-gray-500 italic">
                (Details previously retrieved)
              </p>
            )}
          </div>
        )}

        <div className="mt-6 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default FeatureDetailModal;
```

### 5. Update Wizard to Include Stage 3

Location: `src/pages/CompetitorIntelligence/AnalysisWizard.tsx`

```typescript
import Stage3_FeatureExtraction from './stages/Stage3_FeatureExtraction';

// In the render section:
{wizardState.currentStage === 3 && (
  <Stage3_FeatureExtraction
    sessionId={wizardState.sessionId!}
    hasPreviousAnalysis={wizardState.hasPreviousAnalysis}
    onComplete={goToNextStage}
    onBack={goToPreviousStage}
  />
)}
```

## Testing Requirements

### Backend Unit Tests

Location: `tests/test_feature_extractor.py`

```python
import pytest
from app.agents.feature_extractor import FeatureExtractorAgent, FeatureDetailExpanderAgent

@pytest.mark.asyncio
async def test_feature_extractor_fresh_mode(db_session, mock_llm_service):
    """Test feature extraction in fresh mode"""
    mock_llm_service.call_agent.return_value = {
        "content": '''```json
{
    "competitor_name": "Test Competitor",
    "features": [
        {
            "name": "Feature A",
            "description": "Description",
            "category": "Core",
            "confidence": 0.9,
            "source_url": "https://example.com"
        }
    ],
    "extraction_summary": "Extracted features"
}
```''',
        "tokens_used": 400
    }
    
    agent = FeatureExtractorAgent(db=db_session, llm_service=mock_llm_service)
    
    result = await agent.execute({
        'competitor_name': 'Test Competitor',
        'competitor_url': 'https://example.com',
        'previous_features': None
    })
    
    assert 'features' in result
    assert len(result['features']) >= 1

@pytest.mark.asyncio
async def test_feature_extractor_comparative_mode(db_session, mock_llm_service):
    """Test feature extraction in comparative mode"""
    mock_llm_service.call_agent.return_value = {
        "content": '''```json
{
    "competitor_name": "Test Competitor",
    "analysis_mode": "comparative",
    "features": [
        {
            "name": "Feature A",
            "description": "Description",
            "category": "Core",
            "confidence": 0.9,
            "source_url": "https://example.com",
            "change_type": "new",
            "change_description": "New feature",
            "previous_feature_id": null
        }
    ],
    "summary": {
        "total_features": 1,
        "new_features": 1,
        "modified_features": 0,
        "unchanged_features": 0,
        "removed_features": 0
    }
}
```''',
        "tokens_used": 500
    }
    
    agent = FeatureExtractorAgent(db=db_session, llm_service=mock_llm_service)
    
    result = await agent.execute({
        'competitor_name': 'Test Competitor',
        'competitor_url': 'https://example.com',
        'previous_features': [{'name': 'Old Feature', 'description': 'Desc'}]
    })
    
    assert result['analysis_mode'] == 'comparative'
    assert 'summary' in result
```

Location: `tests/test_celery_tasks.py`

```python
import pytest
from app.tasks.competitor_tasks import extract_competitor_features

@pytest.mark.celery
def test_extract_competitor_features_task(celery_worker, test_session_competitor):
    """Test Celery task for feature extraction"""
    # This requires Celery worker to be running
    result = extract_competitor_features.delay(
        session_competitor_id=str(test_session_competitor.id),
        session_id=str(test_session_competitor.session_id),
        compare_to_previous=False
    )
    
    # Wait for result
    data = result.get(timeout=60)
    
    assert data['status'] == 'completed'
    assert data['feature_count'] > 0
```

### Frontend Manual Testing

1. **Complete Stages 1-2, then proceed to Stage 3**
2. **Watch extraction progress**
   - Should show animated progress bar
   - Should update competitor count
3. **Review extracted features**
   - Should display features grouped by competitor
   - Should show categories and descriptions
4. **Test change detection** (if previous analysis exists)
   - Should show change summary dashboard
   - Should display change type badges
   - Filter toggle should work
5. **Test feature selection**
   - Click features to select/deselect
   - Selected count should update
6. **Test request details**
   - Click "Request Details"
   - Should show loading
   - Should display expanded information
7. **Test confirmation**
   - Select features
   - Click "Generate Ideas"
   - Should proceed to Stage 4

## Acceptance Criteria

**Backend:**
- [ ] FeatureExtractorAgent works in both modes (fresh/comparative)
- [ ] FeatureDetailExpanderAgent provides expanded details
- [ ] Celery tasks execute in parallel
- [ ] Features stored in database with change tracking
- [ ] Product-level features tracked across sessions
- [ ] Feature selection API works
- [ ] All unit tests pass

**Frontend:**
- [ ] Stage 3 starts extraction automatically
- [ ] Progress bar updates in real-time
- [ ] Features display correctly
- [ ] Change summary dashboard shows (when applicable)
- [ ] Change type badges display correctly
- [ ] Can filter by change type
- [ ] Can select/deselect features
- [ ] Request details works
- [ ] Confirmation proceeds to Stage 4

**Integration:**
- [ ] End-to-end flow: Stage 1 → 2 → 3 → confirmation
- [ ] Parallel extraction works for multiple competitors
- [ ] Comparison mode works correctly
- [ ] Fresh extraction (no previous data) works
- [ ] Selected features ready for idea generation (Module 7)

**Celery:**
- [ ] Celery worker starts successfully
- [ ] Tasks execute in parallel
- [ ] Task results return correctly
- [ ] Error handling and retries work

## Files to Create/Modify

**New Backend Files:**
- `app/agents/feature_extractor.py`
- `app/tasks/competitor_tasks.py`
- `app/services/feature_extraction_service.py`
- `scripts/start_celery_worker.sh`
- `tests/test_feature_extractor.py`
- `tests/test_celery_tasks.py`

**New Frontend Files:**
- `src/pages/CompetitorIntelligence/stages/Stage3_FeatureExtraction.tsx`
- `src/pages/CompetitorIntelligence/components/FeatureTable.tsx`
- `src/pages/CompetitorIntelligence/components/ChangeSummaryDashboard.tsx`
- `src/pages/CompetitorIntelligence/components/FeatureDetailModal.tsx`

**Modified Files:**
- `app/config.py` (add Celery settings)
- `app/routers/competitor_intelligence.py` (add feature endpoints)
- `src/pages/CompetitorIntelligence/AnalysisWizard.tsx` (add Stage 3)

**Setup Requirements:**
- Redis server running
- Celery worker running
- Environment variables configured

## Setup Instructions

### 1. Install Redis

```bash
# macOS
brew install redis
brew services start redis

# Ubuntu
sudo apt-get install redis-server
sudo systemctl start redis
```

### 2. Install Celery

```bash
pip install celery redis
```

### 3. Start Celery Worker

```bash
chmod +x scripts/start_celery_worker.sh
./scripts/start_celery_worker.sh
```

Or directly:
```bash
celery -A app.tasks.competitor_tasks worker --loglevel=info
```

### 4. Verify Celery is Running

```bash
celery -A app.tasks.competitor_tasks inspect active
```

## Estimated Time
**4-5 days** including Celery setup and testing

## Next Module
After completing this module, proceed to **Module 7: Idea Generation & Finalization**

---

**Note:** After this module, users can extract features with change detection. Module 7 will convert features to ideas and submit them to the voting system.
