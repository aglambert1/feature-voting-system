"""
Tool-level integration tests for MCP tools.

Verifies that permission checks are enforced at the tool level (not just
the helper), and that the evidence_add bug fix (removed undefined variables)
works end-to-end with mocked embedding/LLM services.
"""

import json
import uuid
from contextlib import contextmanager
from unittest.mock import patch, MagicMock

import pytest

from app.models.competitor_intelligence import (
    CIProduct,
    ProductCompetitor,
    ProductPermission,
    ProductPermissionLevel,
)
from app.models.evidence import Evidence, EvidenceType
from app.models.idea import Idea, IdeaStatus, SourceType
from app.models.queue import QueueJob, JobType, JobStatus
from app.models.idea_comment import IdeaComment
from app.models.idea_status_history import IdeaStatusHistory
from app.models.competitive_reports import CompetitorFunctionalReport
from app.models.pm_review import PMReviewQueue, ReviewQueueType, ReviewQueueStatus, ReviewQueuePriority
from app.models.synthesis import SynthesisRun, SynthesizedOpportunity
from app.models.user import User, UserRole


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def owner(db_session):
    user = User(
        email="owner@test.com", username="owner",
        hashed_password="h", full_name="Owner",
        role=UserRole.PRODUCT_OWNER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def viewer(db_session):
    user = User(
        email="viewer@test.com", username="viewer",
        hashed_password="h", full_name="Viewer",
        role=UserRole.VOTER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def outsider(db_session):
    """User with no access to any product."""
    user = User(
        email="outsider@test.com", username="outsider",
        hashed_password="h", full_name="Outsider",
        role=UserRole.VOTER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def product_a(db_session, owner):
    p = CIProduct(
        product_name="Product A", product_description="desc",
        product_category="Test", created_by_user_id=owner.id, status="active",
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture
def product_b(db_session, owner):
    p = CIProduct(
        product_name="Product B", product_description="desc",
        product_category="Test", created_by_user_id=owner.id, status="active",
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture
def viewer_access(db_session, product_a, viewer, owner):
    """Grant viewer VIEW access to product_a only."""
    perm = ProductPermission(
        product_id=product_a.id, user_id=viewer.id,
        permission_level=ProductPermissionLevel.VIEW,
        granted_by_user_id=owner.id,
    )
    db_session.add(perm)
    db_session.commit()
    return perm


@pytest.fixture
def competitor(db_session, product_a):
    c = ProductCompetitor(
        product_id=product_a.id, competitor_name="Rival Co",
        competitor_url="https://rival.co", status="active",
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def idea(db_session, product_a, viewer, viewer_access):
    i = Idea(
        title="Test Idea", what_description="desc",
        why_description="testing", use_case_description="tests",
        product_id=product_a.id, submitter_id=viewer.id,
        source_type=SourceType.CUSTOMER_SUBMISSION,
        status=IdeaStatus.ACCEPTED, is_active=True,
    )
    db_session.add(i)
    db_session.commit()
    db_session.refresh(i)
    return i


@pytest.fixture
def evidence_record(db_session, product_a):
    e = Evidence(
        product_id=product_a.id,
        evidence_type=EvidenceType.COMPETITIVE_INTEL,
        title="Rival launched X",
        content="Details about the launch",
        created_by="test",
    )
    db_session.add(e)
    db_session.commit()
    db_session.refresh(e)
    return e


@pytest.fixture
def job(db_session, product_a):
    j = QueueJob(
        job_uuid=str(uuid.uuid4()),
        job_type=JobType.FUNCTIONAL_AUDIT,
        status=JobStatus.SUCCESS,
        product_id=product_a.id,
    )
    db_session.add(j)
    db_session.commit()
    db_session.refresh(j)
    return j


# ---------------------------------------------------------------------------
# Helpers — patch get_session and get_mcp_user_id for tool calls
# ---------------------------------------------------------------------------

@contextmanager
def _mock_session(db_session):
    """Patch get_session everywhere it's imported so tool functions use the test DB.

    Since each tool module does `from mcp_server.db import get_session`,
    we patch the source module — but because Python caches the reference
    at import time, we also need to patch every tool module's local copy.
    """
    @contextmanager
    def fake_get_session():
        yield db_session

    patches = [
        patch("mcp_server.db.get_session", fake_get_session),
        patch("mcp_server.tools.product.get_session", fake_get_session),
        patch("mcp_server.tools.competitive.get_session", fake_get_session),
        patch("mcp_server.tools.ideas.get_session", fake_get_session),
        patch("mcp_server.tools.synthesis.get_session", fake_get_session),
        patch("mcp_server.tools.internal.get_session", fake_get_session),
        patch("mcp_server.tools.composite.get_session", fake_get_session),
        patch("mcp_server.tools.evidence.get_session", fake_get_session),
        patch("mcp_server.tools.jobs.get_session", fake_get_session),
        patch("mcp_server.job_wait.get_session", fake_get_session),
        patch("mcp_server.tools.pm_review.get_session", fake_get_session),
        patch("mcp_server.tools.monitoring.get_session", fake_get_session),
    ]
    for p in patches:
        p.start()
    try:
        yield
    finally:
        for p in patches:
            p.stop()


@contextmanager
def _patch_user(user_id):
    """Patch get_mcp_user_id everywhere it's imported."""
    patches = [
        patch("mcp_server.permissions.get_mcp_user_id", return_value=user_id),
        patch("mcp_server.tools.product.get_mcp_user_id", return_value=user_id),
        patch("mcp_server.tools.ideas.get_mcp_user_id", return_value=user_id),
        patch("mcp_server.tools.pm_review.get_mcp_user_id", return_value=user_id),
        patch("mcp_server.user_context.get_mcp_user_id", return_value=user_id),
    ]
    for p in patches:
        p.start()
    try:
        yield
    finally:
        for p in patches:
            p.stop()


# ---------------------------------------------------------------------------
# product_list — returns only permitted products
# ---------------------------------------------------------------------------

class TestProductList:
    def test_owner_sees_own_products(self, db_session, product_a, product_b, owner):
        from mcp_server.tools.product import product_list

        with _mock_session(db_session), _patch_user(owner.id):
            result = product_list()
            ids = {p["product_id"] for p in result["products"]}
            assert product_a.id in ids
            assert product_b.id in ids

    def test_viewer_sees_only_granted(self, db_session, product_a, product_b, viewer, viewer_access):
        from mcp_server.tools.product import product_list

        with _mock_session(db_session), _patch_user(viewer.id):
            result = product_list()
            ids = {p["product_id"] for p in result["products"]}
            assert product_a.id in ids
            assert product_b.id not in ids

    def test_outsider_sees_nothing(self, db_session, product_a, outsider):
        from mcp_server.tools.product import product_list

        with _mock_session(db_session), _patch_user(outsider.id):
            result = product_list()
            assert result["products"] == []


# ---------------------------------------------------------------------------
# product_get_context — VIEW required
# ---------------------------------------------------------------------------

class TestProductGetContext:
    def test_viewer_allowed(self, db_session, product_a, viewer, viewer_access):
        from mcp_server.tools.product import product_get_context

        with _mock_session(db_session), _patch_user(viewer.id):
            result = product_get_context(product_a.id)
            assert "error" not in result
            assert result["product_name"] == "Product A"

    def test_outsider_denied(self, db_session, product_a, outsider):
        from mcp_server.tools.product import product_get_context

        with _mock_session(db_session), _patch_user(outsider.id):
            result = product_get_context(product_a.id)
            assert "error" in result
            assert "VIEW" in result["error"]


# ---------------------------------------------------------------------------
# product_update_scoring — EDIT required
# ---------------------------------------------------------------------------

class TestProductUpdateScoring:
    def test_owner_allowed(self, db_session, product_a, owner):
        from mcp_server.tools.product import product_update_scoring

        with _mock_session(db_session), _patch_user(owner.id):
            result = product_update_scoring(product_a.id, '{}')
            assert "error" not in result

    def test_viewer_denied(self, db_session, product_a, viewer, viewer_access):
        from mcp_server.tools.product import product_update_scoring

        with _mock_session(db_session), _patch_user(viewer.id):
            result = product_update_scoring(product_a.id, '{}')
            assert "error" in result
            assert "EDIT" in result["error"]


# ---------------------------------------------------------------------------
# ci_get_competitor_list — VIEW required
# ---------------------------------------------------------------------------

class TestCiGetCompetitorList:
    def test_viewer_allowed(self, db_session, product_a, viewer, viewer_access, competitor):
        from mcp_server.tools.competitive import ci_get_competitor_list

        with _mock_session(db_session), _patch_user(viewer.id):
            result = ci_get_competitor_list(product_a.id)
            assert "error" not in result
            assert len(result["competitors"]) == 1

    def test_outsider_denied(self, db_session, product_a, outsider, competitor):
        from mcp_server.tools.competitive import ci_get_competitor_list

        with _mock_session(db_session), _patch_user(outsider.id):
            result = ci_get_competitor_list(product_a.id)
            assert "error" in result


# ---------------------------------------------------------------------------
# ideas_get_status — entity-level VIEW (resolves product_id from idea)
# ---------------------------------------------------------------------------

class TestIdeasGetStatus:
    def test_viewer_allowed(self, db_session, idea, viewer, viewer_access):
        from mcp_server.tools.ideas import ideas_get_status

        with _mock_session(db_session), _patch_user(viewer.id):
            result = ideas_get_status(idea.id)
            assert "error" not in result
            assert result["title"] == "Test Idea"

    def test_outsider_denied(self, db_session, idea, outsider):
        from mcp_server.tools.ideas import ideas_get_status

        with _mock_session(db_session), _patch_user(outsider.id):
            result = ideas_get_status(idea.id)
            assert "error" in result
            assert "VIEW" in result["error"]


# ---------------------------------------------------------------------------
# evidence_get — entity-level VIEW (resolves product_id from evidence)
# ---------------------------------------------------------------------------

class TestEvidenceGet:
    def test_viewer_allowed(self, db_session, evidence_record, viewer, viewer_access):
        from mcp_server.tools.evidence import evidence_get

        with _mock_session(db_session), _patch_user(viewer.id):
            result = evidence_get(evidence_record.id)
            assert "error" not in result
            assert result["title"] == "Rival launched X"

    def test_outsider_denied(self, db_session, evidence_record, outsider):
        from mcp_server.tools.evidence import evidence_get

        with _mock_session(db_session), _patch_user(outsider.id):
            result = evidence_get(evidence_record.id)
            assert "error" in result


# ---------------------------------------------------------------------------
# job_get_status — conditional VIEW (only if job has product_id)
# ---------------------------------------------------------------------------

class TestJobGetStatus:
    def test_viewer_allowed(self, db_session, job, viewer, viewer_access):
        from mcp_server.tools.jobs import job_get_status

        with _mock_session(db_session), _patch_user(viewer.id):
            result = job_get_status(job.job_uuid)
            assert "error" not in result
            assert result["status"] == "success"

    def test_outsider_denied(self, db_session, job, outsider):
        from mcp_server.tools.jobs import job_get_status

        with _mock_session(db_session), _patch_user(outsider.id):
            result = job_get_status(job.job_uuid)
            assert "error" in result


# ---------------------------------------------------------------------------
# job_wait helper — kickoff tools' optional wait_seconds behavior
# ---------------------------------------------------------------------------

class TestWaitForJob:
    def test_finished_job_returns_immediately(self, db_session, job):
        from mcp_server.job_wait import wait_for_job

        with _mock_session(db_session):
            result = wait_for_job(job.job_uuid, wait_seconds=30)
            assert result["status"] == "success"
            assert "waiting" not in result

    def test_not_found(self, db_session):
        from mcp_server.job_wait import wait_for_job

        with _mock_session(db_session):
            result = wait_for_job("nonexistent-uuid", wait_seconds=5)
            assert "error" in result

    def test_running_job_times_out_with_waiting_flag(self, db_session, product_a):
        import uuid as _uuid
        from mcp_server.job_wait import wait_for_job
        from app.models.queue import QueueJob, JobStatus, JobType

        running = QueueJob(
            job_uuid=str(_uuid.uuid4()),
            job_type=JobType.FUNCTIONAL_AUDIT,
            status=JobStatus.RUNNING,
            product_id=product_a.id,
        )
        db_session.add(running)
        db_session.commit()

        with _mock_session(db_session):
            # wait_seconds=0 → deadline already passed, returns promptly
            result = wait_for_job(running.job_uuid, wait_seconds=0)
            assert result["status"] == "running"
            assert result["waiting"] is True


class TestMaybeWait:
    def test_zero_wait_returns_queued_unchanged(self, db_session, job):
        from mcp_server.job_wait import maybe_wait

        queued = {"job_uuid": job.job_uuid, "status": "queued", "message": "m"}
        with _mock_session(db_session):
            result = maybe_wait(queued, wait_seconds=0)
        assert result == queued  # untouched, no DB hit needed

    def test_positive_wait_merges_final_status(self, db_session, job):
        from mcp_server.job_wait import maybe_wait

        queued = {"job_uuid": job.job_uuid, "status": "queued", "message": "m"}
        with _mock_session(db_session):
            result = maybe_wait(queued, wait_seconds=30)
        # job fixture is SUCCESS → merged status wins, queued context preserved
        assert result["status"] == "success"
        assert result["message"] == "m"
        assert result["job_uuid"] == job.job_uuid

    def test_wait_error_preserves_queued_context(self, db_session):
        from mcp_server.job_wait import maybe_wait

        queued = {"job_uuid": "missing-uuid", "status": "queued", "message": "m"}
        with _mock_session(db_session):
            result = maybe_wait(queued, wait_seconds=5)
        # dispatch succeeded; wait failed — keep job_uuid, surface wait_error
        assert result["job_uuid"] == "missing-uuid"
        assert "wait_error" in result


# ---------------------------------------------------------------------------
# evidence_add — regression test for the undefined variable bug fix
# Mocks embedding + LLM services so no external APIs are needed.
# ---------------------------------------------------------------------------

class TestEvidenceAdd:
    def test_no_crash_and_creates_record(self, db_session, product_a, owner):
        """evidence_add must not raise NameError (the old bug) and should
        create a valid Evidence record with JTBD statement populated."""
        from mcp_server.tools.evidence import evidence_add

        mock_embedding = [0.001 * i for i in range(1024)]
        mock_jtbd = "When evaluating tools, I want to compare features, so I can make informed decisions"

        with _mock_session(db_session), \
             _patch_user(owner.id), \
             patch("app.services.embedding_service.generate_embedding", return_value=mock_embedding), \
             patch("app.services.evidence_service.extract_jtbd", return_value=mock_jtbd):

            result = evidence_add(
                product_id=product_a.id,
                evidence_type="competitive_intel",
                title="Rival launched new feature",
                content="Rival Co announced a new AI-powered triage feature today.",
                source_url="https://rival.co/blog/ai-triage",
                source_description="Rival blog",
            )

            assert "error" not in result
            assert result["evidence_id"] is not None
            assert result["title"] == "Rival launched new feature"
            assert result["jtbd_statement"] == mock_jtbd
            assert result["has_embedding"] is True
            assert result["source_url"] == "https://rival.co/blog/ai-triage"

    def test_edit_permission_required(self, db_session, product_a, viewer, viewer_access):
        """evidence_add requires EDIT, not just VIEW."""
        from mcp_server.tools.evidence import evidence_add

        with _mock_session(db_session), _patch_user(viewer.id):
            result = evidence_add(
                product_id=product_a.id,
                evidence_type="competitive_intel",
                title="Test", content="Test content",
            )
            assert "error" in result
            assert "EDIT" in result["error"]


# ===========================================================================
# Phase 2: Product CRUD + PO Settings
# ===========================================================================

class TestProductCreate:
    def test_creates_product(self, db_session, owner):
        from mcp_server.tools.product import product_create

        with _mock_session(db_session), _patch_user(owner.id):
            result = product_create("New Product", "A detailed description for testing", "Testing")
            assert "error" not in result
            assert result["product_id"] is not None
            assert result["product_name"] == "New Product"

    def test_rejects_duplicate_name(self, db_session, product_a, owner):
        from mcp_server.tools.product import product_create

        with _mock_session(db_session), _patch_user(owner.id):
            result = product_create("Product A", "A detailed description for testing")
            assert "error" in result
            assert "already exists" in result["error"]

    def test_rejects_short_description(self, db_session, owner):
        from mcp_server.tools.product import product_create

        with _mock_session(db_session), _patch_user(owner.id):
            result = product_create("Test", "short")
            assert "error" in result
            assert "10 characters" in result["error"]


class TestProductUpdate:
    def test_owner_can_update(self, db_session, product_a, owner):
        from mcp_server.tools.product import product_update

        with _mock_session(db_session), _patch_user(owner.id):
            result = product_update(product_a.id, name="Renamed Product")
            assert "error" not in result
            assert result["product_name"] == "Renamed Product"

    def test_viewer_denied(self, db_session, product_a, viewer, viewer_access):
        from mcp_server.tools.product import product_update

        with _mock_session(db_session), _patch_user(viewer.id):
            result = product_update(product_a.id, name="Nope")
            assert "error" in result
            assert "EDIT" in result["error"]


class TestProductDelete:
    def test_owner_can_delete(self, db_session, product_a, owner):
        from mcp_server.tools.product import product_delete

        with _mock_session(db_session), _patch_user(owner.id):
            result = product_delete(product_a.id)
            assert "error" not in result
            assert result["deleted"] is True

    def test_viewer_denied(self, db_session, product_a, viewer, viewer_access):
        from mcp_server.tools.product import product_delete

        with _mock_session(db_session), _patch_user(viewer.id):
            result = product_delete(product_a.id)
            assert "error" in result
            assert "OWNER" in result["error"]


class TestProductGetScoringWeights:
    def test_viewer_can_read(self, db_session, product_a, viewer, viewer_access):
        from mcp_server.tools.product import product_get_scoring_weights

        with _mock_session(db_session), _patch_user(viewer.id):
            result = product_get_scoring_weights(product_a.id)
            assert "error" not in result
            assert "effective_weights" in result
            assert "defaults" in result

    def test_outsider_denied(self, db_session, product_a, outsider):
        from mcp_server.tools.product import product_get_scoring_weights

        with _mock_session(db_session), _patch_user(outsider.id):
            result = product_get_scoring_weights(product_a.id)
            assert "error" in result


class TestProductGetAnalysisHistory:
    def test_returns_empty_for_new_product(self, db_session, product_a, owner):
        from mcp_server.tools.product import product_get_analysis_history

        with _mock_session(db_session), _patch_user(owner.id):
            result = product_get_analysis_history(product_a.id)
            assert "error" not in result
            assert result["count"] == 0
            assert result["history"] == []


class TestProductGetJobs:
    def test_returns_jobs(self, db_session, product_a, job, owner):
        from mcp_server.tools.product import product_get_jobs

        with _mock_session(db_session), _patch_user(owner.id):
            result = product_get_jobs(product_a.id)
            assert "error" not in result
            assert result["count"] >= 1
            assert result["jobs"][0]["job_uuid"] == job.job_uuid


class TestProductGetTriageSettings:
    def test_returns_defaults(self, db_session, product_a, owner):
        from mcp_server.tools.product import product_get_triage_settings

        with _mock_session(db_session), _patch_user(owner.id):
            result = product_get_triage_settings(product_a.id)
            assert "error" not in result
            assert "auto_enabled" in result
            assert "auto_threshold" in result


class TestProductUpdateTriageSettings:
    def test_owner_can_update(self, db_session, product_a, owner):
        from mcp_server.tools.product import product_update_triage_settings

        with _mock_session(db_session), _patch_user(owner.id):
            result = product_update_triage_settings(product_a.id, auto_enabled=True, auto_threshold=0.85)
            assert "error" not in result
            assert result["auto_enabled"] is True
            assert result["auto_threshold"] == 0.85

    def test_rejects_invalid_threshold(self, db_session, product_a, owner):
        from mcp_server.tools.product import product_update_triage_settings

        with _mock_session(db_session), _patch_user(owner.id):
            result = product_update_triage_settings(product_a.id, auto_threshold=1.5)
            assert "error" in result

    def test_viewer_denied(self, db_session, product_a, viewer, viewer_access):
        from mcp_server.tools.product import product_update_triage_settings

        with _mock_session(db_session), _patch_user(viewer.id):
            result = product_update_triage_settings(product_a.id, auto_enabled=True)
            assert "error" in result
            assert "EDIT" in result["error"]


class TestProductGetAgentConfig:
    def test_returns_not_configured(self, db_session, product_a, owner):
        from mcp_server.tools.product import product_get_agent_schedule

        with _mock_session(db_session), _patch_user(owner.id):
            result = product_get_agent_schedule(product_a.id)
            assert "error" not in result
            assert result["configured"] is False


class TestProductUpdateAgentConfig:
    def test_creates_and_updates(self, db_session, product_a, owner):
        from mcp_server.tools.product import product_update_agent_schedule

        with _mock_session(db_session), _patch_user(owner.id):
            result = product_update_agent_schedule(
                product_a.id,
                enabled=True,
                product_analysis_mode="scheduled",
                product_analysis_schedule="weekly",
            )
            assert "error" not in result
            assert result["configured"] is True
            assert result["product_analysis_mode"] == "scheduled"
            assert result["product_analysis_schedule"] == "weekly"

    def test_rejects_invalid_mode(self, db_session, product_a, owner):
        from mcp_server.tools.product import product_update_agent_schedule

        with _mock_session(db_session), _patch_user(owner.id):
            result = product_update_agent_schedule(product_a.id, product_analysis_mode="hourly")
            assert "error" in result
            assert "Invalid mode" in result["error"]

    def test_viewer_denied(self, db_session, product_a, viewer, viewer_access):
        from mcp_server.tools.product import product_update_agent_schedule

        with _mock_session(db_session), _patch_user(viewer.id):
            result = product_update_agent_schedule(product_a.id, enabled=False)
            assert "error" in result
            assert "EDIT" in result["error"]


# ===========================================================================
# Phase 3: Ideas + Unified Creation + Unified Review
# ===========================================================================


class TestIdeasList:
    def test_lists_ideas(self, db_session, product_a, idea, owner):
        from mcp_server.tools.ideas import ideas_list

        with _mock_session(db_session), _patch_user(owner.id):
            result = ideas_list(product_a.id)
            assert "error" not in result
            assert result["count"] == 1
            assert result["ideas"][0]["title"] == "Test Idea"

    def test_filters_by_status(self, db_session, product_a, idea, owner):
        from mcp_server.tools.ideas import ideas_list

        with _mock_session(db_session), _patch_user(owner.id):
            result = ideas_list(product_a.id, status_filter="pending")
            assert result["count"] == 0  # idea is ACCEPTED, not PENDING

    def test_invalid_status_filter(self, db_session, product_a, owner):
        from mcp_server.tools.ideas import ideas_list

        with _mock_session(db_session), _patch_user(owner.id):
            result = ideas_list(product_a.id, status_filter="bogus")
            assert "error" in result

    def test_viewer_denied(self, db_session, product_a, outsider):
        from mcp_server.tools.ideas import ideas_list

        with _mock_session(db_session), _patch_user(outsider.id):
            result = ideas_list(product_a.id)
            assert "error" in result

    def test_imported_idea_exposes_external_provenance_not_summed(self, db_session, product_a, viewer, owner):
        """idea_summary must surface external_source/external_vote_count for
        imported ideas without folding them into the board vote_count — the
        two are different, non-comparable populations."""
        from mcp_server.tools.ideas import ideas_list

        imported = Idea(
            title="Imported Idea", what_description="desc",
            why_description="testing", use_case_description="tests",
            product_id=product_a.id, submitter_id=viewer.id,
            source_type=SourceType.EXTERNAL_SUBMISSION,
            external_source="canny", external_id="CANNY-101",
            source_metadata={"external_vote_count": 55, "external_status": "open"},
            status=IdeaStatus.ACCEPTED, is_active=True,
        )
        db_session.add(imported)
        db_session.commit()

        with _mock_session(db_session), _patch_user(owner.id):
            result = ideas_list(product_a.id)
            item = next(i for i in result["ideas"] if i["title"] == "Imported Idea")
            assert item["source_type"] == "external_submission"
            assert item["vote_count"] == 0  # no internal Vote rows
            assert item["external_source"] == "canny"
            assert item["external_vote_count"] == 55


class TestIdeasCreate:
    def test_manual_source_validation(self, db_session, product_a, owner):
        from mcp_server.tools.ideas import ideas_create

        with _mock_session(db_session), _patch_user(owner.id):
            # Missing title/description
            result = ideas_create(product_a.id, source="manual")
            assert "error" in result
            assert "title and description" in result["error"]

    def test_invalid_source(self, db_session, product_a, owner):
        from mcp_server.tools.ideas import ideas_create

        with _mock_session(db_session), _patch_user(owner.id):
            result = ideas_create(product_a.id, source="bogus")
            assert "error" in result
            assert "Invalid source" in result["error"]

    def test_manual_queues_job(self, db_session, product_a, owner):
        from mcp_server.tools.ideas import ideas_create

        with _mock_session(db_session), _patch_user(owner.id), \
             patch("mcp_server.db.dispatch_task") as mock_dispatch:
            mock_dispatch.return_value = MagicMock(id="fake-celery-id")
            result = ideas_create(
                product_a.id, source="manual",
                title="New Idea", description="A great idea for testing",
            )
            assert "error" not in result
            assert result["status"] == "queued"
            assert result["job_uuid"] is not None
            mock_dispatch.assert_called_once()

    def test_competitor_gaps_requires_name(self, db_session, product_a, owner):
        from mcp_server.tools.ideas import ideas_create

        with _mock_session(db_session), _patch_user(owner.id):
            result = ideas_create(product_a.id, source="competitor_gaps")
            assert "error" in result
            assert "competitor_name" in result["error"]

    def test_competitor_gaps_no_report(self, db_session, product_a, competitor, owner):
        from mcp_server.tools.ideas import ideas_create

        with _mock_session(db_session), _patch_user(owner.id):
            result = ideas_create(product_a.id, source="competitor_gaps", competitor_name="Rival")
            assert "error" in result
            assert "No functional report" in result["error"]

    def test_competitor_gaps_creates_ideas(self, db_session, product_a, competitor, owner):
        """Legacy fallback: audits that ran without a job map populate gaps_deep_dive."""
        from mcp_server.tools.ideas import ideas_create

        report = CompetitorFunctionalReport(
            product_competitor_id=competitor.id,
            product_id=product_a.id,
            report_version=1,
            gaps_deep_dive=[
                {"feature_name": "AI Triage", "user_problem": "Manual work", "evidence": "Seen in demo"},
                {"feature_name": "Dashboards", "user_problem": "No visibility", "evidence": "Blog post"},
            ],
        )
        db_session.add(report)
        db_session.commit()

        with _mock_session(db_session), _patch_user(owner.id), \
             patch("mcp_server.db.dispatch_task") as mock_dispatch:
            result = ideas_create(product_a.id, source="competitor_gaps", competitor_name="Rival")
            assert "error" not in result
            assert result["ideas_created"] == 2
            assert result["ideas_skipped"] == 0

            # Regression: triage dispatch must receive the integer job.id,
            # not the job_uuid string. triage_idea_task expects `job_id: int`.
            assert mock_dispatch.call_count == 2
            for call in mock_dispatch.call_args_list:
                _, dispatched_arg = call.args
                assert isinstance(dispatched_arg, int), (
                    f"dispatch_task called with {type(dispatched_arg).__name__}, expected int job_id"
                )

    def test_competitor_gaps_reads_job_assessments(self, db_session, product_a, competitor, owner):
        """Primary path: unified JTBD model stores gaps in job_assessments[].features[]
        where position == 'gap'. Legacy gaps_deep_dive is typically empty."""
        from mcp_server.tools.ideas import ideas_create
        from app.models.idea import Idea

        # Unified model: gaps live inside job_assessments, gaps_deep_dive is empty
        report = CompetitorFunctionalReport(
            product_competitor_id=competitor.id,
            product_id=product_a.id,
            report_version=1,
            gaps_deep_dive=[],
            job_assessments=[
                {
                    "job_id": "j1",
                    "job_statement": "File expenses quickly",
                    "features": [
                        {
                            "feature_name": "Slack integration",
                            "description": "Submit receipts via Slack",
                            "position": "gap",
                            "whose": "theirs",
                            "evidence_ids": [42, 43],
                        },
                        {
                            "feature_name": "Auto-categorization",
                            "description": "We already have this",
                            "position": "parity",
                            "whose": "both",
                            "evidence_ids": [],
                        },
                    ],
                },
                {
                    "job_id": "j2",
                    "job_statement": "Book travel",
                    "features": [
                        # Same feature surfaced under two jobs — must dedupe
                        {
                            "feature_name": "Slack integration",
                            "description": "Submit receipts via Slack",
                            "position": "gap",
                            "whose": "theirs",
                            "evidence_ids": [42],
                        },
                        {
                            "feature_name": "Travel booking",
                            "description": "In-product flight booking",
                            "position": "gap",
                            "whose": "theirs",
                            "evidence_ids": [],
                        },
                    ],
                },
            ],
        )
        db_session.add(report)
        db_session.commit()

        competitor_name = competitor.competitor_name
        with _mock_session(db_session), _patch_user(owner.id), \
             patch("mcp_server.db.dispatch_task"):
            result = ideas_create(product_a.id, source="competitor_gaps", competitor_name="Rival")
            assert "error" not in result
            # 2 distinct gaps (Slack integration deduped, Travel booking), parity feature ignored
            assert result["ideas_created"] == 2

            ideas = db_session.query(Idea).filter(Idea.product_id == product_a.id).all()
            titles = sorted(i.title for i in ideas)
            assert titles == ["Slack integration", "Travel booking"]

            # User-visible fields must not name the competitor or leak JTBD lingo
            for idea in ideas:
                for visible in (idea.title, idea.what_description or '',
                                idea.why_description or '', idea.use_case_description or ''):
                    assert competitor_name not in visible
                    assert "job" not in visible.lower()
                    assert "jtbd" not in visible.lower()

                # Metadata preserves competitor + evidence traceability
                meta = idea.source_metadata
                assert meta["competitor_id"] == competitor.id
                assert meta["competitor_name"] == competitor_name
                assert meta["feature_name"] == idea.title
                assert "evidence_ids" in meta

    def test_landscape_source_removed(self, db_session, product_a, owner):
        """The 'landscape' source was removed in Phase 4b; confirm it returns an error."""
        from mcp_server.tools.ideas import ideas_create

        with _mock_session(db_session), _patch_user(owner.id):
            result = ideas_create(product_a.id, source="landscape")
            assert "error" in result
            assert "Invalid source" in result["error"]

    def test_synthesis_requires_opportunity_id(self, db_session, product_a, owner):
        from mcp_server.tools.ideas import ideas_create

        with _mock_session(db_session), _patch_user(owner.id):
            result = ideas_create(product_a.id, source="synthesis")
            assert "error" in result
            assert "opportunity_id" in result["error"]

    def test_synthesis_creates_idea(self, db_session, product_a, owner):
        from mcp_server.tools.ideas import ideas_create
        from app.models.synthesis import SynthesisRun, SynthesizedOpportunity

        run = SynthesisRun(product_id=product_a.id, status="completed")
        db_session.add(run)
        db_session.flush()

        opp = SynthesizedOpportunity(
            synthesis_run_id=run.id,
            product_id=product_a.id,
            opportunity_name="Better Dashboards",
            opportunity_summary="Dashboards for monitoring",
            priority_score=0.8,
            source_count=3,
        )
        db_session.add(opp)
        db_session.commit()

        with _mock_session(db_session), _patch_user(owner.id), \
                patch("mcp_server.db.dispatch_task") as dispatch:
            dispatch.side_effect = lambda *a, **k: MagicMock(id="celery-syn")
            result = ideas_create(product_a.id, source="synthesis", opportunity_id=opp.id)
            assert "error" not in result
            assert result["title"] == "Better Dashboards"
            assert result["idea_id"] is not None
            # Bug fix: synthesis-created ideas now carry authoritative
            # metadata and get triaged
            assert result["triage_job_uuid"]
            dispatch.assert_called_once()

        created = db_session.query(Idea).get(result["idea_id"])
        assert created.source_metadata["synthesis_report_id"] == opp.synthesis_report_id
        assert created.source_metadata["opportunity_id"] == opp.id
        assert "competitor_names" in created.source_metadata

    def test_viewer_denied(self, db_session, product_a, viewer, viewer_access):
        from mcp_server.tools.ideas import ideas_create

        with _mock_session(db_session), _patch_user(viewer.id):
            result = ideas_create(product_a.id, source="manual", title="T", description="D")
            assert "error" in result
            assert "EDIT" in result["error"]


class TestIdeasGetComments:
    def test_returns_comments(self, db_session, idea, owner):
        from mcp_server.tools.ideas import ideas_get_comments

        c = IdeaComment(
            idea_id=idea.id, user_id=owner.id,
            comment_text="Looks good!", is_system_generated=False,
        )
        db_session.add(c)
        db_session.commit()

        with _mock_session(db_session), _patch_user(owner.id):
            result = ideas_get_comments(idea.id)
            assert "error" not in result
            assert result["count"] == 1
            assert result["comments"][0]["comment_text"] == "Looks good!"

    def test_not_found(self, db_session, owner):
        from mcp_server.tools.ideas import ideas_get_comments

        with _mock_session(db_session), _patch_user(owner.id):
            result = ideas_get_comments(99999)
            assert "error" in result


class TestIdeasAddComment:
    def test_adds_comment(self, db_session, idea, owner):
        from mcp_server.tools.ideas import ideas_add_comment

        with _mock_session(db_session), _patch_user(owner.id):
            result = ideas_add_comment(idea.id, "Nice idea")
            assert "error" not in result
            assert result["comment_text"] == "Nice idea"

    def test_rejects_empty(self, db_session, idea, owner):
        from mcp_server.tools.ideas import ideas_add_comment

        with _mock_session(db_session), _patch_user(owner.id):
            result = ideas_add_comment(idea.id, "")
            assert "error" in result


class TestIdeasRespond:
    def test_approve(self, db_session, idea, owner):
        from mcp_server.tools.ideas import ideas_respond

        # Set idea to PENDING first
        idea.status = IdeaStatus.PENDING
        idea.is_active = False
        db_session.commit()

        with _mock_session(db_session), _patch_user(owner.id):
            result = ideas_respond(idea.id, status="approved", comment="Ship it")
            assert "error" not in result
            assert result["new_status"] == "accepted"
            assert result["is_active"] is True

    def test_duplicate_transfers_votes(self, db_session, product_a, idea, owner):
        from mcp_server.tools.ideas import ideas_respond
        from app.models.vote import Vote

        # Create a target idea
        target = Idea(
            title="Original", what_description="d", why_description="w",
            use_case_description="u", product_id=product_a.id,
            submitter_id=owner.id, source_type=SourceType.CUSTOMER_SUBMISSION,
            status=IdeaStatus.ACCEPTED, is_active=True,
        )
        db_session.add(target)
        db_session.flush()

        # Add a vote on the duplicate
        vote = Vote(idea_id=idea.id, user_id=owner.id, vote_value=1)
        db_session.add(vote)
        db_session.commit()

        with _mock_session(db_session), _patch_user(owner.id):
            result = ideas_respond(
                idea.id, status="duplicate",
                comment="Same as Original",
                duplicate_of_idea_id=target.id,
            )
            assert "error" not in result
            assert result["votes_transferred"] == 1
            assert result["new_status"] == "duplicate"

    def test_needs_review_defers_and_preserves_is_active(self, db_session, idea, owner):
        from mcp_server.tools.ideas import ideas_respond

        idea.status = IdeaStatus.PENDING
        idea.is_active = True
        db_session.commit()

        with _mock_session(db_session), _patch_user(owner.id):
            result = ideas_respond(idea.id, status="needs_review", comment="Needs a closer look")
            assert "error" not in result
            assert result["new_status"] == "needs_review"
            # Deferral must not deactivate the idea
            assert result["is_active"] is True

    def test_requires_comment(self, db_session, idea, owner):
        from mcp_server.tools.ideas import ideas_respond

        with _mock_session(db_session), _patch_user(owner.id):
            result = ideas_respond(idea.id, status="approved", comment="")
            assert "error" in result

    def test_viewer_denied(self, db_session, idea, viewer, viewer_access):
        from mcp_server.tools.ideas import ideas_respond

        with _mock_session(db_session), _patch_user(viewer.id):
            result = ideas_respond(idea.id, status="approved", comment="ok")
            assert "error" in result
            assert "EDIT" in result["error"]


class TestReviewAction:
    def _queue_item(self, db_session, product_a, idea):
        queue_item = PMReviewQueue(
            queue_type=ReviewQueueType.IDEA,
            status=ReviewQueueStatus.PENDING,
            priority=ReviewQueuePriority.NORMAL,
            item_type="idea",
            item_id=idea.id,
            title=idea.title,
            product_id=product_a.id,
        )
        db_session.add(queue_item)
        db_session.commit()
        return queue_item

    def test_review_queue_item_approve(self, db_session, product_a, idea, owner):
        from mcp_server.tools.pm_review import review_action

        queue_item = self._queue_item(db_session, product_a, idea)

        with _mock_session(db_session), _patch_user(owner.id):
            result = review_action(queue_item.id, action="approve", notes="OK")
            assert "error" not in result
            assert result["status"] == "approved"
            assert result["queue_type"] == "idea"

    def test_review_queue_item_defer(self, db_session, product_a, idea, owner):
        from mcp_server.tools.pm_review import review_action

        queue_item = self._queue_item(db_session, product_a, idea)

        with _mock_session(db_session), _patch_user(owner.id):
            result = review_action(queue_item.id, action="defer")
            assert "error" not in result
            assert result["status"] == "deferred"

    def test_invalid_action(self, db_session, owner):
        from mcp_server.tools.pm_review import review_action

        with _mock_session(db_session), _patch_user(owner.id):
            result = review_action(1, action="bogus")
            assert "error" in result

    def test_queue_item_not_found(self, db_session, owner):
        from mcp_server.tools.pm_review import review_action

        with _mock_session(db_session), _patch_user(owner.id):
            result = review_action(999999, action="approve")
            assert "error" in result

    def test_viewer_denied(self, db_session, product_a, idea, viewer, viewer_access, owner):
        from mcp_server.tools.pm_review import review_action

        queue_item = self._queue_item(db_session, product_a, idea)

        with _mock_session(db_session), _patch_user(viewer.id):
            result = review_action(queue_item.id, action="approve")
            assert "error" in result
            assert "EDIT" in result["error"]


# ---------------------------------------------------------------------------
# ci_get_competitor_report — full report + section projections
# ---------------------------------------------------------------------------

class TestCiGetCompetitorReportSections:
    def _make_report(self, db_session, competitor, product_a):
        from datetime import datetime, timezone
        report = CompetitorFunctionalReport(
            product_competitor_id=competitor.id,
            product_id=product_a.id,
            report_version=2,
            competitor_context={
                "positioning": "Enterprise collaboration",
                "core_differentiation": "All-in-one platform",
                "target_customer": "Mid-market teams",
                "key_features": ["Dashboards", "Automations"],
            },
            functional_comparison=[
                {
                    "feature_category": "Analytics",
                    "competitor_feature_name": "Custom Dashboards",
                    "functional_description": "Drag-and-drop dashboard builder",
                    "mapping_status": "Gap",
                },
            ],
            gaps_deep_dive=[
                {"feature_name": "Custom Dashboards", "user_problem": "No visibility", "evidence": "Demo"},
            ],
            technical_constraints={
                "integrations": ["Slack", "Jira"],
                "api_capabilities": "REST + GraphQL",
                "platform_requirements": "Cloud only",
                "additional_notes": "SOC2 compliant",
            },
            changes_from_previous={"added_features": ["Automations"]},
            generated_at=datetime(2026, 4, 10, 12, 0, 0),
        )
        db_session.add(report)
        db_session.commit()
        return report

    def test_invalid_section(self, db_session, product_a, viewer, viewer_access, competitor):
        from mcp_server.tools.competitive import ci_get_competitor_report

        with _mock_session(db_session), _patch_user(viewer.id):
            result = ci_get_competitor_report(product_a.id, "Rival", "bogus")
            assert "error" in result
            assert "Invalid section" in result["error"]

    def test_features_section(self, db_session, product_a, viewer, viewer_access, competitor):
        from mcp_server.tools.competitive import ci_get_competitor_report
        self._make_report(db_session, competitor, product_a)

        with _mock_session(db_session), _patch_user(viewer.id):
            result = ci_get_competitor_report(product_a.id, "Rival", "features")
            assert "error" not in result
            assert len(result["functional_comparison"]) == 1
            assert result["functional_comparison"][0]["mapping_status"] == "Gap"
            assert len(result["gaps_deep_dive"]) == 1

    def test_positioning_section(self, db_session, product_a, viewer, viewer_access, competitor):
        from mcp_server.tools.competitive import ci_get_competitor_report
        self._make_report(db_session, competitor, product_a)

        with _mock_session(db_session), _patch_user(viewer.id):
            result = ci_get_competitor_report(product_a.id, "Rival", "positioning")
            assert "error" not in result
            assert result["competitor_context"]["positioning"] == "Enterprise collaboration"

    def test_constraints_section(self, db_session, product_a, viewer, viewer_access, competitor):
        from mcp_server.tools.competitive import ci_get_competitor_report
        self._make_report(db_session, competitor, product_a)

        with _mock_session(db_session), _patch_user(viewer.id):
            result = ci_get_competitor_report(product_a.id, "Rival", "constraints")
            assert "error" not in result
            assert "REST + GraphQL" in result["technical_constraints"]["api_capabilities"]

    def test_changes_section(self, db_session, product_a, viewer, viewer_access, competitor):
        from mcp_server.tools.competitive import ci_get_competitor_report
        self._make_report(db_session, competitor, product_a)

        with _mock_session(db_session), _patch_user(viewer.id):
            result = ci_get_competitor_report(product_a.id, "Rival", "changes")
            assert "error" not in result
            assert result["report_version"] == 2
            assert result["changes_from_previous"]["added_features"] == ["Automations"]

    def test_status_section(self, db_session, product_a, viewer, viewer_access, competitor):
        from mcp_server.tools.competitive import ci_get_competitor_report
        self._make_report(db_session, competitor, product_a)

        with _mock_session(db_session), _patch_user(viewer.id):
            result = ci_get_competitor_report(product_a.id, "Rival", "status")
            assert "error" not in result
            assert result["has_report"] is True
            assert result["report_version"] == 2

    def test_full_report_default(self, db_session, product_a, viewer, viewer_access, competitor):
        from mcp_server.tools.competitive import ci_get_competitor_report
        self._make_report(db_session, competitor, product_a)

        with _mock_session(db_session), _patch_user(viewer.id):
            result = ci_get_competitor_report(product_a.id, "Rival")
            assert "error" not in result
            # Full report includes all sections plus report-only fields
            assert result["report_version"] == 2
            assert result["competitor_context"]["positioning"] == "Enterprise collaboration"
            assert len(result["functional_comparison"]) == 1
            assert "job_assessments" in result
            assert "evidence_citations" in result
            assert result["additional_evidence"] == []
            assert "audit_last_run" in result

    def test_no_report_features(self, db_session, product_a, viewer, viewer_access, competitor):
        from mcp_server.tools.competitive import ci_get_competitor_report

        with _mock_session(db_session), _patch_user(viewer.id):
            result = ci_get_competitor_report(product_a.id, "Rival", "features")
            assert "error" in result
            assert "No report available" in result["error"]

    def test_status_no_report(self, db_session, product_a, viewer, viewer_access, competitor):
        from mcp_server.tools.competitive import ci_get_competitor_report

        with _mock_session(db_session), _patch_user(viewer.id):
            result = ci_get_competitor_report(product_a.id, "Rival", "status")
            assert "error" not in result
            assert result["has_report"] is False

    def test_report_survives_deactivation(self, db_session, product_a, viewer, viewer_access, competitor):
        from mcp_server.tools.competitive import ci_get_competitor_report
        self._make_report(db_session, competitor, product_a)
        competitor.status = "inactive"
        db_session.commit()

        with _mock_session(db_session), _patch_user(viewer.id):
            result = ci_get_competitor_report(product_a.id, "Rival")
            assert "error" not in result
            assert result["report_version"] == 2

    def test_latest_version_wins(self, db_session, product_a, viewer, viewer_access, competitor):
        from datetime import datetime
        from mcp_server.tools.competitive import ci_get_competitor_report
        self._make_report(db_session, competitor, product_a)
        older = CompetitorFunctionalReport(
            product_competitor_id=competitor.id,
            product_id=product_a.id,
            report_version=1,
            competitor_context={"positioning": "Old"},
            generated_at=datetime(2026, 3, 1, 12, 0, 0),
        )
        db_session.add(older)
        db_session.commit()

        with _mock_session(db_session), _patch_user(viewer.id):
            result = ci_get_competitor_report(product_a.id, "Rival")
            assert result["report_version"] == 2

    def test_no_competitor_found(self, db_session, product_a, viewer, viewer_access):
        from mcp_server.tools.competitive import ci_get_competitor_report

        with _mock_session(db_session), _patch_user(viewer.id):
            result = ci_get_competitor_report(product_a.id, "NonExistent", "features")
            assert "error" in result
            assert "No competitor" in result["error"]

    def test_outsider_denied(self, db_session, product_a, outsider, competitor):
        from mcp_server.tools.competitive import ci_get_competitor_report

        with _mock_session(db_session), _patch_user(outsider.id):
            result = ci_get_competitor_report(product_a.id, "Rival", "features")
            assert "error" in result
            assert "Permission denied" in result["error"]


# ---------------------------------------------------------------------------
# ci_deactivate_competitor — soft-delete competitor
# ---------------------------------------------------------------------------

class TestCiDeactivateCompetitor:
    def test_owner_can_deactivate(self, db_session, product_a, owner, competitor):
        from mcp_server.tools.competitive import ci_deactivate_competitor

        with _mock_session(db_session), _patch_user(owner.id):
            result = ci_deactivate_competitor(product_a.id, "Rival")
            assert "error" not in result
            assert result["status"] == "inactive"
            assert result["competitor_name"] == "Rival Co"

        # Verify DB state
        db_session.refresh(competitor)
        assert competitor.status == "inactive"
        assert competitor.tracked is False

    def test_already_inactive(self, db_session, product_a, owner, competitor):
        from mcp_server.tools.competitive import ci_deactivate_competitor

        competitor.status = "inactive"
        db_session.commit()

        with _mock_session(db_session), _patch_user(owner.id):
            result = ci_deactivate_competitor(product_a.id, "Rival")
            assert "error" in result
            assert "No active competitor" in result["error"]

    def test_viewer_denied(self, db_session, product_a, viewer, viewer_access, competitor):
        from mcp_server.tools.competitive import ci_deactivate_competitor

        with _mock_session(db_session), _patch_user(viewer.id):
            result = ci_deactivate_competitor(product_a.id, "Rival")
            assert "error" in result
            assert "EDIT" in result["error"]

    def test_outsider_denied(self, db_session, product_a, outsider, competitor):
        from mcp_server.tools.competitive import ci_deactivate_competitor

        with _mock_session(db_session), _patch_user(outsider.id):
            result = ci_deactivate_competitor(product_a.id, "Rival")
            assert "error" in result
            assert "Permission denied" in result["error"]


# ===========================================================================
# Phase 5 Tests
# ===========================================================================

# ---------------------------------------------------------------------------
# review_get_queue — PM review queue listing
# ---------------------------------------------------------------------------

class TestReviewGetQueue:
    def test_owner_gets_queue(self, db_session, product_a, owner):
        from mcp_server.tools.pm_review import review_get_queue

        with _mock_session(db_session), _patch_user(owner.id):
            result = review_get_queue(product_a.id)
            assert "error" not in result
            assert result["total"] == 0
            assert result["items"] == []

    def test_invalid_queue_type(self, db_session, product_a, owner):
        from mcp_server.tools.pm_review import review_get_queue

        with _mock_session(db_session), _patch_user(owner.id):
            result = review_get_queue(product_a.id, queue_type="bogus")
            assert "error" in result
            assert "Invalid queue_type" in result["error"]

    def test_viewer_denied(self, db_session, product_a, viewer, viewer_access):
        from mcp_server.tools.pm_review import review_get_queue

        with _mock_session(db_session), _patch_user(viewer.id):
            result = review_get_queue(product_a.id)
            assert "error" in result
            assert "EDIT" in result["error"]


# ---------------------------------------------------------------------------
# review_get_stats — PM review queue statistics
# ---------------------------------------------------------------------------

class TestReviewGetStats:
    def test_owner_gets_stats(self, db_session, product_a, owner):
        from mcp_server.tools.pm_review import review_get_stats

        with _mock_session(db_session), _patch_user(owner.id):
            result = review_get_stats(product_a.id)
            assert "error" not in result
            assert result["product_id"] == product_a.id

    def test_outsider_denied(self, db_session, product_a, outsider):
        from mcp_server.tools.pm_review import review_get_stats

        with _mock_session(db_session), _patch_user(outsider.id):
            result = review_get_stats(product_a.id)
            assert "error" in result


# ---------------------------------------------------------------------------
# monitoring_get_config / monitoring_update_config
# ---------------------------------------------------------------------------

class TestMonitoringGetConfig:
    def test_no_config_returns_defaults(self, db_session, product_a, owner):
        from mcp_server.tools.monitoring import monitoring_get_config

        with _mock_session(db_session), _patch_user(owner.id):
            result = monitoring_get_config(product_a.id)
            assert "error" not in result
            assert result["configured"] is False
            assert result["monitoring_enabled"] is False

    def test_outsider_denied(self, db_session, product_a, outsider):
        from mcp_server.tools.monitoring import monitoring_get_config

        with _mock_session(db_session), _patch_user(outsider.id):
            result = monitoring_get_config(product_a.id)
            assert "error" in result


class TestMonitoringUpdateConfig:
    def test_enable_monitoring(self, db_session, product_a, owner):
        from mcp_server.tools.monitoring import monitoring_update_config, monitoring_get_config

        with _mock_session(db_session), _patch_user(owner.id):
            result = monitoring_update_config(product_a.id, monitoring_enabled=True, monitoring_frequency="daily")
            assert "error" not in result
            assert result["monitoring_enabled"] is True
            assert result["monitoring_frequency"] == "daily"

            # Verify persistence
            get_result = monitoring_get_config(product_a.id)
            assert get_result["configured"] is True
            assert get_result["monitoring_enabled"] is True

    def test_invalid_frequency(self, db_session, product_a, owner):
        from mcp_server.tools.monitoring import monitoring_update_config

        with _mock_session(db_session), _patch_user(owner.id):
            result = monitoring_update_config(product_a.id, monitoring_frequency="hourly")
            assert "error" in result
            assert "Invalid frequency" in result["error"]

    def test_no_fields_provided(self, db_session, product_a, owner):
        from mcp_server.tools.monitoring import monitoring_update_config

        with _mock_session(db_session), _patch_user(owner.id):
            result = monitoring_update_config(product_a.id)
            assert "error" in result
            assert "No configuration fields" in result["error"]

    def test_viewer_denied(self, db_session, product_a, viewer, viewer_access):
        from mcp_server.tools.monitoring import monitoring_update_config

        with _mock_session(db_session), _patch_user(viewer.id):
            result = monitoring_update_config(product_a.id, monitoring_enabled=True)
            assert "error" in result
            assert "EDIT" in result["error"]


# ---------------------------------------------------------------------------
# evidence_delete
# ---------------------------------------------------------------------------

class TestEvidenceDelete:
    def test_owner_can_delete(self, db_session, product_a, owner, evidence_record):
        from mcp_server.tools.evidence import evidence_delete

        eid = evidence_record.id
        with _mock_session(db_session), _patch_user(owner.id):
            result = evidence_delete(eid)
            assert "error" not in result
            assert result["evidence_id"] == eid
            assert "deleted" in result["message"].lower()

    def test_viewer_denied(self, db_session, product_a, viewer, viewer_access, evidence_record):
        from mcp_server.tools.evidence import evidence_delete

        with _mock_session(db_session), _patch_user(viewer.id):
            result = evidence_delete(evidence_record.id)
            assert "error" in result
            assert "EDIT" in result["error"]

    def test_not_found(self, db_session, owner):
        from mcp_server.tools.evidence import evidence_delete

        with _mock_session(db_session), _patch_user(owner.id):
            result = evidence_delete(99999)
            assert "error" in result


# ---------------------------------------------------------------------------
# evidence_suggest_competitor
# ---------------------------------------------------------------------------

class TestEvidenceSuggestCompetitor:
    def test_returns_suggestion(self, db_session, product_a, owner, evidence_record):
        from mcp_server.tools.evidence import evidence_suggest_competitor

        mock_result = {
            "suggested_name": "Rival Co",
            "matched_competitor_id": 1,
            "matched_competitor_name": "Rival Co",
            "is_new": False,
        }

        with _mock_session(db_session), _patch_user(owner.id), \
             patch("app.services.evidence_service.suggest_competitor", return_value=mock_result):
            result = evidence_suggest_competitor(evidence_record.id)
            assert "error" not in result
            assert result["suggested_name"] == "Rival Co"

    def test_outsider_denied(self, db_session, product_a, outsider, evidence_record):
        from mcp_server.tools.evidence import evidence_suggest_competitor

        with _mock_session(db_session), _patch_user(outsider.id):
            result = evidence_suggest_competitor(evidence_record.id)
            assert "error" in result


# ---------------------------------------------------------------------------
# internal_list_imports
# ---------------------------------------------------------------------------

class TestInternalListImports:
    def test_returns_imports(self, db_session, product_a, owner):
        from mcp_server.tools.internal import internal_list_imports
        from app.models.internal_feedback import InternalFeedbackImport

        imp = InternalFeedbackImport(
            product_id=product_a.id,
            filename="test.json",
            source_type="mcp",
            status="completed",
            deals_count=5,
            tickets_count=3,
        )
        db_session.add(imp)
        db_session.commit()

        with _mock_session(db_session), _patch_user(owner.id):
            result = internal_list_imports(product_a.id)
            assert "error" not in result
            assert len(result["imports"]) == 1
            assert result["imports"][0]["deals_count"] == 5

    def test_outsider_denied(self, db_session, product_a, outsider):
        from mcp_server.tools.internal import internal_list_imports

        with _mock_session(db_session), _patch_user(outsider.id):
            result = internal_list_imports(product_a.id)
            assert "error" in result


# ---------------------------------------------------------------------------
# internal_delete_theme
# ---------------------------------------------------------------------------

class TestInternalDeleteTheme:
    def _make_import(self, db_session, product_a):
        from app.models.internal_feedback import InternalFeedbackImport
        imp = InternalFeedbackImport(
            product_id=product_a.id,
            filename="test.json",
            source_type="test",
            status="completed",
            deals_count=1,
            tickets_count=1,
        )
        db_session.add(imp)
        db_session.flush()
        return imp

    def test_delete_winloss_theme(self, db_session, product_a, owner):
        from mcp_server.tools.internal import internal_delete_theme
        from app.models.internal_feedback import WinLossTheme

        imp = self._make_import(db_session, product_a)
        theme = WinLossTheme(
            import_id=imp.id,
            product_id=product_a.id,
            theme_name="Missing feature X",
            outcome="lost",
            deal_count=3,
        )
        db_session.add(theme)
        db_session.commit()
        db_session.refresh(theme)

        with _mock_session(db_session), _patch_user(owner.id):
            result = internal_delete_theme(theme.id, "winloss")
            assert "error" not in result
            assert result["theme_name"] == "Missing feature X"

    def test_delete_support_theme(self, db_session, product_a, owner):
        from mcp_server.tools.internal import internal_delete_theme
        from app.models.internal_feedback import SupportTheme

        imp = self._make_import(db_session, product_a)
        theme = SupportTheme(
            import_id=imp.id,
            product_id=product_a.id,
            theme_name="Login issues",
            category="bug",
            ticket_count=10,
        )
        db_session.add(theme)
        db_session.commit()
        db_session.refresh(theme)

        with _mock_session(db_session), _patch_user(owner.id):
            result = internal_delete_theme(theme.id, "support")
            assert "error" not in result
            assert result["theme_name"] == "Login issues"

    def test_invalid_theme_type(self, db_session, owner):
        from mcp_server.tools.internal import internal_delete_theme

        with _mock_session(db_session), _patch_user(owner.id):
            result = internal_delete_theme(1, "bogus")
            assert "error" in result
            assert "Invalid theme_type" in result["error"]

    def test_viewer_denied(self, db_session, product_a, viewer, viewer_access):
        from mcp_server.tools.internal import internal_delete_theme
        from app.models.internal_feedback import WinLossTheme

        imp = self._make_import(db_session, product_a)
        theme = WinLossTheme(
            import_id=imp.id,
            product_id=product_a.id,
            theme_name="Theme",
            outcome="lost",
            deal_count=1,
        )
        db_session.add(theme)
        db_session.commit()
        db_session.refresh(theme)

        with _mock_session(db_session), _patch_user(viewer.id):
            result = internal_delete_theme(theme.id, "winloss")
            assert "error" in result
            assert "EDIT" in result["error"]


# ---------------------------------------------------------------------------
# internal_get_activity_insights
# ---------------------------------------------------------------------------

class TestInternalGetActivityInsights:
    def test_no_insights(self, db_session, product_a, owner):
        from mcp_server.tools.internal import internal_get_activity_insights

        with _mock_session(db_session), _patch_user(owner.id):
            result = internal_get_activity_insights(product_a.id)
            assert "error" not in result
            assert result["has_insights"] is False

    def test_outsider_denied(self, db_session, product_a, outsider):
        from mcp_server.tools.internal import internal_get_activity_insights

        with _mock_session(db_session), _patch_user(outsider.id):
            result = internal_get_activity_insights(product_a.id)
            assert "error" in result


# ---------------------------------------------------------------------------
# product_create_invite / product_list_invites / product_list_members
# ---------------------------------------------------------------------------

class TestProductCreateInvite:
    def test_owner_creates_invite(self, db_session, product_a, owner):
        from mcp_server.tools.product import product_create_invite

        with _mock_session(db_session), _patch_user(owner.id):
            result = product_create_invite(product_a.id)
            assert "error" not in result
            assert "code" in result
            assert len(result["code"]) > 0
            assert result["permission_level"] == "view"

    def test_viewer_denied(self, db_session, product_a, viewer, viewer_access):
        from mcp_server.tools.product import product_create_invite

        with _mock_session(db_session), _patch_user(viewer.id):
            result = product_create_invite(product_a.id)
            assert "error" in result
            assert "OWNER" in result["error"]


class TestProductListInvites:
    def test_owner_lists_invites(self, db_session, product_a, owner):
        from mcp_server.tools.product import product_create_invite, product_list_invites

        with _mock_session(db_session), _patch_user(owner.id):
            product_create_invite(product_a.id)
            result = product_list_invites(product_a.id)
            assert "error" not in result
            assert len(result["invites"]) == 1


class TestProductListMembers:
    def test_owner_lists_members(self, db_session, product_a, owner, viewer, viewer_access):
        from mcp_server.tools.product import product_list_members

        with _mock_session(db_session), _patch_user(owner.id):
            result = product_list_members(product_a.id)
            assert "error" not in result
            # viewer_access fixture adds an explicit ProductPermission for viewer
            assert len(result["members"]) >= 1

    def test_viewer_denied(self, db_session, product_a, viewer, viewer_access):
        from mcp_server.tools.product import product_list_members

        with _mock_session(db_session), _patch_user(viewer.id):
            result = product_list_members(product_a.id)
            assert "error" in result
            assert "OWNER" in result["error"]


# ===========================================================================
# Phase 1c: JTBD Job Map tools
# ===========================================================================


class TestProductGetJobMapEmpty:
    def test_returns_empty_when_no_job_map(self, db_session, product_a, owner):
        from mcp_server.tools.product import product_get_job_map

        with _mock_session(db_session), _patch_user(owner.id):
            result = product_get_job_map(product_a.id)
            assert "error" not in result
            assert result["job_map"] is None
            assert result["target_customer_profile"] is None
            assert result["job_map_version"] == 0
            assert result["jobs"] == []


class TestProductSetJobMap:
    def test_sets_job_map_and_creates_records(self, db_session, product_a, owner):
        from mcp_server.tools.product import product_set_job_map
        from app.models.competitor_intelligence import ProductJob

        mock_embeddings = [[0.001 * i for i in range(1024)] for _ in range(2)]
        mock_svc = MagicMock()
        mock_svc.generate_embeddings_batch.return_value = mock_embeddings

        job_map = json.dumps({
            "main_job": "Manage competitive intelligence",
            "functional_jobs": [
                {
                    "job_id": "j1",
                    "job_type": "functional",
                    "statement": "When researching competitors, I want to track features",
                    "desired_outcomes": ["Complete picture"],
                    "importance": "high",
                },
            ],
            "emotional_jobs": [
                {
                    "job_id": "je1",
                    "job_type": "emotional",
                    "statement": "When presenting to leadership, I want to feel confident",
                    "desired_outcomes": [],
                    "importance": "medium",
                },
            ],
            "social_jobs": [],
        })

        with _mock_session(db_session), _patch_user(owner.id), \
             patch("app.services.embedding_service.generate_embeddings_batch", mock_svc.generate_embeddings_batch):
            result = product_set_job_map(product_a.id, job_map)
            assert "error" not in result
            assert result["jobs_created"] == 2
            assert result["job_map_version"] == 1

            # Verify ProductJob records were created
            jobs = db_session.query(ProductJob).filter(
                ProductJob.product_id == product_a.id
            ).all()
            assert len(jobs) == 2
            job_ids = {j.job_id_key for j in jobs}
            assert "j1" in job_ids
            assert "je1" in job_ids


class TestProductAddJob:
    def test_adds_job_to_map(self, db_session, product_a, owner):
        from mcp_server.tools.product import product_add_job
        from app.models.competitor_intelligence import ProductJob

        mock_embedding = [0.001 * i for i in range(1024)]

        with _mock_session(db_session), _patch_user(owner.id), \
             patch("app.services.embedding_service.generate_embedding", return_value=mock_embedding):
            result = product_add_job(
                product_a.id,
                job_id="j1",
                job_type="functional",
                statement="When tracking competitors, I want to see feature gaps",
                importance="high",
            )
            assert "error" not in result
            assert result["job_id_key"] == "j1"
            assert result["job_type"] == "functional"
            assert result["importance"] == "high"
            assert result["job_map_version"] == 1

            # Verify DB record
            pj = db_session.query(ProductJob).filter(
                ProductJob.product_id == product_a.id,
                ProductJob.job_id_key == "j1",
            ).first()
            assert pj is not None
            assert pj.statement_embedding is not None

    def test_rejects_duplicate_job_id(self, db_session, product_a, owner):
        from mcp_server.tools.product import product_add_job

        with _mock_session(db_session), _patch_user(owner.id), \
             patch("app.services.embedding_service.generate_embedding", return_value=[0.0] * 1024):
            # Add first job
            product_add_job(
                product_a.id, job_id="j1", job_type="functional",
                statement="First job statement",
            )
            # Try to add duplicate
            result = product_add_job(
                product_a.id, job_id="j1", job_type="functional",
                statement="Duplicate job statement",
            )
            assert "error" in result
            assert "already exists" in result["error"]


class TestProductEditJob:
    def test_edits_job_statement_and_importance(self, db_session, product_a, owner):
        from mcp_server.tools.product import product_add_job, product_edit_job

        with _mock_session(db_session), _patch_user(owner.id), \
             patch("app.services.embedding_service.generate_embedding", return_value=[0.0] * 1024):
            # Add a job first
            product_add_job(
                product_a.id, job_id="j1", job_type="functional",
                statement="Original statement", importance="medium",
            )

            # Edit it
            result = product_edit_job(
                product_a.id, job_id="j1",
                statement="Updated statement",
                importance="critical",
            )
            assert "error" not in result
            assert result["statement"] == "Updated statement"
            assert result["importance"] == "critical"
            assert result["job_map_version"] == 2  # incremented from add (1) to edit (2)

    def test_returns_error_for_nonexistent_job(self, db_session, product_a, owner):
        from mcp_server.tools.product import product_edit_job

        with _mock_session(db_session), _patch_user(owner.id):
            result = product_edit_job(product_a.id, job_id="nonexistent", statement="x")
            assert "error" in result
            assert "not found" in result["error"]


class TestProductRemoveJob:
    def test_removes_job_from_map(self, db_session, product_a, owner):
        from mcp_server.tools.product import product_add_job, product_remove_job
        from app.models.competitor_intelligence import ProductJob

        with _mock_session(db_session), _patch_user(owner.id), \
             patch("app.services.embedding_service.generate_embedding", return_value=[0.0] * 1024):
            product_add_job(
                product_a.id, job_id="j1", job_type="functional",
                statement="Job to remove",
            )

            result = product_remove_job(product_a.id, job_id="j1")
            assert "error" not in result
            assert result["removed_job_id"] == "j1"
            assert result["job_map_version"] == 2

            # Verify DB record deleted
            pj = db_session.query(ProductJob).filter(
                ProductJob.product_id == product_a.id,
                ProductJob.job_id_key == "j1",
            ).first()
            assert pj is None


class TestProductSetTargetCustomer:
    def test_sets_profile(self, db_session, product_a, owner):
        from mcp_server.tools.product import product_set_target_customer

        with _mock_session(db_session), _patch_user(owner.id):
            result = product_set_target_customer(
                product_a.id,
                persona_name="Mid-market PM",
                company_characteristics="50-500 employees, B2B SaaS",
                key_traits_json='["Data-driven", "Resource-constrained"]',
                hiring_criteria="Needs competitive visibility",
            )
            assert "error" not in result
            assert result["target_customer_profile"]["persona_name"] == "Mid-market PM"
            assert len(result["target_customer_profile"]["key_traits"]) == 2

    def test_viewer_denied(self, db_session, product_a, viewer, viewer_access):
        from mcp_server.tools.product import product_set_target_customer

        with _mock_session(db_session), _patch_user(viewer.id):
            result = product_set_target_customer(product_a.id, persona_name="Test")
            assert "error" in result
            assert "EDIT" in result["error"]


class TestProductGetContextIncludesJobMap:
    def test_includes_job_map_info(self, db_session, product_a, owner):
        from mcp_server.tools.product import product_get_context, product_set_target_customer, product_add_job

        with _mock_session(db_session), _patch_user(owner.id), \
             patch("app.services.embedding_service.generate_embedding", return_value=[0.0] * 1024):
            # Set up target customer and a job
            product_set_target_customer(product_a.id, persona_name="Test PM")
            product_add_job(
                product_a.id, job_id="j1", job_type="functional",
                statement="Test job",
            )

            result = product_get_context(product_a.id)
            assert "error" not in result
            assert result["target_customer_profile"]["persona_name"] == "Test PM"
            assert result["job_map_version"] == 1
            assert "1 jobs defined" in result["job_map_summary"]

    def test_shows_no_job_map_when_empty(self, db_session, product_a, owner):
        from mcp_server.tools.product import product_get_context

        with _mock_session(db_session), _patch_user(owner.id):
            result = product_get_context(product_a.id)
            assert result["target_customer_profile"] is None
            assert result["job_map_version"] == 0
            assert result["job_map_summary"] == "No job map defined"


# ---------------------------------------------------------------------------
# ci_set_tracked — single replacement for ci_set_audit/ci_set_synthesis_inclusion
# ---------------------------------------------------------------------------

class TestCiSetTracked:
    def test_ci_set_tracked_true(self, db_session, product_a, owner, competitor):
        from mcp_server.tools.competitive import ci_set_tracked

        assert competitor.tracked is False

        with _mock_session(db_session), _patch_user(owner.id):
            result = ci_set_tracked(product_a.id, competitor.competitor_name, tracked=True)
            assert "error" not in result
            assert result["tracked"] is True

        db_session.refresh(competitor)
        assert competitor.tracked is True

    def test_ci_set_tracked_false(self, db_session, product_a, owner, competitor):
        from mcp_server.tools.competitive import ci_set_tracked

        competitor.tracked = True
        db_session.commit()

        with _mock_session(db_session), _patch_user(owner.id):
            result = ci_set_tracked(product_a.id, competitor.competitor_name, tracked=False)
            assert "error" not in result
            assert result["tracked"] is False

        db_session.refresh(competitor)
        assert competitor.tracked is False

    def test_viewer_denied(self, db_session, product_a, viewer, viewer_access, competitor):
        from mcp_server.tools.competitive import ci_set_tracked

        with _mock_session(db_session), _patch_user(viewer.id):
            result = ci_set_tracked(product_a.id, competitor.competitor_name, tracked=True)
            assert "error" in result
            assert "EDIT" in result["error"]


# ---------------------------------------------------------------------------
# ci_get_competitor_list — shows tracked + audit status
# ---------------------------------------------------------------------------

class TestCiGetCompetitorListAuditStatus:
    def test_ci_get_competitor_list_shows_tracked_and_audit_status(self, db_session, product_a, owner, competitor):
        from mcp_server.tools.competitive import ci_get_competitor_list

        competitor.tracked = True
        competitor.audit_status = "completed"
        db_session.commit()

        with _mock_session(db_session), _patch_user(owner.id):
            result = ci_get_competitor_list(product_a.id)
            assert "error" not in result
            assert len(result["competitors"]) == 1
            c = result["competitors"][0]
            assert c["tracked"] is True
            assert c["audit_status"] == "completed"


# ---------------------------------------------------------------------------
# Phase 3 unified synthesis tools
# ---------------------------------------------------------------------------

class TestSynthesisConfigure:
    def test_creates_and_updates_config(self, db_session, product_a, owner):
        from mcp_server.tools.synthesis import synthesis_configure
        from app.models.synthesis import SynthesisConfig

        # Create fresh
        with _mock_session(db_session), _patch_user(owner.id):
            result = synthesis_configure(
                product_a.id,
                source_types=["competitive", "customer"],
                auto_generate_ideas=False,
                idea_priority_threshold=0.85,
            )
            assert "error" not in result
            assert result["created"] is True
            assert result["config"]["included_source_types"] == ["competitive", "customer"]
            assert result["config"]["auto_generate_ideas"] is False
            assert result["config"]["idea_priority_threshold"] == 0.85

        # Update existing
        with _mock_session(db_session), _patch_user(owner.id):
            result = synthesis_configure(
                product_a.id,
                source_types=["competitive", "customer", "internal"],
            )
            assert "error" not in result
            assert result["created"] is False
            assert result["config"]["included_source_types"] == [
                "competitive", "customer", "internal"
            ]
            # Unchanged fields persist
            assert result["config"]["auto_generate_ideas"] is False
            assert result["config"]["idea_priority_threshold"] == 0.85

        # Verify only one config row exists
        count = db_session.query(SynthesisConfig).filter(
            SynthesisConfig.product_id == product_a.id
        ).count()
        assert count == 1

    def test_rejects_unknown_source_types(self, db_session, product_a, owner):
        from mcp_server.tools.synthesis import synthesis_configure

        with _mock_session(db_session), _patch_user(owner.id):
            result = synthesis_configure(product_a.id, source_types=["bogus"])
            assert "error" in result
            assert "bogus" in result["error"] or "Unknown" in result["error"]

    def test_viewer_denied(self, db_session, product_a, viewer, viewer_access):
        from mcp_server.tools.synthesis import synthesis_configure

        with _mock_session(db_session), _patch_user(viewer.id):
            result = synthesis_configure(product_a.id, source_types=["competitive"])
            assert "error" in result
            assert "EDIT" in result["error"]


class TestSynthesisGetConfig:
    def test_returns_defaults_when_not_set(self, db_session, product_a, owner):
        from mcp_server.tools.synthesis import synthesis_get_config

        with _mock_session(db_session), _patch_user(owner.id):
            result = synthesis_get_config(product_a.id)
            assert "error" not in result
            assert result["exists"] is False
            assert result["config"]["included_source_types"] == ["competitive"]
            assert result["config"]["auto_generate_ideas"] is True
            assert result["config"]["idea_priority_threshold"] == 0.8

    def test_returns_stored_config(self, db_session, product_a, owner):
        from mcp_server.tools.synthesis import (
            synthesis_configure,
            synthesis_get_config,
        )

        with _mock_session(db_session), _patch_user(owner.id):
            synthesis_configure(
                product_a.id,
                source_types=["competitive", "evidence"],
                idea_priority_threshold=0.5,
            )
            result = synthesis_get_config(product_a.id)
            assert result["exists"] is True
            assert result["config"]["included_source_types"] == [
                "competitive", "evidence"
            ]
            assert result["config"]["idea_priority_threshold"] == 0.5


class TestCiGetCompetitorListMergedFields:
    def test_shows_tracked_flag(
        self, db_session, product_a, owner, competitor
    ):
        from mcp_server.tools.competitive import ci_get_competitor_list

        competitor.tracked = True
        competitor.audit_status = "completed"
        db_session.commit()

        # Second competitor — untracked
        other = ProductCompetitor(
            product_id=product_a.id,
            competitor_name="Other Co",
            competitor_url="https://other.co",
            status="active",
            tracked=False,
        )
        db_session.add(other)
        db_session.commit()

        with _mock_session(db_session), _patch_user(owner.id):
            result = ci_get_competitor_list(product_a.id)
            assert "error" not in result
            assert len(result["competitors"]) == 2
            by_name = {c["competitor_name"]: c for c in result["competitors"]}
            assert by_name["Rival Co"]["tracked"] is True
            assert by_name["Rival Co"]["audit_status"] == "completed"
            assert by_name["Other Co"]["tracked"] is False
            # Serializer fields present even without a report
            assert by_name["Rival Co"]["has_report"] is False
            assert by_name["Rival Co"]["report_generated_at"] is None
            assert "audit_last_run" in by_name["Rival Co"]

    def test_latest_report_version_reported(self, db_session, product_a, owner, competitor):
        from datetime import datetime
        from mcp_server.tools.competitive import ci_get_competitor_list

        for version, day in ((1, 1), (2, 10)):
            db_session.add(CompetitorFunctionalReport(
                product_competitor_id=competitor.id,
                product_id=product_a.id,
                report_version=version,
                generated_at=datetime(2026, 4, day, 12, 0, 0),
            ))
        db_session.commit()

        with _mock_session(db_session), _patch_user(owner.id):
            result = ci_get_competitor_list(product_a.id)
            (row,) = result["competitors"]
            assert row["has_report"] is True
            assert row["report_version"] == 2

    def test_outsider_denied(self, db_session, product_a, outsider, competitor):
        from mcp_server.tools.competitive import ci_get_competitor_list

        with _mock_session(db_session), _patch_user(outsider.id):
            result = ci_get_competitor_list(product_a.id)
            assert "error" in result


class TestSynthesisGetUnifiedReportEmpty:
    def test_returns_error_when_no_report(self, db_session, product_a, owner):
        from mcp_server.tools.synthesis import synthesis_get_unified_report

        with _mock_session(db_session), _patch_user(owner.id):
            result = synthesis_get_unified_report(product_a.id)
            assert "error" in result
            assert "synthesis_run_unified" in result["error"]


# ---------------------------------------------------------------------------
# Scoped-input params on ci_run_competitor_audit and product_run_analysis
# ---------------------------------------------------------------------------

class TestCiRunCompetitorAuditScopedInputs:
    def test_defaults_put_web_research_true_and_empty_urls_in_input_data(
        self, db_session, product_a, competitor, owner
    ):
        from mcp_server.tools.competitive import ci_run_competitor_audit

        with _mock_session(db_session), _patch_user(owner.id), \
             patch("mcp_server.db.dispatch_task") as mock_dispatch:
            mock_dispatch.return_value = MagicMock(id="celery-1")
            result = ci_run_competitor_audit(product_a.id, "Rival")
            assert "error" not in result

            job = db_session.query(QueueJob).filter(QueueJob.id == result["job_id"]).one()
            assert job.input_data["web_research_enabled"] is True
            assert job.input_data["source_urls"] == []
            assert job.input_data["competitor_id"] == competitor.id

    def test_web_research_false_flows_into_input_data(
        self, db_session, product_a, competitor, owner
    ):
        from mcp_server.tools.competitive import ci_run_competitor_audit

        with _mock_session(db_session), _patch_user(owner.id), \
             patch("mcp_server.db.dispatch_task") as mock_dispatch:
            mock_dispatch.return_value = MagicMock(id="celery-2")
            result = ci_run_competitor_audit(
                product_a.id, "Rival", web_research=False,
                source_urls=["https://rival.co/pricing", "https://rival.co/features"],
            )
            assert "error" not in result
            job = db_session.query(QueueJob).filter(QueueJob.id == result["job_id"]).one()
            assert job.input_data["web_research_enabled"] is False
            assert job.input_data["source_urls"] == [
                "https://rival.co/pricing", "https://rival.co/features"
            ]

    def test_too_many_source_urls_returns_structured_error(
        self, db_session, product_a, competitor, owner
    ):
        from mcp_server.tools.competitive import ci_run_competitor_audit

        with _mock_session(db_session), _patch_user(owner.id):
            result = ci_run_competitor_audit(
                product_a.id, "Rival", web_research=False,
                source_urls=[f"https://rival.co/p{i}" for i in range(6)],
            )
            assert "error" in result
            assert result["error_code"] == "SCOPED_INPUT_LIMIT_EXCEEDED"
            assert result["field"] == "source_urls"
            assert result["limit"] == 5
            assert result["got"] == 6
            # No job should be queued
            jobs = db_session.query(QueueJob).filter(
                QueueJob.product_id == product_a.id,
                QueueJob.job_type == JobType.FUNCTIONAL_AUDIT,
            ).all()
            assert len(jobs) == 0


class TestProductRunAnalysisScopedInputs:
    def test_source_urls_flow_into_input_data(self, db_session, product_a, owner):
        from mcp_server.tools.product import product_run_analysis

        # Product description must be >= 50 chars to pass the validation in the tool
        product_a.product_description = "A very detailed product description that easily exceeds fifty characters in length."
        db_session.commit()

        with _mock_session(db_session), _patch_user(owner.id), \
             patch("mcp_server.db.dispatch_task") as mock_dispatch:
            mock_dispatch.return_value = MagicMock(id="celery-3")
            result = product_run_analysis(
                product_a.id, web_research=False,
                source_urls=["https://example.com/page"],
            )
            assert "error" not in result

            job = db_session.query(QueueJob).filter(QueueJob.id == result["job_id"]).one()
            assert job.input_data["web_research_enabled"] is False
            assert job.input_data["source_urls"] == ["https://example.com/page"]

    def test_too_many_source_urls_returns_structured_error(
        self, db_session, product_a, owner
    ):
        from mcp_server.tools.product import product_run_analysis

        product_a.product_description = "A very detailed product description that easily exceeds fifty characters in length."
        db_session.commit()

        with _mock_session(db_session), _patch_user(owner.id):
            result = product_run_analysis(
                product_a.id, web_research=False,
                source_urls=[f"https://example.com/p{i}" for i in range(6)],
            )
            assert "error" in result
            assert result["error_code"] == "SCOPED_INPUT_LIMIT_EXCEEDED"
            # No job should be queued
            jobs = db_session.query(QueueJob).filter(
                QueueJob.product_id == product_a.id,
                QueueJob.job_type == JobType.PRODUCT_ANALYSIS,
            ).all()
            assert len(jobs) == 0


# ---------------------------------------------------------------------------
# Phase B — ci_refresh_research: force cache refresh
# ---------------------------------------------------------------------------

class TestCiRefreshResearch:
    def test_owner_refreshes_cache(
        self, db_session, product_a, competitor, owner
    ):
        from mcp_server.tools.competitive import ci_refresh_research

        fake_results = [
            {"url": "https://rival.co/features", "title": "Features", "snippet": "x"},
            {"url": "https://rival.co/pricing", "title": "Pricing", "snippet": "y"},
        ]
        fake_cache = MagicMock()
        fake_cache.refresh.return_value = fake_results

        # After the MCP tool calls refresh(), it reads competitor.cached_search_at
        # for the return payload — simulate that the service wrote a timestamp.
        def _set_timestamp(comp, *_args, **_kw):
            from datetime import datetime, timezone
            comp.cached_search_at = datetime.now(timezone.utc)
            comp.cached_search_results = fake_results
            return fake_results
        fake_cache.refresh.side_effect = _set_timestamp

        with _mock_session(db_session), _patch_user(owner.id), \
             patch(
                 "app.services.competitor_research_cache.CompetitorResearchCache",
                 return_value=fake_cache,
             ):
            result = ci_refresh_research(product_a.id, "Rival")

        assert "error" not in result
        assert result["competitor_id"] == competitor.id
        assert result["competitor_name"] == "Rival Co"
        assert result["results_count"] == 2
        assert result["cached_at"] is not None
        fake_cache.refresh.assert_called_once()

    def test_refresh_returns_error_when_competitor_not_found(
        self, db_session, product_a, owner
    ):
        from mcp_server.tools.competitive import ci_refresh_research

        with _mock_session(db_session), _patch_user(owner.id):
            result = ci_refresh_research(product_a.id, "Nonexistent Competitor")
            assert "error" in result
            assert "competitor matching" in result["error"]

    def test_refresh_denied_for_outsider(
        self, db_session, product_a, competitor, outsider
    ):
        from mcp_server.tools.competitive import ci_refresh_research

        with _mock_session(db_session), _patch_user(outsider.id):
            result = ci_refresh_research(product_a.id, "Rival")
            assert "error" in result


# ---------------------------------------------------------------------------
# Inactive-competitor handling (resolver routing)
# ---------------------------------------------------------------------------

class TestInactiveCompetitorHandling:
    def _deactivate(self, db_session, competitor):
        competitor.status = "inactive"
        db_session.commit()

    def test_set_tracked_rejects_inactive(self, db_session, product_a, owner, competitor):
        from mcp_server.tools.competitive import ci_set_tracked

        self._deactivate(db_session, competitor)
        with _mock_session(db_session), _patch_user(owner.id):
            result = ci_set_tracked(product_a.id, "Rival", True)
            assert "error" in result
            assert "active competitor" in result["error"]

    def test_refresh_research_rejects_inactive(self, db_session, product_a, owner, competitor):
        from mcp_server.tools.competitive import ci_refresh_research

        self._deactivate(db_session, competitor)
        with _mock_session(db_session), _patch_user(owner.id):
            result = ci_refresh_research(product_a.id, "Rival")
            assert "error" in result
            assert "active competitor" in result["error"]

    def test_run_audit_rejects_inactive(self, db_session, product_a, owner, competitor):
        from mcp_server.tools.competitive import ci_run_competitor_audit

        self._deactivate(db_session, competitor)
        with _mock_session(db_session), _patch_user(owner.id):
            result = ci_run_competitor_audit(product_a.id, "Rival")
            assert "error" in result
            assert "active competitor" in result["error"]

    def test_add_competitor_reactivates_inactive(self, db_session, product_a, owner, competitor):
        from mcp_server.tools.competitive import ci_add_competitor

        competitor.status = "inactive"
        competitor.tracked = False
        db_session.commit()

        with _mock_session(db_session), _patch_user(owner.id):
            result = ci_add_competitor(product_a.id, "Rival Co", "https://rival.co")
            assert "error" not in result
            assert "reactivated" in result["message"]

        db_session.refresh(competitor)
        assert competitor.status == "active"
        assert competitor.tracked is True

    def test_add_competitor_still_blocks_active_duplicate(self, db_session, product_a, owner, competitor):
        from mcp_server.tools.competitive import ci_add_competitor

        with _mock_session(db_session), _patch_user(owner.id):
            result = ci_add_competitor(product_a.id, "Rival Co", "https://rival.co")
            assert "error" in result
            assert "already exists" in result["error"]

    def test_evidence_list_unmatched_competitor_errors(self, db_session, product_a, viewer, viewer_access):
        from mcp_server.tools.evidence import evidence_list

        with _mock_session(db_session), _patch_user(viewer.id):
            result = evidence_list(product_a.id, competitor_name="NoSuchCo")
            assert "error" in result
            assert "No competitor matching" in result["error"]


# ---------------------------------------------------------------------------
# search_internal_themes helper + internal_get_signals
# ---------------------------------------------------------------------------

class TestSearchInternalThemes:
    def _make_themes(self, db_session, product_a):
        from app.models.internal_feedback import (
            InternalFeedbackImport, WinLossTheme, SupportTheme,
        )
        imp = InternalFeedbackImport(product_id=product_a.id, status="completed", filename="test.json")
        db_session.add(imp)
        db_session.flush()
        db_session.add(WinLossTheme(
            product_id=product_a.id, import_id=imp.id,
            theme_name="Reporting exports", outcome="lost",
            deal_count=3, total_value=45000.0,
            feature_keywords=["export", "csv"],
            jtbd_statement="Export data for analysis",
        ))
        db_session.add(SupportTheme(
            product_id=product_a.id, import_id=imp.id,
            theme_name="Dashboard confusion", category="usability",
            ticket_count=12, urgency_indicator="high",
            feature_keywords=["dashboard"],
            jtbd_statement="Understand account health at a glance",
        ))
        db_session.commit()

    def test_matches_theme_name_and_keywords(self, db_session, product_a, viewer, viewer_access):
        from mcp_server.tools.internal import search_internal_themes

        self._make_themes(db_session, product_a)

        wl, st = search_internal_themes(db_session, product_a.id, "export")
        assert len(wl) == 1
        assert wl[0]["theme_name"] == "Reporting exports"
        assert wl[0]["jtbd_statement"] == "Export data for analysis"
        assert st == []

        wl2, st2 = search_internal_themes(db_session, product_a.id, "dashboard")
        assert wl2 == []
        assert len(st2) == 1
        assert st2[0]["category"] == "usability"

    def test_internal_get_signals_uses_helper(self, db_session, product_a, viewer, viewer_access):
        from mcp_server.tools.internal import internal_get_signals

        self._make_themes(db_session, product_a)

        with _mock_session(db_session), _patch_user(viewer.id):
            result = internal_get_signals(product_a.id, "export")
            assert "error" not in result
            assert len(result["winloss_matches"]) == 1
            assert result["winloss_matches"][0]["jtbd_statement"] == "Export data for analysis"


# ---------------------------------------------------------------------------
# synthesis_get_sources freshness flags
# ---------------------------------------------------------------------------

class TestSynthesisGetSourcesFreshness:
    def test_stale_competitive_report_flagged(self, db_session, product_a, owner, competitor):
        from datetime import datetime, timezone
        from mcp_server.tools.synthesis import synthesis_get_sources

        db_session.add(CompetitorFunctionalReport(
            product_competitor_id=competitor.id,
            product_id=product_a.id,
            report_version=1,
            generated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        ))
        db_session.commit()

        with _mock_session(db_session), _patch_user(owner.id):
            result = synthesis_get_sources(product_a.id)
            assert result["sources"]["competitive_landscape"]["is_stale"] is True
            assert result["synthesis"]["has_report"] is False
            assert result["synthesis"]["synthesis_stale"] is False
            assert "job_map" in result

    def test_fresh_report_not_flagged(self, db_session, product_a, owner, competitor):
        from datetime import datetime, timezone
        from mcp_server.tools.synthesis import synthesis_get_sources

        db_session.add(CompetitorFunctionalReport(
            product_competitor_id=competitor.id,
            product_id=product_a.id,
            report_version=1,
            generated_at=datetime.now(timezone.utc),
        ))
        db_session.commit()

        with _mock_session(db_session), _patch_user(owner.id):
            result = synthesis_get_sources(product_a.id)
            assert result["sources"]["competitive_landscape"]["is_stale"] is False

    def test_synthesis_stale_when_newer_signals_exist(self, db_session, product_a, owner, competitor):
        from datetime import datetime, timezone
        from app.models.synthesis import SynthesisReport
        from mcp_server.tools.synthesis import synthesis_get_sources

        db_session.add(SynthesisReport(
            product_id=product_a.id,
            report_version=1,
            included_source_types=["competitive"],
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ))
        db_session.add(CompetitorFunctionalReport(
            product_competitor_id=competitor.id,
            product_id=product_a.id,
            report_version=1,
            generated_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        ))
        db_session.commit()

        with _mock_session(db_session), _patch_user(owner.id):
            result = synthesis_get_sources(product_a.id)
            assert result["synthesis"]["has_report"] is True
            assert result["synthesis"]["synthesis_stale"] is True


# ---------------------------------------------------------------------------
# ideas_import / ideas_get_triage / ideas_mark_exported — external boundary
# ---------------------------------------------------------------------------

def _import_record(external_id="EXT-1", **overrides):
    record = {
        "external_id": external_id,
        "title": f"External idea {external_id}",
        "description": "Imported from an external board",
    }
    record.update(overrides)
    return record


class TestIdeasImport:
    def _run(self, db_session, user_id, product_id, records, **kwargs):
        from mcp_server.tools.ideas import ideas_import

        with _mock_session(db_session), _patch_user(user_id), \
                patch("mcp_server.db.dispatch_task") as dispatch:
            counter = iter(range(10_000))
            dispatch.side_effect = lambda *a, **k: MagicMock(id=f"celery-{next(counter)}")
            result = ideas_import(product_id, "aha", records, **kwargs)
        return result, dispatch

    def test_creates_ideas_with_provenance_and_dispatch(self, db_session, product_a, owner):
        result, dispatch = self._run(
            db_session, owner.id, product_a.id,
            [_import_record("EXT-1", vote_count=12), _import_record("EXT-2")],
        )
        assert "error" not in result
        assert result["created"] == 2
        assert result["skipped"] == 0
        assert dispatch.call_count == 2
        assert all(i["job_uuid"] for i in result["ideas"])

        idea = db_session.query(Idea).filter(
            Idea.external_id == "EXT-1", Idea.external_source == "aha"
        ).one()
        assert idea.product_id == product_a.id
        assert idea.source_type == SourceType.EXTERNAL_SUBMISSION
        assert idea.status == IdeaStatus.PENDING
        assert idea.source_metadata["external_vote_count"] == 12
        assert "job_id_key" not in idea.source_metadata

    def test_conflict_skip_update_error(self, db_session, product_a, owner):
        self._run(db_session, owner.id, product_a.id, [_import_record("EXT-1", vote_count=5)])

        # skip (default)
        result, dispatch = self._run(
            db_session, owner.id, product_a.id, [_import_record("EXT-1")])
        assert result["skipped"] == 1 and result["created"] == 0
        assert dispatch.call_count == 0

        # update: refreshes content + external metadata, never re-triages
        result, dispatch = self._run(
            db_session, owner.id, product_a.id,
            [_import_record("EXT-1", title="Updated title", vote_count=40,
                            external_status="Shipped")],
            on_conflict="update",
        )
        assert result["updated"] == 1
        assert dispatch.call_count == 0
        idea = db_session.query(Idea).filter(Idea.external_id == "EXT-1").one()
        assert idea.title == "Updated title"
        assert idea.source_metadata["external_vote_count"] == 40
        assert idea.source_metadata["external_status"] == "Shipped"
        assert idea.status == IdeaStatus.PENDING  # untouched triage state

        # error mode: record-level error, batch continues
        result, _ = self._run(
            db_session, owner.id, product_a.id,
            [_import_record("EXT-1"), _import_record("EXT-3")],
            on_conflict="error",
        )
        assert result["created"] == 1
        assert len(result["errors"]) == 1
        assert "already imported" in result["errors"][0]["error"]

    def test_same_external_id_different_product_ok(self, db_session, product_a, product_b, owner):
        result, _ = self._run(db_session, owner.id, product_a.id, [_import_record("EXT-9")])
        assert result["created"] == 1
        result, _ = self._run(db_session, owner.id, product_b.id, [_import_record("EXT-9")])
        assert result["created"] == 1

    def test_auto_triage_false_creates_no_jobs(self, db_session, product_a, owner):
        from app.models.queue import QueueJob

        before = db_session.query(QueueJob).count()
        result, dispatch = self._run(
            db_session, owner.id, product_a.id, [_import_record("EXT-NT")],
            auto_triage=False,
        )
        assert result["created"] == 1
        assert dispatch.call_count == 0
        assert db_session.query(QueueJob).count() == before

    def test_invalid_records_do_not_abort_batch(self, db_session, product_a, owner):
        result, _ = self._run(
            db_session, owner.id, product_a.id,
            [
                {"external_id": "", "title": "x", "description": "y"},
                _import_record("EXT-OK"),
                {"external_id": "EXT-BAD", "title": "", "description": "y"},
            ],
        )
        assert result["created"] == 1
        assert len(result["errors"]) == 2

    def test_batch_cap(self, db_session, product_a, owner):
        records = [_import_record(f"EXT-{i}") for i in range(51)]
        result, _ = self._run(db_session, owner.id, product_a.id, records)
        assert "error" in result
        assert "Batch too large" in result["error"]

    def test_viewer_denied(self, db_session, product_a, viewer, viewer_access):
        result, _ = self._run(db_session, viewer.id, product_a.id, [_import_record()])
        assert "error" in result
        assert "EDIT" in result["error"]

    def test_structure_with_llm_fills_missing_fields(self, db_session, product_a, owner):
        from mcp_server.tools.ideas import ideas_import

        with _mock_session(db_session), _patch_user(owner.id), \
                patch("mcp_server.db.dispatch_task") as dispatch, \
                patch("app.services.llm_service.LLMService") as llm_cls:
            dispatch.side_effect = lambda *a, **k: MagicMock(id="celery-s1")
            llm_cls.return_value.structure_idea.return_value = {
                "title": "ignored", "what": "ignored",
                "why": "Structured why", "use_case": "Structured use case",
                "category": "Reporting",
            }
            result = ideas_import(
                product_a.id, "canny", [_import_record("EXT-S")],
                structure_with_llm=True,
            )

        assert result["created"] == 1
        llm_cls.return_value.structure_idea.assert_called_once()
        idea = db_session.query(Idea).filter(Idea.external_id == "EXT-S").one()
        assert idea.why_description == "Structured why"
        assert idea.use_case_description == "Structured use case"
        assert idea.category == "Reporting"


class TestIdeasGetTriage:
    def test_pending_idea(self, db_session, product_a, viewer, viewer_access, idea):
        from mcp_server.tools.ideas import ideas_get_triage

        idea.status = IdeaStatus.PENDING
        db_session.commit()

        with _mock_session(db_session), _patch_user(viewer.id):
            result = ideas_get_triage(idea.id)
            assert result["triaged"] is False
            assert result["status"] == "pending"
            assert "job_get_status" in result["message"]

    def test_full_verdict(self, db_session, product_a, viewer, viewer_access, idea, owner):
        from app.models.competitor_intelligence import ProductJob
        from app.models.competitor_intelligence import JobType as PJJobType
        from mcp_server.tools.ideas import ideas_get_triage

        duplicate_target = Idea(
            title="Original idea", what_description="d", why_description="w",
            use_case_description="u", product_id=product_a.id, submitter_id=owner.id,
            source_type=SourceType.CUSTOMER_SUBMISSION, status=IdeaStatus.ACCEPTED,
            is_active=True,
        )
        db_session.add(duplicate_target)
        db_session.flush()

        pj = ProductJob(
            product_id=product_a.id, job_id_key="j1",
            statement="Understand account health", job_type=PJJobType.FUNCTIONAL,
            status="active",
        )
        db_session.add(pj)

        idea.status = IdeaStatus.FEATURE_EXISTS
        idea.is_active = False
        idea.triage_recommendation = "reject"
        idea.triage_confidence = 0.93
        idea.triage_reasoning = "Feature already exists"
        idea.category = "Reporting"
        idea.auto_categorized = True
        idea.jtbd_statement = "When reporting, I want exports"
        idea.duplicate_of_idea_id = duplicate_target.id
        idea.similarity_score = 0.97
        idea.job_id_key = "j1"
        idea.auto_response_text = "This capability already exists."
        idea.external_id = "EXT-42"
        idea.external_source = "aha"
        idea.competitive_context = {
            "competitors_with_feature": ["Comp A"],
            "competitive_urgency": "high",
            "existing_feature": {
                "feature_name": "CSV Export",
                "feature_description": "Existing export",
                "similarity_score": 0.91,
                "source_url": "https://docs.example.com/export",
            },
        }
        db_session.commit()

        with _mock_session(db_session), _patch_user(viewer.id):
            verdict = ideas_get_triage(idea.id)

        assert verdict["triaged"] is True
        assert verdict["status"] == "feature_exists"
        assert verdict["recommendation"] == "reject"
        assert verdict["confidence"] == 0.93
        assert verdict["duplicate"]["duplicate_of_idea_id"] == duplicate_target.id
        assert verdict["duplicate"]["duplicate_of_title"] == "Original idea"
        assert verdict["feature_exists"]["feature_name"] == "CSV Export"
        assert verdict["competitive"]["competitors_with_feature"] == ["Comp A"]
        assert verdict["competitive"]["competitive_urgency"] == "high"
        assert verdict["job_link"]["job_id_key"] == "j1"
        assert verdict["job_link"]["job_statement"] == "Understand account health"
        assert verdict["external"] == {"external_id": "EXT-42", "external_source": "aha"}

    def test_outsider_denied(self, db_session, product_a, outsider, idea):
        from mcp_server.tools.ideas import ideas_get_triage

        with _mock_session(db_session), _patch_user(outsider.id):
            result = ideas_get_triage(idea.id)
            assert "error" in result


class TestIdeasMarkExported:
    def test_stamps_provenance_and_dedupes_future_imports(self, db_session, product_a, owner, idea):
        from mcp_server.tools.ideas import ideas_import, ideas_mark_exported

        with _mock_session(db_session), _patch_user(owner.id):
            result = ideas_mark_exported(idea.id, "AHA-77", "aha")
            assert "error" not in result

        db_session.refresh(idea)
        assert idea.external_id == "AHA-77"
        assert idea.external_source == "aha"

        # A subsequent import of the same external record dedupes against it
        with _mock_session(db_session), _patch_user(owner.id), \
                patch("mcp_server.db.dispatch_task"):
            result = ideas_import(product_a.id, "aha", [_import_record("AHA-77")])
        assert result["skipped"] == 1
        assert result["created"] == 0

    def test_restamp_different_provenance_errors(self, db_session, product_a, owner, idea):
        from mcp_server.tools.ideas import ideas_mark_exported

        with _mock_session(db_session), _patch_user(owner.id):
            assert "error" not in ideas_mark_exported(idea.id, "AHA-77", "aha")
            result = ideas_mark_exported(idea.id, "CANNY-1", "canny")
            assert "error" in result
            assert "refusing to overwrite" in result["error"]
            # Same provenance re-stamp is idempotent
            assert "error" not in ideas_mark_exported(idea.id, "AHA-77", "aha")

    def test_collision_with_other_idea_errors(self, db_session, product_a, owner, idea):
        from mcp_server.tools.ideas import ideas_mark_exported

        other = Idea(
            title="Other", what_description="d", why_description="w",
            use_case_description="u", product_id=product_a.id, submitter_id=owner.id,
            source_type=SourceType.CUSTOMER_SUBMISSION, status=IdeaStatus.ACCEPTED,
            external_id="AHA-77", external_source="aha",
        )
        db_session.add(other)
        db_session.commit()

        with _mock_session(db_session), _patch_user(owner.id):
            result = ideas_mark_exported(idea.id, "AHA-77", "aha")
            assert "error" in result
            assert "already linked" in result["error"]

    def test_viewer_denied(self, db_session, product_a, viewer, viewer_access, idea):
        from mcp_server.tools.ideas import ideas_mark_exported

        with _mock_session(db_session), _patch_user(viewer.id):
            result = ideas_mark_exported(idea.id, "AHA-1", "aha")
            assert "error" in result
