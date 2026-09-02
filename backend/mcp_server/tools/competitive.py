"""Competitive intelligence tools for MCP server."""

from mcp_server import mcp
from mcp_server.db import get_session
from mcp_server.permissions import require_product_access, require_product_analyzed, require_no_active_job, resolve_user_id_for_job

from app.models.competitor_intelligence import ProductPermissionLevel
from app.services.evidence_service import resolve_competitor_by_name


def _grounding_for(db, product_id: int) -> dict:
    """Which jobs can carry a comparison verdict, keyed by job_id.

    An agent reading these treats them as fact and has no UI caveat beside them, so a
    verdict built on an ungrounded self-score is more dangerous here than on screen.
    Same rule and same source as the app: our confidence from the live self-assessment,
    plus corroborating signals.
    """
    from app.models.competitive_reports import ProductSelfAssessment
    from app.services.job_provenance import signal_counts
    from app.utils.job_position import verdict_grounding

    latest = db.query(ProductSelfAssessment).filter(
        ProductSelfAssessment.product_id == product_id
    ).order_by(ProductSelfAssessment.assessment_version.desc()).first()
    confidences = {
        e.get("job_id"): e.get("confidence")
        for e in ((latest.job_assessments or []) if latest else [])
        if isinstance(e, dict) and e.get("job_id")
    }
    corroboration = signal_counts(db, product_id)

    out = {}
    for job_id, conf in confidences.items():
        shown, reason = verdict_grounding(
            conf, (corroboration.get(job_id) or {}).get("total", 0)
        )
        out[job_id] = {"shown": shown, "reason": reason}
    return out


def _apply_grounding(assessments, grounding: dict) -> list:
    """Strip the derived verdict where it is not grounded.

    A human override survives: it is the PM's own claim and does not rest on our score.
    The competitor's score always survives — it is researched independently of our job
    map and is unaffected by that map's weakness.
    """
    result = []
    for ja in (assessments or []):
        if not isinstance(ja, dict):
            continue
        item = dict(ja)
        g = grounding.get(item.get("job_id"))
        if g and not g["shown"] and not item.get("human_position"):
            item["system_position"] = None
            item["our_score"] = None
            item["verdict_withheld_reason"] = g["reason"]
        result.append(item)
    return result


@mcp.tool()
def ci_get_competitor_list(product_id: int) -> dict:
    """List all competitors for a product with audit status and synthesis-inclusion flags.

    `has_report` is the authoritative signal that an audit has been performed —
    `audit_status` may be stale for reports generated before the status field
    was populated. Use this to see all competitors at a glance; use
    ci_get_competitor_report for a single competitor's full report.
    """
    from app.models.competitor_intelligence import ProductCompetitor
    from mcp_server.serializers import competitor_summary, latest_functional_report

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
                competitor_summary(c, latest_functional_report(db, c.id))
                for c in competitors
            ],
        }


