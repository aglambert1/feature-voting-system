"""
Workflow orchestration for chaining queue jobs.

This module provides high-level workflow functions that chain
multiple queue jobs together for complete analysis pipelines.
"""

from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.queue import QueueJob, JobType, JobStatus, JobPriority
from app.models.competitor_intelligence import CIProduct
from app.services.queue_service import QueueService


class WorkflowError(Exception):
    """Base exception for workflow errors."""
    pass


class WorkflowService:
    """
    Service for managing multi-step analysis workflows.

    Provides methods to:
    - Start full analysis workflows
    - Chain jobs with dependencies
    - Track workflow progress
    """

    def __init__(self, db: Session):
        """
        Initialize the workflow service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.queue_service = QueueService(db)

    def start_full_analysis_workflow(
        self,
        product_id: int,
        user_id: int,
        skip_analysis: bool = False,
        competitor_ids: Optional[List[int]] = None,
    ) -> QueueJob:
        """
        Start a full analysis workflow for a product.

        The workflow consists of:
        1. Product Analysis (if not skipped)
        2. Competitor Discovery
        3. Feature Extraction (parallel for all competitors)

        Args:
            product_id: Product to analyze
            user_id: User initiating the workflow
            skip_analysis: If True, skip product analysis (use existing)
            competitor_ids: Optional specific competitors to analyze

        Returns:
            Parent workflow job for tracking

        Raises:
            WorkflowError: If product not found or not ready
        """
        from app.queue.tasks import (
            analyze_product_task,
            discover_competitors_task,
            extract_features_parallel,
        )

        # Validate product exists
        product = self.db.query(CIProduct).filter(CIProduct.id == product_id).first()
        if not product:
            raise WorkflowError(f"Product {product_id} not found")

        # Check if we can skip analysis
        if skip_analysis and not product.structured_product_data:
            raise WorkflowError(
                f"Cannot skip analysis: Product {product_id} has not been analyzed"
            )

        # Create parent workflow job
        workflow_job = self.queue_service.create_job(
            job_type=JobType.FULL_WORKFLOW,
            input_data={
                'skip_analysis': skip_analysis,
                'competitor_ids': competitor_ids,
            },
            product_id=product_id,
            user_id=user_id,
            priority=JobPriority.NORMAL,
        )

        # Determine workflow steps
        steps = []

        if not skip_analysis:
            # Step 1: Product Analysis
            analysis_job = self.queue_service.create_job(
                job_type=JobType.PRODUCT_ANALYSIS,
                input_data={
                    'product_name': product.product_name,
                    'product_description': product.product_description,
                    'source_type': product.product_source_type or 'text',
                },
                product_id=product_id,
                user_id=user_id,
                parent_job_id=workflow_job.id,
            )
            steps.append(('analysis', analysis_job.id))

        # Step 2: Competitor Discovery (if no specific competitors provided)
        if not competitor_ids:
            discovery_job = self.queue_service.create_job(
                job_type=JobType.COMPETITOR_DISCOVERY,
                input_data={},
                product_id=product_id,
                user_id=user_id,
                parent_job_id=workflow_job.id,
            )
            steps.append(('discovery', discovery_job.id))

        self.db.commit()

        # Queue the first step
        if steps:
            first_step_type, first_step_id = steps[0]
            if first_step_type == 'analysis':
                celery_result = analyze_product_task.delay(first_step_id)
                self.queue_service.mark_queued(first_step_id, celery_result.id)
            elif first_step_type == 'discovery':
                celery_result = discover_competitors_task.delay(first_step_id)
                self.queue_service.mark_queued(first_step_id, celery_result.id)

        # Mark workflow as queued
        self.queue_service.update_job_status(
            workflow_job.id,
            JobStatus.QUEUED,
            progress_message=f"Workflow started with {len(steps)} steps",
        )

        self.db.commit()

        return workflow_job

    def continue_workflow(self, completed_job_id: int) -> Optional[QueueJob]:
        """
        Continue a workflow after a step completes.

        Called by tasks after completion to trigger next step.

        Args:
            completed_job_id: ID of the just-completed job

        Returns:
            Next job if workflow continues, None if complete
        """
        from app.queue.tasks import (
            discover_competitors_task,
            extract_features_parallel,
        )

        completed_job = self.queue_service.get_job(completed_job_id)
        if not completed_job or not completed_job.parent_job_id:
            return None

        parent_job = self.queue_service.get_job(completed_job.parent_job_id)
        if not parent_job or parent_job.job_type != JobType.FULL_WORKFLOW:
            return None

        # Determine next step based on completed job type
        if completed_job.job_type == JobType.PRODUCT_ANALYSIS:
            if completed_job.status == JobStatus.SUCCESS:
                # Next: Competitor Discovery
                discovery_job = self.queue_service.create_job(
                    job_type=JobType.COMPETITOR_DISCOVERY,
                    input_data={},
                    product_id=parent_job.product_id,
                    user_id=parent_job.user_id,
                    parent_job_id=parent_job.id,
                )
                self.db.commit()

                celery_result = discover_competitors_task.delay(discovery_job.id)
                self.queue_service.mark_queued(discovery_job.id, celery_result.id)
                self.db.commit()

                return discovery_job
            else:
                # Analysis failed - mark workflow as failed
                self.queue_service.mark_failure(
                    parent_job.id,
                    f"Product analysis failed: {completed_job.error_message}"
                )
                return None

        elif completed_job.job_type == JobType.COMPETITOR_DISCOVERY:
            if completed_job.status == JobStatus.SUCCESS:
                # Next: Feature Extraction (parallel)
                output = completed_job.output_data or {}
                competitor_ids = output.get('competitor_ids', [])

                if not competitor_ids:
                    # No competitors found - workflow complete
                    self.queue_service.mark_success(
                        parent_job.id,
                        {'message': 'No competitors discovered', 'competitors': 0}
                    )
                    return None

                # Create feature extraction job
                extraction_job = self.queue_service.create_job(
                    job_type=JobType.FEATURE_EXTRACTION,
                    input_data={'competitor_ids': competitor_ids, 'parallel': True},
                    product_id=parent_job.product_id,
                    user_id=parent_job.user_id,
                    parent_job_id=parent_job.id,
                )
                self.db.commit()

                celery_result = extract_features_parallel.delay(
                    extraction_job.id,
                    competitor_ids
                )
                self.queue_service.mark_queued(extraction_job.id, celery_result.id)
                self.db.commit()

                return extraction_job
            else:
                # Discovery failed - mark workflow as failed
                self.queue_service.mark_failure(
                    parent_job.id,
                    f"Competitor discovery failed: {completed_job.error_message}"
                )
                return None

        elif completed_job.job_type == JobType.FEATURE_EXTRACTION:
            # Feature extraction complete - workflow done
            if completed_job.status == JobStatus.SUCCESS:
                output = completed_job.output_data or {}
                self.queue_service.mark_success(
                    parent_job.id,
                    {
                        'message': 'Full analysis complete',
                        'competitors_processed': output.get('competitors_processed', 0),
                        'features_extracted': output.get('total_features_extracted', 0),
                    }
                )
            else:
                self.queue_service.mark_failure(
                    parent_job.id,
                    f"Feature extraction failed: {completed_job.error_message}"
                )
            return None

        return None

    def get_workflow_status(self, workflow_job_id: int) -> Dict[str, Any]:
        """
        Get detailed status of a workflow including all child jobs.

        Args:
            workflow_job_id: Parent workflow job ID

        Returns:
            Dictionary with workflow status and child job details
        """
        workflow_job = self.queue_service.get_job(workflow_job_id)
        if not workflow_job:
            raise WorkflowError(f"Workflow job {workflow_job_id} not found")

        # Get all child jobs
        child_jobs = self.db.query(QueueJob).filter(
            QueueJob.parent_job_id == workflow_job_id
        ).order_by(QueueJob.created_at.asc()).all()

        # Calculate overall progress
        completed_steps = sum(1 for j in child_jobs if j.status == JobStatus.SUCCESS)
        failed_steps = sum(1 for j in child_jobs if j.status == JobStatus.FAILURE)
        total_steps = len(child_jobs)

        if total_steps > 0:
            progress = (completed_steps / total_steps) * 100
        else:
            progress = 0

        return {
            'workflow': workflow_job.to_dict(),
            'steps': [j.to_dict() for j in child_jobs],
            'summary': {
                'total_steps': total_steps,
                'completed_steps': completed_steps,
                'failed_steps': failed_steps,
                'in_progress': total_steps - completed_steps - failed_steps,
                'progress_percent': progress,
            }
        }


def get_workflow_service(db: Session) -> WorkflowService:
    """Factory function to create a WorkflowService instance."""
    return WorkflowService(db)
