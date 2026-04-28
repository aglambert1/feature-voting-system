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
from celery import shared_task
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models.queue import JobStatus, JobType
from app.models.competitor_intelligence import (
    CIProduct, ProductAnalysisHistory, ProductFeature,
    ProductCompetitor
)
from app.models.competitive_reports import CompetitorAlert
from app.models.competitive_agent import CompetitiveAgentConfig
from app.services.queue_service import QueueService
from app.services.llm_service import LLMService
from app.services.competitive_report_metrics import count_gaps
from app.agents.product_analyzer import ProductAnalyzerAgent
from app.agents.competitor_researcher import CompetitorResearcherAgent
from app.utils.url import normalize_url, extract_domain


def get_db():
    """Get a database session for task execution."""
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


def _fetch_source_urls(
    source_urls: List[str],
    *,
    queue_service: Optional[QueueService] = None,
    job_id: Optional[int] = None,
    progress_start: float = 20.0,
    progress_span: float = 5.0,
) -> List[Dict[str, Any]]:
    """Fetch each URL and return a list of {url, title, text} dicts.

    Failures are logged and skipped (one bad URL does not fail the whole job).
    Extracted text is truncated to MAX_URL_EXTRACT_CHARS per URL.

    Optionally emits progress updates via `queue_service.update_progress(job_id, ...)`
    from `progress_start` to `progress_start + progress_span`.
    """
    from app.services.document_parsing_service import DocumentParsingService
    from app.services.scoped_input_validator import MAX_URL_EXTRACT_CHARS

    if not source_urls:
        return []

    parser = DocumentParsingService()
    fetched: List[Dict[str, Any]] = []
    total = len(source_urls)

    for i, url in enumerate(source_urls, 1):
        if queue_service is not None and job_id is not None:
            pct = progress_start + (i / total) * progress_span
            queue_service.update_progress(job_id, pct, f"fetching source {i}/{total}...")
        try:
            result = parser.fetch_url_content(url)
            extracted = (result.get('extracted_text') or '')
            if len(extracted) > MAX_URL_EXTRACT_CHARS:
                print(
                    f"[_fetch_source_urls] Truncating {url} extract from "
                    f"{len(extracted)} to {MAX_URL_EXTRACT_CHARS} chars"
                )
                extracted = extracted[:MAX_URL_EXTRACT_CHARS]
            fetched.append({
                'url': url,
                'title': result.get('title') or '',
                'text': extracted,
            })
        except Exception as e:
            # One failing URL should not kill the whole job.
            print(f"[_fetch_source_urls] Failed to fetch {url}: {e}")
            continue

    return fetched


def _cosine_similarity(a: list, b: list) -> float:
    """Compute cosine similarity between two embedding vectors.

    Voyage AI embeddings are L2-normalized, so the dot product equals
    the cosine similarity. We still normalize defensively to handle
    embeddings from other sources or partially-corrupted vectors.
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    try:
        import numpy as np
        va = np.array(a, dtype=float)
        vb = np.array(b, dtype=float)
        na = np.linalg.norm(va)
        nb = np.linalg.norm(vb)
        if na == 0.0 or nb == 0.0:
            return 0.0
        return float(np.dot(va, vb) / (na * nb))
    except Exception:
        return 0.0


def _link_idea_to_job(db, idea, similarity_threshold: float = 0.5) -> Optional[str]:
    """Link an idea to its best-matching ProductJob via JTBD embedding similarity.

    Mutates idea.job_id_key in place and returns the matched key (or None).
    Caller is responsible for committing.
    """
    if not idea.jtbd_embedding:
        return None

    from app.models.competitor_intelligence import ProductJob

    jobs = db.query(ProductJob).filter(
        ProductJob.product_id == idea.product_id,
        ProductJob.status == "active",
    ).all()
    if not jobs:
        return None

    best_job = None
    best_sim = 0.0
    for job in jobs:
        if not job.statement_embedding:
            continue
        sim = _cosine_similarity(idea.jtbd_embedding, job.statement_embedding)
        if sim > best_sim and sim > similarity_threshold:
            best_sim = sim
            best_job = job

    if best_job:
        idea.job_id_key = best_job.job_id_key
        return best_job.job_id_key
    return None


def _extract_competitor_names(competitive_evidence) -> list:
    """Extract the competitor list from a SynthesizedOpportunity.competitive_evidence blob.

    Returns [] when the blob is null or missing competitors (e.g., customer-only opp).
    Used by both the auto-gen path in unified_synthesis_task and the manual
    create-from-opportunity endpoint so triage gets the same competitor data
    in both flows.
    """
    if not isinstance(competitive_evidence, dict):
        return []
    return [c for c in (competitive_evidence.get("competitors") or []) if c]


def _sanitize_existing_feature_info(info):
    """Return a copy of existing_feature_info with source_url stripped to None
    unless it's a real http(s) URL.

    The triage agent's output passes through json.loads + a Pydantic schema, but
    the schema only enforces `Optional[str]` on source_url. The agent has been
    observed to echo placeholder strings like "N/A" from the prompt context,
    which then render in the UI as relative URLs (e.g., localhost:5173/N/A).
    Strip those defensively at persistence time so the frontend always either
    sees a usable URL or null.
    """
    if not isinstance(info, dict):
        return info
    sanitized = dict(info)
    url = sanitized.get('source_url')
    if isinstance(url, str):
        url_stripped = url.strip()
        if url_stripped.lower().startswith(('http://', 'https://')):
            sanitized['source_url'] = url_stripped
        else:
            sanitized['source_url'] = None
    elif url is not None:
        sanitized['source_url'] = None
    return sanitized


@shared_task(bind=True, name='app.queue.tasks.analyze_product_task', soft_time_limit=300)
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

        # Fetch any caller-supplied source URLs
        source_urls = input_data.get('source_urls') or []
        fetched_sources = _fetch_source_urls(
            source_urls,
            queue_service=queue_service,
            job_id=job_id,
            progress_start=22.0,
            progress_span=6.0,
        )

        # Create LLM service and agent
        web_research_enabled = input_data.get('web_research_enabled', True)
        llm_service = LLMService()
        agent = ProductAnalyzerAgent(
            db=db,
            llm_service=llm_service,
            product_id=product_id,
            user_id=user_id,
            job_id=job.job_uuid,
            web_research_enabled=web_research_enabled,
        )

        # Build input for agent
        agent_input = {
            'product_name': input_data.get('product_name') or product.product_name,
            'product_description': input_data.get('product_description') or product.product_description,
            'source_type': input_data.get('source_type') or product.product_source_type or 'text',
            'fetched_sources': fetched_sources,
        }

        # Update progress
        queue_service.update_progress(job_id, 30.0, "Running AI analysis...")

        # Execute agent (higher token limit for complex product analyses)
        result = agent.execute(agent_input, max_tokens=16000)

        # Update progress
        queue_service.update_progress(job_id, 70.0, "Saving analysis results...")

        # Update product with source data from input (new/modified sources)
        if input_data.get('product_description'):
            product.product_description = input_data['product_description']
        if input_data.get('source_type'):
            product.product_source_type = input_data['source_type']
        if input_data.get('source_data'):
            product.product_source_data = input_data['source_data']

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

        # Propagate any truncation recovery warnings
        if result.get('_warnings'):
            output_data['warnings'] = result['_warnings']

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


@shared_task(bind=True, name='app.queue.tasks.health_check', soft_time_limit=60)
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


@shared_task(bind=True, name='app.queue.tasks.discover_competitors_task', soft_time_limit=600)
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
            product_id=product_id,
            user_id=user_id,
            job_id=job.job_uuid
        )

        # Load existing competitors for this product (for dedup + LLM context)
        existing_competitors = db.query(ProductCompetitor).filter(
            ProductCompetitor.product_id == product_id,
        ).all()

        # Build input from product analysis
        analysis = product.structured_product_data
        agent_input = {
            'product_name': product.product_name,
            'product_category': analysis.get('product_category', ''),
            'core_features': analysis.get('core_features', []),
            'target_users': analysis.get('target_users', ''),
            'competitor_search_keywords': analysis.get('competitor_search_keywords', []),
            'existing_competitors': [
                {'name': c.competitor_name, 'url': c.competitor_url or ''}
                for c in existing_competitors
                if c.status == 'active'
            ],
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
        competitor_names = []  # Track all competitor names for output_data
        new_competitor_names = []  # Track newly discovered competitors for alerts

        # Build lookup indexes from existing competitors (in Python, DB-agnostic)
        name_index = {c.competitor_name.lower(): c for c in existing_competitors}
        domain_index = {}
        for c in existing_competitors:
            domain = extract_domain(c.competitor_url or '')
            if domain:
                domain_index[domain] = c

        for comp_data in competitors:
            discovered_name = comp_data.get('name', '')
            discovered_url = comp_data.get('url', '')

            # Match by name (case-insensitive) first, then by URL domain
            existing = name_index.get(discovered_name.lower())
            if not existing:
                discovered_domain = extract_domain(discovered_url)
                if discovered_domain:
                    existing = domain_index.get(discovered_domain)

            if existing:
                # Update existing competitor
                existing.competitor_url = discovered_url or existing.competitor_url
                existing.status = 'active'
                competitor_ids.append(existing.id)
                competitor_names.append(existing.competitor_name)
            else:
                # Create new competitor
                new_competitor = ProductCompetitor(
                    product_id=product_id,
                    competitor_name=discovered_name,
                    competitor_url=discovered_url,
                    first_discovered_session_id=None,  # Queue-based, no session
                    status='active'
                )
                db.add(new_competitor)
                db.flush()
                competitor_ids.append(new_competitor.id)
                competitor_names.append(new_competitor.competitor_name)
                new_competitor_names.append({
                    'id': new_competitor.id,
                    'name': new_competitor.competitor_name
                })
                # Add to indexes so later items in this batch also dedup
                name_index[discovered_name.lower()] = new_competitor
                new_domain = extract_domain(discovered_url)
                if new_domain:
                    domain_index[new_domain] = new_competitor

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
            'competitor_names': competitor_names,
            'research_summary': result.get('research_summary', ''),
            'next_step': 'Run ci_run_competitor_audit for each competitor name, then ci_run_analysis for landscape synthesis.',
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


# DEPRECATED: extract_features_task, extract_features_parallel, and aggregate_extraction_results
# have been removed. Feature extraction is now handled by the V2 functional audit workflow.
# Use functional_audit_task to extract competitor features into CompetitorFunctionalReport.


# ============================================================================
# Phase 3: Idea Triage Task
# ============================================================================

@shared_task(bind=True, name='app.queue.tasks.triage_idea_task', soft_time_limit=300)
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

            # Link idea to best-matching ProductJob via embedding similarity
            try:
                matched_key = _link_idea_to_job(db, idea)
                if matched_key:
                    print(f"[triage_idea_task] Linked idea {idea.id} to job {matched_key}")
            except Exception as link_err:
                print(f"[triage_idea_task] Warning: Job linkage failed: {link_err}")

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


@shared_task(bind=True, name='app.queue.tasks.submit_and_triage_idea_task', soft_time_limit=600)
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
                matched_key = _link_idea_to_job(db, idea)
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


@shared_task(bind=True, name='app.queue.tasks.check_scheduled_tasks', soft_time_limit=300)
def check_scheduled_tasks(self) -> Dict[str, Any]:
    """
    Master scheduler task - runs daily via Celery Beat.

    Checks CompetitiveAgentConfig for each product and queues work if due:
    - Product analysis (if scheduled mode and next_run <= now)
    - Competitor discovery (if scheduled mode and next_run <= now)
    - V2 competitive analysis (if scheduled mode and next_run <= now)

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

                # Check Competitive Analysis (V2 functional audit + landscape synthesis)
                if (config.deep_analysis_mode == AgentMode.SCHEDULED
                        and config.deep_analysis_next_run
                        and config.deep_analysis_next_run <= now):
                    print(f"[check_scheduled_tasks] Product {product_id}: V2 competitive analysis due")
                    job = queue_service.create_job(
                        job_type=JobType.SCHEDULED_DEEP_ANALYSIS,
                        input_data={'product_id': product_id, 'scheduled': True},
                        product_id=product_id,
                        user_id=None
                    )
                    db.commit()

                    run_competitive_analysis_v2.delay(job.id)

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


