"""Product tools for MCP server."""

import json

from mcp_server import mcp
from mcp_server.db import get_session
from mcp_server.permissions import (
    get_permitted_products,
    require_product_access,
    require_product_analyzed,
    require_no_active_job,
    resolve_user_id_for_job,
)
from mcp_server.serializers import job_summary
from mcp_server.user_context import get_mcp_user_id

from app.models.competitor_intelligence import ProductPermission, ProductPermissionLevel


@mcp.tool()
def product_list() -> dict:
    """List all products available for analysis."""
    from app.models.competitor_intelligence import ProductCompetitor
    from app.models.idea import Idea
    from sqlalchemy import func

    with get_session() as db:
        products = get_permitted_products(db)
        result = []
        for p in products:
            competitor_count = db.query(func.count(ProductCompetitor.id)).filter(
                ProductCompetitor.product_id == p.id
            ).scalar() or 0
            idea_count = db.query(func.count(Idea.id)).filter(
                Idea.product_id == p.id, Idea.is_active == True
            ).scalar() or 0
            result.append({
                "product_id": p.id,
                "product_name": p.product_name,
                "product_category": p.product_category,
                "competitor_count": competitor_count,
                "idea_count": idea_count,
                "status": p.status,
            })
        return {"products": result}


@mcp.tool()
def product_get_context(product_id: int) -> dict:
    """Get full context about a product including its features, positioning, and analysis history."""
    from app.models.competitor_intelligence import CIProduct, ProductFeature
    from app.models.synthesis import SynthesisReport
    from sqlalchemy import desc

    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

        product = db.query(CIProduct).get(product_id)
        if not product:
            return {"error": f"Product {product_id} not found"}

        features = db.query(ProductFeature).filter(
            ProductFeature.product_id == product_id,
            ProductFeature.status == "active",
        ).all()

        latest_report = (
            db.query(SynthesisReport)
            .filter(SynthesisReport.product_id == product_id)
            .order_by(desc(SynthesisReport.report_version))
            .first()
        )

        return {
            "product_id": product.id,
            "product_name": product.product_name,
            "product_description": product.product_description,
            "product_category": product.product_category,
            "structured_product_data": product.structured_product_data,
            "features": [
                {"id": f.id, "name": f.feature_name, "description": f.feature_description}
                for f in features
            ],
            "last_synthesis_analysis": latest_report.generated_at.isoformat() if latest_report else None,
            "synthesis_version": latest_report.report_version if latest_report else None,
            "target_customer_profile": product.target_customer_profile,
            "job_map_version": product.job_map_version,
            "job_map_summary": f"{len(product.jobs)} jobs defined" if product.jobs else "No job map defined",
        }


@mcp.tool()
def product_create(name: str, description: str, category: str = "") -> dict:
    """Create a new product for analysis. The creator gets OWNER access.

    Args:
        name: Product name (must be unique).
        description: Product description (min 10 characters).
        category: Product category (e.g. "Project Management", "CRM"). Optional.
    """
    from app.models.competitor_intelligence import CIProduct

    if len(description) < 10:
        return {"error": "Description must be at least 10 characters."}

    user_id = get_mcp_user_id()

    with get_session() as db:
        # Check for duplicate name
        existing = db.query(CIProduct).filter(CIProduct.product_name == name).first()
        if existing:
            return {"error": f"Product '{name}' already exists (id={existing.id})."}

        product = CIProduct(
            product_name=name,
            product_description=description,
            product_category=category or None,
            created_by_user_id=user_id or None,
            last_modified_by_user_id=user_id or None,
            analysis_version=0,
            analysis_count=0,
            status="active",
        )
        db.add(product)
        db.flush()

        return {
            "product_id": product.id,
            "product_name": product.product_name,
            "product_category": product.product_category,
            "status": "active",
            "message": f"Product '{name}' created. Run product_run_analysis to analyze with AI.",
        }


@mcp.tool()
def product_update(product_id: int, name: str = "", description: str = "", category: str = "") -> dict:
    """Update product metadata. Only provided fields are changed.

    Args:
        product_id: The product to update.
        name: New product name (leave empty to keep current).
        description: New description (leave empty to keep current).
        category: New category (leave empty to keep current).
    """
    from app.models.competitor_intelligence import CIProduct

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.EDIT)
        if denied:
            return denied

        product = db.query(CIProduct).get(product_id)
        if not product:
            return {"error": f"Product {product_id} not found"}

        if name:
            # Check for duplicate
            existing = db.query(CIProduct).filter(
                CIProduct.product_name == name, CIProduct.id != product_id
            ).first()
            if existing:
                return {"error": f"Product '{name}' already exists."}
            product.product_name = name
        if description:
            product.product_description = description
        if category:
            product.product_category = category

        user_id = get_mcp_user_id()
        if user_id:
            product.last_modified_by_user_id = user_id

        db.flush()

        return {
            "product_id": product.id,
            "product_name": product.product_name,
            "product_description": product.product_description[:200],
            "product_category": product.product_category,
            "message": "Product updated.",
        }


