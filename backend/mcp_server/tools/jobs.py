"""Job status tool for MCP server."""

from mcp_server import mcp
from mcp_server.db import get_session


@mcp.tool()
def job_get_status(job_uuid: str) -> dict:
    """Check the status of a background analysis job."""
    from app.services.queue_service import QueueService

    with get_session() as db:
        queue_service = QueueService(db)
        job = queue_service.get_job_by_uuid(job_uuid)

        if not job:
            return {"error": f"Job {job_uuid} not found"}

        result = {
            "job_uuid": job.job_uuid,
            "job_type": job.job_type.value if job.job_type else None,
            "status": job.status.value if job.status else None,
            "progress_percent": job.progress_percent,
            "progress_message": job.progress_message,
            "created_at": job.created_at.isoformat() if job.created_at else None,
        }

        if job.is_complete:
            result["completed_at"] = job.completed_at.isoformat() if job.completed_at else None
            result["output_data"] = job.output_data
            result["duration_seconds"] = job.duration_seconds

        if job.error_message:
            result["error_message"] = job.error_message

        return result
