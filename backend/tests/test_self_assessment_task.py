"""Task-level tests for self_assessment_task.

The task body previously never ran in tests, which let two signature errors ship: it built
LLMService(db=db) and passed product_id/user_id to agent.execute(). Both fail only when
the real constructors are called, so the patches here are autospec'd — a mock that accepts
any arguments would have passed against the broken code.
"""

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.competitive_reports import (
    CompetitorFunctionalReport,
    ProductSelfAssessment,
)
from app.models.competitor_intelligence import (
    CIProduct,
    JobImportance,
    JobType,
    ProductCompetitor,
    ProductJob,
)
from app.models.queue import JobStatus, JobType as QueueJobType, QueueJob
from app.models.user import User, UserRole


@pytest.fixture(scope="function")
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def owner(db_session):
    u = User(
        email="self-assess-task@test.com",
        username="selfassessowner",
        hashed_password="h",
        full_name="Self Assess Owner",
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
def job_map(db_session, product):
    job = ProductJob(
        product_id=product.id,
        job_id_key="j1",
        job_type=JobType.FUNCTIONAL,
        statement="When planning, I want to see demand, so I can prioritise",
        importance=JobImportance.HIGH,
    )
    db_session.add(job)
    db_session.commit()
    return job


@pytest.fixture
def audited_competitor(db_session, product):
    competitor = ProductCompetitor(
        product_id=product.id,
        competitor_name="Canny",
        tracked=True,
        status="active",
    )
    db_session.add(competitor)
    db_session.commit()
    report = CompetitorFunctionalReport(
        product_competitor_id=competitor.id,
        product_id=product.id,
        report_version=1,
        job_assessments=[
            {"job_id": "j1", "job_statement": "x", "competitor_score": 5},
        ],
    )
    db_session.add(report)
    db_session.commit()
    return report


@pytest.fixture
def queued_job(db_session, product, owner):
    job = QueueJob(
        job_type=QueueJobType.SELF_ASSESSMENT,
        status=JobStatus.QUEUED,
        product_id=product.id,
        user_id=owner.id,
        input_data={"product_id": product.id},
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


AGENT_RESULT = {
    "job_assessments": [
        {
            "job_id": "j1",
            "job_statement": "When planning, I want to see demand, so I can prioritise",
            "importance": "high",
            "score": 8,
            "confidence": "low",
            "score_rationale": "Voting board covers demand capture.",
        }
    ],
    "evidence_based": False,
    "assessment_summary": "Strong on demand capture.",
}


def _run_task(db_session, job_id):
    from app.queue.jtbd_tasks import self_assessment_task

    with patch("app.queue.jtbd_tasks.get_db", return_value=db_session), \
         patch("app.queue.jtbd_tasks.LLMService", autospec=True), \
         patch(
             "app.agents.self_assessment_agent.SelfAssessmentAgent.execute",
             autospec=True,
             return_value=AGENT_RESULT,
         ) as execute:
        output = self_assessment_task.run(job_id)
    return output, execute


class TestSelfAssessmentTask:
    def test_task_body_runs_and_stores_an_assessment(
        self, db_session, product, job_map, queued_job
    ):
        product_id, job_id = product.id, queued_job.id

        output, _ = _run_task(db_session, job_id)

        assert output["jobs_assessed"] == 1
        assessment = db_session.query(ProductSelfAssessment).filter(
            ProductSelfAssessment.product_id == product_id
        ).one()
        assert assessment.assessment_version == 1
        assert assessment.job_assessments[0]["score"] == 8
        assert assessment.queue_job_id == job_id
        # No independent evidence was supplied, whatever the model reported.
        assert assessment.evidence_based is False

    def test_agent_is_constructed_for_cost_tracking(
        self, db_session, product, owner, job_map, queued_job
    ):
        # product_id/user_id/job_id belong on the agent so cost rows are attributed;
        # execute() takes only the input.
        product_id, owner_id, job_uuid = product.id, owner.id, queued_job.job_uuid

        with patch("app.queue.jtbd_tasks.get_db", return_value=db_session), \
             patch("app.queue.jtbd_tasks.LLMService", autospec=True), \
             patch(
                 "app.agents.self_assessment_agent.SelfAssessmentAgent.execute",
                 autospec=True,
                 return_value=AGENT_RESULT,
             ) as execute:
            from app.queue.jtbd_tasks import self_assessment_task
            self_assessment_task.run(queued_job.id)

        agent = execute.call_args.args[0]
        assert (agent.product_id, agent.user_id, agent.job_id) == (
            product_id, owner_id, job_uuid
        )

    def test_output_budget_exceeds_the_agent_default(
        self, db_session, product, job_map, queued_job
    ):
        # A 12-job map overran the 4000-token default in prod, and this agent has no
        # concise-recovery prompt, so truncation fails the whole task.
        from app.config import settings

        _, execute = _run_task(db_session, queued_job.id)

        assert execute.call_args.kwargs["max_tokens"] > settings.max_tokens_default

    def test_competitor_positions_are_refreshed(
        self, db_session, product, job_map, audited_competitor, queued_job
    ):
        report_id = audited_competitor.id

        output, _ = _run_task(db_session, queued_job.id)

        assert output["competitor_reports_refreshed"] == 1
        report = db_session.get(CompetitorFunctionalReport, report_id)
        entry = report.job_assessments[0]
        assert entry["our_score"] == 8
        assert entry["system_position"] != "unknown"

    def test_version_increments_on_reassessment(
        self, db_session, product, owner, job_map, queued_job
    ):
        product_id, owner_id = product.id, owner.id
        _run_task(db_session, queued_job.id)

        second = QueueJob(
            job_type=QueueJobType.SELF_ASSESSMENT,
            status=JobStatus.QUEUED,
            product_id=product_id,
            user_id=owner_id,
            input_data={"product_id": product_id},
        )
        db_session.add(second)
        db_session.commit()
        _run_task(db_session, second.id)

        versions = [
            a.assessment_version
            for a in db_session.query(ProductSelfAssessment).order_by(
                ProductSelfAssessment.assessment_version
            )
        ]
        assert versions == [1, 2]