@mcp.tool()
def product_delete(product_id: int) -> dict:
    """Delete a product and all associated data (competitors, ideas, reports, embeddings). This is irreversible.

    Args:
        product_id: The product to delete. Requires OWNER access.
    """
    from app.services.product_service import ProductService

    user_id = get_mcp_user_id()

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.OWNER)
        if denied:
            return denied

        svc = ProductService(db)
        # Get preview first
        preview = svc.get_delete_preview(product_id)
        if preview is None:
            return {"error": f"Product {product_id} not found"}

        try:
            svc.delete_product(product_id, user_id=user_id)
        except PermissionError:
            return {"error": "Permission denied: OWNER access required."}

        return {
            "product_id": product_id,
            "deleted": True,
            "deleted_counts": preview.get("will_delete", {}),
            "message": f"Product '{preview['product']['name']}' and all associated data deleted.",
        }


@mcp.tool()
def product_get_scoring_weights(product_id: int) -> dict:
    """Get the current scoring weights for opportunity synthesis, including defaults and any custom overrides.

    Args:
        product_id: The product to get scoring weights for.
    """
    from app.models.competitor_intelligence import CIProduct
    from app.services.scoring_defaults import get_weights_for_product, DEFAULT_SCORING_WEIGHTS, VOTE_THRESHOLDS

    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

        product = db.query(CIProduct).get(product_id)
        if not product:
            return {"error": f"Product {product_id} not found"}

        effective = get_weights_for_product(product)

        return {
            "product_id": product_id,
            "effective_weights": effective,
            "has_custom_weights": bool(product.scoring_weights),
            "custom_overrides": product.scoring_weights,
            "defaults": DEFAULT_SCORING_WEIGHTS,
            "vote_thresholds": VOTE_THRESHOLDS,
        }


@mcp.tool()
def product_update_scoring(product_id: int, weights_json: str) -> dict:
    """Update scoring weights for opportunity synthesis. Pass a JSON object with weight overrides. Omitted keys keep their defaults. Pass '{}' to reset to defaults.

    Args:
        product_id: The product to update scoring weights for.
        weights_json: JSON string of weight overrides. Valid keys: source_count, competitive_prevalence, customer_votes, internal_signal, evidence_research, confidence_bonus. Example: '{"source_count": {"four": 60, "three": 45}}'
    """
    from app.models.competitor_intelligence import CIProduct
    from app.services.scoring_defaults import get_weights_for_product, DEFAULT_SCORING_WEIGHTS

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.EDIT)
        if denied:
            return denied

        try:
            overrides = json.loads(weights_json) if weights_json else {}
        except json.JSONDecodeError:
            return {"error": "Invalid JSON. Provide a valid JSON object with weight overrides."}

        if not isinstance(overrides, dict):
            return {"error": "Weights must be a JSON object, not a list or scalar."}

        # Validate keys
        valid_keys = set(DEFAULT_SCORING_WEIGHTS.keys())
        invalid_keys = set(overrides.keys()) - valid_keys
        if invalid_keys:
            return {"error": f"Invalid weight keys: {sorted(invalid_keys)}. Valid keys: {sorted(valid_keys)}"}

        product = db.query(CIProduct).get(product_id)
        if not product:
            return {"error": f"Product {product_id} not found"}

        product.scoring_weights = overrides if overrides else None
        db.flush()

        effective = get_weights_for_product(product)

        return {
            "product_id": product_id,
            "has_custom_weights": bool(overrides),
            "custom_overrides": overrides if overrides else None,
            "effective_weights": effective,
        }


@mcp.tool()
def product_search_features(product_id: int, query: str) -> dict:
    """Semantic search across a product's own features."""
    from app.services.embedding_service import generate_embedding
    from app.services.vector_service import VectorService

    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied
        not_ready = require_product_analyzed(db, product_id)
        if not_ready:
            return not_ready

        query_emb = generate_embedding(query, input_type="query")
        matches = VectorService.find_similar_product_features(
            db, query_emb, product_id, limit=5
        )
        return {
            "query": query,
            "matches": [
                {
                    "feature_id": m[0],
                    "feature_name": m[1],
                    "feature_description": m[2],
                    "similarity": round(float(m[3]), 3) if len(m) > 3 else None,
                }
                for m in matches
            ],
        }


