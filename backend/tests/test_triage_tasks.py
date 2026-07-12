"""Characterization tests for the two triage Celery tasks.

These pin the observable behavior of ``triage_idea_task`` and
``submit_and_triage_idea_task`` BEFORE the shared-core extraction, so the
refactor can be proven behavior-preserving. Mocks sit at the LLM/embedding
boundary only — similarity detection, vector storage, job linkage, and status
logic all run for real — so the pins survive internal restructuring.

Deliberately pinned asymmetries between the two tasks (do not "fix" these in
a refactor without a conscious decision):
- Only triage_idea_task writes IdeaStatusHistory (when auto-respond is on).
- Only triage_idea_task calls _maybe_suggest_need.
- Feature-match kwargs differ: limit=3 vs similarity_threshold=0.80.
- Progress sequences and output envelopes differ.
"""

from unittest.mock import patch

import pytest
from sqlalchemy import text

from app.models.competitor_intelligence import CIProduct
from app.models.competitive_reports import CompetitorFunctionalReport
from app.models.idea import Idea, IdeaStatus, SourceType
from app.models.idea_status_history import IdeaStatusHistory
from app.models.pm_review import PMReviewQueue, ReviewQueueType
from app.models.queue import JobStatus, JobType
from app.models.synthesis import SynthesizedOpportunity
from app.models.user import User, UserRole
from app.services.queue_service import QueueService


# ---------------------------------------------------------------------------
# Canned agent output (IdeaTriageOutput.model_dump() shape)
# ---------------------------------------------------------------------------

def agent_result(action="review", confidence=0.7, existing_feature=None,
                 competitors=None, urgency="low"):
    return {
        "idea_summary": "A test idea about exporting data.",
        "jtbd_statement": "When analyzing accounts, I want to export data, so I can report on it.",
        "category": "Reporting",
        "category_confidence": 0.9,
        "similar_ideas_analysis": "No similar ideas found",
        "competitive_context": {
            "competitors_with_feature": competitors if competitors is not None else ["Agent Echo Co"],
            "competitive_urgency": urgency,
            "competitor_count": len(competitors) if competitors else 1,
            "total_competitors_analyzed": 2,
            "urgency_reasoning": "Some reasoning",
            "market_timing_notes": None,
        },
        "existing_feature_info": existing_feature,
        "auto_response_text": "Thanks for your idea! We are reviewing it.",
        "recommendation": {
            "action": action,
            "confidence": confidence,
            "reasoning": "Test reasoning for the recommendation.",
            "merge_target_id": None,
        },
    }


