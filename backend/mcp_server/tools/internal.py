"""Internal feedback tools for MCP server."""

import json
import logging

from mcp_server import mcp
from mcp_server.db import get_session
from mcp_server.permissions import require_product_access, resolve_user_id_for_job
from mcp_server.user_context import get_mcp_user_label

from app.models.competitor_intelligence import ProductPermissionLevel

logger = logging.getLogger(__name__)


@mcp.tool()
def internal_get_themes(
    product_id: int, outcome_filter: str = ""
) -> dict:
    """Get win/loss and support themes from internal feedback, showing deal impact and support burden."""
    from app.models.internal_feedback import WinLossTheme, SupportTheme

    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

        wl_query = db.query(WinLossTheme).filter(
            WinLossTheme.product_id == product_id
        )
        if outcome_filter in ("won", "lost", "both"):
            wl_query = wl_query.filter(WinLossTheme.outcome == outcome_filter)

        winloss_themes = wl_query.all()
        support_themes = db.query(SupportTheme).filter(
            SupportTheme.product_id == product_id
        ).all()

        return {
            "product_id": product_id,
            "winloss_themes": [
                {
                    "id": t.id,
                    "theme_name": t.theme_name,
                    "outcome": t.outcome,
                    "competitor_name": t.competitor_name,
                    "deal_count": t.deal_count,
                    "total_value": t.total_value,
                    "sample_reasons": t.sample_reasons,
                    "feature_keywords": t.feature_keywords,
                    "jtbd_statement": t.jtbd_statement,
                }
                for t in winloss_themes
            ],
            "support_themes": [
                {
                    "id": t.id,
                    "theme_name": t.theme_name,
                    "category": t.category,
                    "ticket_count": t.ticket_count,
                    "sample_subjects": t.sample_subjects,
                    "feature_keywords": t.feature_keywords,
                    "urgency_indicator": t.urgency_indicator,
                    "jtbd_statement": t.jtbd_statement,
                }
                for t in support_themes
            ],
        }


def search_internal_themes(db, product_id: int, query: str) -> tuple[list, list]:
    """Keyword-scan win/loss and support themes for a capability.

    Matches query against theme_name and feature_keywords (case-insensitive
    substring — keyword-based, not semantic). Returns (winloss_matches,
    support_matches) with the full theme field set.
    """
    from app.models.internal_feedback import WinLossTheme, SupportTheme

    query_lower = query.lower()

    wl_themes = db.query(WinLossTheme).filter(
        WinLossTheme.product_id == product_id
    ).all()
    st_themes = db.query(SupportTheme).filter(
        SupportTheme.product_id == product_id
    ).all()

    matching_wl = []
    for t in wl_themes:
        keywords = t.feature_keywords or []
        if (
            query_lower in t.theme_name.lower()
            or any(query_lower in kw.lower() for kw in keywords)
        ):
            matching_wl.append({
                "theme_name": t.theme_name,
                "outcome": t.outcome,
                "deal_count": t.deal_count,
                "total_value": t.total_value,
                "jtbd_statement": t.jtbd_statement,
            })

    matching_st = []
    for t in st_themes:
        keywords = t.feature_keywords or []
        if (
            query_lower in t.theme_name.lower()
            or any(query_lower in kw.lower() for kw in keywords)
        ):
            matching_st.append({
                "theme_name": t.theme_name,
                "category": t.category,
                "ticket_count": t.ticket_count,
                "urgency_indicator": t.urgency_indicator,
                "jtbd_statement": t.jtbd_statement,
            })

    return matching_wl, matching_st


@mcp.tool()
def internal_get_signals(product_id: int, query: str) -> dict:
    """Search internal win/loss and support themes by keyword for a specific capability.

    Internal feedback ONLY — for cross-source evidence (competitive + customer
    ideas + factbase + internal) use evaluate_feature_evidence. Matching is
    keyword-based (theme names and feature keywords), not semantic.
    """
    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

        matching_wl, matching_st = search_internal_themes(db, product_id, query)

        return {
            "query": query,
            "winloss_matches": matching_wl,
            "support_matches": matching_st,
        }


@mcp.tool()
def internal_list_imports(product_id: int) -> dict:
    """List internal feedback imports for a product, showing processing status.

    Args:
        product_id: The product to list imports for.
    """
    from app.models.internal_feedback import InternalFeedbackImport

    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

        imports = db.query(InternalFeedbackImport).filter(
            InternalFeedbackImport.product_id == product_id
        ).order_by(InternalFeedbackImport.imported_at.desc()).all()

        return {
            "product_id": product_id,
            "imports": [
                {
                    "import_id": imp.id,
                    "filename": imp.filename,
                    "source_type": imp.source_type,
                    "status": imp.status,
                    "deals_count": imp.deals_count,
                    "tickets_count": imp.tickets_count,
                    "themes_extracted": imp.themes_extracted,
                    "imported_at": imp.imported_at.isoformat() if imp.imported_at else None,
                    "processed_at": imp.processed_at.isoformat() if imp.processed_at else None,
                }
                for imp in imports
            ],
        }


