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
from app.models.activity_insights import (
    ActivityImport,
    DealActivityInsight,
    SupportActivityInsight
)
from app.schemas.internal_feedback import (
    InternalFeedbackFileInput,
    InternalFeedbackImportResponse,
    WinLossThemeResponse,
    SupportThemeResponse,
    ThemesResponse
)
from app.services.queue_service import QueueService
from app.services.activity_parser import ActivityParserService
from app.models.queue import JobType, JobStatus
from app.utils.security import get_current_active_user, get_product_owner_or_admin
# Thread-safe task dispatch (see app/utils/celery_utils.py for explanation)
from app.utils.celery_utils import send_celery_task as send_task


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
        celery_result = send_task('internal_discovery_task', job.id)
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
    response_model=InternalFeedbackImportResponse
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
        celery_result = send_task('internal_discovery_task', job.id)
        queue_service.mark_queued(job.id, celery_result.id)

        import_record.job_uuid = job.job_uuid
    except Exception as e:
        import_record.status = "failed"
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


# ============================================================================
# Activity Import Schemas
# ============================================================================

class ActivityImportResponse(BaseModel):
    """Response for an activity import."""
    id: int
    product_id: int
    filename: str
    source_type: str
    format_type: str
    status: str
    imported_at: datetime
    deals_count: int
    activities_count: int
    support_tickets_count: int
    error_message: Optional[str] = None


class ActivityImportListResponse(BaseModel):
    """Response for list of activity imports."""
    imports: List[ActivityImportResponse]
    total: int


class ActivityImportStatusResponse(BaseModel):
    """Response for activity import processing status."""
    id: int
    status: str
    deal_insight_count: int
    support_insight_count: int
    error_message: Optional[str] = None


class DealActivityInsightResponse(BaseModel):
    """Response for a deal activity insight."""
    id: int
    import_id: int
    deal_id: Optional[str] = None
    deal_name: Optional[str] = None
    deal_outcome: str
    deal_value: Optional[float] = None
    competitor_mentioned: Optional[str] = None
    theme_name: str
    category: str
    sentiment: str
    urgency_level: str
    sample_quotes: List[str] = []
    activity_count: int
    feature_keywords: List[str] = []


class SupportActivityInsightResponse(BaseModel):
    """Response for a support activity insight."""
    id: int
    import_id: int
    theme_name: str
    category: str
    ticket_count: int
    urgency_level: str
    sample_quotes: List[str] = []
    accounts_affected: List[str] = []
    feature_keywords: List[str] = []


class ActivityInsightsResponse(BaseModel):
    """Response containing all activity insights from an import."""
    import_id: int
    deal_insights: List[DealActivityInsightResponse]
    support_insights: List[SupportActivityInsightResponse]
    top_loss_themes: List[str] = []
    top_win_themes: List[str] = []
    analysis_summary: Optional[str] = None


# ============================================================================
# Activity Import API Endpoints
# ============================================================================

