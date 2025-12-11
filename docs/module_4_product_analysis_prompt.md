# Module 4: Product Analysis Agent & Session Creation

## Objective
Implement the Product Analyzer AI agent and the first stage of the analysis wizard, allowing users to create/select products, input product descriptions, and have AI structure the product information.

## Dependencies
- **Requires**: 
  - Module 1 (Database Schema)
  - Module 2 (Product API - backend)
  - Module 3 (Base Agent Infrastructure)
- **Uses**: Existing authentication, React components

## Scope
- Product Analyzer AI agent
- Session creation logic
- Analysis wizard container (routing and state management)
- Stage 1: Product Definition UI
- Product creation/selection flow
- Integration with LLMService

## What Users Can Do After Module 4

✅ Click "New Product Analysis" button
✅ Choose existing product OR create new product
✅ Enter product description (text, file upload, or URL)
✅ AI analyzes and structures product information
✅ Review AI's understanding of product
✅ Proceed to Stage 2 (competitor discovery - Module 5)

## Backend Implementation

### 1. Product Analyzer Agent

Location: `app/agents/product_analyzer.py`

```python
from typing import Dict, Any, Type
from pydantic import BaseModel, Field
from app.agents.base_agent import BaseAgent

class ProductAnalysisOutput(BaseModel):
    """Output schema for Product Analyzer Agent"""
    product_name: str = Field(..., description="Extracted or confirmed product name")
    product_category: str = Field(..., description="Product category/industry")
    core_features: list[str] = Field(
        ..., 
        description="5-7 core features or capabilities",
        min_items=3,
        max_items=10
    )
    target_users: str = Field(..., description="Target users/customers description")
    value_propositions: list[str] = Field(
        ..., 
        description="Unique value propositions",
        min_items=1,
        max_items=5
    )
    competitor_search_keywords: list[str] = Field(
        ..., 
        description="Keywords for finding competitors",
        min_items=3,
        max_items=10
    )

class ProductAnalyzerAgent(BaseAgent):
    """
    Analyzes product descriptions and structures them for competitive analysis.
    
    Handles input from:
    - Text descriptions
    - Uploaded documents (extracted text)
    - URLs (webpage content)
    """
    
    def get_system_prompt(self) -> str:
        return """You are a Product Analyzer agent specializing in competitive intelligence.

Your role is to analyze product descriptions and extract structured information that will be used to:
1. Find competing products
2. Compare features across competitors
3. Generate strategic insights

You must be thorough but concise. Focus on aspects relevant to competitive analysis.

Always respond with valid JSON matching the specified schema."""
    
    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        product_name = input_data.get('product_name', '')
        product_description = input_data.get('product_description', '')
        source_type = input_data.get('source_type', 'text')
        
        prompt = f"""Analyze the following product information and extract structured data:

Product Name: {product_name if product_name else "(extract from description)"}
Source Type: {source_type}
Product Description:
{product_description}

Extract and return the following information in JSON format:

1. **product_name**: The product name (use provided name or extract from description)
2. **product_category**: The industry/category (e.g., "CRM Software", "Project Management", "E-commerce Platform")
3. **core_features**: List 5-7 key features or capabilities that define this product
4. **target_users**: Describe who uses this product (roles, company sizes, industries)
5. **value_propositions**: List 2-4 unique value propositions or competitive advantages
6. **competitor_search_keywords**: List 5-10 keywords/phrases to use when searching for competing products

Guidelines:
- Be specific and concrete
- Focus on differentiating characteristics
- Use industry-standard terminology
- Keywords should be search-friendly (2-4 words each)
- Avoid marketing fluff, focus on substance

Return ONLY the JSON object, no additional text.
"""
        return prompt
    
    def get_output_schema(self) -> Type[BaseModel]:
        return ProductAnalysisOutput
    
    def get_stage(self) -> str:
        return "product_analysis"
```

### 2. Session Service

Location: `app/services/session_service.py`

