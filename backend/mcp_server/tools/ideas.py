"""Ideas tools for MCP server."""

import logging

from mcp_server import mcp
from mcp_server.db import get_session
from mcp_server.permissions import require_product_access, resolve_user_id_for_job
from mcp_server.user_context import get_mcp_user_id

from app.models.competitor_intelligence import ProductPermissionLevel

logger = logging.getLogger(__name__)


@mcp.tool()
def ideas_search(product_id: int, query: str, search_type: str = "ideas") -> dict:
    """Semantic search across all product ideas to find related feature requests. Set search_type to 'jobs' to search by JTBD statements instead."""
    from app.services.embedding_service import generate_embedding
    from app.services.vector_service import VectorService

    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

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
def ideas_list(product_id: int, status_filter: str = "", limit: int = 20) -> dict:
    """List ideas for a product, optionally filtered by status.

    Args:
        product_id: The product to list ideas for.
        status_filter: Filter by status (pending, accepted, needs_review, duplicate, not_appropriate). Leave empty for all.
        limit: Maximum number of ideas to return (default 20).
    """
    from app.models.idea import Idea, IdeaStatus
    from app.models.vote import Vote
    from sqlalchemy import func

    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

        query = (
            db.query(Idea, func.count(Vote.id).label("vote_count"))
            .outerjoin(Vote, Vote.idea_id == Idea.id)
            .filter(Idea.product_id == product_id)
        )

        if status_filter:
            try:
                status_enum = IdeaStatus(status_filter)
                query = query.filter(Idea.status == status_enum)
            except ValueError:
                valid = [s.value for s in IdeaStatus]
                return {"error": f"Invalid status_filter '{status_filter}'. Must be one of: {valid}"}

        results = (
            query.group_by(Idea.id)
            .order_by(Idea.created_at.desc())
            .limit(limit)
            .all()
        )

        return {
            "product_id": product_id,
            "count": len(results),
            "ideas": [
                {
                    "idea_id": idea.id,
                    "title": idea.title,
                    "category": idea.category,
                    "status": idea.status.value if idea.status else None,
                    "source_type": idea.source_type.value if idea.source_type else None,
                    "vote_count": vote_count,
                    "is_active": idea.is_active,
                    "created_at": idea.created_at.isoformat() if idea.created_at else None,
                }
                for idea, vote_count in results
            ],
        }


@mcp.tool()
def ideas_get_top_voted(product_id: int, limit: int = 10) -> dict:
    """Get the highest-voted customer ideas, showing what customers care about most."""
    from app.models.idea import Idea
    from app.models.vote import Vote
    from sqlalchemy import func

    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

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

        denied = require_product_access(db, idea.product_id)
        if denied:
            return denied

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
def ideas_create(
    product_id: int,
    source: str,
    title: str = "",
    description: str = "",
    competitor_name: str = "",
    feature_id: int = 0,
    opportunity_id: int = 0,
) -> dict:
    """Create ideas from various sources. The source param determines which fields are required.

    Args:
        product_id: The product to create the idea for.
        source: One of: "manual", "competitor_gaps", "synthesis".
            - "manual": User-submitted idea. Requires title + description. Runs full AI triage.
            - "competitor_gaps": Bulk create from ALL gaps in a competitor's audit report. Requires competitor_name.
            - "synthesis": Create from a specific synthesized opportunity. Requires opportunity_id.
        title: Idea title (required for source="manual").
        description: Idea description (required for source="manual").
        competitor_name: Competitor name or partial match (required for source="competitor_gaps").
        feature_id: Competitor feature ID to convert (for source="competitor_feature", advanced use).
        opportunity_id: Synthesized opportunity ID (required for source="synthesis").
    """
    valid_sources = {"manual", "competitor_gaps", "synthesis"}
    if source not in valid_sources:
        return {"error": f"Invalid source '{source}'. Must be one of: {sorted(valid_sources)}"}

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.EDIT)
        if denied:
            return denied

        if source == "manual":
            return _create_manual(db, product_id, title, description)
        elif source == "competitor_gaps":
            return _create_from_gaps(db, product_id, competitor_name)
        elif source == "synthesis":
            return _create_from_synthesis(db, product_id, opportunity_id)


def _create_manual(db, product_id: int, title: str, description: str) -> dict:
    """Submit a manual idea for AI triage."""
    if not title or not description:
        return {"error": "title and description are required for source='manual'."}

    from app.models.queue import JobType
    from app.services.queue_service import QueueService
    from app.queue.triage_tasks import submit_and_triage_idea_task
    from mcp_server.db import dispatch_task

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
        user_id=resolve_user_id_for_job(db, product_id),
    )

    result = dispatch_task(submit_and_triage_idea_task, job.id)
    queue_service.mark_queued(job.id, result.id)

    return {
        "job_id": job.id,
        "job_uuid": job.job_uuid,
        "status": "queued",
        "message": "Idea submitted and triage queued. Poll with job_get_status until complete.",
    }


