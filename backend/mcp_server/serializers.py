"""Shared model-to-dict serializers for MCP tools.

Pure functions over ORM objects so multiple tools return consistent shapes —
an agent correlating results across tools should never have to reconcile two
different spellings of the same record.
"""

from typing import Optional


def job_summary(job, include_output: bool = False) -> dict:
    """Serialize a QueueJob for tool output.

    With include_output, adds output_data once the job is complete.
    """
    result = {
        "job_id": job.id,
        "job_uuid": job.job_uuid,
        "job_type": job.job_type.value if job.job_type else None,
        "status": job.status.value if job.status else None,
        "progress_percent": job.progress_percent,
        "progress_message": job.progress_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "duration_seconds": job.duration_seconds,
        "error_message": job.error_message,
    }
    if include_output and job.is_complete:
        result["output_data"] = job.output_data
    return result


def latest_functional_report(db, product_competitor_id: int):
    """Return the latest CompetitorFunctionalReport for a competitor, or None.

    Always order by report_version — an unordered .first() can return a stale
    version.
    """
    from app.models.competitive_reports import CompetitorFunctionalReport

    return (
        db.query(CompetitorFunctionalReport)
        .filter(CompetitorFunctionalReport.product_competitor_id == product_competitor_id)
        .order_by(CompetitorFunctionalReport.report_version.desc())
        .first()
    )


def competitor_summary(competitor, report) -> dict:
    """Serialize a ProductCompetitor + its latest report for list output.

    `has_report` is the authoritative signal that an audit has been performed —
    `audit_status` may be stale for reports generated before the status field
    was populated.
    """
    return {
        "competitor_id": competitor.id,
        "competitor_name": competitor.competitor_name,
        "competitor_url": competitor.competitor_url,
        "tracked": bool(competitor.tracked),
        "audit_status": competitor.audit_status,
        "audit_last_run": (
            competitor.audit_last_run.isoformat() if competitor.audit_last_run else None
        ),
        "has_report": report is not None,
        "report_version": report.report_version if report else None,
        "report_generated_at": report.generated_at.isoformat() if report else None,
    }


def idea_summary(idea, vote_count: Optional[int] = None) -> dict:
    """Serialize an Idea for list output (superset shape used by all list tools).

    vote_count is board votes only (a Vote-row count passed in by the caller).
    external_vote_count is a separate, non-comparable population imported from
    the idea's source system — never summed with vote_count.
    """
    from app.models.idea import SourceType

    is_imported = idea.source_type == SourceType.EXTERNAL_SUBMISSION
    metadata = idea.source_metadata or {}
    return {
        "idea_id": idea.id,
        "title": idea.title,
        "category": idea.category,
        "status": idea.status.value if idea.status else None,
        "source_type": idea.source_type.value if idea.source_type else None,
        "vote_count": vote_count,
        "external_source": idea.external_source if is_imported else None,
        "external_vote_count": metadata.get("external_vote_count") if is_imported else None,
        "is_active": idea.is_active,
        "jtbd_statement": idea.jtbd_statement,
        "triage_recommendation": idea.triage_recommendation,
        "triage_confidence": idea.triage_confidence,
        "created_at": idea.created_at.isoformat() if idea.created_at else None,
    }