@mcp.tool()
def ci_get_competitor_report(product_id: int, competitor_name: str, section: str = "") -> dict:
    """Get the functional audit report for a competitor — full report by default, or a single section to save context.

    Args:
        product_id: The product the competitor belongs to.
        competitor_name: Name (or partial name) of the competitor.
        section: Empty for the full report, or one of:
            - features: functional_comparison + gaps_deep_dive
            - positioning: competitor_context (positioning, differentiation, target customer)
            - constraints: technical_constraints (integrations, API capabilities)
            - changes: changes from the previous report version
            - status: tracked/audit status and report versioning (works without a report)
            Note: pricing signals live in positioning and evidence, not in a
            dedicated section.
    """
    from mcp_server.serializers import competitor_summary, latest_functional_report

    valid_sections = {"", "features", "positioning", "constraints", "changes", "status"}
    if section not in valid_sections:
        return {"error": f"Invalid section '{section}'. Must be one of: {', '.join(sorted(s for s in valid_sections if s))} (or empty for the full report)"}

    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

        # Fuzzy match on competitor name; include deactivated competitors —
        # deactivation preserves reports, so reads must keep working.
        competitor = resolve_competitor_by_name(
            db, product_id, competitor_name, active_only=False
        )

        if not competitor:
            return {"error": f"No competitor matching '{competitor_name}' found"}

        report = latest_functional_report(db, competitor.id)

        base = {
            "competitor_name": competitor.competitor_name,
            "competitor_id": competitor.id,
        }

        if section == "status":
            return {**base, "section": section, **competitor_summary(competitor, report)}

        if not report:
            return {**base, "error": f"No report available for {competitor.competitor_name}. Run ci_run_competitor_audit first."}

        if section == "features":
            return {
                **base,
                "section": section,
                "functional_comparison": report.functional_comparison,
                "gaps_deep_dive": report.gaps_deep_dive,
            }
        if section == "positioning":
            return {**base, "section": section, "competitor_context": report.competitor_context}
        if section == "constraints":
            return {**base, "section": section, "technical_constraints": report.technical_constraints}
        if section == "changes":
            return {
                **base,
                "section": section,
                "report_version": report.report_version,
                "generated_at": report.generated_at.isoformat(),
                "changes_from_previous": report.changes_from_previous,
            }

        # Full report
        from app.models.evidence import Evidence
        linked_evidence = db.query(Evidence).filter(
            Evidence.product_id == product_id,
            Evidence.competitor_id == competitor.id,
        ).order_by(Evidence.created_at.desc()).limit(20).all()

        return {
            **base,
            "report_version": report.report_version,
            "generated_at": report.generated_at.isoformat(),
            "audit_status": competitor.audit_status,
            "audit_last_run": competitor.audit_last_run.isoformat() if competitor.audit_last_run else None,
            "competitor_context": report.competitor_context,
            "functional_comparison": report.functional_comparison,
            "gaps_deep_dive": report.gaps_deep_dive,
            "technical_constraints": report.technical_constraints,
            "changes_from_previous": report.changes_from_previous,
            "job_assessments": _apply_grounding(
                report.job_assessments, _grounding_for(db, product_id)
            ),
            "evidence_citations": report.evidence_citations,
            "additional_evidence": [e.to_summary_dict() for e in linked_evidence],
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

        parsed = urlparse(competitor_url)
        domain = parsed.netloc or parsed.path
        domain = domain.replace("www.", "")

        # Check for duplicate by name or domain. A deactivated match is
        # reactivated instead of blocking the add forever.
        existing = db.query(ProductCompetitor).filter(
            ProductCompetitor.product_id == product_id,
            ProductCompetitor.competitor_name.ilike(competitor_name),
        ).first()
        if not existing:
            existing = db.query(ProductCompetitor).filter(
                ProductCompetitor.product_id == product_id,
                ProductCompetitor.competitor_url.ilike(f"%{domain}%"),
            ).first()
        if existing:
            if existing.status == "inactive":
                existing.status = "active"
                existing.tracked = True
                db.flush()
                return {
                    "competitor_id": existing.id,
                    "competitor_name": existing.competitor_name,
                    "message": f"Competitor '{existing.competitor_name}' was deactivated and has been reactivated (tracked).",
                }
            return {"error": f"Competitor '{existing.competitor_name}' already exists (id={existing.id})"}

        competitor = ProductCompetitor(
            product_id=product_id,
            competitor_name=competitor_name,
            competitor_url=competitor_url,
            tracked=True,
            status="active",
        )
        db.add(competitor)
        db.flush()

        return {
            "competitor_id": competitor.id,
            "competitor_name": competitor.competitor_name,
            "competitor_url": competitor.competitor_url,
            "tracked": True,
            "message": f"Competitor '{competitor_name}' added. Run ci_run_competitor_audit to analyze.",
        }


@mcp.tool()
def ci_run_discovery(product_id: int, max_competitors: int = 5, wait_seconds: int = 0) -> dict:
    """Discover competitors automatically using AI analysis of the product. Returns a job ID.

    Poll with job_get_status until complete. The completed job's output_data includes competitor_names — use each name to call ci_run_competitor_audit.

    Args:
        product_id: The product to discover competitors for.
        max_competitors: Maximum number of competitors to discover (1-20, default 5).
        wait_seconds: If > 0, wait up to this many seconds (max 120) for the job to finish and return its result inline. Default 0 returns immediately with status "queued" — poll job_get_status. On timeout the result includes "waiting": true.
    """
    from app.models.queue import JobType
    from app.services.queue_service import QueueService
    from app.queue.competitor_tasks import discover_competitors_task

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
            user_id=resolve_user_id_for_job(db, product_id),
        )

        from mcp_server.db import dispatch_task
        from mcp_server.job_wait import maybe_wait
        result = dispatch_task(discover_competitors_task, job.id)
        queue_service.mark_queued(job.id, result.id)

        return maybe_wait({
            "job_id": job.id,
            "job_uuid": job.job_uuid,
            "max_competitors": max_competitors,
            "status": "queued",
            "message": f"Competitor discovery queued (max {max_competitors}). Poll with job_get_status until complete. "
                       "The completed job's output_data.competitor_names lists discovered names — "
                       "run ci_run_competitor_audit for each name.",
        }, wait_seconds)