def _collect_gaps_from_report(report) -> list:
    """Extract distinct gap features from a functional report.

    Primary source is the unified JTBD model: job_assessments[].features[]
    where position == "gap". Falls back to the legacy gaps_deep_dive
    structure only when no job map was present during the audit.

    Returns a list of dicts with stable keys: feature_name, description,
    evidence_ids. Dedupes by feature_name (the same feature can appear
    under multiple jobs in the unified model).
    """
    gaps_by_name = {}

    for job in (report.job_assessments or []):
        for feat in (job.get('features') or []):
            if feat.get('position') != 'gap':
                continue
            name = feat.get('feature_name')
            if not name or name in gaps_by_name:
                continue
            gaps_by_name[name] = {
                'feature_name': name,
                'description': feat.get('description', ''),
                'evidence_ids': list(feat.get('evidence_ids') or []),
            }

    if gaps_by_name:
        return list(gaps_by_name.values())

    # Legacy fallback: audits that ran without a job map populate
    # gaps_deep_dive (feature_name + user_problem + evidence strings).
    for gap in (report.gaps_deep_dive or []):
        name = gap.get('feature_name')
        if not name or name in gaps_by_name:
            continue
        gaps_by_name[name] = {
            'feature_name': name,
            'description': gap.get('user_problem', ''),
            'evidence_ids': [],
        }
    return list(gaps_by_name.values())


def _create_from_gaps(db, product_id: int, competitor_name: str) -> dict:
    """Create ideas from all gaps in a competitor's functional report."""
    if not competitor_name:
        return {"error": "competitor_name is required for source='competitor_gaps'."}

    from app.models.competitor_intelligence import ProductCompetitor
    from app.models.competitive_reports import CompetitorFunctionalReport
    from app.models.idea import Idea, IdeaStatus, SourceType
    from app.models.queue import JobType
    from app.services.queue_service import QueueService
    from app.queue.triage_tasks import triage_idea_task
    from mcp_server.db import dispatch_task

    competitor = db.query(ProductCompetitor).filter(
        ProductCompetitor.product_id == product_id,
        ProductCompetitor.competitor_name.ilike(f"%{competitor_name}%"),
    ).first()
    if not competitor:
        return {"error": f"No competitor matching '{competitor_name}' found for product {product_id}."}

    report = db.query(CompetitorFunctionalReport).filter(
        CompetitorFunctionalReport.product_competitor_id == competitor.id,
        CompetitorFunctionalReport.product_id == product_id,
    ).order_by(CompetitorFunctionalReport.report_version.desc()).first()
    if not report:
        return {"error": f"No functional report found for {competitor.competitor_name}. Run ci_run_competitor_audit first."}

    gaps = _collect_gaps_from_report(report)
    if not gaps:
        return {"error": f"No gaps found in the latest report for {competitor.competitor_name}."}

    # Dedupe against prior ideas from this competitor, keyed on feature_name.
    existing_ideas = db.query(Idea).filter(
        Idea.product_id == product_id,
        Idea.source_type == SourceType.COMPETITOR_AUTOMATED,
    ).all()
    existing_feature_names = set()
    for idea in existing_ideas:
        metadata = idea.source_metadata or {}
        if (metadata.get('source') == 'competitor_gap' and
                str(metadata.get('competitor_id')) == str(competitor.id)):
            fname = metadata.get('feature_name')
            if fname:
                existing_feature_names.add(fname)

    created = []
    skipped = 0
    queue_service = QueueService(db)
    user_id = resolve_user_id_for_job(db, product_id)

    for gap in gaps:
        feature_name = gap['feature_name']
        if feature_name in existing_feature_names:
            skipped += 1
            continue

        description = gap.get('description') or ''
        idea = Idea(
            product_id=product_id,
            title=feature_name,
            what_description=description,
            why_description='',
            use_case_description='',
            status=IdeaStatus.PENDING,
            source_type=SourceType.COMPETITOR_AUTOMATED,
            source_metadata={
                'source': 'competitor_gap',
                'competitor_id': competitor.id,
                'competitor_name': competitor.competitor_name,
                'feature_name': feature_name,
                'evidence_ids': gap.get('evidence_ids', []),
                'functional_report_id': report.id,
            },
            submitter_id=user_id,
        )
        db.add(idea)
        db.flush()

        job = queue_service.create_job(
            job_type=JobType.IDEA_TRIAGE,
            input_data={'idea_id': idea.id},
            product_id=product_id,
            user_id=user_id,
        )
        created.append({"idea_id": idea.id, "title": idea.title, "job_id": job.id, "job_uuid": job.job_uuid})

    db.commit()

    # Dispatch triage tasks after commit
    for item in created:
        try:
            dispatch_task(triage_idea_task, item["job_id"])
        except Exception as e:
            logger.warning(
                "Failed to dispatch triage for idea %s (job_uuid=%s): %s",
                item["idea_id"], item["job_uuid"], e,
            )

    return {
        "competitor_name": competitor.competitor_name,
        "ideas_created": len(created),
        "ideas_skipped": skipped,
        "ideas": created,
        "message": f"Created {len(created)} idea(s) from {competitor.competitor_name}'s gaps. "
                   f"{skipped} gap(s) already had ideas." if skipped else
                   f"Created {len(created)} idea(s) from {competitor.competitor_name}'s gaps.",
    }


