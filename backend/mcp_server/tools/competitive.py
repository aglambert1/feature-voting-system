"""Competitive intelligence tools for MCP server."""

from mcp_server import mcp
from mcp_server.db import get_session
from mcp_server.permissions import require_product_access, require_product_analyzed, require_no_active_job, resolve_user_id_for_job

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
                "audit_enabled": c.audit_enabled,
                "audit_status": c.audit_status,
                "synthesis_included": c.synthesis_included,
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
            "job_assessments": report.job_assessments,
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

    Poll with job_get_status until complete. The completed job's output_data includes competitor_names — use each name to call ci_run_competitor_audit.

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
            user_id=resolve_user_id_for_job(db, product_id),
        )

        from mcp_server.db import dispatch_task
        result = dispatch_task(discover_competitors_task, job.id)
        queue_service.mark_queued(job.id, result.id)

        return {
            "job_id": job.id,
            "job_uuid": job.job_uuid,
            "max_competitors": max_competitors,
            "status": "queued",
            "message": f"Competitor discovery queued (max {max_competitors}). Poll with job_get_status until complete. "
                       "The completed job's output_data.competitor_names lists discovered names — "
                       "run ci_run_competitor_audit for each name.",
        }


@mcp.tool()
def ci_run_competitor_audit(
    product_id: int,
    competitor_name: str,
    web_research: bool = True,
    source_urls: list[str] | None = None,
) -> dict:
    """Trigger a functional audit for a single competitor. Returns a job ID — poll with job_get_status until complete. After all competitor audits finish, run synthesis_run_unified for unified synthesis.

    Args:
        product_id: The product the competitor belongs to.
        competitor_name: Name (or partial name) of the competitor.
        web_research: If true (default), the agent supplements its training knowledge with live Brave web search. Set false to skip Brave and rely on training knowledge + any Evidence records + provided source_urls. Major latency win when false.
        source_urls: Optional list of specific pages to fetch and feed to the agent (max 5 URLs). Useful for grounding analysis in pricing pages, feature lists, or docs you want the agent to cite. For persistent text input, use evidence_create first — Evidence records are reusable across audits and tracked for citations.
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
        if not competitor.audit_enabled:
            competitor.audit_enabled = True
        if not competitor.synthesis_included:
            competitor.synthesis_included = True
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

        from app.queue.tasks import functional_audit_task
        from mcp_server.db import dispatch_task
        result = dispatch_task(functional_audit_task, job.id)
        queue_service.mark_queued(job.id, result.id)

        return {
            "job_id": job.id,
            "job_uuid": job.job_uuid,
            "competitor_name": competitor.competitor_name,
            "status": "queued",
            "message": f"Functional audit for {competitor.competitor_name} queued. Poll with job_get_status until complete. "
                       "After all audits finish, run synthesis_run_unified for unified synthesis.",
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
def ci_set_audit(product_id: int, competitor_id: int, enabled: bool) -> dict:
    """Enable or disable a competitor for functional audit. When enabling, the competitor is also included in synthesis by default.

    Args:
        product_id: The product.
        competitor_id: The competitor to configure.
        enabled: True to enable audit, False to disable.
    """
    from app.models.competitor_intelligence import ProductCompetitor

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.EDIT)
        if denied:
            return denied

        competitor = db.query(ProductCompetitor).filter(
            ProductCompetitor.id == competitor_id,
            ProductCompetitor.product_id == product_id,
        ).first()

        if not competitor:
            return {"error": f"Competitor {competitor_id} not found for product {product_id}"}

        competitor.audit_enabled = enabled
        competitor.deep_analysis_enabled = enabled  # backward compat
        if enabled and not competitor.synthesis_included:
            competitor.synthesis_included = True
        db.flush()

        return {
            "competitor_id": competitor.id,
            "competitor_name": competitor.competitor_name,
            "audit_enabled": competitor.audit_enabled,
            "synthesis_included": competitor.synthesis_included,
            "message": f"{'Enabled' if enabled else 'Disabled'} audit for {competitor.competitor_name}."
                       + (" Also included in synthesis." if enabled and competitor.synthesis_included else ""),
        }


@mcp.tool()
def ci_set_synthesis_inclusion(product_id: int, competitor_id: int, included: bool) -> dict:
    """Include or exclude a competitor from synthesis. This is separate from auditing — a competitor can be audited but excluded from synthesis.

    Args:
        product_id: The product.
        competitor_id: The competitor to configure.
        included: True to include in synthesis, False to exclude.
    """
    from app.models.competitor_intelligence import ProductCompetitor

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.EDIT)
        if denied:
            return denied

        competitor = db.query(ProductCompetitor).filter(
            ProductCompetitor.id == competitor_id,
            ProductCompetitor.product_id == product_id,
        ).first()

        if not competitor:
            return {"error": f"Competitor {competitor_id} not found for product {product_id}"}

        competitor.synthesis_included = included
        db.flush()

        return {
            "competitor_id": competitor.id,
            "competitor_name": competitor.competitor_name,
            "synthesis_included": competitor.synthesis_included,
            "message": f"{'Included' if included else 'Excluded'} {competitor.competitor_name} from synthesis.",
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
                for ja in report.job_assessments:
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
def ci_get_competitor_details(product_id: int, competitor_name: str, section: str) -> dict:
    """Get detailed information about a specific competitor by section.

    Args:
        product_id: The product the competitor belongs to.
        competitor_name: Name (or partial name) of the competitor.
        section: One of "features", "pricing", "positioning", "changes", "momentum".
            - features: functional comparison showing feature-by-feature mapping status
            - pricing: technical constraints including integrations and API capabilities
            - positioning: competitor context — positioning, differentiation, target customer
            - changes: changes from previous report version
            - momentum: deep analysis status and report versioning history
    """
    from app.models.competitor_intelligence import ProductCompetitor
    from app.models.competitive_reports import CompetitorFunctionalReport

    valid_sections = {"features", "pricing", "positioning", "changes", "momentum"}
    if section not in valid_sections:
        return {"error": f"Invalid section '{section}'. Must be one of: {', '.join(sorted(valid_sections))}"}

    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

        competitor = db.query(ProductCompetitor).filter(
            ProductCompetitor.product_id == product_id,
            ProductCompetitor.competitor_name.ilike(f"%{competitor_name}%"),
        ).first()

        if not competitor:
            return {"error": f"No competitor matching '{competitor_name}' found"}

        report = db.query(CompetitorFunctionalReport).filter(
            CompetitorFunctionalReport.product_competitor_id == competitor.id
        ).first()

        base = {
            "competitor_name": competitor.competitor_name,
            "competitor_id": competitor.id,
            "section": section,
        }

        if section == "features":
            if not report:
                return {**base, "error": "No report available. Run ci_run_competitor_audit first."}
            return {
                **base,
                "functional_comparison": report.functional_comparison,
                "gaps_deep_dive": report.gaps_deep_dive,
            }
        elif section == "pricing":
            if not report:
                return {**base, "error": "No report available. Run ci_run_competitor_audit first."}
            return {
                **base,
                "technical_constraints": report.technical_constraints,
            }
        elif section == "positioning":
            if not report:
                return {**base, "error": "No report available. Run ci_run_competitor_audit first."}
            return {
                **base,
                "competitor_context": report.competitor_context,
            }
        elif section == "changes":
            if not report:
                return {**base, "error": "No report available. Run ci_run_competitor_audit first."}
            return {
                **base,
                "report_version": report.report_version,
                "generated_at": report.generated_at.isoformat(),
                "changes_from_previous": report.changes_from_previous,
            }
        else:  # momentum
            return {
                **base,
                "deep_analysis_enabled": competitor.deep_analysis_enabled,
                "deep_analysis_status": competitor.deep_analysis_status,
                "deep_analysis_last_run": competitor.deep_analysis_last_run.isoformat() if competitor.deep_analysis_last_run else None,
                "has_report": report is not None,
                "report_version": report.report_version if report else None,
                "generated_at": report.generated_at.isoformat() if report else None,
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

        competitor = db.query(ProductCompetitor).filter(
            ProductCompetitor.product_id == product_id,
            ProductCompetitor.competitor_name.ilike(f"%{competitor_name}%"),
            ProductCompetitor.status == "active",
        ).first()

        if not competitor:
            return {"error": f"No active competitor matching '{competitor_name}' found for product {product_id}"}

        competitor.status = "inactive"
        competitor.deep_analysis_enabled = False
        db.flush()

        return {
            "competitor_id": competitor.id,
            "competitor_name": competitor.competitor_name,
            "status": "inactive",
            "message": f"Competitor '{competitor.competitor_name}' deactivated. Reports are preserved.",
        }


