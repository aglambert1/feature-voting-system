# Module 5: Competitor Discovery with Differential Analysis

## Objective
Implement competitor discovery using AI web research and differential analysis to compare with previous sessions, allowing users to discover competitors, see what changed, and select which competitors to analyze.

## Dependencies
- **Requires**: 
  - Module 1 (Database Schema)
  - Module 2 (Product API)
  - Module 3 (Base Agent Infrastructure)
  - Module 4 (Product Analysis & Session Creation)
- **Uses**: Web search capabilities, LLMService

## Scope
- Competitor Researcher AI agent (discovers competitors via web search)
- Differential Analysis AI agent (compares with previous sessions)
- Competitor confirmation API
- Stage 2: Competitor Discovery UI with change indicators
- Change summary visualization

## What Users Can Do After Module 5

✅ AI discovers 10-15 potential competitors
✅ See which competitors are NEW / CONTINUING / DISAPPEARED (if previous analysis exists)
✅ View change summary dashboard
✅ Select competitors to analyze
✅ Add custom competitors manually
✅ Proceed to Stage 3 (feature extraction - Module 6)

## Backend Implementation

### 1. Competitor Researcher Agent

Location: `app/agents/competitor_researcher.py`

```python
from typing import Dict, Any, Type, List
from pydantic import BaseModel, Field, HttpUrl
from app.agents.base_agent import BaseAgent

class CompetitorResult(BaseModel):
    """Single competitor discovery result"""
    name: str = Field(..., description="Competitor product name")
    url: HttpUrl = Field(..., description="Primary website URL")
    summary: str = Field(..., description="2-3 sentence summary of what they do")
    relevance_score: float = Field(
        ..., 
        ge=0.0, 
        le=1.0, 
        description="How directly they compete (0.0-1.0)"
    )

class CompetitorResearchOutput(BaseModel):
    """Output schema for Competitor Researcher Agent"""
    competitors: List[CompetitorResult] = Field(
        ..., 
        description="List of discovered competitors",
        min_items=5,
        max_items=20
    )
    research_summary: str = Field(
        ..., 
        description="Brief summary of competitive landscape"
    )

class CompetitorResearcherAgent(BaseAgent):
    """
    Discovers competing products through web research.
    
    Uses product information to search for and identify competitors.
    Returns ranked list of competitors with relevance scores.
    """
    
    def get_system_prompt(self) -> str:
        return """You are a Competitor Research agent specializing in market intelligence.

Your role is to discover competing products based on a target product's description.

You must:
1. Identify direct competitors (products serving the same market/needs)
2. Prioritize active, established products over defunct or tangential ones
3. Provide accurate URLs and concise summaries
4. Score relevance objectively (1.0 = direct competitor, 0.5 = adjacent market)

Focus on quality over quantity. Return 10-15 most relevant competitors.

Always respond with valid JSON matching the specified schema."""
    
    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        product_name = input_data.get('product_name', '')
        product_category = input_data.get('product_category', '')
        core_features = input_data.get('core_features', [])
        target_users = input_data.get('target_users', '')
        search_keywords = input_data.get('competitor_search_keywords', [])
        
        prompt = f"""Research and identify competing products for the following:

**Target Product:** {product_name}
**Category:** {product_category}
**Key Features:** {', '.join(core_features)}
**Target Users:** {target_users}
**Search Keywords:** {', '.join(search_keywords)}

Your task:
1. Use web search to discover 10-15 competing products
2. For each competitor, provide:
   - Product name (official name)
   - Primary website URL (homepage or main product page)
   - Summary (2-3 sentences explaining what they do)
   - Relevance score (0.0-1.0, where 1.0 = direct competitor)

3. Also provide a brief research_summary (2-3 sentences) describing the competitive landscape

Guidelines:
- Focus on DIRECT competitors (same market, same user needs)
- Prefer established, active products
- Include variety (large players and emerging competitors)
- Verify URLs are valid and current
- Be objective with relevance scores

Return the results as JSON in the specified format.
"""
        return prompt
    
    def get_output_schema(self) -> Type[BaseModel]:
        return CompetitorResearchOutput
    
    def get_stage(self) -> str:
        return "competitor_discovery"


class DifferentialAnalysisAgent(BaseAgent):
    """
    Compares new competitor discoveries with previous analysis.
    
    Identifies:
    - NEW: Competitors not in previous analysis
    - CONTINUING: Competitors in both analyses  
    - DISAPPEARED: Previous competitors not found currently
    """
    
    def get_system_prompt(self) -> str:
        return """You are a Differential Analysis agent specializing in competitive intelligence.

Your role is to compare new competitor discovery results with a previous analysis to identify changes in the competitive landscape.

You must:
1. Match competitors between current and previous analyses (by name/URL similarity)
2. Categorize each competitor as: NEW, CONTINUING, or DISAPPEARED
3. Assess significance of changes (how important is this shift?)
4. Provide clear explanations for status changes

Be analytical and highlight truly meaningful competitive shifts, not minor variations.

Always respond with valid JSON matching the specified schema."""
    
    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        current_competitors = input_data.get('current_competitors', [])
        previous_competitors = input_data.get('previous_competitors', [])
        product_name = input_data.get('product_name', '')
        
        prompt = f"""Compare competitor analyses for: {product_name}

**Current Analysis:**
{self._format_competitors(current_competitors)}

**Previous Analysis:**
{self._format_competitors(previous_competitors)}

Your task:
1. Match competitors between the two lists (by name and URL)
2. For each current competitor, determine:
   - status: "new" (wasn't in previous), "continuing" (in both), or "disappeared" (only in previous)
   - status_explanation: Brief reason for the status (e.g., "New market entrant", "Still active competitor")
   - significance: "low", "medium", or "high" (how important is this change?)
   - previous_competitor_match: If continuing, which previous competitor it matches

3. Provide summary statistics:
   - new_count: Number of new competitors
   - continuing_count: Number of continuing competitors
   - disappeared_count: Number of disappeared competitors
   - significant_changes: List of 2-4 brief descriptions of important changes

Return JSON format:
{{
  "competitors": [
    {{
      "name": "...",
      "url": "...",
      "summary": "...",
      "relevance_score": 0.9,
      "status": "new"|"continuing"|"disappeared",
      "status_explanation": "...",
      "significance": "low"|"medium"|"high",
      "previous_competitor_id": "uuid or null"
    }}
  ],
  "summary": {{
    "new_count": 0,
    "continuing_count": 0,
    "disappeared_count": 0,
    "significant_changes": ["..."]
  }}
}}
"""
        return prompt
    
    def _format_competitors(self, competitors: List[Dict]) -> str:
        """Format competitor list for prompt"""
        if not competitors:
            return "(None)"
        
        lines = []
        for comp in competitors:
            lines.append(f"- {comp.get('name', 'Unknown')}: {comp.get('url', 'N/A')}")
        return '\n'.join(lines)
    
    def get_output_schema(self) -> Type[BaseModel]:
        class DifferentialOutput(BaseModel):
            class CompetitorWithStatus(BaseModel):
                name: str
                url: str
                summary: str
                relevance_score: float
                status: str = Field(..., pattern="^(new|continuing|disappeared)$")
                status_explanation: str
                significance: str = Field(..., pattern="^(low|medium|high)$")
                previous_competitor_id: str | None = None
            
            class Summary(BaseModel):
                new_count: int
                continuing_count: int
                disappeared_count: int
                significant_changes: List[str]
            
            competitors: List[CompetitorWithStatus]
            summary: Summary
        
        return DifferentialOutput
    
    def get_stage(self) -> str:
        return "differential_analysis"
```

