"""Synthesis tools for MCP server."""

from typing import List, Optional

from mcp_server import mcp
from mcp_server.db import get_session
from mcp_server.permissions import require_product_access, require_no_active_job, resolve_user_id_for_job

from app.models.competitor_intelligence import ProductPermissionLevel


VALID_SOURCE_TYPES = {"competitive", "customer", "internal", "evidence"}


@mcp.tool()
def synthesis_get_opportunities(
    product_id: int, min_sources: int = 1, limit: int = 15
) -> dict:
    """Get prioritized product opportunities backed by evidence from competitive intelligence, customer votes, internal feedback, and factbase evidence/research. Higher source_count (1-4) means stronger convergent evidence."""
    from app.models.synthesis import SynthesisRun, SynthesizedOpportunity

    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

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
    from app.models.synthesis import SynthesizedOpportunity, SynthesisRun

    with get_session() as db:
        opp = db.query(SynthesizedOpportunity).get(opportunity_id)
        if not opp:
            return {"error": f"Opportunity {opportunity_id} not found"}

        # Resolve product_id through the synthesis run
        run = db.query(SynthesisRun).get(opp.synthesis_run_id)
        if run:
            denied = require_product_access(db, run.product_id)
            if denied:
                return denied

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
            "evidence_signals": opp.evidence_signals,
            "recommended_action": opp.recommended_action,
            "evidence_gaps": [
                "market sizing not available",
                "engineering effort not estimated",
            ],
        }


@mcp.tool()
def synthesis_run(product_id: int) -> dict:
    """Trigger a new opportunity synthesis combining competitive, customer, internal, and factbase evidence data. Returns job ID."""
    from app.models.queue import JobType
    from app.models.synthesis import SynthesisRun
    from app.models.competitive_reports import LandscapeOpportunityReport
    from app.models.idea import Idea
    from app.models.internal_feedback import InternalFeedbackImport
    from app.services.queue_service import QueueService
    from app.queue.tasks import opportunity_synthesis_task

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.EDIT)
        if denied:
            return denied

        # Need at least one data source
        has_landscape = db.query(LandscapeOpportunityReport).filter(
            LandscapeOpportunityReport.product_id == product_id
        ).first() is not None
        has_ideas = db.query(Idea).filter(
            Idea.product_id == product_id, Idea.is_active == True
        ).first() is not None
        has_feedback = db.query(InternalFeedbackImport).filter(
            InternalFeedbackImport.product_id == product_id,
            InternalFeedbackImport.themes_extracted == True,
        ).first() is not None

        if not (has_landscape or has_ideas or has_feedback):
            return {
                "error": "No source data available for synthesis. "
                         "Run competitive analysis, add customer ideas, or import internal feedback first.",
            }

        conflict = require_no_active_job(db, product_id, JobType.OPPORTUNITY_SYNTHESIS, "Opportunity synthesis")
        if conflict:
            return conflict

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
            user_id=resolve_user_id_for_job(db, product_id),
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
def synthesis_list_runs(product_id: int, limit: int = 10) -> dict:
    """List synthesis runs for a product, showing run history and status.

    Args:
        product_id: The product to list synthesis runs for.
        limit: Maximum number of runs to return (default 10).
    """
    from app.models.synthesis import SynthesisRun

    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

        runs = (
            db.query(SynthesisRun)
            .filter(SynthesisRun.product_id == product_id)
            .order_by(SynthesisRun.created_at.desc())
            .limit(limit)
            .all()
        )

        return {
            "product_id": product_id,
            "runs": [
                {
                    "run_id": r.id,
                    "status": r.status,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                    "analysis_summary": r.analysis_summary,
                }
                for r in runs
            ],
        }


