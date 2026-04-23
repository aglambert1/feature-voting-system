"""
Tests for the latest-unified-report endpoint's structured opportunities payload.

Covers:
- opportunities_detail returned when report + rows exist
- linked_idea_id and linked_idea_title populated from the Idea table
- ordering by priority_score descending
- empty list when a report exists but has no opportunity rows
"""

from app.models.idea import Idea, IdeaStatus, SourceType
from app.models.synthesis import (
    SynthesisReport,
    SynthesisRun,
    SynthesizedOpportunity,
)
from conftest import auth_headers


def _make_report(db_session, product_id: int) -> SynthesisReport:
    report = SynthesisReport(
        product_id=product_id,
        report_version=1,
        included_source_types=["competitive"],
        report_content_md="# Test report",
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)
    return report


def _make_run(db_session, product_id: int) -> SynthesisRun:
    run = SynthesisRun(
        product_id=product_id,
        status="completed",
        sources_used=["competitive"],
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)
    return run


class TestOpportunitiesDetail:

    def test_returns_empty_list_when_no_opportunities(
        self, client, po_user, test_product, db_session
    ):
        _make_report(db_session, test_product.id)
        resp = client.get(
            f"/products/{test_product.id}/synthesis/latest",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["exists"] is True
        assert body["opportunities_detail"] == []

    def test_returns_rows_sorted_by_priority_descending(
        self, client, po_user, test_product, db_session
    ):
        report = _make_report(db_session, test_product.id)
        run = _make_run(db_session, test_product.id)
        for name, score in [("Low", 40.0), ("High", 90.0), ("Mid", 70.0)]:
            db_session.add(SynthesizedOpportunity(
                synthesis_run_id=run.id,
                synthesis_report_id=report.id,
                product_id=test_product.id,
                opportunity_name=name,
                priority_score=score,
                source_count=1,
            ))
        db_session.commit()

        resp = client.get(
            f"/products/{test_product.id}/synthesis/latest",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200
        detail = resp.json()["opportunities_detail"]
        assert [d["opportunity_name"] for d in detail] == ["High", "Mid", "Low"]

    def test_populates_linked_idea_title_when_backfilled(
        self, client, po_user, test_product, db_session
    ):
        report = _make_report(db_session, test_product.id)
        run = _make_run(db_session, test_product.id)

        idea = Idea(
            title="Add time tracking",
            what_description="Time tracking capability",
            why_description="Table stakes",
            use_case_description="Synthesized",
            product_id=test_product.id,
            source_type=SourceType.COMPETITOR_AUTOMATED,
            status=IdeaStatus.PENDING,
            is_active=False,
            auto_categorized=False,
        )
        db_session.add(idea)
        db_session.flush()

        linked_opp = SynthesizedOpportunity(
            synthesis_run_id=run.id,
            synthesis_report_id=report.id,
            product_id=test_product.id,
            opportunity_name="Add time tracking",
            priority_score=85.0,
            source_count=1,
            linked_idea_id=idea.id,
        )
        unlinked_opp = SynthesizedOpportunity(
            synthesis_run_id=run.id,
            synthesis_report_id=report.id,
            product_id=test_product.id,
            opportunity_name="Something else",
            priority_score=60.0,
            source_count=1,
        )
        db_session.add_all([linked_opp, unlinked_opp])
        db_session.commit()

        resp = client.get(
            f"/products/{test_product.id}/synthesis/latest",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200
        detail = resp.json()["opportunities_detail"]

        linked = next(d for d in detail if d["opportunity_name"] == "Add time tracking")
        assert linked["linked_idea_id"] == idea.id
        assert linked["linked_idea_title"] == "Add time tracking"

        unlinked = next(d for d in detail if d["opportunity_name"] == "Something else")
        assert unlinked["linked_idea_id"] is None
        assert unlinked["linked_idea_title"] is None
