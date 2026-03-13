"""Competitive intelligence tools for MCP server."""

from mcp_server import mcp
from mcp_server.db import get_session


@mcp.tool()
def ci_get_competitor_list(product_id: int) -> dict:
    """List all tracked competitors for a product with their analysis status."""
    from app.models.competitor_intelligence import ProductCompetitor
    from app.models.competitive_reports import CompetitorFunctionalReport

    with get_session() as db:
        competitors = db.query(ProductCompetitor).filter(
            ProductCompetitor.product_id == product_id,
            ProductCompetitor.status == "active",
        ).all()

        result = []
        for c in competitors:
            report = db.query(CompetitorFunctionalReport).filter(
                CompetitorFunctionalReport.product_competitor_id == c.id
            ).first()
            result.append({
                "competitor_id": c.id,
                "competitor_name": c.competitor_name,
                "competitor_url": c.competitor_url,
                "deep_analysis_enabled": c.deep_analysis_enabled,
                "deep_analysis_status": c.deep_analysis_status,
                "has_report": report is not None,
                "report_version": report.report_version if report else None,
                "last_analyzed": report.generated_at.isoformat() if report else None,
            })
        return {"product_id": product_id, "competitors": result}


@mcp.tool()
def ci_get_competitor_report(product_id: int, competitor_name: str) -> dict:
    """Get the functional audit report for a specific competitor, showing feature-by-feature comparison."""
    from app.models.competitor_intelligence import ProductCompetitor
    from app.models.competitive_reports import CompetitorFunctionalReport

    with get_session() as db:
        # Fuzzy match on competitor name
        competitor = db.query(ProductCompetitor).filter(
            ProductCompetitor.product_id == product_id,
            ProductCompetitor.competitor_name.ilike(f"%{competitor_name}%"),
        ).first()

        if not competitor:
            return {"error": f"No competitor matching '{competitor_name}' found"}

        report = db.query(CompetitorFunctionalReport).filter(
            CompetitorFunctionalReport.product_competitor_id == competitor.id
        ).first()

        if not report:
            return {"error": f"No report available for {competitor.competitor_name}"}

        # Include any evidence linked to this competitor
        from app.models.evidence import Evidence
        linked_evidence = db.query(Evidence).filter(
            Evidence.product_id == product_id,
            Evidence.competitor_id == competitor.id,
        ).order_by(Evidence.created_at.desc()).limit(20).all()

        return {
            "competitor_name": competitor.competitor_name,
            "report_version": report.report_version,
            "generated_at": report.generated_at.isoformat(),
            "competitor_context": report.competitor_context,
            "functional_comparison": report.functional_comparison,
            "gaps_deep_dive": report.gaps_deep_dive,
            "technical_constraints": report.technical_constraints,
            "changes_from_previous": report.changes_from_previous,
            "additional_evidence": [e.to_summary_dict() for e in linked_evidence],
        }


@mcp.tool()
def ci_get_landscape(product_id: int) -> dict:
    """Get the cross-competitor landscape analysis showing feature prevalence, gaps, and opportunities across all competitors."""
    from app.models.competitive_reports import LandscapeOpportunityReport

    with get_session() as db:
        report = db.query(LandscapeOpportunityReport).filter(
            LandscapeOpportunityReport.product_id == product_id
        ).first()

        if not report:
            return {"error": "No landscape analysis available. Run ci_run_analysis first."}

        return {
            "product_id": product_id,
            "report_version": report.report_version,
            "generated_at": report.generated_at.isoformat(),
            "source_competitors": report.source_competitor_names,
            "feature_cluster_matrix": report.feature_cluster_matrix,
            "feature_opportunities": report.feature_opportunities,
            "high_impact_gaps": report.high_impact_gaps,
            "changes_from_previous": report.changes_from_previous,
        }


