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
from app.queue.helpers import get_db, fail_job


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
    from app.models.competitor_intelligence import (
        CIProduct, ProductJob, JobType as JTBDJobType, JobImportance,
        JOB_PROVENANCE_PRODUCT,
    )
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
                        # Inferred from the product's own description. Recording it is
                        # what lets the map-health metric show how much of the map is
                        # self-referential — jobs derived from what the product already
                        # does, which make coverage scores near-tautological.
                        provenance={
                            "type": JOB_PROVENANCE_PRODUCT,
                            "source_ref": f"product:{product_id}",
                            "added_at": datetime.now(timezone.utc).isoformat(),
                        },
                        statement_updated_at=datetime.now(timezone.utc),
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
            # Web UI path: store as pending, PM reviews before committing.
            # Do NOT update job_map_last_updated here — only update it when the PM applies.
            product.pending_job_map = job_map_data
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
        fail_job(db, job_id, error_msg, task_name="extract_job_map_task")
        raise

    finally:
        if db:
            db.close()


# ---------------------------------------------------------------------------
# Self-Assessment
# ---------------------------------------------------------------------------

@shared_task(bind=True, name='app.queue.jtbd_tasks.self_assessment_task', max_retries=2, time_limit=600)
def self_assessment_task(self, job_id: int) -> Dict[str, Any]:
    """Score our own product against each job in its map.

    Runs once per product rather than inside every competitor audit, where the same job
    could otherwise carry a different "our" score in each report.

    Pulls in whatever independent evidence exists — evidence records, support themes,
    win/loss themes — because the job map is generated from the product description, so an
    assessment using only that description is checking whether the product does what it
    says it does. The result records whether any independent evidence was available, since
    that governs how much weight the scores can carry.

    Args:
        job_id: QueueJob ID to process

    Returns:
        Dictionary with assessment results
    """
    from app.models.competitor_intelligence import CIProduct, ProductJob
    from app.models.competitive_reports import ProductSelfAssessment
    from app.models.evidence import Evidence
    from app.models.internal_feedback import SupportTheme, WinLossTheme
    from app.agents.self_assessment_agent import SelfAssessmentAgent

    db = None
    try:
        db = get_db()
        queue_service = QueueService(db)

        job = queue_service.mark_running(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        product_id = job.product_id
        if not product_id:
            raise ValueError("Product ID is required")

        queue_service.update_progress(job_id, 10.0, "Loading product and job map...")

        product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
        if not product:
            raise ValueError(f"Product {product_id} not found")

        jobs = db.query(ProductJob).filter(
            ProductJob.product_id == product_id,
            ProductJob.status == "active",
        ).all()
        if not jobs:
            raise ValueError(
                "No job map to assess against. Generate or author a job map first."
            )

        queue_service.update_progress(job_id, 25.0, "Gathering evidence...")

        evidence = db.query(Evidence).filter(
            Evidence.product_id == product_id
        ).order_by(Evidence.created_at.desc()).limit(50).all()
        support_themes = db.query(SupportTheme).filter(
            SupportTheme.product_id == product_id
        ).all()
        win_loss_themes = db.query(WinLossTheme).filter(
            WinLossTheme.product_id == product_id
        ).all()

        agent_input = {
            "product_name": product.product_name,
            "product_description": product.product_description,
            "job_map": [
                {
                    "job_id": j.job_id_key,
                    "statement": j.statement,
                    "importance": j.importance.value if j.importance else "medium",
                    "desired_outcomes": j.desired_outcomes or [],
                }
                for j in jobs
            ],
            "evidence": [
                {"id": e.id, "title": e.title, "content": e.content} for e in evidence
            ],
            # jtbd_statement rather than a description field — the themes carry an
            # extracted job statement, which is the form this assessment reasons in.
            # job_id_key is already set by import-time linkage, so the agent is told
            # which job each theme bears on rather than having to infer it.
            "support_themes": [
                {
                    "theme_name": t.theme_name,
                    "jtbd_statement": t.jtbd_statement,
                    "category": t.category,
                    "ticket_count": t.ticket_count,
                    "urgency": t.urgency_indicator,
                    "job_id_key": t.job_id_key,
                }
                for t in support_themes
            ],
            "win_loss_themes": [
                {
                    "theme_name": t.theme_name,
                    "jtbd_statement": t.jtbd_statement,
                    "outcome": t.outcome,
                    "deal_count": t.deal_count,
                    "job_id_key": t.job_id_key,
                }
                for t in win_loss_themes
            ],
        }

        queue_service.update_progress(job_id, 40.0, "Assessing coverage per job...")

        agent = SelfAssessmentAgent(db=db, llm_service=LLMService(db=db))
        result = agent.execute(agent_input, product_id=product_id, user_id=job.user_id)

        queue_service.update_progress(job_id, 85.0, "Storing assessment...")

        # The agent is told to report evidence_based itself, but whether independent
        # evidence was actually supplied is a fact we already know — so it is recorded
        # here rather than trusted from the model.
        had_evidence = bool(evidence or support_themes or win_loss_themes)

        previous = db.query(ProductSelfAssessment).filter(
            ProductSelfAssessment.product_id == product_id
        ).order_by(ProductSelfAssessment.assessment_version.desc()).first()

        assessment = ProductSelfAssessment(
            product_id=product_id,
            assessment_version=(previous.assessment_version + 1) if previous else 1,
            job_map_version=product.job_map_version,
            job_assessments=result.get("job_assessments"),
            evidence_based=had_evidence,
            assessment_summary=result.get("assessment_summary"),
            queue_job_id=job_id,
        )
        db.add(assessment)
        db.commit()
        db.refresh(assessment)

        queue_service.update_progress(job_id, 92.0, "Refreshing competitor positions...")

        # Position is a join across this assessment and each competitor audit, so a new
        # assessment changes every stored position. Refresh them here rather than
        # requiring a re-audit: the join is free, and leaving it to a re-audit would mean
        # positions silently lagged until someone remembered to re-run every competitor.
        reports_refreshed = _refresh_competitor_positions(db, product_id, assessment)
        db.commit()

        output_data = {
            "product_id": product_id,
            "assessment_id": assessment.id,
            "assessment_version": assessment.assessment_version,
            "jobs_assessed": len(result.get("job_assessments") or []),
            "evidence_based": had_evidence,
            "competitor_reports_refreshed": reports_refreshed,
        }
        queue_service.mark_success(job_id, output_data=output_data)

        return output_data

    except Exception:
        error_msg = traceback.format_exc()
        if db:
            db.rollback()
        fail_job(db, job_id, error_msg, task_name="self_assessment_task")
        raise

    finally:
        if db:
            db.close()


def _refresh_competitor_positions(db, product_id: int, assessment) -> int:
    """Re-derive stored positions on every competitor report for a product.

    Position needs our score and theirs. Our side now comes from a self-assessment that
    re-runs independently of any audit, so a new assessment invalidates every stored
    position — without this, they would stay stale until each competitor was re-audited,
    which costs an LLM run per competitor and is easy to forget.

    Only the derived fields move. Competitor scores are facts from the audit and are left
    alone, and human review state is carried through by passing each report's current
    assessments as their own previous — a refresh must never discard a PM's override.
    """
    from app.models.competitive_reports import CompetitorFunctionalReport
    from app.utils.job_position import enrich_assessments

    self_scores = {
        entry.get("job_id"): entry.get("score")
        for entry in (assessment.job_assessments or [])
        if isinstance(entry, dict) and entry.get("job_id")
    }

    reports = db.query(CompetitorFunctionalReport).filter(
        CompetitorFunctionalReport.product_id == product_id
    ).all()

    refreshed = 0
    for report in reports:
        if not report.job_assessments:
            continue
        report.job_assessments = enrich_assessments(
            report.job_assessments,
            previous_assessments=report.job_assessments,
            self_scores=self_scores,
            self_assessment_version=assessment.assessment_version,
        )
        refreshed += 1

    return refreshed
