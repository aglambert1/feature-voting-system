"""Builder for the opportunity-sourced idea source_metadata contract.

Ideas created from a SynthesizedOpportunity carry a metadata blob that triage
treats as AUTHORITATIVE: `job_id_key` and `competitor_names` override the
triage agent's own output (see `_authoritative_job_key` /
`_authoritative_competitor_names` in app/queue/helpers.py), and the synthesis
linked-idea backfill script keys on `synthesis_report_id`. Every writer must
therefore emit the same shape — this builder is the single source of it.
"""

from typing import Any, Optional

from app.queue.helpers import _extract_competitor_names


def build_opportunity_source_metadata(
    *,
    synthesis_report_id: Optional[int],
    feature_name: str,
    priority_score: Any,
    sources: Optional[list],
    job_id_key: Optional[str],
    investment_tier: Optional[str],
    competitive_evidence: Any,
    report_version: Optional[int] = None,
    opportunity_id: Optional[int] = None,
    manual_creation: bool = False,
) -> dict:
    """Build source_metadata for an idea created from a synthesized opportunity.

    Optional keys (`synthesis_report_version`, `opportunity_id`,
    `manual_creation`) are included only when provided, preserving the exact
    per-writer shapes that existed before this builder.
    """
    competitors_with = _extract_competitor_names(competitive_evidence)

    metadata: dict = {
        "synthesis_report_id": synthesis_report_id,
    }
    if report_version is not None:
        metadata["synthesis_report_version"] = report_version
    if opportunity_id is not None:
        metadata["opportunity_id"] = opportunity_id
    metadata.update({
        "feature_name": feature_name,
        "priority_score": priority_score,
        "sources": sources or [],
        "job_id_key": job_id_key,
        "investment_tier": investment_tier,
    })
    if manual_creation:
        metadata["manual_creation"] = True
    metadata.update({
        "competitors_with_feature": competitors_with,
        "competitor_names": competitors_with,
    })
    return metadata
