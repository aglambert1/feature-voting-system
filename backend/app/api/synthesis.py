"""
Synthesis API endpoints.

This module provides REST API endpoints for:
- Triggering opportunity synthesis runs
- Retrieving synthesis results
- Exporting opportunities in JSON/CSV formats
- Creating ideas from opportunities
"""

import csv
import io
import json
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from app.database import get_db
from app.models.user import User
from app.models.competitor_intelligence import CIProduct
from app.models.synthesis import SynthesisRun, SynthesizedOpportunity
from app.models.competitive_reports import LandscapeOpportunityReport
from app.models.internal_feedback import (
    InternalFeedbackImport,
    WinLossTheme,
    SupportTheme
)
from app.models.idea import Idea, IdeaStatus, SourceType
from app.models.vote import Vote
from sqlalchemy import func
from app.models.queue import JobType, JobStatus
from app.schemas.synthesis import (
    SynthesisRunResponse,
    SynthesizedOpportunityResponse,
    SynthesisResultsResponse,
    SynthesisSourcesAvailable,
    SynthesisStatusResponse
)
from app.services.queue_service import QueueService
from app.utils.security import get_current_active_user, get_product_owner_or_admin
from app.queue.tasks import opportunity_synthesis_task


router = APIRouter(
    prefix="/synthesis",
    tags=["Opportunity Synthesis"]
)


# ============================================================================
# Response Schemas
# ============================================================================

class SynthesisRunsListResponse(BaseModel):
    """Response for list of synthesis runs."""
    runs: List[SynthesisRunResponse]
    total: int


class CreateIdeaFromOpportunityRequest(BaseModel):
    """Request to create an idea from an opportunity."""
    additional_description: Optional[str] = Field(
        default=None,
        description="Additional context to add to the idea description"
    )


class CreateIdeaResponse(BaseModel):
    """Response for created idea."""
    idea_id: int
    title: str
    status: str


# ============================================================================
# API Endpoints
# ============================================================================