@mcp.tool()
def internal_delete_theme(theme_id: int, theme_type: str) -> dict:
    """Delete a win/loss or support theme.

    Args:
        theme_id: The ID of the theme to delete.
        theme_type: One of "winloss" or "support".
    """
    from app.models.internal_feedback import WinLossTheme, SupportTheme

    valid_types = {"winloss", "support"}
    if theme_type not in valid_types:
        return {"error": f"Invalid theme_type '{theme_type}'. Must be one of: {sorted(valid_types)}"}

    with get_session() as db:
        if theme_type == "winloss":
            theme = db.query(WinLossTheme).get(theme_id)
            if not theme:
                return {"error": f"Win/loss theme {theme_id} not found"}
            denied = require_product_access(db, theme.product_id, ProductPermissionLevel.EDIT)
            if denied:
                return denied
            name = theme.theme_name
            db.delete(theme)
        else:
            theme = db.query(SupportTheme).get(theme_id)
            if not theme:
                return {"error": f"Support theme {theme_id} not found"}
            denied = require_product_access(db, theme.product_id, ProductPermissionLevel.EDIT)
            if denied:
                return denied
            name = theme.theme_name
            db.delete(theme)

        db.flush()

        return {
            "theme_id": theme_id,
            "theme_type": theme_type,
            "theme_name": name,
            "message": f"Theme '{name}' deleted.",
        }


@mcp.tool()
def internal_get_activity_insights(product_id: int) -> dict:
    """Get extracted activity insights from CRM data — deal win/loss patterns and support themes.

    Args:
        product_id: The product to get activity insights for.
    """
    from app.models.activity_insights import ActivityImport, DealActivityInsight, SupportActivityInsight
    from sqlalchemy import desc

    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

        # Get most recent completed import
        import_record = db.query(ActivityImport).filter(
            ActivityImport.product_id == product_id,
            ActivityImport.status == "completed",
        ).order_by(desc(ActivityImport.imported_at)).first()

        if not import_record:
            return {
                "product_id": product_id,
                "has_insights": False,
                "message": "No completed activity imports found. Use internal_submit_feedback or upload CRM data via the web UI.",
            }

        deal_insights = db.query(DealActivityInsight).filter(
            DealActivityInsight.import_id == import_record.id
        ).all()

        support_insights = db.query(SupportActivityInsight).filter(
            SupportActivityInsight.import_id == import_record.id
        ).all()

        return {
            "product_id": product_id,
            "has_insights": True,
            "import_id": import_record.id,
            "analysis_summary": import_record.analysis_summary,
            "top_loss_themes": import_record.top_loss_themes or [],
            "top_win_themes": import_record.top_win_themes or [],
            "deal_insights": [
                {
                    "id": i.id,
                    "deal_name": i.deal_name,
                    "deal_outcome": i.deal_outcome,
                    "deal_value": i.deal_value,
                    "competitor_mentioned": i.competitor_mentioned,
                    "theme_name": i.theme_name,
                    "category": i.category,
                    "sentiment": i.sentiment,
                    "urgency_level": i.urgency_level,
                    "activity_count": i.activity_count,
                    "feature_keywords": i.feature_keywords or [],
                }
                for i in deal_insights
            ],
            "support_insights": [
                {
                    "id": i.id,
                    "theme_name": i.theme_name,
                    "category": i.category,
                    "ticket_count": i.ticket_count,
                    "urgency_level": i.urgency_level,
                    "feature_keywords": i.feature_keywords or [],
                }
                for i in support_insights
            ],
        }


@mcp.tool()
def internal_submit_feedback(
    product_id: int,
    deals_json: str = "[]",
    tickets_json: str = "[]",
    source: str = "mcp",
) -> dict:
    """Submit internal feedback data (win/loss deals and/or support tickets) for theme extraction. The data will be processed asynchronously by an AI agent to extract themes.

    Args:
        product_id: The product this feedback relates to.
        deals_json: JSON array of deal records. Each deal: {"company_name": "Acme", "deal_value": 50000, "outcome": "lost", "loss_reason": "Missing time tracking", "competitor": "Asana"}. Fields: company_name (required), deal_value, outcome (won/lost), loss_reason, win_reason, competitor.
        tickets_json: JSON array of support tickets. Each ticket: {"subject": "Need time tracking", "category": "feature_request", "priority": "high"}. Fields: subject (required), category, priority, description.
        source: Label for where this data came from (default: "mcp").
    """
    from app.models.internal_feedback import InternalFeedbackImport
    from app.models.queue import JobType
    from app.services.queue_service import QueueService
    from app.queue.internal_tasks import internal_discovery_task

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.EDIT)
        if denied:
            return denied

        try:
            deals = json.loads(deals_json) if deals_json else []
        except json.JSONDecodeError:
            return {"error": "Invalid deals_json — must be a valid JSON array."}

        try:
            tickets = json.loads(tickets_json) if tickets_json else []
        except json.JSONDecodeError:
            return {"error": "Invalid tickets_json — must be a valid JSON array."}

        if not deals and not tickets:
            return {"error": "At least one deal or ticket must be provided."}

        # Use authenticated user label when source is the default
        effective_source = get_mcp_user_label() if source == "mcp" else source

        # Create import record
        fb_import = InternalFeedbackImport(
            product_id=product_id,
            filename=f"mcp_import_{effective_source}",
            source_type=effective_source,
            status="pending",
            deals_count=len(deals),
            tickets_count=len(tickets),
            raw_deals=deals if deals else None,
            raw_tickets=tickets if tickets else None,
        )
        db.add(fb_import)
        db.flush()

        queue_service = QueueService(db)
        job = queue_service.create_job(
            job_type=JobType.INTERNAL_DISCOVERY,
            input_data={
                "import_id": fb_import.id,
                "deals": deals,
                "support_tickets": tickets,
            },
            product_id=product_id,
            user_id=resolve_user_id_for_job(db, product_id),
        )

        from mcp_server.db import dispatch_task
        result = dispatch_task(internal_discovery_task, job.id)
        queue_service.mark_queued(job.id, result.id)

        return {
            "import_id": fb_import.id,
            "job_id": job.id,
            "job_uuid": job.job_uuid,
            "deals_count": len(deals),
            "tickets_count": len(tickets),
            "status": "queued",
            "message": "Internal feedback import queued for theme extraction. Use job_get_status to check progress.",
        }