# =============================================================================
# V2 Competitive Analysis Tasks (Functional Audit + Landscape Synthesis)
# =============================================================================

@shared_task(bind=True, name='app.queue.tasks.functional_audit_task', max_retries=2, default_retry_delay=60, soft_time_limit=900)
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
        queue_service.update_progress(job_id, 5.0, "Loading competitor data...")

        # Extract job parameters
        input_data = job.input_data or {}
        competitor_id = input_data.get('competitor_id')
        product_id = job.product_id
        web_research_enabled = input_data.get('web_research_enabled', True)
        source_urls = input_data.get('source_urls') or []

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
        queue_service.update_progress(job_id, 15.0, "Loading product context and job map...")
        product_context = {
            'product_name': product.product_name if product else 'Unknown',
            'product_category': product.product_category if product else None,
            'description': product.product_description if product else None,
        }

        # Load job map for JTBD analysis
        job_map = product.job_map if product else None
        target_customer_profile = product.target_customer_profile if product else None

        # Get product features for context
        features = db.query(ProductFeature).filter(
            ProductFeature.product_id == product_id,
            ProductFeature.status == 'active'
        ).limit(15).all()
        product_context['core_features'] = [f.feature_name for f in features]

        # Resolve web search results via per-competitor cache (Phase B).
        #
        # Priority order:
        #   1. Explicit web_search_results in input_data (legacy / tests)
        #   2. Fresh cache on ProductCompetitor (within TTL)
        #   3. Live refresh via CompetitorResearchCache (if web_research enabled)
        #   4. Empty (if caller disabled web_research and no cache exists)
        #
        # When we have cached/pre-fetched results, we flip effective_web_research
        # to False so the agent renders them into the prompt instead of running
        # the tool-use loop (which would duplicate work and cost more tokens).
        web_search_results = input_data.get('web_search_results') or []
        effective_web_research = web_research_enabled

        if not web_search_results:
            from app.services.competitor_research_cache import CompetitorResearchCache

            cache = CompetitorResearchCache(db)
            cached = cache.get_fresh(competitor)
            if cached is not None:
                web_search_results = cached
                effective_web_research = False
                queue_service.update_progress(
                    job_id, 25.0,
                    f"using cached research for {competitor.competitor_name}...",
                )
            elif web_research_enabled:
                queue_service.update_progress(
                    job_id, 20.0,
                    f"pre-fetching research for {competitor.competitor_name}...",
                )

                def _cache_progress(i: int, total: int) -> None:
                    pct = 20.0 + (i / total) * 5.0
                    queue_service.update_progress(
                        job_id, pct, f"fetching research {i}/{total}...",
                    )

                web_search_results = cache.refresh(
                    competitor, product_context, progress_cb=_cache_progress,
                )
                effective_web_research = False

        # Fetch any caller-supplied source URLs
        fetched_sources = _fetch_source_urls(
            source_urls,
            queue_service=queue_service,
            job_id=job_id,
            progress_start=25.0,
            progress_span=5.0,
        )

        # Query user-provided evidence for this competitor
        from app.models.evidence import Evidence
        competitor_evidence = db.query(Evidence).filter(
            Evidence.competitor_id == competitor_id,
            Evidence.product_id == product_id,
        ).order_by(Evidence.created_at.desc()).limit(20).all()

        user_provided_evidence = []
        for ev in competitor_evidence:
            user_provided_evidence.append({
                'title': ev.title,
                'content': ev.content[:2000] if ev.content else '',
                'evidence_type': ev.evidence_type.value if ev.evidence_type else None,
                'source_url': ev.source_url,
                'source_description': ev.source_description,
            })

        # Initialize LLM service and agent (Phase C: staged execution)
        #
        # effective_web_research may differ from the request param: when we've
        # already fetched cached or fresh results above, we pass them in the
        # prompt and don't need the agent's tool loop.
        #
        # Staged audit: Stage 1 produces competitor_context + functional_comparison
        # + technical_constraints (~45s). Stage 2 uses that output as conditioning
        # context and produces job_assessments + evidence_citations + gaps_deep_dive
        # (~90-150s). This gives the caller visible progress at ~50% instead of a
        # single ~4-minute wait.
        llm_service = LLMService()
        agent = CompetitorFunctionalAuditAgent(
            db=db,
            llm_service=llm_service,
            product_id=product_id,
            user_id=job.user_id,
            job_id=job.job_uuid,
            web_research_enabled=effective_web_research,
        )

        agent_input = {
            'competitor_name': competitor.competitor_name,
            'competitor_url': competitor.competitor_url or '',
            'product_context': product_context,
            'web_search_results': web_search_results,
            'user_provided_evidence': user_provided_evidence,
            'fetched_sources': fetched_sources,
        }
        if job_map:
            agent_input["job_map"] = job_map
        if target_customer_profile:
            agent_input["target_customer_profile"] = target_customer_profile

        # --- Stage 1: context + comparison + technical_constraints ---
        queue_service.update_progress(
            job_id, 30.0,
            f"generating competitor context for {competitor.competitor_name}...",
        )
        stage_1 = agent.execute_stage_1(agent_input, max_tokens=8000)

        # --- Stage 2: job_assessments + evidence_citations + gaps_deep_dive ---
        queue_service.update_progress(
            job_id, 50.0,
            "context ready, generating job assessments...",
        )
        stage_2_input = {**agent_input, "stage_1_output": stage_1}
        stage_2 = agent.execute_stage_2(stage_2_input, max_tokens=12000)

        queue_service.update_progress(job_id, 75.0, "finalizing job assessments...")

        # Merge the two stage outputs into the full schema shape that downstream
        # consumers (report generator, report row, synthesis) expect. Stage-specific
        # keys are additive, so `**stage_1, **stage_2` is sufficient.
        result = {**stage_1, **stage_2}
        # Validate the merged payload against the full schema before persisting —
        # gives us a single clean failure point if either stage dropped a required field.
        result = FunctionalAuditOutput(**result).model_dump()

        queue_service.update_progress(job_id, 85.0, "Generating report...")

        # Generate markdown report (convert dict to Pydantic for the report generator)
        result_model = FunctionalAuditOutput(**result)
        markdown_content = generate_markdown_report(competitor.competitor_name, result_model)

        # Store or update the report
        existing_report = db.query(CompetitorFunctionalReport).filter(
            CompetitorFunctionalReport.product_competitor_id == competitor_id,
            CompetitorFunctionalReport.product_id == product_id
        ).first()

        # Capture previous data for change detection before overwriting
        previous_data = None
        if existing_report:
            previous_data = {
                "functional_comparison": existing_report.functional_comparison or [],
                "competitor_context": existing_report.competitor_context or {},
                "gaps_deep_dive": existing_report.gaps_deep_dive or [],
            }
            # Update existing report
            existing_report.report_version += 1
            existing_report.report_content_md = markdown_content
            existing_report.competitor_context = result['competitor_context']
            existing_report.functional_comparison = result['functional_comparison']
            existing_report.gaps_deep_dive = result['gaps_deep_dive']
            existing_report.technical_constraints = result['technical_constraints']
            existing_report.raw_search_results = web_search_results if isinstance(web_search_results, list) else None
            existing_report.queue_job_id = job_id
            # Store JTBD fields (may be empty if no job map)
            existing_report.job_assessments = result.get("job_assessments")
            existing_report.evidence_citations = result.get("evidence_citations")
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
                queue_job_id=job_id,
                # JTBD fields (may be empty if no job map)
                job_assessments=result.get("job_assessments"),
                evidence_citations=result.get("evidence_citations"),
            )
            db.add(report)

        db.commit()
        db.refresh(report)

        # Mark the competitor as successfully audited (drives synthesis eligibility
        # and the "has been audited" summary in MCP tools)
        now = datetime.utcnow()
        competitor.audit_status = "completed"
        competitor.audit_last_run = now
        competitor.deep_analysis_status = "completed"  # legacy field, keep in sync
        competitor.deep_analysis_last_run = now  # legacy field

        # Update the product-level CompetitiveAgentConfig so the UI "last run"
        # indicator reflects manual audits, not just scheduler runs.
        agent_config = db.query(CompetitiveAgentConfig).filter(
            CompetitiveAgentConfig.product_id == product_id
        ).first()
        if agent_config:
            agent_config.deep_analysis_last_run = now

        db.commit()

        # Compute structured diff from previous version
        if previous_data:
            try:
                from app.services.change_detection_service import ChangeDetectionService
                current_data = {
                    "functional_comparison": result['functional_comparison'],
                    "competitor_context": result['competitor_context'],
                    "gaps_deep_dive": result['gaps_deep_dive'],
                }
                report.changes_from_previous = ChangeDetectionService.compute_functional_report_diff(
                    current_data, previous_data
                )
                db.commit()
            except Exception as diff_err:
                print(f"[functional_audit_task] Warning: Change detection failed: {diff_err}")

        # Increment citation counts for evidence referenced in this report
        try:
            from app.services.evidence_service import increment_evidence_citations

            cited_ids: set = set()

            # evidence_citations: list of {evidence_id, finding_type, ...}
            for citation in (result.get("evidence_citations") or []):
                if isinstance(citation, dict) and citation.get("evidence_id") is not None:
                    cited_ids.add(citation["evidence_id"])

            # job_assessments[*].features[*].evidence_ids
            for assessment in (result.get("job_assessments") or []):
                if not isinstance(assessment, dict):
                    continue
                for feature in (assessment.get("features") or []):
                    if not isinstance(feature, dict):
                        continue
                    for eid in (feature.get("evidence_ids") or []):
                        if eid is not None:
                            cited_ids.add(eid)

            if cited_ids:
                increment_evidence_citations(
                    db,
                    list(cited_ids),
                    f"functional_report:{report.id}",
                )
                db.commit()
        except Exception as cite_err:
            print(f"[functional_audit_task] Warning: Citation increment failed: {cite_err}")

        # output_data envelope is partial-write-ready: `stages_completed` +
        # `stage_1_output` + `stage_2_output` let a future follow-up write
        # Stage 1 at the 50% mark so pollers can read it mid-flight. The
        # top-level keys (report_id, features_compared, gaps_identified) are
        # preserved for existing consumers.
        output_data = {
            'report_id': report.id,
            'competitor_id': competitor_id,
            'competitor_name': competitor.competitor_name,
            'report_version': report.report_version,
            'features_compared': len(result['functional_comparison']),
            # Use the unified helper that prefers functional_comparison, falls
            # back to job_assessments. Pre-PR-#33 the gap count came from
            # gaps_deep_dive but the JTBD redesign moved gaps into the per-job
            # features array; reading the legacy field always returned 0 once
            # job maps existed.
            'gaps_identified': count_gaps(result),
            'stages_completed': ['stage_1', 'stage_2'],
            'stage_1_output': stage_1,
            'stage_2_output': stage_2,
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


@shared_task(bind=True, name='app.queue.tasks.aggregate_functional_audits_v2', soft_time_limit=300)
def aggregate_functional_audits_v2(self, audit_results: list, parent_job_id: int):
    """
    Callback task after all functional audits complete.

    Marks the parent orchestration job as successful. Landscape synthesis
    is no longer auto-triggered — the user should run unified_synthesis
    explicitly via synthesis_run_unified.

    Args:
        audit_results: List of results from functional_audit_task
        parent_job_id: The parent orchestration job ID
    """
    db = None
    try:
        db = SessionLocal()
        queue_service = QueueService(db)

        successful_audits = [r for r in audit_results if r and r.get('report_id')]
        failed_audits = len(audit_results) - len(successful_audits)

        print(f"[aggregate_functional_audits_v2] {len(successful_audits)} successful, {failed_audits} failed")

        queue_service.mark_success(parent_job_id, {
            'status': 'audits_completed',
            'successful_audits': len(successful_audits),
            'failed_audits': failed_audits,
            'audit_report_ids': [r['report_id'] for r in successful_audits],
        })

        return {
            'status': 'audits_completed',
            'successful_audits': len(successful_audits),
            'failed_audits': failed_audits,
        }

    except Exception as e:
        error_msg = str(e)
        error_tb = traceback.format_exc()
        print(f"[aggregate_functional_audits_v2] Error: {error_msg}")

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


@shared_task(bind=True, name='app.queue.tasks.run_competitive_analysis_v2', soft_time_limit=900)
def run_competitive_analysis_v2(self, job_id: int):
    """
    Orchestrate the V2 competitive analysis workflow.

    This task:
    1. Creates functional audit jobs for all enabled competitors
    2. Dispatches audits in parallel using Celery chord
    3. Chord callback marks the parent job complete

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

        # Dispatch parallel audits; callback marks the parent job complete
        workflow = chord(audit_tasks)(aggregate_functional_audits_v2.s(job_id))

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

@shared_task(bind=True, name='app.queue.tasks.internal_discovery_task', max_retries=2, default_retry_delay=60, soft_time_limit=600)
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
        user_id = job.user_id

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
            product_id=import_record.product_id,
            user_id=user_id,
            job_id=job.job_uuid
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

        # Pre-load active ProductJobs and pre-embed JTBD statements so we can
        # link each new theme to its best-matching job in one batch.
        from app.models.competitor_intelligence import ProductJob
        product_jobs = db.query(ProductJob).filter(
            ProductJob.product_id == import_record.product_id,
            ProductJob.status == "active",
        ).all()
        active_jobs_with_emb = [j for j in product_jobs if j.statement_embedding]

        winloss_jtbds = [t.jtbd_statement for t in output.winloss_themes if t.jtbd_statement]
        support_jtbds = [t.jtbd_statement for t in output.support_themes if t.jtbd_statement]
        winloss_embs: Dict[str, list] = {}
        support_embs: Dict[str, list] = {}
        if active_jobs_with_emb and (winloss_jtbds or support_jtbds):
            try:
                from app.services.embedding_service import generate_embeddings_batch
                if winloss_jtbds:
                    embs = generate_embeddings_batch(winloss_jtbds, input_type="document")
                    winloss_embs = dict(zip(winloss_jtbds, embs))
                if support_jtbds:
                    embs = generate_embeddings_batch(support_jtbds, input_type="document")
                    support_embs = dict(zip(support_jtbds, embs))
            except Exception as emb_err:
                print(f"[internal_discovery_task] Warning: JTBD embedding for themes failed: {emb_err}")

        def _match_job_for_jtbd(emb: Optional[list], threshold: float = 0.5) -> Optional[str]:
            if not emb:
                return None
            best_key = None
            best_sim = 0.0
            for j in active_jobs_with_emb:
                sim = _cosine_similarity(emb, j.statement_embedding)
                if sim > best_sim and sim > threshold:
                    best_sim = sim
                    best_key = j.job_id_key
            return best_key

        # Store win/loss themes
        for theme in output.winloss_themes:
            jtbd_emb = winloss_embs.get(theme.jtbd_statement) if theme.jtbd_statement else None
            matched_job_key = _match_job_for_jtbd(jtbd_emb)
            db_theme = WinLossTheme(
                import_id=import_id,
                product_id=import_record.product_id,
                theme_name=theme.theme_name,
                outcome=theme.outcome,
                competitor_name=theme.competitor_correlation,
                deal_count=theme.deal_count,
                total_value=theme.total_value,
                sample_reasons=theme.sample_reasons,
                feature_keywords=theme.feature_keywords,
                jtbd_statement=theme.jtbd_statement,
                job_id_key=matched_job_key,
            )
            db.add(db_theme)

        # Store support themes
        for theme in output.support_themes:
            jtbd_emb = support_embs.get(theme.jtbd_statement) if theme.jtbd_statement else None
            matched_job_key = _match_job_for_jtbd(jtbd_emb)
            db_theme = SupportTheme(
                import_id=import_id,
                product_id=import_record.product_id,
                theme_name=theme.theme_name,
                category=theme.category,
                ticket_count=theme.ticket_count,
                sample_subjects=theme.sample_subjects,
                feature_keywords=theme.feature_keywords,
                urgency_indicator=theme.urgency_indicator,
                jtbd_statement=theme.jtbd_statement,
                job_id_key=matched_job_key,
            )
            db.add(db_theme)

        # Bridge themes to evidence factbase
        from app.models.evidence import EvidenceType
        from app.services.evidence_service import create_evidence, resolve_competitor_by_name

        evidence_count = 0
        for theme in output.winloss_themes:
            # Build content from theme details
            content_parts = [f"Win/Loss Theme: {theme.theme_name}"]
            content_parts.append(f"Outcome: {theme.outcome}")
            content_parts.append(f"Deal count: {theme.deal_count}, Total value: ${theme.total_value:,.0f}")
            if theme.sample_reasons:
                content_parts.append("Sample reasons: " + "; ".join(theme.sample_reasons[:3]))
            if theme.jtbd_statement:
                content_parts.append(f"JTBD: {theme.jtbd_statement}")

            # Resolve competitor if correlated
            competitor_id = None
            if theme.competitor_correlation:
                matched = resolve_competitor_by_name(db, import_record.product_id, theme.competitor_correlation)
                if matched:
                    competitor_id = matched.id

            try:
                create_evidence(
                    db=db,
                    product_id=import_record.product_id,
                    evidence_type=EvidenceType.CUSTOMER_INTERVIEW,
                    title=f"Win/Loss: {theme.theme_name}",
                    content="\n".join(content_parts),
                    source_description=f"CRM import #{import_id}",
                    competitor_id=competitor_id,
                    tags=theme.feature_keywords[:5] if theme.feature_keywords else None,
                    created_by="crm_import",
                )
                evidence_count += 1
            except Exception as e:
                print(f"[internal_discovery_task] Evidence creation failed for winloss theme: {e}")

        for theme in output.support_themes:
            content_parts = [f"Support Theme: {theme.theme_name}"]
            content_parts.append(f"Category: {theme.category}, Urgency: {theme.urgency_indicator}")
            content_parts.append(f"Ticket count: {theme.ticket_count}")
            if theme.sample_subjects:
                content_parts.append("Sample subjects: " + "; ".join(theme.sample_subjects[:3]))
            if theme.jtbd_statement:
                content_parts.append(f"JTBD: {theme.jtbd_statement}")

            try:
                create_evidence(
                    db=db,
                    product_id=import_record.product_id,
                    evidence_type=EvidenceType.CUSTOMER_INTERVIEW,
                    title=f"Support: {theme.theme_name}",
                    content="\n".join(content_parts),
                    source_description=f"CRM import #{import_id}",
                    tags=theme.feature_keywords[:5] if theme.feature_keywords else None,
                    created_by="crm_import",
                )
                evidence_count += 1
            except Exception as e:
                print(f"[internal_discovery_task] Evidence creation failed for support theme: {e}")

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
            'evidence_created': evidence_count,
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


@shared_task(bind=True, name='app.queue.tasks.activity_insight_task', soft_time_limit=600)
def activity_insight_task(self, job_id: int):
    """
    Process CRM activity data to extract product insights.

    This task:
    1. Retrieves the parsed activity data from the import record
    2. Runs the ActivityInsightAgent for per-deal and aggregate analysis
    3. Stores DealActivityInsight and SupportActivityInsight records
    4. Updates the import status with analysis summary

    Args:
        job_id: The QueueJob ID for this task
    """
    from app.agents.activity_insight_agent import ActivityInsightAgent
    from app.models.activity_insights import (
        ActivityImport,
        DealActivityInsight,
        SupportActivityInsight
    )
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
        user_id = job.user_id
        queue_service.update_progress(job_id, 10.0, "Loading activity data...")

        # Extract job parameters
        input_data = job.input_data or {}
        import_id = input_data.get('import_id')
        parsed_data = input_data.get('parsed_data', {})

        if not import_id:
            raise ValueError("import_id is required in input_data")

        # Get import record
        import_record = db.query(ActivityImport).filter(
            ActivityImport.id == import_id
        ).first()

        if not import_record:
            raise ValueError(f"Activity import {import_id} not found")

        queue_service.update_progress(job_id, 20.0, "Initializing activity insight agent...")

        # Initialize LLM service and agent
        llm_service = LLMService()
        agent = ActivityInsightAgent(
            db=db,
            llm_service=llm_service,
            product_id=import_record.product_id,
            user_id=user_id,
            job_id=job.job_uuid
        )

        queue_service.update_progress(job_id, 30.0, "Analyzing deal activities...")

        # Run the agent with higher max_tokens for detailed activity analysis
        # The output includes multiple deal insights, each with quotes, keywords, etc.
        result = agent.execute(parsed_data, max_tokens=8000)

        queue_service.update_progress(job_id, 70.0, "Storing insights...")

        # Store deal activity insights
        for insight in result.get('deal_insights', []):
            db_insight = DealActivityInsight(
                import_id=import_id,
                product_id=import_record.product_id,
                deal_id=insight.get('deal_id'),
                deal_name=insight.get('deal_name'),
                deal_outcome=insight.get('deal_outcome', 'unknown'),
                deal_value=insight.get('deal_value'),
                competitor_mentioned=insight.get('competitor_mentioned'),
                theme_name=insight.get('theme_name'),
                category=insight.get('category', 'feature_gap'),
                sentiment=insight.get('sentiment', 'neutral'),
                urgency_level=insight.get('urgency_level', 'medium'),
                sample_quotes=insight.get('sample_quotes', []),
                activity_count=insight.get('activity_count', 1),
                feature_keywords=insight.get('feature_keywords', [])
            )
            db.add(db_insight)

        # Store support activity insights
        for insight in result.get('support_insights', []):
            db_insight = SupportActivityInsight(
                import_id=import_id,
                product_id=import_record.product_id,
                theme_name=insight.get('theme_name'),
                category=insight.get('category', 'feature_gap'),
                ticket_count=insight.get('ticket_count', 0),
                urgency_level=insight.get('urgency_level', 'medium'),
                sample_quotes=insight.get('sample_quotes', []),
                accounts_affected=insight.get('accounts_affected', []),
                feature_keywords=insight.get('feature_keywords', [])
            )
            db.add(db_insight)

        queue_service.update_progress(job_id, 90.0, "Finalizing...")

        # Update import record
        import_record.status = "completed"
        import_record.analysis_summary = result.get('analysis_summary')
        import_record.top_loss_themes = result.get('top_loss_themes', [])
        import_record.top_win_themes = result.get('top_win_themes', [])
        import_record.competitor_patterns = result.get('competitor_patterns', {})
        import_record.processed_at = datetime.utcnow()

        db.commit()

        # Mark job success
        queue_service.mark_success(job_id, {
            'import_id': import_id,
            'deal_insights_count': len(result.get('deal_insights', [])),
            'support_insights_count': len(result.get('support_insights', [])),
            'deals_analyzed': result.get('deals_analyzed', 0),
            'activities_analyzed': result.get('activities_analyzed', 0)
        })

        return {
            'status': 'completed',
            'import_id': import_id,
            'deal_insights': len(result.get('deal_insights', [])),
            'support_insights': len(result.get('support_insights', []))
        }

    except Exception as e:
        error_msg = str(e)
        error_tb = traceback.format_exc()
        print(f"[activity_insight_task] Error for job {job_id}: {error_msg}")

        if db:
            try:
                queue_service = QueueService(db)
                queue_service.mark_failure(job_id, error_msg, error_tb)

                # Update import record status
                input_data = queue_service.get_job(job_id).input_data or {}
                import_id = input_data.get('import_id')
                if import_id:
                    from app.models.activity_insights import ActivityImport
                    import_record = db.query(ActivityImport).filter(
                        ActivityImport.id == import_id
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


# ---------------------------------------------------------------------------
# JTBD Job Map Extraction
# ---------------------------------------------------------------------------

@shared_task(bind=True, name='app.queue.tasks.extract_job_map_task', max_retries=2, time_limit=300)
def extract_job_map_task(self, job_id: int) -> Dict[str, Any]:
    """
    Extract a JTBD job map from product information.

    This task:
    1. Loads the product and any existing evidence
    2. Runs the JobMapExtractorAgent to produce a job map
    3. Stores the job map on CIProduct and creates ProductJob records
    4. Generates embeddings for each job statement

    Args:
        job_id: QueueJob ID to process

    Returns:
        Dictionary with extraction results
    """
    from app.models.competitor_intelligence import CIProduct, ProductJob, JobType as JTBDJobType, JobImportance
    from app.models.evidence import Evidence
    from app.agents.job_map_extractor import JobMapExtractorAgent
    from app.services.embedding_service import generate_embeddings_batch

    db = None
    try:
        db = get_db()
        queue_service = QueueService(db)

        # Mark job as running
        job = queue_service.mark_running(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        input_data = job.input_data or {}
        product_id = job.product_id
        user_id = job.user_id
        guidance = input_data.get("guidance")

        if not product_id:
            raise ValueError("Product ID is required")

        queue_service.update_progress(job_id, 10.0, "Loading product data...")

        product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
        if not product:
            raise ValueError(f"Product {product_id} not found")

        # Build agent input
        agent_input = {
            "product_name": product.product_name,
            "product_description": product.product_description or "",
            "product_category": product.product_category or "",
            "structured_product_data": product.structured_product_data or {},
        }
        if guidance:
            agent_input["guidance"] = guidance

        # Load existing evidence for context
        queue_service.update_progress(job_id, 20.0, "Loading evidence...")
        evidence_items = (
            db.query(Evidence)
            .filter(Evidence.product_id == product_id)
            .order_by(Evidence.created_at.desc())
            .limit(20)
            .all()
        )
        if evidence_items:
            agent_input["evidence_summaries"] = [
                {
                    "title": e.title,
                    "content": e.content[:500],
                    "type": e.evidence_type.value,
                }
                for e in evidence_items
            ]

        # Run agent
        queue_service.update_progress(job_id, 30.0, "Running JTBD extraction...")
        llm_service = LLMService()
        agent = JobMapExtractorAgent(
            db=db,
            llm_service=llm_service,
            product_id=product_id,
            user_id=user_id,
            job_id=job.job_uuid,
        )
        result = agent.execute(agent_input)

        queue_service.update_progress(job_id, 70.0, "Saving job map...")

        # Store results on CIProduct
        product.target_customer_profile = result.get("target_customer_profile")
        job_map_data = result.get("job_map")
        product.job_map = job_map_data
        product.job_map_version = (product.job_map_version or 0) + 1
        product.job_map_last_updated = datetime.utcnow()

        # Create/update ProductJob records
        db.query(ProductJob).filter(ProductJob.product_id == product_id).delete()

        job_type_map = {
            "functional_jobs": JTBDJobType.FUNCTIONAL,
            "emotional_jobs": JTBDJobType.EMOTIONAL,
            "social_jobs": JTBDJobType.SOCIAL,
        }
        importance_map = {
            "critical": JobImportance.CRITICAL,
            "high": JobImportance.HIGH,
            "medium": JobImportance.MEDIUM,
            "low": JobImportance.LOW,
        }

        all_jobs = []
        for job_list_key in ["functional_jobs", "emotional_jobs", "social_jobs"]:
            for job_data in (job_map_data or {}).get(job_list_key, []):
                product_job = ProductJob(
                    product_id=product_id,
                    job_id_key=job_data["job_id"],
                    job_type=job_type_map[job_list_key],
                    statement=job_data["statement"],
                    desired_outcomes=job_data.get("desired_outcomes", []),
                    importance=importance_map.get(
                        job_data.get("importance", "medium"),
                        JobImportance.MEDIUM,
                    ),
                )
                db.add(product_job)
                all_jobs.append(product_job)

        db.flush()  # Get IDs before generating embeddings

        # Generate embeddings for all job statements
        queue_service.update_progress(job_id, 85.0, "Generating embeddings...")
        if all_jobs:
            statements = [j.statement for j in all_jobs]
            embeddings = generate_embeddings_batch(
                statements, input_type="document"
            )
            for job_obj, embedding in zip(all_jobs, embeddings):
                job_obj.statement_embedding = embedding

        db.commit()

        queue_service.update_progress(job_id, 95.0, "Finalizing...")

        output_data = {
            "product_id": product_id,
            "job_map_version": product.job_map_version,
            "jobs_created": len(all_jobs),
            "extraction_notes": result.get("extraction_notes"),
        }

        queue_service.mark_success(job_id, output_data=output_data)

        return {
            "product_id": product_id,
            "job_map_version": product.job_map_version,
            "jobs_created": len(all_jobs),
        }

    except Exception:
        error_msg = traceback.format_exc()
        if db:
            db.rollback()
            try:
                queue_service = QueueService(db)
                queue_service.mark_failure(job_id, error_msg)
            except Exception:
                pass
        raise

    finally:
        if db:
            db.close()


# ---------------------------------------------------------------------------
# Unified Synthesis (Phase 3)
# ---------------------------------------------------------------------------

def _build_unified_synthesis_markdown(
    product_name: str,
    output: dict,
    source_stats: dict,
) -> str:
    """Build a markdown report for a unified synthesis output.

    Sections: summary -> source stats -> job scorecard -> feature clusters ->
    opportunities -> high-impact items -> innovation whitespace.
    """
    parts: list = []
    parts.append(f"# Unified Synthesis Report — {product_name}\n")

    if output.get("analysis_summary"):
        parts.append("## Summary\n")
        parts.append(output["analysis_summary"].strip() + "\n")

    parts.append("## Source Stats\n")
    for key, val in (source_stats or {}).items():
        parts.append(f"- **{key}**: {val}")
    parts.append("")

    job_scorecard = output.get("job_scorecard") or []
    if job_scorecard:
        parts.append("## Job Scorecard\n")
        for entry in job_scorecard:
            parts.append(f"### {entry.get('job_id')} — {entry.get('job_statement', '')}")
            parts.append(
                f"- Importance: {entry.get('importance', 'medium')}; "
                f"our_score: {entry.get('our_score', 0)}/10; "
                f"rank: {entry.get('our_rank')}/{entry.get('total_ranked')}"
            )
            comp_scores = entry.get("competitor_scores") or {}
            if comp_scores:
                comp_str = ", ".join(f"{n}={s}" for n, s in comp_scores.items())
                parts.append(f"- Competitors: {comp_str}")
            if entry.get("best_in_class"):
                parts.append(f"- Best-in-class: {entry['best_in_class']}")
            parts.append(
                f"- Investment: **{entry.get('investment_recommendation', 'maintain')}** — "
                f"{entry.get('rationale', '')}"
            )
            parts.append("")

    cluster_matrix = output.get("feature_cluster_matrix") or []
    if cluster_matrix:
        parts.append("## Feature Clusters\n")
        for cluster in cluster_matrix:
            parts.append(f"### {cluster.get('job_id')} — {cluster.get('job_statement', '')}")
            for feat in cluster.get("features", []) or []:
                comps = ", ".join(feat.get("competitors_with_feature") or []) or "-"
                parts.append(
                    f"- **{feat.get('feature_name')}** "
                    f"({feat.get('prevalence', '?')}; us: {feat.get('our_status', '?')}; "
                    f"competitors: {comps})"
                )
            parts.append("")

    opportunities = output.get("opportunities") or []
    if opportunities:
        parts.append("## Opportunities\n")
        for opp in opportunities:
            parts.append(
                f"### [{opp.get('priority_score', 0):.1f}] {opp.get('opportunity_name', 'Opportunity')}"
            )
            sources = ", ".join(opp.get("sources") or [])
            parts.append(
                f"- Sources ({opp.get('source_count', 1)}): {sources}; "
                f"action: {opp.get('recommended_action', 'review')}"
            )
            if opp.get("job_id_key"):
                parts.append(
                    f"- Job: {opp['job_id_key']} (Δ satisfaction: "
                    f"{opp.get('job_satisfaction_delta', 0)}); "
                    f"investment: {opp.get('investment_tier', 'maintain')}"
                )
            if opp.get("opportunity_summary"):
                parts.append(f"- {opp['opportunity_summary']}")
            if opp.get("jtbd_statement"):
                parts.append(f"- JTBD: {opp['jtbd_statement']}")
            parts.append("")

    high_impact = output.get("high_impact_items") or []
    if high_impact:
        parts.append("## High-Impact Items\n")
        for item in sorted(high_impact, key=lambda x: x.get("rank", 99)):
            tag = item.get("type", "item").upper()
            parts.append(
                f"### [{tag}] #{item.get('rank', '?')} {item.get('title', '')}"
            )
            if item.get("description"):
                parts.append(f"- {item['description']}")
            if item.get("market_gravity"):
                parts.append(f"- Market gravity: {item['market_gravity']}")
            if item.get("competitors"):
                parts.append(f"- Competitors: {', '.join(item['competitors'])}")
            parts.append("")

    if output.get("innovation_whitespace"):
        parts.append("## Innovation Whitespace\n")
        parts.append(output["innovation_whitespace"].strip() + "\n")

    return "\n".join(parts)


@shared_task(
    bind=True,
    name='app.queue.tasks.unified_synthesis_task',
    max_retries=2,
    default_retry_delay=60,
    soft_time_limit=1200,
)
def unified_synthesis_task(self, job_id: int):
    """Phase 3 unified synthesis: replaces landscape + opportunity synthesis.

    Pulls signals from configured source types, runs UnifiedSynthesisAgent,
    persists a SynthesisReport + SynthesizedOpportunity rows, and optionally
    auto-generates Ideas above the configured priority threshold.
    """
    from app.agents.unified_synthesis_agent import UnifiedSynthesisAgent
    from app.models.synthesis import (
        SynthesisConfig,
        SynthesisReport,
        SynthesisRun,
        SynthesizedOpportunity,
    )
    from app.models.competitive_reports import CompetitorFunctionalReport
    from app.models.evidence import Evidence, COMPETITIVE_EVIDENCE_TYPES
    from app.models.idea import Idea, IdeaStatus, SourceType
    from app.models.vote import Vote
    from app.services.internal_theme_merger import InternalThemeMergerService
    from app.services.llm_service import LLMService
    from app.services.scoring_defaults import DEFAULT_SCORING_WEIGHTS
    from sqlalchemy import desc, func as sql_func

    db = None
    try:
        db = SessionLocal()
        queue_service = QueueService(db)

        job = queue_service.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        queue_service.mark_running(job_id)
        queue_service.update_progress(job_id, 5.0, "Loading synthesis configuration...")

        product_id = job.product_id
        if not product_id:
            raise ValueError("product_id is required for unified synthesis")

        product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
        if not product:
            raise ValueError(f"Product {product_id} not found")

        # Step 1: Load (or create default) SynthesisConfig
        # Defaults come from DEFAULT_* constants in app.models.synthesis.
        from app.models.synthesis import (
            DEFAULT_INCLUDED_SOURCE_TYPES,
            DEFAULT_IDEA_PRIORITY_THRESHOLD,
        )
        config = db.query(SynthesisConfig).filter(
            SynthesisConfig.product_id == product_id
        ).first()
        if not config:
            config = SynthesisConfig(
                product_id=product_id,
                included_source_types=list(DEFAULT_INCLUDED_SOURCE_TYPES),
                # auto_generate_ideas + idea_priority_threshold inherit model defaults
            )
            db.add(config)
            db.flush()

        included_sources = list(
            config.included_source_types or list(DEFAULT_INCLUDED_SOURCE_TYPES)
        )
        included_set = {s.lower() for s in included_sources}

        # Step 2: Load included competitors (synthesis_included == True)
        included_competitors = db.query(ProductCompetitor).filter(
            ProductCompetitor.product_id == product_id,
            ProductCompetitor.status == "active",
            ProductCompetitor.synthesis_included == True,  # noqa: E712
        ).all()

        # Step 3: Auto-trigger missing audits for synthesis_included competitors.
        # A competitor is considered audited if it has an existing
        # CompetitorFunctionalReport, regardless of audit_status (older reports
        # may predate the status field). We dispatch but do NOT block — the user
        # re-runs once audits complete. Synchronous polling inside a Celery task
        # can deadlock workers.
        from app.models.competitive_reports import CompetitorFunctionalReport
        competitors_with_reports = {
            r[0] for r in db.query(CompetitorFunctionalReport.product_competitor_id)
            .filter(CompetitorFunctionalReport.product_id == product_id).all()
        }
        triggered_audit_jobs = []
        if "competitive" in included_set:
            for comp in included_competitors:
                has_report = comp.id in competitors_with_reports
                if not has_report and comp.audit_status != "completed":
                    audit_job = queue_service.create_job(
                        job_type=JobType.FUNCTIONAL_AUDIT,
                        input_data={"competitor_id": comp.id},
                        product_id=product_id,
                        user_id=job.user_id,
                        parent_job_id=job_id,
                    )
                    db.commit()
                    try:
                        result = functional_audit_task.delay(audit_job.id)
                        queue_service.mark_queued(audit_job.id, result.id)
                        triggered_audit_jobs.append(audit_job.id)
                    except Exception as dispatch_err:
                        print(
                            f"[unified_synthesis_task] Failed to dispatch audit for "
                            f"competitor {comp.id}: {dispatch_err}"
                        )

            if triggered_audit_jobs:
                # Refuse to proceed; user re-runs once audits finish.
                msg = (
                    f"Auto-triggered {len(triggered_audit_jobs)} missing competitor "
                    f"audit(s). Re-run unified synthesis once those jobs complete."
                )
                queue_service.mark_success(
                    job_id,
                    {
                        "status": "deferred",
                        "triggered_audit_job_ids": triggered_audit_jobs,
                        "message": msg,
                    },
                )
                return {
                    "status": "deferred",
                    "triggered_audit_job_ids": triggered_audit_jobs,
                }

        queue_service.update_progress(job_id, 15.0, "Loading product context...")

        # Step 4: Build product_context including job_map
        product_context: Dict[str, Any] = {
            "product_name": product.product_name,
            "product_description": product.product_description,
            "product_category": product.product_category,
        }
        if product.target_customer_profile:
            product_context["target_customer_profile"] = product.target_customer_profile
        if product.job_map:
            product_context["job_map"] = product.job_map

        features = db.query(ProductFeature).filter(
            ProductFeature.product_id == product_id,
            ProductFeature.status == "active",
        ).limit(15).all()
        if features:
            product_context["core_features"] = [f.feature_name for f in features]

        queue_service.update_progress(job_id, 25.0, "Gathering competitive data...")

        # Step 5a: COMPETITIVE — load functional reports for included competitors
        competitor_reports: List[Dict[str, Any]] = []
        source_competitor_report_ids: List[int] = []
        included_competitor_ids = [c.id for c in included_competitors]

        if "competitive" in included_set and included_competitor_ids:
            functional_reports = db.query(CompetitorFunctionalReport).filter(
                CompetitorFunctionalReport.product_id == product_id,
                CompetitorFunctionalReport.product_competitor_id.in_(included_competitor_ids),
            ).all()

            # Index competitor-linked evidence (filter to competitive types)
            comp_evidence_q = db.query(Evidence).filter(
                Evidence.product_id == product_id,
                Evidence.competitor_id.in_(included_competitor_ids),
            ).order_by(Evidence.created_at.desc()).all()
            evidence_by_competitor: Dict[int, List[Evidence]] = {}
            for ev in comp_evidence_q:
                if ev.evidence_type in COMPETITIVE_EVIDENCE_TYPES:
                    evidence_by_competitor.setdefault(ev.competitor_id, []).append(ev)

            for report in functional_reports:
                comp = next(
                    (c for c in included_competitors if c.id == report.product_competitor_id),
                    None,
                )
                comp_name = (
                    comp.competitor_name if comp
                    else f"Competitor {report.product_competitor_id}"
                )
                ev_list = evidence_by_competitor.get(report.product_competitor_id, [])[:10]
                competitor_reports.append({
                    "competitor_name": comp_name,
                    "audit": {
                        "competitor_context": report.competitor_context,
                        "functional_comparison": report.functional_comparison,
                        "gaps_deep_dive": report.gaps_deep_dive,
                        "technical_constraints": report.technical_constraints,
                        "job_assessments": report.job_assessments,
                    },
                    "evidence": [{
                        "id": ev.id,
                        "title": ev.title,
                        "evidence_type": ev.evidence_type.value if ev.evidence_type else None,
                        "source_url": ev.source_url,
                        "source_description": ev.source_description,
                    } for ev in ev_list],
                })
                source_competitor_report_ids.append(report.id)

        queue_service.update_progress(job_id, 40.0, "Gathering customer ideas...")

        # Step 5b: CUSTOMER — top 50 ACCEPTED ideas by vote count
        customer_ideas: List[Dict[str, Any]] = []
        if "customer" in included_set:
            vote_counts = db.query(
                Vote.idea_id,
                sql_func.sum(Vote.vote_value).label("vote_count"),
            ).group_by(Vote.idea_id).subquery()

            ideas_with_votes = db.query(
                Idea,
                sql_func.coalesce(vote_counts.c.vote_count, 0).label("vote_count"),
            ).outerjoin(vote_counts, Idea.id == vote_counts.c.idea_id).filter(
                Idea.product_id == product_id,
                Idea.status == IdeaStatus.ACCEPTED,
            ).order_by(desc("vote_count")).limit(50).all()

            for idea, votes in ideas_with_votes:
                customer_ideas.append({
                    "id": idea.id,
                    "title": idea.title,
                    "description": idea.what_description or "",
                    "vote_count": int(votes) if votes else 0,
                    "status": idea.status.value if idea.status else "unknown",
                    "jtbd_statement": getattr(idea, "jtbd_statement", None),
                    "job_id_key": getattr(idea, "job_id_key", None),
                })

        queue_service.update_progress(job_id, 55.0, "Gathering internal feedback...")

        # Step 5c: INTERNAL — merged win/loss + support themes
        winloss_themes: List[Dict[str, Any]] = []
        support_themes: List[Dict[str, Any]] = []
        if "internal" in included_set:
            merger = InternalThemeMergerService(db)
            merged = merger.merge_internal_evidence(product_id)
            internal_data = merger.to_synthesis_format(merged)
            winloss_themes = internal_data.get("winloss_themes", []) or []
            support_themes = internal_data.get("support_themes", []) or []

        queue_service.update_progress(job_id, 65.0, "Gathering evidence/research...")

        # Step 5d: EVIDENCE — non-competitive Evidence records
        evidence_items: List[Dict[str, Any]] = []
        if "evidence" in included_set:
            all_evidence = db.query(Evidence).filter(
                Evidence.product_id == product_id,
            ).order_by(Evidence.created_at.desc()).limit(100).all()
            for ev in all_evidence:
                if ev.evidence_type in COMPETITIVE_EVIDENCE_TYPES:
                    continue  # already routed via competitive enrichment
                evidence_items.append({
                    "id": ev.id,
                    "evidence_id": ev.id,
                    "title": ev.title,
                    "evidence_type": ev.evidence_type.value if ev.evidence_type else None,
                    "content": ev.content,
                    "source_url": ev.source_url,
                    "source_description": ev.source_description,
                    "jtbd_statement": ev.jtbd_statement,
                    "job_id_key": None,
                })

        queue_service.update_progress(job_id, 70.0, "Running unified synthesis agent...")

        # Step 6: Compute effective scoring weights (defaults ∪ overrides)
        effective_weights: Dict[str, Any] = {
            k: (v.copy() if isinstance(v, dict) else v)
            for k, v in DEFAULT_SCORING_WEIGHTS.items()
        }
        overrides = config.scoring_weight_overrides or {}
        for key, val in overrides.items():
            if isinstance(val, dict) and isinstance(effective_weights.get(key), dict):
                effective_weights[key] = {**effective_weights[key], **val}
            else:
                effective_weights[key] = val

        # Sanity check: at least one source produced data
        has_data = bool(
            competitor_reports or customer_ideas or winloss_themes
            or support_themes or evidence_items
        )
        if not has_data:
            raise ValueError(
                "No data available for unified synthesis. Configure source types "
                "and ensure at least one source has data."
            )

        # Step 7: Run agent
        llm_service = LLMService()
        agent = UnifiedSynthesisAgent(
            db=db,
            llm_service=llm_service,
            product_id=product_id,
            user_id=job.user_id,
            job_id=job.job_uuid,
            scoring_weights=effective_weights,
        )

        agent_input = {
            "product_context": product_context,
            "included_source_types": included_sources,
            "competitor_reports": competitor_reports,
            "customer_ideas": customer_ideas,
            "winloss_themes": winloss_themes,
            "support_themes": support_themes,
            "evidence_items": evidence_items,
        }
        # JTBD synthesis output can be verbose: job_scorecard (per job) +
        # feature_cluster_matrix (nested by job) + opportunities with
        # multi-source evidence blobs. With 10+ jobs × 2-3 competitors,
        # 20000 tokens gives enough headroom.
        result = agent.execute(agent_input, max_tokens=20000)

        queue_service.update_progress(job_id, 85.0, "Persisting synthesis report...")

        # Step 8: Persist SynthesisReport
        previous_report = db.query(SynthesisReport).filter(
            SynthesisReport.product_id == product_id,
        ).order_by(desc(SynthesisReport.report_version)).first()
        next_version = (previous_report.report_version + 1) if previous_report else 1

        source_stats = {
            "competitor_count": len(included_competitors),
            "competitor_report_count": len(competitor_reports),
            "idea_count": len(customer_ideas),
            "winloss_count": len(winloss_themes),
            "support_count": len(support_themes),
            "evidence_count": len(evidence_items),
        }

        markdown_md = _build_unified_synthesis_markdown(
            product.product_name, result, source_stats,
        )

        synthesis_report = SynthesisReport(
            product_id=product_id,
            report_version=next_version,
            included_source_types=included_sources,
            job_scorecard=result.get("job_scorecard"),
            feature_cluster_matrix=result.get("feature_cluster_matrix"),
            opportunities=result.get("opportunities"),
            high_impact_items=result.get("high_impact_items"),
            innovation_whitespace=result.get("innovation_whitespace"),
            analysis_summary=result.get("analysis_summary"),
            source_stats=source_stats,
            included_competitor_ids=included_competitor_ids,
            source_competitor_report_ids=source_competitor_report_ids,
            report_content_md=markdown_md,
            queue_job_id=job_id,
        )
        db.add(synthesis_report)
        db.flush()

        # Step 9: Persist SynthesizedOpportunity rows.
        # NOTE: synthesized_opportunities.synthesis_run_id is NOT NULL, so we
        # also create a lightweight SynthesisRun for backward-compat consumers.
        backing_run = SynthesisRun(
            product_id=product_id,
            status="completed",
            sources_used=included_sources,
            source_snapshot=source_stats,
            analysis_summary=result.get("analysis_summary"),
            job_uuid=job.job_uuid,
            completed_at=datetime.utcnow(),
        )
        db.add(backing_run)
        db.flush()

        opportunities_out = result.get("opportunities") or []
        # Pre-compute JTBD embeddings (single batch call)
        jtbd_texts = [
            o.get("jtbd_statement") for o in opportunities_out if o.get("jtbd_statement")
        ]
        jtbd_emb_map: Dict[str, list] = {}
        if jtbd_texts:
            try:
                from app.services.embedding_service import generate_embeddings_batch
                embs = generate_embeddings_batch(jtbd_texts, input_type="document")
                jtbd_emb_map = dict(zip(jtbd_texts, embs))
            except Exception as emb_err:
                print(
                    f"[unified_synthesis_task] Warning: opportunity JTBD embedding failed: "
                    f"{emb_err}"
                )

        # Keyed by opportunity_name so the auto-idea-gen loop below can backfill
        # linked_idea_id when an idea is created from a given opportunity.
        opp_rows_by_name: Dict[str, SynthesizedOpportunity] = {}
        for opp in opportunities_out:
            db_opp = SynthesizedOpportunity(
                synthesis_run_id=backing_run.id,
                synthesis_report_id=synthesis_report.id,
                product_id=product_id,
                opportunity_name=opp.get("opportunity_name", "Opportunity"),
                opportunity_summary=opp.get("opportunity_summary"),
                priority_score=float(opp.get("priority_score", 0.0)),
                source_count=int(opp.get("source_count", 1)),
                sources=opp.get("sources") or [],
                competitive_evidence=opp.get("competitive_evidence"),
                customer_evidence=opp.get("customer_evidence"),
                internal_evidence=opp.get("internal_evidence"),
                evidence_signals=opp.get("evidence_signals"),
                recommended_action=opp.get("recommended_action"),
                feature_keywords=opp.get("feature_keywords") or [],
                jtbd_statement=opp.get("jtbd_statement"),
                jtbd_embedding=jtbd_emb_map.get(opp.get("jtbd_statement") or ""),
                job_id_key=opp.get("job_id_key"),
                investment_tier=opp.get("investment_tier"),
                job_satisfaction_delta=opp.get("job_satisfaction_delta"),
            )
            db.add(db_opp)
            opp_rows_by_name[db_opp.opportunity_name] = db_opp

        db.commit()
        db.refresh(synthesis_report)

        # Increment citation counts for evidence referenced in this synthesis report
        try:
            from app.services.evidence_service import increment_evidence_citations

            cited_ids: set = set()

            # job_scorecard[*].evidence_ids
            for entry in (synthesis_report.job_scorecard or []):
                if not isinstance(entry, dict):
                    continue
                for eid in (entry.get("evidence_ids") or []):
                    if eid is not None:
                        cited_ids.add(eid)

            # opportunities[*].evidence_signals.items[*].evidence_id
            for opp in (synthesis_report.opportunities or []):
                if not isinstance(opp, dict):
                    continue
                signals = opp.get("evidence_signals") or {}
                if isinstance(signals, dict):
                    for item in (signals.get("items") or []):
                        if isinstance(item, dict) and item.get("evidence_id") is not None:
                            cited_ids.add(item["evidence_id"])

            if cited_ids:
                increment_evidence_citations(
                    db,
                    list(cited_ids),
                    f"synthesis_report:{synthesis_report.id}",
                )
                db.commit()
        except Exception as cite_err:
            print(f"[unified_synthesis_task] Warning: Citation increment failed: {cite_err}")

        queue_service.update_progress(job_id, 95.0, "Auto-generating ideas (if enabled)...")

        # Step 10: Auto-generate ideas above threshold
        ideas_generated = 0
        triage_jobs_created = 0
        if config.auto_generate_ideas and opportunities_out:
            # Threshold is 0.0-1.0 in config; opportunity priority_score is 0-100
            score_threshold = float(
                config.idea_priority_threshold or DEFAULT_IDEA_PRIORITY_THRESHOLD
            ) * 100.0
            for opp in opportunities_out:
                if float(opp.get("priority_score", 0.0)) < score_threshold:
                    continue
                feature_name = opp.get("opportunity_name", "Opportunity")
                # Dedup by name + source
                existing_idea = db.query(Idea).filter(
                    Idea.product_id == product_id,
                    Idea.title == feature_name[:255],
                    Idea.source_type == SourceType.COMPETITOR_AUTOMATED,
                ).first()
                if existing_idea:
                    continue

                competitors_with = _extract_competitor_names(opp.get("competitive_evidence"))
                source_metadata = {
                    "synthesis_report_id": synthesis_report.id,
                    "synthesis_report_version": synthesis_report.report_version,
                    "feature_name": feature_name,
                    "priority_score": opp.get("priority_score"),
                    "sources": opp.get("sources") or [],
                    "job_id_key": opp.get("job_id_key"),
                    "investment_tier": opp.get("investment_tier"),
                    "competitors_with_feature": competitors_with,
                    "competitor_names": competitors_with,
                }

                use_case_lines = ["Synthesized from multiple sources:"]
                for src in (opp.get("sources") or []):
                    use_case_lines.append(f"- {src}")

                new_idea = Idea(
                    title=feature_name[:255],
                    what_description=opp.get("opportunity_summary") or feature_name,
                    why_description=(opp.get("recommended_action") or "")[:1000],
                    use_case_description="\n".join(use_case_lines),
                    product_id=product_id,
                    source_type=SourceType.COMPETITOR_AUTOMATED,
                    source_metadata=source_metadata,
                    status=IdeaStatus.PENDING,
                    is_active=False,
                    auto_categorized=False,
                )
                db.add(new_idea)
                db.flush()
                ideas_generated += 1

                # Backfill linked_idea_id on the matching opportunity row so
                # downstream views can render a "created as Idea #N" badge.
                # Use a direct UPDATE rather than attribute assignment because
                # the intervening queue_service.create_job() commit was silently
                # dropping in-session attribute changes in this code path.
                matching_opp = opp_rows_by_name.get(feature_name)
                if matching_opp is not None:
                    db.query(SynthesizedOpportunity).filter(
                        SynthesizedOpportunity.id == matching_opp.id
                    ).update(
                        {SynthesizedOpportunity.linked_idea_id: new_idea.id},
                        synchronize_session=False,
                    )

                triage_job = queue_service.create_job(
                    job_type=JobType.IDEA_TRIAGE,
                    input_data={"idea_id": new_idea.id},
                    product_id=product_id,
                    parent_job_id=job_id,
                    user_id=job.user_id,
                )
                db.commit()
                try:
                    triage_idea_task.delay(triage_job.id)
                    triage_jobs_created += 1
                except Exception as dispatch_err:
                    print(
                        f"[unified_synthesis_task] Triage dispatch failed: {dispatch_err}"
                    )

        output_data = {
            "synthesis_report_id": synthesis_report.id,
            "report_version": synthesis_report.report_version,
            "included_sources": included_sources,
            "source_stats": source_stats,
            "opportunities_count": len(opportunities_out),
            "ideas_generated": ideas_generated,
            "triage_jobs_created": triage_jobs_created,
        }
        queue_service.mark_success(job_id, output_data)
        return output_data

    except Exception as e:
        error_msg = str(e)
        error_tb = traceback.format_exc()
        print(f"[unified_synthesis_task] Error for job {job_id}: {error_msg}")
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