"""
Phase 2 Workflow and Queue Task Tests.

Tests the workflow orchestration and new queue tasks:
- WorkflowService for job chaining
- Workflow status tracking
- Job continuation logic

Note: Tests that require actual Celery task execution (Redis connection)
are marked to be skipped if Redis is not available.
"""

import pytest
import uuid
from datetime import datetime
from unittest.mock import patch, MagicMock, PropertyMock
from sqlalchemy.orm import Session

from app.models.queue import QueueJob, JobType, JobStatus, JobPriority
from app.models.competitor_intelligence import CIProduct
from app.services.queue_service import QueueService
from app.queue.workflows import WorkflowService, WorkflowError


def unique_name(prefix="Test Product"):
    """Generate a unique product name for testing."""
    return f"{prefix} {uuid.uuid4().hex[:8]}"


class TestWorkflowServiceBasic:
    """Test basic WorkflowService functionality without Celery."""

    @pytest.fixture
    def db_session(self):
        """Create a test database session."""
        from app.database import SessionLocal, init_db
        init_db()
        db = SessionLocal()
        yield db
        db.close()

    @pytest.fixture
    def test_product(self, db_session):
        """Create a test product."""
        product = CIProduct(
            product_name=unique_name(),
            product_description="A test product for workflow testing",
            created_by_user_id=1,
            status="active",
            structured_product_data={
                "product_name": "Test Product",
                "product_category": "Testing Tools",
                "competitor_search_keywords": ["testing", "qa"]
            }
        )
        db_session.add(product)
        db_session.commit()
        db_session.refresh(product)
        return product

    @pytest.fixture
    def workflow_service(self, db_session):
        """Create a WorkflowService instance."""
        return WorkflowService(db_session)

    @pytest.fixture
    def queue_service(self, db_session):
        """Create a QueueService instance."""
        return QueueService(db_session)

    def test_start_workflow_product_not_found(self, workflow_service):
        """Test starting workflow for non-existent product."""
        with pytest.raises(WorkflowError, match="not found"):
            workflow_service.start_full_analysis_workflow(
                product_id=9999,
                user_id=1
            )

    def test_start_workflow_skip_analysis_without_data(self, workflow_service, db_session):
        """Test skipping analysis when product not yet analyzed."""
        # Create product without structured_product_data
        product = CIProduct(
            product_name=unique_name("Unanalyzed"),
            product_description="Not analyzed yet",
            created_by_user_id=1,
            status="active",
            structured_product_data=None
        )
        db_session.add(product)
        db_session.commit()

        with pytest.raises(WorkflowError, match="Cannot skip analysis"):
            workflow_service.start_full_analysis_workflow(
                product_id=product.id,
                user_id=1,
                skip_analysis=True
            )

    def test_get_workflow_status(self, workflow_service, queue_service, test_product, db_session):
        """Test getting workflow status."""
        # Create a workflow job manually
        workflow_job = queue_service.create_job(
            job_type=JobType.FULL_WORKFLOW,
            input_data={'skip_analysis': True},
            product_id=test_product.id,
            user_id=1
        )

        # Create child jobs
        child1 = queue_service.create_job(
            job_type=JobType.COMPETITOR_DISCOVERY,
            input_data={},
            product_id=test_product.id,
            user_id=1,
            parent_job_id=workflow_job.id
        )
        queue_service.mark_success(child1.id)

        child2 = queue_service.create_job(
            job_type=JobType.FEATURE_EXTRACTION,
            input_data={},
            product_id=test_product.id,
            user_id=1,
            parent_job_id=workflow_job.id
        )

        db_session.commit()

        status = workflow_service.get_workflow_status(workflow_job.id)

        assert status['workflow']['id'] == workflow_job.id
        assert len(status['steps']) == 2
        assert status['summary']['total_steps'] == 2
        assert status['summary']['completed_steps'] == 1
        assert status['summary']['progress_percent'] == 50.0

    def test_get_workflow_status_not_found(self, workflow_service):
        """Test getting status for non-existent workflow."""
        with pytest.raises(WorkflowError, match="not found"):
            workflow_service.get_workflow_status(9999)

    def test_get_workflow_status_empty_steps(self, workflow_service, queue_service, test_product, db_session):
        """Test workflow status with no child jobs."""
        workflow_job = queue_service.create_job(
            job_type=JobType.FULL_WORKFLOW,
            input_data={},
            product_id=test_product.id,
            user_id=1
        )
        db_session.commit()

        status = workflow_service.get_workflow_status(workflow_job.id)

        assert status['workflow']['id'] == workflow_job.id
        assert len(status['steps']) == 0
        assert status['summary']['total_steps'] == 0
        assert status['summary']['progress_percent'] == 0


