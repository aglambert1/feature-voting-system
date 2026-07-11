"""MCP Resources for Feature-IQ."""

from mcp_server import mcp
from mcp_server.db import get_session
from mcp_server.serializers import latest_functional_report


@mcp.resource("featureiq://product/{product_id}/landscape")
def get_landscape_markdown(product_id: int) -> str:
    """Latest unified synthesis report as markdown."""
    from app.models.synthesis import SynthesisReport
    from sqlalchemy import desc

    with get_session() as db:
        report = (
            db.query(SynthesisReport)
            .filter(SynthesisReport.product_id == product_id)
            .order_by(desc(SynthesisReport.report_version))
            .first()
        )
        if not report or not report.report_content_md:
            return "No synthesis report available for this product."
        return report.report_content_md


@mcp.resource("featureiq://product/{product_id}/competitors")
def get_competitors_summary(product_id: int) -> str:
    """Competitor list with audit status."""
    from app.models.competitor_intelligence import ProductCompetitor

    with get_session() as db:
        competitors = db.query(ProductCompetitor).filter(
            ProductCompetitor.product_id == product_id,
            ProductCompetitor.status == "active",
        ).all()

        if not competitors:
            return "No competitors tracked for this product."

        lines = [f"# Competitors for Product {product_id}\n"]
        for c in competitors:
            report = latest_functional_report(db, c.id)
            status = "analyzed" if report else "not analyzed"
            version = f" (v{report.report_version})" if report else ""
            lines.append(f"- **{c.competitor_name}** — {status}{version}")
            if c.competitor_url:
                lines.append(f"  URL: {c.competitor_url}")

        return "\n".join(lines)


@mcp.resource("featureiq://product/{product_id}/data-freshness")
def get_data_freshness(product_id: int) -> str:
    """When each data source was last updated."""
    from app.models.synthesis import SynthesisReport
    from app.models.internal_feedback import InternalFeedbackImport
    from app.models.idea import Idea
    from sqlalchemy import func, desc

    with get_session() as db:
        latest_report = (
            db.query(SynthesisReport)
            .filter(SynthesisReport.product_id == product_id)
            .order_by(desc(SynthesisReport.report_version))
            .first()
        )

        latest_import = (
            db.query(InternalFeedbackImport)
            .filter(InternalFeedbackImport.product_id == product_id, InternalFeedbackImport.status == "completed")
            .order_by(InternalFeedbackImport.processed_at.desc())
            .first()
        )

        idea_count = db.query(func.count(Idea.id)).filter(
            Idea.product_id == product_id, Idea.is_active == True
        ).scalar() or 0

        lines = [f"# Data Freshness for Product {product_id}\n"]
        lines.append(f"- **Synthesis Report:** {latest_report.generated_at.isoformat() if latest_report else 'Never'}")
        lines.append(f"- **Internal Feedback:** {latest_import.processed_at.isoformat() if latest_import and latest_import.processed_at else 'Never'}")
        lines.append(f"- **Customer Ideas:** {idea_count} active ideas")

        return "\n".join(lines)
