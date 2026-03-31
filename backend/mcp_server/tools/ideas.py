"""Ideas tools for MCP server."""

from mcp_server import mcp
from mcp_server.db import get_session
from mcp_server.user_context import get_mcp_user_id


@mcp.tool()
def ideas_search(product_id: int, query: str, search_type: str = "ideas") -> dict:
    """Semantic search across all product ideas to find related feature requests. Set search_type to 'jobs' to search by JTBD statements instead."""
    from app.services.embedding_service import generate_embedding
    from app.services.vector_service import VectorService

    with get_session() as db:
        query_emb = generate_embedding(query, input_type="query")

        if search_type == "jobs":
            matches = VectorService.find_similar_jtbds(
                db, query_emb, product_id, limit=10
            )
            return {
                "query": query,
                "search_type": "jobs",
                "matches": matches,
            }

        matches = VectorService.find_similar(
            db, query_emb, product_id, limit=10
        )

        # Also search non-competitive evidence (customer interviews, research, etc.)
        from app.models.evidence import EvidenceType, COMPETITIVE_EVIDENCE_TYPES
        non_competitive_types = [
            et.value for et in EvidenceType
            if et not in COMPETITIVE_EVIDENCE_TYPES
        ]
        evidence_matches = VectorService.find_similar_evidence(
            db, query_emb, product_id, limit=5,
            evidence_types=non_competitive_types,
        )

        return {
            "query": query,
            "search_type": "ideas",
            "matches": [
                {
                    "idea_id": m[0],
                    "title": m[1],
                    "similarity": round(float(m[2]), 3) if len(m) > 2 else None,
                }
                for m in matches
            ],
            "related_evidence": [
                {
                    "evidence_id": e["evidence_id"],
                    "title": e["title"],
                    "evidence_type": e["evidence_type"],
                    "source_url": e["source_url"],
                    "source_description": e["source_description"],
                    "similarity": round(1 - float(e["distance"]) / 2, 3),
                }
                for e in evidence_matches
            ],
        }


@mcp.tool()
def ideas_get_top_voted(product_id: int, limit: int = 10) -> dict:
    """Get the highest-voted customer ideas, showing what customers care about most."""
    from app.models.idea import Idea
    from app.models.vote import Vote
    from sqlalchemy import func

    with get_session() as db:
        results = (
            db.query(
                Idea,
                func.count(Vote.id).label("vote_count"),
            )
            .outerjoin(Vote, Vote.idea_id == Idea.id)
            .filter(Idea.product_id == product_id, Idea.is_active == True)
            .group_by(Idea.id)
            .order_by(func.count(Vote.id).desc())
            .limit(limit)
            .all()
        )

        return {
            "product_id": product_id,
            "ideas": [
                {
                    "idea_id": idea.id,
                    "title": idea.title,
                    "category": idea.category,
                    "status": idea.status.value if idea.status else None,
                    "vote_count": vote_count,
                    "jtbd_statement": idea.jtbd_statement,
                    "triage_recommendation": idea.triage_recommendation,
                }
                for idea, vote_count in results
            ],
        }


@mcp.tool()
def ideas_get_status(idea_id: int) -> dict:
    """Get details for a specific idea including votes, competitive context, and triage results."""
    from app.models.idea import Idea
    from app.models.vote import Vote
    from sqlalchemy import func

    with get_session() as db:
        idea = db.query(Idea).get(idea_id)
        if not idea:
            return {"error": f"Idea {idea_id} not found"}

        vote_count = db.query(func.count(Vote.id)).filter(
            Vote.idea_id == idea_id
        ).scalar() or 0

        return {
            "idea_id": idea.id,
            "title": idea.title,
            "what_description": idea.what_description,
            "why_description": idea.why_description,
            "use_case_description": idea.use_case_description,
            "category": idea.category,
            "status": idea.status.value if idea.status else None,
            "vote_count": vote_count,
            "triage_confidence": idea.triage_confidence,
            "triage_reasoning": idea.triage_reasoning,
            "triage_recommendation": idea.triage_recommendation,
            "competitive_context": idea.competitive_context,
            "jtbd_statement": idea.jtbd_statement,
            "auto_response_text": idea.auto_response_text,
            "created_at": idea.created_at.isoformat() if idea.created_at else None,
        }