@mcp.tool()
def synthesis_get_run(product_id: int, run_id: int) -> dict:
    """Get a specific synthesis run with its opportunities.

    Args:
        product_id: The product the run belongs to.
        run_id: The synthesis run ID.
    """
    from app.models.synthesis import SynthesisRun, SynthesizedOpportunity

    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

        run = db.query(SynthesisRun).filter(
            SynthesisRun.id == run_id,
            SynthesisRun.product_id == product_id,
        ).first()

        if not run:
            return {"error": f"Synthesis run {run_id} not found for product {product_id}"}

        opportunities = (
            db.query(SynthesizedOpportunity)
            .filter(SynthesizedOpportunity.synthesis_run_id == run.id)
            .order_by(SynthesizedOpportunity.priority_score.desc())
            .all()
        )

        return {
            "run_id": run.id,
            "product_id": product_id,
            "status": run.status,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "analysis_summary": run.analysis_summary,
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
        }


@mcp.tool()
def synthesis_get_sources(product_id: int) -> dict:
    """Check what data sources are available for synthesis and when they were last updated."""
    from app.models.competitive_reports import LandscapeOpportunityReport
    from app.models.evidence import Evidence
    from app.models.idea import Idea
    from app.models.internal_feedback import InternalFeedbackImport
    from sqlalchemy import func

    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

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

        evidence_count = db.query(func.count(Evidence.id)).filter(
            Evidence.product_id == product_id
        ).scalar() or 0

        latest_evidence = (
            db.query(Evidence)
            .filter(Evidence.product_id == product_id)
            .order_by(Evidence.created_at.desc())
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
                "factbase_evidence": {
                    "available": evidence_count > 0,
                    "total_evidence": evidence_count,
                    "last_added": latest_evidence.created_at.isoformat() if latest_evidence and latest_evidence.created_at else None,
                },
            },
        }


# ============================================================================
# Phase 3 Unified Synthesis tools
# ============================================================================

def _config_to_dict(config) -> dict:
    """Serialize a SynthesisConfig row to a JSON-friendly dict."""
    return {
        "product_id": config.product_id,
        "included_source_types": list(config.included_source_types or []),
        "auto_generate_ideas": bool(config.auto_generate_ideas),
        "idea_priority_threshold": float(config.idea_priority_threshold or 0.7),
        "scoring_weight_overrides": config.scoring_weight_overrides,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }


@mcp.tool()
def synthesis_configure(
    product_id: int,
    source_types: Optional[List[str]] = None,
    auto_generate_ideas: Optional[bool] = None,
    idea_priority_threshold: Optional[float] = None,
) -> dict:
    """Create or update the unified SynthesisConfig for a product.

    Args:
        product_id: The product to configure.
        source_types: Subset of ['competitive', 'customer', 'internal', 'evidence'].
        auto_generate_ideas: When True, opportunities above the threshold spawn ideas.
        idea_priority_threshold: Threshold (0.0-1.0) — opportunities scoring above
            threshold * 100 spawn ideas. Default 0.7.
    """
    from app.models.synthesis import SynthesisConfig

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.EDIT)
        if denied:
            return denied

        # Validate source_types
        if source_types is not None:
            if not isinstance(source_types, list) or not source_types:
                return {"error": "source_types must be a non-empty list"}
            unknown = [s for s in source_types if s not in VALID_SOURCE_TYPES]
            if unknown:
                return {
                    "error": (
                        f"Unknown source_types {unknown}. "
                        f"Allowed: {sorted(VALID_SOURCE_TYPES)}"
                    )
                }

        if idea_priority_threshold is not None:
            if not (0.0 <= float(idea_priority_threshold) <= 1.0):
                return {"error": "idea_priority_threshold must be between 0.0 and 1.0"}

        config = db.query(SynthesisConfig).filter(
            SynthesisConfig.product_id == product_id
        ).first()
        created = False
        if not config:
            config = SynthesisConfig(
                product_id=product_id,
                included_source_types=source_types or ["competitive"],
                auto_generate_ideas=(
                    auto_generate_ideas if auto_generate_ideas is not None else True
                ),
                idea_priority_threshold=(
                    float(idea_priority_threshold)
                    if idea_priority_threshold is not None else 0.7
                ),
            )
            db.add(config)
            created = True
        else:
            if source_types is not None:
                config.included_source_types = source_types
            if auto_generate_ideas is not None:
                config.auto_generate_ideas = bool(auto_generate_ideas)
            if idea_priority_threshold is not None:
                config.idea_priority_threshold = float(idea_priority_threshold)

        db.flush()
        return {
            "created": created,
            "config": _config_to_dict(config),
            "message": (
                "SynthesisConfig created" if created else "SynthesisConfig updated"
            ),
        }