### 2. Competitor Intelligence Service

Location: `app/services/competitor_intelligence_service.py`

```python
from typing import List, Dict, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.competitor_intelligence import (
    CompetitorAnalysisSession,
    ProductCompetitor,
    SessionCompetitor
)
from app.agents.competitor_researcher import (
    CompetitorResearcherAgent, 
    DifferentialAnalysisAgent
)
from app.services.llm_service import LLMService

class CompetitorIntelligenceService:
    """Service for competitor intelligence operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def discover_competitors(
        self,
        session_id: UUID,
        llm_service: LLMService
    ) -> Dict:
        """
        Discover competitors for a session.
        
        If session has comparison enabled, performs differential analysis.
        """
        # Get session
        session = self.db.query(CompetitorAnalysisSession).filter(
            CompetitorAnalysisSession.id == session_id
        ).first()
        
        if not session:
            raise ValueError("Session not found")
        
        # Get product info for research
        product_data = session.analyzed_product_structure
        
        # Run competitor research
        researcher = CompetitorResearcherAgent(
            db=self.db,
            llm_service=llm_service,
            session_id=session_id,
            product_id=session.product_id
        )
        
        research_result = await researcher.execute({
            'product_name': product_data.get('product_name'),
            'product_category': product_data.get('product_category'),
            'core_features': product_data.get('core_features', []),
            'target_users': product_data.get('target_users'),
            'competitor_search_keywords': product_data.get('competitor_search_keywords', [])
        })
        
        # If differential analysis, compare with previous
        if session.analysis_type == "differential" and session.comparison_to_session_id:
            previous_competitors = self._get_previous_competitors(
                session.comparison_to_session_id
            )
            
            differential_agent = DifferentialAnalysisAgent(
                db=self.db,
                llm_service=llm_service,
                session_id=session_id,
                product_id=session.product_id
            )
            
            comparison_result = await differential_agent.execute({
                'current_competitors': research_result['competitors'],
                'previous_competitors': previous_competitors,
                'product_name': product_data.get('product_name')
            })
            
            # Store competitors with status
            stored_competitors = self._store_competitors_with_status(
                session_id=session_id,
                product_id=session.product_id,
                competitors_data=comparison_result['competitors']
            )
            
            return {
                'competitors': stored_competitors,
                'change_summary': comparison_result['summary'],
                'research_summary': research_result.get('research_summary'),
                'has_comparison': True
            }
        
        else:
            # Store competitors without status
            stored_competitors = self._store_competitors_without_status(
                session_id=session_id,
                product_id=session.product_id,
                competitors_data=research_result['competitors']
            )
            
            return {
                'competitors': stored_competitors,
                'change_summary': None,
                'research_summary': research_result.get('research_summary'),
                'has_comparison': False
            }
    
    def _get_previous_competitors(self, previous_session_id: UUID) -> List[Dict]:
        """Get competitors from previous session"""
        competitors = self.db.query(SessionCompetitor).filter(
            SessionCompetitor.session_id == previous_session_id,
            SessionCompetitor.selected_by_user == True
        ).all()
        
        return [
            {
                'id': str(comp.id),
                'name': comp.competitor_name,
                'url': comp.competitor_url,
                'summary': comp.ai_summary
            }
            for comp in competitors
        ]
    
    def _store_competitors_with_status(
        self,
        session_id: UUID,
        product_id: UUID,
        competitors_data: List[Dict]
    ) -> List[Dict]:
        """Store competitors with change status from differential analysis"""
        stored = []
        
        for comp_data in competitors_data:
            # Get or create product-level competitor
            product_competitor = self._get_or_create_product_competitor(
                product_id=product_id,
                competitor_name=comp_data['name'],
                competitor_url=comp_data['url'],
                session_id=session_id
            )
            
            # Create session-specific competitor
            session_competitor = SessionCompetitor(
                session_id=session_id,
                product_competitor_id=product_competitor.id,
                competitor_name=comp_data['name'],
                competitor_url=comp_data['url'],
                ai_summary=comp_data.get('summary'),
                discovery_source='ai_search',
                is_new_discovery=(comp_data['status'] == 'new'),
                selected_by_user=False,  # User will select later
                status_change=comp_data['status']
            )
            
            self.db.add(session_competitor)
            self.db.commit()
            self.db.refresh(session_competitor)
            
            stored.append({
                'id': str(session_competitor.id),
                'name': comp_data['name'],
                'url': comp_data['url'],
                'summary': comp_data.get('summary'),
                'relevance_score': comp_data.get('relevance_score'),
                'status': comp_data['status'],
                'status_explanation': comp_data.get('status_explanation'),
                'significance': comp_data.get('significance'),
                'selected': False
            })
        
        return stored
    
    def _store_competitors_without_status(
        self,
        session_id: UUID,
        product_id: UUID,
        competitors_data: List[Dict]
    ) -> List[Dict]:
        """Store competitors without change status (first analysis)"""
        stored = []
        
        for comp_data in competitors_data:
            # Get or create product-level competitor
            product_competitor = self._get_or_create_product_competitor(
                product_id=product_id,
                competitor_name=comp_data['name'],
                competitor_url=comp_data['url'],
                session_id=session_id
            )
            
            # Create session-specific competitor
            session_competitor = SessionCompetitor(
                session_id=session_id,
                product_competitor_id=product_competitor.id,
                competitor_name=comp_data['name'],
                competitor_url=comp_data['url'],
                ai_summary=comp_data.get('summary'),
                discovery_source='ai_search',
                is_new_discovery=True,
                selected_by_user=False,
                status_change=None
            )
            
            self.db.add(session_competitor)
            self.db.commit()
            self.db.refresh(session_competitor)
            
            stored.append({
                'id': str(session_competitor.id),
                'name': comp_data['name'],
                'url': comp_data['url'],
                'summary': comp_data.get('summary'),
                'relevance_score': comp_data.get('relevance_score'),
                'selected': False
            })
        
        return stored
    
    def _get_or_create_product_competitor(
        self,
        product_id: UUID,
        competitor_name: str,
        competitor_url: str,
        session_id: UUID
    ) -> ProductCompetitor:
        """Get existing or create new product-level competitor"""
        # Try to find existing by name
        existing = self.db.query(ProductCompetitor).filter(
            ProductCompetitor.product_id == product_id,
            ProductCompetitor.competitor_name == competitor_name
        ).first()
        
        if existing:
            # Update last_seen
            existing.last_seen_session_id = session_id
            existing.status = "active"
            self.db.commit()
            return existing
        
        # Create new
        product_competitor = ProductCompetitor(
            product_id=product_id,
            competitor_name=competitor_name,
            competitor_url=competitor_url,
            first_discovered_session_id=session_id,
            last_seen_session_id=session_id,
            status="active"
        )
        
        self.db.add(product_competitor)
        self.db.commit()
        self.db.refresh(product_competitor)
        
        return product_competitor
    
    async def confirm_competitors(
        self,
        session_id: UUID,
        selected_ids: List[UUID],
        custom_competitors: Optional[List[Dict]] = None
    ) -> Dict:
        """
        User confirms which competitors to analyze.
        
        Args:
            session_id: The session ID
            selected_ids: IDs of session_competitors to include
            custom_competitors: Additional competitors added manually
        """
        # Update selected competitors
        self.db.query(SessionCompetitor).filter(
            SessionCompetitor.session_id == session_id
        ).update({"selected_by_user": False})
        
        if selected_ids:
            self.db.query(SessionCompetitor).filter(
                SessionCompetitor.id.in_(selected_ids)
            ).update({"selected_by_user": True}, synchronize_session=False)
        
        # Add custom competitors
        if custom_competitors:
            session = self.db.query(CompetitorAnalysisSession).filter(
                CompetitorAnalysisSession.id == session_id
            ).first()
            
            for custom in custom_competitors:
                product_competitor = self._get_or_create_product_competitor(
                    product_id=session.product_id,
                    competitor_name=custom['name'],
                    competitor_url=custom.get('url', ''),
                    session_id=session_id
                )
                
                session_competitor = SessionCompetitor(
                    session_id=session_id,
                    product_competitor_id=product_competitor.id,
                    competitor_name=custom['name'],
                    competitor_url=custom.get('url', ''),
                    ai_summary=custom.get('summary', 'User-added competitor'),
                    discovery_source='user_added',
                    is_new_discovery=True,
                    selected_by_user=True,
                    status_change=None
                )
                
                self.db.add(session_competitor)
        
        self.db.commit()
        
        # Get count of selected
        selected_count = self.db.query(SessionCompetitor).filter(
            SessionCompetitor.session_id == session_id,
            SessionCompetitor.selected_by_user == True
        ).count()
        
        return {
            'confirmed': True,
            'selected_count': selected_count
        }
    
    async def get_session_competitors(
        self,
        session_id: UUID
    ) -> List[Dict]:
        """Get all competitors for a session"""
        competitors = self.db.query(SessionCompetitor).filter(
            SessionCompetitor.session_id == session_id
        ).all()
        
        return [
            {
                'id': str(comp.id),
                'name': comp.competitor_name,
                'url': comp.competitor_url,
                'summary': comp.ai_summary,
                'discovery_source': comp.discovery_source,
                'is_new_discovery': comp.is_new_discovery,
                'selected': comp.selected_by_user,
                'status_change': comp.status_change
            }
            for comp in competitors
        ]
```

