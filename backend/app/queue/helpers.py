"""Shared utilities for Celery task modules.

These helpers are imported by multiple task modules under app.queue.*. They
deliberately do NOT import from any task module to keep the dependency
direction one-way (tasks → helpers).
"""

from typing import Dict, Any, Optional, List

from app.database import SessionLocal
from app.services.queue_service import QueueService
from app.utils.vectors import cosine_similarity as _cosine_similarity


def get_db():
    """Get a database session for task execution."""
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


def fail_job(
    db,
    job_id: int,
    error_msg: str,
    error_tb: Optional[str] = None,
    *,
    task_name: str = "",
) -> None:
    """Best-effort: mark a queue job as failed.

    Never raises — a status-update failure must not mask the original task
    exception the caller is about to re-raise.
    """
    if db is None:
        return
    try:
        QueueService(db).mark_failure(job_id, error_msg, error_tb)
    except Exception as inner:
        print(f"[{task_name or 'fail_job'}] Failed to update job status: {inner}")


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


# Similarity thresholds for job linkage.
# Domain-specific ideas cluster at 0.80–0.86 even when conceptually unrelated,
# so a simple 0.5 cutoff produces many false matches within the same domain.
_AUTO_LINK_THRESHOLD = 0.88    # link directly — high confidence
_LLM_VALIDATE_THRESHOLD = 0.75  # validate with LLM before linking


def _llm_validate_job_match(llm_service, idea_title: str, jtbd_statement: str, job_statement: str) -> bool:
    """Ask the LLM whether an idea addresses a specific customer need. Returns True if yes."""
    try:
        prompt = (
            f"Does this idea address the following customer need?\n\n"
            f"Idea: {idea_title}\n"
            f"Idea JTBD: {jtbd_statement}\n"
            f"Customer need: {job_statement}\n\n"
            f"Answer YES or NO only."
        )
        response = llm_service.call_agent(
            agent_name="job_match_validator",
            system_prompt="You are a product analyst. Answer with YES or NO only.",
            user_prompt=prompt,
            temperature=0.0,
            max_tokens=5,
            model="claude-haiku-4-5",
        )
        answer = (response.get("content") or "").strip().upper()
        return answer.startswith("YES")
    except Exception as e:
        print(f"[_llm_validate_job_match] Warning: LLM validation failed: {e}")
        return False