@mcp.tool()
def product_get_analysis_history(product_id: int, limit: int = 10) -> dict:
    """Get the history of AI analyses for a product, showing how the product understanding has evolved.

    Args:
        product_id: The product to get analysis history for.
        limit: Maximum number of history entries (default 10).
    """
    from app.models.competitor_intelligence import ProductAnalysisHistory

    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

        entries = (
            db.query(ProductAnalysisHistory)
            .filter(ProductAnalysisHistory.product_id == product_id)
            .order_by(ProductAnalysisHistory.analysis_version.desc())
            .limit(limit)
            .all()
        )

        return {
            "product_id": product_id,
            "count": len(entries),
            "history": [
                {
                    "id": e.id,
                    "analysis_version": e.analysis_version,
                    "product_description": e.product_description[:200] if e.product_description else None,
                    "source_type": e.product_source_type,
                    "tokens_used": e.tokens_used,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in entries
            ],
        }


@mcp.tool()
def product_run_analysis(
    product_id: int,
    source_url: str = "",
    web_research: bool = True,
    source_urls: list[str] | None = None,
) -> dict:
    """Queue an AI analysis of a product. By default, supplements provided data with web research (searches for features, pricing, integrations, reviews). Set web_research=false to skip Brave and rely on training knowledge + provided sources.

    Full competitive-analysis workflow: this is step 1 of 4. After this job
    completes: (2) ci_run_discovery to discover competitors (poll with
    job_get_status; output_data includes competitor_names); (3)
    ci_run_competitor_audit for EACH discovered competitor; (4)
    synthesis_run_unified to synthesize opportunities across all sources.
    Use ci_get_competitor_list at any point to see competitor status.

    Args:
        product_id: The product to analyze.
        source_url: Optional single URL to fetch as the primary product description (e.g. product homepage). Extracted text replaces the stored product_description for this run.
        web_research: Search the web for additional product information (default true). Set false to skip Brave search and rely on training knowledge + any provided source pages.
        source_urls: Optional list of additional pages (max 5) the agent should use as authoritative context — feature pages, pricing, docs, etc. Complements source_url (which replaces the description). Fetched server-side and passed to the agent as '## Fetched Source Pages'.
    """
    from app.models.competitor_intelligence import CIProduct
    from app.models.queue import JobType
    from app.services.queue_service import QueueService
    from app.services.scoped_input_validator import validate_scoped_inputs, ScopedInputError

    try:
        source_urls = validate_scoped_inputs(source_urls)
    except ScopedInputError as err:
        return err.payload

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.EDIT)
        if denied:
            return denied

        # Check for active analysis job
        conflict = require_no_active_job(db, product_id, JobType.PRODUCT_ANALYSIS, "Product analysis")
        if conflict:
            return conflict

        product = db.query(CIProduct).get(product_id)
        if not product:
            return {"error": f"Product {product_id} not found"}

        # Validate there's enough data to analyze
        if not source_url and len(product.product_description or "") < 50:
            return {
                "error": "Product description is too short for meaningful analysis. "
                         "Either provide a source_url or update the product with a detailed description first.",
            }

        input_data = {
            "product_id": product_id,
            "web_research_enabled": web_research,
            "source_urls": source_urls,
        }
        source_type = "text"
        source_data = None

        if source_url:
            # Fetch URL content inline
            try:
                from app.services.document_parsing_service import DocumentParsingService
                fetch_result = DocumentParsingService().fetch_url_content(source_url)
                source_type = "url"
                source_data = {"url": source_url, "title": fetch_result.get("title", "")}
                input_data["product_description"] = fetch_result.get("extracted_text", product.product_description)
                input_data["source_type"] = source_type
                input_data["source_data"] = source_data
            except Exception as e:
                return {"error": f"Failed to fetch URL: {e}"}
        else:
            input_data["product_description"] = product.product_description
            input_data["source_type"] = source_type

        queue_service = QueueService(db)
        job = queue_service.create_job(
            job_type=JobType.PRODUCT_ANALYSIS,
            input_data=input_data,
            product_id=product_id,
            user_id=resolve_user_id_for_job(db, product_id),
        )

        from app.queue.product_tasks import analyze_product_task
        from mcp_server.db import dispatch_task
        result = dispatch_task(analyze_product_task, job.id)
        queue_service.mark_queued(job.id, result.id)

        return {
            "job_id": job.id,
            "job_uuid": job.job_uuid,
            "source_type": source_type,
            "source_url": source_url or None,
            "status": "queued",
            "message": "Product analysis queued (step 1 of the full workflow). Poll with job_get_status; "
                       "then ci_run_discovery -> ci_run_competitor_audit per competitor -> synthesis_run_unified.",
        }


@mcp.tool()
def product_fetch_url(url: str) -> dict:
    """Fetch and extract text content from a URL. Useful for getting product information before creating or analyzing a product.

    Args:
        url: The URL to fetch (must be http or https).
    """
    from app.services.document_parsing_service import DocumentParsingService

    if not url.startswith(("http://", "https://")):
        return {"error": "URL must start with http:// or https://"}

    try:
        result = DocumentParsingService().fetch_url_content(url)
        return {
            "url": result.get("url", url),
            "title": result.get("title", ""),
            "extracted_text": result.get("extracted_text", "")[:5000],
            "token_estimate": result.get("token_estimate", 0),
            "message": "Content extracted. Use this text when creating or analyzing a product.",
        }
    except Exception as e:
        return {"error": f"Failed to fetch URL: {e}"}


@mcp.tool()
def product_get_jobs(product_id: int, limit: int = 10) -> dict:
    """List recent background jobs for a product (analysis, discovery, audits, synthesis).

    Args:
        product_id: The product to list jobs for.
        limit: Maximum number of jobs (default 10).
    """
    from app.services.queue_service import QueueService

    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

        queue_service = QueueService(db)
        jobs = queue_service.get_jobs_for_product(product_id, limit=limit)

        return {
            "product_id": product_id,
            "count": len(jobs),
            "jobs": [job_summary(j) for j in jobs],
        }


