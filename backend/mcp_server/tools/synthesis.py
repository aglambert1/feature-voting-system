"""Synthesis tools for MCP server."""

from typing import List, Optional

from mcp_server import mcp
from mcp_server.db import get_session
from mcp_server.permissions import require_product_access, require_no_active_job, resolve_user_id_for_job

from app.models.competitor_intelligence import ProductPermissionLevel
from app.models.synthesis import (
    DEFAULT_AUTO_GENERATE_IDEAS,
    DEFAULT_IDEA_PRIORITY_THRESHOLD,
    DEFAULT_INCLUDED_SOURCE_TYPES,
)


VALID_SOURCE_TYPES = {"competitive", "customer", "internal", "evidence"}


@mcp.tool()
def synthesis_get_sources(product_id: int) -> dict:
    """Check fact-base health and freshness — what data sources are available for synthesis, when each was last updated, and which are stale.

    Per-source `is_stale` flags surface staleness for PM judgment (competitive
    reports >30 days, internal imports >90 days). `synthesis_stale` is true
    when the newest synthesis report predates newer evidence/ideas/reports —
    i.e. the synthesis no longer reflects the current fact-base.
    """
    from datetime import datetime, timedelta, timezone

    from app.models.evidence import Evidence
    from app.models.idea import Idea
    from app.models.internal_feedback import InternalFeedbackImport
    from app.models.competitor_intelligence import CIProduct, ProductCompetitor
    from app.models.competitive_reports import CompetitorFunctionalReport
    from app.models.synthesis import SynthesisReport
    from sqlalchemy import func

    COMPETITIVE_STALE_DAYS = 30
    INTERNAL_STALE_DAYS = 90

    def _age_days(dt) -> float | None:
        if not dt:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 86400

    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

        # Competitive: count competitors with completed functional audits
        competitor_report_count = (
            db.query(func.count(CompetitorFunctionalReport.id))
            .join(ProductCompetitor, CompetitorFunctionalReport.product_competitor_id == ProductCompetitor.id)
            .filter(ProductCompetitor.product_id == product_id)
            .scalar()
            or 0
        )
        latest_competitor_report = (
            db.query(CompetitorFunctionalReport)
            .join(ProductCompetitor, CompetitorFunctionalReport.product_competitor_id == ProductCompetitor.id)
            .filter(ProductCompetitor.product_id == product_id)
            .order_by(CompetitorFunctionalReport.generated_at.desc())
            .first()
        )

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

        latest_idea = (
            db.query(Idea)
            .filter(Idea.product_id == product_id)
            .order_by(Idea.created_at.desc())
            .first()
        )

        latest_synthesis = (
            db.query(SynthesisReport)
            .filter(SynthesisReport.product_id == product_id)
            .order_by(SynthesisReport.generated_at.desc())
            .first()
        )

        product = db.query(CIProduct).get(product_id)

        report_age = _age_days(latest_competitor_report.generated_at) if latest_competitor_report else None
        import_age = _age_days(latest_import.processed_at) if latest_import and latest_import.processed_at else None
        synthesis_age = _age_days(latest_synthesis.generated_at) if latest_synthesis else None

        # Synthesis is stale when any signal source is newer than the report.
        newest_signal = max(
            (dt for dt in (
                latest_competitor_report.generated_at if latest_competitor_report else None,
                latest_evidence.created_at if latest_evidence else None,
                latest_idea.created_at if latest_idea else None,
                latest_import.processed_at if latest_import else None,
            ) if dt is not None),
            default=None,
        )
        synthesis_stale = bool(
            latest_synthesis
            and newest_signal is not None
            and newest_signal > latest_synthesis.generated_at
        )

        return {
            "product_id": product_id,
            "sources": {
                "competitive_landscape": {
                    "available": competitor_report_count > 0,
                    "last_updated": latest_competitor_report.generated_at.isoformat() if latest_competitor_report else None,
                    "competitors_analyzed": competitor_report_count,
                    "is_stale": bool(report_age is not None and report_age > COMPETITIVE_STALE_DAYS),
                },
                "customer_ideas": {
                    "available": idea_count > 0,
                    "total_ideas": idea_count,
                    "last_added": latest_idea.created_at.isoformat() if latest_idea and latest_idea.created_at else None,
                },
                "internal_feedback": {
                    "available": latest_import is not None,
                    "last_imported": latest_import.processed_at.isoformat() if latest_import and latest_import.processed_at else None,
                    "deals_count": latest_import.deals_count if latest_import else 0,
                    "tickets_count": latest_import.tickets_count if latest_import else 0,
                    "is_stale": bool(import_age is not None and import_age > INTERNAL_STALE_DAYS),
                },
                "factbase_evidence": {
                    "available": evidence_count > 0,
                    "total_evidence": evidence_count,
                    "last_added": latest_evidence.created_at.isoformat() if latest_evidence and latest_evidence.created_at else None,
                },
            },
            "job_map": {
                "version": product.job_map_version if product else None,
                "last_updated": (
                    product.job_map_last_updated.isoformat()
                    if product and product.job_map_last_updated else None
                ),
            },
            "synthesis": {
                "has_report": latest_synthesis is not None,
                "last_generated": latest_synthesis.generated_at.isoformat() if latest_synthesis else None,
                "age_days": round(synthesis_age, 1) if synthesis_age is not None else None,
                "synthesis_stale": synthesis_stale,
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
        "idea_priority_threshold": float(
            config.idea_priority_threshold or DEFAULT_IDEA_PRIORITY_THRESHOLD
        ),
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
            threshold * 100 spawn ideas. See DEFAULT_IDEA_PRIORITY_THRESHOLD in
            app.models.synthesis for the canonical default.
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
                included_source_types=source_types or list(DEFAULT_INCLUDED_SOURCE_TYPES),
                auto_generate_ideas=(
                    auto_generate_ideas if auto_generate_ideas is not None
                    else DEFAULT_AUTO_GENERATE_IDEAS
                ),
                idea_priority_threshold=(
                    float(idea_priority_threshold)
                    if idea_priority_threshold is not None
                    else DEFAULT_IDEA_PRIORITY_THRESHOLD
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
                    "included_source_types": list(DEFAULT_INCLUDED_SOURCE_TYPES),
                    "auto_generate_ideas": DEFAULT_AUTO_GENERATE_IDEAS,
                    "idea_priority_threshold": DEFAULT_IDEA_PRIORITY_THRESHOLD,
                    "scoring_weight_overrides": None,
                },
                "message": "No config exists; defaults shown.",
            }
        return {"exists": True, "config": _config_to_dict(config)}


@mcp.tool()
def synthesis_run_unified(product_id: int) -> dict:
    """Trigger a unified synthesis run.

    Auto-triggers missing functional audits for any tracked competitor without a
    report; if any audits had to be triggered, the synthesis is deferred and the
    caller should re-run after audits complete (poll those audit jobs via
    job_get_status).
    """
    from app.models.queue import JobType
    from app.services.queue_service import QueueService
    from app.queue.synthesis_tasks import unified_synthesis_task

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
