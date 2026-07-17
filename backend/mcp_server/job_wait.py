"""Shared server-side wait for kickoff tools.

Job-starting MCP tools (product_run_analysis, ci_run_competitor_audit,
synthesis_run_unified, ...) accept an optional wait_seconds. When > 0, they
call wait_for_job after dispatch to block server-side until the job finishes
or the window elapses — turning the agent's rapid client-side polling of
job_get_status into a single call. When wait_seconds is 0 (default) they
return immediately with status "queued", preserving fire-and-continue.
"""

import time

from mcp_server.db import get_session

# Ceiling keeps a single call well under typical MCP/HTTP request timeouts;
# the agent re-calls (or polls job_get_status) to keep waiting on a job that
# outlives one window.
WAIT_MAX_SECONDS = 120
_POLL_INTERVAL = 2.0

_TERMINAL_STATUSES = ("success", "failure", "cancelled")


def wait_for_job(job_uuid: str, wait_seconds: int) -> dict:
    """Block until the job reaches a terminal status or wait_seconds elapses.

    wait_seconds is clamped to [0, WAIT_MAX_SECONDS]. Returns a job_summary
    dict (with output_data once complete). Adds "waiting": true if the window
    elapsed while the job was still active — the caller should surface that so
    the agent knows to check back. Returns the summary unchanged (no "waiting"
    key) once the job is terminal.

    Uses a fresh short-lived session per poll so no transaction is held open
    across the sleep loop.
    """
    from app.services.queue_service import QueueService
    from mcp_server.serializers import job_summary

    wait_seconds = max(0, min(WAIT_MAX_SECONDS, wait_seconds))
    deadline = time.monotonic() + wait_seconds

    while True:
        with get_session() as db:
            job = QueueService(db).get_job_by_uuid(job_uuid)
            if not job:
                return {"error": f"Job {job_uuid} not found"}
            summary = job_summary(job, include_output=True)

        if summary.get("status") in _TERMINAL_STATUSES:
            return summary

        if time.monotonic() >= deadline:
            summary["waiting"] = True
            return summary

        remaining = deadline - time.monotonic()
        time.sleep(min(_POLL_INTERVAL, max(0.0, remaining)))


def maybe_wait(queued_result: dict, wait_seconds: int) -> dict:
    """Optionally block for a just-dispatched job, for kickoff tools.

    Given a kickoff tool's queued-return dict (must contain job_uuid), returns
    it unchanged when wait_seconds <= 0 (fire-and-return). Otherwise blocks up
    to wait_seconds and merges the job's live status/progress/output_data into
    the result, so the tool returns the finished result in a single call. On
    timeout the merged result carries "waiting": true.
    """
    if wait_seconds <= 0:
        return queued_result

    job_uuid = queued_result.get("job_uuid")
    if not job_uuid:
        return queued_result

    waited = wait_for_job(job_uuid, wait_seconds)
    if "error" in waited:
        # Dispatch already succeeded; surface the wait error without losing the
        # queued context (job_uuid, message) the caller can poll with.
        return {**queued_result, "wait_error": waited["error"]}

    return {**queued_result, **waited}
