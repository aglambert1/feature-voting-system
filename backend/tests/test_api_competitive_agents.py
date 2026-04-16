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
        # Add a competitor with deep analysis enabled
        competitor = ProductCompetitor(
            product_id=test_product.id,
            competitor_name="Test Rival",
            competitor_url="https://testrival.com",
            deep_analysis_enabled=True,
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


