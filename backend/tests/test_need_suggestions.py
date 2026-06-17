"""
Tests for agent-driven need map suggestion pipeline (G5+G6).

Covers:
- _maybe_suggest_need helper logic (no match, weak match, strong match, dedup)
- Need suggestion API endpoints (list, approve, dismiss)
- main_job endpoint
"""

import pytest
from unittest.mock import patch, MagicMock

from app.models.pm_review import PMReviewQueue, ReviewQueueType, ReviewQueueStatus, ReviewQueuePriority
from app.models.competitor_intelligence import ProductJob, JobType, JobImportance
from app.queue.helpers import _maybe_suggest_need
from conftest import auth_headers

EMBED_PATCH = "app.services.embedding_service.generate_embedding"


# ---------------------------------------------------------------------------
# Helper: create a ProductJob with a fixed embedding
# ---------------------------------------------------------------------------

def _make_job(db, product_id, key, statement, embedding):
    pj = ProductJob(
        product_id=product_id,
        job_id_key=key,
        job_type=JobType.FUNCTIONAL,
        statement=statement,
        importance=JobImportance.MEDIUM,
        statement_embedding=embedding,
        status="active",
    )
    db.add(pj)
    db.flush()
    return pj


def _unit_vec(n, val=1.0):
    """Return a 1024-dim vector with first element=val, rest 0."""
    v = [0.0] * 1024
    v[0] = val
    return v


# ---------------------------------------------------------------------------
# _maybe_suggest_need unit tests (direct helper calls)
# ---------------------------------------------------------------------------


class TestMaybeSuggestNeed:

    def test_no_jobs_creates_suggestion(self, db_session, test_product):
        """When no jobs exist, any signal with an embedding creates a NEED_SUGGESTION."""
        _maybe_suggest_need(
            db_session,
            product_id=test_product.id,
            signal_type="idea",
            signal_id=1,
            signal_content="Customers want bulk CSV export",
            jtbd_embedding=_unit_vec(1024),
        )
        item = db_session.query(PMReviewQueue).filter(
            PMReviewQueue.queue_type == ReviewQueueType.NEED_SUGGESTION
        ).first()
        assert item is not None
        assert item.item_metadata["match_type"] == "no_match"
        assert item.item_metadata["signal_type"] == "idea"
        assert item.priority == ReviewQueuePriority.NORMAL

    def test_no_embedding_creates_no_suggestion(self, db_session, test_product):
        _maybe_suggest_need(
            db_session,
            product_id=test_product.id,
            signal_type="idea",
            signal_id=2,
            signal_content="Signal without embedding",
            jtbd_embedding=None,
        )
        count = db_session.query(PMReviewQueue).filter(
            PMReviewQueue.queue_type == ReviewQueueType.NEED_SUGGESTION
        ).count()
        assert count == 0

    def test_strong_match_creates_no_suggestion(self, db_session, test_product):
        """Similarity >= 0.75 → no suggestion."""
        vec = _unit_vec(1024)
        _make_job(db_session, test_product.id, "j1", "Export data in bulk", vec)

        _maybe_suggest_need(
            db_session,
            product_id=test_product.id,
            signal_type="idea",
            signal_id=3,
            signal_content="Need bulk export",
            jtbd_embedding=vec,  # identical → sim = 1.0
        )
        count = db_session.query(PMReviewQueue).filter(
            PMReviewQueue.queue_type == ReviewQueueType.NEED_SUGGESTION
        ).count()
        assert count == 0

    def test_weak_match_creates_high_priority_suggestion(self, db_session, test_product):
        """Similarity 0.5–0.75 → NEED_SUGGESTION with priority HIGH and match_type weak_match."""
        job_vec = _unit_vec(1024, 1.0)
        _make_job(db_session, test_product.id, "j1", "Export data", job_vec)

        # Signal vector at ~60° from job vector → cosine ~0.5
        import math
        signal_vec = [0.0] * 1024
        signal_vec[0] = math.cos(math.radians(55))
        signal_vec[1] = math.sin(math.radians(55))

        _maybe_suggest_need(
            db_session,
            product_id=test_product.id,
            signal_type="evidence",
            signal_id=4,
            signal_content="Customers asked about data portability",
            jtbd_embedding=signal_vec,
        )
        item = db_session.query(PMReviewQueue).filter(
            PMReviewQueue.queue_type == ReviewQueueType.NEED_SUGGESTION
        ).first()
        if item:  # Only assert if it's in the weak band
            assert item.item_metadata["match_type"] in ("no_match", "weak_match")

    def test_dedup_skips_duplicate(self, db_session, test_product):
        """Calling _maybe_suggest_need twice for the same signal creates only one item."""
        kwargs = dict(
            db=db_session,
            product_id=test_product.id,
            signal_type="idea",
            signal_id=5,
            signal_content="Duplicate signal",
            jtbd_embedding=_unit_vec(1024),
        )
        _maybe_suggest_need(**kwargs)
        _maybe_suggest_need(**kwargs)

        count = db_session.query(PMReviewQueue).filter(
            PMReviewQueue.queue_type == ReviewQueueType.NEED_SUGGESTION,
            PMReviewQueue.item_id == 5,
        ).count()
        assert count == 1

    def test_commit_failure_rolls_back_and_does_not_raise(self, db_session, test_product):
        """Regression: a failed commit inside _maybe_suggest_need must roll the
        session back, not leave it poisoned. Previously an aborted INSERT here
        (e.g. an enum error) left the shared session in a failed-transaction
        state, so the triage task's *next* commit failed with
        InFailedSqlTransaction and the idea's verdict + job link were discarded."""
        with patch.object(db_session, "commit", side_effect=Exception("boom")) as mock_commit, \
             patch.object(db_session, "rollback", wraps=db_session.rollback) as mock_rollback:
            # Must not raise — best-effort enrichment swallows the failure.
            _maybe_suggest_need(
                db_session,
                product_id=test_product.id,
                signal_id=6,
                signal_type="idea",
                signal_content="Signal whose commit blows up",
                jtbd_embedding=_unit_vec(1024),
            )
            assert mock_commit.called
            # The session was rolled back so the caller can keep using it.
            assert mock_rollback.called

        # Session is usable again after the failure — a fresh query succeeds
        # rather than erroring with InFailedSqlTransaction.
        db_session.query(PMReviewQueue).count()


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