def _link_idea_to_job(db, idea, llm_service=None) -> Optional[str]:
    """Link an idea to its best-matching ProductJob via JTBD embedding similarity.

    Thresholds:
      ≥ 0.88  → auto-link (high confidence)
      0.75–0.88 → LLM validation (if llm_service provided, else skip)
      < 0.75  → no link

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
        if sim > best_sim:
            best_sim = sim
            best_job = job

    if not best_job:
        return None

    if best_sim >= _AUTO_LINK_THRESHOLD:
        idea.job_id_key = best_job.job_id_key
        return best_job.job_id_key

    if best_sim >= _LLM_VALIDATE_THRESHOLD and llm_service is not None:
        confirmed = _llm_validate_job_match(
            llm_service,
            idea_title=idea.title or "",
            jtbd_statement=idea.jtbd_statement or "",
            job_statement=best_job.statement,
        )
        if confirmed:
            idea.job_id_key = best_job.job_id_key
            return best_job.job_id_key

    return None


def suggest_needs_from_unmapped_capabilities(
    db,
    product_id: int,
    competitor_name: str,
    capabilities: Optional[List[dict]],
) -> int:
    """File a need suggestion for each competitor capability that fits no job.

    Routed into the SAME PMReviewQueue mechanism that signal-derived suggestions use,
    rather than a parallel one. The map already gains needs from ideas, evidence and
    themes; adding a second path would mean later sources each invent their own, and
    nothing could dedupe a need proposed by both a support theme and a competitor.

    No embedding comparison here, unlike `_maybe_suggest_need`: the audit has already
    judged that no job covers this capability, and re-deriving that from a similarity
    score would be a second opinion on a question already answered.

    Never raises — a failure here must not fail the audit that produced the finding.
    """
    if not capabilities:
        return 0

    try:
        from app.models.pm_review import (
            PMReviewQueue, ReviewQueueType, ReviewQueueStatus, ReviewQueuePriority,
        )

        filed = 0
        accepted_embeddings: List = []
        accepted_capabilities: List[str] = []
        _embed_cache: Dict[str, Any] = {}
        for cap in capabilities:
            if not isinstance(cap, dict):
                continue
            capability = (cap.get("capability") or "").strip()
            if not capability:
                continue

            suggested = (cap.get("suggested_job_statement") or "").strip()

            # Dedupe on MEANING, not on the exact string. Re-auditing surfaces the same
            # gaps again, and two competitors describe one gap differently — "OKR
            # alignment" and "Objective hierarchy and OKR alignment" are one need, and a
            # queue that files both stops being read. Uses the same embedding comparison
            # and threshold that decide whether a signal belongs to an existing job, so
            # "the same thing" means the same thing everywhere in the system.
            candidate_text = suggested or capability
            candidate_emb = None
            try:
                from app.services.embedding_service import generate_embedding
                candidate_emb = generate_embedding(candidate_text, input_type="document")
            except Exception:
                candidate_emb = None

            # Already covered by a job? Then the audit called it unmapped in error, and
            # filing a suggestion would ask the PM to add what they already have.
            if candidate_emb:
                from app.models.competitor_intelligence import ProductJob

                jobs = db.query(ProductJob).filter(
                    ProductJob.product_id == product_id,
                    ProductJob.status == "active",
                ).all()
                if any(
                    j.statement_embedding
                    and _cosine_similarity(candidate_emb, j.statement_embedding)
                    >= _AUTO_LINK_THRESHOLD
                    for j in jobs
                ):
                    continue

            existing = db.query(PMReviewQueue).filter(
                PMReviewQueue.queue_type == ReviewQueueType.NEED_SUGGESTION,
                PMReviewQueue.product_id == product_id,
                PMReviewQueue.status.in_(
                    [ReviewQueueStatus.PENDING, ReviewQueueStatus.IN_REVIEW]
                ),
            ).all()

            # Re-embed the pending items rather than storing their vectors. A 1024-float
            # array in item_metadata is served verbatim by the PM review queue endpoint,
            # so persisting it would ship ~20KB of JSON per suggestion to every client
            # listing the queue. Embedding a handful of short strings is cheap by
            # comparison, and keeps the API payload readable.
            def _duplicate(item) -> bool:
                meta = item.item_metadata or {}
                if meta.get("capability") == capability:
                    return True
                if not candidate_emb:
                    return False
                prior_text = meta.get("signal_content") or meta.get("capability")
                if not prior_text:
                    return False
                prior_emb = _embed_cache.get(prior_text)
                if prior_emb is None:
                    try:
                        from app.services.embedding_service import generate_embedding
                        prior_emb = generate_embedding(prior_text, input_type="document")
                    except Exception:
                        return False
                    _embed_cache[prior_text] = prior_emb
                return _cosine_similarity(candidate_emb, prior_emb) >= _AUTO_LINK_THRESHOLD

            if any(_duplicate(e) for e in existing):
                continue

            # The session is autoflush=False and nothing commits until the loop ends, so
            # the query above cannot see items added earlier in THIS batch. Without this,
            # one audit returning both "OKR alignment" and "Objective hierarchy and OKR
            # alignment" files them both — the exact case this dedupe exists to prevent.
            if candidate_emb and any(
                _cosine_similarity(candidate_emb, seen_emb) >= _AUTO_LINK_THRESHOLD
                for seen_emb in accepted_embeddings
            ):
                continue
            if any(text == capability for text in accepted_capabilities):
                continue

            db.add(PMReviewQueue(
                queue_type=ReviewQueueType.NEED_SUGGESTION,
                status=ReviewQueueStatus.PENDING,
                priority=ReviewQueuePriority.NORMAL,
                product_id=product_id,
                item_type="need_suggestion",
                item_id=0,
                title=f"Need candidate from {competitor_name}: {capability[:70]}",
                summary=(
                    cap.get("why_unmapped")
                    or f"{competitor_name} does this and no need in your map covers it."
                ),
                item_metadata={
                    "signal_type": "competitor_capability",
                    "signal_id": None,
                    "signal_content": suggested or capability,
                    "match_type": "no_match",
                    "matched_job_id": None,
                    "matched_job_statement": None,
                    "matched_similarity": None,
                    "product_id": product_id,
                    "capability": capability,
                    "competitor_name": competitor_name,
                },
            ))
            if candidate_emb:
                accepted_embeddings.append(candidate_emb)
            accepted_capabilities.append(capability)
            filed += 1

        if filed:
            db.commit()
        return filed

    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        print(f"[suggest_needs_from_unmapped_capabilities] failed: {exc}")
        return 0


def _maybe_suggest_need(
    db,
    product_id: int,
    signal_type: str,
    signal_id: int,
    signal_content: str,
    jtbd_embedding: Optional[List],
) -> None:
    """Create a NEED_SUGGESTION review queue item when a signal doesn't match any job.

    Called after job-linkage attempts across all signal ingestion paths.
    Never raises — failures are logged and swallowed so the parent task isn't affected.

    Thresholds:
      < 0.5  → no_match  → NEED_SUGGESTION (priority NORMAL)
      0.5–0.75 → weak_match → NEED_SUGGESTION (priority HIGH)
      ≥ 0.75 → confident match — no action
    """
    NO_MATCH_THRESHOLD = _LLM_VALIDATE_THRESHOLD   # 0.75
    WEAK_MATCH_THRESHOLD = _AUTO_LINK_THRESHOLD      # 0.88

    try:
        if not jtbd_embedding:
            return

        from app.models.competitor_intelligence import ProductJob
        from app.models.pm_review import PMReviewQueue, ReviewQueueType, ReviewQueueStatus, ReviewQueuePriority

        jobs = db.query(ProductJob).filter(
            ProductJob.product_id == product_id,
            ProductJob.status == "active",
        ).all()

        best_job = None
        best_sim = 0.0
        for job in jobs:
            if not job.statement_embedding:
                continue
            sim = _cosine_similarity(jtbd_embedding, job.statement_embedding)
            if sim > best_sim:
                best_sim = sim
                best_job = job

        if best_sim >= WEAK_MATCH_THRESHOLD:
            return  # Confident match — already linked, no suggestion needed

        match_type = "no_match" if best_sim < NO_MATCH_THRESHOLD else "weak_match"
        priority = ReviewQueuePriority.HIGH if match_type == "weak_match" else ReviewQueuePriority.NORMAL

        # Dedup: skip if a pending/in-review suggestion already exists for this signal
        existing = db.query(PMReviewQueue).filter(
            PMReviewQueue.queue_type == ReviewQueueType.NEED_SUGGESTION,
            PMReviewQueue.status.in_([ReviewQueueStatus.PENDING, ReviewQueueStatus.IN_REVIEW]),
            PMReviewQueue.item_type == "need_suggestion",
            PMReviewQueue.item_id == signal_id,
        ).first()
        # item_type+item_id doesn't distinguish signal_type, so also check metadata
        if existing:
            meta = existing.item_metadata or {}
            if meta.get("signal_type") == signal_type and meta.get("signal_id") == signal_id:
                return

        metadata = {
            "signal_type": signal_type,
            "signal_id": signal_id,
            "signal_content": signal_content[:500],
            "match_type": match_type,
            "matched_job_id": best_job.job_id_key if best_job else None,
            "matched_job_statement": best_job.statement if best_job else None,
            "matched_similarity": round(best_sim, 3) if best_job else None,
            "product_id": product_id,
        }

        title = f"Need candidate: {signal_content[:80]}{'…' if len(signal_content) > 80 else ''}"
        summary = (
            f"Weak match to {best_job.job_id_key} (similarity {best_sim:.2f}). Confirm or add as new need."
            if match_type == "weak_match"
            else "No existing need matched this signal. Consider adding a new need."
        )

        item = PMReviewQueue(
            queue_type=ReviewQueueType.NEED_SUGGESTION,
            status=ReviewQueueStatus.PENDING,
            priority=priority,
            product_id=product_id,
            item_type="need_suggestion",
            item_id=signal_id,
            title=title,
            summary=summary,
            item_metadata=metadata,
        )
        db.add(item)
        db.commit()

    except Exception as exc:
        # Roll back so a failed INSERT (e.g. an aborted transaction) doesn't
        # leave the shared session poisoned — without this, the caller's next
        # commit fails with InFailedSqlTransaction and its essential work is
        # lost. This is best-effort signal enrichment; never let it corrupt the
        # caller's session. (Regression: an enum error here once aborted a
        # triage commit, discarding the idea's verdict + job link.)
        print(f"[_maybe_suggest_need] Warning: failed to create suggestion: {exc}")
        try:
            db.rollback()
        except Exception as rollback_exc:
            print(f"[_maybe_suggest_need] Warning: rollback failed: {rollback_exc}")


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


def _authoritative_job_key(source_metadata) -> Optional[str]:
    """Return a job_id_key that was set deterministically by a synthesis writer.

    Ideas created from a SynthesizedOpportunity carry the opportunity's
    job_id_key in source_metadata (auto-gen loop + manual create-from-opp).
    Synthesis already linked the opportunity to a job map need, so that key is
    authoritative — triage must preserve it rather than re-deriving via
    embedding similarity, which often fails to cosine-match an opportunity's
    prose to its own job statement and would drop the link.

    Returns None when there is no source key, so the caller falls back to
    similarity-based linkage.
    """
    if not isinstance(source_metadata, dict):
        return None
    return source_metadata.get('job_id_key') or None


def _authoritative_competitor_names(source_metadata) -> Optional[list]:
    """Return the deterministic competitor list set by a synthesis writer.

    Ideas created from a SynthesizedOpportunity carry the opportunity's
    competitor list in source_metadata as ``competitor_names`` (PR #45), falling
    back to a single legacy ``competitor_name``. This list is authoritative —
    the triage agent's own list is unreliable for opportunity-sourced ideas
    (synthesis prompts use anonymized labels like "Competitor 1" which the agent
    echoes alongside real names, producing phantom duplicates).

    The authoritative signal is the *presence* of the key, not a non-empty value:
    a customer-only opportunity legitimately has ``competitor_names: []`` and
    must show no competitors, NOT fall back to the agent's (possibly
    hallucinated) list. Returns None only when source_metadata carries no
    competitor key at all, signalling the caller to use the agent's list. Keyed
    on the presence of authoritative data rather than the source_type flag,
    mirroring _authoritative_job_key.
    """
    if not isinstance(source_metadata, dict):
        return None
    if 'competitor_names' in source_metadata:
        return list(source_metadata.get('competitor_names') or [])
    single = source_metadata.get('competitor_name')
    if single:
        return [single]
    return None


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


def _relink_all_signals(db, product_id: int, active_job_keys_after_apply: set) -> None:
    """Re-link orphaned signals to the best-matching active job after a map change.

    Only processes signals whose job_id_key is NOT in active_job_keys_after_apply
    (i.e., the job was removed or replaced). Signals on kept jobs are untouched.
    """
    from app.models.competitor_intelligence import ProductJob
    from app.models.idea import Idea
    from app.models.evidence import Evidence
    from app.models.synthesis import SynthesizedOpportunity

    jobs = db.query(ProductJob).filter(
        ProductJob.product_id == product_id,
        ProductJob.status == "active",
    ).all()
    active_jobs = [j for j in jobs if j.statement_embedding]

    if not active_jobs:
        return

    def _relink_table(model, embedding_attr):
        rows = db.query(model).filter(
            model.product_id == product_id,
        ).all()
        changed = 0
        for row in rows:
            current_key = row.job_id_key
            # Skip signals already on a still-active job
            if current_key and current_key in active_job_keys_after_apply:
                continue
            emb = getattr(row, embedding_attr, None)
            if not emb:
                row.job_id_key = None
                changed += 1
                continue
            best_job = None
            best_sim = 0.0
            for job in active_jobs:
                sim = _cosine_similarity(emb, job.statement_embedding)
                if sim > best_sim:
                    best_sim = sim
                    best_job = job
            if best_job and best_sim >= _LLM_VALIDATE_THRESHOLD:
                row.job_id_key = best_job.job_id_key
            else:
                row.job_id_key = None
            changed += 1
        if changed:
            db.flush()

    _relink_table(Idea, 'jtbd_embedding')
    _relink_table(Evidence, 'jtbd_embedding')
    _relink_table(SynthesizedOpportunity, 'jtbd_embedding')
    # WinLossTheme and SupportTheme have no jtbd_embedding column — they re-link
    # naturally via the suggestion pipeline when new evidence is processed.
    db.commit()