@mcp.tool()
def ideas_submit(product_id: int, title: str, description: str) -> dict:
    """Submit a new idea for AI triage. The idea will be normalized, checked for duplicates, and categorized."""
    from app.models.queue import JobType
    from app.services.queue_service import QueueService
    from app.queue.tasks import submit_and_triage_idea_task

    with get_session() as db:
        queue_service = QueueService(db)
        job = queue_service.create_job(
            job_type=JobType.IDEA_TRIAGE,
            input_data={
                "source_type": "customer_submission",
                "raw_input": {
                    "product_id": product_id,
                    "freeform_text": f"{title}\n\n{description}",
                },
            },
            product_id=product_id,
        )

        from mcp_server.db import dispatch_task
        result = dispatch_task(submit_and_triage_idea_task, job.id)
        queue_service.mark_queued(job.id, result.id)

        return {
            "job_id": job.id,
            "job_uuid": job.job_uuid,
            "status": "queued",
            "message": "Idea submitted and triage queued. Use job_get_status to check progress.",
        }


@mcp.tool()
def ideas_vote(idea_id: int) -> dict:
    """Toggle an upvote on an idea. Voting again removes the vote. Returns updated vote count.

    Args:
        idea_id: The ID of the idea to vote on.
    """
    from app.models.idea import Idea
    from app.models.vote import Vote
    from sqlalchemy import func

    with get_session() as db:
        idea = db.query(Idea).get(idea_id)
        if not idea:
            return {"error": f"Idea {idea_id} not found"}

        # Use authenticated user_id (HTTP) or 0 (stdio)
        mcp_user_id = get_mcp_user_id()
        existing = db.query(Vote).filter(
            Vote.idea_id == idea_id,
            Vote.user_id == mcp_user_id,
        ).first()

        if existing:
            db.delete(existing)
            db.flush()
            action = "removed"
        else:
            vote = Vote(idea_id=idea_id, user_id=mcp_user_id, vote_value=1)
            db.add(vote)
            db.flush()
            action = "added"

        vote_count = db.query(func.count(Vote.id)).filter(
            Vote.idea_id == idea_id
        ).scalar() or 0

        return {
            "idea_id": idea_id,
            "title": idea.title,
            "action": action,
            "vote_count": vote_count,
        }


@mcp.tool()
def ideas_review(idea_id: int, action: str, notes: str = "") -> dict:
    """Review an idea as PM: approve, reject, or mark as duplicate.

    Args:
        idea_id: The ID of the idea to review.
        action: One of: "approve" (accept for voting), "reject" (mark not appropriate), "duplicate" (mark as duplicate).
        notes: Optional review notes explaining the decision.
    """
    from app.models.idea import Idea, IdeaStatus
    from app.models.idea_status_history import IdeaStatusHistory

    valid_actions = {"approve", "reject", "duplicate"}
    if action not in valid_actions:
        return {"error": f"Invalid action '{action}'. Must be one of: {sorted(valid_actions)}"}

    with get_session() as db:
        idea = db.query(Idea).get(idea_id)
        if not idea:
            return {"error": f"Idea {idea_id} not found"}

        old_status = idea.status

        if action == "approve":
            idea.status = IdeaStatus.ACCEPTED
            idea.is_active = True
        elif action == "reject":
            idea.status = IdeaStatus.NOT_APPROPRIATE
            idea.is_active = False
        elif action == "duplicate":
            idea.status = IdeaStatus.DUPLICATE
            idea.is_active = False

        # Record status change
        history = IdeaStatusHistory(
            idea_id=idea.id,
            previous_status=old_status,
            new_status=idea.status,
            change_source="mcp_review",
            comment=notes or None,
        )
        db.add(history)
        db.flush()

        return {
            "idea_id": idea.id,
            "title": idea.title,
            "action": action,
            "old_status": old_status.value if old_status else None,
            "new_status": idea.status.value,
            "is_active": idea.is_active,
            "notes": notes or None,
        }


@mcp.tool()
def ideas_get_by_category(product_id: int) -> dict:
    """Get ideas grouped by category with vote counts, showing demand patterns."""
    from app.models.idea import Idea
    from app.models.vote import Vote
    from sqlalchemy import func

    with get_session() as db:
        results = (
            db.query(
                Idea.category,
                func.count(Idea.id).label("idea_count"),
                func.count(Vote.id).label("total_votes"),
            )
            .outerjoin(Vote, Vote.idea_id == Idea.id)
            .filter(Idea.product_id == product_id, Idea.is_active == True)
            .group_by(Idea.category)
            .order_by(func.count(Vote.id).desc())
            .all()
        )

        return {
            "product_id": product_id,
            "categories": [
                {
                    "category": cat or "uncategorized",
                    "idea_count": idea_count,
                    "total_votes": total_votes,
                }
                for cat, idea_count, total_votes in results
            ],
        }
