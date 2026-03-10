"""Product tools for MCP server."""

from mcp_server import mcp
from mcp_server.db import get_session


@mcp.tool()
def product_list() -> dict:
    """List all products available for analysis."""
    from app.models.competitor_intelligence import CIProduct, ProductCompetitor
    from app.models.idea import Idea
    from sqlalchemy import func

    with get_session() as db:
        products = db.query(CIProduct).all()
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
def product_search_features(product_id: int, query: str) -> dict:
    """Semantic search across a product's own features."""
    from app.services.embedding_service import generate_embedding
    from app.services.vector_service import VectorService

    with get_session() as db:
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