### 3. API Endpoints

Location: `app/routers/competitor_intelligence.py` (new file or add to sessions.py)

```python
from fastapi import APIRouter, Depends, HTTPException, status, Body
from uuid import UUID
from typing import List, Optional
from pydantic import BaseModel
from app.services.competitor_intelligence_service import CompetitorIntelligenceService
from app.services.llm_service import LLMService
from app.dependencies import get_current_user, get_db
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/api/competitor-intelligence",
    tags=["competitor-intelligence"]
)

class ConfirmCompetitorsRequest(BaseModel):
    selected_ids: List[UUID]
    custom_competitors: Optional[List[dict]] = None

@router.post("/sessions/{session_id}/discover-competitors")
async def discover_competitors(
    session_id: UUID,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Discover competitors for a session using AI research.
    
    If session has comparison enabled, performs differential analysis.
    """
    service = CompetitorIntelligenceService(db)
    llm_service = LLMService()
    
    try:
        result = await service.discover_competitors(
            session_id=session_id,
            llm_service=llm_service
        )
        
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

@router.get("/sessions/{session_id}/competitors")
async def get_session_competitors(
    session_id: UUID,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all competitors for a session"""
    service = CompetitorIntelligenceService(db)
    
    competitors = await service.get_session_competitors(session_id)
    
    return {
        'competitors': competitors
    }

@router.post("/sessions/{session_id}/confirm-competitors")
async def confirm_competitors(
    session_id: UUID,
    data: ConfirmCompetitorsRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Confirm which competitors to analyze.
    
    User selects from discovered competitors and/or adds custom ones.
    """
    service = CompetitorIntelligenceService(db)
    
    result = await service.confirm_competitors(
        session_id=session_id,
        selected_ids=data.selected_ids,
        custom_competitors=data.custom_competitors
    )
    
    return result
```

