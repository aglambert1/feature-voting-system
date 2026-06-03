"""Celery tasks for unified (Phase 3) synthesis.

Houses the unified synthesis pipeline:

* ``unified_synthesis_task`` — entry point. Loads SynthesisConfig, dispatches
  any missing competitor audits as a chord, and either returns
  ``audits_in_progress`` or runs Steps 4-10 directly when no audits are needed.
* ``resume_unified_synthesis_task`` — chord callback that resumes synthesis
  after triggered audits complete.
* ``_run_unified_synthesis_post_audits`` — Steps 4-10 of the pipeline
  (load all sources, run UnifiedSynthesisAgent, persist SynthesisReport,
  optionally auto-generate Ideas).
* ``_build_unified_synthesis_markdown`` — helper that renders the agent
  output to a markdown report stored on SynthesisReport.report_content_md.
"""

import traceback
from typing import Dict, Any, List
from celery import shared_task
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models.queue import JobType
from app.models.competitor_intelligence import (
    CIProduct, ProductFeature, ProductCompetitor,
)
from app.services.queue_service import QueueService

from app.queue.helpers import _extract_competitor_names
from app.queue.competitor_tasks import functional_audit_task
from app.queue.triage_tasks import triage_idea_task


# ---------------------------------------------------------------------------
# Unified Synthesis (Phase 3)
# ---------------------------------------------------------------------------

def _build_unified_synthesis_markdown(
    product_name: str,
    output: dict,
    source_stats: dict,
) -> str:
    """Build a markdown report for a unified synthesis output.

    Sections: summary -> source stats -> job scorecard -> feature clusters ->
    opportunities -> high-impact items -> innovation whitespace.
    """
    parts: list = []
    parts.append(f"# Unified Synthesis Report — {product_name}\n")

    if output.get("analysis_summary"):
        parts.append("## Summary\n")
        parts.append(output["analysis_summary"].strip() + "\n")

    parts.append("## Source Stats\n")
    for key, val in (source_stats or {}).items():
        parts.append(f"- **{key}**: {val}")
    parts.append("")

    job_scorecard = output.get("job_scorecard") or []
    if job_scorecard:
        parts.append("## Job Scorecard\n")
        for entry in job_scorecard:
            parts.append(f"### {entry.get('job_id')} — {entry.get('job_statement', '')}")
            parts.append(
                f"- Importance: {entry.get('importance', 'medium')}; "
                f"our_score: {entry.get('our_score', 0)}/10; "
                f"rank: {entry.get('our_rank')}/{entry.get('total_ranked')}"
            )
            comp_scores = entry.get("competitor_scores") or {}
            if comp_scores:
                comp_str = ", ".join(f"{n}={s}" for n, s in comp_scores.items())
                parts.append(f"- Competitors: {comp_str}")
            if entry.get("best_in_class"):
                parts.append(f"- Best-in-class: {entry['best_in_class']}")
            parts.append(
                f"- Investment: **{entry.get('investment_recommendation', 'maintain')}** — "
                f"{entry.get('rationale', '')}"
            )
            parts.append("")

    cluster_matrix = output.get("feature_cluster_matrix") or []
    if cluster_matrix:
        parts.append("## Feature Clusters\n")
        for cluster in cluster_matrix:
            parts.append(f"### {cluster.get('job_id')} — {cluster.get('job_statement', '')}")
            for feat in cluster.get("features", []) or []:
                comps = ", ".join(feat.get("competitors_with_feature") or []) or "-"
                parts.append(
                    f"- **{feat.get('feature_name')}** "
                    f"({feat.get('prevalence', '?')}; us: {feat.get('our_status', '?')}; "
                    f"competitors: {comps})"
                )
            parts.append("")

    opportunities = output.get("opportunities") or []
    if opportunities:
        parts.append("## Opportunities\n")
        for opp in opportunities:
            parts.append(
                f"### [{opp.get('priority_score', 0):.1f}] {opp.get('opportunity_name', 'Opportunity')}"
            )
            sources = ", ".join(opp.get("sources") or [])
            parts.append(
                f"- Sources ({opp.get('source_count', 1)}): {sources}; "
                f"action: {opp.get('recommended_action', 'review')}"
            )
            if opp.get("job_id_key"):
                parts.append(
                    f"- Job: {opp['job_id_key']} (Δ satisfaction: "
                    f"{opp.get('job_satisfaction_delta', 0)}); "
                    f"investment: {opp.get('investment_tier', 'maintain')}"
                )
            if opp.get("opportunity_summary"):
                parts.append(f"- {opp['opportunity_summary']}")
            if opp.get("jtbd_statement"):
                parts.append(f"- JTBD: {opp['jtbd_statement']}")
            parts.append("")

    high_impact = output.get("high_impact_items") or []
    if high_impact:
        parts.append("## High-Impact Items\n")
        for item in sorted(high_impact, key=lambda x: x.get("rank", 99)):
            tag = item.get("type", "item").upper()
            parts.append(
                f"### [{tag}] #{item.get('rank', '?')} {item.get('title', '')}"
            )
            if item.get("description"):
                parts.append(f"- {item['description']}")
            if item.get("market_gravity"):
                parts.append(f"- Market gravity: {item['market_gravity']}")
            if item.get("competitors"):
                parts.append(f"- Competitors: {', '.join(item['competitors'])}")
            parts.append("")

    if output.get("innovation_whitespace"):
        parts.append("## Innovation Whitespace\n")
        parts.append(output["innovation_whitespace"].strip() + "\n")

    return "\n".join(parts)