@mcp.tool()
def product_get_triage_settings(product_id: int) -> dict:
    """Get auto-triage configuration for a product (whether ideas are automatically responded to and the confidence threshold).

    Args:
        product_id: The product to get triage settings for.
    """
    from app.models.competitor_intelligence import CIProduct

    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

        product = db.query(CIProduct).get(product_id)
        if not product:
            return {"error": f"Product {product_id} not found"}

        return {
            "product_id": product_id,
            "auto_enabled": product.idea_triage_auto_enabled,
            "auto_threshold": float(product.idea_triage_auto_threshold),
        }


@mcp.tool()
def product_update_triage_settings(
    product_id: int, auto_enabled: bool = None, auto_threshold: float = None
) -> dict:
    """Configure auto-triage behavior for customer ideas.

    Args:
        product_id: The product to configure.
        auto_enabled: Enable (true) or disable (false) automatic triage responses.
        auto_threshold: Confidence threshold (0.0-1.0) for auto-responses. Higher = more conservative.
    """
    from app.models.competitor_intelligence import CIProduct

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.EDIT)
        if denied:
            return denied

        product = db.query(CIProduct).get(product_id)
        if not product:
            return {"error": f"Product {product_id} not found"}

        if auto_enabled is not None:
            product.idea_triage_auto_enabled = auto_enabled
        if auto_threshold is not None:
            if not 0.0 <= auto_threshold <= 1.0:
                return {"error": "auto_threshold must be between 0.0 and 1.0"}
            product.idea_triage_auto_threshold = auto_threshold

        db.flush()

        return {
            "product_id": product_id,
            "auto_enabled": product.idea_triage_auto_enabled,
            "auto_threshold": float(product.idea_triage_auto_threshold),
            "message": "Triage settings updated.",
        }


@mcp.tool()
def product_get_agent_schedule(product_id: int) -> dict:
    """Get the automation SCHEDULE for background agent runs — when product analysis, competitor discovery, and deep analysis run automatically.

    NOT the competitor-change monitoring/alerting settings; for those (and
    "is monitoring enabled?") use monitoring_get_config.

    Args:
        product_id: The product to get the agent schedule for.
    """
    from app.models.competitive_agent import CompetitiveAgentConfig

    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

        config = db.query(CompetitiveAgentConfig).filter(
            CompetitiveAgentConfig.product_id == product_id
        ).first()

        if not config:
            return {
                "product_id": product_id,
                "configured": False,
                "message": "No agent schedule exists. Use product_update_agent_schedule to create one.",
            }

        return {
            "product_id": product_id,
            "configured": True,
            "enabled": config.enabled,
            "product_analysis_mode": config.product_analysis_mode.value if config.product_analysis_mode else "manual",
            "product_analysis_schedule": config.product_analysis_schedule,
            "product_analysis_last_run": config.product_analysis_last_run.isoformat() if config.product_analysis_last_run else None,
            "competitor_discovery_mode": config.competitor_discovery_mode.value if config.competitor_discovery_mode else "manual",
            "competitor_discovery_schedule": config.competitor_discovery_schedule,
            "competitor_discovery_last_run": config.competitor_discovery_last_run.isoformat() if config.competitor_discovery_last_run else None,
            "alert_on_new_competitors": config.alert_on_new_competitors,
            "alert_on_disappeared_competitors": config.alert_on_disappeared_competitors,
            "deep_analysis_mode": config.deep_analysis_mode.value if config.deep_analysis_mode else "manual",
            "deep_analysis_schedule": config.deep_analysis_schedule,
            "deep_analysis_last_run": config.deep_analysis_last_run.isoformat() if config.deep_analysis_last_run else None,
        }


