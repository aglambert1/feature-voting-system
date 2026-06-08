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
        remaining = (
            db_session.query(ProductJob)
            .filter(ProductJob.product_id == test_product.id)
            .all()
        )
        assert len(remaining) == 0

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
