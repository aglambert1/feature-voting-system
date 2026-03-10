"""MCP Resources for Feature-IQ."""

from mcp_server import mcp
from mcp_server.db import get_session


@mcp.resource("featureiq://product/{product_id}/landscape")
def get_landscape_markdown(product_id: int) -> str:
    """Latest landscape report as markdown."""
    from app.models.competitive_reports import LandscapeOpportunityReport

    with get_session() as db:
        report = db.query(LandscapeOpportunityReport).filter(
            LandscapeOpportunityReport.product_id == product_id
        ).first()
        if not report or not report.report_content_md:
            return "No landscape report available for this product."
        return report.report_content_md


@mcp.resource("featureiq://product/{product_id}/competitors")
def get_competitors_summary(product_id: int) -> str:
    """Competitor list with audit status."""
    from app.models.competitor_intelligence import ProductCompetitor
    from app.models.competitive_reports import CompetitorFunctionalReport

    with get_session() as db:
        competitors = db.query(ProductCompetitor).filter(
            ProductCompetitor.product_id == product_id,
            ProductCompetitor.status == "active",
        ).all()

        if not competitors:
            return "No competitors tracked for this product."

        lines = [f"# Competitors for Product {product_id}\n"]
        for c in competitors:
            report = db.query(CompetitorFunctionalReport).filter(
                CompetitorFunctionalReport.product_competitor_id == c.id
            ).first()
            status = "analyzed" if report else "not analyzed"
            version = f" (v{report.report_version})" if report else ""
            lines.append(f"- **{c.competitor_name}** — {status}{version}")
            if c.competitor_url:
                lines.append(f"  URL: {c.competitor_url}")

        return "\n".join(lines)


@mcp.resource("featureiq://product/{product_id}/data-freshness")
def get_data_freshness(product_id: int) -> str:
    """When each data source was last updated."""
    from app.models.competitive_reports import LandscapeOpportunityReport
    from app.models.synthesis import SynthesisRun
    from app.models.internal_feedback import InternalFeedbackImport
    from app.models.idea import Idea
    from sqlalchemy import func

    with get_session() as db:
        landscape = db.query(LandscapeOpportunityReport).filter(
            LandscapeOpportunityReport.product_id == product_id
        ).first()

        latest_synthesis = (
            db.query(SynthesisRun)
            .filter(SynthesisRun.product_id == product_id, SynthesisRun.status == "completed")
            .order_by(SynthesisRun.completed_at.desc())
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
        lines.append(f"- **Landscape Analysis:** {landscape.generated_at.isoformat() if landscape else 'Never'}")
        lines.append(f"- **Opportunity Synthesis:** {latest_synthesis.completed_at.isoformat() if latest_synthesis and latest_synthesis.completed_at else 'Never'}")
        lines.append(f"- **Internal Feedback:** {latest_import.processed_at.isoformat() if latest_import and latest_import.processed_at else 'Never'}")
        lines.append(f"- **Customer Ideas:** {idea_count} active ideas")

        return "\n".join(lines)
