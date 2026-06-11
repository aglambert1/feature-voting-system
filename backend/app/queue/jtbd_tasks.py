"""Celery task for JTBD job map extraction.

Houses ``extract_job_map_task`` which runs JobMapExtractorAgent and persists
the resulting job map onto CIProduct + per-job ProductJob rows (with
statement_embedding populated for semantic linkage).
"""

import traceback
from typing import Dict, Any
from celery import shared_task
from datetime import datetime, timezone

from app.services.queue_service import QueueService
from app.services.llm_service import LLMService
from app.queue.helpers import get_db


# ---------------------------------------------------------------------------
# JTBD Job Map Extraction
# ---------------------------------------------------------------------------

@shared_task(bind=True, name='app.queue.jtbd_tasks.extract_job_map_task', max_retries=2, time_limit=300)
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
        skip_review = input_data.get("skip_review", False)

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

        product.target_customer_profile = result.get("target_customer_profile")
        job_map_data = result.get("job_map")

        if skip_review:
            # MCP / programmatic path: commit directly to ProductJob rows (all-or-nothing)
            product.job_map = job_map_data
            product.job_map_version = (product.job_map_version or 0) + 1
            product.job_map_last_updated = datetime.now(timezone.utc)

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

            db.flush()
            queue_service.update_progress(job_id, 85.0, "Generating embeddings...")
            if all_jobs:
                statements = [j.statement for j in all_jobs]
                embeddings = generate_embeddings_batch(statements, input_type="document")
                for job_obj, embedding in zip(all_jobs, embeddings):
                    job_obj.statement_embedding = embedding
        else:
            # Web UI path: store as pending, PM reviews before committing
            product.pending_job_map = job_map_data
            product.job_map_last_updated = datetime.now(timezone.utc)
            queue_service.update_progress(job_id, 90.0, "Pending PM review...")

        db.commit()

        queue_service.update_progress(job_id, 95.0, "Finalizing...")

        if skip_review:
            pending_status = "committed"
            job_count = len(all_jobs)
        else:
            pending_status = "pending_review"
            # Count jobs in the pending map
            job_count = sum(
                len((job_map_data or {}).get(k, []))
                for k in ["functional_jobs", "emotional_jobs", "social_jobs", "jobs"]
            )

        output_data = {
            "product_id": product_id,
            "status": pending_status,
            "job_map_version": product.job_map_version,
            "jobs_created": job_count,
            "extraction_notes": result.get("extraction_notes"),
        }

        queue_service.mark_success(job_id, output_data=output_data)

        return {
            "product_id": product_id,
            "status": pending_status,
            "job_map_version": product.job_map_version,
            "jobs_created": job_count,
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
