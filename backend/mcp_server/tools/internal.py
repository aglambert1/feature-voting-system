"""Internal feedback tools for MCP server."""

import json
import logging

from mcp_server import mcp
from mcp_server.db import get_session
from mcp_server.permissions import require_product_access
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


@mcp.tool()
def internal_get_signals(product_id: int, query: str) -> dict:
    """Search internal feedback for themes related to a specific capability."""
    from app.models.internal_feedback import WinLossTheme, SupportTheme

    query_lower = query.lower()

    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

        # Text-based search across theme names and feature keywords
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

        return {
            "query": query,
            "winloss_matches": matching_wl,
            "support_matches": matching_st,
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
    from app.queue.tasks import internal_discovery_task

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
