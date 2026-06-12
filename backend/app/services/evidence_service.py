"""
Shared evidence service for creating and managing factbase evidence records.

Used by both the REST API and MCP tools to ensure consistent evidence creation
with embedding generation, JTBD extraction, and competitor association.
"""

import logging
from typing import Optional, List

from sqlalchemy.orm import Session

from app.models.evidence import Evidence, EvidenceType
from app.models.competitor_intelligence import ProductCompetitor

logger = logging.getLogger(__name__)


def create_evidence(
    db: Session,
    product_id: int,
    evidence_type: EvidenceType,
    title: str,
    content: str,
    source_url: Optional[str] = None,
    source_description: Optional[str] = None,
    competitor_id: Optional[int] = None,
    tags: Optional[list] = None,
    created_by: str = "api",
) -> Evidence:
    """Create an evidence record with embedding and JTBD extraction.

    Args:
        db: SQLAlchemy session (caller manages commit/flush).
        product_id: Product this evidence belongs to.
        evidence_type: Validated EvidenceType enum value.
        title: Short headline.
        content: Full evidence content.
        source_url: Original source link.
        source_description: Brief label for the source.
        competitor_id: Optional FK to product_competitors.
        tags: Optional list of categorization tags.
        created_by: Provenance label (e.g. "web_ui", "mcp", "crm_import").

    Returns:
        The created Evidence record (already added to session, not yet committed).
    """
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
        jtbd_statement = extract_jtbd(title, content, evidence_type.value)
        if jtbd_statement:
            from app.services.embedding_service import generate_embedding
            jtbd_embedding = generate_embedding(jtbd_statement, input_type="document")
    except Exception as e:
        logger.warning("Failed to extract JTBD: %s", e)

    evidence = Evidence(
        product_id=product_id,
        evidence_type=evidence_type,
        title=title,
        content=content,
        source_url=source_url or None,
        source_description=source_description or None,
        competitor_id=competitor_id,
        tags=tags if tags else None,
        jtbd_statement=jtbd_statement,
        jtbd_embedding=jtbd_embedding,
        content_embedding=content_embedding,
        created_by=created_by,
    )
    db.add(evidence)
    db.flush()

    # Auto-link evidence to the most similar active job (if any)
    try:
        _link_evidence_to_job(db, evidence, product_id)
    except Exception as e:
        logger.warning("Failed to link evidence to job: %s", e)

    # Surface unmatched/weak-match signals as need map suggestions
    try:
        from app.queue.helpers import _maybe_suggest_need
        _maybe_suggest_need(
            db,
            product_id=product_id,
            signal_type="evidence",
            signal_id=evidence.id,
            signal_content=f"{title}: {content[:400]}",
            jtbd_embedding=jtbd_embedding,
        )
    except Exception as e:
        logger.warning("Failed to create need suggestion from evidence: %s", e)

    return evidence


def _link_evidence_to_job(db: Session, evidence: Evidence, product_id: int) -> None:
    """Match evidence to the most similar active job via embedding similarity.

    Uses cosine similarity between the evidence's JTBD embedding and each
    active ProductJob's statement_embedding. If the best match exceeds the
    similarity threshold (0.5), the evidence's job_id_key is set.
    """
    if not evidence.jtbd_embedding:
        return

    from app.models.competitor_intelligence import ProductJob

    jobs = db.query(ProductJob).filter(
        ProductJob.product_id == product_id,
        ProductJob.status == "active",
    ).all()

    if not jobs:
        return

    # Cosine similarity
    import numpy as np
    evidence_emb = np.array(evidence.jtbd_embedding)

    best_job = None
    best_sim = 0.0
    for job in jobs:
        if not job.statement_embedding:
            continue
        job_emb = np.array(job.statement_embedding)
        sim = float(
            np.dot(evidence_emb, job_emb)
            / (np.linalg.norm(evidence_emb) * np.linalg.norm(job_emb) + 1e-8)
        )
        if sim > best_sim and sim > 0.5:  # threshold
            best_sim = sim
            best_job = job

    if best_job:
        evidence.job_id_key = best_job.job_id_key


