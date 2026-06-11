"""
Job Map API endpoints for JTBD management.

Provides REST endpoints for managing a product's JTBD job map,
target customer profile, and individual jobs.
"""

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.utils.celery_utils import send_celery_task as send_task
from app.models.user import User
from sqlalchemy import func as sa_func
from app.models.competitor_intelligence import (
    CIProduct, ProductJob, JobType, JobImportance,
    ProductPermissionLevel,
)
from app.models.idea import Idea
from app.models.evidence import Evidence
from app.models.internal_feedback import WinLossTheme, SupportTheme
from app.models.queue import JobType as QueueJobType
from app.models.pm_review import PMReviewQueue, ReviewQueueType, ReviewQueueStatus
from app.schemas.job_map import (
    JobCreateRequest, JobUpdateRequest, JobResponse, JobMapResponse,
    TargetCustomerProfile,
)
from app.services.permission_service import PermissionService
from app.services.queue_service import QueueService
from app.utils.security import get_current_active_user

router = APIRouter(
    prefix="/product-intelligence/products",
    tags=["Job Map"],
)


# ============================================================================
# Helpers
# ============================================================================

def _verify_product_access(
    db: Session,
    product_id: int,
    user: User,
    required_level: ProductPermissionLevel = ProductPermissionLevel.VIEW,
) -> CIProduct:
    """Verify product exists and user has the required permission level."""
    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    permission_service = PermissionService(db)
    if not permission_service.can_access_product(
        user_id=user.id,
        product_id=product_id,
        required_level=required_level,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions for this product",
        )
    return product


def _rebuild_job_map_json(db: Session, product: CIProduct):
    """Rebuild CIProduct.job_map JSON from ProductJob records."""
    jobs = db.query(ProductJob).filter(
        ProductJob.product_id == product.id,
        ProductJob.status == "active",
    ).all()

    job_map = product.job_map or {}
    functional = []
    emotional = []
    social = []

    for j in jobs:
        entry = {
            "job_id": j.job_id_key,
            "job_type": j.job_type.value,
            "statement": j.statement,
            "desired_outcomes": j.desired_outcomes or [],
            "importance": j.importance.value,
        }
        if j.job_type.value == "functional":
            functional.append(entry)
        elif j.job_type.value == "emotional":
            emotional.append(entry)
        else:
            social.append(entry)

    job_map["functional_jobs"] = functional
    job_map["emotional_jobs"] = emotional
    job_map["social_jobs"] = social
    product.job_map = job_map


# ============================================================================
# Endpoints
# ============================================================================

def _get_signal_counts(db: Session, product_id: int) -> dict[str, int]:
    """Count signals per job_id_key from all four signal sources."""
    counts: dict[str, int] = {}

    for model in (Idea, Evidence, WinLossTheme, SupportTheme):
        rows = (
            db.query(model.job_id_key, sa_func.count(model.id))
            .filter(
                model.product_id == product_id,
                model.job_id_key.isnot(None),
            )
            .group_by(model.job_id_key)
            .all()
        )
        for key, cnt in rows:
            counts[key] = counts.get(key, 0) + cnt

    return counts


