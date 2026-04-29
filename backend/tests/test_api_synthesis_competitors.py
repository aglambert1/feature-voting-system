"""
Tests for the synthesis competitor endpoints on unified_synthesis.py:
- GET  /products/{id}/synthesis/competitors    (list with has_report)
- PATCH /products/{id}/synthesis/competitors/{cid}/synthesis-inclusion
- POST /products/{id}/synthesis/run            (dispatches Celery task)
"""

from unittest.mock import patch, MagicMock

import pytest

from app.models.competitor_intelligence import ProductCompetitor
from app.models.competitive_reports import CompetitorFunctionalReport
from conftest import auth_headers


@pytest.fixture
def test_competitor(db_session, test_product):
    """A single active competitor on test_product with synthesis_included=False."""
    competitor = ProductCompetitor(
        product_id=test_product.id,
        competitor_name="Acme Rivals",
        competitor_url="https://acme.example.com",
        status="active",
        audit_enabled=False,
        synthesis_included=False,
    )
    db_session.add(competitor)
    db_session.commit()
    db_session.refresh(competitor)
    return competitor


# --- GET list ----------------------------------------------------------------


class TestGetSynthesisCompetitors:

    def test_list_returns_has_report_false_when_no_report(
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
        assert entry["synthesis_included"] is False
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


# --- PATCH synthesis-inclusion -----------------------------------------------


class TestPatchSynthesisInclusion:

    def test_toggles_flag_on_and_off(
        self, client, po_user, test_product, test_competitor, db_session
    ):
        url = (
            f"/products/{test_product.id}/synthesis/competitors/"
            f"{test_competitor.id}/synthesis-inclusion"
        )

        on = client.patch(url, json={"included": True}, headers=auth_headers(po_user))
        assert on.status_code == 200
        assert on.json()["synthesis_included"] is True

        db_session.expire_all()
        refreshed = db_session.query(ProductCompetitor).get(test_competitor.id)
        assert refreshed.synthesis_included is True

        off = client.patch(url, json={"included": False}, headers=auth_headers(po_user))
        assert off.status_code == 200
        assert off.json()["synthesis_included"] is False

    def test_does_not_touch_audit_enabled(
        self, client, po_user, test_product, test_competitor, db_session
    ):
        url = (
            f"/products/{test_product.id}/synthesis/competitors/"
            f"{test_competitor.id}/synthesis-inclusion"
        )
        resp = client.patch(url, json={"included": True}, headers=auth_headers(po_user))
        assert resp.status_code == 200

        db_session.expire_all()
        refreshed = db_session.query(ProductCompetitor).get(test_competitor.id)
        assert refreshed.audit_enabled is False  # still False

    def test_forbidden_for_viewer(
        self,
        client,
        voter_user,
        voter_product_access,
        test_product,
        test_competitor,
    ):
        url = (
            f"/products/{test_product.id}/synthesis/competitors/"
            f"{test_competitor.id}/synthesis-inclusion"
        )
        resp = client.patch(url, json={"included": True}, headers=auth_headers(voter_user))
        assert resp.status_code == 403

    def test_unknown_competitor_returns_404(
        self, client, po_user, test_product
    ):
        url = (
            f"/products/{test_product.id}/synthesis/competitors/"
            f"999999/synthesis-inclusion"
        )
        resp = client.patch(url, json={"included": True}, headers=auth_headers(po_user))
        assert resp.status_code == 404

    def test_competitor_from_other_product_returns_404(
        self, client, po_user, test_product, second_product, db_session
    ):
        # Create a competitor on the SECOND product, then try to patch it
        # via the first product's URL — should 404, not leak.
        other = ProductCompetitor(
            product_id=second_product.id,
            competitor_name="Other Co",
            status="active",
            audit_enabled=False,
            synthesis_included=False,
        )
        db_session.add(other)
        db_session.commit()
        db_session.refresh(other)

        url = (
            f"/products/{test_product.id}/synthesis/competitors/"
            f"{other.id}/synthesis-inclusion"
        )
        resp = client.patch(url, json={"included": True}, headers=auth_headers(po_user))
        assert resp.status_code == 404


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