def increment_evidence_citations(
    db: Session,
    evidence_ids: list,
    cited_in: str,
) -> None:
    """Increment citation_count and update last_cited_in for a list of evidence IDs.

    Args:
        db: SQLAlchemy session (caller manages commit/flush).
        evidence_ids: List of evidence IDs being cited.
        cited_in: Context where cited, e.g. "functional_report:5", "synthesis_report:3".
    """
    if not evidence_ids:
        return

    # Deduplicate + coerce to int so we don't pass bad types
    unique_ids = list({int(eid) for eid in evidence_ids if eid is not None})
    if not unique_ids:
        return

    db.query(Evidence).filter(Evidence.id.in_(unique_ids)).update(
        {
            Evidence.citation_count: Evidence.citation_count + 1,
            Evidence.last_cited_in: cited_in,
        },
        synchronize_session=False,
    )


def extract_jtbd(title: str, content: str, evidence_type: str) -> Optional[str]:
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


def resolve_competitor_by_name(
    db: Session,
    product_id: int,
    competitor_name: str,
) -> Optional[ProductCompetitor]:
    """Fuzzy-match a competitor name against existing competitors for a product."""
    return db.query(ProductCompetitor).filter(
        ProductCompetitor.product_id == product_id,
        ProductCompetitor.competitor_name.ilike(f"%{competitor_name}%"),
        ProductCompetitor.status == "active",
    ).first()


def suggest_competitor(
    db: Session,
    product_id: int,
    title: str,
    content: str,
) -> dict:
    """Use LLM to identify competitor mentions in evidence content.

    Returns:
        Dict with keys:
        - suggested_name: str or None — competitor name found in content
        - matched_competitor_id: int or None — ID if matched to existing competitor
        - matched_competitor_name: str or None — canonical name of matched competitor
        - is_new: bool — True if a competitor was identified but doesn't match existing ones
    """
    from app.services.llm_service import LLMService

    # Get existing competitors for matching
    existing_competitors = db.query(ProductCompetitor).filter(
        ProductCompetitor.product_id == product_id,
        ProductCompetitor.status == "active",
    ).all()

    competitor_names = [c.competitor_name for c in existing_competitors]

    llm = LLMService()
    system_prompt = """You identify competitor mentions in product intelligence evidence.

Given a piece of evidence, determine if it primarily relates to a specific competitor product or company.

Known competitors for this product:
{competitors}

Rules:
- If the evidence is clearly about one of the known competitors, respond with exactly that competitor's name
- If the evidence is about a competitor NOT in the list, respond with the competitor's name
- If the evidence is general/not about a specific competitor, respond with "NONE"
- Respond with ONLY the competitor name or "NONE" — no other text""".format(
        competitors="\n".join(f"- {name}" for name in competitor_names) if competitor_names else "- (none tracked yet)"
    )

    user_prompt = f"""Title: {title}
Content: {content[:3000]}"""

    try:
        result = llm.call_agent(
            agent_name="evidence_competitor_detector",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=100,
        )
        suggested_name = result["content"].strip().strip('"')

        if suggested_name.upper() == "NONE" or len(suggested_name) < 2:
            return {
                "suggested_name": None,
                "matched_competitor_id": None,
                "matched_competitor_name": None,
                "is_new": False,
            }

        # Try to match against existing competitors
        matched = resolve_competitor_by_name(db, product_id, suggested_name)
        if matched:
            return {
                "suggested_name": suggested_name,
                "matched_competitor_id": matched.id,
                "matched_competitor_name": matched.competitor_name,
                "is_new": False,
            }

        return {
            "suggested_name": suggested_name,
            "matched_competitor_id": None,
            "matched_competitor_name": None,
            "is_new": True,
        }

    except Exception as e:
        logger.warning("Competitor suggestion failed: %s", e)
        return {
            "suggested_name": None,
            "matched_competitor_id": None,
            "matched_competitor_name": None,
            "is_new": False,
        }


def get_evidence_count_by_competitor(
    db: Session,
    product_id: int,
) -> dict:
    """Get evidence counts grouped by competitor_id for a product.

    Returns:
        Dict mapping competitor_id -> count. Key None = unlinked evidence.
    """
    from sqlalchemy import func

    results = db.query(
        Evidence.competitor_id,
        func.count(Evidence.id),
    ).filter(
        Evidence.product_id == product_id,
    ).group_by(Evidence.competitor_id).all()

    return {competitor_id: count for competitor_id, count in results}