@mcp.tool()
def product_update_agent_schedule(
    product_id: int,
    enabled: bool = None,
    product_analysis_mode: str = "",
    product_analysis_schedule: str = "",
    competitor_discovery_mode: str = "",
    competitor_discovery_schedule: str = "",
    alert_on_new_competitors: bool = None,
    alert_on_disappeared_competitors: bool = None,
    deep_analysis_mode: str = "",
    deep_analysis_schedule: str = "",
) -> dict:
    """Update the automation SCHEDULE for background agent runs. Only provided fields are changed.

    NOT the competitor-change monitoring/alerting settings; for those use
    monitoring_update_config.

    Args:
        product_id: The product to configure.
        enabled: Enable or disable the competitive agent entirely.
        product_analysis_mode: "manual" or "scheduled".
        product_analysis_schedule: "daily", "weekly", or "monthly" (when mode is scheduled).
        competitor_discovery_mode: "manual" or "scheduled".
        competitor_discovery_schedule: "daily", "weekly", or "monthly".
        alert_on_new_competitors: Alert when new competitors are discovered. This flag (not the monitoring-config one) governs discovery-run alerts.
        alert_on_disappeared_competitors: Alert when competitors disappear.
        deep_analysis_mode: "manual" or "scheduled".
        deep_analysis_schedule: "daily", "weekly", or "monthly".
    """
    from app.models.competitive_agent import CompetitiveAgentConfig, AgentMode

    valid_modes = {"manual", "scheduled"}
    valid_schedules = {"daily", "weekly", "monthly"}

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.EDIT)
        if denied:
            return denied

        # Get or create config
        config = db.query(CompetitiveAgentConfig).filter(
            CompetitiveAgentConfig.product_id == product_id
        ).first()
        if not config:
            config = CompetitiveAgentConfig(product_id=product_id)
            db.add(config)
            db.flush()

        # Apply updates
        if enabled is not None:
            config.enabled = enabled

        if product_analysis_mode:
            if product_analysis_mode not in valid_modes:
                return {"error": f"Invalid mode '{product_analysis_mode}'. Must be: {sorted(valid_modes)}"}
            config.product_analysis_mode = AgentMode(product_analysis_mode)
        if product_analysis_schedule:
            if product_analysis_schedule not in valid_schedules:
                return {"error": f"Invalid schedule '{product_analysis_schedule}'. Must be: {sorted(valid_schedules)}"}
            config.product_analysis_schedule = product_analysis_schedule

        if competitor_discovery_mode:
            if competitor_discovery_mode not in valid_modes:
                return {"error": f"Invalid mode '{competitor_discovery_mode}'. Must be: {sorted(valid_modes)}"}
            config.competitor_discovery_mode = AgentMode(competitor_discovery_mode)
        if competitor_discovery_schedule:
            if competitor_discovery_schedule not in valid_schedules:
                return {"error": f"Invalid schedule '{competitor_discovery_schedule}'. Must be: {sorted(valid_schedules)}"}
            config.competitor_discovery_schedule = competitor_discovery_schedule

        if alert_on_new_competitors is not None:
            config.alert_on_new_competitors = alert_on_new_competitors
        if alert_on_disappeared_competitors is not None:
            config.alert_on_disappeared_competitors = alert_on_disappeared_competitors

        if deep_analysis_mode:
            if deep_analysis_mode not in valid_modes:
                return {"error": f"Invalid mode '{deep_analysis_mode}'. Must be: {sorted(valid_modes)}"}
            config.deep_analysis_mode = AgentMode(deep_analysis_mode)
        if deep_analysis_schedule:
            if deep_analysis_schedule not in valid_schedules:
                return {"error": f"Invalid schedule '{deep_analysis_schedule}'. Must be: {sorted(valid_schedules)}"}
            config.deep_analysis_schedule = deep_analysis_schedule

        db.flush()

        return {
            "product_id": product_id,
            "configured": True,
            "enabled": config.enabled,
            "product_analysis_mode": config.product_analysis_mode.value if config.product_analysis_mode else "manual",
            "product_analysis_schedule": config.product_analysis_schedule,
            "competitor_discovery_mode": config.competitor_discovery_mode.value if config.competitor_discovery_mode else "manual",
            "competitor_discovery_schedule": config.competitor_discovery_schedule,
            "alert_on_new_competitors": config.alert_on_new_competitors,
            "alert_on_disappeared_competitors": config.alert_on_disappeared_competitors,
            "deep_analysis_mode": config.deep_analysis_mode.value if config.deep_analysis_mode else "manual",
            "deep_analysis_schedule": config.deep_analysis_schedule,
            "message": "Agent config updated.",
        }


@mcp.tool()
def product_create_invite(product_id: int, max_uses: int = 0) -> dict:
    """Create an invite code for a product so voters can self-register. Returns the invite code.

    Invite codes always grant VIEW permission. Use the sharing UI or member management
    endpoints to grant higher permission levels to specific users.

    Args:
        product_id: The product to create an invite for.
        max_uses: Maximum number of times this code can be redeemed (0 = unlimited).
    """
    from app.models.product_invite import ProductInviteCode

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.OWNER)
        if denied:
            return denied

        invite = ProductInviteCode(
            product_id=product_id,
            code=ProductInviteCode.generate_code(),
            created_by_user_id=resolve_user_id_for_job(db, product_id),
            max_uses=max_uses if max_uses > 0 else None,
            permission_level=ProductPermissionLevel.VIEW,
        )
        db.add(invite)
        db.flush()

        return {
            "invite_id": invite.id,
            "product_id": product_id,
            "code": invite.code,
            "invite_url": f"/join/{invite.code}",
            "max_uses": invite.max_uses,
            "permission_level": invite.permission_level.value,
            "message": f"Invite code created: {invite.code}",
        }


@mcp.tool()
def product_list_invites(product_id: int) -> dict:
    """List all invite codes for a product with usage stats.

    Args:
        product_id: The product to list invites for.
    """
    from app.models.product_invite import ProductInviteCode

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.OWNER)
        if denied:
            return denied

        codes = db.query(ProductInviteCode).filter(
            ProductInviteCode.product_id == product_id
        ).order_by(ProductInviteCode.created_at.desc()).all()

        return {
            "product_id": product_id,
            "invites": [
                {
                    "invite_id": c.id,
                    "code": c.code,
                    "invite_url": f"/join/{c.code}",
                    "max_uses": c.max_uses,
                    "current_uses": c.current_uses,
                    "permission_level": c.permission_level.value,
                    "is_active": c.is_active,
                    "expires_at": c.expires_at.isoformat() if c.expires_at else None,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                }
                for c in codes
            ],
        }


