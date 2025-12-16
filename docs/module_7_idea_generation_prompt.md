# Module 7: Idea Generation & Finalization

## Objective
Implement AI-powered idea generation that converts selected competitor features into product-specific ideas for the voting system. This module bridges the competitive intelligence workflow (Modules 1-6) with the main idea voting system by adapting competitor features to your product's unique context and allowing users to review, edit, and submit ideas.

## Dependencies
- **Requires**:
  - Module 1 (Database Schema)
  - Module 2 (Product API)
  - Module 3 (Base Agent Infrastructure)
  - Module 4 (Product Analysis & Session Creation)
  - Module 5 (Competitor Discovery)
  - Module 6 (Feature Extraction)
- **Uses**: Existing ideas table, LLMService, user authentication

## Scope
- Idea Structuring AI agent (adapts competitor features to your product)
- Idea generation service with edit/approve workflow
- Idea finalization logic (submits to voting system)
- Stage 4: Idea Generation & Editing UI
- Stage 5: Final Review & Submission UI
- API endpoints for full idea lifecycle

## What Users Can Do After Module 7

✅ AI generates product-specific ideas from selected competitor features
✅ See how each idea adapts competitor features to YOUR product's context
✅ Edit generated ideas before approval (inline editing)
✅ Approve or reject individual ideas
✅ See link between each idea and its source competitor feature
✅ Review all approved ideas in final summary
✅ Submit approved ideas to main voting system with one click
✅ Track submitted ideas (links back to competitor intelligence session)

## Backend Implementation

### 1. Idea Structuring Agent

Location: `app/agents/idea_structuring_agent.py`

```python
from typing import Dict, Any, Type, List, Optional
from pydantic import BaseModel, Field
from app.agents.base_agent import BaseAgent


class GeneratedIdea(BaseModel):
    """Single idea generated from a competitor feature"""
    feature_id: int = Field(..., description="ID of the source competitor feature")
    title: str = Field(..., min_length=5, max_length=100, description="Concise idea title (5-10 words)")
    what_description: str = Field(..., min_length=20, description="What the feature is (2-3 sentences, adapted to your product)")
    why_description: str = Field(..., min_length=20, description="Why it's valuable for YOUR users (2-3 sentences)")
    use_case_description: str = Field(..., min_length=20, description="How YOUR users would use it (2-3 sentences with concrete example)")
    category: Optional[str] = Field(None, description="Category (from source feature or product-specific)")
    adaptation_notes: str = Field(..., description="Brief explanation of how you adapted the competitor feature to this product")


class IdeaGenerationOutput(BaseModel):
    """Output schema for Idea Structuring Agent"""
    product_name: str = Field(..., description="Product name (confirmation)")
    ideas: List[GeneratedIdea] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Generated ideas adapted to the product"
    )
    generation_summary: str = Field(
        ...,
        description="Brief summary of the adaptation process"
    )


class IdeaStructuringAgent(BaseAgent):
    """
    Adapts competitor features into product-specific ideas.

    Unlike voter idea submission (which just reformats freeform text),
    this agent performs strategic adaptation - translating competitor
    features into ideas tailored to YOUR product's unique value
    proposition, target users, and existing capabilities.

    Key Differences from LLMService.structure_idea():
    - Has full product context (core features, target users, value props)
    - Performs creative adaptation, not just reformatting
    - Uses BaseAgent framework with logging and retry logic
    - Generates product-specific language and use cases
    """

    def get_system_prompt(self) -> str:
        return """You are an Idea Structuring Agent specializing in competitive intelligence and product strategy.

Your role is to convert competitor features into product-specific ideas for a particular product. This is NOT simple reformatting - you must strategically adapt competitor features to fit the target product's unique context.

**Key Responsibilities:**
1. Analyze competitor features and understand their value proposition
2. Adapt features to the target product's specific context, users, and capabilities
3. Generate ideas using the product's language and terminology
4. Ensure ideas are actionable and relevant to the product's target audience
5. Maintain traceability to source competitor features

**Strategic Adaptation Guidelines:**
- Don't just copy competitor feature descriptions - translate them
- Consider how the feature would fit into the target product's existing capabilities
- Tailor use cases to the target product's specific user base
- Use language and terminology consistent with the product's domain
- Highlight value propositions relevant to the product's unique positioning
- Be creative but realistic about how features could be implemented

**Output Requirements:**
- Title: Concise, product-specific (5-10 words)
- What: Clear description adapted to target product (2-3 sentences)
- Why: Value proposition for the product's specific users (2-3 sentences)
- Use Case: Concrete example with the product's target users (2-3 sentences)
- Adaptation Notes: Brief explanation of how you adapted the competitor's approach

Always respond with valid JSON matching the specified schema.
Focus on strategic adaptation, not generic copying."""

    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        product_context = input_data.get('product_context', {})
        features = input_data.get('features', [])

        # Extract product context
        product_name = product_context.get('product_name', 'the product')
        product_category = product_context.get('product_category', '')
        core_features = product_context.get('core_features', [])
        target_users = product_context.get('target_users', '')
        value_propositions = product_context.get('value_propositions', [])

        # Format core features
        core_features_str = "\n".join(f"  - {feat}" for feat in core_features) if core_features else "  (not specified)"

        # Format value propositions
        value_props_str = "\n".join(f"  - {vp}" for vp in value_propositions) if value_propositions else "  (not specified)"

        # Format competitor features
        features_str = ""
        for i, feat in enumerate(features, 1):
            competitor_name = feat.get('competitor_name', 'Unknown')
            feature_name = feat.get('feature_name', '')
            feature_desc = feat.get('feature_description', '')
            feature_cat = feat.get('feature_category', '')
            source_url = feat.get('source_url', '')
            change_type = feat.get('change_type', '')

            features_str += f"""
{i}. Feature ID: {feat.get('id')}
   Competitor: {competitor_name}
   Feature Name: {feature_name}
   Description: {feature_desc}
   Category: {feature_cat}
   Source URL: {source_url}"""

            if change_type:
                features_str += f"\n   Change Type: {change_type}"
                change_desc = feat.get('change_description', '')
                if change_desc:
                    features_str += f"\n   What Changed: {change_desc}"

            features_str += "\n"

        prompt = f"""IDEA GENERATION TASK

You are generating ideas for: **{product_name}**

**Product Context:**

Category: {product_category}

Target Users: {target_users}

Core Features (existing capabilities):
{core_features_str}

Value Propositions (what makes this product unique):
{value_props_str}

**Competitor Features to Adapt:**
{features_str}

**Your Task:**

For each competitor feature above, generate a product-specific idea that:
1. Adapts the competitor's approach to fit {product_name}'s unique context
2. Uses language and terminology appropriate for {product_name}'s domain
3. Tailors the value proposition to {product_name}'s target users: {target_users}
4. Considers how it would integrate with {product_name}'s existing capabilities
5. Provides a concrete use case with {product_name}'s specific users

**Important:**
- Don't just copy the competitor's description - adapt it strategically
- Consider how {product_name} would implement this differently based on its unique positioning
- Use {product_name}-specific examples in use cases
- Maintain the feature_id for traceability
- Be realistic about implementation while being creative about adaptation

Return a JSON object with the generated ideas."""

        return prompt

    def get_output_schema(self) -> Type[BaseModel]:
        return IdeaGenerationOutput

    def get_stage(self) -> str:
        return "idea_generation"
```