@router.get(
    "/{product_id}/status",
    response_model=SynthesisStatusResponse
)
async def get_synthesis_status(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Check what sources are available for synthesis.

    Returns information about:
    - Available competitive data (landscape report)
    - Available customer ideas
    - Available internal feedback themes
    - Previous synthesis run (if any)
    """
    # Verify product exists
    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )

    sources = SynthesisSourcesAvailable()

    # Check competitive data
    landscape_report = db.query(LandscapeOpportunityReport).filter(
        LandscapeOpportunityReport.product_id == product_id
    ).first()
    if landscape_report and landscape_report.feature_opportunities:
        count = len(landscape_report.feature_opportunities)
        sources.competitive = True
        sources.competitive_detail = f"{count} opportunities from landscape analysis"

    # Check customer ideas - only count ACCEPTED ideas (those open for voting)
    ideas_count = db.query(Idea).filter(
        Idea.product_id == product_id,
        Idea.status == IdeaStatus.ACCEPTED
    ).count()
    if ideas_count > 0:
        # Count total votes by joining with Vote table (only for accepted ideas)
        total_votes = db.query(func.count(Vote.id)).join(
            Idea, Vote.idea_id == Idea.id
        ).filter(
            Idea.product_id == product_id,
            Idea.status == IdeaStatus.ACCEPTED
        ).scalar() or 0
        sources.customer = True
        sources.customer_detail = f"{ideas_count} ideas with {total_votes} total votes"

    # Check internal feedback
    latest_import = db.query(InternalFeedbackImport).filter(
        InternalFeedbackImport.product_id == product_id,
        InternalFeedbackImport.themes_extracted == True
    ).order_by(desc(InternalFeedbackImport.imported_at)).first()

    if latest_import:
        winloss_count = db.query(WinLossTheme).filter(
            WinLossTheme.import_id == latest_import.id
        ).count()
        support_count = db.query(SupportTheme).filter(
            SupportTheme.import_id == latest_import.id
        ).count()
        if winloss_count > 0 or support_count > 0:
            sources.internal = True
            sources.internal_detail = f"{winloss_count} win/loss themes, {support_count} support themes"

    # Check for previous run
    previous_run = db.query(SynthesisRun).filter(
        SynthesisRun.product_id == product_id
    ).order_by(desc(SynthesisRun.created_at)).first()

    return SynthesisStatusResponse(
        product_id=product_id,
        sources_available=sources,
        has_previous_run=previous_run is not None,
        previous_run=_to_run_response(previous_run) if previous_run else None
    )


@router.post(
    "/{product_id}/run",
    response_model=SynthesisRunResponse,
    status_code=status.HTTP_201_CREATED
)
async def trigger_synthesis(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_product_owner_or_admin)
):
    """
    Trigger a new opportunity synthesis run.

    The synthesis will combine:
    - Competitive opportunities from landscape analysis
    - Customer ideas with votes
    - Internal feedback themes (win/loss + support)

    Returns the synthesis run record. Processing happens in the background.
    """
    # Verify product exists
    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )

    # Check that at least one source has data
    has_competitive = db.query(LandscapeOpportunityReport).filter(
        LandscapeOpportunityReport.product_id == product_id
    ).first() is not None

    has_ideas = db.query(Idea).filter(
        Idea.product_id == product_id
    ).count() > 0

    has_internal = db.query(InternalFeedbackImport).filter(
        InternalFeedbackImport.product_id == product_id,
        InternalFeedbackImport.themes_extracted == True
    ).first() is not None

    if not any([has_competitive, has_ideas, has_internal]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No source data available for synthesis. Run competitive analysis, add customer ideas, or import internal feedback first."
        )

    # Create synthesis run record
    synthesis_run = SynthesisRun(
        product_id=product_id,
        status="pending"
    )
    db.add(synthesis_run)
    db.commit()
    db.refresh(synthesis_run)

    # Queue synthesis job
    try:
        queue_service = QueueService(db)
        job = queue_service.create_job(
            job_type=JobType.OPPORTUNITY_SYNTHESIS,
            product_id=product_id,
            input_data={
                "synthesis_run_id": synthesis_run.id
            },
            user_id=current_user.id
        )

        # Dispatch to Celery
        celery_result = opportunity_synthesis_task.delay(job.id)
        queue_service.mark_queued(job.id, celery_result.id)

        synthesis_run.job_uuid = job.job_uuid
        synthesis_run.status = "processing"
        db.commit()
    except Exception as e:
        synthesis_run.status = "failed"
        synthesis_run.error_message = f"Failed to queue job: {str(e)}"
        db.commit()

    return _to_run_response(synthesis_run)


@router.get(
    "/{product_id}/runs",
    response_model=SynthesisRunsListResponse
)
async def list_synthesis_runs(
    product_id: int,
    limit: int = 10,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List all synthesis runs for a product."""
    # Verify product exists
    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )

    # Get total count
    total = db.query(SynthesisRun).filter(
        SynthesisRun.product_id == product_id
    ).count()

    # Get runs
    runs = db.query(SynthesisRun).filter(
        SynthesisRun.product_id == product_id
    ).order_by(desc(SynthesisRun.created_at)).offset(offset).limit(limit).all()

    return SynthesisRunsListResponse(
        runs=[_to_run_response(r) for r in runs],
        total=total
    )


@router.get(
    "/{product_id}/runs/{run_id}",
    response_model=SynthesisResultsResponse
)
async def get_synthesis_results(
    product_id: int,
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get full synthesis results including opportunities."""
    synthesis_run = db.query(SynthesisRun).filter(
        SynthesisRun.id == run_id,
        SynthesisRun.product_id == product_id
    ).first()

    if not synthesis_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Synthesis run not found"
        )

    # Get opportunities
    opportunities = db.query(SynthesizedOpportunity).filter(
        SynthesizedOpportunity.synthesis_run_id == run_id
    ).order_by(desc(SynthesizedOpportunity.priority_score)).all()

    return SynthesisResultsResponse(
        run=_to_run_response(synthesis_run),
        opportunities=[_to_opportunity_response(o) for o in opportunities]
    )


@router.get(
    "/{product_id}/latest",
    response_model=SynthesisResultsResponse
)
async def get_latest_synthesis(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get the latest completed synthesis results."""
    # Verify product exists
    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )

    synthesis_run = db.query(SynthesisRun).filter(
        SynthesisRun.product_id == product_id,
        SynthesisRun.status == "completed"
    ).order_by(desc(SynthesisRun.created_at)).first()

    if not synthesis_run:
        # Return empty response instead of 404
        return SynthesisResultsResponse(
            run=SynthesisRunResponse(
                id=0,
                product_id=product_id,
                status="none",
                sources_used=[],
                created_at=datetime.utcnow(),
                opportunity_count=0
            ),
            opportunities=[]
        )

    # Get opportunities
    opportunities = db.query(SynthesizedOpportunity).filter(
        SynthesizedOpportunity.synthesis_run_id == synthesis_run.id
    ).order_by(desc(SynthesizedOpportunity.priority_score)).all()

    return SynthesisResultsResponse(
        run=_to_run_response(synthesis_run),
        opportunities=[_to_opportunity_response(o) for o in opportunities]
    )