@mcp.tool()
def product_list_members(product_id: int) -> dict:
    """List all users with access to a product and their permission levels.

    Args:
        product_id: The product to list members for.
    """
    from app.models.user import User

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.OWNER)
        if denied:
            return denied

        permissions = db.query(ProductPermission, User).join(
            User, ProductPermission.user_id == User.id
        ).filter(
            ProductPermission.product_id == product_id
        ).all()

        return {
            "product_id": product_id,
            "members": [
                {
                    "user_id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "permission_level": perm.permission_level.value,
                    "granted_at": perm.granted_at.isoformat() if perm.granted_at else None,
                }
                for perm, user in permissions
            ],
        }


# ---------------------------------------------------------------------------
# Job Map tools — JTBD management
# ---------------------------------------------------------------------------


def _rebuild_job_map_json(db, product):
    """Rebuild CIProduct.job_map JSON from ProductJob records."""
    from app.models.competitor_intelligence import ProductJob

    jobs = db.query(ProductJob).filter(
        ProductJob.product_id == product.id,
        ProductJob.status == "active"
    ).all()

    job_map = product.job_map or {}
    functional = []
    emotional = []
    social = []

    for j in jobs:
        entry = {
            "job_id": j.job_id_key,
            "job_type": j.job_type.value,
            "statement": j.statement,
            "desired_outcomes": j.desired_outcomes or [],
            "importance": j.importance.value,
        }
        if j.job_type.value == "functional":
            functional.append(entry)
        elif j.job_type.value == "emotional":
            emotional.append(entry)
        else:
            social.append(entry)

    job_map["functional_jobs"] = functional
    job_map["emotional_jobs"] = emotional
    job_map["social_jobs"] = social
    product.job_map = job_map


@mcp.tool()
def product_extract_job_map(product_id: int, guidance: str = "") -> dict:
    """Queue the JobMapExtractorAgent to generate a JTBD job map from product information. Returns a job_id for polling.

    Args:
        product_id: The product to extract a job map for.
        guidance: Optional guidance for the extraction (e.g. target customer hints, focus areas).
    """
    from app.models.competitor_intelligence import CIProduct
    from app.models.queue import JobType as QueueJobType
    from app.services.queue_service import QueueService

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.EDIT)
        if denied:
            return denied

        conflict = require_no_active_job(db, product_id, QueueJobType.JOB_MAP_EXTRACTION, "Job map extraction")
        if conflict:
            return conflict

        product = db.query(CIProduct).get(product_id)
        if not product:
            return {"error": f"Product {product_id} not found"}

        # MCP always commits directly — no pending review state for programmatic use
        input_data = {"product_id": product_id, "skip_review": True}
        if guidance:
            input_data["guidance"] = guidance

        queue_service = QueueService(db)
        job = queue_service.create_job(
            job_type=QueueJobType.JOB_MAP_EXTRACTION,
            input_data=input_data,
            product_id=product_id,
            user_id=resolve_user_id_for_job(db, product_id),
        )

        from app.queue.jtbd_tasks import extract_job_map_task
        from mcp_server.db import dispatch_task
        result = dispatch_task(extract_job_map_task, job.id)
        queue_service.mark_queued(job.id, result.id)

        return {
            "job_id": job.id,
            "job_uuid": job.job_uuid,
            "status": "queued",
            "message": "Job map extraction queued. Use job_get_status to check progress.",
        }


@mcp.tool()
def product_get_job_map(product_id: int) -> dict:
    """Get the current JTBD job map including target customer profile and all jobs.

    Args:
        product_id: The product to get the job map for.
    """
    from app.models.competitor_intelligence import CIProduct, ProductJob

    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

        product = db.query(CIProduct).get(product_id)
        if not product:
            return {"error": f"Product {product_id} not found"}

        jobs = db.query(ProductJob).filter(
            ProductJob.product_id == product_id,
            ProductJob.status == "active",
        ).all()

        return {
            "product_id": product_id,
            "target_customer_profile": product.target_customer_profile,
            "job_map": product.job_map,
            "job_map_version": product.job_map_version,
            "job_map_last_updated": product.job_map_last_updated.isoformat() if product.job_map_last_updated else None,
            "jobs": [
                {
                    "id": j.id,
                    "job_id_key": j.job_id_key,
                    "job_type": j.job_type.value,
                    "statement": j.statement,
                    "desired_outcomes": j.desired_outcomes or [],
                    "importance": j.importance.value,
                    "has_embedding": j.statement_embedding is not None,
                }
                for j in jobs
            ],
        }


