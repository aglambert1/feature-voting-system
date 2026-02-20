"""
Tests for Synthesis API endpoints (Category 1B).

Covers synthesis status, triggering runs, retrieving results,
and creating ideas from opportunities.
"""

import pytest
from unittest.mock import patch, MagicMock

from app.models.synthesis import SynthesisRun
from tests.conftest import auth_headers


class TestSynthesisStatus:

    def test_get_status(self, client, po_user, test_product):
        resp = client.get(
            f"/synthesis/{test_product.id}/status",
            headers=auth_headers(po_user)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "sources_available" in data
        assert data["product_id"] == test_product.id
        assert data["has_previous_run"] is False

    def test_get_status_requires_auth(self, client, test_product):
        resp = client.get(f"/synthesis/{test_product.id}/status")
        assert resp.status_code == 401

    def test_get_status_nonexistent_product(self, client, po_user):
        resp = client.get(
            "/synthesis/99999/status",
            headers=auth_headers(po_user)
        )
        assert resp.status_code == 404


class TestTriggerSynthesis:

    @patch("app.api.synthesis.send_task")
    def test_trigger_synthesis(self, mock_task, client, po_user, test_product, db_session):
        # Synthesis requires at least one source of data.
        # Add an accepted idea so there's customer data.
        from app.models.idea import Idea, IdeaStatus, SourceType
        idea = Idea(
            title="Source idea for synthesis",
            what_description="A feature idea providing customer data",
            why_description="Users want this capability",
            use_case_description="Used to validate synthesis has source data",
            product_id=test_product.id,
            submitter_id=po_user.id,
            source_type=SourceType.CUSTOMER_SUBMISSION,
            status=IdeaStatus.ACCEPTED,
            is_active=True,
        )
        db_session.add(idea)
        db_session.commit()

        mock_result = MagicMock()
        mock_result.id = "task-syn-123"
        mock_task.return_value = mock_result

        resp = client.post(
            f"/synthesis/{test_product.id}/run",
            headers=auth_headers(po_user)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["product_id"] == test_product.id
        assert data["status"] in ("pending", "processing")

    def test_trigger_synthesis_requires_auth(self, client, test_product):
        resp = client.post(f"/synthesis/{test_product.id}/run")
        assert resp.status_code == 401

    def test_trigger_synthesis_voter_forbidden(self, client, voter_user, test_product):
        resp = client.post(
            f"/synthesis/{test_product.id}/run",
            headers=auth_headers(voter_user)
        )
        assert resp.status_code == 403

    def test_trigger_synthesis_no_source_data(self, client, po_user, test_product):
        """Triggering synthesis with no source data returns 400."""
        resp = client.post(
            f"/synthesis/{test_product.id}/run",
            headers=auth_headers(po_user)
        )
        assert resp.status_code == 400
        assert "no source data" in resp.json()["detail"].lower()


class TestSynthesisRuns:

    def test_list_runs_empty(self, client, po_user, test_product):
        resp = client.get(
            f"/synthesis/{test_product.id}/runs",
            headers=auth_headers(po_user)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["runs"] == []
        assert data["total"] == 0

    def test_list_runs_requires_auth(self, client, test_product):
        resp = client.get(f"/synthesis/{test_product.id}/runs")
        assert resp.status_code == 401

    def test_get_run_not_found(self, client, po_user, test_product):
        resp = client.get(
            f"/synthesis/{test_product.id}/runs/99999",
            headers=auth_headers(po_user)
        )
        assert resp.status_code == 404

    def test_get_run_results(self, client, po_user, test_product, db_session):
        run = SynthesisRun(
            product_id=test_product.id,
            status="completed",
            sources_used=["competitive", "customer"],
        )
        db_session.add(run)
        db_session.commit()
        db_session.refresh(run)

        resp = client.get(
            f"/synthesis/{test_product.id}/runs/{run.id}",
            headers=auth_headers(po_user)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["run"]["id"] == run.id
        assert data["run"]["status"] == "completed"
