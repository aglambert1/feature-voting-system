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
from mcp_server.user_context import get_mcp_user_id

from app.models.competitor_intelligence import ProductPermissionLevel


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
    from app.models.competitive_reports import LandscapeOpportunityReport

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

        landscape = db.query(LandscapeOpportunityReport).filter(
            LandscapeOpportunityReport.product_id == product_id
        ).first()

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
            "last_landscape_analysis": landscape.generated_at.isoformat() if landscape else None,
            "landscape_version": landscape.report_version if landscape else None,
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
def product_run_analysis(product_id: int, source_url: str = "") -> dict:
    """Queue an AI analysis of a product. Optionally provide a URL to fetch as source data. Returns a job ID.

    Args:
        product_id: The product to analyze.
        source_url: Optional URL to fetch content from for analysis (e.g. product homepage).
    """
    from app.models.competitor_intelligence import CIProduct
    from app.models.queue import JobType
    from app.services.queue_service import QueueService

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

        input_data = {"product_id": product_id}
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

        from app.queue.tasks import analyze_product_task
        from mcp_server.db import dispatch_task
        result = dispatch_task(analyze_product_task, job.id)
        queue_service.mark_queued(job.id, result.id)

        return {
            "job_id": job.id,
            "job_uuid": job.job_uuid,
            "source_type": source_type,
            "source_url": source_url or None,
            "status": "queued",
            "message": "Product analysis queued. Use job_get_status to check progress.",
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
            "jobs": [
                {
                    "job_id": j.id,
                    "job_uuid": j.job_uuid,
                    "job_type": j.job_type.value if j.job_type else None,
                    "status": j.status.value if j.status else None,
                    "progress_percent": j.progress_percent,
                    "progress_message": j.progress_message,
                    "created_at": j.created_at.isoformat() if j.created_at else None,
                    "completed_at": j.completed_at.isoformat() if j.completed_at else None,
                    "duration_seconds": j.duration_seconds,
                    "error_message": j.error_message,
                }
                for j in jobs
            ],
        }


@mcp.tool()
def product_full_analysis(product_id: int) -> dict:
    """Start a full analysis workflow by queuing a product analysis. After it completes, follow up with ci_run_discovery, then ci_run_competitor_audit for each competitor, then ci_run_analysis for landscape synthesis.

    Args:
        product_id: The product to analyze. Must have a detailed description (50+ characters).
    """
    from app.models.competitor_intelligence import CIProduct
    from app.models.queue import JobType
    from app.services.queue_service import QueueService

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.EDIT)
        if denied:
            return denied

        product = db.query(CIProduct).get(product_id)
        if not product:
            return {"error": f"Product {product_id} not found"}
        if len(product.product_description or "") < 50:
            return {
                "error": "Product description is too short for analysis. "
                         "Update the product with a detailed description or use product_run_analysis with a source_url first.",
            }

        conflict = require_no_active_job(db, product_id, JobType.PRODUCT_ANALYSIS, "Product analysis")
        if conflict:
            return conflict

        queue_service = QueueService(db)
        job = queue_service.create_job(
            job_type=JobType.PRODUCT_ANALYSIS,
            input_data={
                "product_id": product_id,
                "product_description": product.product_description,
                "source_type": product.product_source_type or "text",
            },
            product_id=product_id,
            user_id=resolve_user_id_for_job(db, product_id),
        )

        from app.queue.tasks import analyze_product_task
        from mcp_server.db import dispatch_task
        result = dispatch_task(analyze_product_task, job.id)
        queue_service.mark_queued(job.id, result.id)

        return {
            "job_id": job.id,
            "job_uuid": job.job_uuid,
            "status": "queued",
            "message": "Product analysis queued (step 1 of 4). After this completes, run: "
                       "ci_run_discovery → ci_run_competitor_audit (for each) → ci_run_analysis. "
                       "Use job_get_status to check progress.",
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
def product_get_agent_config(product_id: int) -> dict:
    """Get competitive agent scheduling configuration — controls when analysis, discovery, and audits run automatically.

    Args:
        product_id: The product to get agent config for.
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
                "message": "No agent config exists. Use product_update_agent_config to create one.",
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
            "intensity_idea_threshold": config.intensity_idea_threshold,
        }


@mcp.tool()
def product_update_agent_config(
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
    intensity_idea_threshold: float = None,
) -> dict:
    """Update competitive agent scheduling configuration. Only provided fields are changed.

    Args:
        product_id: The product to configure.
        enabled: Enable or disable the competitive agent entirely.
        product_analysis_mode: "manual" or "scheduled".
        product_analysis_schedule: "daily", "weekly", or "monthly" (when mode is scheduled).
        competitor_discovery_mode: "manual" or "scheduled".
        competitor_discovery_schedule: "daily", "weekly", or "monthly".
        alert_on_new_competitors: Alert when new competitors are discovered.
        alert_on_disappeared_competitors: Alert when competitors disappear.
        deep_analysis_mode: "manual" or "scheduled".
        deep_analysis_schedule: "daily", "weekly", or "monthly".
        intensity_idea_threshold: Priority score threshold (0.0-1.0) for auto-generating ideas from competitive gaps.
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

        if intensity_idea_threshold is not None:
            if not 0.0 <= intensity_idea_threshold <= 1.0:
                return {"error": "intensity_idea_threshold must be between 0.0 and 1.0"}
            config.intensity_idea_threshold = intensity_idea_threshold

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
            "intensity_idea_threshold": config.intensity_idea_threshold,
            "message": "Agent config updated.",
        }