@mcp.tool()
def product_set_job_map(product_id: int, job_map_json: str) -> dict:
    """Set or replace the full JTBD job map from a JSON string. Deletes existing jobs and creates new ones.

    Args:
        product_id: The product to set the job map for.
        job_map_json: JSON string with the job map structure. Must have keys: main_job, functional_jobs, emotional_jobs, social_jobs. Each job needs: job_id, job_type, statement, desired_outcomes (list), importance.
    """
    from datetime import datetime
    from app.models.competitor_intelligence import CIProduct, ProductJob, JobType as JTBDJobType, JobImportance

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.EDIT)
        if denied:
            return denied

        try:
            job_map_data = json.loads(job_map_json)
        except json.JSONDecodeError:
            return {"error": "Invalid JSON. Provide a valid job map JSON object."}

        if not isinstance(job_map_data, dict):
            return {"error": "Job map must be a JSON object."}

        product = db.query(CIProduct).get(product_id)
        if not product:
            return {"error": f"Product {product_id} not found"}

        # Delete existing jobs
        db.query(ProductJob).filter(ProductJob.product_id == product_id).delete()

        # Collect all job entries from the map
        all_jobs = []
        for category in ["functional_jobs", "emotional_jobs", "social_jobs"]:
            for entry in job_map_data.get(category, []):
                all_jobs.append(entry)

        # Generate embeddings for all statements
        statements = [j["statement"] for j in all_jobs]
        embeddings = []
        if statements:
            from app.services.embedding_service import generate_embeddings_batch
            embeddings = generate_embeddings_batch(statements, input_type="document")

        # Create ProductJob records
        created_count = 0
        for i, entry in enumerate(all_jobs):
            job_type_val = entry.get("job_type", "functional")
            importance_val = entry.get("importance", "medium")
            pj = ProductJob(
                product_id=product_id,
                job_id_key=entry["job_id"],
                job_type=JTBDJobType(job_type_val),
                statement=entry["statement"],
                desired_outcomes=entry.get("desired_outcomes", []),
                importance=JobImportance(importance_val),
                statement_embedding=embeddings[i] if i < len(embeddings) else None,
            )
            db.add(pj)
            created_count += 1

        # Update product
        product.job_map = job_map_data
        product.job_map_version = (product.job_map_version or 0) + 1
        product.job_map_last_updated = datetime.utcnow()
        db.flush()

        return {
            "product_id": product_id,
            "job_map_version": product.job_map_version,
            "jobs_created": created_count,
            "message": f"Job map set with {created_count} jobs. Version {product.job_map_version}.",
        }


@mcp.tool()
def product_set_target_customer(
    product_id: int,
    persona_name: str,
    company_characteristics: str = "",
    key_traits_json: str = "[]",
    hiring_criteria: str = "",
) -> dict:
    """Set the target customer profile for a product.

    Args:
        product_id: The product to set the target customer for.
        persona_name: Name for the persona, e.g. 'Mid-market Operations Director'.
        company_characteristics: Company size, industry, stage (optional).
        key_traits_json: JSON array of key behavioral traits (optional). Example: '["Budget-conscious", "Risk-averse"]'
        hiring_criteria: What would make them 'hire' this product (optional).
    """
    from app.models.competitor_intelligence import CIProduct

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.EDIT)
        if denied:
            return denied

        product = db.query(CIProduct).get(product_id)
        if not product:
            return {"error": f"Product {product_id} not found"}

        try:
            key_traits = json.loads(key_traits_json) if key_traits_json else []
        except json.JSONDecodeError:
            return {"error": "Invalid JSON for key_traits_json. Provide a JSON array."}

        if not isinstance(key_traits, list):
            return {"error": "key_traits_json must be a JSON array."}

        profile = {
            "persona_name": persona_name,
            "company_characteristics": company_characteristics or None,
            "key_traits": key_traits,
            "hiring_criteria": hiring_criteria or None,
        }
        product.target_customer_profile = profile
        db.flush()

        return {
            "product_id": product_id,
            "target_customer_profile": profile,
            "message": f"Target customer profile set: {persona_name}",
        }


