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
from app.models.user import User
from app.models.competitor_intelligence import (
    CIProduct, ProductJob, JobType, JobImportance,
    ProductPermissionLevel,
)
from app.models.queue import JobType as QueueJobType
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

    return {
        "product_id": product_id,
        "product_name": product.product_name,
        "target_customer_profile": product.target_customer_profile,
        "job_map": product.job_map,
        "job_map_version": product.job_map_version,
        "job_map_last_updated": product.job_map_last_updated.isoformat() if product.job_map_last_updated else None,
        "jobs": [
            {
                "id": j.id,
                "job_id_key": j.job_id_key,
                "job_type": j.job_type.value,
                "statement": j.statement,
                "desired_outcomes": j.desired_outcomes or [],
                "importance": j.importance.value,
                "has_embedding": j.statement_embedding is not None,
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

    # Delete existing jobs
    db.query(ProductJob).filter(ProductJob.product_id == product_id).delete()

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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Queue the JobMapExtractorAgent to generate a JTBD job map."""
    product = _verify_product_access(db, product_id, current_user, ProductPermissionLevel.EDIT)

    input_data = {"product_id": product_id}
    if guidance:
        input_data["guidance"] = guidance

    queue_service = QueueService(db)
    job = queue_service.create_job(
        job_type=QueueJobType.JOB_MAP_EXTRACTION,
        input_data=input_data,
        product_id=product_id,
        user_id=current_user.id,
    )

    from app.queue.jtbd_tasks import extract_job_map_task
    extract_job_map_task.delay(job.id)

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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Remove a job from the product's JTBD job map."""
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

    db.delete(pj)
    db.flush()

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