```python
from typing import Optional, Tuple
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.competitor_intelligence import (
    CIProduct, CompetitorAnalysisSession
)
from app.schemas.competitor_intelligence import SessionCreate
from app.agents.product_analyzer import ProductAnalyzerAgent
from app.services.llm_service import LLMService

class SessionService:
    """Service for managing analysis sessions"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def create_session(
        self,
        user_id: UUID,
        session_data: SessionCreate,
        llm_service: LLMService
    ) -> Tuple[CompetitorAnalysisSession, dict]:
        """
        Create a new analysis session and analyze the product.
        
        Returns:
            Tuple of (session, analyzed_product_structure)
        """
        # Get or create product
        product = await self._get_or_create_product(
            user_id=user_id,
            product_id=session_data.product_id,
            product_name=session_data.product_name,
            product_description=session_data.product_description,
            source_type=session_data.product_source_type,
            source_data=session_data.product_source_data,
            llm_service=llm_service
        )
        
        # Determine session number
        session_number = self._get_next_session_number(product.id)
        
        # Check if we should do comparison analysis
        analysis_type = "full"
        comparison_to_session_id = None
        
        if session_number > 1 and session_data.enable_comparison:
            # Get previous session for comparison
            previous_session = self._get_previous_session(product.id)
            if previous_session:
                analysis_type = "differential"
                comparison_to_session_id = previous_session.id
        
        # Create session
        session = CompetitorAnalysisSession(
            product_id=product.id,
            user_id=user_id,
            session_number=session_number,
            session_name=session_data.session_name,
            analysis_type=analysis_type,
            comparison_to_session_id=comparison_to_session_id,
            product_source_type=session_data.product_source_type,
            product_source_data=session_data.product_source_data,
            analyzed_product_structure=product.structured_product_data,
            status="active"
        )
        
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        
        # Update product last_analyzed
        product.last_analyzed_at = datetime.utcnow()
        product.analysis_count = session_number
        self.db.commit()
        
        return session, product.structured_product_data
    
    async def _get_or_create_product(
        self,
        user_id: UUID,
        product_id: Optional[UUID],
        product_name: Optional[str],
        product_description: Optional[str],
        source_type: str,
        source_data: Optional[dict],
        llm_service: LLMService
    ) -> CIProduct:
        """
        Get existing product or create new one with AI analysis.
        """
        # If product_id provided, fetch existing
        if product_id:
            product = self.db.query(CIProduct).filter(
                CIProduct.id == product_id
            ).first()
            
            if not product:
                raise ValueError(f"Product {product_id} not found")
            
            # Update description if provided (re-analyzing existing product)
            if product_description:
                product.product_description = product_description
                
                # Re-analyze with AI
                analyzed_structure = await self._analyze_product(
                    product_name=product.product_name,
                    product_description=product_description,
                    source_type=source_type,
                    llm_service=llm_service,
                    session_id=None,
                    product_id=product.id
                )
                
                product.structured_product_data = analyzed_structure
                self.db.commit()
            
            return product
        
        # Create new product
        if not product_name or not product_description:
            raise ValueError("Product name and description required for new product")
        
        # Check if product with this name already exists
        existing = self.db.query(CIProduct).filter(
            CIProduct.product_name == product_name
        ).first()
        
        if existing:
            raise ValueError(
                f"Product '{product_name}' already exists. "
                "Please select it from the list or use a different name."
            )
        
        # Analyze product with AI
        analyzed_structure = await self._analyze_product(
            product_name=product_name,
            product_description=product_description,
            source_type=source_type,
            llm_service=llm_service,
            session_id=None,
            product_id=None
        )
        
        # Create product
        product = CIProduct(
            user_id=user_id,  # Created by this user
            product_name=analyzed_structure.get('product_name', product_name),
            product_description=product_description,
            product_category=analyzed_structure.get('product_category'),
            structured_product_data=analyzed_structure,
            status="active"
        )
        
        self.db.add(product)
        self.db.commit()
        self.db.refresh(product)
        
        return product
    
    async def _analyze_product(
        self,
        product_name: str,
        product_description: str,
        source_type: str,
        llm_service: LLMService,
        session_id: Optional[UUID],
        product_id: Optional[UUID]
    ) -> dict:
        """
        Use Product Analyzer agent to structure product information.
        """
        agent = ProductAnalyzerAgent(
            db=self.db,
            llm_service=llm_service,
            session_id=session_id,
            product_id=product_id
        )
        
        result = await agent.execute({
            'product_name': product_name,
            'product_description': product_description,
            'source_type': source_type
        })
        
        return result
    
    def _get_next_session_number(self, product_id: UUID) -> int:
        """Get the next session number for a product."""
        max_session = self.db.query(
            func.max(CompetitorAnalysisSession.session_number)
        ).filter(
            CompetitorAnalysisSession.product_id == product_id
        ).scalar()
        
        return (max_session or 0) + 1
    
    def _get_previous_session(
        self, 
        product_id: UUID
    ) -> Optional[CompetitorAnalysisSession]:
        """Get the most recent completed session for a product."""
        return self.db.query(CompetitorAnalysisSession).filter(
            CompetitorAnalysisSession.product_id == product_id,
            CompetitorAnalysisSession.status == "completed"
        ).order_by(
            CompetitorAnalysisSession.session_number.desc()
        ).first()
    
    async def get_session(
        self, 
        session_id: UUID, 
        user_id: UUID
    ) -> Optional[CompetitorAnalysisSession]:
        """Get session by ID (no user ownership check - sessions are shared)."""
        return self.db.query(CompetitorAnalysisSession).filter(
            CompetitorAnalysisSession.id == session_id
        ).first()
    
    async def update_session_status(
        self,
        session_id: UUID,
        status: str
    ) -> bool:
        """Update session status."""
        session = self.db.query(CompetitorAnalysisSession).filter(
            CompetitorAnalysisSession.id == session_id
        ).first()
        
        if not session:
            return False
        
        session.status = status
        
        if status == "completed":
            session.completed_at = datetime.utcnow()
        
        self.db.commit()
        return True
```