@shared_task(
    bind=True,
    name='app.queue.synthesis_tasks.unified_synthesis_task',
    max_retries=2,
    default_retry_delay=60,
    soft_time_limit=1200,
)
def unified_synthesis_task(self, job_id: int):
    """Phase 3 unified synthesis: replaces landscape + opportunity synthesis.

    Pulls signals from configured source types, runs UnifiedSynthesisAgent,
    persists a SynthesisReport + SynthesizedOpportunity rows, and optionally
    auto-generates Ideas above the configured priority threshold.

    If any included competitor lacks a functional report, this task dispatches
    those audits in parallel via a Celery chord and registers
    resume_unified_synthesis_task as the callback. The synthesis job stays in
    RUNNING state until the resume task finishes Steps 4-10. Callers
    (UI, MCP) need only poll the synthesis job UUID — they never see a
    "deferred" intermediate state.
    """
    from app.models.synthesis import SynthesisConfig
    from app.models.competitive_reports import CompetitorFunctionalReport

    db = None
    try:
        db = SessionLocal()
        queue_service = QueueService(db)

        job = queue_service.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        queue_service.mark_running(job_id)
        queue_service.update_progress(job_id, 5.0, "Loading synthesis configuration...")

        product_id = job.product_id
        if not product_id:
            raise ValueError("product_id is required for unified synthesis")

        product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
        if not product:
            raise ValueError(f"Product {product_id} not found")

        # Step 1: Load (or create default) SynthesisConfig
        # Defaults come from DEFAULT_* constants in app.models.synthesis.
        from app.models.synthesis import DEFAULT_INCLUDED_SOURCE_TYPES
        config = db.query(SynthesisConfig).filter(
            SynthesisConfig.product_id == product_id
        ).first()
        if not config:
            config = SynthesisConfig(
                product_id=product_id,
                included_source_types=list(DEFAULT_INCLUDED_SOURCE_TYPES),
                # auto_generate_ideas + idea_priority_threshold inherit model defaults
            )
            db.add(config)
            db.flush()
            db.commit()

        included_sources = list(
            config.included_source_types or list(DEFAULT_INCLUDED_SOURCE_TYPES)
        )
        included_set = {s.lower() for s in included_sources}

        # Step 2: Load tracked competitors (tracked == True)
        included_competitors = db.query(ProductCompetitor).filter(
            ProductCompetitor.product_id == product_id,
            ProductCompetitor.status == "active",
            ProductCompetitor.tracked == True,  # noqa: E712
        ).all()

        # Step 3: Auto-trigger missing audits for synthesis_included competitors.
        # If any are dispatched, fire them as a Celery chord with
        # resume_unified_synthesis_task as the callback — synthesis Steps 4-10
        # run automatically once all audits complete (or fail).
        competitors_with_reports = {
            r[0] for r in db.query(CompetitorFunctionalReport.product_competitor_id)
            .filter(CompetitorFunctionalReport.product_id == product_id).all()
        }
        audit_signatures = []
        triggered_audit_job_ids = []
        if "competitive" in included_set:
            for comp in included_competitors:
                has_report = comp.id in competitors_with_reports
                if not has_report and comp.audit_status != "completed":
                    audit_job = queue_service.create_job(
                        job_type=JobType.FUNCTIONAL_AUDIT,
                        input_data={"competitor_id": comp.id},
                        product_id=product_id,
                        user_id=job.user_id,
                        parent_job_id=job_id,
                    )
                    db.commit()
                    audit_signatures.append(functional_audit_task.s(audit_job.id))
                    triggered_audit_job_ids.append(audit_job.id)

        if audit_signatures:
            # Dispatch chord: all audits run in parallel; the callback resumes
            # synthesis once they all complete. Synthesis job stays in RUNNING
            # state — callers poll the synthesis job UUID, not the audits.
            from celery import chord
            queue_service.update_progress(
                job_id,
                10.0,
                f"Running {len(audit_signatures)} competitor audit(s) before synthesis...",
            )
            # Persist the triggered audit IDs so a watching frontend (or MCP
            # caller) can drill into individual audit progress if desired.
            existing_output = job.output_data or {}
            existing_output.update({
                "status": "audits_in_progress",
                "triggered_audit_job_ids": triggered_audit_job_ids,
            })
            job.output_data = existing_output
            db.commit()
            chord(audit_signatures)(
                resume_unified_synthesis_task.s(synthesis_job_id=job_id)
            )
            return {
                "status": "audits_in_progress",
                "triggered_audit_job_ids": triggered_audit_job_ids,
            }

        # No missing audits — run the rest of synthesis directly.
        return _run_unified_synthesis_post_audits(db, queue_service, job_id)

    except Exception as e:
        error_msg = str(e)
        error_tb = traceback.format_exc()
        print(f"[unified_synthesis_task] Error for job {job_id}: {error_msg}")
        if db:
            try:
                queue_service = QueueService(db)
                queue_service.mark_failure(job_id, error_msg, error_tb)
            except Exception:
                pass
        raise self.retry(exc=e)

    finally:
        if db:
            db.close()


