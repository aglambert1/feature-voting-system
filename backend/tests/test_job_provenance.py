"""
Tests for job map provenance and corroboration.

The distinction under test: entry provenance answers "where did this job come from" and
measures how circular the map is; corroboration answers "what establishes it is real" and
is derived from signal linkage. A job extracted from the product's own description, with
nothing independent supporting it, is the case the health metric exists to surface.
"""

import pytest

from app.models.competitor_intelligence import (
    JOB_IN_TARGET,
    JOB_OUT_OF_TARGET,
    JOB_PROVENANCE_COMPETITOR,
    JOB_PROVENANCE_PM,
    JOB_PROVENANCE_PRODUCT,
    JOB_PROVENANCE_SIGNAL,
    JOB_UNVALIDATED,
    JOB_VALIDATED,
    JobImportance,
    JobType,
    ProductJob,
)
from app.models.evidence import Evidence, EvidenceType
from app.services.job_provenance import (
    has_independent_support,
    map_health,
    signal_counts,
)


@pytest.fixture
def product(test_product):
    """The shared CIProduct fixture, aliased for readability in this module."""
    return test_product


def _job(db_session, product, key, provenance_type=None, **kwargs):
    job = ProductJob(
        product_id=product.id,
        job_id_key=key,
        job_type=JobType.FUNCTIONAL,
        statement=f"Statement for {key}",
        importance=JobImportance.HIGH,
        provenance=(
            {"type": provenance_type, "source_ref": "x:1", "added_at": "2026-08-31T00:00:00Z"}
            if provenance_type
            else None
        ),
        **kwargs,
    )
    db_session.add(job)
    db_session.commit()
    return job


def _evidence(db_session, product, job_id_key):
    ev = Evidence(
        product_id=product.id,
        evidence_type=EvidenceType.CUSTOMER_INTERVIEW,
        title="A customer said something",
        content="...",
        job_id_key=job_id_key,
    )
    db_session.add(ev)
    db_session.commit()
    return ev


class TestDefaults:
    def test_new_job_is_unvalidated_and_in_target(self, db_session, product):
        # Review is optional, so unvalidated is the resting state rather than a warning.
        job = _job(db_session, product, "j1")
        assert job.validation_state == JOB_UNVALIDATED
        assert job.serve_intent == JOB_IN_TARGET

    def test_provenance_may_be_unknown(self, db_session, product):
        # Jobs predating provenance tracking have no recorded origin, and inventing one
        # would assert a lineage never observed.
        job = _job(db_session, product, "j1")
        assert job.provenance is None


class TestIndependentSupport:
    def test_product_derived_alone_is_not_supported(self, db_session, product):
        job = _job(db_session, product, "j1", JOB_PROVENANCE_PRODUCT)
        assert has_independent_support(job, None) is False

    @pytest.mark.parametrize("provenance", [
        JOB_PROVENANCE_SIGNAL,
        JOB_PROVENANCE_COMPETITOR,
        JOB_PROVENANCE_PM,
    ])
    def test_non_product_origin_is_supported(self, db_session, product, provenance):
        job = _job(db_session, product, "j1", provenance)
        assert has_independent_support(job, None) is True

    def test_product_derived_becomes_supported_once_a_signal_links(self, db_session, product):
        # The map gets less circular as the product is used, with no PM effort.
        job = _job(db_session, product, "j1", JOB_PROVENANCE_PRODUCT)
        assert has_independent_support(job, {"total": 3}) is True

    def test_unknown_provenance_counts_as_unsupported(self, db_session, product):
        job = _job(db_session, product, "j1")
        assert has_independent_support(job, None) is False

    def test_unknown_provenance_with_signals_is_supported(self, db_session, product):
        job = _job(db_session, product, "j1")
        assert has_independent_support(job, {"total": 1}) is True


class TestSignalCounts:
    def test_counts_linked_evidence(self, db_session, product):
        _job(db_session, product, "j1", JOB_PROVENANCE_PRODUCT)
        _evidence(db_session, product, "j1")
        _evidence(db_session, product, "j1")

        counts = signal_counts(db_session, product.id)

        assert counts["j1"]["evidence"] == 2
        assert counts["j1"]["total"] == 2

    def test_unlinked_jobs_are_absent_not_zero(self, db_session, product):
        _job(db_session, product, "j1", JOB_PROVENANCE_PRODUCT)
        counts = signal_counts(db_session, product.id)
        assert "j1" not in counts

    def test_signals_with_no_job_are_ignored(self, db_session, product):
        _job(db_session, product, "j1", JOB_PROVENANCE_PRODUCT)
        _evidence(db_session, product, None)

        counts = signal_counts(db_session, product.id)

        assert counts == {}


class TestMapHealth:
    def test_fully_product_derived_map_scores_zero(self, db_session, product):
        # The warning case: every job came from the product's own description.
        for key in ("j1", "j2", "j3"):
            _job(db_session, product, key, JOB_PROVENANCE_PRODUCT)

        health = map_health(db_session, product.id)

        assert health["total_jobs"] == 3
        assert health["jobs_with_independent_source"] == 0
        assert health["independent_source_pct"] == 0
        assert health["by_provenance"][JOB_PROVENANCE_PRODUCT] == 3

    def test_mixed_map_reports_the_share_supported(self, db_session, product):
        _job(db_session, product, "j1", JOB_PROVENANCE_PRODUCT)
        _job(db_session, product, "j2", JOB_PROVENANCE_SIGNAL)
        _job(db_session, product, "j3", JOB_PROVENANCE_COMPETITOR)
        _job(db_session, product, "j4", JOB_PROVENANCE_PRODUCT)
        _evidence(db_session, product, "j4")  # corroborated after the fact

        health = map_health(db_session, product.id)

        assert health["total_jobs"] == 4
        assert health["jobs_with_independent_source"] == 3
        assert health["independent_source_pct"] == 75

    def test_empty_map_reports_none_not_zero(self, db_session, product):
        # "0% supported" would read as a failing map when there is simply no map yet.
        health = map_health(db_session, product.id)
        assert health["total_jobs"] == 0
        assert health["independent_source_pct"] is None

    def test_counts_unvalidated_and_out_of_target(self, db_session, product):
        _job(db_session, product, "j1", JOB_PROVENANCE_PRODUCT)
        _job(
            db_session, product, "j2", JOB_PROVENANCE_COMPETITOR,
            serve_intent=JOB_OUT_OF_TARGET,
            validation_state=JOB_VALIDATED,
        )

        health = map_health(db_session, product.id)

        assert health["unvalidated"] == 1
        assert health["out_of_target"] == 1

    def test_out_of_target_jobs_still_count_in_the_map(self, db_session, product):
        # The map models the customer's jobs, not our coverage — a job we deliberately
        # don't serve belongs in it and must not be silently excluded.
        _job(
            db_session, product, "j1", JOB_PROVENANCE_COMPETITOR,
            serve_intent=JOB_OUT_OF_TARGET,
        )

        health = map_health(db_session, product.id)

        assert health["total_jobs"] == 1
        assert health["jobs_with_independent_source"] == 1

    def test_retired_jobs_are_excluded(self, db_session, product):
        _job(db_session, product, "j1", JOB_PROVENANCE_PRODUCT)
        _job(db_session, product, "j2", JOB_PROVENANCE_PRODUCT, status="retired")

        health = map_health(db_session, product.id)

        assert health["total_jobs"] == 1
