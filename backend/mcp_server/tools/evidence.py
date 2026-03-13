"""Evidence (factbase) tools for MCP server."""

import json
import logging
from typing import Optional

from mcp_server import mcp
from mcp_server.db import get_session

logger = logging.getLogger(__name__)


@mcp.tool()
def evidence_add(
    product_id: int,
    evidence_type: str,
    title: str,
    content: str,
    source_url: str = "",
    source_description: str = "",
    competitor_name: str = "",
    tags: str = "[]",
) -> dict:
    """Add a piece of evidence to the product factbase. Evidence is any product-relevant information: competitive intel, customer interview insights, market signals, research notes, pricing changes, partnership announcements, etc.

    IMPORTANT: Always provide source_url when the information came from a web page, article, or document. Source links are critical for traceability.

    Args:
        product_id: The product this evidence relates to.
        evidence_type: One of: competitive_intel, customer_interview, market_signal, internal_note, research, pricing_change, partnership, product_launch, analyst_report.
        title: Short headline summarizing the evidence (e.g. "Asana launches AI triage feature").
        content: The full information — can be long-form (article summary, interview notes, research findings).
        source_url: Link to the original source (article URL, blog post, etc.). Provide whenever available.
        source_description: Brief label for the source (e.g. "Asana blog", "Customer interview - Acme Corp").
        competitor_name: Optional — name of a tracked competitor this evidence relates to. Will be fuzzy-matched.
        tags: JSON array of tags for categorization (e.g. '["pricing", "enterprise"]'). Default: [].
    """
    from app.models.evidence import Evidence, EvidenceType
    from app.models.competitor_intelligence import ProductCompetitor

    # Validate evidence_type
    try:
        ev_type = EvidenceType(evidence_type)
    except ValueError:
        valid = [e.value for e in EvidenceType]
        return {"error": f"Invalid evidence_type '{evidence_type}'. Must be one of: {valid}"}

    # Parse tags
    try:
        parsed_tags = json.loads(tags) if tags else []
    except json.JSONDecodeError:
        parsed_tags = []

    with get_session() as db:
        # Resolve competitor name to ID if provided
        competitor_id = None
        resolved_competitor = None
        if competitor_name:
            competitor = db.query(ProductCompetitor).filter(
                ProductCompetitor.product_id == product_id,
                ProductCompetitor.competitor_name.ilike(f"%{competitor_name}%"),
            ).first()
            if competitor:
                competitor_id = competitor.id
                resolved_competitor = competitor.competitor_name

        # Generate content embedding
        content_embedding = None
        try:
            from app.services.embedding_service import generate_embedding
            content_embedding = generate_embedding(content[:8000], input_type="document")
        except Exception as e:
            logger.warning("Failed to generate content embedding: %s", e)

        # Extract JTBD statement and generate JTBD embedding
        jtbd_statement = None
        jtbd_embedding = None
        try:
            jtbd_statement = _extract_jtbd(title, content, evidence_type)
            if jtbd_statement:
                from app.services.embedding_service import generate_embedding
                jtbd_embedding = generate_embedding(jtbd_statement, input_type="document")
        except Exception as e:
            logger.warning("Failed to extract JTBD: %s", e)

        evidence = Evidence(
            product_id=product_id,
            evidence_type=ev_type,
            title=title,
            content=content,
            source_url=source_url or None,
            source_description=source_description or None,
            competitor_id=competitor_id,
            tags=parsed_tags if parsed_tags else None,
            jtbd_statement=jtbd_statement,
            jtbd_embedding=jtbd_embedding,
            content_embedding=content_embedding,
            created_by="mcp",
        )
        db.add(evidence)
        db.flush()

        result = {
            "evidence_id": evidence.id,
            "title": evidence.title,
            "evidence_type": evidence_type,
            "has_embedding": content_embedding is not None,
            "jtbd_statement": jtbd_statement,
            "message": f"Evidence '{title}' added to factbase.",
        }
        if resolved_competitor:
            result["linked_competitor"] = resolved_competitor
        if source_url:
            result["source_url"] = source_url

        return result