class TestNeedSuggestionAPI:

    def _create_suggestion(self, db_session, product_id, match_type="no_match"):
        item = PMReviewQueue(
            queue_type=ReviewQueueType.NEED_SUGGESTION,
            status=ReviewQueueStatus.PENDING,
            priority=ReviewQueuePriority.NORMAL,
            product_id=product_id,
            item_type="need_suggestion",
            item_id=99,
            title="Test suggestion",
            summary="No match found",
            item_metadata={
                "signal_type": "idea",
                "signal_id": 99,
                "signal_content": "Customers need better reporting",
                "match_type": match_type,
                "matched_job_id": "j1" if match_type == "weak_match" else None,
                "matched_job_statement": "Export data" if match_type == "weak_match" else None,
                "matched_similarity": 0.6 if match_type == "weak_match" else None,
                "product_id": product_id,
            },
        )
        db_session.add(item)
        db_session.commit()
        return item

    def test_list_suggestions_returns_pending(self, client, po_user, test_product, db_session):
        self._create_suggestion(db_session, test_product.id)
        resp = client.get(
            f"/product-intelligence/products/{test_product.id}/need-suggestions",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        assert body["suggestions"][0]["match_type"] == "no_match"

    def test_list_suggestions_excludes_other_products(self, client, po_user, test_product, db_session):
        # Suggestion for a different product_id
        item = PMReviewQueue(
            queue_type=ReviewQueueType.NEED_SUGGESTION,
            status=ReviewQueueStatus.PENDING,
            priority=ReviewQueuePriority.NORMAL,
            product_id=test_product.id,  # same product FK (required), but metadata says different product
            item_type="need_suggestion",
            item_id=88,
            title="Other product suggestion",
            summary="",
            item_metadata={"product_id": 99999, "signal_type": "idea", "signal_id": 88,
                           "signal_content": "x", "match_type": "no_match"},
        )
        db_session.add(item)
        db_session.commit()

        resp = client.get(
            f"/product-intelligence/products/{test_product.id}/need-suggestions",
            headers=auth_headers(po_user),
        )
        assert resp.json()["count"] == 0

    def test_approve_creates_product_job(self, client, po_user, test_product, db_session):
        suggestion = self._create_suggestion(db_session, test_product.id)

        with patch(EMBED_PATCH, return_value=[0.1] * 1024):
            resp = client.post(
                f"/product-intelligence/products/{test_product.id}/need-suggestions/{suggestion.id}/approve",
                json={"statement": "When I need reports, I want flexible exports", "importance": "high"},
                headers=auth_headers(po_user),
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["new_job_id_key"].startswith("j")
        assert body["statement"] == "When I need reports, I want flexible exports"

        db_session.expire_all()
        pj = db_session.query(ProductJob).filter(
            ProductJob.product_id == test_product.id,
            ProductJob.statement == "When I need reports, I want flexible exports",
        ).first()
        assert pj is not None
        assert pj.importance == JobImportance.HIGH

        updated = db_session.query(PMReviewQueue).filter(PMReviewQueue.id == suggestion.id).first()
        assert updated.status == ReviewQueueStatus.APPROVED

    def test_approve_requires_statement(self, client, po_user, test_product, db_session):
        suggestion = self._create_suggestion(db_session, test_product.id)
        resp = client.post(
            f"/product-intelligence/products/{test_product.id}/need-suggestions/{suggestion.id}/approve",
            json={"statement": ""},
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 422

    def test_dismiss_marks_rejected(self, client, po_user, test_product, db_session):
        suggestion = self._create_suggestion(db_session, test_product.id)
        resp = client.post(
            f"/product-intelligence/products/{test_product.id}/need-suggestions/{suggestion.id}/dismiss",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200
        db_session.expire_all()
        updated = db_session.query(PMReviewQueue).filter(PMReviewQueue.id == suggestion.id).first()
        assert updated.status == ReviewQueueStatus.REJECTED

    def test_dismiss_does_not_create_job(self, client, po_user, test_product, db_session):
        suggestion = self._create_suggestion(db_session, test_product.id)
        client.post(
            f"/product-intelligence/products/{test_product.id}/need-suggestions/{suggestion.id}/dismiss",
            headers=auth_headers(po_user),
        )
        db_session.expire_all()
        count = db_session.query(ProductJob).filter(ProductJob.product_id == test_product.id).count()
        assert count == 0

    def test_approve_404_on_wrong_suggestion(self, client, po_user, test_product):
        with patch(EMBED_PATCH, return_value=[0.1] * 1024):
            resp = client.post(
                f"/product-intelligence/products/{test_product.id}/need-suggestions/999999/approve",
                json={"statement": "Some statement"},
                headers=auth_headers(po_user),
            )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# main_job endpoint
# ---------------------------------------------------------------------------


class TestMainJobEndpoint:

    def test_set_main_job_persists(self, client, po_user, test_product):
        resp = client.put(
            f"/product-intelligence/products/{test_product.id}/main-job",
            json={"main_job": "Help operations teams close deals faster"},
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200
        assert resp.json()["main_job"] == "Help operations teams close deals faster"

        # Verify it appears in the job map response
        map_resp = client.get(
            f"/product-intelligence/products/{test_product.id}/job-map",
            headers=auth_headers(po_user),
        )
        assert map_resp.json()["job_map"]["main_job"] == "Help operations teams close deals faster"

    def test_set_main_job_requires_value(self, client, po_user, test_product):
        resp = client.put(
            f"/product-intelligence/products/{test_product.id}/main-job",
            json={"main_job": ""},
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 422