def _create_from_synthesis(db, product_id: int, opportunity_id: int) -> dict:
    """Create an idea from a synthesized opportunity."""
    if not opportunity_id:
        return {"error": "opportunity_id is required for source='synthesis'."}

    from app.models.synthesis import SynthesizedOpportunity
    from app.models.idea import Idea, IdeaStatus, SourceType

    opportunity = db.query(SynthesizedOpportunity).filter(
        SynthesizedOpportunity.id == opportunity_id,
        SynthesizedOpportunity.product_id == product_id,
    ).first()
    if not opportunity:
        return {"error": f"Opportunity {opportunity_id} not found for product {product_id}."}

    if opportunity.linked_idea_id:
        return {"error": f"An idea (id={opportunity.linked_idea_id}) has already been created from this opportunity."}

    # Build description from synthesis evidence
    parts = [opportunity.opportunity_summary or ""]
    parts.append("\n\n**Synthesis Evidence:**")

    if opportunity.competitive_evidence:
        ce = opportunity.competitive_evidence
        competitors = ce.get('competitors', [])
        parts.append(f"\n- **Competitive**: {len(competitors)} competitor(s) ({ce.get('prevalence', 'Unknown')})")

    if opportunity.customer_evidence:
        ce = opportunity.customer_evidence
        parts.append(f"\n- **Customer Votes**: {ce.get('vote_count', 0)} votes on related idea")

    if opportunity.internal_evidence:
        ie = opportunity.internal_evidence
        if ie.get('winloss'):
            wl = ie['winloss']
            parts.append(f"\n- **Win/Loss**: {wl.get('deal_count', 0)} deals (${wl.get('total_value', 0):,.0f})")
        if ie.get('support'):
            sup = ie['support']
            parts.append(f"\n- **Support**: {sup.get('ticket_count', 0)} tickets")

    user_id = resolve_user_id_for_job(db, product_id)
    idea = Idea(
        product_id=product_id,
        title=opportunity.opportunity_name,
        what_description=opportunity.opportunity_summary or "",
        why_description=opportunity.recommended_action or "",
        use_case_description="\n".join(parts),
        source_type=SourceType.COMPETITOR_AUTOMATED,
        submitter_id=user_id,
        status=IdeaStatus.PENDING,
    )
    db.add(idea)
    db.flush()

    opportunity.linked_idea_id = idea.id

    return {
        "idea_id": idea.id,
        "title": idea.title,
        "status": idea.status.value,
        "opportunity_id": opportunity_id,
        "message": f"Idea '{idea.title}' created from synthesis opportunity.",
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

        denied = require_product_access(db, idea.product_id)
        if denied:
            return denied

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
def ideas_get_by_category(product_id: int) -> dict:
    """Get ideas grouped by category with vote counts, showing demand patterns."""
    from app.models.idea import Idea
    from app.models.vote import Vote
    from sqlalchemy import func

    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

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


@mcp.tool()
def ideas_get_comments(idea_id: int) -> dict:
    """Get all comments on an idea, including system-generated triage notes and user comments.

    Args:
        idea_id: The ID of the idea.
    """
    from app.models.idea import Idea
    from app.models.idea_comment import IdeaComment

    with get_session() as db:
        idea = db.query(Idea).get(idea_id)
        if not idea:
            return {"error": f"Idea {idea_id} not found"}

        denied = require_product_access(db, idea.product_id)
        if denied:
            return denied

        comments = (
            db.query(IdeaComment)
            .filter(IdeaComment.idea_id == idea_id)
            .order_by(IdeaComment.created_at.asc())
            .all()
        )

        return {
            "idea_id": idea_id,
            "title": idea.title,
            "count": len(comments),
            "comments": [c.to_dict() for c in comments],
        }


@mcp.tool()
def ideas_add_comment(idea_id: int, content: str) -> dict:
    """Add a comment to an idea.

    Args:
        idea_id: The ID of the idea to comment on.
        content: The comment text (1-5000 characters).
    """
    from app.models.idea import Idea
    from app.models.idea_comment import IdeaComment

    if not content or len(content) > 5000:
        return {"error": "Comment content must be 1-5000 characters."}

    with get_session() as db:
        idea = db.query(Idea).get(idea_id)
        if not idea:
            return {"error": f"Idea {idea_id} not found"}

        denied = require_product_access(db, idea.product_id)
        if denied:
            return denied

        comment = IdeaComment(
            idea_id=idea_id,
            user_id=get_mcp_user_id(),
            comment_text=content,
            is_system_generated=False,
        )
        db.add(comment)
        db.flush()

        return {
            "comment_id": comment.id,
            "idea_id": idea_id,
            "comment_text": comment.comment_text,
            "message": "Comment added.",
        }


@mcp.tool()
def ideas_respond(idea_id: int, status: str, comment: str, duplicate_of_idea_id: int = 0) -> dict:
    """Submit a PM structured response to an idea — approve, reject, mark as duplicate, or note that the feature already exists.

    Args:
        idea_id: The ID of the idea to respond to.
        status: One of: "approved", "duplicate", "feature_exists", "not_appropriate".
        comment: Required explanation of the response decision.
        duplicate_of_idea_id: Required when status is "duplicate" — the ID of the original idea.
    """
    from app.models.idea import Idea, IdeaStatus
    from app.models.idea_comment import IdeaComment
    from app.models.idea_status_history import IdeaStatusHistory

    valid_statuses = {"approved", "duplicate", "feature_exists", "not_appropriate"}
    if status not in valid_statuses:
        return {"error": f"Invalid status '{status}'. Must be one of: {sorted(valid_statuses)}"}

    if not comment:
        return {"error": "A comment explaining the response is required."}

    with get_session() as db:
        idea = db.query(Idea).get(idea_id)
        if not idea:
            return {"error": f"Idea {idea_id} not found"}

        denied = require_product_access(db, idea.product_id, ProductPermissionLevel.EDIT)
        if denied:
            return denied

        old_status = idea.status
        votes_transferred = 0

        # Map string status to enum
        status_map = {
            "approved": IdeaStatus.ACCEPTED,
            "duplicate": IdeaStatus.DUPLICATE,
            "feature_exists": IdeaStatus.FEATURE_EXISTS,
            "not_appropriate": IdeaStatus.NOT_APPROPRIATE,
        }
        new_status = status_map[status]

        # Handle duplicate with vote transfer
        if status == "duplicate":
            if not duplicate_of_idea_id:
                return {"error": "duplicate_of_idea_id is required for status='duplicate'."}

            from app.models.vote import Vote
            duplicate_target = db.query(Idea).filter(
                Idea.id == duplicate_of_idea_id,
                Idea.product_id == idea.product_id,
            ).first()
            if not duplicate_target:
                return {"error": f"Duplicate target idea {duplicate_of_idea_id} not found in same product."}

            idea.duplicate_of_idea_id = duplicate_of_idea_id

            # Transfer votes
            votes = db.query(Vote).filter(Vote.idea_id == idea_id).all()
            for vote in votes:
                existing = db.query(Vote).filter(
                    Vote.idea_id == duplicate_of_idea_id,
                    Vote.user_id == vote.user_id,
                ).first()
                if not existing:
                    vote.idea_id = duplicate_of_idea_id
                    votes_transferred += 1
                else:
                    db.delete(vote)

        # Update idea status
        idea.status = new_status
        idea.is_active = (status == "approved")
        idea.review_notes = comment

        # Record status history
        history = IdeaStatusHistory(
            idea_id=idea.id,
            previous_status=old_status,
            new_status=new_status,
            change_source="mcp_respond",
            comment=comment,
        )
        db.add(history)

        # Add comment
        idea_comment = IdeaComment(
            idea_id=idea_id,
            user_id=get_mcp_user_id(),
            comment_text=comment,
            is_system_generated=False,
        )
        db.add(idea_comment)
        db.flush()

        result = {
            "idea_id": idea.id,
            "title": idea.title,
            "old_status": old_status.value if old_status else None,
            "new_status": idea.status.value,
            "is_active": idea.is_active,
            "comment": comment,
        }
        if votes_transferred:
            result["votes_transferred"] = votes_transferred
            result["duplicate_of_idea_id"] = duplicate_of_idea_id

        return result
