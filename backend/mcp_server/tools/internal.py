"""Internal feedback tools for MCP server."""

from mcp_server import mcp
from mcp_server.db import get_session


@mcp.tool()
def internal_get_themes(
    product_id: int, outcome_filter: str = ""
) -> dict:
    """Get win/loss and support themes from internal feedback, showing deal impact and support burden."""
    from app.models.internal_feedback import WinLossTheme, SupportTheme

    with get_session() as db:
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