@router.get("/{product_id}/job-map")
def get_job_map(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get the current JTBD job map including target customer profile and all jobs."""
    product = _verify_product_access(db, product_id, current_user)

    jobs = db.query(ProductJob).filter(
        ProductJob.product_id == product_id,
        ProductJob.status == "active",
    ).all()

    signal_counts = _get_signal_counts(db, product_id)

    return {
        "product_id": product_id,
        "product_name": product.product_name,
        "target_customer_profile": product.target_customer_profile,
        "job_map": product.job_map,
        "job_map_version": product.job_map_version,
        "job_map_last_updated": product.job_map_last_updated.isoformat() if product.job_map_last_updated else None,
        "has_pending_map": product.pending_job_map is not None,
        "jobs": [
            {
                "id": j.id,
                "job_id_key": j.job_id_key,
                "job_type": j.job_type.value,
                "statement": j.statement,
                "desired_outcomes": j.desired_outcomes or [],
                "importance": j.importance.value,
                "has_embedding": j.statement_embedding is not None,
                "signal_count": signal_counts.get(j.job_id_key, 0),
                "updated_at": j.updated_at.isoformat() if j.updated_at else None,
            }
            for j in jobs
        ],
    }


@router.put("/{product_id}/job-map")
def set_job_map(
    product_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Set or replace the full JTBD job map. Deletes existing jobs and creates new ones."""
    product = _verify_product_access(db, product_id, current_user, ProductPermissionLevel.EDIT)

    job_map_data = body

    # Hard-delete all existing jobs. Full map replacement reuses key values (j1, j2…)
    # so soft-deleted rows would conflict with the unique (product_id, job_id_key) constraint.
    db.query(ProductJob).filter(
        ProductJob.product_id == product_id,
    ).delete()

    # Collect all job entries
    all_jobs = []
    for category in ["functional_jobs", "emotional_jobs", "social_jobs"]:
        for entry in job_map_data.get(category, []):
            all_jobs.append(entry)

    # Generate embeddings
    statements = [j["statement"] for j in all_jobs]
    embeddings = []
    if statements:
        from app.services.embedding_service import generate_embeddings_batch
        embeddings = generate_embeddings_batch(statements, input_type="document")

    # Create ProductJob records
    created_count = 0
    for i, entry in enumerate(all_jobs):
        pj = ProductJob(
            product_id=product_id,
            job_id_key=entry["job_id"],
            job_type=JobType(entry.get("job_type", "functional")),
            statement=entry["statement"],
            desired_outcomes=entry.get("desired_outcomes", []),
            importance=JobImportance(entry.get("importance", "medium")),
            statement_embedding=embeddings[i] if i < len(embeddings) else None,
        )
        db.add(pj)
        created_count += 1

    product.job_map = job_map_data
    product.job_map_version = (product.job_map_version or 0) + 1
    product.job_map_last_updated = datetime.now(timezone.utc)
    db.commit()

    return {
        "product_id": product_id,
        "job_map_version": product.job_map_version,
        "jobs_created": created_count,
        "message": f"Job map set with {created_count} jobs.",
    }


@router.put("/{product_id}/target-customer")
def set_target_customer(
    product_id: int,
    body: TargetCustomerProfile,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Set the target customer profile for a product."""
    product = _verify_product_access(db, product_id, current_user, ProductPermissionLevel.EDIT)

    profile = body.model_dump()
    product.target_customer_profile = profile
    db.commit()

    return {
        "product_id": product_id,
        "target_customer_profile": profile,
        "message": f"Target customer profile set: {body.persona_name}",
    }


@router.post("/{product_id}/extract-job-map")
def extract_job_map(
    product_id: int,
    guidance: str = "",
    skip_review: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Queue the JobMapExtractorAgent to generate a JTBD job map.

    skip_review=True commits directly (MCP/programmatic use).
    skip_review=False (default) stores result as pending for PM review.
    """
    product = _verify_product_access(db, product_id, current_user, ProductPermissionLevel.EDIT)

    input_data = {"product_id": product_id, "skip_review": skip_review}
    if guidance:
        input_data["guidance"] = guidance

    queue_service = QueueService(db)
    job = queue_service.create_job(
        job_type=QueueJobType.JOB_MAP_EXTRACTION,
        input_data=input_data,
        product_id=product_id,
        user_id=current_user.id,
    )

    send_task('extract_job_map_task', job.id)

    return {
        "job_id": job.id,
        "job_uuid": job.job_uuid,
        "status": "queued",
        "message": "Job map extraction queued.",
    }


@router.post("/{product_id}/jobs")
def add_job(
    product_id: int,
    body: JobCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Add a single job to the product's JTBD job map."""
    product = _verify_product_access(db, product_id, current_user, ProductPermissionLevel.EDIT)

    # Check uniqueness
    existing = db.query(ProductJob).filter(
        ProductJob.product_id == product_id,
        ProductJob.job_id_key == body.job_id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job '{body.job_id}' already exists for this product.",
        )

    # Generate embedding
    from app.services.embedding_service import generate_embedding
    embedding = generate_embedding(body.statement, input_type="document")

    pj = ProductJob(
        product_id=product_id,
        job_id_key=body.job_id,
        job_type=JobType(body.job_type),
        statement=body.statement,
        desired_outcomes=body.desired_outcomes,
        importance=JobImportance(body.importance),
        statement_embedding=embedding,
    )
    db.add(pj)
    db.flush()

    _rebuild_job_map_json(db, product)
    product.job_map_version = (product.job_map_version or 0) + 1
    product.job_map_last_updated = datetime.now(timezone.utc)
    db.commit()

    return {
        "id": pj.id,
        "job_id_key": pj.job_id_key,
        "job_type": pj.job_type.value,
        "statement": pj.statement,
        "desired_outcomes": pj.desired_outcomes or [],
        "importance": pj.importance.value,
        "job_map_version": product.job_map_version,
    }


@router.put("/{product_id}/jobs/{job_id}")
def edit_job(
    product_id: int,
    job_id: str,
    body: JobUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Edit a single job in the product's JTBD job map (partial update)."""
    product = _verify_product_access(db, product_id, current_user, ProductPermissionLevel.EDIT)

    pj = db.query(ProductJob).filter(
        ProductJob.product_id == product_id,
        ProductJob.job_id_key == job_id,
    ).first()
    if not pj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found for product {product_id}.",
        )

    if body.statement is not None:
        pj.statement = body.statement
        from app.services.embedding_service import generate_embedding
        pj.statement_embedding = generate_embedding(body.statement, input_type="document")

    if body.desired_outcomes is not None:
        pj.desired_outcomes = body.desired_outcomes

    if body.importance is not None:
        pj.importance = JobImportance(body.importance)

    db.flush()

    _rebuild_job_map_json(db, product)
    product.job_map_version = (product.job_map_version or 0) + 1
    product.job_map_last_updated = datetime.now(timezone.utc)
    db.commit()

    return {
        "job_id_key": pj.job_id_key,
        "job_type": pj.job_type.value,
        "statement": pj.statement,
        "desired_outcomes": pj.desired_outcomes or [],
        "importance": pj.importance.value,
        "job_map_version": product.job_map_version,
    }


@router.delete("/{product_id}/jobs/{job_id}")
def remove_job(
    product_id: int,
    job_id: str,
    relink: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Remove a job from the product's JTBD job map.

    relink=True (default): re-link orphaned signals to their closest remaining job.
    relink=False: clear job_id_key on all linked signals (they become unlinked).
    """
    product = _verify_product_access(db, product_id, current_user, ProductPermissionLevel.EDIT)

    pj = db.query(ProductJob).filter(
        ProductJob.product_id == product_id,
        ProductJob.job_id_key == job_id,
    ).first()
    if not pj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found for product {product_id}.",
        )

    pj.status = "inactive"
    db.flush()

    if not relink:
        # Clear linkages on all signals pointing to this job
        from app.models.idea import Idea
        from app.models.evidence import Evidence
        from app.models.synthesis import SynthesizedOpportunity
        for model in (Idea, Evidence, SynthesizedOpportunity):
            db.query(model).filter(
                model.product_id == product_id,
                model.job_id_key == job_id,
            ).update({"job_id_key": None})
    else:
        # Re-link orphaned signals to their best remaining active job
        from app.queue.helpers import _relink_all_signals
        remaining_active = {
            j.job_id_key for j in db.query(ProductJob).filter(
                ProductJob.product_id == product_id,
                ProductJob.status == "active",
            ).all()
        }
        _relink_all_signals(db, product_id, remaining_active)

    _rebuild_job_map_json(db, product)
    product.job_map_version = (product.job_map_version or 0) + 1
    product.job_map_last_updated = datetime.now(timezone.utc)
    db.commit()

    return {
        "product_id": product_id,
        "removed_job_id": job_id,
        "job_map_version": product.job_map_version,
        "message": f"Job '{job_id}' removed.",
    }


@router.put("/{product_id}/main-job")
def set_main_job(
    product_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Set the main job statement for the product's need map."""
    product = _verify_product_access(db, product_id, current_user, ProductPermissionLevel.EDIT)

    main_job = body.get("main_job", "").strip()
    if not main_job:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="main_job is required.")

    job_map = product.job_map or {}
    job_map["main_job"] = main_job
    product.job_map = job_map
    product.job_map_version = (product.job_map_version or 0) + 1
    product.job_map_last_updated = datetime.now(timezone.utc)
    db.commit()

    return {"product_id": product_id, "main_job": main_job, "job_map_version": product.job_map_version}


@router.get("/{product_id}/need-suggestions")
def list_need_suggestions(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List pending need map suggestions for a product."""
    _verify_product_access(db, product_id, current_user)

    items = db.query(PMReviewQueue).filter(
        PMReviewQueue.queue_type == ReviewQueueType.NEED_SUGGESTION,
        PMReviewQueue.status.in_([ReviewQueueStatus.PENDING, ReviewQueueStatus.IN_REVIEW]),
    ).order_by(PMReviewQueue.created_at.desc()).all()

    # Filter by product_id stored in item_metadata
    results = []
    for item in items:
        meta = item.item_metadata or {}
        if meta.get("product_id") == product_id:
            results.append({
                "id": item.id,
                "signal_type": meta.get("signal_type"),
                "signal_id": meta.get("signal_id"),
                "signal_content": meta.get("signal_content"),
                "match_type": meta.get("match_type"),
                "matched_job_id": meta.get("matched_job_id"),
                "matched_job_statement": meta.get("matched_job_statement"),
                "matched_similarity": meta.get("matched_similarity"),
                "priority": item.priority.value,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            })

    return {"product_id": product_id, "suggestions": results, "count": len(results)}


@router.post("/{product_id}/need-suggestions/{suggestion_id}/approve")
def approve_need_suggestion(
    product_id: int,
    suggestion_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Approve a need suggestion — creates a new ProductJob and closes the suggestion."""
    product = _verify_product_access(db, product_id, current_user, ProductPermissionLevel.EDIT)

    item = db.query(PMReviewQueue).filter(
        PMReviewQueue.id == suggestion_id,
        PMReviewQueue.queue_type == ReviewQueueType.NEED_SUGGESTION,
    ).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found.")

    meta = item.item_metadata or {}
    if meta.get("product_id") != product_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Suggestion does not belong to this product.")

    statement = (body.get("statement") or "").strip()
    if not statement:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="statement is required.")

    desired_outcomes = body.get("desired_outcomes") or []
    importance_str = body.get("importance", "medium")
    try:
        importance = JobImportance(importance_str)
    except ValueError:
        importance = JobImportance.MEDIUM

    # Generate next job_id_key across all existing jobs
    existing_keys = [
        j.job_id_key for j in db.query(ProductJob.job_id_key)
        .filter(ProductJob.product_id == product_id).all()
    ]
    import re
    max_index = max(
        (int(m.group(1)) for key in existing_keys if (m := re.match(r'^j(\d+)$', key))),
        default=0,
    )
    new_key = f"j{max_index + 1}"

    from app.services.embedding_service import generate_embedding
    embedding = generate_embedding(statement, input_type="document")

    pj = ProductJob(
        product_id=product_id,
        job_id_key=new_key,
        job_type=JobType("functional"),
        statement=statement,
        desired_outcomes=desired_outcomes,
        importance=importance,
        statement_embedding=embedding,
    )
    db.add(pj)
    db.flush()

    _rebuild_job_map_json(db, product)
    product.job_map_version = (product.job_map_version or 0) + 1
    product.job_map_last_updated = datetime.now(timezone.utc)

    item.status = ReviewQueueStatus.APPROVED
    item.reviewed_by_user_id = current_user.id
    db.commit()

    return {
        "product_id": product_id,
        "new_job_id_key": new_key,
        "statement": statement,
        "job_map_version": product.job_map_version,
        "suggestion_id": suggestion_id,
    }


@router.post("/{product_id}/need-suggestions/{suggestion_id}/dismiss")
def dismiss_need_suggestion(
    product_id: int,
    suggestion_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Dismiss a need suggestion without modifying the need map."""
    _verify_product_access(db, product_id, current_user, ProductPermissionLevel.EDIT)

    item = db.query(PMReviewQueue).filter(
        PMReviewQueue.id == suggestion_id,
        PMReviewQueue.queue_type == ReviewQueueType.NEED_SUGGESTION,
    ).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found.")

    meta = item.item_metadata or {}
    if meta.get("product_id") != product_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Suggestion does not belong to this product.")

    item.status = ReviewQueueStatus.REJECTED
    item.reviewed_by_user_id = current_user.id
    db.commit()

    return {"suggestion_id": suggestion_id, "status": "dismissed"}


@router.get("/{product_id}/jobs/{job_id_key}/signals")
def get_job_signals(
    product_id: int,
    job_id_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get all signals linked to a specific customer need, grouped by type."""
    _verify_product_access(db, product_id, current_user)

    from app.models.vote import Vote
    from app.models.synthesis import SynthesizedOpportunity

    LIMIT = 20

    ideas = (
        db.query(Idea, sa_func.count(Vote.id).label("vote_count"))
        .outerjoin(Vote, Vote.idea_id == Idea.id)
        .filter(Idea.product_id == product_id, Idea.job_id_key == job_id_key, Idea.is_active == True)
        .group_by(Idea.id)
        .order_by(sa_func.count(Vote.id).desc())
        .limit(LIMIT)
        .all()
    )

    evidence = (
        db.query(Evidence)
        .filter(Evidence.product_id == product_id, Evidence.job_id_key == job_id_key)
        .order_by(Evidence.created_at.desc())
        .limit(LIMIT)
        .all()
    )

    win_loss = (
        db.query(WinLossTheme)
        .filter(WinLossTheme.product_id == product_id, WinLossTheme.job_id_key == job_id_key)
        .order_by(WinLossTheme.deal_count.desc())
        .limit(LIMIT)
        .all()
    )

    support = (
        db.query(SupportTheme)
        .filter(SupportTheme.product_id == product_id, SupportTheme.job_id_key == job_id_key)
        .order_by(SupportTheme.ticket_count.desc())
        .limit(LIMIT)
        .all()
    )

    opportunities = (
        db.query(SynthesizedOpportunity)
        .filter(SynthesizedOpportunity.product_id == product_id, SynthesizedOpportunity.job_id_key == job_id_key)
        .order_by(SynthesizedOpportunity.priority_score.desc())
        .limit(LIMIT)
        .all()
    )

    return {
        "job_id_key": job_id_key,
        "ideas": [
            {
                "id": idea.id,
                "title": idea.title,
                "status": idea.status.value if idea.status else None,
                "vote_count": vote_count,
                "created_at": idea.created_at.isoformat() if idea.created_at else None,
            }
            for idea, vote_count in ideas
        ],
        "evidence": [
            {
                "id": e.id,
                "title": e.title,
                "evidence_type": e.evidence_type.value if e.evidence_type else None,
                "source_url": e.source_url,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in evidence
        ],
        "win_loss_themes": [
            {
                "id": t.id,
                "theme_name": t.theme_name,
                "outcome": t.outcome,
                "deal_count": t.deal_count,
            }
            for t in win_loss
        ],
        "support_themes": [
            {
                "id": t.id,
                "theme_name": t.theme_name,
                "category": t.category,
                "ticket_count": t.ticket_count,
            }
            for t in support
        ],
        "synthesis_opportunities": [
            {
                "id": o.id,
                "opportunity_name": o.opportunity_name,
                "priority_score": float(o.priority_score) if o.priority_score else 0.0,
                "investment_tier": o.investment_tier,
            }
            for o in opportunities
        ],
    }


@router.get("/{product_id}/job-map/pending-comparison")
def get_pending_comparison(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Return current and pending jobs matched by embedding similarity for PM review."""
    from app.services.embedding_service import generate_embeddings_batch
    product = _verify_product_access(db, product_id, current_user, ProductPermissionLevel.EDIT)

    if not product.pending_job_map:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending job map.")

    current_jobs = db.query(ProductJob).filter(
        ProductJob.product_id == product_id,
        ProductJob.status == "active",
    ).all()

    # Flatten pending map jobs
    pending_jobs = []
    for key in ["functional_jobs", "emotional_jobs", "social_jobs", "jobs"]:
        for j in (product.pending_job_map or {}).get(key, []):
            pending_jobs.append({
                "job_id_key": j.get("job_id", j.get("job_id_key", "")),
                "statement": j.get("statement", ""),
                "desired_outcomes": j.get("desired_outcomes", []),
                "importance": j.get("importance", "medium"),
                "job_type": j.get("job_type", "functional"),
            })

    # Generate embeddings for pending jobs
    pending_statements = [j["statement"] for j in pending_jobs]
    pending_embeddings = []
    if pending_statements:
        try:
            pending_embeddings = generate_embeddings_batch(pending_statements, input_type="document")
        except Exception:
            pending_embeddings = [None] * len(pending_statements)

    # Match each pending job to best current job
    current_jobs_with_emb = [j for j in current_jobs if j.statement_embedding]
    matched_current_keys = set()
    pairs = []

    for i, (pj, pemb) in enumerate(zip(pending_jobs, pending_embeddings)):
        best_match = None
        best_sim = 0.0
        if pemb:
            for cj in current_jobs_with_emb:
                sim = sum(a * b for a, b in zip(pemb, cj.statement_embedding)) / (
                    (sum(a * a for a in pemb) ** 0.5) * (sum(b * b for b in cj.statement_embedding) ** 0.5) + 1e-8
                )
                if sim > best_sim:
                    best_sim = sim
                    best_match = cj

        if best_match and best_sim >= 0.6:
            matched_current_keys.add(best_match.job_id_key)
            if best_sim >= 0.85:
                change_type = "unchanged"
                default_selection = "new"
            else:
                change_type = "modified"
                default_selection = "old"
            pairs.append({
                "id": f"pair_{i}",
                "similarity": round(best_sim, 3),
                "change_type": change_type,
                "default_selection": default_selection,
                "old": {
                    "job_id_key": best_match.job_id_key,
                    "statement": best_match.statement,
                    "desired_outcomes": best_match.desired_outcomes or [],
                    "importance": best_match.importance.value,
                },
                "new": pj,
            })
        else:
            pairs.append({
                "id": f"pair_{i}",
                "similarity": round(best_sim, 3) if best_sim else None,
                "change_type": "new",
                "default_selection": "new",
                "old": None,
                "new": pj,
            })

    # Current jobs with no pending match are marked removed
    for cj in current_jobs:
        if cj.job_id_key not in matched_current_keys:
            pairs.append({
                "id": f"removed_{cj.job_id_key}",
                "similarity": None,
                "change_type": "removed",
                "default_selection": "drop",
                "old": {
                    "job_id_key": cj.job_id_key,
                    "statement": cj.statement,
                    "desired_outcomes": cj.desired_outcomes or [],
                    "importance": cj.importance.value,
                },
                "new": None,
            })

    return {"has_pending": True, "pairs": pairs}


@router.post("/{product_id}/job-map/apply-pending")
def apply_pending_job_map(
    product_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Apply PM selections from the pending job map comparison."""
    from app.services.embedding_service import generate_embedding
    from app.queue.helpers import _relink_all_signals

    product = _verify_product_access(db, product_id, current_user, ProductPermissionLevel.EDIT)
    if not product.pending_job_map:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending job map.")

    selections = body.get("selections", [])
    importance_map = {
        "critical": JobImportance.CRITICAL,
        "high": JobImportance.HIGH,
        "medium": JobImportance.MEDIUM,
        "low": JobImportance.LOW,
    }

    # Track which old job_id_keys are being kept (choice="old") — their signals stay
    kept_old_keys = set()
    for sel in selections:
        if sel.get("choice") == "old" and sel.get("old_job_id_key"):
            kept_old_keys.add(sel["old_job_id_key"])

    # Get current active job keys to determine which to delete
    current_jobs = {j.job_id_key: j for j in db.query(ProductJob).filter(
        ProductJob.product_id == product_id, ProductJob.status == "active",
    ).all()}

    new_active_keys = set(kept_old_keys)  # Start with kept old jobs

    for sel in selections:
        choice = sel.get("choice")
        old_key = sel.get("old_job_id_key")
        new_data = sel.get("new_job_data")

        if choice == "old":
            # Keep existing row unchanged
            pass
        elif choice == "new" and new_data:
            # Delete old row if it exists, insert new one
            if old_key and old_key in current_jobs:
                current_jobs[old_key].status = "inactive"
                db.flush()
            statement = sel.get("statement") or new_data.get("statement", "")
            desired_outcomes = sel.get("desired_outcomes") or new_data.get("desired_outcomes", [])
            importance_str = sel.get("importance") or new_data.get("importance", "medium")
            new_key = new_data.get("job_id_key", "")

            emb = generate_embedding(statement, input_type="document")
            pj = ProductJob(
                product_id=product_id,
                job_id_key=new_key,
                job_type=JobType(new_data.get("job_type", "functional")),
                statement=statement,
                desired_outcomes=desired_outcomes,
                importance=importance_map.get(importance_str, JobImportance.MEDIUM),
                statement_embedding=emb,
            )
            db.add(pj)
            db.flush()
            new_active_keys.add(new_key)
        elif choice == "drop" and old_key and old_key in current_jobs:
            current_jobs[old_key].status = "inactive"
            db.flush()

    # Archive and clear pending
    product.previous_job_map = product.job_map
    product.pending_job_map = None
    _rebuild_job_map_json(db, product)
    product.job_map_version = (product.job_map_version or 0) + 1
    product.job_map_last_updated = datetime.now(timezone.utc)
    db.commit()

    # Re-link signals orphaned by dropped/replaced jobs
    _relink_all_signals(db, product_id, new_active_keys)

    return {
        "product_id": product_id,
        "job_map_version": product.job_map_version,
        "message": "Job map applied.",
    }


@router.delete("/{product_id}/job-map/pending")
def discard_pending_job_map(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Discard the pending job map without applying it."""
    product = _verify_product_access(db, product_id, current_user, ProductPermissionLevel.EDIT)
    product.pending_job_map = None
    db.commit()
    return {"product_id": product_id, "message": "Pending job map discarded."}