@mcp.tool()
def product_add_job(
    product_id: int,
    job_id: str,
    statement: str,
    desired_outcomes_json: str = "[]",
    importance: str = "medium",
    job_type: str = "functional",
) -> dict:
    """Add a single job to the product's JTBD job map.

    Args:
        product_id: The product to add the job to.
        job_id: Unique key for this job within the product (e.g. 'j1', 'j2', 'j3').
        statement: Job statement, ideally: 'When [situation], I want to [action], so I can [outcome]'.
        job_type: One of: functional, emotional, social (default: functional).
        desired_outcomes_json: JSON array of desired outcome strings (optional).
        importance: One of: critical, high, medium, low (default medium).
    """
    from datetime import datetime
    from app.models.competitor_intelligence import CIProduct, ProductJob, JobType as JTBDJobType, JobImportance

    valid_types = {"functional", "emotional", "social"}
    valid_importance = {"critical", "high", "medium", "low"}

    if job_type not in valid_types:
        return {"error": f"Invalid job_type '{job_type}'. Must be one of: {sorted(valid_types)}"}
    if importance not in valid_importance:
        return {"error": f"Invalid importance '{importance}'. Must be one of: {sorted(valid_importance)}"}

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.EDIT)
        if denied:
            return denied

        product = db.query(CIProduct).get(product_id)
        if not product:
            return {"error": f"Product {product_id} not found"}

        # Check uniqueness
        existing = db.query(ProductJob).filter(
            ProductJob.product_id == product_id,
            ProductJob.job_id_key == job_id,
        ).first()
        if existing:
            return {"error": f"Job '{job_id}' already exists for this product. Use product_edit_job to modify it."}

        try:
            desired_outcomes = json.loads(desired_outcomes_json) if desired_outcomes_json else []
        except json.JSONDecodeError:
            return {"error": "Invalid JSON for desired_outcomes_json. Provide a JSON array."}

        # Generate embedding
        from app.services.embedding_service import generate_embedding
        embedding = generate_embedding(statement, input_type="document")

        pj = ProductJob(
            product_id=product_id,
            job_id_key=job_id,
            job_type=JTBDJobType(job_type),
            statement=statement,
            desired_outcomes=desired_outcomes,
            importance=JobImportance(importance),
            statement_embedding=embedding,
        )
        db.add(pj)
        db.flush()

        # Rebuild job_map JSON and increment version
        _rebuild_job_map_json(db, product)
        product.job_map_version = (product.job_map_version or 0) + 1
        product.job_map_last_updated = datetime.utcnow()
        db.flush()

        return {
            "product_id": product_id,
            "job_id": pj.id,
            "job_id_key": pj.job_id_key,
            "job_type": pj.job_type.value,
            "statement": pj.statement,
            "importance": pj.importance.value,
            "job_map_version": product.job_map_version,
            "message": f"Job '{job_id}' added to the map.",
        }


@mcp.tool()
def product_edit_job(
    product_id: int,
    job_id: str,
    statement: str = "",
    desired_outcomes_json: str = "",
    importance: str = "",
) -> dict:
    """Edit a single job in the product's JTBD job map (partial update — only provided fields are changed).

    Args:
        product_id: The product the job belongs to.
        job_id: The job_id_key of the job to edit.
        statement: New job statement (leave empty to keep current).
        desired_outcomes_json: New desired outcomes JSON array (leave empty to keep current).
        importance: New importance level: critical, high, medium, low (leave empty to keep current).
    """
    from datetime import datetime
    from app.models.competitor_intelligence import CIProduct, ProductJob, JobImportance

    valid_importance = {"critical", "high", "medium", "low"}

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.EDIT)
        if denied:
            return denied

        product = db.query(CIProduct).get(product_id)
        if not product:
            return {"error": f"Product {product_id} not found"}

        pj = db.query(ProductJob).filter(
            ProductJob.product_id == product_id,
            ProductJob.job_id_key == job_id,
        ).first()
        if not pj:
            return {"error": f"Job '{job_id}' not found for product {product_id}."}

        if statement:
            pj.statement = statement
            # Regenerate embedding
            from app.services.embedding_service import generate_embedding
            pj.statement_embedding = generate_embedding(statement, input_type="document")

        if desired_outcomes_json:
            try:
                pj.desired_outcomes = json.loads(desired_outcomes_json)
            except json.JSONDecodeError:
                return {"error": "Invalid JSON for desired_outcomes_json."}

        if importance:
            if importance not in valid_importance:
                return {"error": f"Invalid importance '{importance}'. Must be one of: {sorted(valid_importance)}"}
            pj.importance = JobImportance(importance)

        db.flush()

        # Rebuild job_map JSON and increment version
        _rebuild_job_map_json(db, product)
        product.job_map_version = (product.job_map_version or 0) + 1
        product.job_map_last_updated = datetime.utcnow()
        db.flush()

        return {
            "product_id": product_id,
            "job_id_key": pj.job_id_key,
            "job_type": pj.job_type.value,
            "statement": pj.statement,
            "desired_outcomes": pj.desired_outcomes or [],
            "importance": pj.importance.value,
            "job_map_version": product.job_map_version,
            "message": f"Job '{job_id}' updated.",
        }


@mcp.tool()
def product_remove_job(product_id: int, job_id: str) -> dict:
    """Remove a job from the product's JTBD job map.

    Args:
        product_id: The product the job belongs to.
        job_id: The job_id_key of the job to remove.
    """
    from datetime import datetime
    from app.models.competitor_intelligence import CIProduct, ProductJob

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.EDIT)
        if denied:
            return denied

        product = db.query(CIProduct).get(product_id)
        if not product:
            return {"error": f"Product {product_id} not found"}

        pj = db.query(ProductJob).filter(
            ProductJob.product_id == product_id,
            ProductJob.job_id_key == job_id,
        ).first()
        if not pj:
            return {"error": f"Job '{job_id}' not found for product {product_id}."}

        db.delete(pj)
        db.flush()

        # Rebuild job_map JSON and increment version
        _rebuild_job_map_json(db, product)
        product.job_map_version = (product.job_map_version or 0) + 1
        product.job_map_last_updated = datetime.utcnow()
        db.flush()

        return {
            "product_id": product_id,
            "removed_job_id": job_id,
            "job_map_version": product.job_map_version,
            "message": f"Job '{job_id}' removed from the map.",
        }
