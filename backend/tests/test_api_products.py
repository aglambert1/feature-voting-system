"""
Tests for Products API endpoints (Category 1B).

Covers product CRUD, listing with permissions, and job status.
"""

import pytest
from unittest.mock import patch, MagicMock

from app.models.competitor_intelligence import CIProduct
from app.models.user import UserRole
from conftest import auth_headers


class TestCreateProduct:

    def test_create_product_as_po(self, client, po_user):
        resp = client.post("/product-intelligence/products", json={
            "product_name": "New Product",
            "product_description": "A new product for testing product creation endpoint",
        }, headers=auth_headers(po_user))
        assert resp.status_code == 201
        data = resp.json()
        assert data["product_name"] == "New Product"
        assert data["created_by_user_id"] == po_user.id
        assert data["analysis_version"] == 0

    def test_create_product_as_admin(self, client, admin_user):
        resp = client.post("/product-intelligence/products", json={
            "product_name": "Admin Product",
            "product_description": "A product created by admin for testing",
        }, headers=auth_headers(admin_user))
        assert resp.status_code == 201

    def test_create_product_as_voter_forbidden(self, client, voter_user):
        resp = client.post("/product-intelligence/products", json={
            "product_name": "Voter Product",
            "product_description": "Voters should not create products",
        }, headers=auth_headers(voter_user))
        assert resp.status_code == 403

    def test_create_product_requires_auth(self, client):
        resp = client.post("/product-intelligence/products", json={
            "product_name": "No Auth Product",
            "product_description": "Should fail without authentication",
        })
        assert resp.status_code == 401

    def test_create_product_missing_name(self, client, po_user):
        resp = client.post("/product-intelligence/products", json={
            "product_description": "Missing the product name field",
        }, headers=auth_headers(po_user))
        assert resp.status_code == 422

    def test_create_product_short_description(self, client, po_user):
        resp = client.post("/product-intelligence/products", json={
            "product_name": "Short Desc",
            "product_description": "Too short",
        }, headers=auth_headers(po_user))
        assert resp.status_code == 422