@router.get(
    "/{product_id}/runs/{run_id}/export/json"
)
async def export_synthesis_json(
    product_id: int,
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Export synthesis results as JSON."""
    synthesis_run = db.query(SynthesisRun).filter(
        SynthesisRun.id == run_id,
        SynthesisRun.product_id == product_id
    ).first()

    if not synthesis_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Synthesis run not found"
        )

    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()

    opportunities = db.query(SynthesizedOpportunity).filter(
        SynthesizedOpportunity.synthesis_run_id == run_id
    ).order_by(desc(SynthesizedOpportunity.priority_score)).all()

    export_data = {
        "version": "1.0",
        "export_format": "json",
        "generated_at": datetime.utcnow().isoformat(),
        "product_id": product_id,
        "product_name": product.product_name if product else None,
        "synthesis_run_id": run_id,
        "analysis_summary": synthesis_run.analysis_summary,
        "opportunities": [o.get_export_dict() for o in opportunities],
        "metadata": {
            "sources_used": synthesis_run.sources_used,
            "source_snapshot": synthesis_run.source_snapshot,
            "summary_stats": synthesis_run.summary_stats
        }
    }

    # Create response as downloadable file
    content = json.dumps(export_data, indent=2)
    filename = f"synthesis_{product.product_name.replace(' ', '_')}_{run_id}.json" if product else f"synthesis_{run_id}.json"

    return StreamingResponse(
        io.BytesIO(content.encode()),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get(
    "/{product_id}/runs/{run_id}/export/csv"
)
async def export_synthesis_csv(
    product_id: int,
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Export synthesis results as CSV."""
    synthesis_run = db.query(SynthesisRun).filter(
        SynthesisRun.id == run_id,
        SynthesisRun.product_id == product_id
    ).first()

    if not synthesis_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Synthesis run not found"
        )

    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()

    opportunities = db.query(SynthesizedOpportunity).filter(
        SynthesizedOpportunity.synthesis_run_id == run_id
    ).order_by(desc(SynthesizedOpportunity.priority_score)).all()

    # Create CSV content
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        "Opportunity Name",
        "Summary",
        "Priority Score",
        "Match Type",
        "Sources",
        "Competitive Evidence",
        "Customer Evidence",
        "Internal Evidence",
        "Recommended Action",
        "Keywords"
    ])

    # Data rows
    for opp in opportunities:
        comp_evidence = ""
        if opp.competitive_evidence:
            comp_evidence = f"{opp.competitive_evidence.get('competitor_count', 0)} competitors"

        cust_evidence = ""
        if opp.customer_evidence:
            cust_evidence = f"{opp.customer_evidence.get('vote_count', 0)} votes"

        int_evidence = ""
        if opp.internal_evidence:
            parts = []
            if opp.internal_evidence.get('winloss'):
                wl = opp.internal_evidence['winloss']
                parts.append(f"{wl.get('deal_count', 0)} deals (${wl.get('total_value', 0):,.0f})")
            if opp.internal_evidence.get('support'):
                sup = opp.internal_evidence['support']
                parts.append(f"{sup.get('ticket_count', 0)} tickets")
            int_evidence = ", ".join(parts)

        writer.writerow([
            opp.opportunity_name,
            opp.opportunity_summary or "",
            opp.priority_score,
            opp.get_match_type_label(),
            ", ".join(opp.sources or []),
            comp_evidence,
            cust_evidence,
            int_evidence,
            opp.recommended_action or "",
            ", ".join(opp.feature_keywords or [])
        ])

    # Create response
    content = output.getvalue()
    filename = f"synthesis_{product.product_name.replace(' ', '_')}_{run_id}.csv" if product else f"synthesis_{run_id}.csv"

    return StreamingResponse(
        io.BytesIO(content.encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post(
    "/{product_id}/opportunities/{opportunity_id}/create-idea",
    response_model=CreateIdeaResponse
)
async def create_idea_from_opportunity(
    product_id: int,
    opportunity_id: int,
    request: CreateIdeaFromOpportunityRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_product_owner_or_admin)
):
    """Create an idea from a synthesized opportunity."""
    opportunity = db.query(SynthesizedOpportunity).filter(
        SynthesizedOpportunity.id == opportunity_id,
        SynthesizedOpportunity.product_id == product_id
    ).first()

    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found"
        )

    if opportunity.linked_idea_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An idea has already been created from this opportunity"
        )

    # Build description from synthesis evidence
    description_parts = [opportunity.opportunity_summary or ""]

    description_parts.append("\n\n**Synthesis Evidence:**")

    if opportunity.competitive_evidence:
        ce = opportunity.competitive_evidence
        competitors = ce.get('competitors', [])
        description_parts.append(f"\n- **Competitive**: {len(competitors)} competitor(s) have this feature ({ce.get('prevalence', 'Unknown')})")

    if opportunity.customer_evidence:
        ce = opportunity.customer_evidence
        description_parts.append(f"\n- **Customer Votes**: {ce.get('vote_count', 0)} votes on related idea")

    if opportunity.internal_evidence:
        ie = opportunity.internal_evidence
        if ie.get('winloss'):
            wl = ie['winloss']
            description_parts.append(f"\n- **Win/Loss**: {wl.get('deal_count', 0)} deals (${wl.get('total_value', 0):,.0f}) mentioned this")
        if ie.get('support'):
            sup = ie['support']
            description_parts.append(f"\n- **Support**: {sup.get('ticket_count', 0)} support tickets related to this")

    if request.additional_description:
        description_parts.append(f"\n\n**Additional Context:**\n{request.additional_description}")

    # Create the idea
    idea = Idea(
        product_id=product_id,
        title=opportunity.opportunity_name,
        description="\n".join(description_parts),
        source_type=SourceType.COMPETITIVE_INTELLIGENCE,
        submitter_id=current_user.id,
        status=IdeaStatus.SUBMITTED,
        vote_count=0
    )
    db.add(idea)
    db.commit()
    db.refresh(idea)

    # Link the opportunity to the idea
    opportunity.linked_idea_id = idea.id
    db.commit()

    return CreateIdeaResponse(
        idea_id=idea.id,
        title=idea.title,
        status=idea.status.value
    )


