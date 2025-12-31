"""
Celery tasks for background job processing.

This module defines Celery tasks that wrap existing agents and services
for asynchronous execution. Each task:
1. Retrieves its QueueJob record
2. Updates job status as it progresses
3. Executes the underlying agent/service
4. Stores results and updates final status
"""

import traceback
from typing import Dict, Any, Optional, List
from celery import shared_task, group, chain
from datetime import datetime

from app.database import SessionLocal
from app.models.queue import JobStatus, JobType
from app.models.competitor_intelligence import (
    CIProduct, ProductAnalysisHistory, ProductFeature,
    ProductCompetitor, ProductCompetitorFeature, SessionCompetitor, CompetitorFeature
)
from app.services.queue_service import QueueService
from app.services.llm_service import LLMService
from app.agents.product_analyzer import ProductAnalyzerAgent
from app.agents.competitor_researcher import CompetitorResearcherAgent
from app.agents.feature_extractor import FeatureExtractorAgent


def get_db():
    """Get a database session for task execution."""
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


@shared_task(bind=True, name='app.queue.tasks.analyze_product_task')
def analyze_product_task(self, job_id: int) -> Dict[str, Any]:
    """
    Background task to analyze a product using ProductAnalyzerAgent.

    This task:
    1. Retrieves the product and job from database
    2. Runs the ProductAnalyzerAgent
    3. Updates product.structured_product_data with results
    4. Creates a ProductAnalysisHistory record
    5. Updates job status throughout

    Args:
        job_id: QueueJob ID to process

    Returns:
        Dictionary with analysis results
    """
    db = None
    try:
        db = get_db()
        queue_service = QueueService(db)

        # Mark job as running
        job = queue_service.mark_running(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        # Get input data
        input_data = job.input_data or {}
        product_id = job.product_id
        user_id = job.user_id

        if not product_id:
            raise ValueError("Product ID is required")

        # Update progress
        queue_service.update_progress(job_id, 10.0, "Loading product data...")

        # Get product
        product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
        if not product:
            raise ValueError(f"Product {product_id} not found")

        # Update progress
        queue_service.update_progress(job_id, 20.0, "Initializing product analyzer...")

        # Create LLM service and agent
        llm_service = LLMService()
        agent = ProductAnalyzerAgent(
            db=db,
            llm_service=llm_service,
            product_id=product_id
        )

        # Build input for agent
        agent_input = {
            'product_name': input_data.get('product_name') or product.product_name,
            'product_description': input_data.get('product_description') or product.product_description,
            'source_type': input_data.get('source_type') or product.product_source_type or 'text',
        }

        # Update progress
        queue_service.update_progress(job_id, 30.0, "Running AI analysis...")

        # Execute agent
        result = agent.execute(agent_input)

        # Update progress
        queue_service.update_progress(job_id, 70.0, "Saving analysis results...")

        # Update product with structured data
        product.structured_product_data = result
        product.product_category = result.get('product_category', product.product_category)
        product.analysis_version = (product.analysis_version or 0) + 1
        product.last_analyzed_at = datetime.utcnow()
        product.last_analyzed_by_user_id = user_id
        product.analysis_count = (product.analysis_count or 0) + 1

        # Create analysis history record
        history = ProductAnalysisHistory(
            product_id=product_id,
            analysis_version=product.analysis_version,
            analyzed_by_user_id=user_id,
            product_description=product.product_description,
            product_source_type=product.product_source_type or 'text',
            product_source_data=product.product_source_data,
            analyzed_structure=result,
        )
        db.add(history)
        db.flush()  # Get the history.id

        # Store detailed features
        detailed_features = result.get('detailed_features', [])
        for feat in detailed_features:
            product_feature = ProductFeature(
                product_id=product_id,
                analysis_history_id=history.id,
                analysis_version=product.analysis_version,
                feature_name=feat.get('name', ''),
                feature_description=feat.get('description', ''),
                feature_category=feat.get('category', ''),
                extraction_confidence=feat.get('confidence', 0.0),
                source_reference=feat.get('source_reference', ''),
            )
            db.add(product_feature)

        db.commit()

        # Update progress
        queue_service.update_progress(job_id, 90.0, "Finalizing...")

        # Prepare output data
        output_data = {
            'product_id': product_id,
            'analysis_version': product.analysis_version,
            'product_name': result.get('product_name'),
            'product_category': result.get('product_category'),
            'core_features_count': len(result.get('core_features', [])),
            'detailed_features_count': len(detailed_features),
            'competitor_keywords': result.get('competitor_search_keywords', []),
        }

        # Mark job as success
        queue_service.mark_success(job_id, output_data)

        return output_data

    except Exception as e:
        # Mark job as failed
        error_msg = str(e)
        error_tb = traceback.format_exc()
        print(f"[analyze_product_task] Error: {error_msg}")
        print(f"[analyze_product_task] Traceback: {error_tb}")

        if db:
            try:
                queue_service = QueueService(db)
                queue_service.mark_failure(job_id, error_msg, error_tb)
            except Exception as inner_e:
                print(f"[analyze_product_task] Failed to update job status: {inner_e}")

        raise

    finally:
        if db:
            db.close()


@shared_task(bind=True, name='app.queue.tasks.health_check')
def health_check(self) -> Dict[str, Any]:
    """
    Simple health check task for testing Celery connectivity.

    Returns:
        Dictionary with status and timestamp
    """
    return {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'worker': self.request.hostname if self.request else 'unknown',
    }


@shared_task(bind=True, name='app.queue.tasks.discover_competitors_task')
def discover_competitors_task(self, job_id: int) -> Dict[str, Any]:
    """
    Background task to discover competitors using CompetitorResearcherAgent.

    This task:
    1. Retrieves product analysis data
    2. Runs CompetitorResearcherAgent
    3. Stores discovered competitors in ProductCompetitor table
    4. Returns competitor IDs for feature extraction

    Args:
        job_id: QueueJob ID to process

    Returns:
        Dictionary with discovered competitor IDs
    """
    db = None
    try:
        db = get_db()
        queue_service = QueueService(db)

        # Mark job as running
        job = queue_service.mark_running(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        product_id = job.product_id
        user_id = job.user_id

        if not product_id:
            raise ValueError("Product ID is required")

        # Update progress
        queue_service.update_progress(job_id, 10.0, "Loading product data...")

        # Get product with analysis data
        product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
        if not product:
            raise ValueError(f"Product {product_id} not found")

        if not product.structured_product_data:
            raise ValueError(f"Product {product_id} has not been analyzed yet")

        # Update progress
        queue_service.update_progress(job_id, 20.0, "Initializing competitor researcher...")

        # Create LLM service and agent
        llm_service = LLMService()
        agent = CompetitorResearcherAgent(
            db=db,
            llm_service=llm_service,
            product_id=product_id
        )

        # Build input from product analysis
        analysis = product.structured_product_data
        agent_input = {
            'product_name': product.product_name,
            'product_category': analysis.get('product_category', ''),
            'core_features': analysis.get('core_features', []),
            'target_users': analysis.get('target_users', ''),
            'competitor_search_keywords': analysis.get('competitor_search_keywords', []),
        }

        # Update progress
        queue_service.update_progress(job_id, 30.0, "Discovering competitors...")

        # Execute agent
        result = agent.execute(agent_input)

        # Update progress
        queue_service.update_progress(job_id, 70.0, "Storing competitors...")

        # Store discovered competitors
        competitors = result.get('competitors', [])
        competitor_ids = []

        for comp_data in competitors:
            # Check if competitor already exists for this product
            existing = db.query(ProductCompetitor).filter(
                ProductCompetitor.product_id == product_id,
                ProductCompetitor.competitor_name == comp_data.get('name')
            ).first()

            if existing:
                # Update existing competitor
                existing.competitor_url = comp_data.get('url', existing.competitor_url)
                existing.status = 'active'
                competitor_ids.append(existing.id)
            else:
                # Create new competitor
                new_competitor = ProductCompetitor(
                    product_id=product_id,
                    competitor_name=comp_data.get('name'),
                    competitor_url=comp_data.get('url'),
                    first_discovered_session_id=None,  # Queue-based, no session
                    status='active'
                )
                db.add(new_competitor)
                db.flush()
                competitor_ids.append(new_competitor.id)

        db.commit()

        # Update progress
        queue_service.update_progress(job_id, 90.0, "Finalizing...")

        # Prepare output data
        output_data = {
            'product_id': product_id,
            'competitors_discovered': len(competitors),
            'competitor_ids': competitor_ids,
            'research_summary': result.get('research_summary', ''),
        }

        # Mark job as success
        queue_service.mark_success(job_id, output_data)

        return output_data

    except Exception as e:
        error_msg = str(e)
        error_tb = traceback.format_exc()
        print(f"[discover_competitors_task] Error: {error_msg}")
        print(f"[discover_competitors_task] Traceback: {error_tb}")

        if db:
            try:
                queue_service = QueueService(db)
                queue_service.mark_failure(job_id, error_msg, error_tb)
            except Exception as inner_e:
                print(f"[discover_competitors_task] Failed to update job status: {inner_e}")

        raise

    finally:
        if db:
            db.close()


@shared_task(bind=True, name='app.queue.tasks.extract_features_task')
def extract_features_task(self, job_id: int) -> Dict[str, Any]:
    """
    Background task to extract features from a single competitor.

    This task:
    1. Gets competitor info
    2. Runs FeatureExtractorAgent
    3. Stores features in ProductCompetitorFeature table

    Args:
        job_id: QueueJob ID to process

    Returns:
        Dictionary with extraction results
    """
    db = None
    try:
        db = get_db()
        queue_service = QueueService(db)

        # Mark job as running
        job = queue_service.mark_running(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        input_data = job.input_data or {}
        competitor_id = input_data.get('competitor_id')
        product_id = job.product_id

        if not competitor_id:
            raise ValueError("Competitor ID is required")

        # Update progress
        queue_service.update_progress(job_id, 10.0, "Loading competitor data...")

        # Get competitor
        competitor = db.query(ProductCompetitor).filter(
            ProductCompetitor.id == competitor_id
        ).first()

        if not competitor:
            raise ValueError(f"Competitor {competitor_id} not found")

        # Check for previous features (for comparative analysis)
        previous_features = []
        existing_features = db.query(ProductCompetitorFeature).filter(
            ProductCompetitorFeature.product_competitor_id == competitor_id,
            ProductCompetitorFeature.status == 'active'
        ).all()

        if existing_features:
            previous_features = [
                {
                    'id': str(f.id),
                    'name': f.feature_name,
                    'description': f.feature_description,
                    'category': f.feature_category,
                }
                for f in existing_features
            ]

        # Update progress
        queue_service.update_progress(job_id, 20.0, "Initializing feature extractor...")

        # Create LLM service and agent
        llm_service = LLMService()
        agent = FeatureExtractorAgent(
            db=db,
            llm_service=llm_service,
            product_id=product_id
        )

        # Build input
        agent_input = {
            'competitor_name': competitor.competitor_name,
            'competitor_url': competitor.competitor_url,
        }

        if previous_features:
            agent_input['previous_features'] = previous_features

        # Update progress
        queue_service.update_progress(job_id, 30.0, f"Extracting features from {competitor.competitor_name}...")

        # Execute agent
        result = agent.execute(agent_input)

        # Update progress
        queue_service.update_progress(job_id, 70.0, "Storing features...")

        # Store extracted features
        features = result.get('features', [])
        feature_count = 0
        new_features = []  # Track newly created features for embedding

        for feat_data in features:
            change_type = feat_data.get('change_type', 'new')

            if change_type == 'removed':
                # Mark as inactive
                prev_id = feat_data.get('previous_feature_id')
                if prev_id:
                    try:
                        prev_feature = db.query(ProductCompetitorFeature).filter(
                            ProductCompetitorFeature.id == int(prev_id)
                        ).first()
                        if prev_feature:
                            prev_feature.status = 'removed'
                    except (ValueError, TypeError):
                        pass
            else:
                # Create or update feature
                feature = ProductCompetitorFeature(
                    product_competitor_id=competitor_id,
                    feature_name=feat_data.get('name', ''),
                    feature_description=feat_data.get('description', ''),
                    feature_category=feat_data.get('category', ''),
                    first_discovered_session_id=None,  # Queue-based
                    status='active'
                )
                db.add(feature)
                db.flush()  # Get feature.id
                new_features.append(feature)
                feature_count += 1

        db.commit()

        # Store embeddings for new features (for vector similarity search)
        try:
            from app.services.similarity_detector import SimilarityDetectorService
            similarity_service = SimilarityDetectorService(db)
            for feature in new_features:
                feature_text = f"{feature.feature_name}\n{feature.feature_description or ''}"
                similarity_service.store_competitor_feature_embedding(feature.id, feature_text)
            db.commit()
            print(f"[extract_features_task] Stored embeddings for {len(new_features)} features")
        except Exception as embed_error:
            print(f"[extract_features_task] Warning: Failed to store embeddings: {embed_error}")

        # Update progress
        queue_service.update_progress(job_id, 90.0, "Finalizing...")

        # Prepare output data
        output_data = {
            'competitor_id': competitor_id,
            'competitor_name': competitor.competitor_name,
            'features_extracted': feature_count,
            'extraction_summary': result.get('extraction_summary', ''),
            'analysis_mode': result.get('analysis_mode', 'fresh'),
        }

        # Add summary if comparative
        if 'summary' in result:
            output_data['change_summary'] = result['summary']

        # Mark job as success
        queue_service.mark_success(job_id, output_data)

        return output_data

    except Exception as e:
        error_msg = str(e)
        error_tb = traceback.format_exc()
        print(f"[extract_features_task] Error: {error_msg}")
        print(f"[extract_features_task] Traceback: {error_tb}")

        if db:
            try:
                queue_service = QueueService(db)
                queue_service.mark_failure(job_id, error_msg, error_tb)
            except Exception as inner_e:
                print(f"[extract_features_task] Failed to update job status: {inner_e}")

        raise

    finally:
        if db:
            db.close()


@shared_task(bind=True, name='app.queue.tasks.extract_features_parallel')
def extract_features_parallel(self, job_id: int, competitor_ids: List[int]) -> Dict[str, Any]:
    """
    Orchestrates parallel feature extraction for multiple competitors.

    Uses Celery chord to dispatch child tasks in parallel and aggregate results
    via a callback task. This avoids the anti-pattern of calling .get() within a task.

    Args:
        job_id: Parent QueueJob ID
        competitor_ids: List of competitor IDs to process

    Returns:
        Dictionary indicating chord was dispatched
    """
    from celery import chord

    db = None
    try:
        db = get_db()
        queue_service = QueueService(db)

        # Mark parent job as running
        job = queue_service.mark_running(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        product_id = job.product_id

        # Update progress
        queue_service.update_progress(
            job_id, 10.0,
            f"Creating extraction jobs for {len(competitor_ids)} competitors..."
        )

        # Create child jobs for each competitor
        child_job_ids = []
        for comp_id in competitor_ids:
            child_job = queue_service.create_job(
                job_type=JobType.FEATURE_EXTRACTION,
                input_data={'competitor_id': comp_id},
                product_id=product_id,
                user_id=job.user_id,
                parent_job_id=job_id,
            )
            child_job_ids.append(child_job.id)

        db.commit()

        # Update progress
        queue_service.update_progress(
            job_id, 20.0,
            f"Dispatching {len(child_job_ids)} parallel extraction tasks..."
        )

        # Use chord: group of extraction tasks -> callback to aggregate
        extraction_chord = chord(
            [extract_features_task.s(child_id) for child_id in child_job_ids],
            aggregate_extraction_results.s(job_id, child_job_ids)
        )

        # Dispatch the chord
        chord_result = extraction_chord.apply_async()

        # Mark child jobs as queued (best effort)
        db.commit()

        # Return immediately - the callback will handle completion
        return {
            'status': 'chord_dispatched',
            'parent_job_id': job_id,
            'child_job_ids': child_job_ids,
            'chord_id': chord_result.id if chord_result else None,
        }

    except Exception as e:
        error_msg = str(e)
        error_tb = traceback.format_exc()
        print(f"[extract_features_parallel] Error: {error_msg}")

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


@shared_task(bind=True, name='app.queue.tasks.aggregate_extraction_results')
def aggregate_extraction_results(self, results: List[Dict], parent_job_id: int, child_job_ids: List[int]) -> Dict[str, Any]:
    """
    Callback task to aggregate results from parallel feature extraction.

    Called automatically by Celery chord after all extraction tasks complete.

    Args:
        results: List of results from each extraction task
        parent_job_id: Parent QueueJob ID to update
        child_job_ids: List of child job IDs that were processed

    Returns:
        Aggregated results
    """
    db = None
    try:
        db = get_db()
        queue_service = QueueService(db)

        # Get parent job
        job = queue_service.get_job(parent_job_id)
        if not job:
            raise ValueError(f"Parent job {parent_job_id} not found")

        # Aggregate results
        total_features = 0
        successful = 0
        for r in results:
            if r:
                total_features += r.get('features_extracted', 0)
                successful += 1

        output_data = {
            'product_id': job.product_id,
            'competitors_processed': len(child_job_ids),
            'successful_extractions': successful,
            'total_features_extracted': total_features,
            'child_job_ids': child_job_ids,
        }

        # Mark parent job as success
        queue_service.mark_success(parent_job_id, output_data)

        return output_data

    except Exception as e:
        error_msg = str(e)
        error_tb = traceback.format_exc()
        print(f"[aggregate_extraction_results] Error: {error_msg}")

        if db:
            try:
                queue_service = QueueService(db)
                queue_service.mark_failure(parent_job_id, error_msg, error_tb)
            except Exception:
                pass

        raise

    finally:
        if db:
            db.close()


# ============================================================================
# Phase 3: Idea Normalization and Triage Tasks
# ============================================================================

@shared_task(bind=True, name='app.queue.tasks.normalize_idea_task')
def normalize_idea_task(self, job_id: int) -> Dict[str, Any]:
    """
    Background task to normalize an idea from any source.

    This task:
    1. Retrieves the job and input data
    2. Determines source type
    3. Uses appropriate adapter to normalize
    4. Creates Idea record
    5. Optionally chains to triage task

    Args:
        job_id: QueueJob ID

    Returns:
        Dictionary with idea_id and normalization details
    """
    from app.services.idea_normalizer_service import IdeaNormalizerService
    from app.models.idea import SourceType, TriageStatus

    db = None
    try:
        db = get_db()
        queue_service = QueueService(db)
        llm_service = LLMService()

        # Mark job as running
        job = queue_service.mark_running(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        # Get input data
        input_data = job.input_data or {}
        raw_input = input_data.get('raw_input', {})
        source_type_str = input_data.get('source_type')
        chain_triage = input_data.get('chain_triage', True)

        # Parse source type if provided
        source_type = None
        if source_type_str:
            source_type = SourceType(source_type_str)

        # Update progress
        queue_service.update_progress(job_id, 20.0, "Normalizing idea...")

        # Normalize the idea
        normalizer = IdeaNormalizerService(db, llm_service)
        normalized = normalizer.normalize(raw_input, source_type)

        # Update progress
        queue_service.update_progress(job_id, 60.0, "Creating idea record...")

        # Create the idea
        idea = normalizer.create_idea_from_normalized(
            normalized,
            triage_status=TriageStatus.PENDING
        )
        db.add(idea)
        db.commit()
        db.refresh(idea)

        # Output data
        output_data = {
            'idea_id': idea.id,
            'title': idea.title,
            'source_type': idea.source_type.value,
            'category': idea.category,
            'auto_categorized': idea.auto_categorized,
        }

        # Chain to triage if requested
        if chain_triage:
            queue_service.update_progress(job_id, 80.0, "Queueing triage task...")

            # Create triage job
            triage_job = queue_service.create_job(
                job_type=JobType.IDEA_TRIAGE,
                input_data={'idea_id': idea.id},
                product_id=idea.product_id,
                user_id=job.user_id,
                parent_job_id=job.parent_job_id or job.id,
            )
            db.commit()

            # Queue the triage task
            triage_idea_task.delay(triage_job.id)

            output_data['triage_job_id'] = triage_job.id
            output_data['triage_job_uuid'] = triage_job.job_uuid

        # Mark success
        queue_service.mark_success(job_id, output_data)

        return output_data

    except Exception as e:
        error_msg = str(e)
        error_tb = traceback.format_exc()
        print(f"[normalize_idea_task] Error: {error_msg}")

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


@shared_task(bind=True, name='app.queue.tasks.triage_idea_task')
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
    from app.models.idea import Idea, TriageStatus, TriageAction
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

        # Find competitive matches (returns structured dict with matches and urgency)
        competitive_context = similarity_service.find_competitive_matches(
            idea_text=idea_text,
            product_id=idea.product_id,
            limit=5
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
        }

        # Run triage agent
        agent = IdeaTriageAgent(
            db=db,
            llm_service=llm_service,
            product_id=idea.product_id
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

        # Determine triage status (only auto-approves if auto-respond is enabled)
        triage_status_str = agent.determine_triage_status(
            triage_result,
            auto_respond_enabled=auto_respond_enabled,
            auto_respond_threshold=auto_respond_threshold
        )
        triage_status = TriageStatus(triage_status_str)

        # Map recommendation action to TriageAction enum
        recommendation = triage_result.get('recommendation', {})
        action_str = recommendation.get('action', 'review')
        try:
            triage_action = TriageAction(action_str)
        except ValueError:
            triage_action = TriageAction.REVIEW

        # Update idea with triage results
        idea.triage_status = triage_status
        idea.triage_confidence = recommendation.get('confidence', 0.5)
        idea.triage_reasoning = recommendation.get('reasoning', '')
        idea.triage_recommendation = triage_action
        idea.triage_job_id = job.id

        # Update category if provided
        if triage_result.get('category'):
            idea.category = triage_result['category']
            idea.auto_categorized = True

        # Handle duplicate detection - store duplicate info if agent recommends merge
        # This is stored regardless of auto-respond setting so PO can see the suggestion
        if triage_action == TriageAction.MERGE and similarity_result.best_match:
            idea.duplicate_of_idea_id = similarity_result.best_match.idea_id
            idea.similarity_score = similarity_result.best_match.similarity_score

        # Store competitive context
        comp_context = triage_result.get('competitive_context', {})
        if comp_context:
            idea.competitive_context = {
                'competitors_with_feature': comp_context.get('competitors_with_feature', []),
                'competitive_urgency': comp_context.get('competitive_urgency', 'low'),
            }

        # Store auto-response text (always store for PO to use, regardless of auto-respond setting)
        if triage_result.get('auto_response_text'):
            idea.auto_response_text = triage_result['auto_response_text']

        # If auto-approved, publish for voting and mark as auto-responded
        if triage_status == TriageStatus.AUTO_APPROVED:
            idea.published_for_voting = True
            idea.auto_responded = True

        # Record status history for agent triage
        # Only record as automated action if auto-respond is ON and status changed
        # When auto-respond is OFF, we don't record the agent's recommendation in history
        # (the PO's response will be recorded when they respond)
        if auto_respond_enabled:
            status_history = IdeaStatusHistory(
                idea_id=idea.id,
                previous_status=TriageStatus.PENDING,
                new_status=triage_status,
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
            'triage_status': triage_status.value,
            'triage_confidence': idea.triage_confidence,
            'triage_recommendation': triage_action.value,
            'category': idea.category,
            'has_duplicates': similarity_result.has_duplicates,
            'has_similar': similarity_result.has_similar,
            'similar_count': len(similarity_result.similar_ideas),
            'duplicate_of_idea_id': idea.duplicate_of_idea_id,
            'competitors_with_feature': comp_context.get('competitors_with_feature', []),
            'auto_response_generated': bool(idea.auto_response_text),
            'published_for_voting': idea.published_for_voting,
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


@shared_task(bind=True, name='app.queue.tasks.submit_and_triage_idea_task')
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
    from app.models.idea import Idea, TriageStatus, TriageAction, SourceType
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
        idea = normalizer.create_idea_from_normalized(normalized, TriageStatus.PENDING)
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

        # Step 4: Competitive matches (returns structured dict with matches and urgency)
        queue_service.update_progress(job_id, 55.0, "Finding competitive matches...")
        competitive_context = similarity_service.find_competitive_matches(
            idea_text=idea_text,
            product_id=idea.product_id,
            limit=5
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
        }

        agent = IdeaTriageAgent(
            db=db,
            llm_service=llm_service,
            product_id=idea.product_id
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

        # Determine triage status (only auto-approves if auto-respond is enabled)
        triage_status_str = agent.determine_triage_status(
            triage_result,
            auto_respond_enabled=auto_respond_enabled,
            auto_respond_threshold=auto_respond_threshold
        )
        triage_status = TriageStatus(triage_status_str)

        recommendation = triage_result.get('recommendation', {})
        action_str = recommendation.get('action', 'review')
        try:
            triage_action = TriageAction(action_str)
        except ValueError:
            triage_action = TriageAction.REVIEW

        idea.triage_status = triage_status
        idea.triage_confidence = recommendation.get('confidence', 0.5)
        idea.triage_reasoning = recommendation.get('reasoning', '')
        idea.triage_recommendation = triage_action
        idea.triage_job_id = job.id

        if triage_result.get('category'):
            idea.category = triage_result['category']
            idea.auto_categorized = True

        # Handle duplicate detection - store duplicate info if agent recommends merge
        # This is stored regardless of auto-respond setting so PO can see the suggestion
        if triage_action == TriageAction.MERGE and similarity_result.best_match:
            idea.duplicate_of_idea_id = similarity_result.best_match.idea_id
            idea.similarity_score = similarity_result.best_match.similarity_score

        comp_context = triage_result.get('competitive_context', {})
        if comp_context:
            idea.competitive_context = {
                'competitors_with_feature': comp_context.get('competitors_with_feature', []),
                'competitive_urgency': comp_context.get('competitive_urgency', 'low'),
            }

        # Store auto-response text (always store for PO to use, regardless of auto-respond setting)
        if triage_result.get('auto_response_text'):
            idea.auto_response_text = triage_result['auto_response_text']

        # If auto-approved, publish for voting and mark as auto-responded
        if triage_status == TriageStatus.AUTO_APPROVED:
            idea.published_for_voting = True
            idea.auto_responded = True

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
            'triage_status': triage_status.value,
            'triage_confidence': idea.triage_confidence,
            'triage_recommendation': triage_action.value,
            'has_duplicates': similarity_result.has_duplicates,
            'has_similar': similarity_result.has_similar,
            'duplicate_of_idea_id': idea.duplicate_of_idea_id,
            'competitors_with_feature': comp_context.get('competitors_with_feature', []),
            'auto_response_text': idea.auto_response_text,
            'published_for_voting': idea.published_for_voting,
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


# ============================================================================
# Phase 4: Competitive Monitoring Tasks
# ============================================================================

@shared_task(bind=True, name='app.queue.tasks.monitor_competitors_task')
def monitor_competitors_task(self, job_id: int, product_id: int, force_full: bool = False) -> Dict[str, Any]:
    """
    Background task to monitor competitors for changes.

    This task:
    1. Gets all competitors for the product
    2. For each competitor:
       - Extracts current features
       - Creates a snapshot
       - Compares with previous snapshot
       - Detects changes
    3. Generates alerts for significant changes
    4. Updates monitoring config timestamps

    Args:
        job_id: QueueJob ID
        product_id: Product ID to monitor
        force_full: If True, perform full re-extraction instead of differential

    Returns:
        Dictionary with monitoring results
    """
    from app.services.competitive_monitor_service import CompetitiveMonitorService

    db = None
    try:
        db = get_db()
        queue_service = QueueService(db)

        # Mark job as running
        job = queue_service.mark_running(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        # Update progress
        queue_service.update_progress(job_id, 10.0, "Initializing competitive monitoring...")

        # Run monitoring
        monitor_service = CompetitiveMonitorService(db)
        result = monitor_service.run_monitoring(
            product_id=product_id,
            job_id=job_id,
            force_full=force_full,
            progress_callback=lambda pct, msg: queue_service.update_progress(job_id, pct, msg)
        )

        # Mark success
        queue_service.mark_success(job_id, result)

        return result

    except Exception as e:
        error_msg = str(e)
        error_tb = traceback.format_exc()
        print(f"[monitor_competitors_task] Error: {error_msg}")

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


@shared_task(bind=True, name='app.queue.tasks.scheduled_monitoring_task')
def scheduled_monitoring_task(self) -> Dict[str, Any]:
    """
    Scheduled task that runs monitoring for all products due for monitoring.

    Called by Celery Beat on a schedule (e.g., daily).
    Checks monitoring configs and runs monitoring for products that are due.

    Returns:
        Dictionary with list of products monitored
    """
    db = None
    try:
        db = get_db()
        queue_service = QueueService(db)

        from app.services.pm_review_service import PMReviewService
        from app.models.queue import JobType, JobStatus

        pm_service = PMReviewService(db)

        # Get products due for monitoring
        configs = pm_service.get_products_due_for_monitoring()

        products_monitored = []
        jobs_created = []

        for config in configs:
            try:
                # Create a job for each product
                job = queue_service.create_job(
                    job_type=JobType.COMPETITIVE_MONITORING,
                    input_data={
                        'product_id': config.product_id,
                        'triggered_by': 'scheduled',
                    },
                    product_id=config.product_id,
                    user_id=None,  # System-triggered
                )
                db.commit()

                # Queue the monitoring task
                result = monitor_competitors_task.delay(
                    job_id=job.id,
                    product_id=config.product_id,
                    force_full=False
                )

                job.celery_task_id = result.id
                job.status = JobStatus.QUEUED
                db.commit()

                products_monitored.append(config.product_id)
                jobs_created.append(job.job_uuid)

            except Exception as e:
                print(f"[scheduled_monitoring_task] Error scheduling product {config.product_id}: {e}")

        return {
            'products_monitored': products_monitored,
            'jobs_created': jobs_created,
            'total': len(products_monitored),
        }

    except Exception as e:
        error_msg = str(e)
        print(f"[scheduled_monitoring_task] Error: {error_msg}")
        raise

    finally:
        if db:
            db.close()


# Note: triage_existing_idea_task was removed as it was redundant with triage_idea_task.
# Use triage_idea_task for triaging existing ideas.