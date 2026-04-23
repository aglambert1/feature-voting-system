"""Task-level integration tests for functional_audit_task.

Exercises the staged execution flow end-to-end with the agent LLM calls
patched out. Asserts:
- Both stages run in order
- Stage 2 receives Stage 1 output as input
- Merged result is persisted to CompetitorFunctionalReport
- output_data has the partial-write-ready envelope
- Progress milestones hit expected percentages
"""

from datetime import datetime
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.competitive_reports import CompetitorFunctionalReport
from app.models.competitor_intelligence import (
    CIProduct,
    ProductCompetitor,
)
from app.models.queue import JobStatus, JobType, QueueJob
from app.models.user import User, UserRole


@pytest.fixture(scope="function")
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def owner(db_session):
    u = User(
        email="audit-task@test.com",
        username="auditowner",
        hashed_password="h",
        full_name="Audit Owner",
        role=UserRole.PRODUCT_OWNER,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def product(db_session, owner):
    p = CIProduct(
        product_name="VoteFlow",
        product_description="Feature voting system",
        product_category="SaaS",
        created_by_user_id=owner.id,
        status="active",
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture
def competitor(db_session, product):
    c = ProductCompetitor(
        product_id=product.id,
        competitor_name="Canny",
        competitor_url="https://canny.io",
        status="active",
        # Pre-populate cache so the task skips Brave and the staged path runs
        # deterministically without network interaction.
        cached_search_results=[
            {"url": "https://canny.io/features", "title": "Features", "snippet": "x"},
        ],
        cached_search_at=datetime.utcnow(),
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def queued_audit_job(db_session, product, competitor, owner):
    j = QueueJob(
        job_type=JobType.FUNCTIONAL_AUDIT,
        status=JobStatus.QUEUED,
        product_id=product.id,
        user_id=owner.id,
        input_data={
            "competitor_id": competitor.id,
            "web_research_enabled": True,
            "source_urls": [],
        },
    )
    db_session.add(j)
    db_session.commit()
    db_session.refresh(j)
    return j


STAGE_1_RESULT = {
    "competitor_context": {
        "positioning": "Best feature voting tool",
        "core_differentiation": "AI-first roadmapping",
        "target_customer": "B2B SaaS product teams",
        "key_features": ["Voting", "Roadmap", "Changelog", "Analytics", "API"],
    },
    "functional_comparison": [
        {
            "feature_category": "Core",
            "competitor_feature_name": "Public Voting Board",
            "functional_description": "Users upvote features publicly.",
            "mapping_status": "Parity",
            "job_id": None,
        },
        {
            "feature_category": "Integrations",
            "competitor_feature_name": "Jira Sync",
            "functional_description": "Bi-directional Jira issue sync.",
            "mapping_status": "Gap",
            "job_id": None,
        },
    ],
    "technical_constraints": {
        "integrations": ["Jira", "Slack"],
        "api_capabilities": "REST API with webhooks",
        "platform_requirements": "Web app",
        "additional_notes": None,
    },
}

STAGE_2_RESULT = {
    "job_assessments": [],
    "evidence_citations": [],
    "gaps_deep_dive": [
        {
            "feature_name": "Jira Sync",
            "user_problem": "Teams can't keep roadmap and engineering in sync.",
            "evidence": "From docs: bi-directional issue sync.",
        },
    ],
}


def _patch_db_and_agent(db_session):
    """Context manager factory that wires the test DB + patches the agent's LLM calls.

    Returns a list of context managers to `enter` in sequence. Using a factory
    (rather than a single contextmanager) keeps the call-order readable at the
    test site.
    """
    # 1. Route the task's SessionLocal to our test DB
    session_patch = patch(
        "app.queue.tasks.SessionLocal",
        return_value=db_session,
    )
    # 2. Patch execute_stage_1/2 on the real agent class so no LLM is called
    stage_1_patch = patch(
        "app.agents.functional_audit_agent.CompetitorFunctionalAuditAgent.execute_stage_1",
        return_value=STAGE_1_RESULT,
    )
    stage_2_patch = patch(
        "app.agents.functional_audit_agent.CompetitorFunctionalAuditAgent.execute_stage_2",
        return_value=STAGE_2_RESULT,
    )
    # 3. LLMService is instantiated in the task but never called once execute_*
    #    is mocked; patch it to avoid any Anthropic key validation side effects.
    llm_patch = patch("app.queue.tasks.LLMService")

    return [session_patch, stage_1_patch, stage_2_patch, llm_patch]


def _run_task_with_patches(db_session, job_id, extra_patches=None):
    """Invoke functional_audit_task with the standard patches applied.

    Celery's @shared_task exposes the underlying function on `.run`; calling
    `.run()` bypasses the task registry and executes inline, which is what
    we want for unit tests.
    """
    from app.queue.tasks import functional_audit_task

    patches = _patch_db_and_agent(db_session)
    if extra_patches:
        patches.extend(extra_patches)
    for p in patches:
        p.start()
    try:
        # .run() is Celery's recommended entry point for synchronous invocation.
        return functional_audit_task.run(job_id)
    finally:
        for p in reversed(patches):
            p.stop()


class TestStagedAuditTask:
    def test_both_stages_run_and_result_persisted(
        self, db_session, product, competitor, queued_audit_job
    ):
        # Capture IDs before running the task, since the task closes its
        # db session in a finally block and detaches ORM instances.
        competitor_id = competitor.id
        competitor_name = competitor.competitor_name

        output = _run_task_with_patches(db_session, queued_audit_job.id)

        # Downstream top-level keys preserved for existing consumers.
        assert output["report_id"] is not None
        assert output["competitor_id"] == competitor_id
        assert output["competitor_name"] == competitor_name
        assert output["features_compared"] == len(STAGE_1_RESULT["functional_comparison"])
        assert output["gaps_identified"] == len(STAGE_2_RESULT["gaps_deep_dive"])

        # Report row contains merged Stage 1 + Stage 2 content.
        db_session.expire_all()
        report = db_session.query(CompetitorFunctionalReport).filter(
            CompetitorFunctionalReport.id == output["report_id"]
        ).one()
        assert report.competitor_context["positioning"] == "Best feature voting tool"
        assert len(report.functional_comparison) == 2
        assert len(report.gaps_deep_dive) == 1
        assert report.technical_constraints["api_capabilities"] == "REST API with webhooks"

    def test_output_data_has_partial_write_ready_envelope(
        self, db_session, product, competitor, queued_audit_job
    ):
        """output_data should include stages_completed + raw stage outputs so a
        future follow-up can add mid-flight partial writes without schema work."""
        output = _run_task_with_patches(db_session, queued_audit_job.id)

        assert output["stages_completed"] == ["stage_1", "stage_2"]
        assert output["stage_1_output"] == STAGE_1_RESULT
        assert output["stage_2_output"] == STAGE_2_RESULT

        # Also verify it lands on the QueueJob for polling consumers.
        db_session.expire_all()
        job = db_session.query(QueueJob).filter(QueueJob.id == queued_audit_job.id).one()
        assert job.output_data["stages_completed"] == ["stage_1", "stage_2"]

    def test_stage2_receives_stage1_output(
        self, db_session, product, competitor, queued_audit_job
    ):
        """Stage 2 must be called with `stage_1_output` in its input so it can
        anchor its analysis on Stage 1's context."""
        calls = {"stage_1_arg": None, "stage_2_arg": None}

        def capture_stage_1(self, input_data, **kwargs):
            calls["stage_1_arg"] = input_data
            return STAGE_1_RESULT

        def capture_stage_2(self, input_data, **kwargs):
            calls["stage_2_arg"] = input_data
            return STAGE_2_RESULT

        with patch("app.queue.tasks.SessionLocal", return_value=db_session), \
             patch("app.queue.tasks.LLMService"), \
             patch(
                 "app.agents.functional_audit_agent.CompetitorFunctionalAuditAgent.execute_stage_1",
                 new=capture_stage_1,
             ), \
             patch(
                 "app.agents.functional_audit_agent.CompetitorFunctionalAuditAgent.execute_stage_2",
                 new=capture_stage_2,
             ):
            from app.queue.tasks import functional_audit_task
            functional_audit_task.run(queued_audit_job.id)

        assert calls["stage_1_arg"] is not None, "Stage 1 was not invoked"
        assert calls["stage_2_arg"] is not None, "Stage 2 was not invoked"
        # Stage 1's input must NOT include stage_1_output (it hasn't run yet)
        assert "stage_1_output" not in calls["stage_1_arg"]
        # Stage 2's input MUST include stage_1_output (conditioning context)
        assert calls["stage_2_arg"].get("stage_1_output") == STAGE_1_RESULT

    def test_updates_competitive_agent_config_last_run(
        self, db_session, product, competitor, queued_audit_job
    ):
        """Manual audits must update CompetitiveAgentConfig.deep_analysis_last_run
        so the product-level 'last run' UI indicator reflects manual runs, not
        just scheduled-mode runs. Regression for the 'never run' bug."""
        from app.models.competitive_agent import CompetitiveAgentConfig

        config = CompetitiveAgentConfig(
            product_id=product.id,
            enabled=False,
            deep_analysis_last_run=None,
        )
        db_session.add(config)
        db_session.commit()
        config_id = config.id

        _run_task_with_patches(db_session, queued_audit_job.id)

        db_session.expire_all()
        refreshed = db_session.query(CompetitiveAgentConfig).filter(
            CompetitiveAgentConfig.id == config_id
        ).one()
        assert refreshed.deep_analysis_last_run is not None

    def test_progress_milestones_hit_expected_percentages(
        self, db_session, product, competitor, queued_audit_job
    ):
        """Progress should walk through Stage 1 -> Stage 2 -> finalize."""
        from app.services.queue_service import QueueService
        real_update_progress = QueueService.update_progress
        recorded: list[tuple[float, str]] = []

        def tracking_update_progress(self, job_id, pct, message=None):
            recorded.append((pct, message or ""))
            return real_update_progress(self, job_id, pct, message)

        with patch.object(QueueService, "update_progress", tracking_update_progress):
            _run_task_with_patches(db_session, queued_audit_job.id)

        percentages = [p for p, _ in recorded]
        messages = [m for _, m in recorded]

        # Stage boundaries — explicit checkpoints the plan calls out
        assert 30.0 in percentages, "Missing Stage 1 start milestone at 30%"
        assert 50.0 in percentages, "Missing Stage 1 -> Stage 2 handoff at 50%"
        assert 75.0 in percentages, "Missing Stage 2 finalize milestone at 75%"
        assert 85.0 in percentages, "Missing report-generation milestone at 85%"

        # Stage 1 -> Stage 2 handoff message should mention that context is ready
        assert any(
            "context ready" in m.lower() or "job assessments" in m.lower()
            for m in messages
        )