**Register Router:**
In `app/main.py`:
```python
from app.routers import competitor_intelligence

app.include_router(competitor_intelligence.router)
```

## Frontend Implementation

### 1. Stage 2: Competitor Discovery

Location: `src/pages/CompetitorIntelligence/stages/Stage2_CompetitorDiscovery.tsx`

```typescript
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import CompetitorCard from '../components/CompetitorCard';
import ChangeSummaryCard from '../components/ChangeSummaryCard';
import AddCompetitorModal from '../components/AddCompetitorModal';

interface Stage2Props {
  sessionId: string;
  hasPreviousAnalysis: boolean;
  onComplete: () => void;
  onBack: () => void;
}

interface Competitor {
  id: string;
  name: string;
  url: string;
  summary: string;
  relevance_score?: number;
  status?: 'new' | 'continuing' | 'disappeared';
  status_explanation?: string;
  significance?: 'low' | 'medium' | 'high';
  selected: boolean;
  discovery_source?: string;
}

interface ChangeSummary {
  new_count: number;
  continuing_count: number;
  disappeared_count: number;
  significant_changes: string[];
}

type ViewMode = 'loading' | 'reviewing' | 'error';

const Stage2_CompetitorDiscovery: React.FC<Stage2Props> = ({
  sessionId,
  hasPreviousAnalysis,
  onComplete,
  onBack,
}) => {
  const [mode, setMode] = useState<ViewMode>('loading');
  const [competitors, setCompetitors] = useState<Competitor[]>([]);
  const [changeSummary, setChangeSummary] = useState<ChangeSummary | null>(null);
  const [researchSummary, setResearchSummary] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    discoverCompetitors();
  }, []);

  const discoverCompetitors = async () => {
    try {
      setMode('loading');
      const response = await axios.post(
        `/api/competitor-intelligence/sessions/${sessionId}/discover-competitors`
      );

      setCompetitors(response.data.competitors);
      setChangeSummary(response.data.change_summary);
      setResearchSummary(response.data.research_summary);
      setMode('reviewing');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to discover competitors');
      setMode('error');
    }
  };

  const toggleCompetitor = (competitorId: string) => {
    setCompetitors((prev) =>
      prev.map((c) =>
        c.id === competitorId ? { ...c, selected: !c.selected } : c
      )
    );
  };

  const handleAddCustom = (competitor: { name: string; url: string; summary?: string }) => {
    // Add to local state (will be sent to backend on confirm)
    const newCompetitor: Competitor = {
      id: `temp-${Date.now()}`,
      name: competitor.name,
      url: competitor.url,
      summary: competitor.summary || 'User-added competitor',
      selected: true,
      discovery_source: 'user_added',
    };
    setCompetitors((prev) => [...prev, newCompetitor]);
    setShowAddModal(false);
  };

  const handleConfirm = async () => {
    const selectedIds = competitors
      .filter((c) => c.selected && !c.id.startsWith('temp-'))
      .map((c) => c.id);

    const customCompetitors = competitors
      .filter((c) => c.selected && c.id.startsWith('temp-'))
      .map((c) => ({
        name: c.name,
        url: c.url,
        summary: c.summary,
      }));

    if (selectedIds.length === 0 && customCompetitors.length === 0) {
      alert('Please select at least one competitor');
      return;
    }

    setSubmitting(true);

    try {
      await axios.post(
        `/api/competitor-intelligence/sessions/${sessionId}/confirm-competitors`,
        {
          selected_ids: selectedIds,
          custom_competitors: customCompetitors.length > 0 ? customCompetitors : null,
        }
      );

      onComplete();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to confirm competitors');
    } finally {
      setSubmitting(false);
    }
  };

  if (mode === 'loading') {
    return (
      <div className="text-center py-12">
        <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
        <h3 className="text-lg font-medium text-gray-900 mb-2">
          Discovering Competitors...
        </h3>
        <p className="text-gray-600">
          AI is researching the competitive landscape
        </p>
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
          Discovery Failed
        </h3>
        <p className="text-gray-600 mb-4">{error}</p>
        <button
          onClick={discoverCompetitors}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          Retry
        </button>
      </div>
    );
  }

  const selectedCount = competitors.filter((c) => c.selected).length;

  return (
    <div>
      <div className="flex justify-between items-start mb-6">
        <div>
          <h2 className="text-2xl font-bold mb-2">Competitor Discovery</h2>
          <p className="text-gray-600">{researchSummary}</p>
        </div>
        <div className="text-sm text-gray-600">
          {selectedCount} of {competitors.length} selected
        </div>
      </div>

      {hasPreviousAnalysis && changeSummary && (
        <ChangeSummaryCard changeSummary={changeSummary} />
      )}

      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-red-800">{error}</p>
        </div>
      )}

      <div className="mb-6">
        <button
          onClick={() => setShowAddModal(true)}
          className="px-4 py-2 border border-blue-600 text-blue-600 rounded-lg hover:bg-blue-50"
        >
          + Add Custom Competitor
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {competitors.map((competitor) => (
          <CompetitorCard
            key={competitor.id}
            competitor={competitor}
            onToggle={() => toggleCompetitor(competitor.id)}
            showStatus={hasPreviousAnalysis}
          />
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
          onClick={handleConfirm}
          disabled={submitting || selectedCount === 0}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
        >
          {submitting ? 'Confirming...' : `Extract Features (${selectedCount}) →`}
        </button>
      </div>

      {showAddModal && (
        <AddCompetitorModal
          onAdd={handleAddCustom}
          onClose={() => setShowAddModal(false)}
        />
      )}
    </div>
  );
};

export default Stage2_CompetitorDiscovery;
```

