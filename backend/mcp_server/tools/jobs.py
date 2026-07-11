"""Job status tool for MCP server."""

from mcp_server import mcp
from mcp_server.db import get_session
from mcp_server.permissions import require_product_access
from mcp_server.serializers import job_summary


@mcp.tool()
def job_get_status(job_uuid: str) -> dict:
    """Check the status of a background analysis job."""
    from app.services.queue_service import QueueService

    with get_session() as db:
        queue_service = QueueService(db)
        job = queue_service.get_job_by_uuid(job_uuid)

        if not job:
            return {"error": f"Job {job_uuid} not found"}

        # Permission check if job is tied to a product
        if job.product_id:
            denied = require_product_access(db, job.product_id)
            if denied:
                return denied

        return job_summary(job, include_output=True)