### 3. Session API Endpoints

Location: `app/routers/sessions.py`

```python
from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from app.schemas.competitor_intelligence import SessionCreate, SessionResponse
from app.services.session_service import SessionService
from app.services.llm_service import LLMService
from app.dependencies import get_current_user, get_db
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/api/competitor-intelligence/sessions",
    tags=["sessions"]
)

@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_session(
    session_data: SessionCreate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new analysis session.
    
    This will:
    1. Get or create the product
    2. Analyze product description with AI (if new or updated)
    3. Create session record
    4. Return session info + analyzed product structure
    """
    service = SessionService(db)
    llm_service = LLMService()
    
    try:
        session, analyzed_structure = await service.create_session(
            user_id=current_user.id,
            session_data=session_data,
            llm_service=llm_service
        )
        
        return {
            "session": {
                "id": session.id,
                "product_id": session.product_id,
                "session_number": session.session_number,
                "session_name": session.session_name,
                "analysis_type": session.analysis_type,
                "status": session.status,
                "created_at": session.created_at
            },
            "analyzed_product": analyzed_structure,
            "has_previous_analysis": session.analysis_type == "differential"
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/{session_id}", response_model=dict)
async def get_session(
    session_id: UUID,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get session details"""
    service = SessionService(db)
    session = await service.get_session(session_id, current_user.id)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    return {
        "id": session.id,
        "product_id": session.product_id,
        "session_number": session.session_number,
        "session_name": session.session_name,
        "analysis_type": session.analysis_type,
        "status": session.status,
        "analyzed_product": session.analyzed_product_structure,
        "created_at": session.created_at,
        "completed_at": session.completed_at
    }

@router.patch("/{session_id}/status")
async def update_session_status(
    session_id: UUID,
    status: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update session status"""
    service = SessionService(db)
    success = await service.update_session_status(session_id, status)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    return {"status": "updated"}
```

**Register Router:**
In `app/main.py`:
```python
from app.routers import sessions

app.include_router(sessions.router)
```

### 4. Update Pydantic Schemas

Location: `app/schemas/competitor_intelligence.py` (add to existing)

```python
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from uuid import UUID

class SessionCreate(BaseModel):
    """Schema for creating a new session"""
    product_id: Optional[UUID] = None  # If selecting existing product
    product_name: Optional[str] = Field(None, min_length=1, max_length=255)  # If creating new
    product_description: Optional[str] = Field(None, min_length=10)  # Required if creating new
    session_name: Optional[str] = None
    product_source_type: str = Field(..., pattern="^(text|document|url)$")
    product_source_data: Optional[Dict[str, Any]] = None
    enable_comparison: bool = Field(default=True, description="Enable differential analysis if previous sessions exist")

class AnalyzedProduct(BaseModel):
    """Structured product analysis from AI"""
    product_name: str
    product_category: str
    core_features: list[str]
    target_users: str
    value_propositions: list[str]
    competitor_search_keywords: list[str]
```