@mcp.tool()
def evidence_list(
    product_id: int,
    evidence_type: str = "",
    competitor_name: str = "",
    tag: str = "",
    limit: int = 20,
) -> dict:
    """Browse evidence in the product factbase with optional filters.

    Args:
        product_id: The product to list evidence for.
        evidence_type: Filter by type (e.g. "competitive_intel", "customer_interview"). Leave empty for all.
        competitor_name: Filter by competitor name (fuzzy match). Leave empty for all.
        tag: Filter by tag (exact match within tags array). Leave empty for all.
        limit: Maximum number of results (default 20).
    """
    from app.models.evidence import Evidence, EvidenceType
    from app.models.competitor_intelligence import ProductCompetitor

    with get_session() as db:
        query = db.query(Evidence).filter(
            Evidence.product_id == product_id
        )

        if evidence_type:
            try:
                ev_type = EvidenceType(evidence_type)
                query = query.filter(Evidence.evidence_type == ev_type)
            except ValueError:
                pass

        if competitor_name:
            competitor = db.query(ProductCompetitor).filter(
                ProductCompetitor.product_id == product_id,
                ProductCompetitor.competitor_name.ilike(f"%{competitor_name}%"),
            ).first()
            if competitor:
                query = query.filter(Evidence.competitor_id == competitor.id)

        results = query.order_by(Evidence.created_at.desc()).limit(limit).all()

        evidence_list = []
        for e in results:
            summary = e.to_summary_dict()
            # Add competitor name if linked
            if e.competitor_id and e.competitor:
                summary["competitor_name"] = e.competitor.competitor_name
            # Filter by tag in-app if requested (JSON containment varies by DB)
            if tag and e.tags and tag not in e.tags:
                continue
            evidence_list.append(summary)

        return {
            "product_id": product_id,
            "count": len(evidence_list),
            "evidence": evidence_list,
        }


@mcp.tool()
def evidence_get(evidence_id: int) -> dict:
    """Get the full content of a specific evidence record.

    Args:
        evidence_id: The ID of the evidence record to retrieve.
    """
    from app.models.evidence import Evidence

    with get_session() as db:
        evidence = db.query(Evidence).get(evidence_id)
        if not evidence:
            return {"error": f"Evidence {evidence_id} not found"}

        result = evidence.to_dict()
        # Add competitor name if linked
        if evidence.competitor_id and evidence.competitor:
            result["competitor_name"] = evidence.competitor.competitor_name
        return result


def _extract_jtbd(title: str, content: str, evidence_type: str) -> Optional[str]:
    """Extract a JTBD statement from evidence using LLM.

    Returns a statement in the format:
    'When [situation], I want to [motivation], so I can [outcome]'
    or None if not applicable.
    """
    from app.services.llm_service import LLMService

    # Skip JTBD extraction for types where it doesn't make sense
    skip_types = {"internal_note"}
    if evidence_type in skip_types:
        return None

    llm = LLMService()
    system_prompt = """You extract Jobs-to-be-Done statements from product intelligence.

Given a piece of evidence (competitive intel, customer feedback, market signal, etc.),
extract the underlying customer job in this format:
"When [situation], I want to [motivation], so I can [outcome]"

Rules:
- Focus on the customer's job, not the product feature
- Be specific to the evidence provided
- If the evidence doesn't clearly imply a customer job, respond with just "NONE"
- Respond with ONLY the JTBD statement or "NONE" — no other text"""

    user_prompt = f"""Evidence type: {evidence_type}
Title: {title}
Content: {content[:3000]}"""

    try:
        result = llm.call_agent(
            agent_name="evidence_jtbd_extractor",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,
            max_tokens=200,
        )
        statement = result["content"].strip().strip('"')
        if statement.upper() == "NONE" or len(statement) < 20:
            return None
        return statement
    except Exception as e:
        logger.warning("JTBD extraction failed: %s", e)
        return None
