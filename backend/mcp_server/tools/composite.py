"""Composite tools that chain multiple data sources for MCP server."""

from mcp_server import mcp
from mcp_server.db import get_session


@mcp.tool()
def evaluate_feature_evidence(product_id: int, feature_description: str) -> dict:
    """Gather all available evidence about a feature capability from competitive data, customer ideas, and internal feedback. Does NOT recommend build/don't-build — returns evidence for PM decision-making."""
    from app.services.embedding_service import generate_embedding
    from app.services.vector_service import VectorService
    from app.models.internal_feedback import WinLossTheme, SupportTheme

    with get_session() as db:
        query_emb = generate_embedding(feature_description, input_type="query")

        # Search competitor features
        comp_matches = VectorService.find_similar_competitor_features(
            db, query_emb, product_id, limit=5
        )
        competitive_signals = [
            {
                "feature_id": m[0],
                "competitor_name": m[1] if len(m) > 1 else None,
                "feature_name": m[2] if len(m) > 2 else None,
                "similarity": round(float(m[4]), 3) if len(m) > 4 else None,
            }
            for m in comp_matches
        ]

        # Search customer ideas
        idea_matches = VectorService.find_similar(
            db, query_emb, product_id, limit=5
        )
        customer_signals = [
            {
                "idea_id": m[0],
                "title": m[1],
                "similarity": round(float(m[2]), 3) if len(m) > 2 else None,
            }
            for m in idea_matches
        ]

        # Search internal themes (text-based)
        query_lower = feature_description.lower()
        wl_themes = db.query(WinLossTheme).filter(
            WinLossTheme.product_id == product_id
        ).all()
        st_themes = db.query(SupportTheme).filter(
            SupportTheme.product_id == product_id
        ).all()

        internal_signals = []
        for t in wl_themes:
            keywords = t.feature_keywords or []
            if query_lower in t.theme_name.lower() or any(
                query_lower in kw.lower() for kw in keywords
            ):
                internal_signals.append({
                    "type": "winloss",
                    "theme_name": t.theme_name,
                    "outcome": t.outcome,
                    "deal_count": t.deal_count,
                    "total_value": t.total_value,
                })
        for t in st_themes:
            keywords = t.feature_keywords or []
            if query_lower in t.theme_name.lower() or any(
                query_lower in kw.lower() for kw in keywords
            ):
                internal_signals.append({
                    "type": "support",
                    "theme_name": t.theme_name,
                    "ticket_count": t.ticket_count,
                    "urgency_indicator": t.urgency_indicator,
                })

        # Search factbase evidence
        evidence_signals = VectorService.find_similar_evidence(
            db, query_emb, product_id, limit=5
        )
        factbase_evidence = [
            {
                "evidence_id": e["evidence_id"],
                "title": e["title"],
                "evidence_type": e["evidence_type"],
                "source_url": e["source_url"],
                "source_description": e["source_description"],
                "jtbd_statement": e["jtbd_statement"],
                "similarity": round(1 - float(e["distance"]) / 2, 3),
            }
            for e in evidence_signals
        ]

        # Build signal summary
        source_count = sum([
            1 if competitive_signals else 0,
            1 if customer_signals else 0,
            1 if internal_signals else 0,
            1 if factbase_evidence else 0,
        ])
        competitors_with = list(set(
            s["competitor_name"] for s in competitive_signals if s.get("competitor_name")
        ))

        # Dynamic evidence gaps based on what's actually available
        evidence_gaps = []
        if not factbase_evidence:
            evidence_gaps.append("no factbase evidence found — use evidence_add to capture relevant intel")
        if not any(e["evidence_type"] == "customer_interview" for e in factbase_evidence):
            evidence_gaps.append("no customer interview data available")
        evidence_gaps.extend([
            "market sizing not available",
            "engineering effort not estimated",
        ])

        return {
            "feature_description": feature_description,
            "competitive_signals": competitive_signals,
            "customer_signals": customer_signals,
            "internal_signals": internal_signals,
            "factbase_evidence": factbase_evidence,
            "signal_summary": {
                "source_count": source_count,
                "competitors_with_feature": competitors_with,
                "customer_ideas_found": len(customer_signals),
                "internal_themes_found": len(internal_signals),
                "factbase_evidence_found": len(factbase_evidence),
            },
            "evidence_gaps": evidence_gaps,
        }


@mcp.tool()
def get_jobs_cluster(product_id: int, job_query: str) -> dict:
    """Find all evidence related to a customer job across ideas, competitive features, internal themes, synthesized opportunities, and factbase evidence. Groups related signals by the underlying job customers are trying to accomplish."""
    from app.services.embedding_service import generate_embedding
    from app.services.vector_service import VectorService

    with get_session() as db:
        query_emb = generate_embedding(job_query, input_type="query")

        # Search JTBD across ideas
        idea_jtbds = VectorService.find_similar_jtbds(
            db, query_emb, product_id, limit=10
        )

        # Search JTBD across opportunities
        opp_jtbds = VectorService.find_similar_opportunity_jtbds(
            db, query_emb, product_id, limit=10
        )

        # Search competitor features for coverage
        comp_matches = VectorService.find_similar_competitor_features(
            db, query_emb, product_id, limit=5
        )
        competitive_coverage = [
            {
                "competitor_name": m[1] if len(m) > 1 else None,
                "feature_name": m[2] if len(m) > 2 else None,
                "similarity": round(float(m[4]), 3) if len(m) > 4 else None,
            }
            for m in comp_matches
        ]

        # Search factbase evidence
        evidence_matches = VectorService.find_similar_evidence(
            db, query_emb, product_id, limit=5
        )
        factbase_evidence = [
            {
                "evidence_id": e["evidence_id"],
                "title": e["title"],
                "evidence_type": e["evidence_type"],
                "source_url": e["source_url"],
                "jtbd_statement": e["jtbd_statement"],
                "similarity": round(1 - float(e["distance"]) / 2, 3),
            }
            for e in evidence_matches
        ]

        return {
            "job_query": job_query,
            "related_ideas": idea_jtbds,
            "related_opportunities": opp_jtbds,
            "competitive_coverage": competitive_coverage,
            "factbase_evidence": factbase_evidence,
        }