## Frontend Implementation

### 1. Wizard Container

Location: `src/pages/CompetitorIntelligence/AnalysisWizard.tsx`

```typescript
import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import Stage1_ProductDefinition from './stages/Stage1_ProductDefinition';
// Stages 2-5 will be added in future modules

type Stage = 1 | 2 | 3 | 4 | 5;

interface WizardState {
  sessionId: string | null;
  productId: string | null;
  currentStage: Stage;
  analyzedProduct: any | null;
  hasPreviousAnalysis: boolean;
}

const AnalysisWizard: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const productIdParam = searchParams.get('product_id');

  const [wizardState, setWizardState] = useState<WizardState>({
    sessionId: null,
    productId: productIdParam,
    currentStage: 1,
    analyzedProduct: null,
    hasPreviousAnalysis: false,
  });

  const updateWizardState = (updates: Partial<WizardState>) => {
    setWizardState((prev) => ({ ...prev, ...updates }));
  };

  const goToNextStage = () => {
    if (wizardState.currentStage < 5) {
      updateWizardState({ currentStage: (wizardState.currentStage + 1) as Stage });
    }
  };

  const goToPreviousStage = () => {
    if (wizardState.currentStage > 1) {
      updateWizardState({ currentStage: (wizardState.currentStage - 1) as Stage });
    }
  };

  const handleExit = () => {
    if (confirm('Are you sure you want to exit? Progress may be lost.')) {
      navigate('/competitor-intelligence');
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Progress Header */}
      <div className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-2xl font-bold text-gray-900">
              Competitor Intelligence Analysis
            </h1>
            <button
              onClick={handleExit}
              className="text-gray-600 hover:text-gray-900"
            >
              Exit
            </button>
          </div>

          {/* Progress Stepper */}
          <div className="flex items-center justify-between">
            {[1, 2, 3, 4, 5].map((stage) => (
              <div
                key={stage}
                className="flex items-center"
              >
                <div
                  className={`
                    w-10 h-10 rounded-full flex items-center justify-center
                    ${
                      stage === wizardState.currentStage
                        ? 'bg-blue-600 text-white'
                        : stage < wizardState.currentStage
                        ? 'bg-green-500 text-white'
                        : 'bg-gray-200 text-gray-600'
                    }
                  `}
                >
                  {stage}
                </div>
                {stage < 5 && (
                  <div
                    className={`
                      h-1 w-24
                      ${
                        stage < wizardState.currentStage
                          ? 'bg-green-500'
                          : 'bg-gray-200'
                      }
                    `}
                  />
                )}
              </div>
            ))}
          </div>

          {/* Stage Labels */}
          <div className="flex items-center justify-between mt-2 text-xs">
            <span className={wizardState.currentStage === 1 ? 'font-bold' : ''}>
              Product
            </span>
            <span className={wizardState.currentStage === 2 ? 'font-bold' : ''}>
              Competitors
            </span>
            <span className={wizardState.currentStage === 3 ? 'font-bold' : ''}>
              Features
            </span>
            <span className={wizardState.currentStage === 4 ? 'font-bold' : ''}>
              Ideas
            </span>
            <span className={wizardState.currentStage === 5 ? 'font-bold' : ''}>
              Review
            </span>
          </div>
        </div>
      </div>

      {/* Stage Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {wizardState.currentStage === 1 && (
          <Stage1_ProductDefinition
            existingProductId={wizardState.productId}
            onComplete={(sessionId, analyzedProduct, hasPreviousAnalysis) => {
              updateWizardState({
                sessionId,
                analyzedProduct,
                hasPreviousAnalysis,
              });
              goToNextStage();
            }}
            onBack={handleExit}
          />
        )}

        {/* Stages 2-5 will be rendered here in future modules */}
        {wizardState.currentStage > 1 && (
          <div className="text-center py-12">
            <p className="text-gray-500">
              Stage {wizardState.currentStage} coming in next module
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default AnalysisWizard;
```

### 2. Stage 1: Product Definition

Location: `src/pages/CompetitorIntelligence/stages/Stage1_ProductDefinition.tsx`

