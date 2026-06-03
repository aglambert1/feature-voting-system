"""
Tests for Competitive Agents API endpoints (Category 1B).

Covers agent configuration CRUD, competitor management,
and V2 analysis trigger endpoints.
"""

import pytest
from unittest.mock import patch, MagicMock

from app.models.competitive_agent import CompetitiveAgentConfig, AgentMode
from app.models.competitor_intelligence import CIProduct, ProductCompetitor
from conftest import auth_headers


class TestAgentConfig:

    def test_get_config_creates_default(self, client, po_user, test_product):
        resp = client.get(
            f"/product-intelligence/agents/{test_product.id}/config",
            headers=auth_headers(po_user)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["product_id"] == test_product.id
        assert data["product_analysis_mode"] == "manual"
        assert data["deep_analysis_mode"] == "manual"
        assert data["enabled"] is True

    def test_update_config(self, client, po_user, test_product):
        # First create config
        client.get(
            f"/product-intelligence/agents/{test_product.id}/config",
            headers=auth_headers(po_user)
        )
        # Update it
        resp = client.put(
            f"/product-intelligence/agents/{test_product.id}/config",
            json={
                "deep_analysis_mode": "scheduled",
                "deep_analysis_schedule": "weekly",
            },
            headers=auth_headers(po_user)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["deep_analysis_mode"] == "scheduled"
        assert data["deep_analysis_schedule"] == "weekly"

    def test_get_config_requires_auth(self, client, test_product):
        resp = client.get(
            f"/product-intelligence/agents/{test_product.id}/config"
        )
        assert resp.status_code == 401

    def test_get_config_nonexistent_product(self, client, po_user):
        resp = client.get(
            "/product-intelligence/agents/99999/config",
            headers=auth_headers(po_user)
        )
        assert resp.status_code == 404

    def test_update_config_invalid_mode(self, client, po_user, test_product):
        # Create config first
        client.get(
            f"/product-intelligence/agents/{test_product.id}/config",
            headers=auth_headers(po_user)
        )
        resp = client.put(
            f"/product-intelligence/agents/{test_product.id}/config",
            json={"deep_analysis_mode": "invalid_mode"},
            headers=auth_headers(po_user)
        )
        assert resp.status_code == 422


class TestAlerts:

    def test_list_alerts_empty(self, client, po_user, test_product):
        resp = client.get(
            f"/product-intelligence/agents/{test_product.id}/alerts",
            headers=auth_headers(po_user)
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_alert_count(self, client, po_user, test_product):
        resp = client.get(
            f"/product-intelligence/agents/{test_product.id}/alerts/count",
            headers=auth_headers(po_user)
        )
        assert resp.status_code == 200
        assert resp.json()["unread_count"] == 0


class TestCompetitorManagement:

    def test_list_competitors_empty(self, client, po_user, test_product):
        resp = client.get(
            f"/product-intelligence/agents/{test_product.id}/competitors",
            headers=auth_headers(po_user)
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_add_competitor(self, client, po_user, test_product, db_session):
        resp = client.post(
            f"/product-intelligence/agents/{test_product.id}/competitors/add",
            json={
                "competitor_name": "Rival Corp",
                "competitor_url": "https://rivalcorp.com",
            },
            headers=auth_headers(po_user)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["competitor_name"] == "Rival Corp"

    def test_add_competitor_requires_auth(self, client, test_product):
        resp = client.post(
            f"/product-intelligence/agents/{test_product.id}/competitors/add",
            json={
                "competitor_name": "Rival Corp",
                "competitor_url": "https://rivalcorp.com",
            }
        )
        assert resp.status_code == 401

    def test_add_competitor_voter_forbidden(self, client, voter_user, test_product):
        resp = client.post(
            f"/product-intelligence/agents/{test_product.id}/competitors/add",
            json={
                "competitor_name": "Rival Corp",
                "competitor_url": "https://rivalcorp.com",
            },
            headers=auth_headers(voter_user)
        )
        assert resp.status_code == 403


class TestTriggerAnalysis:

    @patch("app.api.competitive_agents.send_task")
    def test_trigger_v2_analysis(self, mock_task, client, po_user, test_product, db_session):
        # Add a tracked competitor
        competitor = ProductCompetitor(
            product_id=test_product.id,
            competitor_name="Test Rival",
            competitor_url="https://testrival.com",
            tracked=True,
        )
        db_session.add(competitor)
        db_session.commit()

        mock_result = MagicMock()
        mock_result.id = "task-v2-123"
        mock_task.return_value = mock_result

        resp = client.post(
            f"/product-intelligence/agents/{test_product.id}/run-competitive-analysis-v2",
            headers=auth_headers(po_user)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_type"] == "scheduled_deep_analysis"
        assert "job_id" in data

    def test_trigger_v2_requires_auth(self, client, test_product):
        resp = client.post(
            f"/product-intelligence/agents/{test_product.id}/run-competitive-analysis-v2"
        )
        assert resp.status_code == 401

    @patch("app.api.competitive_agents.send_task")
    def test_discover_competitors(self, mock_task, client, po_user, test_product):
        mock_result = MagicMock()
        mock_result.id = "task-dc-123"
        mock_task.return_value = mock_result

        resp = client.post(
            f"/product-intelligence/agents/{test_product.id}/discover-competitors",
            headers=auth_headers(po_user)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_type"] == "competitor_discovery"


class TestFunctionalReports:

    def test_list_functional_reports_empty(self, client, po_user, test_product):
        resp = client.get(
            f"/product-intelligence/agents/{test_product.id}/functional-reports",
            headers=auth_headers(po_user)
        )
        assert resp.status_code == 200
        assert resp.json() == []


class TestTriggerFunctionalAuditScopedInputs:
    """REST-side scoped-input params on POST .../functional-audit — must match the MCP surface."""

    @pytest.fixture
    def test_competitor(self, db_session, test_product):
        comp = ProductCompetitor(
            product_id=test_product.id,
            competitor_name="Rival Co",
            competitor_url="https://rival.co",
            status="active",
        )
        db_session.add(comp)
        db_session.commit()
        db_session.refresh(comp)
        return comp

    @patch("app.api.competitive_agents.send_task")
    def test_defaults_put_web_research_true_and_empty_urls_in_input_data(
        self, mock_task, client, po_user, db_session, test_product, test_competitor
    ):
        from app.models.queue import QueueJob, JobType
        mock_task.return_value = MagicMock(id="task-fa-1")

        resp = client.post(
            f"/product-intelligence/agents/{test_product.id}/competitors/{test_competitor.id}/functional-audit",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200
        job_uuid = resp.json()["job_uuid"]
        job = db_session.query(QueueJob).filter(
            QueueJob.job_uuid == job_uuid,
            QueueJob.job_type == JobType.FUNCTIONAL_AUDIT,
        ).one()
        assert job.input_data["web_research_enabled"] is True
        assert job.input_data["source_urls"] == []
        assert job.input_data["competitor_id"] == test_competitor.id

    @patch("app.api.competitive_agents.send_task")
    def test_scoped_params_flow_into_input_data(
        self, mock_task, client, po_user, db_session, test_product, test_competitor
    ):
        from app.models.queue import QueueJob, JobType
        mock_task.return_value = MagicMock(id="task-fa-2")

        resp = client.post(
            f"/product-intelligence/agents/{test_product.id}/competitors/{test_competitor.id}/functional-audit",
            headers=auth_headers(po_user),
            json={
                "web_research": False,
                "source_urls": ["https://rival.co/features", "https://rival.co/pricing"],
            },
        )
        assert resp.status_code == 200
        job_uuid = resp.json()["job_uuid"]
        job = db_session.query(QueueJob).filter(QueueJob.job_uuid == job_uuid).one()
        assert job.input_data["web_research_enabled"] is False
        assert job.input_data["source_urls"] == [
            "https://rival.co/features", "https://rival.co/pricing"
        ]

    def test_too_many_source_urls_returns_400_with_structured_payload(
        self, client, po_user, test_product, test_competitor
    ):
        resp = client.post(
            f"/product-intelligence/agents/{test_product.id}/competitors/{test_competitor.id}/functional-audit",
            headers=auth_headers(po_user),
            json={
                "web_research": False,
                "source_urls": [f"https://rival.co/p{i}" for i in range(6)],
            },
        )
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert detail["error_code"] == "SCOPED_INPUT_LIMIT_EXCEEDED"
        assert detail["field"] == "source_urls"
        assert detail["limit"] == 5
        assert detail["got"] == 6


class TestRefreshCompetitorResearch:
    """REST-side cache refresh endpoint — must match MCP ci_refresh_research behavior."""

    @pytest.fixture
    def test_competitor(self, db_session, test_product):
        comp = ProductCompetitor(
            product_id=test_product.id,
            competitor_name="Rival Co",
            competitor_url="https://rival.co",
            status="active",
        )
        db_session.add(comp)
        db_session.commit()
        db_session.refresh(comp)
        return comp

    def test_po_refreshes_cache(
        self, client, po_user, db_session, test_product, test_competitor
    ):
        from datetime import datetime, timezone

        fake_results = [
            {"url": "https://rival.co/features", "title": "Features", "snippet": "x"},
            {"url": "https://rival.co/pricing", "title": "Pricing", "snippet": "y"},
        ]
        fake_cache = MagicMock()

        def _set_timestamp(comp, *_args, **_kwargs):
            comp.cached_search_at = datetime.now(timezone.utc)
            comp.cached_search_results = fake_results
            return fake_results

        fake_cache.refresh.side_effect = _set_timestamp

        with patch(
            "app.services.competitor_research_cache.CompetitorResearchCache",
            return_value=fake_cache,
        ):
            resp = client.post(
                f"/product-intelligence/agents/{test_product.id}/competitors/{test_competitor.id}/refresh-research",
                headers=auth_headers(po_user),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["competitor_id"] == test_competitor.id
        assert data["competitor_name"] == "Rival Co"
        assert data["results_count"] == 2
        assert data["cached_at"] is not None
        fake_cache.refresh.assert_called_once()

    def test_refresh_404_when_competitor_missing(
        self, client, po_user, test_product
    ):
        resp = client.post(
            f"/product-intelligence/agents/{test_product.id}/competitors/99999/refresh-research",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 404

    def test_refresh_requires_auth(self, client, test_product, test_competitor):
        resp = client.post(
            f"/product-intelligence/agents/{test_product.id}/competitors/{test_competitor.id}/refresh-research",
        )
        assert resp.status_code == 401


