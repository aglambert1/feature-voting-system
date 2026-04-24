"""Tests for POST /products/{pid}/synthesis/opportunities/{oid}/create-idea.

Manual path that mirrors the auto-idea-generation loop but with user-edited
fields and no priority threshold check.
"""

from unittest.mock import MagicMock, patch

from app.models.idea import Idea, IdeaStatus, SourceType
from app.models.synthesis import (
    SynthesisReport,
    SynthesisRun,
    SynthesizedOpportunity,
)
from conftest import auth_headers


def _make_opp(db_session, product_id: int, **overrides) -> SynthesizedOpportunity:
    report = SynthesisReport(
        product_id=product_id,
        report_version=1,
        included_source_types=["competitive"],
    )
    run = SynthesisRun(product_id=product_id, status="completed")
    db_session.add(report)
    db_session.add(run)
    db_session.flush()

    opp = SynthesizedOpportunity(
        synthesis_run_id=run.id,
        synthesis_report_id=report.id,
        product_id=product_id,
        opportunity_name=overrides.get("opportunity_name", "Test Opportunity"),
        opportunity_summary="summary",
        priority_score=overrides.get("priority_score", 42.0),
        source_count=1,
        sources=["source A"],
        recommended_action="do the thing",
        investment_tier="now",
    )
    db_session.add(opp)
    db_session.commit()
    db_session.refresh(opp)
    return opp


class TestCreateIdeaFromOpportunity:

    def test_creates_idea_links_opp_and_dispatches_triage(
        self, client, po_user, test_product, db_session
    ):
        opp = _make_opp(db_session, test_product.id)

        payload = {
            "title": "Edited Title",
            "what_description": "Edited what",
            "why_description": "Edited why",
            "use_case_description": "Edited use case",
        }

        with patch(
            "app.api.unified_synthesis.send_task",
            return_value=MagicMock(id="celery-id-1"),
        ) as mock_send:
            resp = client.post(
                f"/products/{test_product.id}/synthesis/opportunities/{opp.id}/create-idea",
                json=payload,
                headers=auth_headers(po_user),
            )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["idea_id"]
        assert body["triage_job_id"]

        mock_send.assert_called_once()
        assert mock_send.call_args.args[0] == "triage_idea_task"

        idea = db_session.query(Idea).filter(Idea.id == body["idea_id"]).first()
        assert idea is not None
        assert idea.title == "Edited Title"
        assert idea.what_description == "Edited what"
        assert idea.why_description == "Edited why"
        assert idea.source_type == SourceType.COMPETITOR_AUTOMATED
        assert idea.status == IdeaStatus.PENDING
        assert idea.submitter_id == po_user.id
        assert idea.source_metadata["opportunity_id"] == opp.id
        assert idea.source_metadata["manual_creation"] is True

        db_session.refresh(opp)
        assert opp.linked_idea_id == idea.id

    def test_conflicts_when_opp_already_linked(
        self, client, po_user, test_product, db_session
    ):
        opp = _make_opp(db_session, test_product.id)
        existing = Idea(
            title="Existing",
            what_description="w",
            why_description="y",
            use_case_description="u",
            product_id=test_product.id,
            source_type=SourceType.COMPETITOR_AUTOMATED,
            status=IdeaStatus.PENDING,
            is_active=False,
            auto_categorized=False,
        )
        db_session.add(existing)
        db_session.flush()
        opp.linked_idea_id = existing.id
        db_session.commit()

        resp = client.post(
            f"/products/{test_product.id}/synthesis/opportunities/{opp.id}/create-idea",
            json={"title": "X", "what_description": "Y"},
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 409

    def test_404_when_opportunity_missing(
        self, client, po_user, test_product
    ):
        resp = client.post(
            f"/products/{test_product.id}/synthesis/opportunities/99999/create-idea",
            json={"title": "X", "what_description": "Y"},
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 404

    def test_forbidden_for_viewer(
        self, client, voter_user, voter_product_access, test_product, db_session
    ):
        opp = _make_opp(db_session, test_product.id)
        resp = client.post(
            f"/products/{test_product.id}/synthesis/opportunities/{opp.id}/create-idea",
            json={"title": "X", "what_description": "Y"},
            headers=auth_headers(voter_user),
        )
        assert resp.status_code == 403