@mcp.tool()
def ci_search_features(product_id: int, query: str) -> dict:
    """Search across all competitor reports and competitive evidence for a specific capability using semantic matching. Returns both structured competitor features and ad-hoc competitive intelligence from the factbase."""
    from app.services.embedding_service import generate_embedding
    from app.services.vector_service import VectorService
    from app.models.evidence import COMPETITIVE_EVIDENCE_TYPES

    with get_session() as db:
        query_emb = generate_embedding(query, input_type="query")
        matches = VectorService.find_similar_competitor_features(
            db, query_emb, product_id, limit=10
        )

        # Also search competitive evidence
        competitive_types = [et.value for et in COMPETITIVE_EVIDENCE_TYPES]
        evidence_matches = VectorService.find_similar_evidence(
            db, query_emb, product_id, limit=5,
            evidence_types=competitive_types,
        )

        return {
            "query": query,
            "matches": [
                {
                    "feature_id": m[0],
                    "competitor_name": m[1] if len(m) > 1 else None,
                    "feature_name": m[2] if len(m) > 2 else None,
                    "feature_description": m[3] if len(m) > 3 else None,
                    "similarity": round(float(m[4]), 3) if len(m) > 4 else None,
                }
                for m in matches
            ],
            "evidence": [
                {
                    "evidence_id": e["evidence_id"],
                    "title": e["title"],
                    "evidence_type": e["evidence_type"],
                    "source_url": e["source_url"],
                    "source_description": e["source_description"],
                    "similarity": round(1 - float(e["distance"]) / 2, 3),
                }
                for e in evidence_matches
            ],
        }


@mcp.tool()
def ci_get_alerts(product_id: int, limit: int = 20) -> dict:
    """Get recent competitive alerts — new competitors, competitor changes."""
    from app.models.competitor_intelligence import CompetitorAlert

    with get_session() as db:
        alerts = db.query(CompetitorAlert).filter(
            CompetitorAlert.product_id == product_id
        ).order_by(CompetitorAlert.created_at.desc()).limit(limit).all()

        return {
            "product_id": product_id,
            "alerts": [a.to_dict() for a in alerts],
        }


@mcp.tool()
def ci_run_competitor_audit(product_id: int, competitor_name: str) -> dict:
    """Trigger a functional audit for a single competitor. Returns a job ID to check status with job_get_status."""
    from app.models.competitor_intelligence import ProductCompetitor
    from app.models.queue import JobType
    from app.services.queue_service import QueueService

    with get_session() as db:
        competitor = db.query(ProductCompetitor).filter(
            ProductCompetitor.product_id == product_id,
            ProductCompetitor.competitor_name.ilike(f"%{competitor_name}%"),
        ).first()

        if not competitor:
            return {"error": f"No competitor matching '{competitor_name}' found for product {product_id}"}

        queue_service = QueueService(db)
        job = queue_service.create_job(
            job_type=JobType.FUNCTIONAL_AUDIT,
            input_data={"competitor_id": competitor.id},
            product_id=product_id,
        )

        from app.queue.tasks import functional_audit_task
        from mcp_server.db import dispatch_task
        result = dispatch_task(functional_audit_task, job.id)
        queue_service.mark_queued(job.id, result.id)

        return {
            "job_id": job.id,
            "job_uuid": job.job_uuid,
            "competitor_name": competitor.competitor_name,
            "status": "queued",
            "message": f"Functional audit for {competitor.competitor_name} queued. Use job_get_status to check progress.",
        }


@mcp.tool()
def ci_run_analysis(product_id: int) -> dict:
    """Trigger a landscape synthesis across all competitors. Returns a job ID to check status with job_get_status."""
    from app.models.queue import JobType
    from app.services.queue_service import QueueService

    with get_session() as db:
        queue_service = QueueService(db)
        job = queue_service.create_job(
            job_type=JobType.LANDSCAPE_SYNTHESIS,
            input_data={"product_id": product_id},
            product_id=product_id,
        )

        from app.queue.tasks import landscape_synthesis_task
        from mcp_server.db import dispatch_task
        result = dispatch_task(landscape_synthesis_task, job.id)
        queue_service.mark_queued(job.id, result.id)

        return {
            "job_id": job.id,
            "job_uuid": job.job_uuid,
            "status": "queued",
            "message": "Landscape synthesis queued. Use job_get_status to check progress.",
        }