class TestListProducts:

    def test_list_products_returns_owned(self, client, po_user, test_product):
        resp = client.get(
            "/product-intelligence/products",
            headers=auth_headers(po_user)
        )
        assert resp.status_code == 200
        names = [p["product_name"] for p in resp.json()]
        assert "Test Product" in names

    def test_list_products_admin_sees_only_accessible(self, client, admin_user, db_session, test_product):
        from app.models.competitor_intelligence import ProductPermission, ProductPermissionLevel
        perm = ProductPermission(
            product_id=test_product.id,
            user_id=admin_user.id,
            permission_level=ProductPermissionLevel.OWNER,
            granted_by_user_id=admin_user.id,
        )
        db_session.add(perm)
        db_session.commit()
        resp = client.get(
            "/product-intelligence/products",
            headers=auth_headers(admin_user)
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_list_products_requires_auth(self, client):
        resp = client.get("/product-intelligence/products")
        assert resp.status_code == 401


class TestGetProduct:

    def test_get_product_by_id(self, client, po_user, test_product):
        resp = client.get(
            f"/product-intelligence/products/{test_product.id}",
            headers=auth_headers(po_user)
        )
        assert resp.status_code == 200
        assert resp.json()["product_name"] == "Test Product"

    def test_get_product_not_found(self, client, po_user):
        resp = client.get(
            "/product-intelligence/products/99999",
            headers=auth_headers(po_user)
        )
        assert resp.status_code == 404

    def test_get_product_voter_without_access_denied(self, client, voter_user, test_product):
        """Voter without product permission gets 404 (product hidden)."""
        resp = client.get(
            f"/product-intelligence/products/{test_product.id}",
            headers=auth_headers(voter_user)
        )
        assert resp.status_code == 404

    def test_get_product_voter_with_access_succeeds(self, client, voter_user, test_product, voter_product_access):
        """Voter with VIEW permission can access the product."""
        resp = client.get(
            f"/product-intelligence/products/{test_product.id}",
            headers=auth_headers(voter_user)
        )
        assert resp.status_code == 200
        assert resp.json()["product_name"] == test_product.product_name


class TestUpdateProduct:

    def test_update_product_name(self, client, po_user, test_product):
        resp = client.patch(
            f"/product-intelligence/products/{test_product.id}",
            json={"product_name": "Updated Product Name"},
            headers=auth_headers(po_user)
        )
        assert resp.status_code == 200
        assert resp.json()["product_name"] == "Updated Product Name"

    def test_update_product_not_found(self, client, po_user):
        resp = client.patch(
            "/product-intelligence/products/99999",
            json={"product_name": "Ghost"},
            headers=auth_headers(po_user)
        )
        # Permission check runs before product lookup, so returns 403
        assert resp.status_code == 403


class TestDeleteProduct:

    def test_delete_product(self, client, po_user, test_product):
        resp = client.delete(
            f"/product-intelligence/products/{test_product.id}",
            headers=auth_headers(po_user)
        )
        assert resp.status_code == 200

    def test_delete_product_not_found(self, client, po_user):
        resp = client.delete(
            "/product-intelligence/products/99999",
            headers=auth_headers(po_user)
        )
        # Permission check runs before product lookup, so returns 403
        assert resp.status_code == 403


class TestProductJobs:

    def test_list_jobs_empty(self, client, po_user, test_product):
        resp = client.get(
            f"/product-intelligence/products/{test_product.id}/jobs",
            headers=auth_headers(po_user)
        )
        assert resp.status_code == 200
        assert resp.json() == []


class TestQueueProductAnalysisScopedInputs:
    """REST-side scoped-input params on POST .../analyze/queue — must match the MCP surface."""

    @patch("app.api.products.send_task")
    def test_defaults_put_web_research_true_and_empty_urls_in_input_data(
        self, mock_task, client, po_user, db_session, test_product
    ):
        from app.models.queue import QueueJob, JobType
        mock_task.return_value = MagicMock(id="task-qa-1")

        resp = client.post(
            f"/product-intelligence/products/{test_product.id}/analyze/queue",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200
        job_uuid = resp.json()["job_uuid"]
        job = db_session.query(QueueJob).filter(
            QueueJob.job_uuid == job_uuid,
            QueueJob.job_type == JobType.PRODUCT_ANALYSIS,
        ).one()
        assert job.input_data["web_research_enabled"] is True
        assert job.input_data["source_urls"] == []

    @patch("app.api.products.send_task")
    def test_scoped_params_flow_into_input_data(
        self, mock_task, client, po_user, db_session, test_product
    ):
        from app.models.queue import QueueJob, JobType
        mock_task.return_value = MagicMock(id="task-qa-2")

        resp = client.post(
            f"/product-intelligence/products/{test_product.id}/analyze/queue",
            headers=auth_headers(po_user),
            json={
                "web_research": False,
                "source_urls": ["https://example.com/features"],
            },
        )
        assert resp.status_code == 200
        job_uuid = resp.json()["job_uuid"]
        job = db_session.query(QueueJob).filter(QueueJob.job_uuid == job_uuid).one()
        assert job.input_data["web_research_enabled"] is False
        assert job.input_data["source_urls"] == ["https://example.com/features"]

    def test_too_many_source_urls_returns_400_with_structured_payload(
        self, client, po_user, test_product
    ):
        resp = client.post(
            f"/product-intelligence/products/{test_product.id}/analyze/queue",
            headers=auth_headers(po_user),
            json={
                "web_research": False,
                "source_urls": [f"https://example.com/p{i}" for i in range(6)],
            },
        )
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert detail["error_code"] == "SCOPED_INPUT_LIMIT_EXCEEDED"
        assert detail["field"] == "source_urls"
        assert detail["limit"] == 5
        assert detail["got"] == 6
