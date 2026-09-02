"""
Tests for the job coverage view and self-assessment endpoints.

Coverage is a plain join over the self-assessment and whatever audits have run — no LLM,
and deliberately not gated behind synthesis, which answers a different question. A PM who
has audited three competitors can compare them immediately.
"""

import pytest

from conftest import auth_headers

from app.models.competitive_reports import (
    CompetitorFunctionalReport,
    ProductSelfAssessment,
)
from app.models.competitor_intelligence import (
    JobImportance,
    JobType,
    ProductCompetitor,
    ProductJob,
)


def _job(db_session, product, key, importance=JobImportance.HIGH, **kwargs):
    job = ProductJob(
        product_id=product.id,
        job_id_key=key,
        job_type=JobType.FUNCTIONAL,
        statement=f"Statement for {key}",
        importance=importance,
        **kwargs,
    )
    db_session.add(job)
    db_session.commit()
    return job


def _competitor(db_session, product, name, tracked=True):
    comp = ProductCompetitor(
        product_id=product.id,
        competitor_name=name,
        tracked=tracked,
        status="active",
    )
    db_session.add(comp)
    db_session.commit()
    return comp


def _report(db_session, product, competitor, assessments):
    report = CompetitorFunctionalReport(
        product_competitor_id=competitor.id,
        product_id=product.id,
        report_version=1,
        job_assessments=assessments,
    )
    db_session.add(report)
    db_session.commit()
    return report


def _evidence_for_job(db_session, product, job_id_key):
    from app.models.evidence import Evidence, EvidenceType

    ev = Evidence(
        product_id=product.id,
        evidence_type=EvidenceType.CUSTOMER_INTERVIEW,
        title="A customer described this struggle",
        content="...",
        job_id_key=job_id_key,
    )
    db_session.add(ev)
    db_session.commit()
    return ev


def _self_assessment(db_session, product, entries, version=1, evidence_based=True):
    assessment = ProductSelfAssessment(
        product_id=product.id,
        assessment_version=version,
        job_assessments=entries,
        evidence_based=evidence_based,
    )
    db_session.add(assessment)
    db_session.commit()
    return assessment


