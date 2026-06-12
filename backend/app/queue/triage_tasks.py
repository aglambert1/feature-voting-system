"""Celery tasks for idea triage.

Houses the two triage entry points:

* ``triage_idea_task`` — runs IdeaTriageAgent against an existing Idea row.
* ``submit_and_triage_idea_task`` — normalize raw input, create the Idea,
  then run triage in one job.

Both paths set ``job_id_key`` via ``_link_idea_to_job`` and persist competitive
context, JTBD embedding, and auto-response text.
"""

import traceback
from typing import Dict, Any
from celery import shared_task

from app.services.queue_service import QueueService
from app.services.llm_service import LLMService
from app.queue.helpers import (
    get_db,
    _link_idea_to_job,
    _maybe_suggest_need,
    _sanitize_existing_feature_info,
)


# ============================================================================
# Phase 3: Idea Triage Task
# ============================================================================

@shared_task(bind=True, name='app.queue.triage_tasks.triage_idea_task', soft_time_limit=300)
def triage_idea_task(self, job_id: int) -> Dict[str, Any]:
    """
    Background task to triage an idea.

    This task:
    1. Retrieves the idea
    2. Runs similarity detection for duplicates
    3. Finds competitive matches
    4. Runs IdeaTriageAgent for analysis
    5. Updates idea with triage results
    6. Stores idea embedding for future similarity

    Args:
        job_id: QueueJob ID

    Returns:
        Dictionary with triage results
    """
    from app.services.similarity_detector import SimilarityDetectorService
    from app.agents.idea_triage import IdeaTriageAgent
    from app.models.idea import Idea, IdeaStatus, SourceType
    from app.models.idea_status_history import IdeaStatusHistory
    from app.models.competitor_intelligence import CIProduct

    db = None
    try:
        db = get_db()
        queue_service = QueueService(db)
        llm_service = LLMService()

        # Mark job as running
        job = queue_service.mark_running(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        # Get idea
        idea_id = job.input_data.get('idea_id')
        if not idea_id:
            raise ValueError("No idea_id in job input_data")

        idea = db.query(Idea).filter(Idea.id == idea_id).first()
        if not idea:
            raise ValueError(f"Idea {idea_id} not found")

        user_id = job.user_id

        # Check if this is a competitor-sourced idea
        is_competitor_idea = idea.source_type == SourceType.COMPETITOR_AUTOMATED

        # Update progress
        queue_service.update_progress(job_id, 10.0, "Finding similar ideas...")

        # Run similarity detection
        similarity_service = SimilarityDetectorService(db)
        idea_text = f"{idea.title}\n\n{idea.what_description}\n\n{idea.why_description}\n\n{idea.use_case_description}"
        similarity_result = similarity_service.detect_duplicates(
            idea_text=idea_text,
            product_id=idea.product_id,
            exclude_idea_id=idea.id
        )

        # Update progress
        queue_service.update_progress(job_id, 30.0, "Finding competitive matches...")

        # Find competitive matches - use different strategies based on idea source
        if is_competitor_idea and idea.source_metadata:
            # For competitor-sourced ideas, use pre-computed data from landscape report
            # This ensures consistency between landscape analysis and triage
            from app.models.competitive_reports import CompetitorFunctionalReport

            competitors_with = idea.source_metadata.get('competitors_with_feature', [])
            tracked_count = db.query(CompetitorFunctionalReport).filter(
                CompetitorFunctionalReport.product_id == idea.product_id
            ).count()

            # Calculate urgency based on competitor prevalence
            if tracked_count > 0:
                prevalence = len(competitors_with) / tracked_count
                if prevalence >= 0.8:
                    urgency_level = "critical"
                    reasoning = f"Table stakes: {len(competitors_with)} of {tracked_count} tracked competitors ({prevalence*100:.0f}%) have this feature."
                elif prevalence >= 0.5 or len(competitors_with) >= 3:
                    urgency_level = "high"
                    reasoning = f"High priority: {len(competitors_with)} of {tracked_count} tracked competitors have this feature."
                elif len(competitors_with) >= 1:
                    urgency_level = "medium"
                    reasoning = f"Competitive parity: {len(competitors_with)} of {tracked_count} tracked competitors have this feature."
                else:
                    urgency_level = "low"
                    reasoning = f"Potential differentiator: None of {tracked_count} tracked competitors have this feature."
            else:
                urgency_level = "low"
                reasoning = "No competitive data available from landscape analysis."

            competitive_context = {
                "matches": [],  # No need to re-match - we have authoritative data
                "urgency": {
                    "urgency": urgency_level,
                    "competitor_count": len(competitors_with),
                    "total_competitors_analyzed": tracked_count,
                    "competitors_with_feature": competitors_with,
                    "reasoning": reasoning
                }
            }
        else:
            # For customer-submitted ideas, use V2 functional reports
            competitive_context = similarity_service.find_competitive_matches_from_reports(
                idea_text=idea_text,
                product_id=idea.product_id,
                limit=5
            )

        # Update progress
        queue_service.update_progress(job_id, 40.0, "Checking existing product features...")

        # Find matching product features (detect if idea describes existing functionality)
        product_feature_result = similarity_service.find_product_feature_matches(
            idea_text=idea_text,
            product_id=idea.product_id,
            limit=3
        )

        # Find related synthesis opportunities so the agent knows whether this
        # idea has already been identified as an opportunity for the product.
        # Especially important for ideas created from a parent opportunity
        # (manual create-from-opp endpoint or auto-gen path).
        from app.models.synthesis import SynthesizedOpportunity
        related_opps_list = []
        seen_opp_ids = set()
        opportunity_id = (idea.source_metadata or {}).get('opportunity_id')
        if opportunity_id:
            direct = db.query(SynthesizedOpportunity).filter_by(id=opportunity_id).first()
            if direct:
                related_opps_list.append(direct)
                seen_opp_ids.add(direct.id)
        title_fragment = (idea.title or '')[:40]
        if title_fragment.strip():
            fuzzy_q = db.query(SynthesizedOpportunity).filter(
                SynthesizedOpportunity.product_id == idea.product_id,
                SynthesizedOpportunity.opportunity_name.ilike(f"%{title_fragment}%"),
            ).order_by(SynthesizedOpportunity.priority_score.desc()).limit(3).all()
            for opp in fuzzy_q:
                if opp.id not in seen_opp_ids:
                    related_opps_list.append(opp)
                    seen_opp_ids.add(opp.id)

        # Get product context
        product = db.query(CIProduct).filter(CIProduct.id == idea.product_id).first()
        product_context = {}
        if product:
            product_context = {
                'product_name': product.product_name,
                'product_category': product.product_category,
                'existing_categories': _get_existing_categories(db, idea.product_id),
            }
            if product.structured_product_data:
                product_context.update({
                    'core_features': product.structured_product_data.get('core_features', []),
                    'target_users': product.structured_product_data.get('target_users', ''),
                })

        # Update progress
        queue_service.update_progress(job_id, 50.0, "Running AI triage analysis...")

        # Prepare input for triage agent
        agent_input = {
            'idea': {
                'title': idea.title,
                'what_description': idea.what_description,
                'why_description': idea.why_description,
                'use_case_description': idea.use_case_description,
                'source_type': idea.source_type.value,
            },
            'product_context': product_context,
            'similar_ideas': [
                {
                    'idea_id': s.idea_id,
                    'title': s.title,
                    'similarity_score': s.similarity_score,
                    'is_duplicate': s.is_duplicate,
                }
                for s in similarity_result.similar_ideas
            ],
            # Pass full competitive context with structured urgency
            'competitive_context': competitive_context,
            # Pass existing product feature match info for feature exists detection
            'existing_feature_match': {
                'has_match': product_feature_result.has_match,
                'best_match': {
                    'feature_name': product_feature_result.best_match.feature_name,
                    'feature_description': product_feature_result.best_match.feature_description,
                    'similarity_score': product_feature_result.best_match.similarity_score,
                    'source_url': product_feature_result.best_match.source_url,
                } if product_feature_result.best_match else None,
                'all_matches': [
                    {
                        'feature_name': m.feature_name,
                        'feature_description': m.feature_description,
                        'similarity_score': m.similarity_score,
                        'source_url': m.source_url,
                    }
                    for m in product_feature_result.matches
                ]
            },
            'related_synthesis_opportunities': [
                {
                    'opportunity_id': o.id,
                    'opportunity_name': o.opportunity_name,
                    'priority_score': float(o.priority_score) if o.priority_score is not None else None,
                    'investment_tier': o.investment_tier,
                    'job_id_key': o.job_id_key,
                    'has_linked_idea': o.linked_idea_id is not None,
                    'sources': o.sources or [],
                }
                for o in related_opps_list[:3]
            ],
        }

        # Run triage agent
        agent = IdeaTriageAgent(
            db=db,
            llm_service=llm_service,
            product_id=idea.product_id,
            user_id=user_id,
            job_id=job.job_uuid
        )
        triage_result = agent.execute(agent_input)

        # Update progress
        queue_service.update_progress(job_id, 80.0, "Updating idea with triage results...")

        # Get product auto-respond settings
        auto_respond_enabled = False
        auto_respond_threshold = 0.9
        if product and hasattr(product, 'idea_triage_auto_enabled'):
            auto_respond_enabled = product.idea_triage_auto_enabled
            auto_respond_threshold = getattr(product, 'idea_triage_auto_threshold', 0.9)

        # Determine status (only auto-approves if auto-respond is enabled).
        # The agent is the arbiter; the deterministic existing-feature
        # similarity signal is passed into the agent's prompt (above) and the
        # agent decides whether to populate existing_feature_info. We do NOT
        # backfill existing_feature_info from the deterministic match — if the
        # agent didn't populate it, the agent disagreed that the idea actually
        # duplicates the matched feature, and we trust that judgment.
        new_status = agent.determine_triage_status(
            triage_result,
            auto_respond_enabled=auto_respond_enabled,
            auto_respond_threshold=auto_respond_threshold,
        )

        # Get recommendation details
        recommendation = triage_result.get('recommendation', {})
        action_str = recommendation.get('action', 'review')

        # Update idea with triage results
        old_status = idea.status
        idea.status = new_status
        # Set is_active based on product's visibility config
        idea.is_active = product.get_is_active_for_status(new_status) if product else new_status == IdeaStatus.ACCEPTED
        idea.triage_confidence = recommendation.get('confidence', 0.5)
        idea.triage_reasoning = recommendation.get('reasoning', '')
        idea.triage_recommendation = action_str  # Store as string
        idea.triage_job_id = job.id

        # Update category if provided
        if triage_result.get('category'):
            idea.category = triage_result['category']
            idea.auto_categorized = True

        # Handle duplicate detection - store duplicate info if agent recommends merge
        # This is stored regardless of auto-respond setting so PO can see the suggestion
        if action_str == 'merge' and similarity_result.best_match:
            idea.duplicate_of_idea_id = similarity_result.best_match.idea_id
            idea.similarity_score = similarity_result.best_match.similarity_score

        # Store competitive context.
        # Two sources of competitors_with_feature exist:
        # - Agent output (`triage_result.competitive_context.competitors_with_feature`):
        #   reliable for customer-submitted ideas because the agent saw real
        #   similarity_service matches in its prompt and echoed them back.
        # - Deterministic source_metadata (set by synthesis writers in PR #45):
        #   the authoritative competitor list for competitor-sourced ideas
        #   (auto-gen + manual create-from-opp).
        # For competitor-sourced ideas the agent's list is unreliable — synthesis
        # prompts sometimes use anonymized labels ("Competitor 1") which the
        # agent echoes alongside the real names, producing phantom duplicates.
        # Trust the deterministic list and ignore the agent's prose for this field.
        comp_context = triage_result.get('competitive_context', {})

        if is_competitor_idea and idea.source_metadata:
            source_competitor_names = idea.source_metadata.get('competitor_names', [])
            if not source_competitor_names:
                single_name = idea.source_metadata.get('competitor_name')
                if single_name:
                    source_competitor_names = [single_name]
            competitors_with_feature = list(source_competitor_names)
        else:
            competitors_with_feature = list(comp_context.get('competitors_with_feature', []))

        if comp_context or competitors_with_feature:
            idea.competitive_context = {
                'competitors_with_feature': competitors_with_feature,
                'competitive_urgency': comp_context.get('competitive_urgency', 'medium' if is_competitor_idea else 'low'),
            }

        # Store existing feature info if detected (feature exists case).
        # Sanitize source_url to drop placeholder/non-URL values like "N/A"
        # that the agent occasionally echoes from prompt context.
        existing_feature_info = triage_result.get('existing_feature_info')
        if existing_feature_info:
            idea.competitive_context = idea.competitive_context or {}
            idea.competitive_context['existing_feature'] = _sanitize_existing_feature_info(existing_feature_info)

        # Store auto-response text
        if not is_competitor_idea and triage_result.get('auto_response_text'):
            # Customer ideas get AI-generated response
            idea.auto_response_text = triage_result['auto_response_text']
        elif is_competitor_idea:
            # Competitor ideas get a default response referencing the source
            source_names = idea.source_metadata.get('competitor_names', []) if idea.source_metadata else []
            if not source_names:
                source_names = [idea.source_metadata.get('competitor_name')] if idea.source_metadata and idea.source_metadata.get('competitor_name') else []
            competitor_ref = ', '.join(source_names[:3]) if source_names else 'competitor analysis'
            if len(source_names) > 3:
                competitor_ref += f" and {len(source_names) - 3} others"
            idea.auto_response_text = f"From analysis of {competitor_ref}"

        # Store JTBD statement and generate embedding for clustering
        jtbd = triage_result.get('jtbd_statement')
        if jtbd:
            idea.jtbd_statement = jtbd
            try:
                from app.services.embedding_service import generate_embedding
                idea.jtbd_embedding = generate_embedding(jtbd, input_type="document")
            except Exception as jtbd_emb_err:
                print(f"[triage_idea_task] Warning: JTBD embedding failed: {jtbd_emb_err}")

            # Link idea to best-matching ProductJob via embedding similarity.
            # Reset first so a no-match clears any stale value from a previous triage.
            idea.job_id_key = None
            try:
                matched_key = _link_idea_to_job(db, idea, llm_service=llm_service)
                if matched_key:
                    print(f"[triage_idea_task] Linked idea {idea.id} to job {matched_key}")
            except Exception as link_err:
                print(f"[triage_idea_task] Warning: Job linkage failed: {link_err}")

            # Surface unmatched/weak-match signals as need map suggestions
            _maybe_suggest_need(
                db,
                product_id=idea.product_id,
                signal_type="idea",
                signal_id=idea.id,
                signal_content=idea.title or idea.description or "",
                jtbd_embedding=idea.jtbd_embedding,
            )

        # Record status history for agent triage
        # Only record as automated action if auto-respond is ON and status changed
        # When auto-respond is OFF, we don't record the agent's recommendation in history
        # (the PO's response will be recorded when they respond)
        if auto_respond_enabled:
            status_history = IdeaStatusHistory(
                idea_id=idea.id,
                previous_status=old_status,
                new_status=new_status,
                changed_by_user_id=None,  # Automated by agent
                is_automated=True,
                change_source='agent_triage',
                comment=idea.triage_reasoning,
                confidence=int(idea.triage_confidence * 100) if idea.triage_confidence else None,
            )
            db.add(status_history)

        db.commit()

        # Update progress
        queue_service.update_progress(job_id, 90.0, "Storing idea embedding...")

        # Store embedding for future similarity detection
        try:
            similarity_service.store_idea_embedding(idea)
            db.commit()
        except Exception as e:
            print(f"[triage_idea_task] Warning: Failed to store embedding: {e}")

        # Prepare output
        output_data = {
            'idea_id': idea.id,
            'status': new_status.value,
            'is_active': idea.is_active,
            'triage_confidence': idea.triage_confidence,
            'triage_recommendation': action_str,
            'category': idea.category,
            'has_duplicates': similarity_result.has_duplicates,
            'has_similar': similarity_result.has_similar,
            'similar_count': len(similarity_result.similar_ideas),
            'duplicate_of_idea_id': idea.duplicate_of_idea_id,
            'competitors_with_feature': comp_context.get('competitors_with_feature', []),
            'existing_feature_match': product_feature_result.has_match,
            'existing_feature_info': {
                'feature_name': product_feature_result.best_match.feature_name,
                'feature_description': product_feature_result.best_match.feature_description,
                'similarity_score': product_feature_result.best_match.similarity_score,
                'source_url': product_feature_result.best_match.source_url,
            } if product_feature_result.best_match else None,
            'auto_response_generated': bool(idea.auto_response_text),
        }

        # Mark success
        queue_service.mark_success(job_id, output_data)

        return output_data

    except Exception as e:
        error_msg = str(e)
        error_tb = traceback.format_exc()
        print(f"[triage_idea_task] Error: {error_msg}")

        if db:
            try:
                queue_service = QueueService(db)
                queue_service.mark_failure(job_id, error_msg, error_tb)
            except Exception:
                pass

        raise

    finally:
        if db:
            db.close()


def _get_existing_categories(db, product_id: int) -> list:
    """Get list of existing idea categories for a product."""
    from app.models.idea import Idea
    from sqlalchemy import distinct

    results = db.query(distinct(Idea.category)).filter(
        Idea.product_id == product_id,
        Idea.category.isnot(None)
    ).all()

    return [r[0] for r in results if r[0]]


@shared_task(bind=True, name='app.queue.triage_tasks.submit_and_triage_idea_task', soft_time_limit=600)
def submit_and_triage_idea_task(self, job_id: int) -> Dict[str, Any]:
    """
    Combined task for submitting and triaging an idea in one step.

    This is a convenience task that:
    1. Normalizes the raw input
    2. Creates the idea
    3. Runs triage
    4. Returns complete results

    Args:
        job_id: QueueJob ID

    Returns:
        Dictionary with idea creation and triage results
    """
    from app.services.idea_normalizer_service import IdeaNormalizerService
    from app.services.similarity_detector import SimilarityDetectorService
    from app.agents.idea_triage import IdeaTriageAgent
    from app.models.idea import Idea, IdeaStatus, SourceType
    from app.models.competitor_intelligence import CIProduct

    db = None
    try:
        db = get_db()
        queue_service = QueueService(db)
        llm_service = LLMService()

        # Mark job as running
        job = queue_service.mark_running(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        input_data = job.input_data or {}
        raw_input = input_data.get('raw_input', {})
        source_type_str = input_data.get('source_type')
        user_id = job.user_id

        # Parse source type
        source_type = None
        if source_type_str:
            source_type = SourceType(source_type_str)

        # Step 1: Normalize
        queue_service.update_progress(job_id, 10.0, "Normalizing idea...")
        normalizer = IdeaNormalizerService(db, llm_service)
        normalized = normalizer.normalize(raw_input, source_type)

        # Step 2: Create idea
        queue_service.update_progress(job_id, 25.0, "Creating idea record...")
        idea = normalizer.create_idea_from_normalized(normalized, IdeaStatus.PENDING)
        db.add(idea)
        db.commit()
        db.refresh(idea)

        # Step 3: Similarity detection
        queue_service.update_progress(job_id, 40.0, "Finding similar ideas...")
        similarity_service = SimilarityDetectorService(db)
        idea_text = f"{idea.title}\n\n{idea.what_description}\n\n{idea.why_description}\n\n{idea.use_case_description}"
        similarity_result = similarity_service.detect_duplicates(
            idea_text=idea_text,
            product_id=idea.product_id,
            exclude_idea_id=idea.id
        )

        # Step 4: Competitive matches using V2 functional reports
        queue_service.update_progress(job_id, 55.0, "Finding competitive matches...")
        competitive_context = similarity_service.find_competitive_matches_from_reports(
            idea_text=idea_text,
            product_id=idea.product_id,
            limit=5
        )

        # Step 4b: Check if idea matches existing product features ("Feature Exists" detection)
        queue_service.update_progress(job_id, 60.0, "Checking for existing product features...")
        product_feature_result = similarity_service.find_product_feature_matches(
            idea_text=idea_text,
            product_id=idea.product_id,
            similarity_threshold=0.80
        )

        # Get product context
        product = db.query(CIProduct).filter(CIProduct.id == idea.product_id).first()
        product_context = {}
        if product:
            product_context = {
                'product_name': product.product_name,
                'product_category': product.product_category,
                'existing_categories': _get_existing_categories(db, idea.product_id),
            }
            if product.structured_product_data:
                product_context.update({
                    'core_features': product.structured_product_data.get('core_features', []),
                    'target_users': product.structured_product_data.get('target_users', ''),
                })

        # Step 5: Run triage agent
        queue_service.update_progress(job_id, 70.0, "Running AI triage analysis...")
        agent_input = {
            'idea': {
                'title': idea.title,
                'what_description': idea.what_description,
                'why_description': idea.why_description,
                'use_case_description': idea.use_case_description,
                'source_type': idea.source_type.value,
            },
            'product_context': product_context,
            'similar_ideas': [
                {
                    'idea_id': s.idea_id,
                    'title': s.title,
                    'similarity_score': s.similarity_score,
                    'is_duplicate': s.is_duplicate,
                }
                for s in similarity_result.similar_ideas
            ],
            # Pass full competitive context with structured urgency
            'competitive_context': competitive_context,
            # Pass existing product feature match for "Feature Exists" detection
            'existing_feature_match': {
                'has_match': product_feature_result.has_match,
                'best_match': {
                    'feature_name': product_feature_result.best_match.feature_name,
                    'feature_description': product_feature_result.best_match.feature_description,
                    'similarity_score': product_feature_result.best_match.similarity_score,
                    'source_url': product_feature_result.best_match.source_url,
                } if product_feature_result.best_match else None,
            } if product_feature_result else None,
        }

        agent = IdeaTriageAgent(
            db=db,
            llm_service=llm_service,
            product_id=idea.product_id,
            user_id=user_id,
            job_id=job.job_uuid
        )
        triage_result = agent.execute(agent_input)

        # Step 6: Update idea with triage results
        queue_service.update_progress(job_id, 85.0, "Updating idea with triage results...")

        # Get product auto-respond settings
        auto_respond_enabled = False
        auto_respond_threshold = 0.9
        if product and hasattr(product, 'idea_triage_auto_enabled'):
            auto_respond_enabled = product.idea_triage_auto_enabled
            auto_respond_threshold = getattr(product, 'idea_triage_auto_threshold', 0.9)

        # Determine status (only auto-approves if auto-respond is enabled).
        # Agent is the arbiter; deterministic similarity signal lives in the
        # prompt. We do NOT backfill existing_feature_info — if the agent didn't
        # populate it, the agent disagreed that the idea actually duplicates
        # the matched feature.
        new_status = agent.determine_triage_status(
            triage_result,
            auto_respond_enabled=auto_respond_enabled,
            auto_respond_threshold=auto_respond_threshold,
        )

        recommendation = triage_result.get('recommendation', {})
        action_str = recommendation.get('action', 'review')

        idea.status = new_status
        # Set is_active based on product's visibility config
        idea.is_active = product.get_is_active_for_status(new_status) if product else new_status == IdeaStatus.ACCEPTED
        idea.triage_confidence = recommendation.get('confidence', 0.5)
        idea.triage_reasoning = recommendation.get('reasoning', '')
        idea.triage_recommendation = action_str  # Store as string
        idea.triage_job_id = job.id

        if triage_result.get('category'):
            idea.category = triage_result['category']
            idea.auto_categorized = True

        # Handle duplicate detection - store duplicate info if agent recommends merge
        # This is stored regardless of auto-respond setting so PO can see the suggestion
        if action_str == 'merge' and similarity_result.best_match:
            idea.duplicate_of_idea_id = similarity_result.best_match.idea_id
            idea.similarity_score = similarity_result.best_match.similarity_score

        comp_context = triage_result.get('competitive_context', {})
        if comp_context:
            idea.competitive_context = {
                'competitors_with_feature': comp_context.get('competitors_with_feature', []),
                'competitive_urgency': comp_context.get('competitive_urgency', 'low'),
            }

        # Store existing feature info if detected (feature exists case).
        # Sanitize source_url to drop placeholder/non-URL values.
        existing_feature_info = triage_result.get('existing_feature_info')
        if existing_feature_info:
            idea.competitive_context = idea.competitive_context or {}
            idea.competitive_context['existing_feature'] = _sanitize_existing_feature_info(existing_feature_info)

        # Store auto-response text (always store for PO to use, regardless of auto-respond setting)
        if triage_result.get('auto_response_text'):
            idea.auto_response_text = triage_result['auto_response_text']

        # Store JTBD statement and generate embedding for clustering
        jtbd = triage_result.get('jtbd_statement')
        if jtbd:
            idea.jtbd_statement = jtbd
            try:
                from app.services.embedding_service import generate_embedding
                idea.jtbd_embedding = generate_embedding(jtbd, input_type="document")
            except Exception as jtbd_emb_err:
                print(f"[submit_and_triage_idea_task] Warning: JTBD embedding failed: {jtbd_emb_err}")

            # Link idea to best-matching ProductJob via embedding similarity
            try:
                matched_key = _link_idea_to_job(db, idea, llm_service=llm_service)
                if matched_key:
                    print(f"[submit_and_triage_idea_task] Linked idea {idea.id} to job {matched_key}")
            except Exception as link_err:
                print(f"[submit_and_triage_idea_task] Warning: Job linkage failed: {link_err}")

        db.commit()

        # Step 7: Store embedding
        queue_service.update_progress(job_id, 95.0, "Storing idea embedding...")
        try:
            similarity_service.store_idea_embedding(idea)
            db.commit()
        except Exception as e:
            print(f"[submit_and_triage_idea_task] Warning: Failed to store embedding: {e}")

        # Prepare output
        output_data = {
            'idea_id': idea.id,
            'title': idea.title,
            'source_type': idea.source_type.value,
            'category': idea.category,
            'status': new_status.value,
            'is_active': idea.is_active,
            'triage_confidence': idea.triage_confidence,
            'triage_recommendation': action_str,
            'has_duplicates': similarity_result.has_duplicates,
            'has_similar': similarity_result.has_similar,
            'duplicate_of_idea_id': idea.duplicate_of_idea_id,
            'competitors_with_feature': comp_context.get('competitors_with_feature', []),
            'existing_feature_match': product_feature_result.has_match if product_feature_result else False,
            'auto_response_text': idea.auto_response_text,
        }

        queue_service.mark_success(job_id, output_data)
        return output_data

    except Exception as e:
        error_msg = str(e)
        error_tb = traceback.format_exc()
        print(f"[submit_and_triage_idea_task] Error: {error_msg}")

        if db:
            try:
                queue_service = QueueService(db)
                queue_service.mark_failure(job_id, error_msg, error_tb)
            except Exception:
                pass

        raise

    finally:
        if db:
            db.close()


# DEPRECATED: Phase 4 Competitive Monitoring Tasks have been removed.
# monitor_competitors_task and scheduled_monitoring_task are deprecated.
# Competitive monitoring is now handled by the V2 functional audit workflow.
# Use functional_audit_task to run competitive analysis.
