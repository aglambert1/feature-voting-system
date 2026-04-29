from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.models.competitor_intelligence import (
    CompetitorAnalysisSession,
    CompetitorFeature,
    SessionCompetitor,
    CompetitorGeneratedIdea,
    ProductFeature,
    CIProduct
)
from app.models.idea import Idea, SourceType, IdeaStatus
from app.models.queue import JobType
from app.agents.idea_structuring_agent import IdeaStructuringAgent
from app.services.llm_service import LLMService
from app.services.queue_service import QueueService


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

        # Enhance product context with detailed features for duplicate detection
        if session.analysis_version:
            detailed_features = self.db.query(ProductFeature).filter(
                ProductFeature.product_id == session.product_id,
                ProductFeature.analysis_version == session.analysis_version,
                ProductFeature.status == "active"
            ).all()

            product_context['detailed_features'] = [
                {
                    'feature_name': feat.feature_name,
                    'feature_description': feat.feature_description,
                    'feature_category': feat.feature_category
                }
                for feat in detailed_features
            ]
        else:
            # Fallback: try to get the latest product features if no analysis_version
            product = self.db.query(CIProduct).filter(
                CIProduct.id == session.product_id
            ).first()

            if product and product.analysis_version:
                detailed_features = self.db.query(ProductFeature).filter(
                    ProductFeature.product_id == session.product_id,
                    ProductFeature.analysis_version == product.analysis_version,
                    ProductFeature.status == "active"
                ).all()

                product_context['detailed_features'] = [
                    {
                        'feature_name': feat.feature_name,
                        'feature_description': feat.feature_description,
                        'feature_category': feat.feature_category
                    }
                    for feat in detailed_features
                ]

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

        # Store generated ideas and create Idea records with triage
        generated_ideas = []
        triage_jobs_queued = 0

        # Import triage task here to avoid circular imports
        from app.queue.triage_tasks import triage_idea_task
        queue_service = QueueService(self.db)

        for idea_data in agent_result.get('ideas', []):
            # Get feature info for source metadata
            feature = self.db.query(CompetitorFeature).filter(
                CompetitorFeature.id == idea_data['feature_id']
            ).first()
            competitor = feature.session_competitor if feature else None
            competitor_name = competitor.competitor_name if competitor else None
            feature_name = feature.feature_name if feature else None

            # Check if CompetitorGeneratedIdea already exists for this feature
            existing = self.db.query(CompetitorGeneratedIdea).filter(
                CompetitorGeneratedIdea.feature_id == idea_data['feature_id'],
                CompetitorGeneratedIdea.session_id == session_id
            ).first()

            if existing:
                # Update existing CompetitorGeneratedIdea
                existing.idea_what = idea_data['what']
                existing.idea_why = idea_data['why']
                existing.idea_use_case = idea_data['use_case']
                existing.user_edited = False
                existing.user_approved = False
                existing.submitted_to_ideas = True  # Now submitted immediately
                generated_idea = existing

                # If there's an existing linked Idea, update it
                if existing.final_idea_id:
                    linked_idea = self.db.query(Idea).filter(
                        Idea.id == existing.final_idea_id
                    ).first()
                    if linked_idea:
                        linked_idea.what_description = idea_data['what']
                        linked_idea.why_description = idea_data['why']
                        linked_idea.use_case_description = idea_data['use_case']
                        linked_idea.status = IdeaStatus.PENDING
                        linked_idea.is_active = False
                        idea_record = linked_idea
                    else:
                        # Linked idea was deleted, create new one
                        idea_record = None
                else:
                    idea_record = None
            else:
                # Create new CompetitorGeneratedIdea
                generated_idea = CompetitorGeneratedIdea(
                    feature_id=idea_data['feature_id'],
                    session_id=session_id,
                    product_id=session.product_id,
                    idea_what=idea_data['what'],
                    idea_why=idea_data['why'],
                    idea_use_case=idea_data['use_case'],
                    user_edited=False,
                    user_approved=False,
                    submitted_to_ideas=True  # Now submitted immediately
                )
                self.db.add(generated_idea)
                idea_record = None

            self.db.flush()

            # Create Idea record if not exists
            if idea_record is None:
                # Generate title from what description (first sentence)
                what_first_sentence = idea_data['what'].split('.')[0].strip()
                title = what_first_sentence[:100] if len(what_first_sentence) <= 100 else what_first_sentence[:97] + "..."

                idea_record = Idea(
                    title=title,
                    what_description=idea_data['what'],
                    why_description=idea_data['why'],
                    use_case_description=idea_data['use_case'],
                    category=feature.feature_category if feature else None,
                    product_id=session.product_id,
                    source_type=SourceType.COMPETITOR_AUTOMATED,
                    submitter_id=None,  # Competitor ideas have no submitter
                    status=IdeaStatus.PENDING,
                    is_active=False,
                    source_metadata={
                        'competitor_generated_idea_id': generated_idea.id,
                        'feature_id': idea_data['feature_id'],
                        'session_id': session_id,
                        'competitor_name': competitor_name,
                        'feature_name': feature_name,
                    }
                )
                self.db.add(idea_record)
                self.db.flush()

                # Link CompetitorGeneratedIdea to Idea
                generated_idea.final_idea_id = idea_record.id

            # Queue triage job for this idea
            try:
                job = queue_service.create_job(
                    job_type=JobType.IDEA_TRIAGE,
                    input_data={
                        'idea_id': idea_record.id,
                        'source_type': SourceType.COMPETITOR_AUTOMATED.value,
                    },
                    product_id=session.product_id,
                    user_id=None,  # System-initiated for competitor ideas
                )
                celery_result = triage_idea_task.delay(job.id)
                queue_service.mark_queued(job.id, celery_result.id)
                triage_jobs_queued += 1
            except Exception as e:
                print(f"Warning: Failed to queue triage job for idea {idea_record.id}: {e}")

            generated_ideas.append({
                'id': generated_idea.id,
                'feature_id': generated_idea.feature_id,
                'title': idea_data.get('title', ''),
                'what': generated_idea.idea_what,
                'why': generated_idea.idea_why,
                'use_case': generated_idea.idea_use_case,
                'adaptation_notes': idea_data.get('adaptation_notes', ''),
                # NEW: Include linked Idea data
                'idea_id': idea_record.id,
                'status': idea_record.status.value if idea_record.status else 'pending',
                'is_active': idea_record.is_active,
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
            'generation_summary': agent_result.get('generation_summary', ''),
            'triage_jobs_queued': triage_jobs_queued,
        }

    def get_generated_ideas(self, session_id: int) -> Dict[str, Any]:
        """
        Get all generated ideas for a session.

        Args:
            session_id: Session ID

        Returns:
            Dict with generated ideas and metadata including triage status
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

            # Get linked Idea for triage status
            linked_idea = None
            if idea.final_idea_id:
                linked_idea = self.db.query(Idea).filter(
                    Idea.id == idea.final_idea_id
                ).first()

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
                'created_at': idea.created_at.isoformat() if idea.created_at else None,
                # Include linked Idea data for status
                'idea_id': idea.final_idea_id,
                'status': linked_idea.status.value if linked_idea and linked_idea.status else None,
                'triage_confidence': linked_idea.triage_confidence if linked_idea else None,
                'triage_recommendation': linked_idea.triage_recommendation if linked_idea else None,
                'is_active': linked_idea.is_active if linked_idea else False,
            })

        # Count by status
        accepted_count = sum(1 for i in result if i.get('status') == 'accepted')
        needs_review_count = sum(1 for i in result if i.get('status') == 'needs_review')
        pending_count = sum(1 for i in result if i.get('status') == 'pending')
        duplicate_count = sum(1 for i in result if i.get('status') == 'duplicate')

        return {
            'session_id': session_id,
            'ideas': result,
            'total_count': len(result),
            'accepted_count': accepted_count,
            'needs_review_count': needs_review_count,
            'pending_count': pending_count,
            'duplicate_count': duplicate_count,
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
        Mark session as completed.

        Note: Ideas are now created during generation (generate_ideas_for_session)
        and triaged immediately. This method just marks the session as completed
        for tracking purposes.

        Args:
            session_id: Session ID

        Returns:
            Dict with session completion status
        """
        # Get session
        session = self.db.query(CompetitorAnalysisSession).filter(
            CompetitorAnalysisSession.id == session_id
        ).first()

        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Get all generated ideas for this session
        generated_ideas = self.db.query(CompetitorGeneratedIdea).filter(
            CompetitorGeneratedIdea.session_id == session_id
        ).all()

        # Count statuses from linked Ideas (using new IdeaStatus values)
        status_counts = {
            'accepted': 0,
            'needs_review': 0,
            'pending': 0,
            'duplicate': 0,
            'merged': 0,
            'feature_exists': 0,
            'not_appropriate': 0,
        }

        for gen_idea in generated_ideas:
            if gen_idea.final_idea_id:
                linked_idea = self.db.query(Idea).filter(
                    Idea.id == gen_idea.final_idea_id
                ).first()
                if linked_idea and linked_idea.status:
                    status = linked_idea.status.value
                    if status in status_counts:
                        status_counts[status] += 1
                    else:
                        status_counts['pending'] += 1

        # Update session stage to completed
        session.current_stage = "completed"
        self.db.commit()

        return {
            'status': 'success',
            'session_id': session_id,
            'total_ideas': len(generated_ideas),
            'status_counts': status_counts,
            'message': f'Session completed with {len(generated_ideas)} ideas'
        }