@shared_task(
    bind=True,
    name='app.queue.synthesis_tasks.resume_unified_synthesis_task',
    max_retries=1,
    default_retry_delay=30,
    soft_time_limit=1200,
)
def resume_unified_synthesis_task(self, audit_results, synthesis_job_id: int):
    """Chord callback that resumes synthesis after triggered audits complete.

    The first positional arg `audit_results` is the list of return values from
    the chord's audit tasks; we don't read individual fields from it (the
    audits already wrote CompetitorFunctionalReport rows that
    _run_unified_synthesis_post_audits will load). We only check that at
    least one audit produced a report — if all failed, fail the synthesis
    job rather than running on stale/no data.
    """
    db = None
    try:
        db = SessionLocal()
        queue_service = QueueService(db)

        successful_audits = [
            r for r in (audit_results or [])
            if isinstance(r, dict) and r.get('report_id')
        ]
        if not successful_audits and audit_results:
            queue_service.mark_failure(
                synthesis_job_id,
                "All triggered competitor audits failed; cannot proceed with synthesis.",
                None,
            )
            return {"status": "failed", "reason": "all_audits_failed"}

        return _run_unified_synthesis_post_audits(db, queue_service, synthesis_job_id)

    except Exception as e:
        error_msg = str(e)
        error_tb = traceback.format_exc()
        print(f"[resume_unified_synthesis_task] Error for job {synthesis_job_id}: {error_msg}")
        if db:
            try:
                queue_service = QueueService(db)
                queue_service.mark_failure(synthesis_job_id, error_msg, error_tb)
            except Exception:
                pass
        raise self.retry(exc=e)

    finally:
        if db:
            db.close()