class TestContinueWorkflow:
    """Test workflow continuation logic."""

    @pytest.fixture
    def db_session(self):
        """Create a test database session."""
        from app.database import SessionLocal, init_db
        init_db()
        db = SessionLocal()
        yield db
        db.close()

    @pytest.fixture
    def test_product(self, db_session):
        """Create a test product."""
        product = CIProduct(
            product_name=unique_name("Continue Test"),
            product_description="A test product",
            created_by_user_id=1,
            status="active",
            structured_product_data={"product_name": "Test"}
        )
        db_session.add(product)
        db_session.commit()
        db_session.refresh(product)
        return product

    @pytest.fixture
    def workflow_service(self, db_session):
        """Create a WorkflowService instance."""
        return WorkflowService(db_session)

    @pytest.fixture
    def queue_service(self, db_session):
        """Create a QueueService instance."""
        return QueueService(db_session)

    def test_continue_workflow_no_parent(self, workflow_service, queue_service, db_session):
        """Test continuing workflow with job that has no parent."""
        job = queue_service.create_job(
            job_type=JobType.PRODUCT_ANALYSIS,
            input_data={}
        )
        queue_service.mark_success(job.id)
        db_session.commit()

        result = workflow_service.continue_workflow(job.id)
        assert result is None

    def test_continue_workflow_non_workflow_parent(self, workflow_service, queue_service, test_product, db_session):
        """Test continuing workflow with non-workflow parent."""
        # Create a parent that's not a workflow
        parent_job = queue_service.create_job(
            job_type=JobType.PRODUCT_ANALYSIS,
            input_data={},
            product_id=test_product.id,
            user_id=1
        )

        child_job = queue_service.create_job(
            job_type=JobType.COMPETITOR_DISCOVERY,
            input_data={},
            product_id=test_product.id,
            user_id=1,
            parent_job_id=parent_job.id
        )
        queue_service.mark_success(child_job.id)
        db_session.commit()

        result = workflow_service.continue_workflow(child_job.id)
        assert result is None

    def test_continue_after_analysis_failure(self, workflow_service, queue_service, test_product, db_session):
        """Test workflow stops when analysis fails."""
        # Create parent workflow
        workflow_job = queue_service.create_job(
            job_type=JobType.FULL_WORKFLOW,
            input_data={},
            product_id=test_product.id,
            user_id=1
        )

        # Create and fail analysis job
        analysis_job = queue_service.create_job(
            job_type=JobType.PRODUCT_ANALYSIS,
            input_data={},
            product_id=test_product.id,
            user_id=1,
            parent_job_id=workflow_job.id
        )
        queue_service.mark_failure(analysis_job.id, "Analysis failed")
        db_session.commit()

        # Continue workflow
        next_job = workflow_service.continue_workflow(analysis_job.id)

        # No next job, parent should be failed
        assert next_job is None

        # Refresh parent job
        db_session.refresh(workflow_job)
        assert workflow_job.status == JobStatus.FAILURE

    def test_continue_after_discovery_failure(self, workflow_service, queue_service, test_product, db_session):
        """Test workflow stops when discovery fails."""
        # Create parent workflow
        workflow_job = queue_service.create_job(
            job_type=JobType.FULL_WORKFLOW,
            input_data={},
            product_id=test_product.id,
            user_id=1
        )

        # Create and fail discovery job
        discovery_job = queue_service.create_job(
            job_type=JobType.COMPETITOR_DISCOVERY,
            input_data={},
            product_id=test_product.id,
            user_id=1,
            parent_job_id=workflow_job.id
        )
        queue_service.mark_failure(discovery_job.id, "Discovery failed")
        db_session.commit()

        # Continue workflow
        next_job = workflow_service.continue_workflow(discovery_job.id)

        assert next_job is None

        db_session.refresh(workflow_job)
        assert workflow_job.status == JobStatus.FAILURE

    def test_continue_after_discovery_no_competitors(self, workflow_service, queue_service, test_product, db_session):
        """Test workflow completes when no competitors found."""
        # Create parent workflow
        workflow_job = queue_service.create_job(
            job_type=JobType.FULL_WORKFLOW,
            input_data={},
            product_id=test_product.id,
            user_id=1
        )

        # Create and complete discovery job with no competitors
        discovery_job = queue_service.create_job(
            job_type=JobType.COMPETITOR_DISCOVERY,
            input_data={},
            product_id=test_product.id,
            user_id=1,
            parent_job_id=workflow_job.id
        )
        queue_service.mark_success(
            discovery_job.id,
            output_data={'competitor_ids': []}
        )
        db_session.commit()

        # Continue workflow
        next_job = workflow_service.continue_workflow(discovery_job.id)

        # No next job, workflow should be complete
        assert next_job is None

        # Refresh parent job
        db_session.refresh(workflow_job)
        assert workflow_job.status == JobStatus.SUCCESS

    def test_continue_after_extraction_success(self, workflow_service, queue_service, test_product, db_session):
        """Test workflow completes after feature extraction."""
        # Create parent workflow
        workflow_job = queue_service.create_job(
            job_type=JobType.FULL_WORKFLOW,
            input_data={},
            product_id=test_product.id,
            user_id=1
        )

        # Create and complete extraction job
        extraction_job = queue_service.create_job(
            job_type=JobType.FEATURE_EXTRACTION,
            input_data={},
            product_id=test_product.id,
            user_id=1,
            parent_job_id=workflow_job.id
        )
        queue_service.mark_success(
            extraction_job.id,
            output_data={'competitors_processed': 3, 'total_features_extracted': 15}
        )
        db_session.commit()

        # Continue workflow
        next_job = workflow_service.continue_workflow(extraction_job.id)

        # No next job, workflow should be complete
        assert next_job is None

        # Refresh parent job
        db_session.refresh(workflow_job)
        assert workflow_job.status == JobStatus.SUCCESS
        assert workflow_job.output_data['competitors_processed'] == 3

    def test_continue_after_extraction_failure(self, workflow_service, queue_service, test_product, db_session):
        """Test workflow fails when extraction fails."""
        # Create parent workflow
        workflow_job = queue_service.create_job(
            job_type=JobType.FULL_WORKFLOW,
            input_data={},
            product_id=test_product.id,
            user_id=1
        )

        # Create and fail extraction job
        extraction_job = queue_service.create_job(
            job_type=JobType.FEATURE_EXTRACTION,
            input_data={},
            product_id=test_product.id,
            user_id=1,
            parent_job_id=workflow_job.id
        )
        queue_service.mark_failure(extraction_job.id, "Extraction failed")
        db_session.commit()

        # Continue workflow
        next_job = workflow_service.continue_workflow(extraction_job.id)

        assert next_job is None

        db_session.refresh(workflow_job)
        assert workflow_job.status == JobStatus.FAILURE