@mcp.tool()
def synthesis_get_config(product_id: int) -> dict:
    """Retrieve the current SynthesisConfig (with defaults applied)."""
    from app.models.synthesis import SynthesisConfig

    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

        config = db.query(SynthesisConfig).filter(
            SynthesisConfig.product_id == product_id
        ).first()
        if not config:
            return {
                "exists": False,
                "config": {
                    "product_id": product_id,
                    "included_source_types": ["competitive"],
                    "auto_generate_ideas": True,
                    "idea_priority_threshold": 0.7,
                    "scoring_weight_overrides": None,
                },
                "message": "No config exists; defaults shown.",
            }
        return {"exists": True, "config": _config_to_dict(config)}


@mcp.tool()
def synthesis_get_competitors(product_id: int) -> dict:
    """List all competitors with their audit/synthesis inclusion flags.

    This is the PO-facing view used to review and edit which competitors
    feed the unified synthesis run.
    """
    from app.models.competitor_intelligence import ProductCompetitor

    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

        competitors = db.query(ProductCompetitor).filter(
            ProductCompetitor.product_id == product_id,
            ProductCompetitor.status == "active",
        ).all()

        return {
            "product_id": product_id,
            "competitors": [
                {
                    "competitor_id": c.id,
                    "competitor_name": c.competitor_name,
                    "competitor_url": c.competitor_url,
                    "audit_enabled": bool(c.audit_enabled),
                    "audit_status": c.audit_status,
                    "audit_last_run": (
                        c.audit_last_run.isoformat() if c.audit_last_run else None
                    ),
                    "synthesis_included": bool(c.synthesis_included),
                }
                for c in competitors
            ],
        }


@mcp.tool()
def synthesis_run_unified(product_id: int) -> dict:
    """Trigger a unified synthesis run.

    Auto-triggers missing functional audits for any competitor with
    synthesis_included=True; if any audits had to be triggered, the
    synthesis is deferred and the caller should re-run after audits
    complete (poll those audit jobs via job_get_status).
    """
    from app.models.queue import JobType
    from app.services.queue_service import QueueService
    from app.queue.tasks import unified_synthesis_task

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.EDIT)
        if denied:
            return denied

        conflict = require_no_active_job(
            db, product_id, JobType.UNIFIED_SYNTHESIS, "Unified synthesis"
        )
        if conflict:
            return conflict

        queue_service = QueueService(db)
        job = queue_service.create_job(
            job_type=JobType.UNIFIED_SYNTHESIS,
            input_data={"product_id": product_id},
            product_id=product_id,
            user_id=resolve_user_id_for_job(db, product_id),
        )

        from mcp_server.db import dispatch_task
        result = dispatch_task(unified_synthesis_task, job.id)
        queue_service.mark_queued(job.id, result.id)

        return {
            "job_id": job.id,
            "job_uuid": job.job_uuid,
            "status": "queued",
            "message": (
                "Unified synthesis queued. Use job_get_status to check progress. "
                "If competitor audits were missing, the job returns "
                "status='deferred' with the audit job IDs to poll first."
            ),
        }


def _latest_synthesis_report(db, product_id: int):
    """Return the latest SynthesisReport for a product, or None."""
    from app.models.synthesis import SynthesisReport
    from sqlalchemy import desc

    return db.query(SynthesisReport).filter(
        SynthesisReport.product_id == product_id
    ).order_by(desc(SynthesisReport.report_version)).first()