def _run_unified_synthesis_post_audits(db, queue_service, job_id: int) -> Dict[str, Any]:
    """Steps 4-10 of unified synthesis. Re-loads state from DB so this is safe
    to call from a fresh worker context (e.g., the chord callback in
    resume_unified_synthesis_task). Marks the parent job successful or failed
    itself; callers don't need to.
    """
    from app.agents.unified_synthesis_agent import UnifiedSynthesisAgent
    from app.models.synthesis import (
        SynthesisConfig,
        SynthesisReport,
        SynthesisRun,
        SynthesizedOpportunity,
        DEFAULT_INCLUDED_SOURCE_TYPES,
        DEFAULT_IDEA_PRIORITY_THRESHOLD,
    )
    from app.models.competitive_reports import CompetitorFunctionalReport
    from app.models.evidence import Evidence, COMPETITIVE_EVIDENCE_TYPES
    from app.models.idea import Idea, IdeaStatus, SourceType
    from app.models.vote import Vote
    from app.services.internal_theme_merger import InternalThemeMergerService
    from app.services.llm_service import LLMService
    from app.services.scoring_defaults import DEFAULT_SCORING_WEIGHTS
    from sqlalchemy import desc, func as sql_func

    job = queue_service.get_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")

    product_id = job.product_id
    if not product_id:
        raise ValueError("product_id is required for unified synthesis")

    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
    if not product:
        raise ValueError(f"Product {product_id} not found")

    config = db.query(SynthesisConfig).filter(
        SynthesisConfig.product_id == product_id
    ).first()
    if not config:
        # Should not happen — Step 1 of the task creates a default — but
        # be defensive in the resume path in case the row was deleted.
        config = SynthesisConfig(
            product_id=product_id,
            included_source_types=list(DEFAULT_INCLUDED_SOURCE_TYPES),
        )
        db.add(config)
        db.flush()
        db.commit()

    included_sources = list(
        config.included_source_types or list(DEFAULT_INCLUDED_SOURCE_TYPES)
    )
    included_set = {s.lower() for s in included_sources}

    included_competitors = db.query(ProductCompetitor).filter(
        ProductCompetitor.product_id == product_id,
        ProductCompetitor.status == "active",
        ProductCompetitor.tracked == True,  # noqa: E712
    ).all()

    queue_service.update_progress(job_id, 15.0, "Loading product context...")

    # Step 4: Build product_context including job_map
    product_context: Dict[str, Any] = {
        "product_name": product.product_name,
        "product_description": product.product_description,
        "product_category": product.product_category,
    }
    if product.target_customer_profile:
        product_context["target_customer_profile"] = product.target_customer_profile
    if product.job_map:
        product_context["job_map"] = product.job_map

    # Pass features as {feature_name, feature_description} so the synthesis
    # agent can recognize semantic matches and avoid surfacing existing
    # features as opportunities (see "DO NOT surface existing product
    # features" rule in the agent system prompt).
    features = db.query(ProductFeature).filter(
        ProductFeature.product_id == product_id,
        ProductFeature.status == "active",
    ).limit(20).all()
    if features:
        product_context["core_features"] = [
            {
                "feature_name": f.feature_name,
                "feature_description": f.feature_description or "",
            }
            for f in features
        ]

    queue_service.update_progress(job_id, 25.0, "Gathering competitive data...")

    # Step 5a: COMPETITIVE — load functional reports for included competitors
    competitor_reports: List[Dict[str, Any]] = []
    source_competitor_report_ids: List[int] = []
    included_competitor_ids = [c.id for c in included_competitors]

    if "competitive" in included_set and included_competitor_ids:
        functional_reports = db.query(CompetitorFunctionalReport).filter(
            CompetitorFunctionalReport.product_id == product_id,
            CompetitorFunctionalReport.product_competitor_id.in_(included_competitor_ids),
        ).all()

        # Index competitor-linked evidence (filter to competitive types)
        comp_evidence_q = db.query(Evidence).filter(
            Evidence.product_id == product_id,
            Evidence.competitor_id.in_(included_competitor_ids),
        ).order_by(Evidence.created_at.desc()).all()
        evidence_by_competitor: Dict[int, List[Evidence]] = {}
        for ev in comp_evidence_q:
            if ev.evidence_type in COMPETITIVE_EVIDENCE_TYPES:
                evidence_by_competitor.setdefault(ev.competitor_id, []).append(ev)

        for report in functional_reports:
            comp = next(
                (c for c in included_competitors if c.id == report.product_competitor_id),
                None,
            )
            comp_name = (
                comp.competitor_name if comp
                else f"Competitor {report.product_competitor_id}"
            )
            ev_list = evidence_by_competitor.get(report.product_competitor_id, [])[:10]
            competitor_reports.append({
                "competitor_name": comp_name,
                "audit": {
                    "competitor_context": report.competitor_context,
                    "functional_comparison": report.functional_comparison,
                    "gaps_deep_dive": report.gaps_deep_dive,
                    "technical_constraints": report.technical_constraints,
                    "job_assessments": report.job_assessments,
                },
                "evidence": [{
                    "id": ev.id,
                    "title": ev.title,
                    "evidence_type": ev.evidence_type.value if ev.evidence_type else None,
                    "source_url": ev.source_url,
                    "source_description": ev.source_description,
                } for ev in ev_list],
            })
            source_competitor_report_ids.append(report.id)

    queue_service.update_progress(job_id, 40.0, "Gathering customer ideas...")

    # Step 5b: CUSTOMER — top 50 ACCEPTED ideas by vote count
    customer_ideas: List[Dict[str, Any]] = []
    if "customer" in included_set:
        vote_counts = db.query(
            Vote.idea_id,
            sql_func.sum(Vote.vote_value).label("vote_count"),
        ).group_by(Vote.idea_id).subquery()

        ideas_with_votes = db.query(
            Idea,
            sql_func.coalesce(vote_counts.c.vote_count, 0).label("vote_count"),
        ).outerjoin(vote_counts, Idea.id == vote_counts.c.idea_id).filter(
            Idea.product_id == product_id,
            Idea.status == IdeaStatus.ACCEPTED,
        ).order_by(desc("vote_count")).limit(50).all()

        for idea, votes in ideas_with_votes:
            customer_ideas.append({
                "id": idea.id,
                "title": idea.title,
                "description": idea.what_description or "",
                "vote_count": int(votes) if votes else 0,
                "status": idea.status.value if idea.status else "unknown",
                "jtbd_statement": getattr(idea, "jtbd_statement", None),
                "job_id_key": getattr(idea, "job_id_key", None),
            })

    queue_service.update_progress(job_id, 55.0, "Gathering internal feedback...")

    # Step 5c: INTERNAL — merged win/loss + support themes
    winloss_themes: List[Dict[str, Any]] = []
    support_themes: List[Dict[str, Any]] = []
    if "internal" in included_set:
        merger = InternalThemeMergerService(db)
        merged = merger.merge_internal_evidence(product_id)
        internal_data = merger.to_synthesis_format(merged)
        winloss_themes = internal_data.get("winloss_themes", []) or []
        support_themes = internal_data.get("support_themes", []) or []

    queue_service.update_progress(job_id, 65.0, "Gathering evidence/research...")

    # Step 5d: EVIDENCE — non-competitive Evidence records
    evidence_items: List[Dict[str, Any]] = []
    if "evidence" in included_set:
        all_evidence = db.query(Evidence).filter(
            Evidence.product_id == product_id,
        ).order_by(Evidence.created_at.desc()).limit(100).all()
        for ev in all_evidence:
            if ev.evidence_type in COMPETITIVE_EVIDENCE_TYPES:
                continue  # already routed via competitive enrichment
            evidence_items.append({
                "id": ev.id,
                "evidence_id": ev.id,
                "title": ev.title,
                "evidence_type": ev.evidence_type.value if ev.evidence_type else None,
                "content": ev.content,
                "source_url": ev.source_url,
                "source_description": ev.source_description,
                "jtbd_statement": ev.jtbd_statement,
                "job_id_key": None,
            })

    queue_service.update_progress(job_id, 70.0, "Running unified synthesis agent...")

    # Step 6: Compute effective scoring weights (defaults ∪ overrides)
    effective_weights: Dict[str, Any] = {
        k: (v.copy() if isinstance(v, dict) else v)
        for k, v in DEFAULT_SCORING_WEIGHTS.items()
    }
    overrides = config.scoring_weight_overrides or {}
    for key, val in overrides.items():
        if isinstance(val, dict) and isinstance(effective_weights.get(key), dict):
            effective_weights[key] = {**effective_weights[key], **val}
        else:
            effective_weights[key] = val

    # Sanity check: at least one source produced data
    has_data = bool(
        competitor_reports or customer_ideas or winloss_themes
        or support_themes or evidence_items
    )
    if not has_data:
        raise ValueError(
            "No data available for unified synthesis. Configure source types "
            "and ensure at least one source has data."
        )

    # Step 7: Run agent
    llm_service = LLMService()
    agent = UnifiedSynthesisAgent(
        db=db,
        llm_service=llm_service,
        product_id=product_id,
        user_id=job.user_id,
        job_id=job.job_uuid,
        scoring_weights=effective_weights,
    )

    agent_input = {
        "product_context": product_context,
        "included_source_types": included_sources,
        "competitor_reports": competitor_reports,
        "customer_ideas": customer_ideas,
        "winloss_themes": winloss_themes,
        "support_themes": support_themes,
        "evidence_items": evidence_items,
    }
    # JTBD synthesis output can be verbose: job_scorecard (per job) +
    # feature_cluster_matrix (nested by job) + opportunities with
    # multi-source evidence blobs. With 10+ jobs × 2-3 competitors,
    # 20000 tokens gives enough headroom.
    result = agent.execute(agent_input, max_tokens=20000)

    queue_service.update_progress(job_id, 85.0, "Persisting synthesis report...")

    # Step 8: Persist SynthesisReport
    previous_report = db.query(SynthesisReport).filter(
        SynthesisReport.product_id == product_id,
    ).order_by(desc(SynthesisReport.report_version)).first()
    next_version = (previous_report.report_version + 1) if previous_report else 1

    source_stats = {
        "competitor_count": len(included_competitors),
        "competitor_report_count": len(competitor_reports),
        "idea_count": len(customer_ideas),
        "winloss_count": len(winloss_themes),
        "support_count": len(support_themes),
        "evidence_count": len(evidence_items),
    }

    markdown_md = _build_unified_synthesis_markdown(
        product.product_name, result, source_stats,
    )

    synthesis_report = SynthesisReport(
        product_id=product_id,
        report_version=next_version,
        included_source_types=included_sources,
        job_scorecard=result.get("job_scorecard"),
        feature_cluster_matrix=result.get("feature_cluster_matrix"),
        opportunities=result.get("opportunities"),
        high_impact_items=result.get("high_impact_items"),
        innovation_whitespace=result.get("innovation_whitespace"),
        analysis_summary=result.get("analysis_summary"),
        source_stats=source_stats,
        included_competitor_ids=included_competitor_ids,
        source_competitor_report_ids=source_competitor_report_ids,
        report_content_md=markdown_md,
        queue_job_id=job_id,
    )
    db.add(synthesis_report)
    db.flush()

    # Step 9: Persist SynthesizedOpportunity rows.
    # NOTE: synthesized_opportunities.synthesis_run_id is NOT NULL, so we
    # also create a lightweight SynthesisRun for backward-compat consumers.
    backing_run = SynthesisRun(
        product_id=product_id,
        status="completed",
        sources_used=included_sources,
        source_snapshot=source_stats,
        analysis_summary=result.get("analysis_summary"),
        job_uuid=job.job_uuid,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(backing_run)
    db.flush()

    opportunities_out = result.get("opportunities") or []
    # Pre-compute JTBD embeddings (single batch call)
    jtbd_texts = [
        o.get("jtbd_statement") for o in opportunities_out if o.get("jtbd_statement")
    ]
    jtbd_emb_map: Dict[str, list] = {}
    if jtbd_texts:
        try:
            from app.services.embedding_service import generate_embeddings_batch
            embs = generate_embeddings_batch(jtbd_texts, input_type="document")
            jtbd_emb_map = dict(zip(jtbd_texts, embs))
        except Exception as emb_err:
            print(
                f"[unified_synthesis_task] Warning: opportunity JTBD embedding failed: "
                f"{emb_err}"
            )

    # Keyed by opportunity_name so the auto-idea-gen loop below can backfill
    # linked_idea_id when an idea is created from a given opportunity.
    opp_rows_by_name: Dict[str, SynthesizedOpportunity] = {}
    for opp in opportunities_out:
        db_opp = SynthesizedOpportunity(
            synthesis_run_id=backing_run.id,
            synthesis_report_id=synthesis_report.id,
            product_id=product_id,
            opportunity_name=opp.get("opportunity_name", "Opportunity"),
            opportunity_summary=opp.get("opportunity_summary"),
            priority_score=float(opp.get("priority_score", 0.0)),
            source_count=int(opp.get("source_count", 1)),
            sources=opp.get("sources") or [],
            competitive_evidence=opp.get("competitive_evidence"),
            customer_evidence=opp.get("customer_evidence"),
            internal_evidence=opp.get("internal_evidence"),
            evidence_signals=opp.get("evidence_signals"),
            recommended_action=opp.get("recommended_action"),
            feature_keywords=opp.get("feature_keywords") or [],
            jtbd_statement=opp.get("jtbd_statement"),
            jtbd_embedding=jtbd_emb_map.get(opp.get("jtbd_statement") or ""),
            job_id_key=opp.get("job_id_key"),
            investment_tier=opp.get("investment_tier"),
            job_satisfaction_delta=opp.get("job_satisfaction_delta"),
        )
        db.add(db_opp)
        opp_rows_by_name[db_opp.opportunity_name] = db_opp

    db.commit()
    db.refresh(synthesis_report)

    # Increment citation counts for evidence referenced in this synthesis report
    try:
        from app.services.evidence_service import increment_evidence_citations

        cited_ids: set = set()

        # job_scorecard[*].evidence_ids
        for entry in (synthesis_report.job_scorecard or []):
            if not isinstance(entry, dict):
                continue
            for eid in (entry.get("evidence_ids") or []):
                if eid is not None:
                    cited_ids.add(eid)

        # opportunities[*].evidence_signals.items[*].evidence_id
        for opp in (synthesis_report.opportunities or []):
            if not isinstance(opp, dict):
                continue
            signals = opp.get("evidence_signals") or {}
            if isinstance(signals, dict):
                for item in (signals.get("items") or []):
                    if isinstance(item, dict) and item.get("evidence_id") is not None:
                        cited_ids.add(item["evidence_id"])

        if cited_ids:
            increment_evidence_citations(
                db,
                list(cited_ids),
                f"synthesis_report:{synthesis_report.id}",
            )
            db.commit()
    except Exception as cite_err:
        print(f"[unified_synthesis_task] Warning: Citation increment failed: {cite_err}")

    queue_service.update_progress(job_id, 95.0, "Auto-generating ideas (if enabled)...")

    # Step 10: Auto-generate ideas above threshold
    ideas_generated = 0
    triage_jobs_created = 0
    if config.auto_generate_ideas and opportunities_out:
        # Threshold is 0.0-1.0 in config; opportunity priority_score is 0-100
        score_threshold = float(
            config.idea_priority_threshold or DEFAULT_IDEA_PRIORITY_THRESHOLD
        ) * 100.0
        for opp in opportunities_out:
            if float(opp.get("priority_score", 0.0)) < score_threshold:
                continue
            feature_name = opp.get("opportunity_name", "Opportunity")
            # Dedup by name + source
            existing_idea = db.query(Idea).filter(
                Idea.product_id == product_id,
                Idea.title == feature_name[:255],
                Idea.source_type == SourceType.COMPETITOR_AUTOMATED,
            ).first()
            if existing_idea:
                continue

            competitors_with = _extract_competitor_names(opp.get("competitive_evidence"))
            source_metadata = {
                "synthesis_report_id": synthesis_report.id,
                "synthesis_report_version": synthesis_report.report_version,
                "feature_name": feature_name,
                "priority_score": opp.get("priority_score"),
                "sources": opp.get("sources") or [],
                "job_id_key": opp.get("job_id_key"),
                "investment_tier": opp.get("investment_tier"),
                "competitors_with_feature": competitors_with,
                "competitor_names": competitors_with,
            }

            use_case_lines = ["Synthesized from multiple sources:"]
            for src in (opp.get("sources") or []):
                use_case_lines.append(f"- {src}")

            new_idea = Idea(
                title=feature_name[:255],
                what_description=opp.get("opportunity_summary") or feature_name,
                why_description=(opp.get("recommended_action") or "")[:1000],
                use_case_description="\n".join(use_case_lines),
                product_id=product_id,
                source_type=SourceType.COMPETITOR_AUTOMATED,
                source_metadata=source_metadata,
                status=IdeaStatus.PENDING,
                is_active=False,
                auto_categorized=False,
            )
            db.add(new_idea)
            db.flush()
            ideas_generated += 1

            # Backfill linked_idea_id on the matching opportunity row so
            # downstream views can render a "created as Idea #N" badge.
            # Use a direct UPDATE rather than attribute assignment because
            # the intervening queue_service.create_job() commit was silently
            # dropping in-session attribute changes in this code path.
            matching_opp = opp_rows_by_name.get(feature_name)
            if matching_opp is not None:
                db.query(SynthesizedOpportunity).filter(
                    SynthesizedOpportunity.id == matching_opp.id
                ).update(
                    {SynthesizedOpportunity.linked_idea_id: new_idea.id},
                    synchronize_session=False,
                )

            triage_job = queue_service.create_job(
                job_type=JobType.IDEA_TRIAGE,
                input_data={"idea_id": new_idea.id},
                product_id=product_id,
                parent_job_id=job_id,
                user_id=job.user_id,
            )
            db.commit()
            try:
                triage_idea_task.delay(triage_job.id)
                triage_jobs_created += 1
            except Exception as dispatch_err:
                print(
                    f"[unified_synthesis_task] Triage dispatch failed: {dispatch_err}"
                )

    output_data = {
        "synthesis_report_id": synthesis_report.id,
        "report_version": synthesis_report.report_version,
        "included_sources": included_sources,
        "source_stats": source_stats,
        "opportunities_count": len(opportunities_out),
        "ideas_generated": ideas_generated,
        "triage_jobs_created": triage_jobs_created,
    }
    queue_service.mark_success(job_id, output_data)
    return output_data