@router.post(
    "/{product_id}/activity-import",
    response_model=ActivityImportResponse,
    status_code=status.HTTP_201_CREATED
)
async def upload_activity_data(
    product_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_product_owner_or_admin)
):
    """
    Upload CRM activity data file (JSON or Markdown format).

    The file should contain deal activities and/or support activities
    with conversational content (call notes, emails, meeting notes).

    Supported formats:
    - JSON (.json): Programmatic exports from CRM APIs
    - Markdown (.md): Human-readable format for manual preparation

    Returns the import record. Activity insight extraction will be
    triggered automatically in the background.
    """
    # Verify product exists
    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )

    # Validate file type
    filename = file.filename or "upload.json"
    if not (filename.endswith('.json') or filename.endswith('.md') or filename.endswith('.markdown')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be JSON (.json) or Markdown (.md)"
        )

    # Read file content
    try:
        content = await file.read()
        content_str = content.decode('utf-8')
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read file: {str(e)}"
        )

    # Parse the file
    parser = ActivityParserService()
    try:
        parsed_data = parser.parse(content_str, filename)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON format: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse file: {str(e)}"
        )

    # Count activities
    total_activities = sum(len(d.activities) for d in parsed_data.deals)
    total_activities += sum(len(t.activities) for t in parsed_data.support_tickets)

    # Create import record
    import_record = ActivityImport(
        product_id=product_id,
        filename=filename,
        source_type=parsed_data.source,
        format_type=parser.get_format_type(filename),
        status="pending",
        deals_count=len(parsed_data.deals),
        activities_count=total_activities,
        support_tickets_count=len(parsed_data.support_tickets),
        raw_content=parsed_data.model_dump()
    )
    db.add(import_record)
    db.commit()
    db.refresh(import_record)

    # Queue insight extraction job
    try:
        queue_service = QueueService(db)
        job = queue_service.create_job(
            job_type=JobType.ACTIVITY_INSIGHT,
            product_id=product_id,
            input_data={
                "import_id": import_record.id,
                "parsed_data": parsed_data.model_dump()
            },
            user_id=current_user.id
        )

        # Dispatch to Celery
        celery_result = send_task('activity_insight_task', job.id)
        queue_service.mark_queued(job.id, celery_result.id)

        import_record.job_uuid = job.job_uuid
        import_record.status = "processing"
        db.commit()
    except Exception as e:
        # Log error but don't fail - can be reprocessed later
        import_record.status = "pending"
        import_record.error_message = f"Failed to queue job: {str(e)}"
        db.commit()

    return ActivityImportResponse(
        id=import_record.id,
        product_id=import_record.product_id,
        filename=import_record.filename,
        source_type=import_record.source_type,
        format_type=import_record.format_type,
        status=import_record.status,
        imported_at=import_record.imported_at,
        deals_count=import_record.deals_count,
        activities_count=import_record.activities_count,
        support_tickets_count=import_record.support_tickets_count,
        error_message=import_record.error_message
    )


@router.get(
    "/{product_id}/activity-imports",
    response_model=ActivityImportListResponse
)
async def list_activity_imports(
    product_id: int,
    limit: int = 10,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List all activity imports for a product."""
    # Verify product exists
    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )

    # Get total count
    total = db.query(ActivityImport).filter(
        ActivityImport.product_id == product_id
    ).count()

    # Get imports
    imports = db.query(ActivityImport).filter(
        ActivityImport.product_id == product_id
    ).order_by(desc(ActivityImport.imported_at)).offset(offset).limit(limit).all()

    return ActivityImportListResponse(
        imports=[
            ActivityImportResponse(
                id=i.id,
                product_id=i.product_id,
                filename=i.filename,
                source_type=i.source_type,
                format_type=i.format_type,
                status=i.status,
                imported_at=i.imported_at,
                deals_count=i.deals_count,
                activities_count=i.activities_count,
                support_tickets_count=i.support_tickets_count,
                error_message=i.error_message
            ) for i in imports
        ],
        total=total
    )


@router.get(
    "/{product_id}/activity-imports/{import_id}/status",
    response_model=ActivityImportStatusResponse
)
async def get_activity_import_status(
    product_id: int,
    import_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get processing status for an activity import."""
    import_record = db.query(ActivityImport).filter(
        ActivityImport.id == import_id,
        ActivityImport.product_id == product_id
    ).first()

    if not import_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity import not found"
        )

    # Count insights
    deal_insight_count = db.query(DealActivityInsight).filter(
        DealActivityInsight.import_id == import_id
    ).count()
    support_insight_count = db.query(SupportActivityInsight).filter(
        SupportActivityInsight.import_id == import_id
    ).count()

    return ActivityImportStatusResponse(
        id=import_record.id,
        status=import_record.status,
        deal_insight_count=deal_insight_count,
        support_insight_count=support_insight_count,
        error_message=import_record.error_message
    )