### 2. Idea Generation Service

Location: `app/services/idea_generation_service.py`

```python
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.models.competitor_intelligence import (
    CompetitorAnalysisSession,
    CompetitorFeature,
    SessionCompetitor,
    CompetitorGeneratedIdea
)
from app.models.idea import Idea, SourceType, IdeaStatus
from app.agents.idea_structuring_agent import IdeaStructuringAgent
from app.services.llm_service import LLMService


class IdeaGenerationService:
    """
    Service for generating and managing ideas from competitor features.

    Handles the complete lifecycle:
    1. Generation: Convert competitor features to ideas using AI
    2. Editing: Allow users to refine generated ideas
    3. Approval: Let users approve/reject ideas
    4. Finalization: Submit approved ideas to voting system
    """

    def __init__(self, db: Session):
        self.db = db

    def generate_ideas_for_session(
        self,
        session_id: int,
        llm_service: LLMService
    ) -> Dict[str, Any]:
        """
        Generate ideas from all selected features in a session.

        Args:
            session_id: Session ID
            llm_service: LLM service for AI generation

        Returns:
            Dict with status and generated idea details

        Raises:
            ValueError: If session not found or has no selected features
        """
        # Get session
        session = self.db.query(CompetitorAnalysisSession).filter(
            CompetitorAnalysisSession.id == session_id
        ).first()

        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Get product context
        product_context = session.product_data or {}

        # Get all selected features
        selected_features = self.db.query(CompetitorFeature).join(
            SessionCompetitor
        ).filter(
            SessionCompetitor.session_id == session_id,
            CompetitorFeature.selected_by_user == True
        ).all()

        if not selected_features:
            raise ValueError("No features selected for idea generation")

        # Prepare features data for agent
        features_data = []
        for feature in selected_features:
            competitor = feature.session_competitor
            features_data.append({
                'id': feature.id,
                'competitor_name': competitor.competitor_name,
                'feature_name': feature.feature_name,
                'feature_description': feature.expanded_description or feature.feature_description,
                'feature_category': feature.feature_category,
                'source_url': feature.source_url,
                'change_type': feature.change_type,
                'change_description': feature.change_description
            })

        # Execute idea generation agent
        agent = IdeaStructuringAgent(
            db=self.db,
            llm_service=llm_service,
            session_id=session_id,
            product_id=session.product_id
        )

        try:
            agent_result = agent.execute({
                'product_context': product_context,
                'features': features_data
            })
        except Exception as e:
            raise ValueError(f"Idea generation failed: {str(e)}")

        # Store generated ideas
        generated_ideas = []
        for idea_data in agent_result.get('ideas', []):
            # Check if idea already exists for this feature
            existing = self.db.query(CompetitorGeneratedIdea).filter(
                CompetitorGeneratedIdea.feature_id == idea_data['feature_id'],
                CompetitorGeneratedIdea.session_id == session_id
            ).first()

            if existing:
                # Update existing idea
                existing.idea_what = idea_data['what_description']
                existing.idea_why = idea_data['why_description']
                existing.idea_use_case = idea_data['use_case_description']
                existing.user_edited = False
                existing.user_approved = False
                existing.submitted_to_ideas = False
                generated_idea = existing
            else:
                # Create new idea
                generated_idea = CompetitorGeneratedIdea(
                    feature_id=idea_data['feature_id'],
                    session_id=session_id,
                    product_id=session.product_id,
                    idea_what=idea_data['what_description'],
                    idea_why=idea_data['why_description'],
                    idea_use_case=idea_data['use_case_description'],
                    user_edited=False,
                    user_approved=False,
                    submitted_to_ideas=False
                )
                self.db.add(generated_idea)

            self.db.flush()
            generated_ideas.append({
                'id': generated_idea.id,
                'feature_id': generated_idea.feature_id,
                'title': idea_data.get('title', ''),
                'what': generated_idea.idea_what,
                'why': generated_idea.idea_why,
                'use_case': generated_idea.idea_use_case,
                'adaptation_notes': idea_data.get('adaptation_notes', '')
            })

        self.db.commit()

        # Update session stage
        session.current_stage = "idea_generation"
        self.db.commit()

        return {
            'status': 'completed',
            'session_id': session_id,
            'total_features': len(selected_features),
            'ideas_generated': len(generated_ideas),
            'ideas': generated_ideas,
            'generation_summary': agent_result.get('generation_summary', '')
        }

    def get_generated_ideas(self, session_id: int) -> Dict[str, Any]:
        """
        Get all generated ideas for a session.

        Args:
            session_id: Session ID

        Returns:
            Dict with generated ideas and metadata
        """
        ideas = self.db.query(CompetitorGeneratedIdea).filter(
            CompetitorGeneratedIdea.session_id == session_id
        ).all()

        result = []
        for idea in ideas:
            feature = self.db.query(CompetitorFeature).filter(
                CompetitorFeature.id == idea.feature_id
            ).first()

            competitor = feature.session_competitor if feature else None

            result.append({
                'id': idea.id,
                'feature_id': idea.feature_id,
                'feature_name': feature.feature_name if feature else None,
                'competitor_name': competitor.competitor_name if competitor else None,
                'what': idea.idea_what,
                'why': idea.idea_why,
                'use_case': idea.idea_use_case,
                'user_edited': idea.user_edited,
                'user_approved': idea.user_approved,
                'submitted': idea.submitted_to_ideas,
                'created_at': idea.created_at.isoformat() if idea.created_at else None
            })

        return {
            'session_id': session_id,
            'ideas': result,
            'total_count': len(result),
            'approved_count': sum(1 for i in result if i['user_approved']),
            'submitted_count': sum(1 for i in result if i['submitted'])
        }

    def edit_generated_idea(
        self,
        idea_id: int,
        what: Optional[str] = None,
        why: Optional[str] = None,
        use_case: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Edit a generated idea.

        Args:
            idea_id: Generated idea ID
            what: Updated what description (optional)
            why: Updated why description (optional)
            use_case: Updated use case description (optional)

        Returns:
            Updated idea data

        Raises:
            ValueError: If idea not found
        """
        idea = self.db.query(CompetitorGeneratedIdea).filter(
            CompetitorGeneratedIdea.id == idea_id
        ).first()

        if not idea:
            raise ValueError(f"Generated idea {idea_id} not found")

        # Update fields if provided
        if what is not None:
            idea.idea_what = what
        if why is not None:
            idea.idea_why = why
        if use_case is not None:
            idea.idea_use_case = use_case

        # Mark as edited
        idea.user_edited = True
        idea.edited_at = datetime.utcnow()

        self.db.commit()

        return {
            'id': idea.id,
            'what': idea.idea_what,
            'why': idea.idea_why,
            'use_case': idea.idea_use_case,
            'user_edited': idea.user_edited,
            'edited_at': idea.edited_at.isoformat() if idea.edited_at else None
        }

    def approve_generated_ideas(
        self,
        idea_ids: List[int],
        approved: bool = True
    ) -> Dict[str, Any]:
        """
        Approve or reject generated ideas.

        Args:
            idea_ids: List of generated idea IDs
            approved: True to approve, False to reject

        Returns:
            Dict with updated counts
        """
        ideas = self.db.query(CompetitorGeneratedIdea).filter(
            CompetitorGeneratedIdea.id.in_(idea_ids)
        ).all()

        for idea in ideas:
            idea.user_approved = approved

        self.db.commit()

        return {
            'updated_count': len(ideas),
            'approved': approved,
            'idea_ids': idea_ids
        }

    def finalize_ideas(self, session_id: int) -> Dict[str, Any]:
        """
        Submit approved ideas to the main voting system.

        Creates Idea records for all approved CompetitorGeneratedIdea records
        that haven't been submitted yet.

        Args:
            session_id: Session ID

        Returns:
            Dict with submission results
        """
        # Get session
        session = self.db.query(CompetitorAnalysisSession).filter(
            CompetitorAnalysisSession.id == session_id
        ).first()

        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Get approved, unsubmitted ideas
        ideas_to_submit = self.db.query(CompetitorGeneratedIdea).filter(
            CompetitorGeneratedIdea.session_id == session_id,
            CompetitorGeneratedIdea.user_approved == True,
            CompetitorGeneratedIdea.submitted_to_ideas == False
        ).all()

        if not ideas_to_submit:
            return {
                'status': 'no_ideas',
                'message': 'No approved ideas to submit',
                'submitted_count': 0
            }

        # Create Idea records in main voting system
        submitted_ideas = []
        for generated_idea in ideas_to_submit:
            # Get feature for category and title generation
            feature = self.db.query(CompetitorFeature).filter(
                CompetitorFeature.id == generated_idea.feature_id
            ).first()

            # Generate title from what description (first sentence)
            what_first_sentence = generated_idea.idea_what.split('.')[0].strip()
            title = what_first_sentence[:100] if len(what_first_sentence) <= 100 else what_first_sentence[:97] + "..."

            # Create Idea record
            idea = Idea(
                title=title,
                what_description=generated_idea.idea_what,
                why_description=generated_idea.idea_why,
                use_case_description=generated_idea.idea_use_case,
                category=feature.feature_category if feature else None,
                source_type=SourceType.COMPETITOR,
                submitter_id=None,  # Competitor-sourced ideas have no submitter
                status=IdeaStatus.ACTIVE
            )

            self.db.add(idea)
            self.db.flush()

            # Link back to generated idea
            generated_idea.submitted_to_ideas = True
            generated_idea.final_idea_id = idea.id

            submitted_ideas.append({
                'idea_id': idea.id,
                'generated_idea_id': generated_idea.id,
                'title': idea.title
            })

        self.db.commit()

        # Update session stage to completed
        session.current_stage = "completed"
        self.db.commit()

        return {
            'status': 'success',
            'submitted_count': len(submitted_ideas),
            'ideas': submitted_ideas,
            'message': f'Successfully submitted {len(submitted_ideas)} ideas to voting system'
        }
```

