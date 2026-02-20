"""
Tests for Submissions API endpoints (Category 1B).

Covers AI-powered idea structuring and submission with triage.
"""

import pytest
from unittest.mock import patch, MagicMock

from conftest import auth_headers


class TestStructureFreeformText:

    @patch("app.api.submissions.llm_service")
    def test_structure_success(self, mock_llm, client, voter_user, test_product):
        mock_llm.structure_idea.return_value = {
            "title": "AI Generated Title",
            "what_description": "What the feature does",
            "why_description": "Why it matters to users",
            "use_case_description": "How users would use it",
            "processing_time": 1.5,
        }
        resp = client.post("/submissions/structure", json={
            "freeform_text": "I think we should add a way to export data to CSV format for reports",
            "product_id": test_product.id,
        }, headers=auth_headers(voter_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "AI Generated Title"
        assert "processing_time" in data

    def test_structure_requires_auth(self, client, test_product):
        resp = client.post("/submissions/structure", json={
            "freeform_text": "I think we should add a way to export data to CSV format for reports",
            "product_id": test_product.id,
        })
        assert resp.status_code == 401

    def test_structure_text_too_short(self, client, voter_user, test_product):
        resp = client.post("/submissions/structure", json={
            "freeform_text": "short",
            "product_id": test_product.id,
        }, headers=auth_headers(voter_user))
        assert resp.status_code == 422

    def test_structure_product_not_found(self, client, voter_user):
        resp = client.post("/submissions/structure", json={
            "freeform_text": "I think we should add a way to export data to CSV format for reports",
            "product_id": 99999,
        }, headers=auth_headers(voter_user))
        assert resp.status_code == 404


class TestSubmitIdea:

    @patch("app.utils.celery_utils.send_celery_task")
    def test_submit_success(self, mock_celery, client, voter_user, test_product):
        mock_result = MagicMock()
        mock_result.id = "task-123"
        mock_celery.return_value = mock_result

        resp = client.post("/submissions/submit", json={
            "original_freeform_text": "I want a feature to export data to CSV files for reporting",
            "title": "CSV Export Feature",
            "what_description": "Add ability to export data to CSV format",
            "why_description": "Users need to share data with external tools",
            "use_case_description": "User clicks export button and gets a CSV file downloaded",
            "product_id": test_product.id,
        }, headers=auth_headers(voter_user))
        assert resp.status_code == 201
        data = resp.json()
        assert data["idea_title"] == "CSV Export Feature"
        assert "idea_id" in data

    def test_submit_requires_auth(self, client, test_product):
        resp = client.post("/submissions/submit", json={
            "original_freeform_text": "I want a feature to export data to CSV files for reporting",
            "title": "CSV Export",
            "what_description": "Add ability to export data to CSV format",
            "why_description": "Users need to share data with external tools",
            "use_case_description": "User clicks export button and gets a CSV file downloaded",
            "product_id": test_product.id,
        })
        assert resp.status_code == 401

    def test_submit_product_not_found(self, client, voter_user):
        resp = client.post("/submissions/submit", json={
            "original_freeform_text": "I want a feature to export data to CSV files for reporting",
            "title": "CSV Export",
            "what_description": "Add ability to export data to CSV format",
            "why_description": "Users need to share data with external tools",
            "use_case_description": "User clicks export button and gets a CSV file downloaded",
            "product_id": 99999,
        }, headers=auth_headers(voter_user))
        assert resp.status_code == 404

    def test_submit_validation_short_title(self, client, voter_user, test_product):
        resp = client.post("/submissions/submit", json={
            "original_freeform_text": "I want a feature to export data to CSV files for reporting",
            "title": "AB",
            "what_description": "Add ability to export data to CSV format",
            "why_description": "Users need to share data with external tools",
            "use_case_description": "User clicks export button and gets a CSV file downloaded",
            "product_id": test_product.id,
        }, headers=auth_headers(voter_user))
        assert resp.status_code == 422
