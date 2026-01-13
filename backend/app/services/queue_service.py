"""
Queue Service for managing background jobs.

This module provides a high-level interface for creating, tracking,
and managing background jobs. It bridges the gap between the API
layer and Celery task execution.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.models.queue import QueueJob, JobType, JobStatus, JobPriority

# Jobs older than this without a celery_task_id are considered stale
STALE_PENDING_THRESHOLD_MINUTES = 5
# Jobs running longer than this without progress are considered stale
STALE_RUNNING_THRESHOLD_MINUTES = 60


class QueueServiceError(Exception):
    """Base exception for queue service errors."""
    pass


class JobNotFoundError(QueueServiceError):
    """Raised when a job is not found."""
    pass


class QueueService:
    """
    Service for managing background jobs.

    Provides methods to:
    - Create and queue jobs
    - Update job status and progress
    - Query job history
    - Cancel running jobs
    """

    def __init__(self, db: Session):
        """
        Initialize the queue service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def create_job(
        self,
        job_type: JobType,
        input_data: Dict[str, Any],
        product_id: Optional[int] = None,
        user_id: Optional[int] = None,
        parent_job_id: Optional[int] = None,
        priority: JobPriority = JobPriority.NORMAL,
        auto_commit: bool = True,
    ) -> QueueJob:
        """
        Create a new job record in the database.

        Args:
            job_type: Type of job to create
            input_data: Input parameters for the job
            product_id: Optional product this job relates to
            user_id: Optional user who initiated the job
            parent_job_id: Optional parent job for chaining
            priority: Job priority level
            auto_commit: If True, commit immediately. If False, caller must commit.

        Returns:
            Created QueueJob instance
        """
        job = QueueJob(
            job_type=job_type,
            status=JobStatus.PENDING,
            priority=priority,
            input_data=input_data,
            product_id=product_id,
            user_id=user_id,
            parent_job_id=parent_job_id,
        )
        self.db.add(job)
        if auto_commit:
            self.db.commit()
            self.db.refresh(job)
        else:
            self.db.flush()  # Get the ID without committing
        return job

    def get_job(self, job_id: int) -> Optional[QueueJob]:
        """
        Get a job by ID.

        Args:
            job_id: Job ID to look up

        Returns:
            QueueJob if found, None otherwise
        """
        return self.db.query(QueueJob).filter(QueueJob.id == job_id).first()

    def get_job_by_uuid(self, job_uuid: str) -> Optional[QueueJob]:
        """
        Get a job by UUID.

        Args:
            job_uuid: Job UUID to look up

        Returns:
            QueueJob if found, None otherwise
        """
        return self.db.query(QueueJob).filter(QueueJob.job_uuid == job_uuid).first()

    def get_job_by_celery_id(self, celery_task_id: str) -> Optional[QueueJob]:
        """
        Get a job by its Celery task ID.

        Args:
            celery_task_id: Celery task ID

        Returns:
            QueueJob if found, None otherwise
        """
        return self.db.query(QueueJob).filter(
            QueueJob.celery_task_id == celery_task_id
        ).first()

    def update_job_status(
        self,
        job_id: int,
        status: JobStatus,
        celery_task_id: Optional[str] = None,
        progress_percent: Optional[float] = None,
        progress_message: Optional[str] = None,
        output_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        error_traceback: Optional[str] = None,
    ) -> QueueJob:
        """
        Update job status and optionally other fields.

        Args:
            job_id: Job ID to update
            status: New status
            celery_task_id: Celery task ID (set when queued)
            progress_percent: Progress percentage (0-100)
            progress_message: Human-readable progress message
            output_data: Job output/result data
            error_message: Error message if failed
            error_traceback: Full error traceback if failed

        Returns:
            Updated QueueJob

        Raises:
            JobNotFoundError: If job doesn't exist
        """
        job = self.get_job(job_id)
        if not job:
            raise JobNotFoundError(f"Job {job_id} not found")

        job.status = status

        if celery_task_id is not None:
            job.celery_task_id = celery_task_id

        if progress_percent is not None:
            job.progress_percent = progress_percent

        if progress_message is not None:
            job.progress_message = progress_message

        if output_data is not None:
            job.output_data = output_data

        if error_message is not None:
            job.error_message = error_message

        if error_traceback is not None:
            job.error_traceback = error_traceback

        # Update timestamps based on status
        now = datetime.utcnow()
        if status == JobStatus.QUEUED:
            job.queued_at = now
        elif status == JobStatus.RUNNING:
            job.started_at = now
        elif status in (JobStatus.SUCCESS, JobStatus.FAILURE, JobStatus.CANCELLED):
            job.completed_at = now
            if status == JobStatus.SUCCESS:
                job.progress_percent = 100.0

        self.db.commit()
        self.db.refresh(job)
        return job

    def update_progress(
        self,
        job_id: int,
        progress_percent: float,
        progress_message: Optional[str] = None,
    ) -> QueueJob:
        """
        Update job progress without changing status.

        Args:
            job_id: Job ID to update
            progress_percent: Progress percentage (0-100)
            progress_message: Optional progress message

        Returns:
            Updated QueueJob
        """
        return self.update_job_status(
            job_id=job_id,
            status=JobStatus.RUNNING,
            progress_percent=progress_percent,
            progress_message=progress_message,
        )

    def mark_queued(self, job_id: int, celery_task_id: str) -> QueueJob:
        """
        Mark job as queued with its Celery task ID.

        Args:
            job_id: Job ID to update
            celery_task_id: Celery task ID

        Returns:
            Updated QueueJob
        """
        return self.update_job_status(
            job_id=job_id,
            status=JobStatus.QUEUED,
            celery_task_id=celery_task_id,
        )

    def mark_running(self, job_id: int) -> QueueJob:
        """
        Mark job as currently running.

        Args:
            job_id: Job ID to update

        Returns:
            Updated QueueJob
        """
        return self.update_job_status(
            job_id=job_id,
            status=JobStatus.RUNNING,
        )

    def mark_success(
        self,
        job_id: int,
        output_data: Optional[Dict[str, Any]] = None,
    ) -> QueueJob:
        """
        Mark job as successfully completed.

        Args:
            job_id: Job ID to update
            output_data: Job result data

        Returns:
            Updated QueueJob
        """
        return self.update_job_status(
            job_id=job_id,
            status=JobStatus.SUCCESS,
            output_data=output_data,
            progress_percent=100.0,
        )

    def mark_failure(
        self,
        job_id: int,
        error_message: str,
        error_traceback: Optional[str] = None,
    ) -> QueueJob:
        """
        Mark job as failed.

        Args:
            job_id: Job ID to update
            error_message: Error message
            error_traceback: Full error traceback

        Returns:
            Updated QueueJob
        """
        job = self.get_job(job_id)
        if job:
            job.retry_count = (job.retry_count or 0) + 1

        return self.update_job_status(
            job_id=job_id,
            status=JobStatus.FAILURE,
            error_message=error_message,
            error_traceback=error_traceback,
        )

    def cancel_job(self, job_id: int) -> QueueJob:
        """
        Cancel a pending or running job.

        Args:
            job_id: Job ID to cancel

        Returns:
            Updated QueueJob

        Raises:
            JobNotFoundError: If job doesn't exist
            QueueServiceError: If job cannot be cancelled
        """
        job = self.get_job(job_id)
        if not job:
            raise JobNotFoundError(f"Job {job_id} not found")

        if job.is_complete:
            raise QueueServiceError(f"Cannot cancel completed job {job_id}")

        # TODO: Actually revoke the Celery task if running
        # from app.queue import celery_app
        # celery_app.control.revoke(job.celery_task_id, terminate=True)

        return self.update_job_status(
            job_id=job_id,
            status=JobStatus.CANCELLED,
        )

    def get_jobs_for_product(
        self,
        product_id: int,
        status: Optional[JobStatus] = None,
        job_type: Optional[JobType] = None,
        limit: int = 50,
    ) -> List[QueueJob]:
        """
        Get jobs for a specific product.

        Args:
            product_id: Product ID to filter by
            status: Optional status filter
            job_type: Optional type filter
            limit: Maximum number of jobs to return

        Returns:
            List of matching QueueJob records
        """
        query = self.db.query(QueueJob).filter(QueueJob.product_id == product_id)

        if status:
            query = query.filter(QueueJob.status == status)

        if job_type:
            query = query.filter(QueueJob.job_type == job_type)

        return query.order_by(QueueJob.created_at.desc()).limit(limit).all()

    def cleanup_stale_jobs(
        self,
        product_id: Optional[int] = None,
    ) -> int:
        """
        Mark stale jobs as failed.

        A job is considered stale if:
        - It's PENDING without a celery_task_id for more than STALE_PENDING_THRESHOLD_MINUTES
        - It's QUEUED/RUNNING without started_at for more than STALE_PENDING_THRESHOLD_MINUTES
        - It's RUNNING for more than STALE_RUNNING_THRESHOLD_MINUTES

        Args:
            product_id: Optional product filter

        Returns:
            Number of jobs marked as failed
        """
        now = datetime.utcnow()
        pending_threshold = now - timedelta(minutes=STALE_PENDING_THRESHOLD_MINUTES)
        running_threshold = now - timedelta(minutes=STALE_RUNNING_THRESHOLD_MINUTES)

        # Find stale jobs
        query = self.db.query(QueueJob).filter(
            QueueJob.status.in_([JobStatus.PENDING, JobStatus.QUEUED, JobStatus.RUNNING])
        )

        if product_id:
            query = query.filter(QueueJob.product_id == product_id)

        stale_jobs = []
        for job in query.all():
            is_stale = False
            reason = ""

            if job.status == JobStatus.PENDING:
                # PENDING jobs without celery_task_id that are old
                if not job.celery_task_id and job.created_at < pending_threshold:
                    is_stale = True
                    reason = "Job stuck in PENDING state without being dispatched to Celery"

            elif job.status == JobStatus.QUEUED:
                # QUEUED jobs that never started
                if not job.started_at and job.queued_at and job.queued_at < pending_threshold:
                    is_stale = True
                    reason = "Job stuck in QUEUED state without starting"

            elif job.status == JobStatus.RUNNING:
                # RUNNING jobs that have been running too long
                if job.started_at and job.started_at < running_threshold:
                    is_stale = True
                    reason = f"Job running for more than {STALE_RUNNING_THRESHOLD_MINUTES} minutes"

            if is_stale:
                job.status = JobStatus.FAILURE
                job.error_message = reason
                job.completed_at = now
                stale_jobs.append(job)

        if stale_jobs:
            self.db.commit()

        return len(stale_jobs)

    def get_active_jobs(
        self,
        product_id: Optional[int] = None,
        user_id: Optional[int] = None,
        cleanup_stale: bool = True,
    ) -> List[QueueJob]:
        """
        Get currently active (queued or running) jobs.

        Args:
            product_id: Optional product filter
            user_id: Optional user filter
            cleanup_stale: If True, automatically mark stale jobs as failed first

        Returns:
            List of active QueueJob records
        """
        # Clean up stale jobs first
        if cleanup_stale:
            self.cleanup_stale_jobs(product_id=product_id)

        query = self.db.query(QueueJob).filter(
            QueueJob.status.in_([JobStatus.PENDING, JobStatus.QUEUED, JobStatus.RUNNING])
        )

        if product_id:
            query = query.filter(QueueJob.product_id == product_id)

        if user_id:
            query = query.filter(QueueJob.user_id == user_id)

        return query.order_by(QueueJob.created_at.asc()).all()

    def get_job_with_children(self, job_id: int) -> Dict[str, Any]:
        """
        Get a job with its child jobs for workflow tracking.

        Args:
            job_id: Parent job ID

        Returns:
            Dictionary with job and children
        """
        job = self.get_job(job_id)
        if not job:
            raise JobNotFoundError(f"Job {job_id} not found")

        children = self.db.query(QueueJob).filter(
            QueueJob.parent_job_id == job_id
        ).order_by(QueueJob.created_at.asc()).all()

        return {
            "job": job.to_dict(),
            "children": [child.to_dict() for child in children],
        }


def get_queue_service(db: Session) -> QueueService:
    """Factory function to create a QueueService instance."""
    return QueueService(db)
