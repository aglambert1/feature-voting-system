"""Competitive intelligence tools for MCP server."""

from mcp_server import mcp
from mcp_server.db import get_session
from mcp_server.permissions import require_product_access, require_product_analyzed, require_no_active_job

from app.models.competitor_intelligence import ProductPermissionLevel


@mcp.tool()
def ci_get_competitor_list(product_id: int) -> dict:
    """List all tracked competitors for a product with their analysis status."""
    from app.models.competitor_intelligence import ProductCompetitor
    from app.models.competitive_reports import CompetitorFunctionalReport

    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

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
        denied = require_product_access(db, product_id)
        if denied:
            return denied

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
        denied = require_product_access(db, product_id)
        if denied:
            return denied

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
        denied = require_product_access(db, product_id)
        if denied:
            return denied

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
        denied = require_product_access(db, product_id)
        if denied:
            return denied

        alerts = db.query(CompetitorAlert).filter(
            CompetitorAlert.product_id == product_id
        ).order_by(CompetitorAlert.created_at.desc()).limit(limit).all()

        return {
            "product_id": product_id,
            "alerts": [a.to_dict() for a in alerts],
        }


@mcp.tool()
def ci_add_competitor(product_id: int, competitor_name: str, competitor_url: str) -> dict:
    """Add a new competitor to track for a product. The competitor will be available for audits and landscape analysis.

    Args:
        product_id: The product to add the competitor to.
        competitor_name: Name of the competitor (e.g. "Asana").
        competitor_url: Website URL (e.g. "https://asana.com").
    """
    from app.models.competitor_intelligence import ProductCompetitor
    from urllib.parse import urlparse

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.EDIT)
        if denied:
            return denied

        # Check for duplicate by name
        existing = db.query(ProductCompetitor).filter(
            ProductCompetitor.product_id == product_id,
            ProductCompetitor.competitor_name.ilike(competitor_name),
        ).first()
        if existing:
            return {"error": f"Competitor '{existing.competitor_name}' already exists (id={existing.id})"}

        # Check for duplicate by domain
        parsed = urlparse(competitor_url)
        domain = parsed.netloc or parsed.path
        domain = domain.replace("www.", "")
        existing_url = db.query(ProductCompetitor).filter(
            ProductCompetitor.product_id == product_id,
            ProductCompetitor.competitor_url.ilike(f"%{domain}%"),
        ).first()
        if existing_url:
            return {"error": f"A competitor with domain '{domain}' already exists: {existing_url.competitor_name}"}

        competitor = ProductCompetitor(
            product_id=product_id,
            competitor_name=competitor_name,
            competitor_url=competitor_url,
            deep_analysis_enabled=True,
            status="active",
        )
        db.add(competitor)
        db.flush()

        return {
            "competitor_id": competitor.id,
            "competitor_name": competitor.competitor_name,
            "competitor_url": competitor.competitor_url,
            "deep_analysis_enabled": True,
            "message": f"Competitor '{competitor_name}' added. Run ci_run_competitor_audit to analyze.",
        }


@mcp.tool()
def ci_run_discovery(product_id: int, max_competitors: int = 5) -> dict:
    """Discover competitors automatically using AI analysis of the product. Returns a job ID.

    Args:
        product_id: The product to discover competitors for.
        max_competitors: Maximum number of competitors to discover (1-20, default 5).
    """
    from app.models.queue import JobType
    from app.services.queue_service import QueueService
    from app.queue.tasks import discover_competitors_task

    max_competitors = max(1, min(20, max_competitors))

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.EDIT)
        if denied:
            return denied
        not_ready = require_product_analyzed(db, product_id)
        if not_ready:
            return not_ready
        conflict = require_no_active_job(db, product_id, JobType.COMPETITOR_DISCOVERY, "Competitor discovery")
        if conflict:
            return conflict

        queue_service = QueueService(db)
        job = queue_service.create_job(
            job_type=JobType.COMPETITOR_DISCOVERY,
            input_data={"max_competitors": max_competitors},
            product_id=product_id,
        )

        from mcp_server.db import dispatch_task
        result = dispatch_task(discover_competitors_task, job.id)
        queue_service.mark_queued(job.id, result.id)

        return {
            "job_id": job.id,
            "job_uuid": job.job_uuid,
            "max_competitors": max_competitors,
            "status": "queued",
            "message": f"Competitor discovery queued (max {max_competitors}). Use job_get_status to check progress.",
        }


@mcp.tool()
def ci_run_competitor_audit(product_id: int, competitor_name: str) -> dict:
    """Trigger a functional audit for a single competitor. Returns a job ID to check status with job_get_status."""
    from app.models.competitor_intelligence import ProductCompetitor
    from app.models.queue import JobType
    from app.services.queue_service import QueueService

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.EDIT)
        if denied:
            return denied

        competitor = db.query(ProductCompetitor).filter(
            ProductCompetitor.product_id == product_id,
            ProductCompetitor.competitor_name.ilike(f"%{competitor_name}%"),
        ).first()

        if not competitor:
            return {"error": f"No competitor matching '{competitor_name}' found for product {product_id}"}

        # Check for active audit job
        conflict = require_no_active_job(db, product_id, JobType.FUNCTIONAL_AUDIT, "Functional audit")
        if conflict:
            return conflict

        # Auditing a competitor implies it should be included in synthesis
        if not competitor.deep_analysis_enabled:
            competitor.deep_analysis_enabled = True
            db.flush()

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
def ci_set_deep_analysis(product_id: int, competitor_name: str, enabled: bool = True) -> dict:
    """Enable or disable a competitor for deep analysis and synthesis inclusion.

    Args:
        product_id: The product the competitor belongs to.
        competitor_name: Name (or partial name) of the competitor.
        enabled: True to include in synthesis, False to exclude.
    """
    from app.models.competitor_intelligence import ProductCompetitor

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.EDIT)
        if denied:
            return denied

        competitor = db.query(ProductCompetitor).filter(
            ProductCompetitor.product_id == product_id,
            ProductCompetitor.competitor_name.ilike(f"%{competitor_name}%"),
        ).first()

        if not competitor:
            return {"error": f"No competitor matching '{competitor_name}' found for product {product_id}"}

        competitor.deep_analysis_enabled = enabled
        db.flush()

        return {
            "competitor_id": competitor.id,
            "competitor_name": competitor.competitor_name,
            "deep_analysis_enabled": competitor.deep_analysis_enabled,
            "message": f"{'Enabled' if enabled else 'Disabled'} deep analysis for {competitor.competitor_name}.",
        }


@mcp.tool()
def ci_run_analysis(product_id: int) -> dict:
    """Trigger a landscape synthesis across all competitors. Returns a job ID to check status with job_get_status."""
    from app.models.queue import JobType
    from app.models.competitive_reports import CompetitorFunctionalReport
    from app.services.queue_service import QueueService

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.EDIT)
        if denied:
            return denied

        # Need at least one functional report
        report_count = db.query(CompetitorFunctionalReport).join(
            CompetitorFunctionalReport.competitor
        ).filter(
            CompetitorFunctionalReport.competitor.has(product_id=product_id)
        ).count()
        if report_count == 0:
            return {
                "error": "No functional reports found. Run ci_run_competitor_audit for at least one competitor first.",
            }

        conflict = require_no_active_job(db, product_id, JobType.LANDSCAPE_SYNTHESIS, "Landscape synthesis")
        if conflict:
            return conflict

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
