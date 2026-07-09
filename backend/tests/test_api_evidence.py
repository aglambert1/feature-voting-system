"""API tests for the evidence router.

Regression focus: creating evidence with a new competitor_name auto-creates a
ProductCompetitor. This path used to pass the dropped `deep_analysis_enabled`
column and 500'd (fixed to `tracked=True`).
"""

import pytest

from app.models.competitor_intelligence import ProductCompetitor
from tests.conftest import auth_headers


@pytest.fixture(autouse=True)
def _no_external_calls(monkeypatch):
    """Evidence creation tries embeddings + JTBD extraction; keep tests offline."""
    monkeypatch.setattr(
        "app.services.embedding_service.generate_embedding",
        lambda *a, **k: [0.0] * 1024,
    )
    monkeypatch.setattr(
        "app.services.evidence_service.extract_jtbd",
        lambda *a, **k: None,
    )


class TestCreateEvidence:
    def test_create_with_new_competitor_name_creates_tracked_competitor(
        self, client, db_session, test_product, po_user
    ):
        """Regression: auto-created competitor must use `tracked`, not the
        dropped `deep_analysis_enabled` column (which raised TypeError)."""
        response = client.post(
            f"/product-intelligence/products/{test_product.id}/evidence",
            json={
                "evidence_type": "customer_interview",
                "title": "Customer asked about Acme",
                "content": "Prospect said Acme has a better export feature.",
                "competitor_name": "Acme Corp",
            },
            headers=auth_headers(po_user),
        )
        assert response.status_code == 200, response.text

        competitor = db_session.query(ProductCompetitor).filter(
            ProductCompetitor.product_id == test_product.id,
            ProductCompetitor.competitor_name == "Acme Corp",
        ).first()
        assert competitor is not None
        assert competitor.tracked is True
        assert response.json()["competitor_id"] == competitor.id

    def test_create_plain_evidence(self, client, test_product, po_user):
        response = client.post(
            f"/product-intelligence/products/{test_product.id}/evidence",
            json={
                "evidence_type": "customer_interview",
                "title": "Feature request",
                "content": "Customer wants CSV export.",
            },
            headers=auth_headers(po_user),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["title"] == "Feature request"
        assert body["competitor_id"] is None

    def test_create_requires_edit_permission(
        self, client, test_product, voter_user, voter_product_access
    ):
        """VIEW-only users cannot create evidence."""
        response = client.post(
            f"/product-intelligence/products/{test_product.id}/evidence",
            json={
                "evidence_type": "customer_interview",
                "title": "Nope",
                "content": "Should be forbidden.",
            },
            headers=auth_headers(voter_user),
        )
        assert response.status_code == 403
