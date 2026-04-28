"""Counters and aggregations over CompetitorFunctionalReport content.

Post-JTBD redesign (PR #33), gap data lives in different fields depending on
whether a job map exists for the product:
- `functional_comparison[].mapping_status == 'Gap'` — populated in Stage 1
  always (with or without job map).
- `job_assessments[].features[].position == 'gap'` — populated in Stage 2
  only when a job map exists.
- `gaps_deep_dive[]` — populated only when no job map exists (legacy path).

This helper picks the most reliable source available so callers don't need
to know about the JTBD branching.
"""

from typing import Any


def count_gaps(report_or_dict: Any) -> int:
    """Count gaps in a competitor functional report.

    Accepts either a CompetitorFunctionalReport ORM instance or a dict with
    the same field names (so the same logic works in the audit task before
    the report is reloaded from DB).

    Resolution order:
    1. functional_comparison entries with mapping_status == 'Gap' (preferred —
       populated in Stage 1 regardless of job map presence)
    2. job_assessments[].features[] entries with position == 'gap' (fallback —
       used if functional_comparison is empty for any reason)
    3. len(gaps_deep_dive) (legacy fallback for no-job-map reports)
    """
    if report_or_dict is None:
        return 0

    def _get(field: str):
        if isinstance(report_or_dict, dict):
            return report_or_dict.get(field)
        return getattr(report_or_dict, field, None)

    functional_comparison = _get('functional_comparison')
    if functional_comparison:
        gaps = sum(
            1 for entry in functional_comparison
            if isinstance(entry, dict) and entry.get('mapping_status') == 'Gap'
        )
        if gaps or len(functional_comparison) > 0:
            # Stage 1 ran successfully (even if 0 gaps); trust this count.
            return gaps

    job_assessments = _get('job_assessments')
    if job_assessments:
        gaps = 0
        for assessment in job_assessments:
            if not isinstance(assessment, dict):
                continue
            for feature in (assessment.get('features') or []):
                if isinstance(feature, dict) and feature.get('position') == 'gap':
                    gaps += 1
        if gaps:
            return gaps

    gaps_deep_dive = _get('gaps_deep_dive')
    if gaps_deep_dive:
        return len(gaps_deep_dive)

    return 0
