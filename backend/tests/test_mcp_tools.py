"""
Tool-level integration tests for MCP tools.

Verifies that permission checks are enforced at the tool level (not just
the helper), and that the evidence_add bug fix (removed undefined variables)
works end-to-end with mocked embedding/LLM services.
"""

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
        from mcp_server.tools.product import product_get_agent_config

        with _mock_session(db_session), _patch_user(owner.id):
            result = product_get_agent_config(product_a.id)
            assert "error" not in result
            assert result["configured"] is False


class TestProductUpdateAgentConfig:
    def test_creates_and_updates(self, db_session, product_a, owner):
        from mcp_server.tools.product import product_update_agent_config

        with _mock_session(db_session), _patch_user(owner.id):
            result = product_update_agent_config(
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
        from mcp_server.tools.product import product_update_agent_config

        with _mock_session(db_session), _patch_user(owner.id):
            result = product_update_agent_config(product_a.id, product_analysis_mode="hourly")
            assert "error" in result
            assert "Invalid mode" in result["error"]

    def test_viewer_denied(self, db_session, product_a, viewer, viewer_access):
        from mcp_server.tools.product import product_update_agent_config

        with _mock_session(db_session), _patch_user(viewer.id):
            result = product_update_agent_config(product_a.id, enabled=False)
            assert "error" in result
            assert "EDIT" in result["error"]