FAKE_EMBEDDING = [0.03] * 1024


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def po(db_session):
    user = User(
        email="triage-po@example.com", username="triagepo",
        hashed_password="x", full_name="Triage PO", role=UserRole.PRODUCT_OWNER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def product(db_session, po):
    p = CIProduct(
        product_name="Triage Test Product",
        product_description="A product for triage characterization tests",
        product_category="Testing",
        created_by_user_id=po.id,
        status="active",
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture
def vec_tables(db_session):
    """Ensure sqlite-vec virtual tables exist on the test engine (SQLite only).

    App startup normally creates these; the test engine only runs
    Base.metadata.create_all. On PG, conftest adds the ideas.embedding column
    instead and VectorService uses pgvector.
    """
    if db_session.bind.dialect.name == "sqlite":
        db_session.execute(text(
            "CREATE VIRTUAL TABLE IF NOT EXISTS vec_ideas "
            "USING vec0(idea_id INTEGER PRIMARY KEY, embedding FLOAT[1024])"
        ))
        db_session.execute(text(
            "CREATE VIRTUAL TABLE IF NOT EXISTS vec_product_features "
            "USING vec0(feature_id INTEGER PRIMARY KEY, embedding FLOAT[1024])"
        ))
        db_session.commit()


def make_idea(db_session, product, po, *, source_type=SourceType.CUSTOMER_SUBMISSION,
              source_metadata=None, title="Export data to CSV"):
    idea = Idea(
        title=title,
        what_description="Ability to export account data to CSV",
        why_description="Needed for offline analysis",
        use_case_description="Analyst exports monthly",
        product_id=product.id,
        submitter_id=po.id,
        source_type=source_type,
        source_metadata=source_metadata,
        status=IdeaStatus.PENDING,
        is_active=False,
    )
    db_session.add(idea)
    db_session.commit()
    db_session.refresh(idea)
    return idea


def make_triage_job(db_session, product, idea):
    job = QueueService(db_session).create_job(
        job_type=JobType.IDEA_TRIAGE,
        input_data={"idea_id": idea.id},
        product_id=product.id,
    )
    return job


# ---------------------------------------------------------------------------
# Patch harness
# ---------------------------------------------------------------------------

def run_task(db_session, task, job_id, result=None, progress_log=None,
             structure_result=None):
    """Run a triage task inline with LLM/embedding boundary patches."""
    result = result if result is not None else agent_result()

    real_update_progress = QueueService.update_progress

    def recording_update_progress(self, job_id_, pct, msg):
        if progress_log is not None:
            progress_log.append((pct, msg))
        return real_update_progress(self, job_id_, pct, msg)

    patches = [
        patch("app.queue.helpers.SessionLocal", return_value=db_session),
        patch("app.agents.idea_triage.IdeaTriageAgent.execute", return_value=result),
        patch("app.queue.triage_tasks.LLMService"),
        patch("app.services.similarity_detector._generate_embedding",
              return_value=FAKE_EMBEDDING),
        patch("app.services.embedding_service.generate_embedding",
              return_value=FAKE_EMBEDDING),
        patch.object(QueueService, "update_progress", recording_update_progress),
    ]
    if structure_result is not None:
        # Freeform submissions route through the normalizer's LLM structuring;
        # the normalizer receives the task's (mocked) LLMService instance.
        llm_patch = patches[2]
        started = [p.start() for p in patches]
        started[2].return_value.structure_idea.return_value = structure_result
        try:
            return task.run(job_id)
        finally:
            for p in reversed(patches):
                p.stop()

    for p in patches:
        p.start()
    try:
        return task.run(job_id)
    finally:
        for p in reversed(patches):
            p.stop()


TRIAGE_ENVELOPE_KEYS = {
    "idea_id", "status", "is_active", "triage_confidence",
    "triage_recommendation", "category", "has_duplicates", "has_similar",
    "similar_count", "duplicate_of_idea_id", "competitors_with_feature",
    "existing_feature_match", "existing_feature_info", "auto_response_generated",
    "verdict",
}

SUBMIT_ENVELOPE_KEYS = {
    "idea_id", "title", "source_type", "category", "status", "is_active",
    "triage_confidence", "triage_recommendation", "has_duplicates",
    "has_similar", "duplicate_of_idea_id", "competitors_with_feature",
    "existing_feature_match", "auto_response_text", "verdict",
}


# ---------------------------------------------------------------------------
# triage_idea_task characterization
# ---------------------------------------------------------------------------

class TestTriageIdeaTaskCharacterization:
    def test_customer_idea_auto_respond_off(self, db_session, product, po, vec_tables):
        from app.queue.triage_tasks import triage_idea_task

        idea = make_idea(db_session, product, po)
        job = make_triage_job(db_session, product, idea)
        idea_id, job_id, job_db_id = idea.id, job.id, job.id

        output = run_task(db_session, triage_idea_task, job_id)

        assert set(output.keys()) == TRIAGE_ENVELOPE_KEYS
        assert output["status"] == "needs_review"  # auto-respond off => always NEEDS_REVIEW
        assert output["is_active"] is False
        assert output["triage_recommendation"] == "review"
        assert output["has_duplicates"] is False
        assert output["similar_count"] == 0
        assert output["existing_feature_match"] is False
        assert output["existing_feature_info"] is None
        assert output["auto_response_generated"] is True
        # Envelope echoes the AGENT's competitor list (not the persisted one)
        assert output["competitors_with_feature"] == ["Agent Echo Co"]

        idea = db_session.query(Idea).get(idea_id)
        assert idea.status == IdeaStatus.NEEDS_REVIEW
        assert idea.is_active is False
        assert idea.triage_confidence == 0.7
        assert idea.triage_reasoning == "Test reasoning for the recommendation."
        assert idea.triage_recommendation == "review"
        assert idea.triage_job_id == job_db_id
        assert idea.category == "Reporting"
        assert idea.auto_categorized is True
        assert idea.jtbd_statement.startswith("When analyzing accounts")
        assert idea.jtbd_embedding is not None
        assert idea.auto_response_text == "Thanks for your idea! We are reviewing it."
        assert idea.competitive_context["competitors_with_feature"] == ["Agent Echo Co"]
        assert idea.competitive_context["competitive_urgency"] == "low"
        assert idea.job_id_key is None  # no ProductJobs exist
        assert idea.duplicate_of_idea_id is None

        # No status history when auto-respond is off
        assert db_session.query(IdeaStatusHistory).filter_by(idea_id=idea_id).count() == 0

        # One NEED_SUGGESTION queue item (jtbd embedding set, no jobs => no_match)
        suggestions = db_session.query(PMReviewQueue).filter(
            PMReviewQueue.queue_type == ReviewQueueType.NEED_SUGGESTION
        ).all()
        assert len(suggestions) == 1
        assert suggestions[0].item_id == idea_id

        job = db_session.query(type(job)).get(job_db_id) if False else None
        from app.models.queue import QueueJob
        job_row = db_session.query(QueueJob).get(job_id)
        assert job_row.status == JobStatus.SUCCESS
        assert job_row.output_data == output

    def test_customer_idea_auto_respond_on_approve(self, db_session, product, po, vec_tables):
        from app.queue.triage_tasks import triage_idea_task

        product.idea_triage_auto_enabled = True
        product.idea_triage_auto_threshold = 0.9
        db_session.commit()

        idea = make_idea(db_session, product, po)
        job = make_triage_job(db_session, product, idea)
        idea_id, job_id = idea.id, job.id

        output = run_task(db_session, triage_idea_task, job_id,
                          result=agent_result(action="approve", confidence=0.95))

        assert output["status"] == "accepted"
        assert output["is_active"] is True

        idea = db_session.query(Idea).get(idea_id)
        assert idea.status == IdeaStatus.ACCEPTED
        assert idea.is_active is True

        history = db_session.query(IdeaStatusHistory).filter_by(idea_id=idea_id).all()
        assert len(history) == 1
        assert history[0].is_automated is True
        assert history[0].change_source == "agent_triage"
        assert history[0].previous_status == IdeaStatus.PENDING
        assert history[0].new_status == IdeaStatus.ACCEPTED
        assert history[0].confidence == 95

    def test_merge_action_persists_duplicate_info(self, db_session, product, po, vec_tables):
        from app.queue.triage_tasks import triage_idea_task
        from app.services.similarity_detector import SimilarityDetectorService

        # Seed a near-duplicate idea whose stored embedding equals the mocked
        # query embedding => similarity 1.0 => detect_duplicates best_match.
        existing = make_idea(db_session, product, po, title="Export account data as CSV")
        existing.is_active = True  # find_similar only surfaces active ideas
        with patch("app.services.similarity_detector._generate_embedding",
                   return_value=FAKE_EMBEDDING):
            SimilarityDetectorService(db_session).store_idea_embedding(existing)
        db_session.commit()

        idea = make_idea(db_session, product, po)
        job = make_triage_job(db_session, product, idea)
        idea_id, existing_id, job_id = idea.id, existing.id, job.id

        output = run_task(db_session, triage_idea_task, job_id,
                          result=agent_result(action="merge", confidence=0.9))

        assert output["has_duplicates"] is True
        assert output["duplicate_of_idea_id"] == existing_id

        idea = db_session.query(Idea).get(idea_id)
        assert idea.duplicate_of_idea_id == existing_id
        assert idea.similarity_score is not None
        # Auto-respond off => status still NEEDS_REVIEW even though action=merge
        assert idea.status == IdeaStatus.NEEDS_REVIEW

    def test_gap_idea_uses_authoritative_competitor_and_default_response(
        self, db_session, product, po, vec_tables
    ):
        from app.queue.triage_tasks import triage_idea_task

        from app.models.competitor_intelligence import ProductCompetitor
        competitor = ProductCompetitor(
            product_id=product.id, competitor_name="Rival Co",
            competitor_url="https://rival.co", status="active",
        )
        db_session.add(competitor)
        db_session.flush()
        report = CompetitorFunctionalReport(
            product_competitor_id=competitor.id, product_id=product.id, report_version=1,
        )
        db_session.add(report)
        db_session.commit()

        idea = make_idea(
            db_session, product, po,
            source_type=SourceType.COMPETITOR_AUTOMATED,
            source_metadata={
                "source": "competitor_gap",
                "competitor_id": 123,
                "competitor_name": "Rival Co",
                "feature_name": "CSV Export",
                "evidence_ids": [],
                "functional_report_id": report.id,
            },
        )
        job = make_triage_job(db_session, product, idea)
        idea_id, job_id = idea.id, job.id

        run_task(db_session, triage_idea_task, job_id)

        idea = db_session.query(Idea).get(idea_id)
        # Authoritative single competitor_name wins over the agent's list
        assert idea.competitive_context["competitors_with_feature"] == ["Rival Co"]
        # Competitor ideas get the default source-referencing response
        assert idea.auto_response_text == "From analysis of Rival Co"

    def test_synthesis_idea_preserves_authoritative_job_key(
        self, db_session, product, po, vec_tables
    ):
        from app.queue.triage_tasks import triage_idea_task

        from app.models.synthesis import SynthesisRun
        run = SynthesisRun(product_id=product.id, status="completed")
        db_session.add(run)
        db_session.flush()
        opp = SynthesizedOpportunity(
            synthesis_run_id=run.id,
            product_id=product.id,
            opportunity_name="Export data to CSV",
            priority_score=88,
            source_count=1,
            investment_tier="strategic",
            job_id_key="j3",
            sources=["competitive"],
        )
        db_session.add(opp)
        db_session.commit()

        idea = make_idea(
            db_session, product, po,
            source_type=SourceType.COMPETITOR_AUTOMATED,
            source_metadata={
                "synthesis_report_id": 1,
                "synthesis_report_version": 1,
                "feature_name": "Export data to CSV",
                "priority_score": 88,
                "sources": ["competitive"],
                "job_id_key": "j3",
                "investment_tier": "strategic",
                "competitors_with_feature": ["Comp A"],
                "competitor_names": ["Comp A"],
            },
        )
        job = make_triage_job(db_session, product, idea)
        idea_id, job_id = idea.id, job.id

        run_task(db_session, triage_idea_task, job_id)

        idea = db_session.query(Idea).get(idea_id)
        # Authoritative job link preserved even with zero ProductJob rows
        assert idea.job_id_key == "j3"
        # Authoritative competitor list wins over the agent's
        assert idea.competitive_context["competitors_with_feature"] == ["Comp A"]
        # Authoritative link present => no NEED_SUGGESTION noise
        assert db_session.query(PMReviewQueue).filter(
            PMReviewQueue.queue_type == ReviewQueueType.NEED_SUGGESTION
        ).count() == 0

    def test_progress_sequence(self, db_session, product, po, vec_tables):
        from app.queue.triage_tasks import triage_idea_task

        idea = make_idea(db_session, product, po)
        job = make_triage_job(db_session, product, idea)

        progress = []
        run_task(db_session, triage_idea_task, job.id, progress_log=progress)

        assert progress == [
            (10.0, "Finding similar ideas..."),
            (30.0, "Finding competitive matches..."),
            (40.0, "Checking existing product features..."),
            (50.0, "Running AI triage analysis..."),
            (80.0, "Updating idea with triage results..."),
            (90.0, "Storing idea embedding..."),
        ]

    def test_missing_idea_id_fails_job(self, db_session, product, po, vec_tables):
        from app.models.queue import QueueJob
        from app.queue.triage_tasks import triage_idea_task

        job = QueueService(db_session).create_job(
            job_type=JobType.IDEA_TRIAGE, input_data={}, product_id=product.id,
        )
        job_id = job.id

        with pytest.raises(ValueError, match="No idea_id"):
            run_task(db_session, triage_idea_task, job_id)

        job_row = db_session.query(QueueJob).get(job_id)
        assert job_row.status == JobStatus.FAILURE
        assert "No idea_id" in job_row.error_message

    def test_task_identity(self):
        from app.queue.triage_tasks import triage_idea_task

        assert triage_idea_task.name == "app.queue.triage_tasks.triage_idea_task"
        assert triage_idea_task.soft_time_limit == 300


# ---------------------------------------------------------------------------
# submit_and_triage_idea_task characterization
# ---------------------------------------------------------------------------

class TestSubmitAndTriageTaskCharacterization:
    def _make_submit_job(self, db_session, product, po, raw_input):
        return QueueService(db_session).create_job(
            job_type=JobType.IDEA_TRIAGE,
            input_data={
                "raw_input": raw_input,
                "source_type": "customer_submission",
            },
            product_id=product.id,
            user_id=po.id,
        )

    def test_structured_raw_input(self, db_session, product, po, vec_tables):
        from app.queue.triage_tasks import submit_and_triage_idea_task

        product.idea_triage_auto_enabled = True  # pin: STILL no history rows
        db_session.commit()

        po_id = po.id
        job = self._make_submit_job(db_session, product, po, {
            "product_id": product.id,
            "submitter_id": po.id,
            "title": "Export data to CSV",
            "what_description": "Ability to export account data",
            "why_description": "Offline analysis",
            "use_case_description": "Monthly reporting",
        })
        job_id = job.id

        output = run_task(db_session, submit_and_triage_idea_task, job_id,
                          result=agent_result(action="approve", confidence=0.95))

        assert set(output.keys()) == SUBMIT_ENVELOPE_KEYS
        assert output["title"] == "Export data to CSV"
        assert output["source_type"] == "customer_submission"
        assert output["status"] == "accepted"
        assert output["auto_response_text"] == "Thanks for your idea! We are reviewing it."

        idea = db_session.query(Idea).get(output["idea_id"])
        assert idea.source_type == SourceType.CUSTOMER_SUBMISSION
        assert idea.submitter_id == po_id
        assert idea.source_metadata == {"submission_type": "structured"}
        assert idea.status == IdeaStatus.ACCEPTED

        # Pinned asymmetry: submit task NEVER writes status history...
        assert db_session.query(IdeaStatusHistory).filter_by(idea_id=idea.id).count() == 0
        # ...and never creates need suggestions.
        assert db_session.query(PMReviewQueue).filter(
            PMReviewQueue.queue_type == ReviewQueueType.NEED_SUGGESTION
        ).count() == 0

    def test_freeform_raw_input_structures_via_llm(self, db_session, product, po, vec_tables):
        from app.queue.triage_tasks import submit_and_triage_idea_task

        job = self._make_submit_job(db_session, product, po, {
            "product_id": product.id,
            "submitter_id": po.id,
            "freeform_text": "I really wish I could get my data out as a csv file somehow",
        })

        output = run_task(
            db_session, submit_and_triage_idea_task, job.id,
            structure_result={
                "title": "CSV data export",
                "what": "Export data as CSV",
                "why": "Data portability",
                "use_case": "Analysis",
                "category": "Reporting",
            },
        )

        assert output["title"] == "CSV data export"
        idea = db_session.query(Idea).get(output["idea_id"])
        assert idea.source_metadata == {"submission_type": "freeform"}
        assert idea.auto_categorized is True

    def test_progress_sequence(self, db_session, product, po, vec_tables):
        from app.queue.triage_tasks import submit_and_triage_idea_task

        job = self._make_submit_job(db_session, product, po, {
            "product_id": product.id,
            "submitter_id": po.id,
            "title": "Export data to CSV",
            "what_description": "Ability to export account data",
            "why_description": "Offline analysis",
            "use_case_description": "Monthly reporting",
        })

        progress = []
        run_task(db_session, submit_and_triage_idea_task, job.id, progress_log=progress)

        assert progress == [
            (10.0, "Normalizing idea..."),
            (25.0, "Creating idea record..."),
            (40.0, "Finding similar ideas..."),
            (55.0, "Finding competitive matches..."),
            (60.0, "Checking for existing product features..."),
            (70.0, "Running AI triage analysis..."),
            (85.0, "Updating idea with triage results..."),
            (95.0, "Storing idea embedding..."),
        ]

    def test_task_identity(self):
        from app.queue.triage_tasks import submit_and_triage_idea_task

        assert submit_and_triage_idea_task.name == "app.queue.triage_tasks.submit_and_triage_idea_task"
        assert submit_and_triage_idea_task.soft_time_limit == 600