### 2. Competitor Card Component

Location: `src/pages/CompetitorIntelligence/components/CompetitorCard.tsx`

```typescript
import React from 'react';

interface CompetitorCardProps {
  competitor: {
    id: string;
    name: string;
    url: string;
    summary: string;
    relevance_score?: number;
    status?: 'new' | 'continuing' | 'disappeared';
    status_explanation?: string;
    significance?: 'low' | 'medium' | 'high';
    selected: boolean;
    discovery_source?: string;
  };
  onToggle: () => void;
  showStatus: boolean;
}

const CompetitorCard: React.FC<CompetitorCardProps> = ({
  competitor,
  onToggle,
  showStatus,
}) => {
  const getStatusBadge = () => {
    if (!showStatus || !competitor.status) return null;

    const badges = {
      new: { bg: 'bg-green-100', text: 'text-green-800', label: 'NEW' },
      continuing: { bg: 'bg-blue-100', text: 'text-blue-800', label: 'CONTINUING' },
      disappeared: { bg: 'bg-red-100', text: 'text-red-800', label: 'DISAPPEARED' },
    };

    const badge = badges[competitor.status];

    return (
      <span
        className={`inline-block px-2 py-1 rounded-full text-xs font-medium ${badge.bg} ${badge.text}`}
      >
        {badge.label}
      </span>
    );
  };

  return (
    <div
      className={`border rounded-lg p-4 cursor-pointer transition-all ${
        competitor.selected
          ? 'border-blue-500 bg-blue-50'
          : 'border-gray-200 hover:border-blue-300'
      }`}
      onClick={onToggle}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-start flex-1">
          <input
            type="checkbox"
            checked={competitor.selected}
            onChange={onToggle}
            onClick={(e) => e.stopPropagation()}
            className="mt-1 mr-3"
          />
          <div className="flex-1">
            <h3 className="font-semibold text-gray-900 mb-1">
              {competitor.name}
            </h3>
            {getStatusBadge()}
          </div>
        </div>
      </div>

      <a
        href={competitor.url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-sm text-blue-600 hover:underline mb-2 block"
        onClick={(e) => e.stopPropagation()}
      >
        {competitor.url}
      </a>

      <p className="text-sm text-gray-700 mb-2">{competitor.summary}</p>

      {showStatus && competitor.status_explanation && (
        <p className="text-xs text-gray-600 italic">
          {competitor.status_explanation}
        </p>
      )}

      {competitor.discovery_source === 'user_added' && (
        <span className="inline-block px-2 py-1 bg-purple-100 text-purple-800 text-xs rounded-full mt-2">
          User Added
        </span>
      )}
    </div>
  );
};

export default CompetitorCard;
```

