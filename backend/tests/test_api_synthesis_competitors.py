"""
Tests for the synthesis competitor endpoints on unified_synthesis.py:
- GET  /products/{id}/synthesis/competitors    (list with tracked + has_report)
- PATCH /products/{id}/competitors/{cid}/tracked  (set tracked flag)
- POST /products/{id}/synthesis/run            (dispatches Celery task)
"""

from unittest.mock import patch, MagicMock

import pytest

from app.models.competitor_intelligence import ProductCompetitor
from app.models.competitive_reports import CompetitorFunctionalReport
from conftest import auth_headers


@pytest.fixture
def test_competitor(db_session, test_product):
    """A single active untracked competitor on test_product."""
    competitor = ProductCompetitor(
        product_id=test_product.id,
        competitor_name="Acme Rivals",
        competitor_url="https://acme.example.com",
        status="active",
        tracked=False,
    )
    db_session.add(competitor)
    db_session.commit()
    db_session.refresh(competitor)
    return competitor


# --- GET synthesis/competitors ------------------------------------------------


class TestGetSynthesisCompetitors:

    def test_list_returns_tracked_and_has_report(
        self, client, po_user, test_product, test_competitor
    ):
        resp = client.get(
            f"/products/{test_product.id}/synthesis/competitors",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["product_id"] == test_product.id
        assert len(body["competitors"]) == 1
        entry = body["competitors"][0]
        assert entry["competitor_id"] == test_competitor.id
        assert entry["tracked"] is False
        assert entry["has_report"] is False

    def test_list_returns_has_report_true_when_report_exists(
        self, client, po_user, test_product, test_competitor, db_session
    ):
        report = CompetitorFunctionalReport(
            product_competitor_id=test_competitor.id,
            product_id=test_product.id,
            report_version=1,
        )
        db_session.add(report)
        db_session.commit()

        resp = client.get(
            f"/products/{test_product.id}/synthesis/competitors",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200
        entry = resp.json()["competitors"][0]
        assert entry["has_report"] is True


# --- PATCH tracked ------------------------------------------------------------


class TestPatchTracked:

    def test_sets_tracked_true(
        self, client, po_user, test_product, test_competitor, db_session
    ):
        url = (
            f"/product-intelligence/agents/{test_product.id}/competitors/"
            f"{test_competitor.id}/tracked"
        )
        resp = client.patch(url, json={"tracked": True}, headers=auth_headers(po_user))
        assert resp.status_code == 200
        assert resp.json()["tracked"] is True

        db_session.expire_all()
        refreshed = db_session.query(ProductCompetitor).get(test_competitor.id)
        assert refreshed.tracked is True

    def test_sets_tracked_false(
        self, client, po_user, test_product, test_competitor, db_session
    ):
        # First track it
        test_competitor.tracked = True
        db_session.commit()

        url = (
            f"/product-intelligence/agents/{test_product.id}/competitors/"
            f"{test_competitor.id}/tracked"
        )
        resp = client.patch(url, json={"tracked": False}, headers=auth_headers(po_user))
        assert resp.status_code == 200
        assert resp.json()["tracked"] is False

        db_session.expire_all()
        refreshed = db_session.query(ProductCompetitor).get(test_competitor.id)
        assert refreshed.tracked is False

    def test_tracked_competitor_appears_in_synthesis_query(
        self, client, po_user, test_product, test_competitor, db_session
    ):
        # Track it
        url = (
            f"/product-intelligence/agents/{test_product.id}/competitors/"
            f"{test_competitor.id}/tracked"
        )
        client.patch(url, json={"tracked": True}, headers=auth_headers(po_user))

        # Verify it shows as tracked in the synthesis competitors list
        resp = client.get(
            f"/products/{test_product.id}/synthesis/competitors",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200
        entry = resp.json()["competitors"][0]
        assert entry["tracked"] is True

    def test_untracked_competitor_not_in_synthesis_query(
        self, client, po_user, test_product, test_competitor, db_session
    ):
        # Untrack it explicitly
        url = (
            f"/product-intelligence/agents/{test_product.id}/competitors/"
            f"{test_competitor.id}/tracked"
        )
        client.patch(url, json={"tracked": False}, headers=auth_headers(po_user))

        resp = client.get(
            f"/products/{test_product.id}/synthesis/competitors",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200
        entry = resp.json()["competitors"][0]
        assert entry["tracked"] is False

    def test_forbidden_for_viewer(
        self,
        client,
        voter_user,
        voter_product_access,
        test_product,
        test_competitor,
    ):
        url = (
            f"/product-intelligence/agents/{test_product.id}/competitors/"
            f"{test_competitor.id}/tracked"
        )
        resp = client.patch(url, json={"tracked": True}, headers=auth_headers(voter_user))
        assert resp.status_code == 403


# --- POST /synthesis/run -----------------------------------------------------


class TestRunUnifiedSynthesis:
    """Regression guard for a prior bug: the endpoint passed the full
    ``app.queue.tasks.unified_synthesis_task`` name to ``send_celery_task``,
    which also prepends that prefix, producing a double-prefixed name Celery
    couldn't resolve. Messages were silently discarded. The guard in
    ``send_celery_task`` now raises on prefixed input, but we also pin the
    exact short name here so a future refactor can't drift."""

    def test_run_dispatches_short_task_name(
        self, client, po_user, test_product
    ):
        with patch(
            "app.api.unified_synthesis.send_task", return_value=MagicMock(id="celery-id-1")
        ) as mock_send:
            resp = client.post(
                f"/products/{test_product.id}/synthesis/run",
                headers=auth_headers(po_user),
            )
        assert resp.status_code == 201
        mock_send.assert_called_once()
        task_name = mock_send.call_args.args[0]
        assert task_name == "unified_synthesis_task", (
            f"expected short name 'unified_synthesis_task' "
            f"(send_celery_task prepends the module prefix); got {task_name!r}"
        )

    def test_run_forbidden_for_viewer(
        self, client, voter_user, voter_product_access, test_product
    ):
        resp = client.post(
            f"/products/{test_product.id}/synthesis/run",
            headers=auth_headers(voter_user),
        )
        assert resp.status_code == 403


class TestSendCeleryTaskGuard:
    """Unit-level guard: passing an already-prefixed task name must raise.

    This is the class-wide defense: even if someone adds a new endpoint and
    makes the same mistake, they'll see a ValueError at dispatch instead of
    messages silently dropping on the worker floor."""

    def test_raises_on_prefixed_name(self):
        from app.utils.celery_utils import send_celery_task

        with pytest.raises(ValueError, match="must not include"):
            send_celery_task("app.queue.tasks.unified_synthesis_task", 1)

    def test_accepts_short_name(self):
        # Don't actually hit a broker — patch the underlying send_task.
        from app.utils import celery_utils

        with patch.object(
            celery_utils.celery_app, "send_task", return_value=MagicMock(id="x")
        ) as mock_send:
            celery_utils.send_celery_task("unified_synthesis_task", 7)

        mock_send.assert_called_once()
        assert (
            mock_send.call_args.args[0]
            == "app.queue.synthesis_tasks.unified_synthesis_task"
        )
