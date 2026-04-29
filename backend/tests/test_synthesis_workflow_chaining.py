"""Tests for unified synthesis workflow chaining.

Two behaviors:
1. _bump_parent_synthesis_progress updates an in-flight synthesis job's
   progress as each child audit completes, but only when the parent is
   actually a unified synthesis in audits_in_progress state.
2. unified_synthesis_task dispatches a Celery chord with
   resume_unified_synthesis_task as the callback when any included
   competitor lacks a functional report; otherwise it runs synthesis
   directly via _run_unified_synthesis_post_audits.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.models.queue import QueueJob, JobStatus, JobType
from app.models.competitor_intelligence import ProductCompetitor
from app.queue.helpers import _bump_parent_synthesis_progress


def _make_synthesis_job(db_session, product_id: int, **overrides) -> QueueJob:
    """Create a synthesis-shaped QueueJob in the given state."""
    job = QueueJob(
        job_type=overrides.get("job_type", JobType.UNIFIED_SYNTHESIS)
            if hasattr(JobType, "UNIFIED_SYNTHESIS")
            else JobType.LANDSCAPE_SYNTHESIS,
        status=overrides.get("status", JobStatus.RUNNING),
        product_id=product_id,
        output_data=overrides.get(
            "output_data",
            {"status": "audits_in_progress", "triggered_audit_job_ids": []},
        ),
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


def _make_audit_child(db_session, parent_job_id: int, product_id: int,
                     status: JobStatus = JobStatus.PENDING) -> QueueJob:
    job = QueueJob(
        job_type=JobType.FUNCTIONAL_AUDIT,
        status=status,
        product_id=product_id,
        parent_job_id=parent_job_id,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


class TestBumpParentSynthesisProgress:
    """Helper updates parent progress as audits finish — but only for
    in-flight unified synthesis parents."""

    def test_bumps_progress_proportional_to_completed_audits(
        self, db_session, test_product
    ):
        parent = _make_synthesis_job(db_session, test_product.id)
        # 4 children, 2 done (1 success, 1 failure), 2 still running
        _make_audit_child(db_session, parent.id, test_product.id, JobStatus.SUCCESS)
        _make_audit_child(db_session, parent.id, test_product.id, JobStatus.FAILURE)
        _make_audit_child(db_session, parent.id, test_product.id, JobStatus.RUNNING)
        _make_audit_child(db_session, parent.id, test_product.id, JobStatus.PENDING)

        _bump_parent_synthesis_progress(db_session, parent.id)

        db_session.refresh(parent)
        # 2 of 4 = 50% of audit window. Range is 10–14%, so 10 + 4*0.5 = 12.0
        assert parent.progress_percent == pytest.approx(12.0, abs=0.01)
        assert "2 of 4 complete" in (parent.progress_message or "")

    def test_bump_is_noop_when_parent_not_running(self, db_session, test_product):
        parent = _make_synthesis_job(
            db_session, test_product.id, status=JobStatus.SUCCESS,
        )
        original_message = parent.progress_message
        _make_audit_child(db_session, parent.id, test_product.id, JobStatus.SUCCESS)
        _bump_parent_synthesis_progress(db_session, parent.id)
        db_session.refresh(parent)
        assert parent.progress_message == original_message

    def test_bump_is_noop_when_status_not_audits_in_progress(
        self, db_session, test_product
    ):
        # Parent is running but its output_data doesn't say audits_in_progress —
        # this means it's a synthesis without triggered audits, or some other
        # job entirely. Don't touch it.
        parent = _make_synthesis_job(
            db_session, test_product.id,
            output_data={"status": "running_synthesis"},
        )
        _make_audit_child(db_session, parent.id, test_product.id, JobStatus.SUCCESS)
        _bump_parent_synthesis_progress(db_session, parent.id)
        db_session.refresh(parent)
        # progress_percent should remain whatever it was (None or 0)
        assert parent.progress_message != "Running competitor audit(s)... 1 of 1 complete"

    def test_bump_handles_zero_children_safely(self, db_session, test_product):
        parent = _make_synthesis_job(db_session, test_product.id)
        # No children at all; should not divide-by-zero.
        _bump_parent_synthesis_progress(db_session, parent.id)
        # No assertion needed — the test passes if no exception is raised.

    def test_bump_handles_missing_parent_safely(self, db_session):
        # Pointed at an ID that doesn't exist — best-effort behavior is no-op.
        _bump_parent_synthesis_progress(db_session, 999_999)


class TestUnifiedSynthesisChordDispatch:
    """When a synthesis run finds missing audits, it must dispatch a chord
    with resume_unified_synthesis_task as the callback (not block, not return
    "deferred")."""

    def _make_competitor(self, db_session, product_id: int, name: str,
                         synthesis_included: bool = True,
                         audit_status: str | None = None) -> ProductCompetitor:
        c = ProductCompetitor(
            product_id=product_id,
            competitor_name=name,
            competitor_url=f"https://{name.lower()}.example.com",
            status="active",
            synthesis_included=synthesis_included,
        )
        if audit_status:
            c.audit_status = audit_status
        db_session.add(c)
        db_session.commit()
        db_session.refresh(c)
        return c

    @patch("app.queue.synthesis_tasks.SessionLocal")
    @patch("celery.chord")
    def test_dispatches_chord_when_audits_missing(
        self, mock_chord, mock_session_local, db_session, test_product
    ):
        """When at least one included competitor has no functional report,
        the task must call chord(audit_signatures)(resume_callback)."""
        from app.queue.synthesis_tasks import unified_synthesis_task

        mock_session_local.return_value = db_session

        # Create the synthesis job
        synthesis_job = QueueJob(
            job_type=JobType.LANDSCAPE_SYNTHESIS,
            status=JobStatus.PENDING,
            product_id=test_product.id,
        )
        db_session.add(synthesis_job)
        db_session.commit()
        db_session.refresh(synthesis_job)
        synthesis_job_id = synthesis_job.id  # capture before the task may detach it

        # Create competitors that need audits (no functional report exists)
        self._make_competitor(db_session, test_product.id, "Acme")
        self._make_competitor(db_session, test_product.id, "Globex")

        # Configure the chord mock to be a callable returning a callable
        chord_callback = MagicMock()
        mock_chord.return_value = chord_callback

        # Run the task body (bypassing Celery's @shared_task wrapper)
        result = unified_synthesis_task.run(synthesis_job_id)

        # Chord was called with audit signatures
        assert mock_chord.called
        # The callback (signature) was applied
        assert chord_callback.called

        # Task returned the audits-in-progress envelope
        assert result["status"] == "audits_in_progress"
        assert len(result["triggered_audit_job_ids"]) == 2

        # Synthesis job is RUNNING with audits_in_progress in output_data.
        # Re-fetch by captured ID — the task body may have closed/refreshed
        # the session, leaving the original instance detached.
        refreshed = db_session.query(QueueJob).filter(
            QueueJob.id == synthesis_job_id
        ).first()
        assert refreshed.status == JobStatus.RUNNING
        assert refreshed.output_data["status"] == "audits_in_progress"
