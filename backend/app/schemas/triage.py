"""TriageVerdict — the stable, structured triage result for an idea.

This is the write-back contract for external idea systems: an agent syncing
verdicts to Aha!/Canny/Jira maps these fixed vocabularies onto the external
tool's own statuses/tags/comments. Every field derives from persisted Idea
columns, so verdicts are available for any past triage, not just the run
that produced them.

Vocabularies:
- status: IdeaStatus values (pending, accepted, needs_review, duplicate,
  merged, feature_exists, not_appropriate)
- recommendation: approve | merge | review | reject
- competitive.competitive_urgency: low | medium | high | critical
"""

from typing import List, Optional

from pydantic import BaseModel


class TriageDuplicateInfo(BaseModel):
    duplicate_of_idea_id: int
    duplicate_of_title: Optional[str] = None
    similarity_score: Optional[float] = None


class TriageFeatureExistsInfo(BaseModel):
    feature_name: Optional[str] = None
    feature_description: Optional[str] = None
    similarity_score: Optional[float] = None
    source_url: Optional[str] = None


class TriageCompetitiveInfo(BaseModel):
    competitors_with_feature: List[str] = []
    competitive_urgency: Optional[str] = None


class TriageJobLink(BaseModel):
    job_id_key: str
    job_statement: Optional[str] = None


class TriageExternalInfo(BaseModel):
    external_id: str
    external_source: str


class TriageVerdict(BaseModel):
    idea_id: int
    triaged: bool
    status: str
    is_active: bool
    recommendation: Optional[str] = None
    confidence: Optional[float] = None
    reasoning: Optional[str] = None
    category: Optional[str] = None
    auto_categorized: bool = False
    jtbd_statement: Optional[str] = None
    duplicate: Optional[TriageDuplicateInfo] = None
    feature_exists: Optional[TriageFeatureExistsInfo] = None
    competitive: Optional[TriageCompetitiveInfo] = None
    job_link: Optional[TriageJobLink] = None
    auto_response_text: Optional[str] = None
    triage_job_uuid: Optional[str] = None
    triaged_at: Optional[str] = None
    external: Optional[TriageExternalInfo] = None


def build_triage_verdict(db, idea) -> TriageVerdict:
    """Build a TriageVerdict from a persisted Idea row."""
    from app.models.idea import Idea, IdeaStatus

    duplicate = None
    if idea.duplicate_of_idea_id:
        target = db.query(Idea).get(idea.duplicate_of_idea_id)
        duplicate = TriageDuplicateInfo(
            duplicate_of_idea_id=idea.duplicate_of_idea_id,
            duplicate_of_title=target.title if target else None,
            similarity_score=idea.similarity_score,
        )

    context = idea.competitive_context or {}
    feature_exists = None
    if context.get("existing_feature"):
        ef = context["existing_feature"]
        feature_exists = TriageFeatureExistsInfo(
            feature_name=ef.get("feature_name"),
            feature_description=ef.get("feature_description"),
            similarity_score=ef.get("similarity_score"),
            source_url=ef.get("source_url"),
        )

    competitive = None
    if context.get("competitors_with_feature") or context.get("competitive_urgency"):
        competitive = TriageCompetitiveInfo(
            competitors_with_feature=list(context.get("competitors_with_feature") or []),
            competitive_urgency=context.get("competitive_urgency"),
        )

    job_link = None
    if idea.job_id_key:
        from app.models.competitor_intelligence import ProductJob
        pj = db.query(ProductJob).filter(
            ProductJob.product_id == idea.product_id,
            ProductJob.job_id_key == idea.job_id_key,
        ).first()
        job_link = TriageJobLink(
            job_id_key=idea.job_id_key,
            job_statement=pj.statement if pj else None,
        )

    external = None
    if idea.external_id and idea.external_source:
        external = TriageExternalInfo(
            external_id=idea.external_id,
            external_source=idea.external_source,
        )

    triage_job = idea.triage_job
    return TriageVerdict(
        idea_id=idea.id,
        triaged=idea.status != IdeaStatus.PENDING,
        status=idea.status.value if idea.status else "pending",
        is_active=bool(idea.is_active),
        recommendation=idea.triage_recommendation,
        confidence=idea.triage_confidence,
        reasoning=idea.triage_reasoning,
        category=idea.category,
        auto_categorized=bool(idea.auto_categorized),
        jtbd_statement=idea.jtbd_statement,
        duplicate=duplicate,
        feature_exists=feature_exists,
        competitive=competitive,
        job_link=job_link,
        auto_response_text=idea.auto_response_text,
        triage_job_uuid=triage_job.job_uuid if triage_job else None,
        triaged_at=(
            triage_job.completed_at.isoformat()
            if triage_job and triage_job.completed_at else None
        ),
        external=external,
    )