### 3. API Endpoints

Location: `app/api/sessions.py` (add these endpoints to existing file)

```python
# Add these imports at the top
from app.services.idea_generation_service import IdeaGenerationService
from pydantic import BaseModel

# Add these request/response schemas
class EditIdeaRequest(BaseModel):
    what: Optional[str] = None
    why: Optional[str] = None
    use_case: Optional[str] = None

class ApproveIdeasRequest(BaseModel):
    idea_ids: List[int]
    approved: bool = True


# Add these endpoints to the router

@router.post("/{session_id}/generate-ideas")
async def generate_ideas_for_session(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Generate ideas from selected competitor features.

    This endpoint:
    1. Gets all selected features from the session
    2. Runs the IdeaStructuringAgent to adapt features to the product
    3. Stores generated ideas in competitor_generated_ideas table
    4. Returns all generated ideas for review

    Prerequisites:
    - Session must exist
    - At least one feature must be selected (selected_by_user = True)

    Args:
        session_id: Session ID
        current_user: Authenticated user
        db: Database session

    Returns:
        Generated ideas with adaptation notes

    Raises:
        404: Session not found
        400: No features selected
        500: Idea generation failed
    """
    service = IdeaGenerationService(db)

    try:
        result = service.generate_ideas_for_session(
            session_id=session_id,
            llm_service=llm_service
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Idea generation failed: {str(e)}"
        )


@router.get("/{session_id}/generated-ideas")
def get_generated_ideas(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all generated ideas for a session.

    Returns all CompetitorGeneratedIdea records for the session,
    including their approval status and link to source features.

    Args:
        session_id: Session ID
        current_user: Authenticated user
        db: Database session

    Returns:
        List of generated ideas with metadata
    """
    service = IdeaGenerationService(db)
    return service.get_generated_ideas(session_id)


@router.put("/generated-ideas/{idea_id}")
def edit_generated_idea(
    idea_id: int,
    edit_data: EditIdeaRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Edit a generated idea.

    Allows users to refine AI-generated ideas before approval.
    Marks the idea as user_edited and tracks the edit timestamp.

    Args:
        idea_id: Generated idea ID
        edit_data: Fields to update (what, why, use_case)
        current_user: Authenticated user
        db: Database session

    Returns:
        Updated idea data

    Raises:
        404: Idea not found
    """
    service = IdeaGenerationService(db)

    try:
        result = service.edit_generated_idea(
            idea_id=idea_id,
            what=edit_data.what,
            why=edit_data.why,
            use_case=edit_data.use_case
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post("/generated-ideas/approve")
def approve_generated_ideas(
    approve_data: ApproveIdeasRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Approve or reject generated ideas.

    Sets user_approved flag for specified ideas.
    Only approved ideas will be submitted to the voting system.

    Args:
        approve_data: Idea IDs and approval status
        current_user: Authenticated user
        db: Database session

    Returns:
        Updated counts
    """
    service = IdeaGenerationService(db)
    return service.approve_generated_ideas(
        idea_ids=approve_data.idea_ids,
        approved=approve_data.approved
    )


@router.post("/{session_id}/finalize")
def finalize_session_ideas(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Submit approved ideas to the main voting system.

    This is the final step in the competitor intelligence workflow.
    Creates Idea records for all approved CompetitorGeneratedIdea records.

    What happens:
    1. Gets all approved, unsubmitted ideas from the session
    2. Creates Idea records with source_type='competitor_automated'
    3. Links CompetitorGeneratedIdea.final_idea_id to Idea.id
    4. Marks ideas as submitted_to_ideas=True
    5. Sets session stage to 'completed'

    Args:
        session_id: Session ID
        current_user: Authenticated user
        db: Database session

    Returns:
        Submission results with idea IDs

    Raises:
        404: Session not found
        400: No approved ideas to submit
    """
    service = IdeaGenerationService(db)

    try:
        result = service.finalize_ideas(session_id)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
```