```typescript
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import ProductSelector from '../components/ProductSelector';
import ProductInputForm from '../components/ProductInputForm';

interface Stage1Props {
  existingProductId: string | null;
  onComplete: (sessionId: string, analyzedProduct: any, hasPreviousAnalysis: boolean) => void;
  onBack: () => void;
}

type Mode = 'select' | 'create' | 'analyzing' | 'review';

const Stage1_ProductDefinition: React.FC<Stage1Props> = ({
  existingProductId,
  onComplete,
  onBack,
}) => {
  const [mode, setMode] = useState<Mode>(existingProductId ? 'create' : 'select');
  const [selectedProductId, setSelectedProductId] = useState<string | null>(
    existingProductId
  );
  const [analyzedProduct, setAnalyzedProduct] = useState<any>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [hasPreviousAnalysis, setHasPreviousAnalysis] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleProductSelect = (productId: string) => {
    setSelectedProductId(productId);
    setMode('create');
  };

  const handleCreateProduct = async (productData: {
    product_name?: string;
    product_description: string;
    product_source_type: 'text' | 'document' | 'url';
    product_source_data?: any;
    enable_comparison?: boolean;
  }) => {
    setLoading(true);
    setError(null);
    setMode('analyzing');

    try {
      const response = await axios.post('/api/competitor-intelligence/sessions', {
        product_id: selectedProductId,
        ...productData,
      });

      setSessionId(response.data.session.id);
      setAnalyzedProduct(response.data.analyzed_product);
      setHasPreviousAnalysis(response.data.has_previous_analysis);
      setMode('review');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create session');
      setMode('create');
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = () => {
    if (sessionId && analyzedProduct) {
      onComplete(sessionId, analyzedProduct, hasPreviousAnalysis);
    }
  };

  if (mode === 'select') {
    return (
      <div>
        <h2 className="text-2xl font-bold mb-6">Select or Create Product</h2>
        <ProductSelector
          onSelect={handleProductSelect}
          onCreateNew={() => {
            setSelectedProductId(null);
            setMode('create');
          }}
        />
      </div>
    );
  }

  if (mode === 'analyzing') {
    return (
      <div className="text-center py-12">
        <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
        <h3 className="text-lg font-medium text-gray-900 mb-2">
          Analyzing Product...
        </h3>
        <p className="text-gray-600">
          AI is structuring your product information for competitive analysis
        </p>
      </div>
    );
  }

  if (mode === 'review') {
    return (
      <div>
        <h2 className="text-2xl font-bold mb-6">Review Product Analysis</h2>

        {hasPreviousAnalysis && (
          <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="flex items-start">
              <svg
                className="w-5 h-5 text-blue-600 mt-0.5 mr-2"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                  clipRule="evenodd"
                />
              </svg>
              <div>
                <p className="font-medium text-blue-900">Comparison Mode Enabled</p>
                <p className="text-sm text-blue-700">
                  This analysis will be compared with previous sessions to identify changes
                </p>
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-red-800">{error}</p>
          </div>
        )}

        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="mb-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              Product Name
            </h3>
            <p className="text-gray-700">{analyzedProduct.product_name}</p>
          </div>

          <div className="mb-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Category</h3>
            <span className="inline-block px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm">
              {analyzedProduct.product_category}
            </span>
          </div>

          <div className="mb-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              Core Features
            </h3>
            <ul className="list-disc list-inside space-y-1">
              {analyzedProduct.core_features.map((feature: string, idx: number) => (
                <li key={idx} className="text-gray-700">
                  {feature}
                </li>
              ))}
            </ul>
          </div>

          <div className="mb-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              Target Users
            </h3>
            <p className="text-gray-700">{analyzedProduct.target_users}</p>
          </div>

          <div className="mb-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              Value Propositions
            </h3>
            <ul className="list-disc list-inside space-y-1">
              {analyzedProduct.value_propositions.map((vp: string, idx: number) => (
                <li key={idx} className="text-gray-700">
                  {vp}
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              Competitor Search Keywords
            </h3>
            <div className="flex flex-wrap gap-2">
              {analyzedProduct.competitor_search_keywords.map((kw: string, idx: number) => (
                <span
                  key={idx}
                  className="px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm"
                >
                  {kw}
                </span>
              ))}
            </div>
          </div>
        </div>

        <div className="flex justify-between">
          <button
            onClick={() => {
              setMode('create');
              setAnalyzedProduct(null);
            }}
            className="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
          >
            Re-analyze
          </button>
          <button
            onClick={handleConfirm}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Find Competitors →
          </button>
        </div>
      </div>
    );
  }

  // mode === 'create'
  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">
        {selectedProductId ? 'Start New Analysis' : 'Create Product'}
      </h2>

      <button
        onClick={() => setMode('select')}
        className="mb-6 text-blue-600 hover:text-blue-800"
      >
        ← Back to product selection
      </button>

      <ProductInputForm
        existingProductId={selectedProductId}
        onSubmit={handleCreateProduct}
        loading={loading}
      />

      {error && (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-red-800">{error}</p>
        </div>
      )}
    </div>
  );
};

export default Stage1_ProductDefinition;
```