@router.get(
    "/{product_id}/activity-insights",
    response_model=ActivityInsightsResponse
)
async def get_activity_insights(
    product_id: int,
    import_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get extracted activity insights for a product.

    If import_id is provided, returns insights from that specific import.
    Otherwise, returns insights from the most recent completed import.
    """
    # Verify product exists
    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )

    # Find the import to get insights from
    if import_id:
        import_record = db.query(ActivityImport).filter(
            ActivityImport.id == import_id,
            ActivityImport.product_id == product_id
        ).first()
    else:
        # Get most recent completed import
        import_record = db.query(ActivityImport).filter(
            ActivityImport.product_id == product_id,
            ActivityImport.status == "completed"
        ).order_by(desc(ActivityImport.imported_at)).first()

    if not import_record:
        # Return empty response instead of 404
        return ActivityInsightsResponse(
            import_id=0,
            deal_insights=[],
            support_insights=[],
            top_loss_themes=[],
            top_win_themes=[],
            analysis_summary=None
        )

    # Get deal insights
    deal_insights = db.query(DealActivityInsight).filter(
        DealActivityInsight.import_id == import_record.id
    ).all()

    # Get support insights
    support_insights = db.query(SupportActivityInsight).filter(
        SupportActivityInsight.import_id == import_record.id
    ).all()

    return ActivityInsightsResponse(
        import_id=import_record.id,
        deal_insights=[
            DealActivityInsightResponse(
                id=i.id,
                import_id=i.import_id,
                deal_id=i.deal_id,
                deal_name=i.deal_name,
                deal_outcome=i.deal_outcome,
                deal_value=i.deal_value,
                competitor_mentioned=i.competitor_mentioned,
                theme_name=i.theme_name,
                category=i.category,
                sentiment=i.sentiment,
                urgency_level=i.urgency_level,
                sample_quotes=i.sample_quotes or [],
                activity_count=i.activity_count,
                feature_keywords=i.feature_keywords or []
            ) for i in deal_insights
        ],
        support_insights=[
            SupportActivityInsightResponse(
                id=i.id,
                import_id=i.import_id,
                theme_name=i.theme_name,
                category=i.category,
                ticket_count=i.ticket_count,
                urgency_level=i.urgency_level,
                sample_quotes=i.sample_quotes or [],
                accounts_affected=i.accounts_affected or [],
                feature_keywords=i.feature_keywords or []
            ) for i in support_insights
        ],
        top_loss_themes=import_record.top_loss_themes or [],
        top_win_themes=import_record.top_win_themes or [],
        analysis_summary=import_record.analysis_summary
    )


@router.delete(
    "/{product_id}/activity-imports/{import_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def delete_activity_import(
    product_id: int,
    import_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_product_owner_or_admin)
):
    """Delete an activity import and its associated insights."""
    import_record = db.query(ActivityImport).filter(
        ActivityImport.id == import_id,
        ActivityImport.product_id == product_id
    ).first()

    if not import_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity import not found"
        )

    # Delete will cascade to insights
    db.delete(import_record)
    db.commit()

    return None


@router.post(
    "/{product_id}/activity-imports/{import_id}/reprocess",
    response_model=ActivityImportResponse
)
async def reprocess_activity_import(
    product_id: int,
    import_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_product_owner_or_admin)
):
    """Re-run insight extraction on an existing activity import."""
    import_record = db.query(ActivityImport).filter(
        ActivityImport.id == import_id,
        ActivityImport.product_id == product_id
    ).first()

    if not import_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity import not found"
        )

    # Clear existing insights
    db.query(DealActivityInsight).filter(DealActivityInsight.import_id == import_id).delete()
    db.query(SupportActivityInsight).filter(SupportActivityInsight.import_id == import_id).delete()

    # Reset status
    import_record.status = "processing"
    import_record.error_message = None
    import_record.analysis_summary = None
    import_record.top_loss_themes = None
    import_record.top_win_themes = None

    # Queue new job
    try:
        queue_service = QueueService(db)
        job = queue_service.create_job(
            job_type=JobType.ACTIVITY_INSIGHT,
            product_id=product_id,
            input_data={
                "import_id": import_record.id,
                "parsed_data": import_record.raw_content
            },
            user_id=current_user.id
        )

        # Dispatch to Celery
        celery_result = send_task('activity_insight_task', job.id)
        queue_service.mark_queued(job.id, celery_result.id)

        import_record.job_uuid = job.job_uuid
    except Exception as e:
        import_record.status = "failed"
        import_record.error_message = f"Failed to queue job: {str(e)}"

    db.commit()

    return ActivityImportResponse(
        id=import_record.id,
        product_id=import_record.product_id,
        filename=import_record.filename,
        source_type=import_record.source_type,
        format_type=import_record.format_type,
        status=import_record.status,
        imported_at=import_record.imported_at,
        deals_count=import_record.deals_count,
        activities_count=import_record.activities_count,
        support_tickets_count=import_record.support_tickets_count,
        error_message=import_record.error_message
    )