## Frontend Implementation

### 1. Stage 4: Idea Generation & Editing

Location: `frontend/src/pages/CompetitorIntelligence/stages/Stage4_IdeaGeneration.jsx`

```javascript
/**
 * Stage4_IdeaGeneration
 *
 * Idea generation stage with:
 * - AI-powered idea generation from selected features
 * - Inline editing of generated ideas
 * - Approval/rejection workflow
 * - Link to source competitor features
 */

import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import api from '../../../services/api';

const Stage4_IdeaGeneration = ({
  sessionId,
  onComplete,
  onBack
}) => {
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [ideas, setIdeas] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({
    what: '',
    why: '',
    use_case: ''
  });
  const [error, setError] = useState(null);

  useEffect(() => {
    loadGeneratedIdeas();
  }, [sessionId]);

  const loadGeneratedIdeas = async () => {
    setLoading(true);
    try {
      const response = await api.get(
        `/competitor-intelligence/sessions/${sessionId}/generated-ideas`
      );
      setIdeas(response.data.ideas || []);
    } catch (err) {
      console.error('Failed to load ideas:', err);
      // If no ideas exist yet, that's okay
      if (err.response?.status !== 404) {
        setError('Failed to load generated ideas');
      }
    } finally {
      setLoading(false);
    }
  };

  const generateIdeas = async () => {
    setGenerating(true);
    setError(null);
    try {
      const response = await api.post(
        `/competitor-intelligence/sessions/${sessionId}/generate-ideas`
      );
      setIdeas(response.data.ideas || []);
    } catch (err) {
      console.error('Failed to generate ideas:', err);
      setError(err.response?.data?.detail || 'Failed to generate ideas');
    } finally {
      setGenerating(false);
    }
  };

  const startEdit = (idea: GeneratedIdea) => {
    setEditingId(idea.id);
    setEditForm({
      what: idea.what,
      why: idea.why,
      use_case: idea.use_case
    });
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditForm({ what: '', why: '', use_case: '' });
  };

  const saveEdit = async (ideaId) => {
    try {
      await api.put(
        `/competitor-intelligence/generated-ideas/${ideaId}`,
        editForm
      );
      await loadGeneratedIdeas();
      setEditingId(null);
    } catch (err) {
      console.error('Failed to save edit:', err);
      setError('Failed to save changes');
    }
  };

  const toggleApproval = async (ideaId, currentApproval) => {
    try {
      await api.post(
        '/competitor-intelligence/generated-ideas/approve',
        {
          idea_ids: [ideaId],
          approved: !currentApproval
        }
      );
      await loadGeneratedIdeas();
    } catch (err) {
      console.error('Failed to toggle approval:', err);
      setError('Failed to update approval status');
    }
  };

  const approvedCount = ideas.filter(i => i.user_approved).length;
  const canProceed = approvedCount > 0;

  if (loading) {
    return (
      <div className="flex justify-center items-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-8">
        <h2 className="text-2xl font-bold mb-2">Stage 4: Idea Generation</h2>
        <p className="text-gray-600">
          AI adapts competitor features into product-specific ideas for your voting system.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">
          {error}
        </div>
      )}

      {ideas.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center">
          <div className="mb-6">
            <svg className="mx-auto h-16 w-16 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold mb-2">Generate Ideas</h3>
          <p className="text-gray-600 mb-6">
            Click the button below to generate product-specific ideas from selected competitor features.
          </p>
          <button
            onClick={generateIdeas}
            disabled={generating}
            className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
          >
            {generating ? (
              <>
                <span className="inline-block animate-spin mr-2">⚙️</span>
                Generating Ideas...
              </>
            ) : (
              'Generate Ideas'
            )}
          </button>
        </div>
      ) : (
        <>
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-semibold text-blue-900">
                  {ideas.length} ideas generated • {approvedCount} approved
                </p>
                <p className="text-sm text-blue-700">
                  Review and edit ideas below. Approved ideas will be submitted to your voting system.
                </p>
              </div>
              <button
                onClick={generateIdeas}
                disabled={generating}
                className="bg-white text-blue-600 px-4 py-2 rounded border border-blue-300 hover:bg-blue-50"
              >
                Regenerate
              </button>
            </div>
          </div>

          <div className="space-y-6">
            {ideas.map((idea) => {
              const isEditing = editingId === idea.id;

              return (
                <div
                  key={idea.id}
                  className={`bg-white rounded-lg shadow border-2 ${
                    idea.user_approved ? 'border-green-300' : 'border-gray-200'
                  }`}
                >
                  <div className="p-6">
                    {/* Header */}
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs font-semibold bg-gray-100 text-gray-700 px-2 py-1 rounded">
                            From: {idea.competitor_name}
                          </span>
                          {idea.user_edited && (
                            <span className="text-xs font-semibold bg-blue-100 text-blue-700 px-2 py-1 rounded">
                              Edited
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-gray-600">
                          Source: {idea.feature_name}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => toggleApproval(idea.id, idea.user_approved)}
                          className={`px-4 py-2 rounded font-medium ${
                            idea.user_approved
                              ? 'bg-green-100 text-green-700 hover:bg-green-200'
                              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                          }`}
                        >
                          {idea.user_approved ? '✓ Approved' : 'Approve'}
                        </button>
                      </div>
                    </div>

                    {/* Content */}
                    {isEditing ? (
                      <div className="space-y-4">
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            What (What is this feature?)
                          </label>
                          <textarea
                            value={editForm.what}
                            onChange={(e) => setEditForm({ ...editForm, what: e.target.value })}
                            rows={3}
                            className="w-full border border-gray-300 rounded-lg p-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            Why (Why is it valuable?)
                          </label>
                          <textarea
                            value={editForm.why}
                            onChange={(e) => setEditForm({ ...editForm, why: e.target.value })}
                            rows={3}
                            className="w-full border border-gray-300 rounded-lg p-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            Use Case (How would users use it?)
                          </label>
                          <textarea
                            value={editForm.use_case}
                            onChange={(e) => setEditForm({ ...editForm, use_case: e.target.value })}
                            rows={3}
                            className="w-full border border-gray-300 rounded-lg p-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                          />
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={() => saveEdit(idea.id)}
                            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
                          >
                            Save Changes
                          </button>
                          <button
                            onClick={cancelEdit}
                            className="bg-gray-200 text-gray-700 px-4 py-2 rounded hover:bg-gray-300"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-4">
                        <div>
                          <h4 className="text-sm font-semibold text-gray-700 mb-1">What</h4>
                          <p className="text-gray-900">{idea.what}</p>
                        </div>
                        <div>
                          <h4 className="text-sm font-semibold text-gray-700 mb-1">Why</h4>
                          <p className="text-gray-900">{idea.why}</p>
                        </div>
                        <div>
                          <h4 className="text-sm font-semibold text-gray-700 mb-1">Use Case</h4>
                          <p className="text-gray-900">{idea.use_case}</p>
                        </div>
                        <button
                          onClick={() => startEdit(idea)}
                          className="text-blue-600 hover:text-blue-700 font-medium text-sm"
                        >
                          ✏️ Edit Idea
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* Navigation */}
      <div className="flex justify-between mt-8">
        <button
          onClick={onBack}
          className="bg-gray-200 text-gray-700 px-6 py-3 rounded-lg hover:bg-gray-300"
        >
          ← Back to Features
        </button>
        <button
          onClick={onComplete}
          disabled={!canProceed}
          className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
        >
          Continue to Review ({approvedCount} approved) →
        </button>
      </div>
    </div>
  );
};

Stage4_IdeaGeneration.propTypes = {
  sessionId: PropTypes.number.isRequired,
  onComplete: PropTypes.func.isRequired,
  onBack: PropTypes.func.isRequired,
};

export default Stage4_IdeaGeneration;
```