### 3. Product Selector Component

Location: `src/pages/CompetitorIntelligence/components/ProductSelector.tsx`

```typescript
import React, { useEffect, useState } from 'react';
import axios from 'axios';

interface Product {
  id: string;
  product_name: string;
  product_description: string;
  analysis_count: number;
  last_analyzed_at: string | null;
}

interface ProductSelectorProps {
  onSelect: (productId: string) => void;
  onCreateNew: () => void;
}

const ProductSelector: React.FC<ProductSelectorProps> = ({
  onSelect,
  onCreateNew,
}) => {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchProducts();
  }, []);

  const fetchProducts = async () => {
    try {
      const response = await axios.get('/api/competitor-intelligence/products');
      setProducts(response.data);
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to load products');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="text-center py-8">Loading products...</div>;
  }

  return (
    <div>
      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-red-800">{error}</p>
        </div>
      )}

      <div className="mb-6">
        <button
          onClick={onCreateNew}
          className="w-full p-4 border-2 border-dashed border-gray-300 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition-colors"
        >
          <div className="text-center">
            <svg
              className="mx-auto h-12 w-12 text-gray-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 4v16m8-8H4"
              />
            </svg>
            <p className="mt-2 text-sm font-medium text-gray-900">
              Create New Product
            </p>
          </div>
        </button>
      </div>

      {products.length > 0 && (
        <div>
          <h3 className="text-lg font-medium text-gray-900 mb-4">
            Or select an existing product:
          </h3>
          <div className="space-y-3">
            {products.map((product) => (
              <button
                key={product.id}
                onClick={() => onSelect(product.id)}
                className="w-full text-left p-4 border border-gray-200 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition-colors"
              >
                <h4 className="font-medium text-gray-900 mb-1">
                  {product.product_name}
                </h4>
                <p className="text-sm text-gray-600 mb-2 line-clamp-2">
                  {product.product_description}
                </p>
                <div className="flex items-center text-xs text-gray-500">
                  <span>{product.analysis_count} analyses</span>
                  {product.last_analyzed_at && (
                    <>
                      <span className="mx-2">•</span>
                      <span>
                        Last: {new Date(product.last_analyzed_at).toLocaleDateString()}
                      </span>
                    </>
                  )}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default ProductSelector;
```

### 4. Product Input Form Component

Location: `src/pages/CompetitorIntelligence/components/ProductInputForm.tsx`

