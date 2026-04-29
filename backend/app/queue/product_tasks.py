"""Celery tasks for product analysis and worker health checks.

Houses ``analyze_product_task`` (runs ProductAnalyzerAgent) and the trivial
``health_check`` task used to verify Celery connectivity.
"""

import traceback
from typing import Dict, Any
from celery import shared_task
from datetime import datetime

from app.models.competitor_intelligence import (
    CIProduct, ProductAnalysisHistory, ProductFeature,
)
from app.services.queue_service import QueueService
from app.services.llm_service import LLMService
from app.agents.product_analyzer import ProductAnalyzerAgent
from app.queue.helpers import get_db, _fetch_source_urls


@shared_task(bind=True, name='app.queue.product_tasks.analyze_product_task', soft_time_limit=300)
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


@shared_task(bind=True, name='app.queue.product_tasks.health_check', soft_time_limit=60)
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