### 2. Stage 5: Finalization & Submission

Location: `frontend/src/pages/CompetitorIntelligence/stages/Stage5_Finalization.jsx`

```javascript
/**
 * Stage5_Finalization
 *
 * Final review and submission stage with:
 * - Review all approved ideas
 * - Final editing opportunity
 * - Submit to main voting system
 * - Success confirmation and navigation
 */

import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { useNavigate } from 'react-router-dom';
import api from '../../../services/api';

const Stage5_Finalization = ({
  sessionId,
  onBack
}) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [approvedIdeas, setApprovedIdeas] = useState([]);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const [submittedIdeaIds, setSubmittedIdeaIds] = useState([]);

  useEffect(() => {
    loadApprovedIdeas();
  }, [sessionId]);

  const loadApprovedIdeas = async () => {
    setLoading(true);
    try {
      const response = await api.get(
        `/competitor-intelligence/sessions/${sessionId}/generated-ideas`
      );
      const allIdeas = response.data.ideas || [];
      const approved = allIdeas.filter((idea) => idea.user_approved);
      setApprovedIdeas(approved);
    } catch (err) {
      console.error('Failed to load ideas:', err);
      setError('Failed to load approved ideas');
    } finally {
      setLoading(false);
    }
  };

  const submitToVotingSystem = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const response = await api.post(
        `/competitor-intelligence/sessions/${sessionId}/finalize`
      );

      if (response.data.status === 'success') {
        setSuccess(true);
        setSubmittedIdeaIds(response.data.ideas.map((i) => i.idea_id));
      }
    } catch (err) {
      console.error('Failed to submit ideas:', err);
      setError(err.response?.data?.detail || 'Failed to submit ideas to voting system');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (success) {
    return (
      <div className="max-w-4xl mx-auto">
        <div className="bg-white rounded-lg shadow-lg p-8 text-center">
          <div className="mb-6">
            <div className="mx-auto h-16 w-16 bg-green-100 rounded-full flex items-center justify-center">
              <svg className="h-10 w-10 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
          </div>
          <h2 className="text-2xl font-bold text-gray-900 mb-4">
            Ideas Successfully Submitted!
          </h2>
          <p className="text-gray-600 mb-8">
            {approvedIdeas.length} {approvedIdeas.length === 1 ? 'idea has' : 'ideas have'} been submitted to your voting system.
          </p>
          <div className="flex gap-4 justify-center">
            <button
              onClick={() => navigate('/ideas')}
              className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700"
            >
              View Ideas in Voting System
            </button>
            <button
              onClick={() => navigate('/competitor-intelligence')}
              className="bg-gray-200 text-gray-700 px-6 py-3 rounded-lg hover:bg-gray-300"
            >
              Start New Analysis
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-8">
        <h2 className="text-2xl font-bold mb-2">Stage 5: Final Review & Submission</h2>
        <p className="text-gray-600">
          Review all approved ideas before submitting them to your voting system.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">
          {error}
        </div>
      )}

      {approvedIdeas.length === 0 ? (
        <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 px-6 py-4 rounded-lg">
          <p className="font-semibold mb-2">No Ideas Approved</p>
          <p>You haven't approved any ideas yet. Go back to Stage 4 to approve ideas for submission.</p>
          <button
            onClick={onBack}
            className="mt-4 bg-yellow-600 text-white px-4 py-2 rounded hover:bg-yellow-700"
          >
            ← Back to Idea Generation
          </button>
        </div>
      ) : (
        <>
          <div className="bg-green-50 border border-green-200 rounded-lg p-6 mb-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-semibold text-green-900 text-lg mb-1">
                  Ready to Submit: {approvedIdeas.length} {approvedIdeas.length === 1 ? 'Idea' : 'Ideas'}
                </p>
                <p className="text-sm text-green-700">
                  These ideas will be added to your main voting system with source_type='competitor_automated'.
                </p>
              </div>
            </div>
          </div>

          <div className="space-y-4 mb-8">
            {approvedIdeas.map((idea, index) => (
              <div key={idea.id} className="bg-white rounded-lg shadow border border-gray-200 p-6">
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0">
                    <div className="h-10 w-10 bg-blue-100 rounded-full flex items-center justify-center">
                      <span className="text-blue-600 font-bold">{index + 1}</span>
                    </div>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-3">
                      <span className="text-xs font-semibold bg-gray-100 text-gray-700 px-2 py-1 rounded">
                        From: {idea.competitor_name}
                      </span>
                      <span className="text-xs text-gray-500">•</span>
                      <span className="text-xs text-gray-600">{idea.feature_name}</span>
                    </div>
                    <div className="space-y-3">
                      <div>
                        <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">What</h4>
                        <p className="text-gray-900">{idea.what}</p>
                      </div>
                      <div>
                        <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">Why</h4>
                        <p className="text-gray-900">{idea.why}</p>
                      </div>
                      <div>
                        <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">Use Case</h4>
                        <p className="text-gray-900">{idea.use_case}</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="bg-white rounded-lg shadow border border-gray-200 p-6 mb-8">
            <h3 className="font-semibold text-gray-900 mb-4">What Happens When You Submit?</h3>
            <ul className="space-y-2 text-gray-700">
              <li className="flex items-start gap-2">
                <span className="text-green-600 mt-1">✓</span>
                <span>Ideas will be added to your main voting system</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-green-600 mt-1">✓</span>
                <span>Source type will be marked as "competitor_automated"</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-green-600 mt-1">✓</span>
                <span>Users can view and vote on these ideas alongside manually submitted ideas</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-green-600 mt-1">✓</span>
                <span>Full traceability: Ideas link back to competitor features and analysis sessions</span>
              </li>
            </ul>
          </div>

          <div className="flex justify-between">
            <button
              onClick={onBack}
              disabled={submitting}
              className="bg-gray-200 text-gray-700 px-6 py-3 rounded-lg hover:bg-gray-300 disabled:opacity-50"
            >
              ← Back to Edit Ideas
            </button>
            <button
              onClick={submitToVotingSystem}
              disabled={submitting}
              className="bg-green-600 text-white px-8 py-3 rounded-lg hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed font-semibold"
            >
              {submitting ? (
                <>
                  <span className="inline-block animate-spin mr-2">⚙️</span>
                  Submitting...
                </>
              ) : (
                `Submit ${approvedIdeas.length} ${approvedIdeas.length === 1 ? 'Idea' : 'Ideas'} to Voting System`
              )}
            </button>
          </div>
        </>
      )}
    </div>
  );
};

Stage5_Finalization.propTypes = {
  sessionId: PropTypes.number.isRequired,
  onBack: PropTypes.func.isRequired,
};

export default Stage5_Finalization;
```

