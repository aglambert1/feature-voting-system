"""
Phase 1 Queue Infrastructure Tests.

Tests the queue-based product analysis implementation including:
- QueueJob model and enums
- QueueService CRUD operations
- API endpoints for queue-based analysis
"""

import pytest
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.queue import QueueJob, JobType, JobStatus, JobPriority, generate_uuid
from app.services.queue_service import QueueService, JobNotFoundError, QueueServiceError


class TestQueueJobModel:
    """Test the QueueJob model."""

    def test_job_type_enum(self):
        """Test JobType enum values."""
        assert JobType.PRODUCT_ANALYSIS.value == "product_analysis"
        assert JobType.COMPETITOR_DISCOVERY.value == "competitor_discovery"
        assert JobType.FEATURE_EXTRACTION.value == "feature_extraction"

    def test_jobtype_pg_enum_names_do_not_collide(self):
        """Regression: the two JobType enums must map to DISTINCT Postgres types.

        queue.JobType and competitor_intelligence.JobType both used to derive
        the same native enum type name ``jobtype``, so create_all() only built
        one of them and every queue_jobs insert 500'd on Postgres. Each column
        now pins an explicit, distinct ``name=``. If anyone drops those names,
        the collision returns (and SQLite won't catch it) — this test will.
        """
        from app.models.queue import QueueJob
        from app.models.competitor_intelligence import ProductJob

        queue_enum = QueueJob.__table__.c.job_type.type
        jtbd_enum = ProductJob.__table__.c.job_type.type

        assert queue_enum.name == "queue_job_type"
        assert jtbd_enum.name == "jtbd_job_type"
        assert queue_enum.name != jtbd_enum.name

    def test_job_status_enum(self):
        """Test JobStatus enum values."""
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.QUEUED.value == "queued"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.SUCCESS.value == "success"
        assert JobStatus.FAILURE.value == "failure"

    def test_generate_uuid(self):
        """Test UUID generation."""
        uuid1 = generate_uuid()
        uuid2 = generate_uuid()
        assert uuid1 != uuid2
        assert len(uuid1) == 36

    def test_job_is_complete(self):
        """Test is_complete property."""
        job = QueueJob(job_type=JobType.PRODUCT_ANALYSIS)

        job.status = JobStatus.PENDING
        assert not job.is_complete

        job.status = JobStatus.RUNNING
        assert not job.is_complete

        job.status = JobStatus.SUCCESS
        assert job.is_complete

        job.status = JobStatus.FAILURE
        assert job.is_complete

    def test_job_to_dict(self):
        """Test to_dict method."""
        job = QueueJob(
            id=1,
            job_uuid="test-uuid",
            job_type=JobType.PRODUCT_ANALYSIS,
            status=JobStatus.PENDING,
            priority=JobPriority.NORMAL,
            product_id=42,
        )
        job.created_at = datetime(2024, 1, 1, 12, 0, 0)

        d = job.to_dict()
        assert d["id"] == 1
        assert d["job_uuid"] == "test-uuid"
        assert d["job_type"] == "product_analysis"
        assert d["status"] == "pending"
        assert d["priority"] == "normal"
        assert d["product_id"] == 42


