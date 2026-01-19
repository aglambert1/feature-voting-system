"""
Internal Feedback API endpoints.

This module provides REST API endpoints for:
- Uploading internal feedback files (JSON format)
- Triggering theme extraction via Internal Discovery Agent
- Retrieving extracted themes
- Managing import history
"""

import json
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from pydantic import BaseModel, Field, ValidationError
from datetime import datetime

from app.database import get_db
from app.models.user import User
from app.models.competitor_intelligence import CIProduct
from app.models.internal_feedback import (
    InternalFeedbackImport,
    WinLossTheme,
    SupportTheme
)
from app.schemas.internal_feedback import (
    InternalFeedbackFileInput,
    InternalFeedbackImportResponse,
    WinLossThemeResponse,
    SupportThemeResponse,
    ThemesResponse
)
from app.services.queue_service import QueueService
from app.models.queue import JobType, JobStatus
from app.utils.security import get_current_active_user, get_product_owner_or_admin
from app.queue.tasks import internal_discovery_task


router = APIRouter(
    prefix="/internal-feedback",
    tags=["Internal Feedback"]
)


# ============================================================================
# Response Schemas
# ============================================================================

class ImportListResponse(BaseModel):
    """Response for list of imports."""
    imports: List[InternalFeedbackImportResponse]
    total: int


class ImportStatusResponse(BaseModel):
    """Response for import processing status."""
    id: int
    status: str
    themes_extracted: bool
    winloss_theme_count: int
    support_theme_count: int
    error_message: Optional[str] = None


# ============================================================================
# API Endpoints
# ============================================================================

@router.post(
    "/{product_id}/import",
    response_model=InternalFeedbackImportResponse,
    status_code=status.HTTP_201_CREATED
)
async def upload_internal_feedback(
    product_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_product_owner_or_admin)
):
    """
    Upload an internal feedback JSON file.

    The file should contain:
    - deals: Array of win/loss deal records
    - support_tickets: Array of support ticket records

    Returns the import record. Theme extraction will be triggered
    automatically in the background.
    """
    # Verify product exists
    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )

    # Validate file type
    if not file.filename.endswith('.json'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a JSON file"
        )

    # Read and parse file content
    try:
        content = await file.read()
        data = json.loads(content.decode('utf-8'))
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON format: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read file: {str(e)}"
        )

    # Validate against schema
    try:
        validated_data = InternalFeedbackFileInput(**data)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Data validation failed: {e.errors()}"
        )

    # Create import record
    import_record = InternalFeedbackImport(
        product_id=product_id,
        filename=file.filename,
        source_type=validated_data.source or "file_import",
        status="pending",
        deals_count=len(validated_data.deals),
        tickets_count=len(validated_data.support_tickets),
        raw_deals=[d.model_dump() for d in validated_data.deals],
        raw_tickets=[t.model_dump() for t in validated_data.support_tickets],
        themes_extracted=False
    )
    db.add(import_record)
    db.commit()
    db.refresh(import_record)

    # Queue theme extraction job
    try:
        queue_service = QueueService(db)
        job = queue_service.create_job(
            job_type=JobType.INTERNAL_DISCOVERY,
            product_id=product_id,
            input_data={
                "import_id": import_record.id,
                "deals": import_record.raw_deals,
                "support_tickets": import_record.raw_tickets
            },
            user_id=current_user.id
        )

        # Dispatch to Celery
        celery_result = internal_discovery_task.delay(job.id)
        queue_service.mark_queued(job.id, celery_result.id)

        import_record.job_uuid = job.job_uuid
        import_record.status = "processing"
        db.commit()
    except Exception as e:
        # Log error but don't fail - can be reprocessed later
        import_record.status = "pending"
        import_record.error_message = f"Failed to queue job: {str(e)}"
        db.commit()

    return InternalFeedbackImportResponse(
        id=import_record.id,
        product_id=import_record.product_id,
        filename=import_record.filename,
        source_type=import_record.source_type,
        status=import_record.status,
        imported_at=import_record.imported_at,
        deals_count=import_record.deals_count,
        tickets_count=import_record.tickets_count,
        themes_extracted=import_record.themes_extracted,
        error_message=import_record.error_message
    )


@router.get(
    "/{product_id}/imports",
    response_model=ImportListResponse
)
async def list_imports(
    product_id: int,
    limit: int = 10,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List all internal feedback imports for a product."""
    # Verify product exists
    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )

    # Get total count
    total = db.query(InternalFeedbackImport).filter(
        InternalFeedbackImport.product_id == product_id
    ).count()

    # Get imports
    imports = db.query(InternalFeedbackImport).filter(
        InternalFeedbackImport.product_id == product_id
    ).order_by(desc(InternalFeedbackImport.imported_at)).offset(offset).limit(limit).all()

    return ImportListResponse(
        imports=[
            InternalFeedbackImportResponse(
                id=i.id,
                product_id=i.product_id,
                filename=i.filename,
                source_type=i.source_type,
                status=i.status,
                imported_at=i.imported_at,
                deals_count=i.deals_count,
                tickets_count=i.tickets_count,
                themes_extracted=i.themes_extracted,
                error_message=i.error_message
            ) for i in imports
        ],
        total=total
    )


@router.get(
    "/{product_id}/imports/{import_id}",
    response_model=InternalFeedbackImportResponse
)
async def get_import(
    product_id: int,
    import_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific import record."""
    import_record = db.query(InternalFeedbackImport).filter(
        InternalFeedbackImport.id == import_id,
        InternalFeedbackImport.product_id == product_id
    ).first()

    if not import_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import not found"
        )

    return InternalFeedbackImportResponse(
        id=import_record.id,
        product_id=import_record.product_id,
        filename=import_record.filename,
        source_type=import_record.source_type,
        status=import_record.status,
        imported_at=import_record.imported_at,
        deals_count=import_record.deals_count,
        tickets_count=import_record.tickets_count,
        themes_extracted=import_record.themes_extracted,
        error_message=import_record.error_message
    )