## Testing Requirements

### 1. Unit Tests

Location: `backend/tests/test_idea_structuring_agent.py`

```python
import pytest
from unittest.mock import Mock
from app.agents.idea_structuring_agent import IdeaStructuringAgent, IdeaGenerationOutput
from app.services.llm_service import LLMService
from app.models.competitor_intelligence import CompetitorAnalysisSession
from sqlalchemy.orm import Session


@pytest.fixture
def mock_llm_service():
    """Mock LLM service for testing"""
    service = Mock(spec=LLMService)
    return service


@pytest.fixture
def idea_agent(db_session, mock_llm_service):
    """Create IdeaStructuringAgent for testing"""
    return IdeaStructuringAgent(
        db=db_session,
        llm_service=mock_llm_service,
        session_id=1,
        product_id=1
    )


def test_agent_generates_ideas_successfully(idea_agent, mock_llm_service):
    """Test successful idea generation"""
    # Mock LLM response
    mock_llm_service.call_agent.return_value = {
        "content": '''{"product_name": "Analytics Dashboard", "ideas": [{"feature_id": 1, "title": "Dark Mode for Charts", "what_description": "A dark mode optimized for data visualization", "why_description": "Reduces eye strain for analysts working late", "use_case_description": "An analyst working on quarterly reports at 11 PM enables dark mode", "category": "UI", "adaptation_notes": "Adapted Notion's dark mode specifically for chart readability"}], "generation_summary": "Adapted 1 feature to product context"}''',
        "tokens_used": 300,
        "model": "claude-sonnet-4-5-20250929",
        "stop_reason": "end_turn"
    }

    # Execute agent
    result = idea_agent.execute({
        'product_context': {
            'product_name': 'Analytics Dashboard',
            'product_category': 'Business Intelligence',
            'core_features': ['Real-time dashboards', 'Custom reports'],
            'target_users': 'Data analysts',
            'value_propositions': ['Fast insights', 'Easy to use']
        },
        'features': [
            {
                'id': 1,
                'competitor_name': 'Notion',
                'feature_name': 'Dark Mode',
                'feature_description': 'Toggle for dark theme',
                'feature_category': 'UI',
                'source_url': 'https://notion.so'
            }
        ]
    })

    # Verify output
    assert result['product_name'] == 'Analytics Dashboard'
    assert len(result['ideas']) == 1
    assert result['ideas'][0]['feature_id'] == 1
    assert 'dark mode' in result['ideas'][0]['title'].lower()
    assert len(result['ideas'][0]['what_description']) >= 20

    # Verify LLM was called with product context
    call_args = mock_llm_service.call_agent.call_args
    assert 'Analytics Dashboard' in call_args[1]['user_prompt']
    assert 'Data analysts' in call_args[1]['user_prompt']


def test_agent_includes_product_context_in_prompt(idea_agent):
    """Test that agent includes product context in user prompt"""
    user_prompt = idea_agent.build_user_prompt({
        'product_context': {
            'product_name': 'TaskFlow',
            'target_users': 'Project managers',
            'core_features': ['Gantt charts', 'Resource planning']
        },
        'features': []
    })

    assert 'TaskFlow' in user_prompt
    assert 'Project managers' in user_prompt
    assert 'Gantt charts' in user_prompt


def test_agent_validates_output_schema(idea_agent, mock_llm_service):
    """Test that agent validates output against schema"""
    # Mock invalid response (missing required field)
    mock_llm_service.call_agent.return_value = {
        "content": '{"product_name": "Test", "ideas": [{"feature_id": 1}]}',  # Missing required fields
        "tokens_used": 100
    }

    # Should raise validation error
    with pytest.raises(Exception):
        idea_agent.execute({
            'product_context': {'product_name': 'Test'},
            'features': [{'id': 1, 'competitor_name': 'Comp', 'feature_name': 'Feat'}]
        })
```