class TestWorkflowWithMockedTasks:
    """Tests that require mocked Celery tasks."""

    @pytest.fixture
    def db_session(self):
        """Create a test database session."""
        from app.database import SessionLocal, init_db
        init_db()
        db = SessionLocal()
        yield db
        db.close()

    @pytest.fixture
    def test_product(self, db_session):
        """Create a test product."""
        product = CIProduct(
            product_name=unique_name("Task Test"),
            product_description="A test product",
            created_by_user_id=1,
            status="active",
            structured_product_data={"product_name": "Test"}
        )
        db_session.add(product)
        db_session.commit()
        db_session.refresh(product)
        return product

    @pytest.fixture
    def workflow_service(self, db_session):
        """Create a WorkflowService instance."""
        return WorkflowService(db_session)

    @pytest.fixture
    def queue_service(self, db_session):
        """Create a QueueService instance."""
        return QueueService(db_session)

    def test_start_workflow_skip_analysis_queues_discovery(self, workflow_service, queue_service, test_product, db_session):
        """Test that starting workflow with skip_analysis queues discovery task."""
        # Patch at the tasks module level since that's where they're imported from
        with patch('app.queue.tasks.discover_competitors_task') as mock_discover:
            mock_result = MagicMock()
            mock_result.id = f"mock-celery-{uuid.uuid4().hex[:8]}"
            mock_discover.delay.return_value = mock_result

            workflow_job = workflow_service.start_full_analysis_workflow(
                product_id=test_product.id,
                user_id=1,
                skip_analysis=True
            )

            assert workflow_job.job_type == JobType.FULL_WORKFLOW
            assert workflow_job.product_id == test_product.id
            mock_discover.delay.assert_called_once()

    def test_start_workflow_queues_analysis(self, workflow_service, queue_service, db_session):
        """Test that starting workflow without skip_analysis queues analysis task."""
        # Create product without analysis
        product = CIProduct(
            product_name=unique_name("New Product"),
            product_description="Needs analysis - this is more than 10 characters for validation",
            created_by_user_id=1,
            status="active",
            structured_product_data=None
        )
        db_session.add(product)
        db_session.commit()

        with patch('app.queue.tasks.analyze_product_task') as mock_analyze:
            mock_result = MagicMock()
            mock_result.id = f"mock-celery-{uuid.uuid4().hex[:8]}"
            mock_analyze.delay.return_value = mock_result

            workflow_job = workflow_service.start_full_analysis_workflow(
                product_id=product.id,
                user_id=1,
                skip_analysis=False
            )

            assert workflow_job.job_type == JobType.FULL_WORKFLOW
            mock_analyze.delay.assert_called_once()

    def test_continue_after_analysis_queues_discovery(self, workflow_service, queue_service, test_product, db_session):
        """Test continuing workflow after analysis queues discovery."""
        with patch('app.queue.tasks.discover_competitors_task') as mock_discover:
            mock_result = MagicMock()
            mock_result.id = f"mock-celery-{uuid.uuid4().hex[:8]}"
            mock_discover.delay.return_value = mock_result

            # Create parent workflow
            workflow_job = queue_service.create_job(
                job_type=JobType.FULL_WORKFLOW,
                input_data={},
                product_id=test_product.id,
                user_id=1
            )

            # Create and complete analysis job
            analysis_job = queue_service.create_job(
                job_type=JobType.PRODUCT_ANALYSIS,
                input_data={},
                product_id=test_product.id,
                user_id=1,
                parent_job_id=workflow_job.id
            )
            queue_service.mark_success(analysis_job.id)
            db_session.commit()

            # Continue workflow
            next_job = workflow_service.continue_workflow(analysis_job.id)

            assert next_job is not None
            assert next_job.job_type == JobType.COMPETITOR_DISCOVERY
            mock_discover.delay.assert_called_once()

    def test_continue_after_discovery_queues_extraction(self, workflow_service, queue_service, test_product, db_session):
        """Test continuing workflow after discovery queues extraction."""
        with patch('app.queue.tasks.extract_features_parallel') as mock_extract:
            mock_result = MagicMock()
            mock_result.id = f"mock-celery-{uuid.uuid4().hex[:8]}"
            mock_extract.delay.return_value = mock_result

            # Create parent workflow
            workflow_job = queue_service.create_job(
                job_type=JobType.FULL_WORKFLOW,
                input_data={},
                product_id=test_product.id,
                user_id=1
            )

            # Create and complete discovery job with competitor IDs
            discovery_job = queue_service.create_job(
                job_type=JobType.COMPETITOR_DISCOVERY,
                input_data={},
                product_id=test_product.id,
                user_id=1,
                parent_job_id=workflow_job.id
            )
            queue_service.mark_success(
                discovery_job.id,
                output_data={'competitor_ids': [1, 2, 3]}
            )
            db_session.commit()

            # Continue workflow
            next_job = workflow_service.continue_workflow(discovery_job.id)

            assert next_job is not None
            assert next_job.job_type == JobType.FEATURE_EXTRACTION
            mock_extract.delay.assert_called_once()


class TestQueueJobModel:
    """Test QueueJob model additions for Phase 2."""

    def test_job_type_has_workflow(self):
        """Test that FULL_WORKFLOW job type exists."""
        assert JobType.FULL_WORKFLOW.value == "full_workflow"

    def test_job_type_has_competitor_discovery(self):
        """Test that COMPETITOR_DISCOVERY job type exists."""
        assert JobType.COMPETITOR_DISCOVERY.value == "competitor_discovery"

    def test_job_type_has_feature_extraction(self):
        """Test that FEATURE_EXTRACTION job type exists."""
        assert JobType.FEATURE_EXTRACTION.value == "feature_extraction"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
