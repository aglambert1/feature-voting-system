"""
Tests for Job Map API endpoints (JTBD).

Covers CRUD for target customer profile and individual jobs, plus permission
checks. Embedding generation is mocked to avoid hitting the Voyage API during
tests.
"""

import pytest
from unittest.mock import patch

from app.models.competitor_intelligence import ProductJob
from conftest import auth_headers


# --- Helpers ------------------------------------------------------------------


def _mock_embedding():
    """Return a deterministic 1024-dim fake embedding."""
    return [0.1] * 1024


# `generate_embedding` is imported *inside* the handler functions
# (`from app.services.embedding_service import generate_embedding`) so we must
# patch the source module, not a re-export.
EMBED_PATCH_PATH = "app.services.embedding_service.generate_embedding"


# --- Target customer ---------------------------------------------------------


class TestSetTargetCustomer:

    def test_set_target_customer_persists_profile(self, client, po_user, test_product):
        resp = client.put(
            f"/product-intelligence/products/{test_product.id}/target-customer",
            json={
                "persona_name": "VP Product",
                "company_characteristics": "Series B SaaS",
                "key_traits": ["data-driven", "owns roadmap"],
                "hiring_criteria": "Ships with clear onboarding",
            },
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["target_customer_profile"]["persona_name"] == "VP Product"
        assert body["target_customer_profile"]["key_traits"] == [
            "data-driven",
            "owns roadmap",
        ]

    def test_set_target_customer_requires_edit_access(
        self, client, voter_user, voter_product_access, test_product
    ):
        # voter has VIEW only → should be 403 on EDIT endpoint
        resp = client.put(
            f"/product-intelligence/products/{test_product.id}/target-customer",
            json={"persona_name": "X", "key_traits": []},
            headers=auth_headers(voter_user),
        )
        assert resp.status_code == 403


# --- GET job map -------------------------------------------------------------


class TestGetJobMap:

    def test_get_job_map_empty_returns_200(self, client, po_user, test_product):
        resp = client.get(
            f"/product-intelligence/products/{test_product.id}/job-map",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["product_id"] == test_product.id
        assert body["product_name"] == test_product.product_name
        assert body["jobs"] == []
        assert body["job_map_version"] == 0
        assert body["target_customer_profile"] is None

    def test_get_job_map_forbidden_for_non_member(
        self, client, voter_user, test_product
    ):
        # voter_user has no permission on test_product
        resp = client.get(
            f"/product-intelligence/products/{test_product.id}/job-map",
            headers=auth_headers(voter_user),
        )
        assert resp.status_code == 403

    def test_get_job_map_not_found(self, client, po_user):
        resp = client.get(
            "/product-intelligence/products/999999/job-map",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 404


# --- Add job -----------------------------------------------------------------


class TestAddJob:

    def test_add_job_happy_path_increments_version(
        self, client, po_user, test_product, db_session
    ):
        with patch(EMBED_PATCH_PATH, return_value=_mock_embedding()):
            resp = client.post(
                f"/product-intelligence/products/{test_product.id}/jobs",
                json={
                    "job_id": "j1",
                    "job_type": "functional",
                    "statement": "When I'm planning a roadmap, I want to see impact data.",
                    "desired_outcomes": ["Reduce guesswork"],
                    "importance": "high",
                },
                headers=auth_headers(po_user),
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["job_id_key"] == "j1"
        assert body["job_type"] == "functional"
        assert body["importance"] == "high"
        assert body["job_map_version"] == 1

        db_session.expire_all()
        jobs = (
            db_session.query(ProductJob)
            .filter(ProductJob.product_id == test_product.id)
            .all()
        )
        assert len(jobs) == 1
        assert jobs[0].job_id_key == "j1"
        assert jobs[0].statement_embedding is not None

    def test_add_job_duplicate_returns_409(self, client, po_user, test_product):
        with patch(EMBED_PATCH_PATH, return_value=_mock_embedding()):
            first = client.post(
                f"/product-intelligence/products/{test_product.id}/jobs",
                json={
                    "job_id": "j1",
                    "job_type": "functional",
                    "statement": "First job statement",
                    "desired_outcomes": [],
                    "importance": "medium",
                },
                headers=auth_headers(po_user),
            )
            assert first.status_code == 200

            dup = client.post(
                f"/product-intelligence/products/{test_product.id}/jobs",
                json={
                    "job_id": "j1",
                    "job_type": "functional",
                    "statement": "Duplicate key",
                    "desired_outcomes": [],
                    "importance": "medium",
                },
                headers=auth_headers(po_user),
            )
        assert dup.status_code == 409


# --- Update job --------------------------------------------------------------


class TestUpdateJob:

    def test_update_job_partial_update_keeps_other_fields(
        self, client, po_user, test_product, db_session
    ):
        with patch(EMBED_PATCH_PATH, return_value=_mock_embedding()):
            create = client.post(
                f"/product-intelligence/products/{test_product.id}/jobs",
                json={
                    "job_id": "j1",
                    "job_type": "functional",
                    "statement": "Original statement",
                    "desired_outcomes": ["outcome A"],
                    "importance": "medium",
                },
                headers=auth_headers(po_user),
            )
            assert create.status_code == 200
            version_after_create = create.json()["job_map_version"]

            # Update only importance — statement + outcomes must remain
            update = client.put(
                f"/product-intelligence/products/{test_product.id}/jobs/j1",
                json={"importance": "critical"},
                headers=auth_headers(po_user),
            )
        assert update.status_code == 200
        body = update.json()
        assert body["importance"] == "critical"
        assert body["statement"] == "Original statement"
        assert body["desired_outcomes"] == ["outcome A"]
        assert body["job_map_version"] == version_after_create + 1


# --- Delete job --------------------------------------------------------------


class TestDeleteJob:

    def test_delete_job_removes_row_and_bumps_version(
        self, client, po_user, test_product, db_session
    ):
        with patch(EMBED_PATCH_PATH, return_value=_mock_embedding()):
            create = client.post(
                f"/product-intelligence/products/{test_product.id}/jobs",
                json={
                    "job_id": "j1",
                    "job_type": "functional",
                    "statement": "Job to be deleted",
                    "desired_outcomes": [],
                    "importance": "low",
                },
                headers=auth_headers(po_user),
            )
            assert create.status_code == 200
            version_after_create = create.json()["job_map_version"]

        resp = client.delete(
            f"/product-intelligence/products/{test_product.id}/jobs/j1",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["removed_job_id"] == "j1"
        assert body["job_map_version"] == version_after_create + 1

        db_session.expire_all()
        # Soft delete — row remains but status is inactive
        remaining = (
            db_session.query(ProductJob)
            .filter(ProductJob.product_id == test_product.id)
            .all()
        )
        assert len(remaining) == 1
        assert remaining[0].status == "inactive"

    def test_delete_missing_job_returns_404(self, client, po_user, test_product):
        resp = client.delete(
            f"/product-intelligence/products/{test_product.id}/jobs/nope",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 404


# --- Signal count + defaults --------------------------------------------------


class TestSignalCountAndDefaults:

    def test_get_job_map_includes_signal_count_and_updated_at(
        self, client, po_user, test_product
    ):
        with patch(EMBED_PATCH_PATH, return_value=_mock_embedding()):
            client.post(
                f"/product-intelligence/products/{test_product.id}/jobs",
                json={
                    "job_id": "j1",
                    "statement": "When I need insight, I want data.",
                    "desired_outcomes": [],
                    "importance": "medium",
                },
                headers=auth_headers(po_user),
            )
        resp = client.get(
            f"/product-intelligence/products/{test_product.id}/job-map",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200
        job = resp.json()["jobs"][0]
        assert "signal_count" in job
        assert job["signal_count"] == 0
        assert "updated_at" in job
        assert job["updated_at"] is not None

    def test_add_job_defaults_job_type_to_functional(
        self, client, po_user, test_product
    ):
        with patch(EMBED_PATCH_PATH, return_value=_mock_embedding()):
            resp = client.post(
                f"/product-intelligence/products/{test_product.id}/jobs",
                json={
                    "job_id": "j1",
                    "statement": "Need without explicit job_type",
                    "desired_outcomes": [],
                    "importance": "medium",
                },
                headers=auth_headers(po_user),
            )
        assert resp.status_code == 200
        assert resp.json()["job_type"] == "functional"


# ---------------------------------------------------------------------------
# Pending job map review flow
# ---------------------------------------------------------------------------


EMBED_BATCH_PATCH_PATH = "app.services.embedding_service.generate_embeddings_batch"


def _make_pending_map():
    return {
        "functional_jobs": [
            {
                "job_id_key": "j1",
                "statement": "When reconciling accounts, I want auto-matching",
                "desired_outcomes": ["Reduce manual steps"],
                "importance": "high",
                "job_type": "functional",
            }
        ],
        "emotional_jobs": [],
        "social_jobs": [],
    }


class TestPendingJobMapFlow:

    def test_get_job_map_has_pending_false_when_none(self, client, po_user, test_product):
        resp = client.get(
            f"/product-intelligence/products/{test_product.id}/job-map",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200
        assert resp.json()["has_pending_map"] is False

    def test_pending_comparison_404_when_no_pending(self, client, po_user, test_product):
        resp = client.get(
            f"/product-intelligence/products/{test_product.id}/job-map/pending-comparison",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 404

    def test_discard_pending_idempotent_when_no_pending(self, client, po_user, test_product):
        # Discard is idempotent — returns 200 even when nothing is pending
        resp = client.delete(
            f"/product-intelligence/products/{test_product.id}/job-map/pending",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200

    def test_get_job_map_shows_has_pending_true(self, client, po_user, test_product, db_session):
        from app.models.competitor_intelligence import CIProduct
        product = db_session.query(CIProduct).filter(CIProduct.id == test_product.id).first()
        product.pending_job_map = _make_pending_map()
        db_session.commit()

        resp = client.get(
            f"/product-intelligence/products/{test_product.id}/job-map",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200
        assert resp.json()["has_pending_map"] is True

    def test_discard_pending_clears_pending(self, client, po_user, test_product, db_session):
        from app.models.competitor_intelligence import CIProduct
        product = db_session.query(CIProduct).filter(CIProduct.id == test_product.id).first()
        product.pending_job_map = _make_pending_map()
        db_session.commit()

        resp = client.delete(
            f"/product-intelligence/products/{test_product.id}/job-map/pending",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200

        map_resp = client.get(
            f"/product-intelligence/products/{test_product.id}/job-map",
            headers=auth_headers(po_user),
        )
        assert map_resp.json()["has_pending_map"] is False

    def test_pending_comparison_returns_pairs(self, client, po_user, test_product, db_session):
        from app.models.competitor_intelligence import CIProduct
        product = db_session.query(CIProduct).filter(CIProduct.id == test_product.id).first()
        product.pending_job_map = _make_pending_map()
        db_session.commit()

        with patch(EMBED_BATCH_PATCH_PATH, return_value=[_mock_embedding()]):
            resp = client.get(
                f"/product-intelligence/products/{test_product.id}/job-map/pending-comparison",
                headers=auth_headers(po_user),
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_pending"] is True
        assert len(body["pairs"]) >= 1
        pair = body["pairs"][0]
        assert "id" in pair
        assert "change_type" in pair
        assert "default_selection" in pair

    def test_apply_pending_new_job_creates_product_job(
        self, client, po_user, test_product, db_session
    ):
        from app.models.competitor_intelligence import CIProduct
        product = db_session.query(CIProduct).filter(CIProduct.id == test_product.id).first()
        product.pending_job_map = _make_pending_map()
        db_session.commit()

        new_job_data = {
            "job_id_key": "j1",
            "statement": "When reconciling accounts, I want auto-matching",
            "desired_outcomes": ["Reduce manual steps"],
            "importance": "high",
            "job_type": "functional",
        }
        selections = [
            {
                "pair_id": "pending_0",
                "choice": "new",
                "old_job_id_key": None,
                "new_job_data": new_job_data,
                "statement": new_job_data["statement"],
                "desired_outcomes": new_job_data["desired_outcomes"],
                "importance": new_job_data["importance"],
            }
        ]

        with patch(EMBED_PATCH_PATH, return_value=_mock_embedding()):
            resp = client.post(
                f"/product-intelligence/products/{test_product.id}/job-map/apply-pending",
                json={"selections": selections},
                headers=auth_headers(po_user),
            )
        assert resp.status_code == 200

        db_session.expire_all()
        pj = db_session.query(ProductJob).filter(
            ProductJob.product_id == test_product.id,
            ProductJob.job_id_key == "j1",
            ProductJob.status == "active",
        ).first()
        assert pj is not None
        assert pj.statement == "When reconciling accounts, I want auto-matching"

        product = db_session.query(CIProduct).filter(CIProduct.id == test_product.id).first()
        assert product.pending_job_map is None  # cleared after apply

    def test_apply_pending_drop_removes_existing_job(
        self, client, po_user, test_product, db_session
    ):
        # First add a real job
        with patch(EMBED_PATCH_PATH, return_value=_mock_embedding()):
            client.post(
                f"/product-intelligence/products/{test_product.id}/jobs",
                json={
                    "job_id": "j_old",
                    "statement": "Old job to be dropped",
                    "desired_outcomes": [],
                    "importance": "medium",
                },
                headers=auth_headers(po_user),
            )
        # Set a pending map that doesn't include j_old
        from app.models.competitor_intelligence import CIProduct
        product = db_session.query(CIProduct).filter(CIProduct.id == test_product.id).first()
        product.pending_job_map = {"functional_jobs": [], "emotional_jobs": [], "social_jobs": []}
        db_session.commit()

        selections = [
            {
                "pair_id": "removed_j_old",
                "choice": "drop",
                "old_job_id_key": "j_old",
                "new_job_data": None,
                "statement": "",
                "desired_outcomes": [],
                "importance": "medium",
            }
        ]

        with patch(EMBED_PATCH_PATH, return_value=_mock_embedding()):
            resp = client.post(
                f"/product-intelligence/products/{test_product.id}/job-map/apply-pending",
                json={"selections": selections},
                headers=auth_headers(po_user),
            )
        assert resp.status_code == 200

        db_session.expire_all()
        active = db_session.query(ProductJob).filter(
            ProductJob.product_id == test_product.id,
            ProductJob.job_id_key == "j_old",
            ProductJob.status == "active",
        ).first()
        assert active is None