```typescript
import React, { useState } from 'react';

interface ProductInputFormProps {
  existingProductId: string | null;
  onSubmit: (data: {
    product_name?: string;
    product_description: string;
    product_source_type: 'text' | 'document' | 'url';
    product_source_data?: any;
    enable_comparison?: boolean;
  }) => void;
  loading: boolean;
}

type InputMode = 'text' | 'document' | 'url';

const ProductInputForm: React.FC<ProductInputFormProps> = ({
  existingProductId,
  onSubmit,
  loading,
}) => {
  const [inputMode, setInputMode] = useState<InputMode>('text');
  const [productName, setProductName] = useState('');
  const [productDescription, setProductDescription] = useState('');
  const [productUrl, setProductUrl] = useState('');
  const [enableComparison, setEnableComparison] = useState(true);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const data: any = {
      product_source_type: inputMode,
      enable_comparison: enableComparison,
    };

    if (!existingProductId) {
      data.product_name = productName;
    }

    if (inputMode === 'text') {
      data.product_description = productDescription;
    } else if (inputMode === 'url') {
      data.product_description = `Product URL: ${productUrl}`;
      data.product_source_data = { url: productUrl };
    }
    // File upload would be handled similarly

    onSubmit(data);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {!existingProductId && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Product Name
          </label>
          <input
            type="text"
            value={productName}
            onChange={(e) => setProductName(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            placeholder="e.g., Our CRM Platform"
            required
          />
        </div>
      )}

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          How would you like to describe your product?
        </label>
        <div className="flex space-x-4 mb-4">
          <button
            type="button"
            onClick={() => setInputMode('text')}
            className={`px-4 py-2 rounded-lg ${
              inputMode === 'text'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700'
            }`}
          >
            Text
          </button>
          <button
            type="button"
            onClick={() => setInputMode('url')}
            className={`px-4 py-2 rounded-lg ${
              inputMode === 'url'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700'
            }`}
          >
            URL
          </button>
          <button
            type="button"
            onClick={() => setInputMode('document')}
            className={`px-4 py-2 rounded-lg ${
              inputMode === 'document'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700'
            }`}
            disabled
          >
            Upload Document (Coming Soon)
          </button>
        </div>

        {inputMode === 'text' && (
          <textarea
            value={productDescription}
            onChange={(e) => setProductDescription(e.target.value)}
            rows={8}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            placeholder="Describe your product... Include key features, target users, and what makes it unique."
            required
          />
        )}

        {inputMode === 'url' && (
          <input
            type="url"
            value={productUrl}
            onChange={(e) => setProductUrl(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            placeholder="https://yourproduct.com"
            required
          />
        )}
      </div>

      {existingProductId && (
        <div className="flex items-start">
          <input
            type="checkbox"
            id="enable_comparison"
            checked={enableComparison}
            onChange={(e) => setEnableComparison(e.target.checked)}
            className="mt-1 mr-2"
          />
          <label htmlFor="enable_comparison" className="text-sm text-gray-700">
            <span className="font-medium">Enable comparison mode</span>
            <br />
            Compare with previous analyses to identify changes in the competitive landscape
          </label>
        </div>
      )}

      <button
        type="submit"
        disabled={loading}
        className="w-full px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
      >
        {loading ? 'Analyzing...' : 'Analyze Product'}
      </button>
    </form>
  );
};

export default ProductInputForm;
```

### 5. Add Route

Location: `src/App.tsx`

```typescript
import AnalysisWizard from './pages/CompetitorIntelligence/AnalysisWizard';

// Add to routes:
<Route path="/competitor-intelligence/wizard" element={<AnalysisWizard />} />
```

### 6. Update Product List "New Analysis" Button

Location: `src/pages/CompetitorIntelligence/ProductList.tsx`

```typescript
// Change the button onClick:
const handleNewAnalysis = () => {
  navigate('/competitor-intelligence/wizard');
};
```

## Testing Requirements

### Backend Unit Tests

Location: `tests/test_product_analyzer.py`

```python
import pytest
from app.agents.product_analyzer import ProductAnalyzerAgent
from app.services.llm_service import LLMService
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_product_analyzer_agent(db_session, mock_llm_service):
    """Test ProductAnalyzerAgent execution"""
    # Mock LLM response
    mock_llm_service.call_agent.return_value = {
        "content": '''```json
{
    "product_name": "Test CRM",
    "product_category": "CRM Software",
    "core_features": ["Contact Management", "Sales Pipeline", "Reporting"],
    "target_users": "Small businesses",
    "value_propositions": ["Easy to use", "Affordable"],
    "competitor_search_keywords": ["crm software", "contact management", "sales tools"]
}
```''',
        "tokens_used": 200
    }
    
    agent = ProductAnalyzerAgent(db=db_session, llm_service=mock_llm_service)
    
    result = await agent.execute({
        'product_name': 'Test CRM',
        'product_description': 'A CRM for small businesses',
        'source_type': 'text'
    })
    
    assert result['product_name'] == 'Test CRM'
    assert result['product_category'] == 'CRM Software'
    assert len(result['core_features']) >= 3
    assert len(result['competitor_search_keywords']) >= 3
```

Location: `tests/test_session_service.py`