@mcp.tool()
def ci_run_competitor_audit(
    product_id: int,
    competitor_name: str,
    web_research: bool = True,
    source_urls: list[str] | None = None,
    wait_seconds: int = 0,
) -> dict:
    """Trigger a functional audit for a single competitor. Returns a job ID — poll with job_get_status until complete. After all competitor audits finish, run synthesis_run_unified for unified synthesis.

    Args:
        product_id: The product the competitor belongs to.
        competitor_name: Name (or partial name) of the competitor.
        web_research: If true (default), the agent supplements its training knowledge with live Brave web search. Set false to skip Brave and rely on training knowledge + any Evidence records + provided source_urls. Major latency win when false.
        source_urls: Optional list of specific pages to fetch and feed to the agent (max 5 URLs). Useful for grounding analysis in pricing pages, feature lists, or docs you want the agent to cite. For persistent text input, use evidence_add first — Evidence records are reusable across audits and tracked for citations.
        wait_seconds: If > 0, wait up to this many seconds (max 120) for the job to finish and return its result inline. Default 0 returns immediately with status "queued" — poll job_get_status. On timeout the result includes "waiting": true.
    """
    from app.models.competitor_intelligence import ProductCompetitor
    from app.models.queue import JobType
    from app.services.queue_service import QueueService
    from app.services.scoped_input_validator import validate_scoped_inputs, ScopedInputError

    # Validate scoped inputs before touching the DB
    try:
        source_urls = validate_scoped_inputs(source_urls)
    except ScopedInputError as err:
        return err.payload

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.EDIT)
        if denied:
            return denied

        competitor = resolve_competitor_by_name(db, product_id, competitor_name)

        if not competitor:
            return {"error": f"No active competitor matching '{competitor_name}' found for product {product_id}"}

        # Check for active audit job
        conflict = require_no_active_job(db, product_id, JobType.FUNCTIONAL_AUDIT, "Functional audit")
        if conflict:
            return conflict

        db.flush()

        queue_service = QueueService(db)
        job = queue_service.create_job(
            job_type=JobType.FUNCTIONAL_AUDIT,
            input_data={
                "competitor_id": competitor.id,
                "web_research_enabled": web_research,
                "source_urls": source_urls,
            },
            product_id=product_id,
            user_id=resolve_user_id_for_job(db, product_id),
        )

        from app.queue.competitor_tasks import functional_audit_task
        from mcp_server.db import dispatch_task
        from mcp_server.job_wait import maybe_wait
        result = dispatch_task(functional_audit_task, job.id)
        queue_service.mark_queued(job.id, result.id)

        return maybe_wait({
            "job_id": job.id,
            "job_uuid": job.job_uuid,
            "competitor_name": competitor.competitor_name,
            "status": "queued",
            "message": f"Functional audit for {competitor.competitor_name} queued. Poll with job_get_status until complete. "
                       "After all audits finish, run synthesis_run_unified for unified synthesis.",
        }, wait_seconds)


@mcp.tool()
def ci_refresh_research(product_id: int, competitor_name: str) -> dict:
    """Force a re-fetch of cached web research for a competitor.

    Runs 3-5 targeted Brave queries (features, pricing, integrations, reviews, vs-product),
    merges and dedupes results, and stores them on the competitor. Subsequent audits
    within the TTL (default 24h) will use the cached payload and skip Brave entirely.

    Runs synchronously (~5s). Use when you know a competitor has shipped something new
    and the stored cache is stale.

    Args:
        product_id: The product the competitor belongs to.
        competitor_name: Name (or partial name) of the competitor.
    """
    from app.models.competitor_intelligence import CIProduct, ProductCompetitor, ProductFeature
    from app.services.competitor_research_cache import CompetitorResearchCache

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.EDIT)
        if denied:
            return denied

        competitor = resolve_competitor_by_name(db, product_id, competitor_name)

        if not competitor:
            return {"error": f"No active competitor matching '{competitor_name}' found for product {product_id}"}

        # Build product_context for the "vs" query — matches the shape
        # functional_audit_task assembles, so the cache queries are stable
        # across refresh paths.
        product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
        features = (
            db.query(ProductFeature)
            .filter(ProductFeature.product_id == product_id, ProductFeature.status == "active")
            .limit(15)
            .all()
        )
        product_context = {
            "product_name": product.product_name if product else "",
            "product_category": product.product_category if product else None,
            "core_features": [f.feature_name for f in features],
        }

        results = CompetitorResearchCache(db).refresh(competitor, product_context)

        return {
            "competitor_id": competitor.id,
            "competitor_name": competitor.competitor_name,
            "results_count": len(results),
            "cached_at": competitor.cached_search_at.isoformat() if competitor.cached_search_at else None,
            "message": f"Refreshed research for {competitor.competitor_name}. "
                       f"Cached {len(results)} results; next audit within TTL will use this payload.",
        }