### 3. Change Summary Component

Location: `src/pages/CompetitorIntelligence/components/ChangeSummaryCard.tsx`

```typescript
import React from 'react';

interface ChangeSummaryCardProps {
  changeSummary: {
    new_count: number;
    continuing_count: number;
    disappeared_count: number;
    significant_changes: string[];
  };
}

const ChangeSummaryCard: React.FC<ChangeSummaryCardProps> = ({ changeSummary }) => {
  return (
    <div className="mb-6 p-6 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg">
      <div className="flex items-start mb-4">
        <svg
          className="w-6 h-6 text-blue-600 mr-2 flex-shrink-0"
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path
            fillRule="evenodd"
            d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
            clipRule="evenodd"
          />
        </svg>
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            Competitive Landscape Changes
          </h3>
          <p className="text-sm text-gray-700 mb-4">
            Comparing with previous analysis
          </p>

          <div className="grid grid-cols-3 gap-4 mb-4">
            <div className="bg-white rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-green-600">
                {changeSummary.new_count}
              </div>
              <div className="text-xs text-gray-600">New Competitors</div>
            </div>
            <div className="bg-white rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-blue-600">
                {changeSummary.continuing_count}
              </div>
              <div className="text-xs text-gray-600">Continuing</div>
            </div>
            <div className="bg-white rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-red-600">
                {changeSummary.disappeared_count}
              </div>
              <div className="text-xs text-gray-600">Disappeared</div>
            </div>
          </div>

          {changeSummary.significant_changes.length > 0 && (
            <div>
              <h4 className="font-medium text-gray-900 mb-2">
                Significant Changes:
              </h4>
              <ul className="space-y-1">
                {changeSummary.significant_changes.map((change, idx) => (
                  <li key={idx} className="text-sm text-gray-700 flex items-start">
                    <span className="text-blue-600 mr-2">•</span>
                    <span>{change}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ChangeSummaryCard;
```