# ============================================================================
# Helper Functions
# ============================================================================

def _to_run_response(run: SynthesisRun) -> SynthesisRunResponse:
    """Convert SynthesisRun to response model."""
    return SynthesisRunResponse(
        id=run.id,
        product_id=run.product_id,
        status=run.status,
        error_message=run.error_message,
        source_snapshot=run.source_snapshot,
        sources_used=run.sources_used or [],
        summary_stats=run.summary_stats,
        analysis_summary=run.analysis_summary,
        job_uuid=run.job_uuid,
        created_at=run.created_at,
        completed_at=run.completed_at,
        opportunity_count=len(run.opportunities) if run.opportunities else 0
    )


def _to_opportunity_response(opp: SynthesizedOpportunity) -> SynthesizedOpportunityResponse:
    """Convert SynthesizedOpportunity to response model."""
    return SynthesizedOpportunityResponse(
        id=opp.id,
        synthesis_run_id=opp.synthesis_run_id,
        product_id=opp.product_id,
        opportunity_name=opp.opportunity_name,
        opportunity_summary=opp.opportunity_summary,
        priority_score=opp.priority_score,
        source_count=opp.source_count,
        sources=opp.sources or [],
        competitive_evidence=opp.competitive_evidence,
        customer_evidence=opp.customer_evidence,
        internal_evidence=opp.internal_evidence,
        recommended_action=opp.recommended_action,
        feature_keywords=opp.feature_keywords or [],
        linked_idea_id=opp.linked_idea_id,
        created_at=opp.created_at
    )