@mcp.tool()
def ci_set_tracked(product_id: int, competitor_name: str, tracked: bool) -> dict:
    """Set whether a competitor is tracked (scheduled for audit + included in synthesis).

    Args:
        product_id: The product the competitor belongs to.
        competitor_name: Name (or partial name) of the competitor.
        tracked: True to track, False to untrack.
    """
    from app.models.competitor_intelligence import ProductCompetitor

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.EDIT)
        if denied:
            return denied

        competitor = resolve_competitor_by_name(db, product_id, competitor_name)

        if not competitor:
            return {"error": f"No active competitor matching '{competitor_name}' found for product {product_id}"}

        competitor.tracked = tracked
        db.flush()

        return {
            "competitor_id": competitor.id,
            "competitor_name": competitor.competitor_name,
            "tracked": competitor.tracked,
            "message": f"{'Tracking' if tracked else 'Untracked'} {competitor.competitor_name}.",
        }


@mcp.tool()
def ci_get_job_comparison(product_id: int, job_id: str) -> dict:
    """Compare how all audited competitors score on a specific job from the job map.

    Args:
        product_id: The product.
        job_id: The job ID from the job map (e.g., 'j1').
    """
    from app.models.competitor_intelligence import ProductCompetitor, CIProduct
    from app.models.competitive_reports import CompetitorFunctionalReport

    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

        # Validate job_id exists in the product's job map
        product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
        if not product or not product.job_map:
            return {"error": "No job map configured for this product. Run job map extraction first."}

        # Find the job in the job map
        job_info = None
        jobs = product.job_map.get("jobs", [])
        for j in jobs:
            if j.get("id") == job_id:
                job_info = j
                break

        if not job_info:
            available_ids = [j.get("id") for j in jobs]
            return {"error": f"Job '{job_id}' not found in job map. Available: {available_ids}"}

        # Get all reports for this product
        reports = db.query(CompetitorFunctionalReport).join(
            ProductCompetitor,
            CompetitorFunctionalReport.product_competitor_id == ProductCompetitor.id
        ).filter(
            ProductCompetitor.product_id == product_id,
            ProductCompetitor.status == "active",
        ).all()

        comparison = []
        for report in reports:
            competitor = db.query(ProductCompetitor).filter(
                ProductCompetitor.id == report.product_competitor_id
            ).first()

            assessment = None
            if report.job_assessments:
                grounded = _apply_grounding(
                    report.job_assessments, _grounding_for(db, product_id)
                )
                for ja in grounded:
                    if ja.get("job_id") == job_id:
                        assessment = ja
                        break

            comparison.append({
                "competitor_id": competitor.id if competitor else None,
                "competitor_name": competitor.competitor_name if competitor else "Unknown",
                "assessment": assessment,
            })

        return {
            "product_id": product_id,
            "job_id": job_id,
            "job_info": job_info,
            "competitors": comparison,
        }


@mcp.tool()
def ci_deactivate_competitor(product_id: int, competitor_name: str) -> dict:
    """Deactivate a competitor (soft-delete). Reports are preserved but the competitor is excluded from future analyses.

    Args:
        product_id: The product the competitor belongs to.
        competitor_name: Name (or partial name) of the competitor to deactivate.
    """
    from app.models.competitor_intelligence import ProductCompetitor

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.EDIT)
        if denied:
            return denied

        competitor = resolve_competitor_by_name(db, product_id, competitor_name)

        if not competitor:
            return {"error": f"No active competitor matching '{competitor_name}' found for product {product_id}"}

        competitor.status = "inactive"
        competitor.tracked = False
        db.flush()

        return {
            "competitor_id": competitor.id,
            "competitor_name": competitor.competitor_name,
            "status": "inactive",
            "message": f"Competitor '{competitor.competitor_name}' deactivated. Reports are preserved.",
        }


