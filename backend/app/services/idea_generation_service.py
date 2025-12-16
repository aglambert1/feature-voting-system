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
        product_context = session.analyzed_product_structure or {}

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
                existing.idea_what = idea_data['what']
                existing.idea_why = idea_data['why']
                existing.idea_use_case = idea_data['use_case']
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
                    idea_what=idea_data['what'],
                    idea_why=idea_data['why'],
                    idea_use_case=idea_data['use_case'],
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
                product_id=session.product_id,  # Associate with session's product
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