class TestQueueService:
    """Test the QueueService."""

    @pytest.fixture
    def db_session(self):
        """Create a test database session."""
        from app.database import SessionLocal, init_db
        init_db()
        db = SessionLocal()
        yield db
        db.close()

    @pytest.fixture
    def queue_service(self, db_session):
        """Create a QueueService instance."""
        return QueueService(db_session)

    def test_create_job(self, queue_service, db_session):
        """Test creating a new job."""
        # Create a product and user so FK constraints are satisfied
        from app.models.competitor_intelligence import CIProduct
        from app.models.user import User, UserRole
        user = User(email="qtest@example.com", username="qtest", hashed_password="h", role=UserRole.VOTER)
        db_session.add(user)
        db_session.flush()
        product = CIProduct(product_name="Queue Test Product", product_description="For queue tests", created_by_user_id=user.id, status="active")
        db_session.add(product)
        db_session.commit()

        job = queue_service.create_job(
            job_type=JobType.PRODUCT_ANALYSIS,
            input_data={"product_name": "Test Product"},
            product_id=product.id,
            user_id=user.id,
        )

        assert job.id is not None
        assert job.job_uuid is not None
        assert job.job_type == JobType.PRODUCT_ANALYSIS
        assert job.status == JobStatus.PENDING
        assert job.input_data == {"product_name": "Test Product"}
        assert job.product_id == product.id
        assert job.user_id == user.id

    def test_queue_and_jtbd_jobtypes_persist_independently(self, db_session):
        """Regression: a QueueJob and a ProductJob with their respective
        JobType enums must both persist and read back, proving the two columns
        no longer share one native enum type."""
        from app.models.competitor_intelligence import (
            CIProduct, ProductJob, JobType as JTBDJobType, JobImportance,
        )
        from app.models.user import User, UserRole

        user = User(email="enumcollide@example.com", username="enumcollide",
                    hashed_password="h", role=UserRole.VOTER)
        db_session.add(user)
        db_session.flush()
        product = CIProduct(product_name="Enum Collision Product",
                            product_description="x", created_by_user_id=user.id,
                            status="active")
        db_session.add(product)
        db_session.commit()

        queue_job = QueueJob(job_type=JobType.PRODUCT_ANALYSIS,
                             status=JobStatus.PENDING, priority=JobPriority.NORMAL,
                             product_id=product.id, user_id=user.id)
        jtbd_job = ProductJob(product_id=product.id, job_id_key="j1",
                              job_type=JTBDJobType.FUNCTIONAL,
                              statement="When X, I want Y, so I can Z",
                              importance=JobImportance.MEDIUM)
        db_session.add_all([queue_job, jtbd_job])
        db_session.commit()
        db_session.refresh(queue_job)
        db_session.refresh(jtbd_job)

        assert queue_job.job_type == JobType.PRODUCT_ANALYSIS
        assert jtbd_job.job_type == JTBDJobType.FUNCTIONAL

    def test_get_job(self, queue_service, db_session):
        """Test retrieving a job by ID."""
        created = queue_service.create_job(
            job_type=JobType.PRODUCT_ANALYSIS,
            input_data={},
        )

        found = queue_service.get_job(created.id)
        assert found is not None
        assert found.id == created.id

    def test_get_job_by_uuid(self, queue_service, db_session):
        """Test retrieving a job by UUID."""
        created = queue_service.create_job(
            job_type=JobType.PRODUCT_ANALYSIS,
            input_data={},
        )

        found = queue_service.get_job_by_uuid(created.job_uuid)
        assert found is not None
        assert found.job_uuid == created.job_uuid

    def test_update_job_status(self, queue_service, db_session):
        """Test updating job status."""
        job = queue_service.create_job(
            job_type=JobType.PRODUCT_ANALYSIS,
            input_data={},
        )

        updated = queue_service.update_job_status(
            job_id=job.id,
            status=JobStatus.RUNNING,
            progress_percent=50.0,
            progress_message="Processing...",
        )

        assert updated.status == JobStatus.RUNNING
        assert updated.progress_percent == 50.0
        assert updated.progress_message == "Processing..."
        assert updated.started_at is not None

    def test_mark_success(self, queue_service, db_session):
        """Test marking a job as successful."""
        job = queue_service.create_job(
            job_type=JobType.PRODUCT_ANALYSIS,
            input_data={},
        )
        queue_service.mark_running(job.id)

        updated = queue_service.mark_success(
            job_id=job.id,
            output_data={"result": "completed"},
        )

        assert updated.status == JobStatus.SUCCESS
        assert updated.progress_percent == 100.0
        assert updated.output_data == {"result": "completed"}
        assert updated.completed_at is not None

    def test_mark_failure(self, queue_service, db_session):
        """Test marking a job as failed."""
        job = queue_service.create_job(
            job_type=JobType.PRODUCT_ANALYSIS,
            input_data={},
        )

        updated = queue_service.mark_failure(
            job_id=job.id,
            error_message="Something went wrong",
            error_traceback="Traceback...",
        )

        assert updated.status == JobStatus.FAILURE
        assert updated.error_message == "Something went wrong"
        assert updated.error_traceback == "Traceback..."
        assert updated.retry_count == 1

    def test_cancel_job(self, queue_service, db_session):
        """Test cancelling a job."""
        job = queue_service.create_job(
            job_type=JobType.PRODUCT_ANALYSIS,
            input_data={},
        )

        cancelled = queue_service.cancel_job(job.id)

        assert cancelled.status == JobStatus.CANCELLED
        assert cancelled.completed_at is not None

    def test_cancel_completed_job_fails(self, queue_service, db_session):
        """Test that cancelling a completed job raises error."""
        job = queue_service.create_job(
            job_type=JobType.PRODUCT_ANALYSIS,
            input_data={},
        )
        queue_service.mark_success(job.id)

        with pytest.raises(QueueServiceError):
            queue_service.cancel_job(job.id)

    def test_get_active_jobs(self, queue_service, db_session):
        """Test getting active jobs."""
        # Create a real product so FK constraints are satisfied
        from app.models.competitor_intelligence import CIProduct
        from app.models.user import User, UserRole
        user = db_session.query(User).filter(User.username == "qtest").first()
        if not user:
            user = User(email="qtest2@example.com", username="qtest2", hashed_password="h", role=UserRole.VOTER)
            db_session.add(user)
            db_session.flush()
        product = CIProduct(product_name="Active Jobs Test Product", product_description="For active jobs test", created_by_user_id=user.id, status="active")
        db_session.add(product)
        db_session.commit()
        test_product_id = product.id

        # Create jobs with different statuses
        pending = queue_service.create_job(
            job_type=JobType.PRODUCT_ANALYSIS,
            input_data={},
            product_id=test_product_id,
        )
        running = queue_service.create_job(
            job_type=JobType.PRODUCT_ANALYSIS,
            input_data={},
            product_id=test_product_id,
        )
        queue_service.mark_running(running.id)

        completed = queue_service.create_job(
            job_type=JobType.PRODUCT_ANALYSIS,
            input_data={},
            product_id=test_product_id,
        )
        queue_service.mark_success(completed.id)

        # Get active jobs
        active = queue_service.get_active_jobs(product_id=test_product_id)

        assert len(active) == 2
        active_ids = [j.id for j in active]
        assert pending.id in active_ids
        assert running.id in active_ids
        assert completed.id not in active_ids


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