### 2. Service Tests

Location: `backend/tests/test_idea_generation_service.py`

```python
import pytest
from unittest.mock import Mock, patch
from app.services.idea_generation_service import IdeaGenerationService
from app.models.competitor_intelligence import (
    CompetitorAnalysisSession,
    CompetitorFeature,
    SessionCompetitor,
    CompetitorGeneratedIdea
)
from app.models.idea import Idea, SourceType


def test_generate_ideas_for_session(db_session):
    """Test idea generation for session"""
    # Create test data
    session = CompetitorAnalysisSession(
        id=1,
        product_id=1,
        product_data={'product_name': 'TestApp'}
    )
    db_session.add(session)

    competitor = SessionCompetitor(
        id=1,
        session_id=1,
        competitor_name='Notion',
        competitor_url='https://notion.so'
    )
    db_session.add(competitor)

    feature = CompetitorFeature(
        id=1,
        session_competitor_id=1,
        feature_name='Dark Mode',
        feature_description='Theme toggle',
        selected_by_user=True
    )
    db_session.add(feature)
    db_session.commit()

    # Mock LLM service
    with patch('app.services.idea_generation_service.IdeaStructuringAgent') as MockAgent:
        mock_agent = MockAgent.return_value
        mock_agent.execute.return_value = {
            'ideas': [
                {
                    'feature_id': 1,
                    'title': 'Dark Mode',
                    'what_description': 'A dark theme',
                    'why_description': 'Reduces eye strain',
                    'use_case_description': 'Users working at night'
                }
            ],
            'generation_summary': 'Generated 1 idea'
        }

        service = IdeaGenerationService(db_session)
        result = service.generate_ideas_for_session(
            session_id=1,
            llm_service=Mock()
        )

    # Verify result
    assert result['status'] == 'completed'
    assert result['ideas_generated'] == 1

    # Verify database record created
    idea = db_session.query(CompetitorGeneratedIdea).first()
    assert idea is not None
    assert idea.feature_id == 1
    assert idea.idea_what == 'A dark theme'


def test_finalize_ideas_creates_idea_records(db_session):
    """Test that finalization creates Idea records"""
    # Create session and approved idea
    session = CompetitorAnalysisSession(id=1, product_id=1)
    db_session.add(session)

    competitor = SessionCompetitor(id=1, session_id=1, competitor_name='Notion')
    db_session.add(competitor)

    feature = CompetitorFeature(
        id=1,
        session_competitor_id=1,
        feature_name='Dark Mode',
        feature_category='UI'
    )
    db_session.add(feature)

    generated_idea = CompetitorGeneratedIdea(
        feature_id=1,
        session_id=1,
        product_id=1,
        idea_what='Dark mode for app',
        idea_why='Reduces eye strain',
        idea_use_case='Users working late',
        user_approved=True,
        submitted_to_ideas=False
    )
    db_session.add(generated_idea)
    db_session.commit()

    # Finalize
    service = IdeaGenerationService(db_session)
    result = service.finalize_ideas(session_id=1)

    # Verify Idea created
    assert result['status'] == 'success'
    assert result['submitted_count'] == 1

    idea = db_session.query(Idea).first()
    assert idea is not None
    assert idea.source_type == SourceType.COMPETITOR
    assert idea.what_description == 'Dark mode for app'
    assert idea.submitter_id is None  # Competitor ideas have no submitter

    # Verify linking
    generated_idea = db_session.query(CompetitorGeneratedIdea).first()
    assert generated_idea.submitted_to_ideas == True
    assert generated_idea.final_idea_id == idea.id
```

