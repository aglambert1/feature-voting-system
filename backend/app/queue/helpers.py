"""Shared utilities for Celery task modules.

These helpers are imported by multiple task modules under app.queue.*. They
deliberately do NOT import from any task module to keep the dependency
direction one-way (tasks → helpers).
"""

from typing import Dict, Any, Optional, List

from app.database import SessionLocal
from app.services.queue_service import QueueService


def get_db():
    """Get a database session for task execution."""
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


def _fetch_source_urls(
    source_urls: List[str],
    *,
    queue_service: Optional[QueueService] = None,
    job_id: Optional[int] = None,
    progress_start: float = 20.0,
    progress_span: float = 5.0,
) -> List[Dict[str, Any]]:
    """Fetch each URL and return a list of {url, title, text} dicts.

    Failures are logged and skipped (one bad URL does not fail the whole job).
    Extracted text is truncated to MAX_URL_EXTRACT_CHARS per URL.

    Optionally emits progress updates via `queue_service.update_progress(job_id, ...)`
    from `progress_start` to `progress_start + progress_span`.
    """
    from app.services.document_parsing_service import DocumentParsingService
    from app.services.scoped_input_validator import MAX_URL_EXTRACT_CHARS

    if not source_urls:
        return []

    parser = DocumentParsingService()
    fetched: List[Dict[str, Any]] = []
    total = len(source_urls)

    for i, url in enumerate(source_urls, 1):
        if queue_service is not None and job_id is not None:
            pct = progress_start + (i / total) * progress_span
            queue_service.update_progress(job_id, pct, f"fetching source {i}/{total}...")
        try:
            result = parser.fetch_url_content(url)
            extracted = (result.get('extracted_text') or '')
            if len(extracted) > MAX_URL_EXTRACT_CHARS:
                print(
                    f"[_fetch_source_urls] Truncating {url} extract from "
                    f"{len(extracted)} to {MAX_URL_EXTRACT_CHARS} chars"
                )
                extracted = extracted[:MAX_URL_EXTRACT_CHARS]
            fetched.append({
                'url': url,
                'title': result.get('title') or '',
                'text': extracted,
            })
        except Exception as e:
            # One failing URL should not kill the whole job.
            print(f"[_fetch_source_urls] Failed to fetch {url}: {e}")
            continue

    return fetched


def _cosine_similarity(a: list, b: list) -> float:
    """Compute cosine similarity between two embedding vectors.

    Voyage AI embeddings are L2-normalized, so the dot product equals
    the cosine similarity. We still normalize defensively to handle
    embeddings from other sources or partially-corrupted vectors.
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    try:
        import numpy as np
        va = np.array(a, dtype=float)
        vb = np.array(b, dtype=float)
        na = np.linalg.norm(va)
        nb = np.linalg.norm(vb)
        if na == 0.0 or nb == 0.0:
            return 0.0
        return float(np.dot(va, vb) / (na * nb))
    except Exception:
        return 0.0


def _link_idea_to_job(db, idea, similarity_threshold: float = 0.5) -> Optional[str]:
    """Link an idea to its best-matching ProductJob via JTBD embedding similarity.

    Mutates idea.job_id_key in place and returns the matched key (or None).
    Caller is responsible for committing.
    """
    if not idea.jtbd_embedding:
        return None

    from app.models.competitor_intelligence import ProductJob

    jobs = db.query(ProductJob).filter(
        ProductJob.product_id == idea.product_id,
        ProductJob.status == "active",
    ).all()
    if not jobs:
        return None

    best_job = None
    best_sim = 0.0
    for job in jobs:
        if not job.statement_embedding:
            continue
        sim = _cosine_similarity(idea.jtbd_embedding, job.statement_embedding)
        if sim > best_sim and sim > similarity_threshold:
            best_sim = sim
            best_job = job

    if best_job:
        idea.job_id_key = best_job.job_id_key
        return best_job.job_id_key
    return None


def _bump_parent_synthesis_progress(db, parent_job_id: int) -> None:
    """Update an in-flight unified synthesis job's progress to reflect how many
    of its triggered audit children have completed.

    Called from functional_audit_task at the end of each audit. Best-effort:
    swallow errors so an audit that succeeded at its primary job isn't marked
    failed by a progress-bump issue. Only acts when the parent job is the
    unified_synthesis_task in RUNNING state with status='audits_in_progress'
    in its output_data — leaves other parents alone.
    """
    try:
        from app.models.queue import QueueJob, JobStatus, JobType
        parent = db.query(QueueJob).filter(QueueJob.id == parent_job_id).first()
        if not parent or parent.status != JobStatus.RUNNING:
            return
        existing_output = parent.output_data or {}
        if existing_output.get("status") != "audits_in_progress":
            return

        siblings = db.query(QueueJob).filter(
            QueueJob.parent_job_id == parent_job_id,
            QueueJob.job_type == JobType.FUNCTIONAL_AUDIT,
        ).all()
        total = len(siblings)
        if total == 0:
            return
        done = sum(1 for s in siblings if s.status in (
            JobStatus.SUCCESS, JobStatus.FAILURE, JobStatus.CANCELLED
        ))

        # Map audits-in-progress to the 10–14% range — Step 4 (post-audit
        # resume) starts at 15% with "Loading product context...".
        pct = 10.0 + (4.0 * done / total)
        msg = f"Running competitor audit(s)... {done} of {total} complete"
        QueueService(db).update_progress(parent_job_id, pct, msg)
    except Exception as bump_err:
        print(
            f"[_bump_parent_synthesis_progress] Best-effort progress bump failed "
            f"for parent {parent_job_id}: {bump_err}"
        )


def _extract_competitor_names(competitive_evidence) -> list:
    """Extract the competitor list from a SynthesizedOpportunity.competitive_evidence blob.

    Returns [] when the blob is null or missing competitors (e.g., customer-only opp).
    Used by both the auto-gen path in unified_synthesis_task and the manual
    create-from-opportunity endpoint so triage gets the same competitor data
    in both flows.
    """
    if not isinstance(competitive_evidence, dict):
        return []
    return [c for c in (competitive_evidence.get("competitors") or []) if c]


def _sanitize_existing_feature_info(info):
    """Return a copy of existing_feature_info with source_url stripped to None
    unless it's a real http(s) URL.

    The triage agent's output passes through json.loads + a Pydantic schema, but
    the schema only enforces `Optional[str]` on source_url. The agent has been
    observed to echo placeholder strings like "N/A" from the prompt context,
    which then render in the UI as relative URLs (e.g., localhost:5173/N/A).
    Strip those defensively at persistence time so the frontend always either
    sees a usable URL or null.
    """
    if not isinstance(info, dict):
        return info
    sanitized = dict(info)
    url = sanitized.get('source_url')
    if isinstance(url, str):
        url_stripped = url.strip()
        if url_stripped.lower().startswith(('http://', 'https://')):
            sanitized['source_url'] = url_stripped
        else:
            sanitized['source_url'] = None
    elif url is not None:
        sanitized['source_url'] = None
    return sanitized