@router.get(
    "/{product_id}/imports/{import_id}/status",
    response_model=ImportStatusResponse
)
async def get_import_status(
    product_id: int,
    import_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get processing status for an import."""
    import_record = db.query(InternalFeedbackImport).filter(
        InternalFeedbackImport.id == import_id,
        InternalFeedbackImport.product_id == product_id
    ).first()

    if not import_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import not found"
        )

    # Count themes
    winloss_count = db.query(WinLossTheme).filter(
        WinLossTheme.import_id == import_id
    ).count()
    support_count = db.query(SupportTheme).filter(
        SupportTheme.import_id == import_id
    ).count()

    return ImportStatusResponse(
        id=import_record.id,
        status=import_record.status,
        themes_extracted=import_record.themes_extracted,
        winloss_theme_count=winloss_count,
        support_theme_count=support_count,
        error_message=import_record.error_message
    )


@router.get(
    "/{product_id}/themes",
    response_model=ThemesResponse
)
async def get_themes(
    product_id: int,
    import_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get extracted themes for a product.

    If import_id is provided, returns themes from that specific import.
    Otherwise, returns themes from the most recent completed import.
    """
    # Verify product exists
    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )

    # Find the import to get themes from
    if import_id:
        import_record = db.query(InternalFeedbackImport).filter(
            InternalFeedbackImport.id == import_id,
            InternalFeedbackImport.product_id == product_id
        ).first()
    else:
        # Get most recent completed import
        import_record = db.query(InternalFeedbackImport).filter(
            InternalFeedbackImport.product_id == product_id,
            InternalFeedbackImport.themes_extracted == True
        ).order_by(desc(InternalFeedbackImport.imported_at)).first()

    if not import_record:
        # Return empty themes instead of 404
        return ThemesResponse(
            import_id=0,
            winloss_themes=[],
            support_themes=[],
            analysis_summary=None
        )

    # Get themes
    winloss_themes = db.query(WinLossTheme).filter(
        WinLossTheme.import_id == import_record.id
    ).all()

    support_themes = db.query(SupportTheme).filter(
        SupportTheme.import_id == import_record.id
    ).all()

    return ThemesResponse(
        import_id=import_record.id,
        winloss_themes=[
            WinLossThemeResponse(
                id=t.id,
                import_id=t.import_id,
                theme_name=t.theme_name,
                outcome=t.outcome,
                competitor_name=t.competitor_name,
                deal_count=t.deal_count,
                total_value=t.total_value,
                sample_reasons=t.sample_reasons or [],
                feature_keywords=t.feature_keywords or []
            ) for t in winloss_themes
        ],
        support_themes=[
            SupportThemeResponse(
                id=t.id,
                import_id=t.import_id,
                theme_name=t.theme_name,
                category=t.category,
                ticket_count=t.ticket_count,
                sample_subjects=t.sample_subjects or [],
                feature_keywords=t.feature_keywords or [],
                urgency_indicator=t.urgency_indicator
            ) for t in support_themes
        ],
        analysis_summary=import_record.analysis_summary
    )


@router.delete(
    "/{product_id}/imports/{import_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def delete_import(
    product_id: int,
    import_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_product_owner_or_admin)
):
    """Delete an import and its associated themes."""
    import_record = db.query(InternalFeedbackImport).filter(
        InternalFeedbackImport.id == import_id,
        InternalFeedbackImport.product_id == product_id
    ).first()

    if not import_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import not found"
        )

    # Delete will cascade to themes
    db.delete(import_record)
    db.commit()

    return None


@router.post(
    "/{product_id}/imports/{import_id}/reprocess",
    response_model=ImportStatusResponse
)
async def reprocess_import(
    product_id: int,
    import_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_product_owner_or_admin)
):
    """Re-run theme extraction on an existing import."""
    import_record = db.query(InternalFeedbackImport).filter(
        InternalFeedbackImport.id == import_id,
        InternalFeedbackImport.product_id == product_id
    ).first()

    if not import_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import not found"
        )

    # Clear existing themes
    db.query(WinLossTheme).filter(WinLossTheme.import_id == import_id).delete()
    db.query(SupportTheme).filter(SupportTheme.import_id == import_id).delete()

    # Reset status
    import_record.status = "processing"
    import_record.themes_extracted = False
    import_record.error_message = None
    import_record.analysis_summary = None

    # Queue new job
    try:
        queue_service = QueueService(db)
        job = queue_service.create_job(
            job_type=JobType.INTERNAL_DISCOVERY,
            product_id=product_id,
            input_data={
                "import_id": import_record.id,
                "deals": import_record.raw_deals,
                "support_tickets": import_record.raw_tickets
            },
            user_id=current_user.id
        )

        # Dispatch to Celery
        celery_result = internal_discovery_task.delay(job.id)
        queue_service.mark_queued(job.id, celery_result.id)

        import_record.job_uuid = job.job_uuid
    except Exception as e:
        import_record.status = "failed"
        import_record.error_message = f"Failed to queue job: {str(e)}"

    db.commit()

    return ImportStatusResponse(
        id=import_record.id,
        status=import_record.status,
        themes_extracted=import_record.themes_extracted,
        winloss_theme_count=0,
        support_theme_count=0,
        error_message=import_record.error_message
    )