### 3. Manual Testing Steps

1. **Complete Feature Extraction (Stage 3)**
   - Run competitor analysis session through Stages 1-3
   - Select at least 3 features for idea generation
   - Verify features show as "selected"

2. **Test Idea Generation (Stage 4)**
   - Click "Generate Ideas" button
   - Verify AI generates ideas for each selected feature
   - Check that ideas are product-specific (not generic copies)
   - Verify source competitor and feature shown for each idea
   - Test inline editing:
     - Click "Edit Idea" on an idea
     - Modify what/why/use_case fields
     - Save and verify changes persist
     - Check "Edited" badge appears
   - Test approval:
     - Click "Approve" on several ideas
     - Verify border changes to green
     - Verify count updates ("X approved")
   - Test regeneration:
     - Click "Regenerate" button
     - Verify new ideas generated
     - Check that previous approvals/edits are reset

3. **Test Finalization (Stage 5)**
   - Navigate to Stage 5
   - Verify only approved ideas shown
   - Check count display correct
   - Review all idea content
   - Click "Submit to Voting System"
   - Verify success message
   - Click "View Ideas in Voting System"
   - Verify ideas appear in main ideas list
   - Check source_type = "competitor_automated"
   - Verify no submitter shown (null submitter_id)

4. **Test Error Cases**
   - Try generating ideas with no features selected (should show error)
   - Try finalizing with no approved ideas (should show warning)
   - Test API failures (mock API errors, verify UI shows appropriate messages)

5. **Test Traceability**
   - After submission, query database:
     ```sql
     SELECT i.id, i.title, cgi.id as gen_id, cf.feature_name, sc.competitor_name
     FROM ideas i
     JOIN competitor_generated_ideas cgi ON i.id = cgi.final_idea_id
     JOIN competitor_features cf ON cgi.feature_id = cf.id
     JOIN session_competitors sc ON cf.session_competitor_id = sc.id
     WHERE i.source_type = 'competitor_automated';
     ```
   - Verify full chain: Idea → CompetitorGeneratedIdea → CompetitorFeature → Competitor

## Acceptance Criteria

### Backend
- [ ] IdeaStructuringAgent inherits from BaseAgent properly
- [ ] Agent includes full product context in prompts
- [ ] Agent generates product-specific ideas (not generic)
- [ ] Agent validates output against Pydantic schema
- [ ] Agent execution logged to AgentExecutionLog
- [ ] IdeaGenerationService orchestrates full lifecycle
- [ ] Service creates CompetitorGeneratedIdea records
- [ ] Service supports editing with user_edited flag
- [ ] Service supports approval/rejection
- [ ] Service finalize creates Idea records correctly
- [ ] Idea records have source_type='competitor_automated'
- [ ] Idea records have null submitter_id
- [ ] CompetitorGeneratedIdea.final_idea_id links to Idea.id
- [ ] All API endpoints return appropriate status codes
- [ ] Error handling with meaningful messages

### Frontend
- [ ] Stage 4 loads existing ideas if already generated
- [ ] Generate button triggers idea generation
- [ ] Loading states shown during generation
- [ ] Ideas display in cards with what/why/use_case
- [ ] Source competitor and feature shown
- [ ] Inline editing works for all three fields
- [ ] Edited badge appears after editing
- [ ] Approve/reject toggles work correctly
- [ ] Approval count updates in real-time
- [ ] Stage 5 shows only approved ideas
- [ ] Idea count displayed correctly
- [ ] Submit button creates Idea records
- [ ] Success message shown after submission
- [ ] Link to main ideas page works
- [ ] Navigation between stages works smoothly

### Integration
- [ ] End-to-end workflow: Stage 3 → Stage 4 → Stage 5 → Ideas list
- [ ] Ideas searchable in main ideas page
- [ ] Ideas votable by users
- [ ] Traceability maintained through all tables
- [ ] Session stage updates correctly
- [ ] Multiple sessions don't interfere with each other
- [ ] Product context properly passed from session to agent

### Data Integrity
- [ ] No orphaned CompetitorGeneratedIdea records
- [ ] Foreign keys properly constrained
- [ ] Idea.source_type set correctly
- [ ] Timestamps (created_at, edited_at) accurate
- [ ] user_edited flag accurate
- [ ] user_approved flag accurate
- [ ] submitted_to_ideas flag prevents double submission

## Files to Create/Modify

### New Files
- `backend/app/agents/idea_structuring_agent.py` - AI agent for idea adaptation
- `backend/app/services/idea_generation_service.py` - Service layer for idea lifecycle
- `backend/tests/test_idea_structuring_agent.py` - Agent unit tests
- `backend/tests/test_idea_generation_service.py` - Service unit tests
- `frontend/src/pages/CompetitorIntelligence/stages/Stage4_IdeaGeneration.jsx` - Stage 4 UI
- `frontend/src/pages/CompetitorIntelligence/stages/Stage5_Finalization.jsx` - Stage 5 UI

### Modified Files
- `backend/app/api/sessions.py` - Add 5 new endpoints for idea generation/approval/finalization
- `frontend/src/pages/CompetitorIntelligence/SessionWorkflowPage.jsx` - Add Stage 4 and 5 to wizard flow

## Estimated Time
3-4 days

## Next Module
**Module 8: Frontend Wizard Integration & Polish**
- Wizard navigation and progress indicators
- Change indicator components throughout
- Session history and re-analysis
- Responsive design polish
- Performance optimization