```python
import pytest
from app.services.session_service import SessionService
from app.schemas.competitor_intelligence import SessionCreate

@pytest.mark.asyncio
async def test_create_session_new_product(db_session, test_user, mock_llm_service):
    """Test creating session with new product"""
    service = SessionService(db_session)
    
    # Mock agent response
    mock_llm_service.call_agent.return_value = {
        "content": '{"product_name": "Test", "product_category": "Software", "core_features": ["a","b","c"], "target_users": "users", "value_propositions": ["vp1"], "competitor_search_keywords": ["k1","k2","k3"]}',
        "tokens_used": 100
    }
    
    session_data = SessionCreate(
        product_name="Test Product",
        product_description="A test product",
        product_source_type="text"
    )
    
    session, analyzed = await service.create_session(
        user_id=test_user.id,
        session_data=session_data,
        llm_service=mock_llm_service
    )
    
    assert session.session_number == 1
    assert session.analysis_type == "full"
    assert analyzed['product_name'] == "Test"

@pytest.mark.asyncio
async def test_create_session_existing_product(
    db_session, test_user, test_product, mock_llm_service
):
    """Test creating session for existing product"""
    service = SessionService(db_session)
    
    session_data = SessionCreate(
        product_id=test_product.id,
        product_description="Updated description",
        product_source_type="text"
    )
    
    session, analyzed = await service.create_session(
        user_id=test_user.id,
        session_data=session_data,
        llm_service=mock_llm_service
    )
    
    assert session.product_id == test_product.id
    assert session.session_number > 0
```

### Frontend Manual Testing

1. **Navigate to product list**
2. **Click "New Product Analysis"**
   - Should open wizard at Stage 1
   - Should show product selector

3. **Test "Create New Product" flow**
   - Click "Create New Product"
   - Enter product name and description
   - Click "Analyze Product"
   - Should show analyzing state
   - Should display AI analysis results
   - Click "Find Competitors" to proceed

4. **Test "Select Existing Product" flow**
   - Select existing product from list
   - Should skip to product input form
   - Comparison toggle should be enabled
   - Complete analysis

5. **Test error handling**
   - Try duplicate product name
   - Try empty description
   - Verify error messages display

## Acceptance Criteria

**Backend:**
- [ ] ProductAnalyzerAgent executes successfully
- [ ] Agent structures product information correctly
- [ ] SessionService creates sessions
- [ ] Sessions link to products correctly
- [ ] Session numbering increments properly
- [ ] Comparison mode enabled for subsequent sessions
- [ ] API endpoints work (create session, get session)
- [ ] All unit tests pass

**Frontend:**
- [ ] Wizard launches from product list
- [ ] Progress stepper displays correctly
- [ ] Can select existing product
- [ ] Can create new product
- [ ] Product input form works (text/URL modes)
- [ ] AI analysis displays correctly
- [ ] Can review and confirm analysis
- [ ] Comparison mode indicator shows when appropriate
- [ ] Loading and error states work
- [ ] Can navigate back to product selection

**Integration:**
- [ ] End-to-end flow works (select/create → analyze → review)
- [ ] Product created in database
- [ ] Session created and linked
- [ ] Agent execution logged
- [ ] Stage 2 placeholder shows (Modules 5-8 coming)

## Files to Create/Modify

**New Backend Files:**
- `app/agents/product_analyzer.py`
- `app/services/session_service.py`
- `app/routers/sessions.py`
- `tests/test_product_analyzer.py`
- `tests/test_session_service.py`

**New Frontend Files:**
- `src/pages/CompetitorIntelligence/AnalysisWizard.tsx`
- `src/pages/CompetitorIntelligence/stages/Stage1_ProductDefinition.tsx`
- `src/pages/CompetitorIntelligence/components/ProductSelector.tsx`
- `src/pages/CompetitorIntelligence/components/ProductInputForm.tsx`

**Modified Files:**
- `app/main.py` (register sessions router)
- `app/schemas/competitor_intelligence.py` (add SessionCreate schema)
- `src/App.tsx` (add wizard route)
- `src/pages/CompetitorIntelligence/ProductList.tsx` (update button)

## Estimated Time
**2-3 days** including testing

## Next Module
After completing this module, proceed to **Module 5: Competitor Discovery with Differential Analysis**

---

**Note:** After this module, users can create products and start analyses, but the wizard only has Stage 1 complete. Stages 2-5 will be added in subsequent modules.
