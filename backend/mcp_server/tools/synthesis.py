"""Synthesis tools for MCP server."""

from mcp_server import mcp
from mcp_server.db import get_session


@mcp.tool()
def synthesis_get_opportunities(
    product_id: int, min_sources: int = 1, limit: int = 15
) -> dict:
    """Get prioritized product opportunities backed by evidence from competitive intelligence, customer votes, and internal feedback. Higher source_count means stronger convergent evidence."""
    from app.models.synthesis import SynthesisRun, SynthesizedOpportunity

    with get_session() as db:
        latest_run = (
            db.query(SynthesisRun)
            .filter(
                SynthesisRun.product_id == product_id,
                SynthesisRun.status == "completed",
            )
            .order_by(SynthesisRun.completed_at.desc())
            .first()
        )

        if not latest_run:
            return {
                "error": "No completed synthesis run found. Run synthesis_run first.",
                "evidence_gaps": ["no synthesis data available"],
            }

        opportunities = (
            db.query(SynthesizedOpportunity)
            .filter(
                SynthesizedOpportunity.synthesis_run_id == latest_run.id,
                SynthesizedOpportunity.source_count >= min_sources,
            )
            .order_by(SynthesizedOpportunity.priority_score.desc())
            .limit(limit)
            .all()
        )

        return {
            "product_id": product_id,
            "synthesis_run_id": latest_run.id,
            "completed_at": latest_run.completed_at.isoformat() if latest_run.completed_at else None,
            "analysis_summary": latest_run.analysis_summary,
            "opportunities": [
                {
                    "opportunity_id": o.id,
                    "name": o.opportunity_name,
                    "summary": o.opportunity_summary,
                    "priority_score": o.priority_score,
                    "source_count": o.source_count,
                    "sources": o.sources,
                    "recommended_action": o.recommended_action,
                    "jtbd_statement": o.jtbd_statement,
                    "feature_keywords": o.feature_keywords,
                }
                for o in opportunities
            ],
            "evidence_gaps": [
                "market sizing not available",
                "engineering effort not estimated",
                "usability not validated",
            ],
        }


@mcp.tool()
def synthesis_get_evidence(opportunity_id: int) -> dict:
    """Get detailed evidence for a specific opportunity from all contributing sources."""
    from app.models.synthesis import SynthesizedOpportunity

    with get_session() as db:
        opp = db.query(SynthesizedOpportunity).get(opportunity_id)
        if not opp:
            return {"error": f"Opportunity {opportunity_id} not found"}

        return {
            "opportunity_id": opp.id,
            "name": opp.opportunity_name,
            "summary": opp.opportunity_summary,
            "priority_score": opp.priority_score,
            "source_count": opp.source_count,
            "jtbd_statement": opp.jtbd_statement,
            "competitive_evidence": opp.competitive_evidence,
            "customer_evidence": opp.customer_evidence,
            "internal_evidence": opp.internal_evidence,
            "recommended_action": opp.recommended_action,
            "evidence_gaps": [
                "market sizing not available",
                "engineering effort not estimated",
            ],
        }


@mcp.tool()
def synthesis_run(product_id: int) -> dict:
    """Trigger a new opportunity synthesis combining competitive, customer, and internal data. Returns job ID."""
    from app.models.queue import JobType
    from app.models.synthesis import SynthesisRun
    from app.services.queue_service import QueueService
    from app.queue.tasks import opportunity_synthesis_task

    with get_session() as db:
        # Create SynthesisRun record first (same pattern as API)
        synthesis_run = SynthesisRun(
            product_id=product_id,
            status="pending",
        )
        db.add(synthesis_run)
        db.flush()

        queue_service = QueueService(db)
        job = queue_service.create_job(
            job_type=JobType.OPPORTUNITY_SYNTHESIS,
            input_data={"synthesis_run_id": synthesis_run.id},
            product_id=product_id,
        )

        from mcp_server.db import dispatch_task
        result = dispatch_task(opportunity_synthesis_task, job.id)
        queue_service.mark_queued(job.id, result.id)

        return {
            "job_id": job.id,
            "job_uuid": job.job_uuid,
            "synthesis_run_id": synthesis_run.id,
            "status": "queued",
            "message": "Opportunity synthesis queued. Use job_get_status to check progress.",
        }


@mcp.tool()
def synthesis_get_sources(product_id: int) -> dict:
    """Check what data sources are available for synthesis and when they were last updated."""
    from app.models.competitive_reports import LandscapeOpportunityReport
    from app.models.idea import Idea
    from app.models.internal_feedback import InternalFeedbackImport
    from sqlalchemy import func

    with get_session() as db:
        landscape = db.query(LandscapeOpportunityReport).filter(
            LandscapeOpportunityReport.product_id == product_id
        ).first()

        idea_count = db.query(func.count(Idea.id)).filter(
            Idea.product_id == product_id, Idea.is_active == True
        ).scalar() or 0

        latest_import = (
            db.query(InternalFeedbackImport)
            .filter(
                InternalFeedbackImport.product_id == product_id,
                InternalFeedbackImport.status == "completed",
            )
            .order_by(InternalFeedbackImport.processed_at.desc())
            .first()
        )

        return {
            "product_id": product_id,
            "sources": {
                "competitive_landscape": {
                    "available": landscape is not None,
                    "last_updated": landscape.generated_at.isoformat() if landscape else None,
                    "version": landscape.report_version if landscape else None,
                    "competitors_analyzed": len(landscape.source_competitor_names) if landscape and landscape.source_competitor_names else 0,
                },
                "customer_ideas": {
                    "available": idea_count > 0,
                    "total_ideas": idea_count,
                },
                "internal_feedback": {
                    "available": latest_import is not None,
                    "last_imported": latest_import.processed_at.isoformat() if latest_import and latest_import.processed_at else None,
                    "deals_count": latest_import.deals_count if latest_import else 0,
                    "tickets_count": latest_import.tickets_count if latest_import else 0,
                },
            },
        }