### 4. Add Competitor Modal

Location: `src/pages/CompetitorIntelligence/components/AddCompetitorModal.tsx`

```typescript
import React, { useState } from 'react';

interface AddCompetitorModalProps {
  onAdd: (competitor: { name: string; url: string; summary?: string }) => void;
  onClose: () => void;
}

const AddCompetitorModal: React.FC<AddCompetitorModalProps> = ({
  onAdd,
  onClose,
}) => {
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [summary, setSummary] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onAdd({ name, url, summary: summary || undefined });
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
        <h3 className="text-xl font-bold mb-4">Add Custom Competitor</h3>

        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Competitor Name *
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              placeholder="e.g., Competitor Inc."
              required
            />
          </div>

          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Website URL *
            </label>
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              placeholder="https://competitor.com"
              required
            />
          </div>

          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Summary (Optional)
            </label>
            <textarea
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              placeholder="Brief description of what they do..."
            />
          </div>

          <div className="flex justify-end space-x-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Add Competitor
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AddCompetitorModal;
```

### 5. Update Wizard to Include Stage 2

Location: `src/pages/CompetitorIntelligence/AnalysisWizard.tsx`

```typescript
import Stage2_CompetitorDiscovery from './stages/Stage2_CompetitorDiscovery';

// In the render section, replace the placeholder:
{wizardState.currentStage === 2 && (
  <Stage2_CompetitorDiscovery
    sessionId={wizardState.sessionId!}
    hasPreviousAnalysis={wizardState.hasPreviousAnalysis}
    onComplete={goToNextStage}
    onBack={goToPreviousStage}
  />
)}
```

## Testing Requirements

### Backend Unit Tests

Location: `tests/test_competitor_researcher.py`

```python
import pytest
from app.agents.competitor_researcher import CompetitorResearcherAgent, DifferentialAnalysisAgent

@pytest.mark.asyncio
async def test_competitor_researcher_agent(db_session, mock_llm_service):
    """Test CompetitorResearcherAgent execution"""
    mock_llm_service.call_agent.return_value = {
        "content": '''```json
{
    "competitors": [
        {
            "name": "Competitor A",
            "url": "https://competitor-a.com",
            "summary": "A leading CRM platform",
            "relevance_score": 0.9
        }
    ],
    "research_summary": "Competitive landscape analysis"
}
```''',
        "tokens_used": 300
    }
    
    agent = CompetitorResearcherAgent(db=db_session, llm_service=mock_llm_service)
    
    result = await agent.execute({
        'product_name': 'Test CRM',
        'product_category': 'CRM Software',
        'core_features': ['Contact Management'],
        'target_users': 'SMBs',
        'competitor_search_keywords': ['crm', 'sales']
    })
    
    assert len(result['competitors']) >= 1
    assert result['competitors'][0]['name'] == 'Competitor A'
    assert 'research_summary' in result

@pytest.mark.asyncio
async def test_differential_analysis_agent(db_session, mock_llm_service):
    """Test DifferentialAnalysisAgent execution"""
    mock_llm_service.call_agent.return_value = {
        "content": '''```json
{
    "competitors": [
        {
            "name": "Competitor A",
            "url": "https://competitor-a.com",
            "summary": "Summary",
            "relevance_score": 0.9,
            "status": "continuing",
            "status_explanation": "Still active",
            "significance": "low",
            "previous_competitor_id": null
        }
    ],
    "summary": {
        "new_count": 0,
        "continuing_count": 1,
        "disappeared_count": 0,
        "significant_changes": []
    }
}
```''',
        "tokens_used": 250
    }
    
    agent = DifferentialAnalysisAgent(db=db_session, llm_service=mock_llm_service)
    
    result = await agent.execute({
        'current_competitors': [{'name': 'Competitor A', 'url': 'https://competitor-a.com'}],
        'previous_competitors': [{'name': 'Competitor A', 'url': 'https://competitor-a.com'}],
        'product_name': 'Test Product'
    })
    
    assert 'competitors' in result
    assert 'summary' in result
    assert result['summary']['continuing_count'] == 1
```

