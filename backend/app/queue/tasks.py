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
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models.queue import JobStatus, JobType
from app.models.competitor_intelligence import (
    CIProduct, ProductAnalysisHistory, ProductFeature,
    ProductCompetitor, ProductCompetitorFeature, SessionCompetitor, CompetitorFeature
)
from app.models.competitive_reports import CompetitorAlert
from app.models.competitive_agent import CompetitiveAgentConfig
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

        # Get agent config to check alert settings
        agent_config = db.query(CompetitiveAgentConfig).filter(
            CompetitiveAgentConfig.product_id == product_id
        ).first()
        alert_on_new = agent_config.alert_on_new_competitors if agent_config else False

        # Store discovered competitors
        competitors = result.get('competitors', [])
        competitor_ids = []
        new_competitor_names = []  # Track newly discovered competitors for alerts

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
                new_competitor_names.append({
                    'id': new_competitor.id,
                    'name': new_competitor.competitor_name
                })

        # Create alerts for newly discovered competitors
        if alert_on_new and new_competitor_names:
            for comp in new_competitor_names:
                alert = CompetitorAlert(
                    product_id=product_id,
                    alert_type='new_competitor',
                    competitor_id=comp['id'],
                    competitor_name=comp['name'],
                    message=f"New competitor discovered: {comp['name']}",
                    is_read=False
                )
                db.add(alert)

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
    from app.models.idea import SourceType, IdeaStatus

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
            status=IdeaStatus.PENDING
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

        # Find competitive matches (returns structured dict with matches and urgency)
        competitive_context = similarity_service.find_competitive_matches(
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
            }
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

        # Apply existing feature fallback BEFORE status determination
        # If agent didn't populate existing_feature_info but we detected a match, use the detected match
        if not triage_result.get('existing_feature_info') and product_feature_result.has_match and product_feature_result.best_match:
            triage_result['existing_feature_info'] = {
                'feature_name': product_feature_result.best_match.feature_name,
                'feature_description': product_feature_result.best_match.feature_description,
                'similarity_score': product_feature_result.best_match.similarity_score,
                'source_url': product_feature_result.best_match.source_url,
            }

        # Determine status (only auto-approves if auto-respond is enabled)
        # Returns IdeaStatus enum directly
        new_status = agent.determine_triage_status(
            triage_result,
            auto_respond_enabled=auto_respond_enabled,
            auto_respond_threshold=auto_respond_threshold
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

        # Store competitive context
        comp_context = triage_result.get('competitive_context', {})
        competitors_with_feature = comp_context.get('competitors_with_feature', [])

        # For competitor-sourced ideas, ensure source competitors are included in the list
        if is_competitor_idea and idea.source_metadata:
            # Support both singular 'competitor_name' and plural 'competitor_names' for cluster-based ideas
            source_competitor_names = idea.source_metadata.get('competitor_names', [])
            if not source_competitor_names:
                # Fallback to singular for backwards compatibility
                single_name = idea.source_metadata.get('competitor_name')
                if single_name:
                    source_competitor_names = [single_name]

            # Add source competitors that aren't already in the list
            for name in source_competitor_names:
                if name and name not in competitors_with_feature:
                    competitors_with_feature.append(name)

        if comp_context or competitors_with_feature:
            idea.competitive_context = {
                'competitors_with_feature': competitors_with_feature,
                'competitive_urgency': comp_context.get('competitive_urgency', 'medium' if is_competitor_idea else 'low'),
            }

        # Store existing feature info if detected (feature exists case)
        # Note: Fallback was already applied before status determination above
        existing_feature_info = triage_result.get('existing_feature_info')
        if existing_feature_info:
            idea.competitive_context = idea.competitive_context or {}
            idea.competitive_context['existing_feature'] = existing_feature_info

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

        # Step 4: Competitive matches (returns structured dict with matches and urgency)
        queue_service.update_progress(job_id, 55.0, "Finding competitive matches...")
        competitive_context = similarity_service.find_competitive_matches(
            idea_text=idea_text,
            product_id=idea.product_id,
            limit=5
        )

        # Step 4b: Check if idea matches existing product features ("Feature Exists" detection)
        queue_service.update_progress(job_id, 60.0, "Checking for existing product features...")
        product_feature_result = similarity_service.find_product_feature_matches(
            idea_text=idea_text,
            product_id=idea.product_id,
            threshold=0.80
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

        # Apply existing feature fallback BEFORE status determination
        # If agent didn't populate existing_feature_info but we detected a match, use the detected match
        if not triage_result.get('existing_feature_info') and product_feature_result.has_match and product_feature_result.best_match:
            triage_result['existing_feature_info'] = {
                'feature_name': product_feature_result.best_match.feature_name,
                'feature_description': product_feature_result.best_match.feature_description,
                'similarity_score': product_feature_result.best_match.similarity_score,
                'source_url': product_feature_result.best_match.source_url,
            }

        # Determine status (only auto-approves if auto-respond is enabled)
        # Returns IdeaStatus enum directly
        new_status = agent.determine_triage_status(
            triage_result,
            auto_respond_enabled=auto_respond_enabled,
            auto_respond_threshold=auto_respond_threshold
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

        # Store existing feature info if detected (feature exists case)
        existing_feature_info = triage_result.get('existing_feature_info')
        if existing_feature_info:
            idea.competitive_context = idea.competitive_context or {}
            idea.competitive_context['existing_feature'] = existing_feature_info

        # Store auto-response text (always store for PO to use, regardless of auto-respond setting)
        if triage_result.get('auto_response_text'):
            idea.auto_response_text = triage_result['auto_response_text']

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


# ============================================================================
# Scheduled Execution Tasks (Chunk 7)
# ============================================================================

def _calculate_next_run(schedule: str) -> datetime:
    """
    Calculate the next run time based on schedule frequency.

    Args:
        schedule: One of 'daily', 'weekly', 'biweekly', 'monthly'

    Returns:
        Next run datetime (UTC)
    """
    now = datetime.utcnow()
    if schedule == 'daily':
        return now + timedelta(days=1)
    elif schedule == 'weekly':
        return now + timedelta(weeks=1)
    elif schedule == 'biweekly':
        return now + timedelta(weeks=2)
    elif schedule == 'monthly':
        return now + timedelta(days=30)
    else:
        # Default to weekly
        return now + timedelta(weeks=1)


@shared_task(bind=True, name='app.queue.tasks.check_scheduled_tasks')
def check_scheduled_tasks(self) -> Dict[str, Any]:
    """
    Master scheduler task - runs hourly via Celery Beat.

    Checks CompetitiveAgentConfig for each product and queues work if due:
    - Product analysis (if scheduled mode and next_run <= now)
    - Competitor discovery (if scheduled mode and next_run <= now)
    - Deep analysis (if scheduled mode and next_run <= now)

    Returns:
        Dictionary with queued jobs summary
    """
    from app.models.competitive_agent import CompetitiveAgentConfig, AgentMode

    db = None
    try:
        db = get_db()
        queue_service = QueueService(db)
        now = datetime.utcnow()

        jobs_queued = {
            'product_analysis': [],
            'competitor_discovery': [],
            'deep_analysis': [],
        }

        # Get all enabled configs
        configs = db.query(CompetitiveAgentConfig).filter(
            CompetitiveAgentConfig.enabled == True
        ).all()

        print(f"[check_scheduled_tasks] Checking {len(configs)} products for scheduled tasks...")

        for config in configs:
            try:
                product_id = config.product_id

                # Check Product Analysis
                if (config.product_analysis_mode == AgentMode.SCHEDULED
                        and config.product_analysis_next_run
                        and config.product_analysis_next_run <= now):
                    print(f"[check_scheduled_tasks] Product {product_id}: Product analysis due")
                    job = queue_service.create_job(
                        job_type=JobType.PRODUCT_ANALYSIS,
                        input_data={'product_id': product_id, 'scheduled': True},
                        product_id=product_id,
                        user_id=None  # System scheduled
                    )
                    db.commit()

                    # Queue the task
                    analyze_product_task.delay(job.id)

                    # Update next run time
                    config.product_analysis_last_run = now
                    config.product_analysis_next_run = _calculate_next_run(
                        config.product_analysis_schedule or 'weekly'
                    )
                    db.commit()

                    jobs_queued['product_analysis'].append({
                        'product_id': product_id,
                        'job_id': job.id
                    })

                # Check Competitor Discovery
                if (config.competitor_discovery_mode == AgentMode.SCHEDULED
                        and config.competitor_discovery_next_run
                        and config.competitor_discovery_next_run <= now):
                    print(f"[check_scheduled_tasks] Product {product_id}: Competitor discovery due")
                    job = queue_service.create_job(
                        job_type=JobType.COMPETITOR_DISCOVERY,
                        input_data={'product_id': product_id, 'scheduled': True},
                        product_id=product_id,
                        user_id=None
                    )
                    db.commit()

                    discover_competitors_task.delay(job.id)

                    config.competitor_discovery_last_run = now
                    config.competitor_discovery_next_run = _calculate_next_run(
                        config.competitor_discovery_schedule or 'weekly'
                    )
                    db.commit()

                    jobs_queued['competitor_discovery'].append({
                        'product_id': product_id,
                        'job_id': job.id
                    })

                # Check Deep Analysis
                if (config.deep_analysis_mode == AgentMode.SCHEDULED
                        and config.deep_analysis_next_run
                        and config.deep_analysis_next_run <= now):
                    print(f"[check_scheduled_tasks] Product {product_id}: Deep analysis due")
                    job = queue_service.create_job(
                        job_type=JobType.SCHEDULED_DEEP_ANALYSIS,
                        input_data={'product_id': product_id, 'scheduled': True},
                        product_id=product_id,
                        user_id=None
                    )
                    db.commit()

                    scheduled_deep_analysis_task.delay(job.id)

                    config.deep_analysis_last_run = now
                    config.deep_analysis_next_run = _calculate_next_run(
                        config.deep_analysis_schedule or 'weekly'
                    )
                    db.commit()

                    jobs_queued['deep_analysis'].append({
                        'product_id': product_id,
                        'job_id': job.id
                    })

            except Exception as e:
                print(f"[check_scheduled_tasks] Error processing product {config.product_id}: {e}")
                continue

        total_queued = sum(len(v) for v in jobs_queued.values())
        print(f"[check_scheduled_tasks] Queued {total_queued} jobs across {len(configs)} products")

        return {
            'products_checked': len(configs),
            'jobs_queued': jobs_queued,
            'total_jobs': total_queued,
            'checked_at': now.isoformat()
        }

    except Exception as e:
        error_msg = str(e)
        print(f"[check_scheduled_tasks] Error: {error_msg}")
        raise

    finally:
        if db:
            db.close()


# ============================================================================
# Agent-Centric Architecture Tasks (Chunk 5)
# ============================================================================

@shared_task(bind=True, name='app.queue.tasks.deep_analysis_task')
def deep_analysis_task(self, job_id: int) -> Dict[str, Any]:
    """
    DEPRECATED: This task is deprecated in V2.
    Use functional_audit_task and landscape_synthesis_task instead.

    This task now returns a deprecation error.
    """
    from app.models.competitive_agent import CompetitiveAgentConfig

    # DEPRECATED: Strategic analysis models have been removed in V2
    # Return a deprecation error immediately
    db = None
    try:
        db = get_db()
        queue_service = QueueService(db)
        queue_service.mark_failure(
            job_id,
            "DEPRECATED: deep_analysis_task is no longer supported. Use functional_audit_task instead.",
            None
        )
        return {
            'status': 'deprecated',
            'message': 'This task is deprecated. Use V2 functional audit workflow instead.'
        }
    except Exception as e:
        print(f"[deep_analysis_task] Deprecation error: {e}")
        raise
    finally:
        if db:
            db.close()


# NOTE: The old deep_analysis_task implementation has been removed.
# Strategic analysis models (pricing, positioning, momentum, changes, financials)
# have been deprecated and replaced by V2 functional audit workflow.
# See functional_audit_task and landscape_synthesis_task below.


def _run_feature_extraction(db, competitor: ProductCompetitor, product_id: int) -> Dict[str, Any]:
    """Run feature extraction for a competitor."""
    llm_service = LLMService()
    agent = FeatureExtractorAgent(
        db=db,
        llm_service=llm_service,
        product_id=product_id
    )

    agent_input = {
        'competitor_name': competitor.competitor_name,
        'competitor_url': competitor.competitor_url,
    }

    result = agent.execute(agent_input)

    # Store features
    features = result.get('features', [])
    feature_count = 0
    new_features = []

    for feat_data in features:
        feature = ProductCompetitorFeature(
            product_competitor_id=competitor.id,
            feature_name=feat_data.get('name', ''),
            feature_description=feat_data.get('description', ''),
            feature_category=feat_data.get('category', ''),
            status='active'
        )
        db.add(feature)
        db.flush()
        new_features.append(feature)
        feature_count += 1

    db.commit()

    # Store embeddings
    try:
        from app.services.similarity_detector import SimilarityDetectorService
        similarity_service = SimilarityDetectorService(db)
        for feature in new_features:
            feature_text = f"{feature.feature_name}\n{feature.feature_description or ''}"
            similarity_service.store_competitor_feature_embedding(feature.id, feature_text)
        db.commit()
    except Exception as e:
        print(f"[_run_feature_extraction] Warning: Failed to store embeddings: {e}")

    return {
        'features_extracted': feature_count,
        'extraction_summary': result.get('extraction_summary', '')
    }


# DEPRECATED: The following helper functions have been removed in V2:
# - _run_pricing_analysis
# - _run_positioning_analysis
# - _run_changes_tracking
# - _run_momentum_analysis
# - _run_financials_analysis
# These used models that no longer exist (CompetitorPricingAnalysis, etc.)
# Use functional_audit_task for the new V2 workflow.


@shared_task(bind=True, name='app.queue.tasks.feature_clustering_task')
def feature_clustering_task(self, job_id: int) -> Dict[str, Any]:
    """
    Background task to run feature clustering for a product.

    This task:
    1. Gets all competitor features with embeddings
    2. Runs agglomerative clustering
    3. Creates/updates FeatureCluster records
    4. Calculates competitive intensity

    Args:
        job_id: QueueJob ID to process

    Returns:
        Dictionary with clustering results
    """
    from app.services.feature_clustering_service import FeatureClusteringService

    db = None
    try:
        db = get_db()
        queue_service = QueueService(db)

        # Mark job as running
        job = queue_service.mark_running(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        product_id = job.product_id
        if not product_id:
            raise ValueError("Product ID is required")

        input_data = job.input_data or {}
        similarity_threshold = input_data.get('similarity_threshold', 0.75)

        # Update progress
        queue_service.update_progress(job_id, 10.0, "Initializing clustering service...")

        # Run clustering
        clustering_service = FeatureClusteringService(db)

        queue_service.update_progress(job_id, 20.0, "Running feature clustering...")
        result = clustering_service.cluster_features(
            product_id=product_id,
            similarity_threshold=similarity_threshold
        )

        # Update progress
        queue_service.update_progress(job_id, 90.0, "Finalizing...")

        output_data = {
            'product_id': product_id,
            'clusters_created': result.clusters_created,
            'clusters_updated': result.clusters_updated,
            'features_clustered': result.features_clustered,
            'high_intensity_clusters': result.high_intensity_clusters,
            'execution_time_ms': result.execution_time_ms
        }

        # Mark success
        queue_service.mark_success(job_id, output_data)

        return output_data

    except Exception as e:
        error_msg = str(e)
        error_tb = traceback.format_exc()
        print(f"[feature_clustering_task] Error: {error_msg}")

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


@shared_task(bind=True, name='app.queue.tasks.intensity_idea_generation_task')
def intensity_idea_generation_task(self, job_id: int) -> Dict[str, Any]:
    """
    Background task to generate ideas from high-intensity feature clusters.

    This task:
    1. Gets high-intensity clusters (meeting threshold)
    2. For each cluster, generates an idea using IntensityIdeaGeneratorAgent
    3. Creates Idea records with traceability to source clusters
    4. Optionally chains to triage for dedup and recommendations

    Args:
        job_id: QueueJob ID to process

    Returns:
        Dictionary with generation results
    """
    from app.services.feature_clustering_service import FeatureClusteringService

    db = None
    try:
        db = get_db()
        queue_service = QueueService(db)
        llm_service = LLMService()

        # Mark job as running
        job = queue_service.mark_running(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        product_id = job.product_id
        if not product_id:
            raise ValueError("Product ID is required")

        input_data = job.input_data or {}
        threshold = input_data.get('threshold')
        chain_triage = input_data.get('chain_triage', True)

        # Update progress
        queue_service.update_progress(job_id, 10.0, "Loading high-intensity clusters...")

        # Generate ideas
        clustering_service = FeatureClusteringService(db)

        queue_service.update_progress(job_id, 20.0, "Generating ideas from clusters...")
        results = clustering_service.generate_ideas_for_high_intensity_clusters(
            product_id=product_id,
            threshold=threshold,
            llm_service=llm_service
        )

        # Chain to triage if requested
        if chain_triage:
            queue_service.update_progress(job_id, 80.0, "Queueing triage for generated ideas...")

            for result in results:
                if result.get('status') == 'generated' and result.get('idea_id'):
                    # Create triage job
                    triage_job = queue_service.create_job(
                        job_type=JobType.IDEA_TRIAGE,
                        input_data={'idea_id': result['idea_id']},
                        product_id=product_id,
                        user_id=job.user_id,
                        parent_job_id=job.id,
                    )
                    db.commit()

                    # Queue the triage task
                    triage_idea_task.delay(triage_job.id)

                    result['triage_job_id'] = triage_job.id

        # Update progress
        queue_service.update_progress(job_id, 95.0, "Finalizing...")

        output_data = {
            'product_id': product_id,
            'ideas_generated': len([r for r in results if r.get('status') == 'generated']),
            'ideas_skipped': len([r for r in results if r.get('status') == 'skipped']),
            'errors': len([r for r in results if r.get('status') == 'error']),
            'results': results
        }

        # Mark success
        queue_service.mark_success(job_id, output_data)

        return output_data

    except Exception as e:
        error_msg = str(e)
        error_tb = traceback.format_exc()
        print(f"[intensity_idea_generation_task] Error: {error_msg}")

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


@shared_task(bind=True, name='app.queue.tasks.scheduled_deep_analysis_task')
def scheduled_deep_analysis_task(self, job_id: int) -> Dict[str, Any]:
    """
    Run scheduled deep analysis for a product.

    This task:
    1. Finds all competitors with deep_analysis_enabled=True
    2. Queues deep_analysis_task for each (parallel via chord)
    3. After all complete, runs clustering and intensity idea generation

    Args:
        job_id: QueueJob ID to process

    Returns:
        Dictionary indicating chord was dispatched
    """
    from celery import chord
    from app.models.competitive_agent import CompetitiveAgentConfig

    db = None
    try:
        db = get_db()
        queue_service = QueueService(db)

        # Mark job as running
        job = queue_service.mark_running(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        product_id = job.product_id
        if not product_id:
            raise ValueError("Product ID is required")

        # Get enabled competitors
        competitors = db.query(ProductCompetitor).filter(
            ProductCompetitor.product_id == product_id,
            ProductCompetitor.status == 'active',
            ProductCompetitor.deep_analysis_enabled == True
        ).all()

        if not competitors:
            output_data = {
                'product_id': product_id,
                'message': 'No competitors enabled for deep analysis',
                'competitors_processed': 0
            }
            queue_service.mark_success(job_id, output_data)
            return output_data

        # Update progress
        queue_service.update_progress(
            job_id, 10.0,
            f"Creating deep analysis jobs for {len(competitors)} competitors..."
        )

        # Create child jobs for each competitor
        child_job_ids = []
        for competitor in competitors:
            child_job = queue_service.create_job(
                job_type=JobType.DEEP_ANALYSIS,
                input_data={'competitor_id': competitor.id},
                product_id=product_id,
                user_id=job.user_id,
                parent_job_id=job_id,
            )
            child_job_ids.append(child_job.id)

        db.commit()

        # Update progress
        queue_service.update_progress(
            job_id, 20.0,
            f"Dispatching {len(child_job_ids)} deep analysis tasks..."
        )

        # Use chord: group of deep analysis tasks -> callback to aggregate and cluster
        analysis_chord = chord(
            [deep_analysis_task.s(child_id) for child_id in child_job_ids],
            aggregate_deep_analysis_results.s(job_id, child_job_ids, product_id)
        )

        # Dispatch the chord
        chord_result = analysis_chord.apply_async()

        db.commit()

        return {
            'status': 'chord_dispatched',
            'parent_job_id': job_id,
            'child_job_ids': child_job_ids,
            'chord_id': chord_result.id if chord_result else None,
        }

    except Exception as e:
        error_msg = str(e)
        error_tb = traceback.format_exc()
        print(f"[scheduled_deep_analysis_task] Error: {error_msg}")

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


@shared_task(bind=True, name='app.queue.tasks.aggregate_deep_analysis_results')
def aggregate_deep_analysis_results(
    self,
    results: List[Dict],
    parent_job_id: int,
    child_job_ids: List[int],
    product_id: int
) -> Dict[str, Any]:
    """
    Callback task to aggregate results from parallel deep analysis.

    After all deep analysis tasks complete, this:
    1. Aggregates results
    2. Runs feature clustering
    3. Generates ideas from high-intensity clusters
    4. Marks parent job as complete

    Args:
        results: List of results from each deep analysis task
        parent_job_id: Parent QueueJob ID to update
        child_job_ids: List of child job IDs that were processed
        product_id: Product ID

    Returns:
        Aggregated results
    """
    from app.services.feature_clustering_service import FeatureClusteringService

    db = None
    try:
        db = get_db()
        queue_service = QueueService(db)
        llm_service = LLMService()

        # Get parent job
        job = queue_service.get_job(parent_job_id)
        if not job:
            raise ValueError(f"Parent job {parent_job_id} not found")

        # Aggregate deep analysis results
        successful = 0
        total_features = 0
        for r in results:
            if r and r.get('analyses_completed'):
                successful += 1
                if 'feature_extraction' in r.get('analyses_completed', []):
                    total_features += r.get('feature_extraction', {}).get('features_extracted', 0)

        # Update progress
        queue_service.update_progress(
            parent_job_id, 70.0,
            f"Running feature clustering across {total_features} features..."
        )

        # Run clustering
        clustering_service = FeatureClusteringService(db)
        cluster_result = clustering_service.cluster_features(product_id=product_id)

        # Update progress
        queue_service.update_progress(
            parent_job_id, 85.0,
            "Generating ideas from high-intensity clusters..."
        )

        # Generate ideas
        idea_results = clustering_service.generate_ideas_for_high_intensity_clusters(
            product_id=product_id,
            llm_service=llm_service
        )

        # Chain to triage for all generated ideas (duplicate + feature exists detection)
        queue_service.update_progress(
            parent_job_id, 90.0,
            "Queueing triage for generated ideas..."
        )

        triage_jobs_created = 0
        for result in idea_results:
            if result.get('status') == 'generated' and result.get('idea_id'):
                # Create triage job for each generated idea
                triage_job = queue_service.create_job(
                    job_type=JobType.IDEA_TRIAGE,
                    input_data={'idea_id': result['idea_id']},
                    product_id=product_id,
                    parent_job_id=parent_job_id,
                )
                db.commit()

                # Queue the triage task
                triage_idea_task.delay(triage_job.id)

                result['triage_job_id'] = triage_job.id
                triage_jobs_created += 1

        output_data = {
            'product_id': product_id,
            'competitors_analyzed': len(child_job_ids),
            'successful_analyses': successful,
            'total_features_extracted': total_features,
            'clusters_created': cluster_result.clusters_created,
            'high_intensity_clusters': cluster_result.high_intensity_clusters,
            'ideas_generated': len([r for r in idea_results if r.get('status') == 'generated']),
            'triage_jobs_created': triage_jobs_created,
            'child_job_ids': child_job_ids,
        }

        # Mark parent job as success
        queue_service.mark_success(parent_job_id, output_data)

        return output_data

    except Exception as e:
        error_msg = str(e)
        error_tb = traceback.format_exc()
        print(f"[aggregate_deep_analysis_results] Error: {error_msg}")

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


# =============================================================================
# V2 Competitive Analysis Tasks (Functional Audit + Landscape Synthesis)
# =============================================================================

@shared_task(bind=True, name='app.queue.tasks.functional_audit_task', max_retries=2, default_retry_delay=60)
def functional_audit_task(self, job_id: int):
    """
    Run a functional audit for a single competitor.

    This task:
    1. Fetches competitor data and web search results
    2. Runs the CompetitorFunctionalAuditAgent
    3. Stores the report in the database
    4. Returns the report ID for aggregation

    Args:
        job_id: The QueueJob ID for this audit
    """
    from app.agents.functional_audit_agent import (
        CompetitorFunctionalAuditAgent,
        generate_markdown_report
    )
    from app.models.competitive_reports import CompetitorFunctionalReport
    from app.schemas.competitive_reports import FunctionalAuditOutput
    from app.services.llm_service import LLMService

    db = None
    try:
        db = SessionLocal()
        queue_service = QueueService(db)

        # Get job details
        job = queue_service.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        queue_service.mark_running(job_id)

        # Extract job parameters
        input_data = job.input_data or {}
        competitor_id = input_data.get('competitor_id')
        product_id = job.product_id

        if not competitor_id:
            raise ValueError("competitor_id is required in input_data")

        # Get competitor info
        competitor = db.query(ProductCompetitor).filter(
            ProductCompetitor.id == competitor_id,
            ProductCompetitor.product_id == product_id
        ).first()

        if not competitor:
            raise ValueError(f"Competitor {competitor_id} not found for product {product_id}")

        # Get product context
        product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
        product_context = {
            'product_name': product.product_name if product else 'Unknown',
            'product_category': product.product_category if product else None,
            'description': product.product_description if product else None,
        }

        # Get product features for context
        features = db.query(ProductFeature).filter(
            ProductFeature.product_id == product_id,
            ProductFeature.status == 'active'
        ).limit(15).all()
        product_context['core_features'] = [f.feature_name for f in features]

        # Get web search results (from previous web search or fetch now)
        web_search_results = input_data.get('web_search_results', [])

        if not web_search_results and competitor.competitor_url:
            # Could trigger web search here if needed
            # For now, use any cached search data
            pass

        # Initialize LLM service and agent
        llm_service = LLMService()
        agent = CompetitorFunctionalAuditAgent(db=db, llm_service=llm_service)

        # Run the audit
        agent_input = {
            'competitor_name': competitor.competitor_name,
            'competitor_url': competitor.competitor_url or '',
            'product_context': product_context,
            'web_search_results': web_search_results,
        }

        # Use higher max_tokens for detailed audit output
        result = agent.execute(agent_input, max_tokens=8000)

        # Generate markdown report (convert dict to Pydantic for the report generator)
        result_model = FunctionalAuditOutput(**result)
        markdown_content = generate_markdown_report(competitor.competitor_name, result_model)

        # Store or update the report
        existing_report = db.query(CompetitorFunctionalReport).filter(
            CompetitorFunctionalReport.product_competitor_id == competitor_id,
            CompetitorFunctionalReport.product_id == product_id
        ).first()

        if existing_report:
            # Update existing report
            existing_report.report_version += 1
            existing_report.report_content_md = markdown_content
            existing_report.competitor_context = result['competitor_context']
            existing_report.functional_comparison = result['functional_comparison']
            existing_report.gaps_deep_dive = result['gaps_deep_dive']
            existing_report.technical_constraints = result['technical_constraints']
            existing_report.raw_search_results = web_search_results if isinstance(web_search_results, list) else None
            existing_report.queue_job_id = job_id
            report = existing_report
        else:
            # Create new report
            report = CompetitorFunctionalReport(
                product_competitor_id=competitor_id,
                product_id=product_id,
                report_version=1,
                report_content_md=markdown_content,
                competitor_context=result['competitor_context'],
                functional_comparison=result['functional_comparison'],
                gaps_deep_dive=result['gaps_deep_dive'],
                technical_constraints=result['technical_constraints'],
                raw_search_results=web_search_results if isinstance(web_search_results, list) else None,
                queue_job_id=job_id
            )
            db.add(report)

        db.commit()
        db.refresh(report)

        output_data = {
            'report_id': report.id,
            'competitor_id': competitor_id,
            'competitor_name': competitor.competitor_name,
            'report_version': report.report_version,
            'features_compared': len(result['functional_comparison']),
            'gaps_identified': len(result['gaps_deep_dive']),
        }

        queue_service.mark_success(job_id, output_data)
        return output_data

    except Exception as e:
        error_msg = str(e)
        error_tb = traceback.format_exc()
        print(f"[functional_audit_task] Error for job {job_id}: {error_msg}")

        if db:
            try:
                queue_service = QueueService(db)
                queue_service.mark_failure(job_id, error_msg, error_tb)
            except Exception:
                pass

        raise self.retry(exc=e)

    finally:
        if db:
            db.close()


@shared_task(bind=True, name='app.queue.tasks.landscape_synthesis_task', max_retries=2, default_retry_delay=60)
def landscape_synthesis_task(self, job_id: int):
    """
    Run landscape synthesis across all competitor functional reports.

    This task:
    1. Gathers all functional reports for the product
    2. Runs the LandscapeOpportunitySynthesizerAgent
    3. Stores the landscape report
    4. Auto-exports all reports to filesystem

    Args:
        job_id: The QueueJob ID for this synthesis
    """
    from app.agents.landscape_synthesizer_agent import (
        LandscapeOpportunitySynthesizerAgent,
        generate_markdown_report
    )
    from app.models.competitive_reports import (
        CompetitorFunctionalReport,
        LandscapeOpportunityReport
    )
    from app.schemas.competitive_reports import LandscapeSynthesisOutput
    from app.services.llm_service import LLMService
    from app.services.report_export_service import get_report_export_service

    db = None
    try:
        db = SessionLocal()
        queue_service = QueueService(db)

        # Get job details
        job = queue_service.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        queue_service.mark_running(job_id)

        product_id = job.product_id
        input_data = job.input_data or {}

        # Get product context
        product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
        if not product:
            raise ValueError(f"Product {product_id} not found")

        product_context = {
            'product_name': product.product_name,
            'product_category': product.product_category,
            'description': product.product_description,
        }

        # Get product features
        features = db.query(ProductFeature).filter(
            ProductFeature.product_id == product_id,
            ProductFeature.status == 'active'
        ).limit(15).all()
        product_context['core_features'] = [f.feature_name for f in features]

        # Get all functional reports for this product
        functional_reports = db.query(CompetitorFunctionalReport).filter(
            CompetitorFunctionalReport.product_id == product_id
        ).all()

        if not functional_reports:
            raise ValueError(f"No functional reports found for product {product_id}")

        # Format reports for the agent
        competitor_reports = []
        report_ids = []
        report_tuples = []  # For export service

        for report in functional_reports:
            # Get competitor name
            competitor = db.query(ProductCompetitor).filter(
                ProductCompetitor.id == report.product_competitor_id
            ).first()
            competitor_name = competitor.competitor_name if competitor else f"Competitor {report.product_competitor_id}"

            competitor_reports.append({
                'competitor_name': competitor_name,
                'audit': {
                    'competitor_context': report.competitor_context,
                    'functional_comparison': report.functional_comparison,
                    'gaps_deep_dive': report.gaps_deep_dive,
                    'technical_constraints': report.technical_constraints,
                }
            })
            report_ids.append(report.id)
            report_tuples.append((report, competitor_name))

        # Initialize LLM service and agent
        llm_service = LLMService()
        agent = LandscapeOpportunitySynthesizerAgent(db=db, llm_service=llm_service)

        # Run the synthesis
        agent_input = {
            'product_context': product_context,
            'competitor_reports': competitor_reports,
        }

        # Use higher max_tokens for synthesis output
        result = agent.execute(agent_input, max_tokens=8000)

        # Convert dict to Pydantic for markdown generation
        result_model = LandscapeSynthesisOutput(**result)

        # Generate markdown report
        markdown_content = generate_markdown_report(
            product.product_name,
            result_model,
            len(functional_reports)
        )

        # Store or update the landscape report
        existing_report = db.query(LandscapeOpportunityReport).filter(
            LandscapeOpportunityReport.product_id == product_id
        ).first()

        if existing_report:
            existing_report.report_version += 1
            existing_report.report_content_md = markdown_content
            existing_report.feature_cluster_matrix = result['feature_cluster_matrix']
            existing_report.feature_opportunities = result['feature_opportunities']
            existing_report.high_impact_gaps = result['high_impact_gaps']
            existing_report.source_competitor_report_ids = report_ids
            existing_report.queue_job_id = job_id
            landscape_report = existing_report
        else:
            landscape_report = LandscapeOpportunityReport(
                product_id=product_id,
                report_version=1,
                report_content_md=markdown_content,
                feature_cluster_matrix=result['feature_cluster_matrix'],
                feature_opportunities=result['feature_opportunities'],
                high_impact_gaps=result['high_impact_gaps'],
                source_competitor_report_ids=report_ids,
                queue_job_id=job_id
            )
            db.add(landscape_report)

        db.commit()
        db.refresh(landscape_report)

        # Auto-export all reports to filesystem
        export_service = get_report_export_service()
        export_result = export_service.export_analysis_run(
            product_id=product_id,
            product_name=product.product_name,
            functional_reports=report_tuples,
            landscape_report=landscape_report
        )

        output_data = {
            'landscape_report_id': landscape_report.id,
            'report_version': landscape_report.report_version,
            'competitors_analyzed': len(functional_reports),
            'feature_clusters': len(result['feature_cluster_matrix']),
            'feature_opportunities': len(result['feature_opportunities']),
            'high_impact_gaps': len(result['high_impact_gaps']),
            'source_report_ids': report_ids,
            'export_folder': export_result.get('folder'),
            'export_files': export_result.get('total_files', 0),
        }

        queue_service.mark_success(job_id, output_data)

        # If this was triggered as part of V2 workflow, mark parent job complete
        if job.parent_job_id:
            parent_job = queue_service.get_job(job.parent_job_id)
            if parent_job and parent_job.status == JobStatus.RUNNING:
                parent_output = parent_job.output_data or {}
                parent_output['landscape_synthesis_job_id'] = job_id
                parent_output['landscape_report_id'] = landscape_report.id
                parent_output['status'] = 'completed'
                queue_service.mark_success(job.parent_job_id, parent_output)
                print(f"[landscape_synthesis_task] Marked parent job {job.parent_job_id} as success")

        return output_data

    except Exception as e:
        error_msg = str(e)
        error_tb = traceback.format_exc()
        print(f"[landscape_synthesis_task] Error for job {job_id}: {error_msg}")

        if db:
            try:
                queue_service = QueueService(db)
                queue_service.mark_failure(job_id, error_msg, error_tb)
            except Exception:
                pass

        raise self.retry(exc=e)

    finally:
        if db:
            db.close()


@shared_task(bind=True, name='app.queue.tasks.aggregate_functional_audits')
def aggregate_functional_audits(self, audit_results: list, parent_job_id: int):
    """
    Callback task after all functional audits complete.

    Triggers landscape synthesis automatically.

    Args:
        audit_results: List of results from functional_audit_task
        parent_job_id: The parent orchestration job ID
    """
    from app.models.queue import QueueJob, JobType, JobStatus

    db = None
    try:
        db = SessionLocal()
        queue_service = QueueService(db)

        # Get parent job to find product_id
        parent_job = queue_service.get_job(parent_job_id)
        if not parent_job:
            raise ValueError(f"Parent job {parent_job_id} not found")

        product_id = parent_job.product_id

        # Count successful audits
        successful_audits = [r for r in audit_results if r and r.get('report_id')]
        failed_audits = len(audit_results) - len(successful_audits)

        print(f"[aggregate_functional_audits] {len(successful_audits)} successful, {failed_audits} failed")

        if not successful_audits:
            raise ValueError("All functional audits failed, cannot proceed with synthesis")

        # Create landscape synthesis job
        synthesis_job = QueueJob(
            job_type=JobType.LANDSCAPE_SYNTHESIS,
            status=JobStatus.PENDING,
            product_id=product_id,
            parent_job_id=parent_job_id,
            input_data={
                'audit_report_ids': [r['report_id'] for r in successful_audits],
            }
        )
        db.add(synthesis_job)
        db.commit()
        db.refresh(synthesis_job)

        # Trigger landscape synthesis
        landscape_synthesis_task.delay(synthesis_job.id)

        return {
            'status': 'synthesis_triggered',
            'successful_audits': len(successful_audits),
            'failed_audits': failed_audits,
            'synthesis_job_id': synthesis_job.id,
        }

    except Exception as e:
        error_msg = str(e)
        error_tb = traceback.format_exc()
        print(f"[aggregate_functional_audits] Error: {error_msg}")

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


@shared_task(bind=True, name='app.queue.tasks.run_competitive_analysis_v2')
def run_competitive_analysis_v2(self, job_id: int):
    """
    Orchestrate the V2 competitive analysis workflow.

    This task:
    1. Creates functional audit jobs for all enabled competitors
    2. Dispatches audits in parallel using Celery chord
    3. Chord callback triggers landscape synthesis

    Args:
        job_id: The parent orchestration job ID
    """
    from celery import chord
    from app.models.queue import QueueJob, JobType, JobStatus

    db = None
    try:
        db = SessionLocal()
        queue_service = QueueService(db)

        # Get job details
        job = queue_service.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        queue_service.mark_running(job_id)

        product_id = job.product_id

        # Get competitors enabled for deep analysis (selected by user in Market Discovery)
        competitors = db.query(ProductCompetitor).filter(
            ProductCompetitor.product_id == product_id,
            ProductCompetitor.status == 'active',
            ProductCompetitor.deep_analysis_enabled == True
        ).all()

        if not competitors:
            raise ValueError(f"No competitors enabled for deep analysis. Enable competitors in Market Discovery first.")

        print(f"[run_competitive_analysis_v2] Starting analysis for {len(competitors)} competitors")

        # Create audit jobs for each competitor
        audit_tasks = []
        audit_job_ids = []

        for competitor in competitors:
            # Create job record
            audit_job = QueueJob(
                job_type=JobType.FUNCTIONAL_AUDIT,
                status=JobStatus.PENDING,
                product_id=product_id,
                parent_job_id=job_id,
                input_data={
                    'competitor_id': competitor.id,
                    'competitor_name': competitor.competitor_name,
                }
            )
            db.add(audit_job)
            db.flush()  # Get ID without committing

            audit_job_ids.append(audit_job.id)
            audit_tasks.append(functional_audit_task.s(audit_job.id))

        db.commit()

        # Update parent job with child job IDs
        job.output_data = {
            'status': 'audits_dispatched',
            'audit_job_ids': audit_job_ids,
            'competitor_count': len(competitors),
        }
        db.commit()

        # Dispatch parallel audits with callback for synthesis
        workflow = chord(audit_tasks)(aggregate_functional_audits.s(job_id))

        return {
            'status': 'workflow_started',
            'audit_jobs': len(audit_job_ids),
            'competitors': [c.competitor_name for c in competitors],
        }

    except Exception as e:
        error_msg = str(e)
        error_tb = traceback.format_exc()
        print(f"[run_competitive_analysis_v2] Error for job {job_id}: {error_msg}")

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


# =============================================================================
# Internal Discovery Task (Three-Source Synthesis)
# =============================================================================

@shared_task(bind=True, name='app.queue.tasks.internal_discovery_task', max_retries=2, default_retry_delay=60)
def internal_discovery_task(self, job_id: int):
    """
    Process uploaded internal feedback data to extract themes.

    This task:
    1. Retrieves the imported data from the database
    2. Runs the InternalDiscoveryAgent to extract themes
    3. Stores WinLossTheme and SupportTheme records
    4. Updates the import status

    Args:
        job_id: The QueueJob ID for this task
    """
    from app.agents.internal_discovery_agent import InternalDiscoveryAgent
    from app.models.internal_feedback import (
        InternalFeedbackImport,
        WinLossTheme,
        SupportTheme
    )
    from app.schemas.internal_feedback import InternalDiscoveryOutput
    from app.services.llm_service import LLMService
    from datetime import datetime

    db = None
    try:
        db = SessionLocal()
        queue_service = QueueService(db)

        # Get job details
        job = queue_service.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        queue_service.mark_running(job_id)

        # Extract job parameters
        input_data = job.input_data or {}
        import_id = input_data.get('import_id')
        deals = input_data.get('deals', [])
        support_tickets = input_data.get('support_tickets', [])

        if not import_id:
            raise ValueError("import_id is required in input_data")

        # Get import record
        import_record = db.query(InternalFeedbackImport).filter(
            InternalFeedbackImport.id == import_id
        ).first()

        if not import_record:
            raise ValueError(f"Import {import_id} not found")

        # Initialize LLM service and agent
        llm_service = LLMService()
        agent = InternalDiscoveryAgent(
            db=db,
            llm_service=llm_service,
            product_id=import_record.product_id
        )

        # Run the agent
        result = agent.execute({
            'deals': deals,
            'support_tickets': support_tickets
        })

        # Parse output
        if isinstance(result, InternalDiscoveryOutput):
            output = result
        else:
            output = InternalDiscoveryOutput(**result)

        # Store win/loss themes
        for theme in output.winloss_themes:
            db_theme = WinLossTheme(
                import_id=import_id,
                product_id=import_record.product_id,
                theme_name=theme.theme_name,
                outcome=theme.outcome,
                competitor_name=theme.competitor_correlation,
                deal_count=theme.deal_count,
                total_value=theme.total_value,
                sample_reasons=theme.sample_reasons,
                feature_keywords=theme.feature_keywords
            )
            db.add(db_theme)

        # Store support themes
        for theme in output.support_themes:
            db_theme = SupportTheme(
                import_id=import_id,
                product_id=import_record.product_id,
                theme_name=theme.theme_name,
                category=theme.category,
                ticket_count=theme.ticket_count,
                sample_subjects=theme.sample_subjects,
                feature_keywords=theme.feature_keywords,
                urgency_indicator=theme.urgency_indicator
            )
            db.add(db_theme)

        # Update import record
        import_record.status = "completed"
        import_record.themes_extracted = True
        import_record.analysis_summary = output.analysis_summary
        import_record.processed_at = datetime.utcnow()

        db.commit()

        # Mark job success
        queue_service.mark_success(job_id, {
            'import_id': import_id,
            'winloss_themes_count': len(output.winloss_themes),
            'support_themes_count': len(output.support_themes),
            'deals_analyzed': output.deals_analyzed,
            'tickets_analyzed': output.tickets_analyzed
        })

        return {
            'status': 'completed',
            'import_id': import_id,
            'winloss_themes': len(output.winloss_themes),
            'support_themes': len(output.support_themes)
        }

    except Exception as e:
        error_msg = str(e)
        error_tb = traceback.format_exc()
        print(f"[internal_discovery_task] Error for job {job_id}: {error_msg}")

        if db:
            try:
                queue_service = QueueService(db)
                queue_service.mark_failure(job_id, error_msg, error_tb)

                # Update import record status
                input_data = queue_service.get_job(job_id).input_data or {}
                import_id = input_data.get('import_id')
                if import_id:
                    import_record = db.query(InternalFeedbackImport).filter(
                        InternalFeedbackImport.id == import_id
                    ).first()
                    if import_record:
                        import_record.status = "failed"
                        import_record.error_message = error_msg
                        db.commit()
            except Exception:
                pass

        raise

    finally:
        if db:
            db.close()


@shared_task(bind=True, name='app.queue.tasks.opportunity_synthesis_task')
def opportunity_synthesis_task(self, job_id: int):
    """
    Synthesize opportunities from competitive, customer, and internal sources.

    This task:
    1. Gathers data from all available sources
    2. Runs the OpportunitySynthesisAgent
    3. Stores SynthesizedOpportunity records
    4. Updates the SynthesisRun status

    Args:
        job_id: The QueueJob ID for this task
    """
    from app.agents.synthesis_agent import OpportunitySynthesisAgent
    from app.models.synthesis import SynthesisRun, SynthesizedOpportunity
    from app.models.competitive_reports import LandscapeOpportunityReport
    from app.models.internal_feedback import (
        InternalFeedbackImport,
        WinLossTheme,
        SupportTheme
    )
    from app.models.idea import Idea, IdeaStatus
    from app.schemas.synthesis import OpportunitySynthesisOutput
    from app.services.llm_service import LLMService
    from datetime import datetime
    from sqlalchemy import desc

    db = None
    try:
        db = SessionLocal()
        queue_service = QueueService(db)

        # Get job details
        job = queue_service.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        queue_service.mark_running(job_id)

        # Extract job parameters
        input_data = job.input_data or {}
        synthesis_run_id = input_data.get('synthesis_run_id')
        product_id = job.product_id

        if not synthesis_run_id:
            raise ValueError("synthesis_run_id is required in input_data")

        if not product_id:
            raise ValueError("product_id is required")

        # Get synthesis run record
        synthesis_run = db.query(SynthesisRun).filter(
            SynthesisRun.id == synthesis_run_id
        ).first()

        if not synthesis_run:
            raise ValueError(f"SynthesisRun {synthesis_run_id} not found")

        # Gather data from all sources
        queue_service.update_progress(job_id, 10.0, "Gathering competitive data...")

        # 1. Competitive opportunities from landscape report
        competitive_opportunities = []
        landscape_report = db.query(LandscapeOpportunityReport).filter(
            LandscapeOpportunityReport.product_id == product_id
        ).first()

        if landscape_report and landscape_report.feature_opportunities:
            competitive_opportunities = landscape_report.feature_opportunities

        queue_service.update_progress(job_id, 25.0, "Gathering customer ideas...")

        # 2. Customer ideas (top voted)
        # Vote count is computed via relationship, not a stored column
        from app.models.vote import Vote
        from sqlalchemy import func as sql_func

        customer_ideas = []
        # Subquery to count votes per idea
        vote_counts = db.query(
            Vote.idea_id,
            sql_func.sum(Vote.vote_value).label('vote_count')
        ).group_by(Vote.idea_id).subquery()

        # Query ideas with their vote counts, ordered by votes descending
        # Only include ACCEPTED ideas (those open for voting)
        ideas_with_votes = db.query(
            Idea,
            sql_func.coalesce(vote_counts.c.vote_count, 0).label('vote_count')
        ).outerjoin(
            vote_counts, Idea.id == vote_counts.c.idea_id
        ).filter(
            Idea.product_id == product_id,
            Idea.status == IdeaStatus.ACCEPTED
        ).order_by(desc('vote_count')).limit(50).all()

        for idea, vote_count in ideas_with_votes:
            customer_ideas.append({
                'id': idea.id,
                'title': idea.title,
                'description': idea.what_description,  # Use what_description as the description
                'vote_count': int(vote_count) if vote_count else 0,
                'status': idea.status.value if idea.status else 'submitted'
            })

        queue_service.update_progress(job_id, 40.0, "Gathering internal feedback...")

        # 3. Internal feedback themes (from most recent completed import)
        winloss_themes = []
        support_themes = []

        latest_import = db.query(InternalFeedbackImport).filter(
            InternalFeedbackImport.product_id == product_id,
            InternalFeedbackImport.themes_extracted == True
        ).order_by(desc(InternalFeedbackImport.imported_at)).first()

        if latest_import:
            # Get win/loss themes
            wl_themes = db.query(WinLossTheme).filter(
                WinLossTheme.import_id == latest_import.id
            ).all()
            for theme in wl_themes:
                winloss_themes.append({
                    'id': theme.id,
                    'theme_name': theme.theme_name,
                    'outcome': theme.outcome,
                    'competitor_name': theme.competitor_name,
                    'deal_count': theme.deal_count,
                    'total_value': theme.total_value,
                    'sample_reasons': theme.sample_reasons or [],
                    'feature_keywords': theme.feature_keywords or []
                })

            # Get support themes
            sup_themes = db.query(SupportTheme).filter(
                SupportTheme.import_id == latest_import.id
            ).all()
            for theme in sup_themes:
                support_themes.append({
                    'id': theme.id,
                    'theme_name': theme.theme_name,
                    'category': theme.category,
                    'ticket_count': theme.ticket_count,
                    'sample_subjects': theme.sample_subjects or [],
                    'feature_keywords': theme.feature_keywords or [],
                    'urgency_indicator': theme.urgency_indicator
                })

        # Update source snapshot
        sources_used = []
        if competitive_opportunities:
            sources_used.append("competitive")
        if customer_ideas:
            sources_used.append("customer")
        if winloss_themes or support_themes:
            sources_used.append("internal")

        source_snapshot = {
            'landscape_report_id': landscape_report.id if landscape_report else None,
            'competitive_opportunities_count': len(competitive_opportunities),
            'ideas_count': len(customer_ideas),
            'ideas_total_votes': sum(i.get('vote_count', 0) for i in customer_ideas),
            'internal_import_id': latest_import.id if latest_import else None,
            'winloss_themes_count': len(winloss_themes),
            'support_themes_count': len(support_themes)
        }

        synthesis_run.source_snapshot = source_snapshot
        synthesis_run.sources_used = sources_used
        db.commit()

        queue_service.update_progress(job_id, 50.0, "Running synthesis agent...")

        # Initialize LLM service and agent
        llm_service = LLMService()
        agent = OpportunitySynthesisAgent(
            db=db,
            llm_service=llm_service,
            product_id=product_id
        )

        # Run the agent with higher max_tokens for complex JSON output
        # Synthesis generates detailed evidence for up to 15 opportunities
        result = agent.execute(
            {
                'competitive_opportunities': competitive_opportunities,
                'customer_ideas': customer_ideas,
                'winloss_themes': winloss_themes,
                'support_themes': support_themes
            },
            max_tokens=8000  # Higher limit for complex synthesis output
        )

        queue_service.update_progress(job_id, 80.0, "Storing synthesis results...")

        # Parse output
        if isinstance(result, OpportunitySynthesisOutput):
            output = result
        else:
            output = OpportunitySynthesisOutput(**result)

        # Store synthesized opportunities
        three_way = 0
        two_way = 0
        single_source = 0

        for opp in output.opportunities:
            db_opp = SynthesizedOpportunity(
                synthesis_run_id=synthesis_run_id,
                product_id=product_id,
                opportunity_name=opp.opportunity_name,
                opportunity_summary=opp.opportunity_summary,
                priority_score=opp.priority_score,
                source_count=opp.source_count,
                sources=opp.sources,
                competitive_evidence=opp.competitive_evidence.model_dump() if opp.competitive_evidence else None,
                customer_evidence=opp.customer_evidence.model_dump() if opp.customer_evidence else None,
                internal_evidence=opp.internal_evidence.model_dump() if opp.internal_evidence else None,
                recommended_action=opp.recommended_action,
                feature_keywords=opp.feature_keywords
            )
            db.add(db_opp)

            if opp.source_count >= 3:
                three_way += 1
            elif opp.source_count == 2:
                two_way += 1
            else:
                single_source += 1

        # Update synthesis run
        synthesis_run.status = 'completed'
        synthesis_run.analysis_summary = output.analysis_summary
        synthesis_run.summary_stats = {
            'three_way_matches': three_way,
            'two_way_matches': two_way,
            'single_source': single_source,
            'total_opportunities': len(output.opportunities)
        }
        synthesis_run.completed_at = datetime.utcnow()

        db.commit()

        # Mark job success
        queue_service.mark_success(job_id, {
            'synthesis_run_id': synthesis_run_id,
            'opportunities_count': len(output.opportunities),
            'three_way_matches': three_way,
            'two_way_matches': two_way,
            'single_source': single_source
        })

        return {
            'status': 'completed',
            'synthesis_run_id': synthesis_run_id,
            'opportunities': len(output.opportunities)
        }

    except Exception as e:
        error_msg = str(e)
        error_tb = traceback.format_exc()
        print(f"[opportunity_synthesis_task] Error for job {job_id}: {error_msg}")

        if db:
            try:
                queue_service = QueueService(db)
                queue_service.mark_failure(job_id, error_msg, error_tb)

                # Update synthesis run status
                synthesis_run_id = (job.input_data or {}).get('synthesis_run_id') if 'job' in dir() else None
                if synthesis_run_id:
                    synthesis_run = db.query(SynthesisRun).filter(
                        SynthesisRun.id == synthesis_run_id
                    ).first()
                    if synthesis_run:
                        synthesis_run.status = 'failed'
                        synthesis_run.error_message = error_msg
                        db.commit()
            except Exception:
                pass

        raise

    finally:
        if db:
            db.close()