class TestSelfAssessmentEndpoint:
    def test_requires_a_job_map(self, client, test_product, po_user):
        # Assessing against an empty map would produce nothing, so fail with a reason
        # rather than queueing work that cannot succeed.
        resp = client.post(
            f"/product-intelligence/products/{test_product.id}/self-assessment",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 400
        assert "job map" in resp.json()["detail"].lower()

    def test_queues_the_task_when_a_job_map_exists(
        self, db_session, client, test_product, po_user, monkeypatch
    ):
        # The success path was previously untested, which let a missing entry in
        # _TASK_NAME_MAP ship: create_job commits, then send_task raises, leaving a 500
        # and an orphaned PENDING job. Since self-assessment is the only source of
        # our_score, every competitor position would have stayed unknown forever.
        sent = {}

        def fake_send(task_name, *args, **kwargs):
            sent["task_name"] = task_name
            return type("R", (), {"id": "task-1"})()

        monkeypatch.setattr("app.api.job_coverage.send_task", fake_send)
        _job(db_session, test_product, "j1")

        resp = client.post(
            f"/product-intelligence/products/{test_product.id}/self-assessment",
            headers=auth_headers(po_user),
        )

        assert resp.status_code == 200
        assert resp.json()["job_id"]
        assert sent["task_name"] == "self_assessment_task"

    def test_the_queued_task_name_is_resolvable(self):
        # send_task resolves short names through a map; an unregistered name raises at
        # call time rather than import time, so nothing catches it until a PM clicks.
        from app.utils.celery_utils import _TASK_NAME_MAP

        assert "self_assessment_task" in _TASK_NAME_MAP

    def test_returns_null_when_none_has_run(self, client, test_product, po_user):
        resp = client.get(
            f"/product-intelligence/products/{test_product.id}/self-assessment",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["assessment"] is None
        # The message has to explain the consequence, not just the absence.
        assert "positions cannot be derived" in body["message"]

    def test_returns_the_latest_version(self, db_session, client, test_product, po_user):
        _self_assessment(db_session, test_product, [{"job_id": "j1", "score": 4}], version=1)
        _self_assessment(db_session, test_product, [{"job_id": "j1", "score": 7}], version=2)

        resp = client.get(
            f"/product-intelligence/products/{test_product.id}/self-assessment",
            headers=auth_headers(po_user),
        )

        assert resp.json()["assessment"]["assessment_version"] == 2


class TestJobCoverage:
    def test_joins_our_score_with_each_competitor(
        self, db_session, client, test_product, po_user
    ):
        _job(db_session, test_product, "j1")
        comp = _competitor(db_session, test_product, "Productboard")
        _report(db_session, test_product, comp, [{
            "job_id": "j1",
            "competitor_score": 8,
            "system_position": "gap",
            "confidence": "high",
        }])
        _self_assessment(db_session, test_product, [{"job_id": "j1", "score": 4, "confidence": "medium"}])

        resp = client.get(
            f"/product-intelligence/products/{test_product.id}/job-coverage",
            headers=auth_headers(po_user),
        )

        assert resp.status_code == 200
        body = resp.json()
        row = body["jobs"][0]
        assert row["our_score"] == 4
        assert row["competitors"][0]["competitor_score"] == 8
        assert row["competitors"][0]["system_position"] == "gap"

    def test_untracked_competitors_are_excluded(
        self, db_session, client, test_product, po_user
    ):
        _job(db_session, test_product, "j1")
        _competitor(db_session, test_product, "Tracked", tracked=True)
        _competitor(db_session, test_product, "Untracked", tracked=False)

        resp = client.get(
            f"/product-intelligence/products/{test_product.id}/job-coverage",
            headers=auth_headers(po_user),
        )

        names = [c["competitor_name"] for c in resp.json()["competitors"]]
        assert names == ["Tracked"]

    def test_unaudited_competitors_appear_with_an_empty_column(
        self, db_session, client, test_product, po_user
    ):
        # An empty column prompts an audit; a missing column looks like a competitor
        # that does not exist, which silently narrows the comparison.
        _job(db_session, test_product, "j1")
        _competitor(db_session, test_product, "Never audited")

        resp = client.get(
            f"/product-intelligence/products/{test_product.id}/job-coverage",
            headers=auth_headers(po_user),
        )

        body = resp.json()
        assert body["competitors"][0]["audited"] is False
        assert body["jobs"][0]["competitors"][0]["assessed"] is False

    def test_works_without_a_self_assessment(
        self, db_session, client, test_product, po_user
    ):
        # The competitor side is still reportable; only our column is missing.
        _job(db_session, test_product, "j1")
        comp = _competitor(db_session, test_product, "Productboard")
        _report(db_session, test_product, comp, [{"job_id": "j1", "competitor_score": 8}])

        resp = client.get(
            f"/product-intelligence/products/{test_product.id}/job-coverage",
            headers=auth_headers(po_user),
        )

        body = resp.json()
        assert body["self_assessment"]["exists"] is False
        assert body["jobs"][0]["our_score"] is None
        assert body["jobs"][0]["competitors"][0]["competitor_score"] == 8

    def test_reports_whether_our_scores_rest_on_evidence(
        self, db_session, client, test_product, po_user
    ):
        # Without independent evidence the job map and the assessment both trace to the
        # product's own description, so the whole "us" column is self-referential.
        _job(db_session, test_product, "j1")
        _self_assessment(
            db_session, test_product, [{"job_id": "j1", "score": 9}], evidence_based=False
        )

        resp = client.get(
            f"/product-intelligence/products/{test_product.id}/job-coverage",
            headers=auth_headers(po_user),
        )

        assert resp.json()["self_assessment"]["evidence_based"] is False

    def test_human_override_is_carried_through(
        self, db_session, client, test_product, po_user
    ):
        _job(db_session, test_product, "j1")
        comp = _competitor(db_session, test_product, "Productboard")
        _report(db_session, test_product, comp, [{
            "job_id": "j1",
            "competitor_score": 8,
            "system_position": "gap",
            "human_position": "parity",
            "review_stale": False,
        }])

        resp = client.get(
            f"/product-intelligence/products/{test_product.id}/job-coverage",
            headers=auth_headers(po_user),
        )

        cell = resp.json()["jobs"][0]["competitors"][0]
        # Both are returned: the human verdict is authoritative for display, and the
        # system verdict is kept rather than replaced.
        assert cell["human_position"] == "parity"
        assert cell["system_position"] == "gap"

    def test_job_metadata_travels_with_the_row(
        self, db_session, client, test_product, po_user
    ):
        # Importance and serve_intent govern how a low score should be read: a job we
        # deliberately do not serve is not a failing.
        _job(
            db_session, test_product, "j1",
            importance=JobImportance.CRITICAL,
            serve_intent="out_of_target",
        )

        resp = client.get(
            f"/product-intelligence/products/{test_product.id}/job-coverage",
            headers=auth_headers(po_user),
        )

        row = resp.json()["jobs"][0]
        assert row["importance"] == "critical"
        assert row["serve_intent"] == "out_of_target"


class TestPositionRefreshOnSelfAssessment:
    def test_refresh_rederives_stored_positions(self, db_session, test_product):
        # Position is a join, so a new assessment invalidates every stored position.
        # Without this they would stay stale until each competitor was re-audited.
        from app.queue.jtbd_tasks import _refresh_competitor_positions

        comp = _competitor(db_session, test_product, "Productboard")
        _report(db_session, test_product, comp, [{
            "job_id": "j1",
            "competitor_score": 8,
            "our_score": None,
            "system_position": "unknown",
        }])
        assessment = _self_assessment(db_session, test_product, [{"job_id": "j1", "score": 4}], version=3)

        count = _refresh_competitor_positions(db_session, test_product.id, assessment)
        db_session.commit()

        report = db_session.query(CompetitorFunctionalReport).filter(
            CompetitorFunctionalReport.product_id == test_product.id
        ).first()
        assert count == 1
        assert report.job_assessments[0]["system_position"] == "gap"
        assert report.job_assessments[0]["our_score"] == 4
        assert report.job_assessments[0]["self_assessment_version"] == 3

    def test_refresh_preserves_human_overrides(self, db_session, test_product):
        # A refresh must never discard a PM's judgement — it regenerates the system
        # verdict alongside theirs, not on top of it.
        from app.queue.jtbd_tasks import _refresh_competitor_positions

        comp = _competitor(db_session, test_product, "Productboard")
        _report(db_session, test_product, comp, [{
            "job_id": "j1",
            "job_statement": "Statement for j1",
            "competitor_score": 8,
            "system_position": "unknown",
            "human_position": "advantage",
            "reviewed_by": 7,
            "reviewed_job_statement": "Statement for j1",
        }])
        assessment = _self_assessment(db_session, test_product, [{"job_id": "j1", "score": 4}])

        _refresh_competitor_positions(db_session, test_product.id, assessment)
        db_session.commit()

        report = db_session.query(CompetitorFunctionalReport).filter(
            CompetitorFunctionalReport.product_id == test_product.id
        ).first()
        entry = report.job_assessments[0]
        assert entry["human_position"] == "advantage"
        assert entry["reviewed_by"] == 7
        assert entry["system_position"] == "gap"


class TestAuditWarnsWhenSelfAssessmentIsMissing:
    """An audit takes minutes. A caller that only learns the result is degraded from the
    finished report has already paid for it, so the warning has to come at trigger time."""

    def _trigger(self, client, product, competitor, user):
        return client.post(
            f"/product-intelligence/agents/{product.id}/competitors/{competitor.id}/functional-audit",
            headers=auth_headers(user),
        )

    def test_warns_when_no_self_assessment_exists(
        self, db_session, client, test_product, po_user, monkeypatch
    ):
        monkeypatch.setattr(
            "app.api.competitive_agents.send_task", lambda *a, **k: type("R", (), {"id": "x"})()
        )
        comp = _competitor(db_session, test_product, "Productboard")

        resp = self._trigger(client, test_product, comp, po_user)

        assert resp.status_code == 200
        warnings = resp.json()["warnings"]
        assert len(warnings) == 1
        assert "unknown" in warnings[0]
        # The warning must say what to do, and that the audit need not be repeated —
        # otherwise the obvious reading is "cancel and start over".
        assert "does not need to be re-run" in warnings[0]

    def test_no_warning_once_a_self_assessment_exists(
        self, db_session, client, test_product, po_user, monkeypatch
    ):
        monkeypatch.setattr(
            "app.api.competitive_agents.send_task", lambda *a, **k: type("R", (), {"id": "x"})()
        )
        comp = _competitor(db_session, test_product, "Productboard")
        _self_assessment(db_session, test_product, [{"job_id": "j1", "score": 5}])

        resp = self._trigger(client, test_product, comp, po_user)

        assert resp.json()["warnings"] == []


class TestReviewEndpoint:
    """Three states, and the gap between the first two is the point: corrections alone
    tell you where the model is wrong and never where it is right, and cannot be told
    apart from nobody having looked."""

    def _url(self, product, competitor, job_id="j1"):
        return (
            f"/product-intelligence/products/{product.id}"
            f"/competitors/{competitor.id}/job-assessments/{job_id}/review"
        )

    def _setup(self, db_session, product):
        _job(db_session, product, "j1")
        comp = _competitor(db_session, product, "Productboard")
        _report(db_session, product, comp, [{
            "job_id": "j1",
            "job_statement": "Statement for j1",
            "competitor_score": 8,
            "our_score": 4,
            "system_position": "gap",
        }])
        return comp

    def test_agreeing_records_the_review_without_asserting_a_position(
        self, db_session, client, test_product, po_user
    ):
        # Recording agreement as an override would freeze today's verdict against
        # future re-derivation.
        comp = self._setup(db_session, test_product)

        resp = client.post(
            self._url(test_product, comp),
            json={"action": "agree"},
            headers=auth_headers(po_user),
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["human_position"] is None
        assert body["reviewed_at"] is not None
        assert body["system_position"] == "gap"

    def test_override_sets_the_human_verdict(
        self, db_session, client, test_product, po_user
    ):
        comp = self._setup(db_session, test_product)

        resp = client.post(
            self._url(test_product, comp),
            json={"action": "override", "position": "parity", "note": "They dropped it"},
            headers=auth_headers(po_user),
        )

        body = resp.json()
        assert body["human_position"] == "parity"
        # The system verdict is kept alongside, not replaced.
        assert body["system_position"] == "gap"

    def test_override_requires_a_position(
        self, db_session, client, test_product, po_user
    ):
        comp = self._setup(db_session, test_product)
        resp = client.post(
            self._url(test_product, comp),
            json={"action": "override"},
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 400
        assert "position is required" in resp.json()["detail"]

    def test_unknown_cannot_be_asserted_by_a_human(
        self, db_session, client, test_product, po_user
    ):
        # `unknown` is what the system says when it cannot compare. A person has no
        # reason to claim it.
        comp = self._setup(db_session, test_product)
        resp = client.post(
            self._url(test_product, comp),
            json={"action": "override", "position": "unknown"},
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 400

    def test_clear_returns_to_unreviewed_not_agreed(
        self, db_session, client, test_product, po_user
    ):
        # Undoing a mistaken override is not an assertion that the verdict is right.
        comp = self._setup(db_session, test_product)
        client.post(
            self._url(test_product, comp),
            json={"action": "override", "position": "parity"},
            headers=auth_headers(po_user),
        )

        resp = client.post(
            self._url(test_product, comp),
            json={"action": "clear"},
            headers=auth_headers(po_user),
        )

        body = resp.json()
        assert body["human_position"] is None
        assert body["reviewed_at"] is None

    def test_review_snapshots_the_wording_judged_against(
        self, db_session, client, test_product, po_user
    ):
        comp = self._setup(db_session, test_product)
        client.post(
            self._url(test_product, comp),
            json={"action": "agree"},
            headers=auth_headers(po_user),
        )

        report = db_session.query(CompetitorFunctionalReport).filter(
            CompetitorFunctionalReport.product_competitor_id == comp.id
        ).first()
        db_session.refresh(report)
        # Without this snapshot a later restatement would silently apply the review to
        # a materially different job.
        assert report.job_assessments[0]["reviewed_job_statement"] == "Statement for j1"

    def test_unknown_job_is_rejected(self, db_session, client, test_product, po_user):
        comp = self._setup(db_session, test_product)
        resp = client.post(
            self._url(test_product, comp, job_id="j99"),
            json={"action": "agree"},
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 404

    def test_unaudited_competitor_is_rejected(
        self, db_session, client, test_product, po_user
    ):
        _job(db_session, test_product, "j1")
        comp = _competitor(db_session, test_product, "Never audited")
        resp = client.post(
            self._url(test_product, comp),
            json={"action": "agree"},
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 404

    def test_invalid_action_is_rejected(self, db_session, client, test_product, po_user):
        comp = self._setup(db_session, test_product)
        resp = client.post(
            self._url(test_product, comp),
            json={"action": "approve"},
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 400

    def test_voter_cannot_review(
        self, db_session, client, test_product, voter_user, voter_product_access
    ):
        # Reviewing is an edit to the analysis, not a read of it.
        comp = self._setup(db_session, test_product)
        resp = client.post(
            self._url(test_product, comp),
            json={"action": "agree"},
            headers=auth_headers(voter_user),
        )
        assert resp.status_code in (403, 404)


class TestMapHealthOnCoverage:
    """Map health belongs on this response because this is where the misleading
    conclusion gets drawn — high scores across the board mean nothing if the jobs came
    from the product's own description."""

    def test_reports_the_share_with_a_non_product_source(
        self, db_session, client, test_product, po_user
    ):
        from app.models.competitor_intelligence import (
            JOB_PROVENANCE_COMPETITOR,
            JOB_PROVENANCE_PRODUCT,
        )

        _job(db_session, test_product, "j1", provenance={"type": JOB_PROVENANCE_PRODUCT})
        _job(db_session, test_product, "j2", provenance={"type": JOB_PROVENANCE_COMPETITOR})

        resp = client.get(
            f"/product-intelligence/products/{test_product.id}/job-coverage",
            headers=auth_headers(po_user),
        )

        health = resp.json()["map_health"]
        assert health["total_jobs"] == 2
        assert health["independent_source_pct"] == 50

    def test_fully_product_derived_map_is_visible_as_zero(
        self, db_session, client, test_product, po_user
    ):
        from app.models.competitor_intelligence import JOB_PROVENANCE_PRODUCT

        _job(db_session, test_product, "j1", provenance={"type": JOB_PROVENANCE_PRODUCT})

        resp = client.get(
            f"/product-intelligence/products/{test_product.id}/job-coverage",
            headers=auth_headers(po_user),
        )

        assert resp.json()["map_health"]["independent_source_pct"] == 0


class TestVerdictWithholding:
    """A verdict is a claim about how we compare, and is only as good as our own score.

    The job map is usually generated from the product's own description, so a low-confidence
    self-score with nothing corroborating it is close to a restatement of marketing copy.
    Rendering that as a confident GAP is worse than saying nothing, because a reader cannot
    tell it apart from a grounded one.
    """

    def _setup(self, db_session, product, our_confidence, with_evidence=False):
        _job(db_session, product, "j1")
        comp = _competitor(db_session, product, "Productboard")
        _report(db_session, product, comp, [{
            "job_id": "j1",
            "competitor_score": 8,
            "system_position": "gap",
        }])
        _self_assessment(db_session, product, [{
            "job_id": "j1", "score": 4, "confidence": our_confidence,
        }])
        if with_evidence:
            _evidence_for_job(db_session, product, "j1")
        return comp

    def test_withheld_when_our_score_is_ungrounded(
        self, db_session, client, test_product, po_user
    ):
        self._setup(db_session, test_product, "low")

        resp = client.get(
            f"/product-intelligence/products/{test_product.id}/job-coverage",
            headers=auth_headers(po_user),
        )

        cell = resp.json()["jobs"][0]["competitors"][0]
        assert cell["verdict_shown"] is False
        assert "product description" in cell["verdict_withheld_reason"]

    def test_competitor_score_is_still_reported_when_withheld(
        self, db_session, client, test_product, po_user
    ):
        # Their side is researched independently of our map and is unaffected by its
        # weakness — withholding it too would discard sound data.
        self._setup(db_session, test_product, "low")

        resp = client.get(
            f"/product-intelligence/products/{test_product.id}/job-coverage",
            headers=auth_headers(po_user),
        )

        cell = resp.json()["jobs"][0]["competitors"][0]
        assert cell["competitor_score"] == 8

    def test_shown_when_confidence_is_not_low(
        self, db_session, client, test_product, po_user
    ):
        self._setup(db_session, test_product, "medium")

        resp = client.get(
            f"/product-intelligence/products/{test_product.id}/job-coverage",
            headers=auth_headers(po_user),
        )

        cell = resp.json()["jobs"][0]["competitors"][0]
        assert cell["verdict_shown"] is True
        assert cell["verdict_withheld_reason"] is None

    def test_corroborating_signal_rescues_a_low_confidence_score(
        self, db_session, client, test_product, po_user
    ):
        # Provenance is not the trigger — grounding is. A job carrying real customer
        # signal deserves a verdict even when the map entry came from product copy.
        self._setup(db_session, test_product, "low", with_evidence=True)

        resp = client.get(
            f"/product-intelligence/products/{test_product.id}/job-coverage",
            headers=auth_headers(po_user),
        )

        row = resp.json()["jobs"][0]
        assert row["corroborating_signals"] == 1
        assert row["competitors"][0]["verdict_shown"] is True