Location: `tests/test_competitor_intelligence_service.py`

```python
import pytest
from app.services.competitor_intelligence_service import CompetitorIntelligenceService

@pytest.mark.asyncio
async def test_discover_competitors(
    db_session, test_session, mock_llm_service
):
    """Test competitor discovery"""
    service = CompetitorIntelligenceService(db_session)
    
    # Mock both agents
    mock_llm_service.call_agent.return_value = {
        "content": '{"competitors": [{"name": "Test", "url": "https://test.com", "summary": "Summary", "relevance_score": 0.8}], "research_summary": "Summary"}',
        "tokens_used": 200
    }
    
    result = await service.discover_competitors(
        session_id=test_session.id,
        llm_service=mock_llm_service
    )
    
    assert 'competitors' in result
    assert len(result['competitors']) > 0
    assert result['has_comparison'] == False

@pytest.mark.asyncio
async def test_confirm_competitors(db_session, test_session, test_session_competitors):
    """Test competitor confirmation"""
    service = CompetitorIntelligenceService(db_session)
    
    result = await service.confirm_competitors(
        session_id=test_session.id,
        selected_ids=[test_session_competitors[0].id],
        custom_competitors=None
    )
    
    assert result['confirmed'] == True
    assert result['selected_count'] == 1
```

### Frontend Manual Testing

1. **Navigate through Stage 1 to Stage 2**
2. **Wait for competitor discovery**
   - Should show loading state
   - Should display discovered competitors
3. **Test competitor selection**
   - Click competitors to select/deselect
   - Selected count should update
4. **Test comparison mode** (if previous analysis exists)
   - Should show change summary card
   - Should show status badges (NEW/CONTINUING/DISAPPEARED)
5. **Test add custom competitor**
   - Click "Add Custom Competitor"
   - Fill form and submit
   - Should appear in list with "User Added" badge
6. **Test confirmation**
   - Select competitors
   - Click "Extract Features"
   - Should proceed to Stage 3

## Acceptance Criteria

**Backend:**
- [ ] CompetitorResearcherAgent discovers 10-15 competitors
- [ ] DifferentialAnalysisAgent compares with previous analysis
- [ ] Competitors stored in database with correct relationships
- [ ] Product-level competitors tracked across sessions
- [ ] Session-specific competitors with status tracking
- [ ] Confirmation API updates selected competitors
- [ ] All unit tests pass

**Frontend:**
- [ ] Stage 2 loads and discovers competitors automatically
- [ ] Competitor cards display correctly
- [ ] Can select/deselect competitors
- [ ] Change summary displays (when applicable)
- [ ] Status badges show correctly (NEW/CONTINUING/DISAPPEARED)
- [ ] Can add custom competitors
- [ ] Confirmation proceeds to Stage 3
- [ ] Loading and error states work

**Integration:**
- [ ] End-to-end flow: Stage 1 → Stage 2 → confirmation
- [ ] Comparison mode works when previous sessions exist
- [ ] First analysis (no comparison) works correctly
- [ ] Selected competitors ready for feature extraction (Module 6)

## Files to Create/Modify

**New Backend Files:**
- `app/agents/competitor_researcher.py`
- `app/services/competitor_intelligence_service.py`
- `app/routers/competitor_intelligence.py`
- `tests/test_competitor_researcher.py`
- `tests/test_competitor_intelligence_service.py`

**New Frontend Files:**
- `src/pages/CompetitorIntelligence/stages/Stage2_CompetitorDiscovery.tsx`
- `src/pages/CompetitorIntelligence/components/CompetitorCard.tsx`
- `src/pages/CompetitorIntelligence/components/ChangeSummaryCard.tsx`
- `src/pages/CompetitorIntelligence/components/AddCompetitorModal.tsx`

**Modified Files:**
- `app/main.py` (register router)
- `src/pages/CompetitorIntelligence/AnalysisWizard.tsx` (add Stage 2)

## Estimated Time
**3-4 days** including testing

## Next Module
After completing this module, proceed to **Module 6: Feature Extraction with Parallel Processing**

---

**Note:** After this module, users can discover and select competitors. Stage 3 (feature extraction) will be added in Module 6.