@mcp.tool()
def synthesis_get_unified_report(product_id: int) -> dict:
    """Get the latest unified SynthesisReport with all sections."""
    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

        report = _latest_synthesis_report(db, product_id)
        if not report:
            return {
                "error": "No unified synthesis report found. Run synthesis_run_unified first.",
            }

        return {
            "product_id": product_id,
            "synthesis_report_id": report.id,
            "report_version": report.report_version,
            "generated_at": report.generated_at.isoformat() if report.generated_at else None,
            "included_source_types": report.included_source_types,
            "source_stats": report.source_stats,
            "included_competitor_ids": report.included_competitor_ids,
            "source_competitor_report_ids": report.source_competitor_report_ids,
            "job_scorecard": report.job_scorecard,
            "feature_cluster_matrix": report.feature_cluster_matrix,
            "opportunities": report.opportunities,
            "high_impact_items": report.high_impact_items,
            "innovation_whitespace": report.innovation_whitespace,
            "analysis_summary": report.analysis_summary,
            "report_content_md": report.report_content_md,
            "changes_from_previous": report.changes_from_previous,
        }


@mcp.tool()
def synthesis_get_job_scorecard(product_id: int) -> dict:
    """Get the per-job scorecard from the latest unified synthesis report."""
    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

        report = _latest_synthesis_report(db, product_id)
        if not report:
            return {"error": "No unified synthesis report. Run synthesis_run_unified first."}

        return {
            "product_id": product_id,
            "synthesis_report_id": report.id,
            "report_version": report.report_version,
            "job_scorecard": report.job_scorecard or [],
        }


@mcp.tool()
def synthesis_get_investment_recommendations(product_id: int) -> dict:
    """Get per-job investment recommendations + rationale from the latest report."""
    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

        report = _latest_synthesis_report(db, product_id)
        if not report:
            return {"error": "No unified synthesis report. Run synthesis_run_unified first."}

        recs = []
        for entry in (report.job_scorecard or []):
            recs.append({
                "job_id": entry.get("job_id"),
                "job_statement": entry.get("job_statement"),
                "importance": entry.get("importance"),
                "investment_recommendation": entry.get("investment_recommendation"),
                "rationale": entry.get("rationale"),
                "our_score": entry.get("our_score"),
                "best_in_class": entry.get("best_in_class"),
                "evidence_ids": entry.get("evidence_ids") or [],
            })

        return {
            "product_id": product_id,
            "synthesis_report_id": report.id,
            "report_version": report.report_version,
            "investment_recommendations": recs,
        }


@mcp.tool()
def synthesis_get_by_job(product_id: int, job_id: str) -> dict:
    """Pivot the latest report by job_id: scorecard entry + features + opportunities.

    Args:
        product_id: The product.
        job_id: The job_id_key from the product's job map (e.g., 'j1').
    """
    from app.models.synthesis import SynthesizedOpportunity

    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

        report = _latest_synthesis_report(db, product_id)
        if not report:
            return {"error": "No unified synthesis report. Run synthesis_run_unified first."}

        scorecard_entry = None
        for entry in (report.job_scorecard or []):
            if entry.get("job_id") == job_id:
                scorecard_entry = entry
                break

        feature_cluster = None
        for cluster in (report.feature_cluster_matrix or []):
            if cluster.get("job_id") == job_id:
                feature_cluster = cluster
                break

        # Opportunities tagged to this job
        opps = db.query(SynthesizedOpportunity).filter(
            SynthesizedOpportunity.synthesis_report_id == report.id,
            SynthesizedOpportunity.job_id_key == job_id,
        ).order_by(SynthesizedOpportunity.priority_score.desc()).all()

        return {
            "product_id": product_id,
            "job_id": job_id,
            "synthesis_report_id": report.id,
            "report_version": report.report_version,
            "scorecard_entry": scorecard_entry,
            "feature_cluster": feature_cluster,
            "opportunities": [
                {
                    "opportunity_id": o.id,
                    "name": o.opportunity_name,
                    "summary": o.opportunity_summary,
                    "priority_score": o.priority_score,
                    "source_count": o.source_count,
                    "sources": o.sources,
                    "recommended_action": o.recommended_action,
                    "investment_tier": o.investment_tier,
                    "job_satisfaction_delta": o.job_satisfaction_delta,
                    "jtbd_statement": o.jtbd_statement,
                    "feature_keywords": o.feature_keywords,
                }
                for o in opps
            ],
        }
