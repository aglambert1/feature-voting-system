"""
Queue Job models for background task tracking.

This module defines the database models for tracking Celery task
execution, status, and results.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey,
    JSON, Enum, Float
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
import uuid

from app.database import Base


class JobType(str, enum.Enum):
    """
    Types of background jobs that can be queued.

    Phase 1:
    - PRODUCT_ANALYSIS: Analyze product description

    Phase 2:
    - COMPETITOR_DISCOVERY: Discover competitors
    - FEATURE_EXTRACTION: Extract features from competitor
    - FULL_WORKFLOW: Complete analysis workflow

    Phase 3+:
    - IDEA_NORMALIZATION: Normalize ideas from various sources
    - IDEA_TRIAGE: Auto-categorize and dedupe ideas
    - COMPETITIVE_MONITORING: Scheduled monitoring
    - REPORT_GENERATION: Generate reports

    Agent-Centric Architecture:
    - DEEP_ANALYSIS: Per-competitor deep analysis
    - SCHEDULED_DEEP_ANALYSIS: Orchestrates multiple deep_analysis jobs
    - FEATURE_EXTRACTION_ONLY: Feature extraction only
    - FEATURE_CLUSTERING: Run feature clustering across competitors
    - INTENSITY_IDEA_GENERATION: Generate ideas from high-intensity clusters

    Two-Step Competitive Analysis (New):
    - FUNCTIONAL_AUDIT: Per-competitor functional feature audit
    - LANDSCAPE_SYNTHESIS: Cross-competitor landscape opportunity synthesis

    DEPRECATED (kept for backwards compatibility):
    - STRATEGIC_ANALYSIS_ONLY, PRICING_ANALYSIS, POSITIONING_ANALYSIS,
    - CHANGES_TRACKING, MOMENTUM_ANALYSIS, FINANCIALS_ANALYSIS
    """
    PRODUCT_ANALYSIS = "product_analysis"
    COMPETITOR_DISCOVERY = "competitor_discovery"
    FEATURE_EXTRACTION = "feature_extraction"
    FULL_WORKFLOW = "full_workflow"
    IDEA_NORMALIZATION = "idea_normalization"
    IDEA_TRIAGE = "idea_triage"
    COMPETITIVE_MONITORING = "competitive_monitoring"
    REPORT_GENERATION = "report_generation"

    # Agent-Centric Architecture job types
    DEEP_ANALYSIS = "deep_analysis"
    SCHEDULED_DEEP_ANALYSIS = "scheduled_deep_analysis"  # Orchestrates multiple deep_analysis jobs
    FEATURE_EXTRACTION_ONLY = "feature_extraction_only"
    FEATURE_CLUSTERING = "feature_clustering"
    INTENSITY_IDEA_GENERATION = "intensity_idea_generation"

    # New Competitive Reports job types (two-step analysis)
    FUNCTIONAL_AUDIT = "functional_audit"  # Per-competitor functional audit
    LANDSCAPE_SYNTHESIS = "landscape_synthesis"  # Cross-competitor landscape synthesis

    # DEPRECATED: These job types are no longer used in the new two-step analysis system
    # Kept for backwards compatibility with existing job records
    STRATEGIC_ANALYSIS_ONLY = "strategic_analysis_only"  # DEPRECATED
    PRICING_ANALYSIS = "pricing_analysis"  # DEPRECATED
    POSITIONING_ANALYSIS = "positioning_analysis"  # DEPRECATED
    CHANGES_TRACKING = "changes_tracking"  # DEPRECATED
    MOMENTUM_ANALYSIS = "momentum_analysis"  # DEPRECATED
    FINANCIALS_ANALYSIS = "financials_analysis"  # DEPRECATED


class JobStatus(str, enum.Enum):
    """
    Status of a queued job.

    Lifecycle:
    PENDING -> QUEUED -> RUNNING -> SUCCESS/FAILURE/CANCELLED
    """
    PENDING = "pending"      # Created but not yet queued
    QUEUED = "queued"        # Sent to Celery
    RUNNING = "running"      # Being processed by worker
    SUCCESS = "success"      # Completed successfully
    FAILURE = "failure"      # Failed with error
    CANCELLED = "cancelled"  # Cancelled by user
    RETRYING = "retrying"    # Failed, being retried


class JobPriority(str, enum.Enum):
    """Job priority levels for queue ordering."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


def generate_uuid():
    """Generate a UUID string for job IDs."""
    return str(uuid.uuid4())


class QueueJob(Base):
    """
    Central job tracking for all background tasks.

    Stores job metadata, status, progress, and results.
    Links to Celery task IDs for status synchronization.
    """
    __tablename__ = "queue_jobs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_uuid = Column(String(36), unique=True, nullable=False, default=generate_uuid, index=True)

    # Job type and status
    job_type = Column(Enum(JobType), nullable=False, index=True)
    status = Column(Enum(JobStatus), nullable=False, default=JobStatus.PENDING, index=True)
    priority = Column(Enum(JobPriority), nullable=False, default=JobPriority.NORMAL)

    # Celery task tracking
    celery_task_id = Column(String(255), unique=True, index=True)

    # Input and output data
    input_data = Column(JSON)
    output_data = Column(JSON)

    # Progress tracking
    progress_percent = Column(Float, default=0.0)
    progress_message = Column(String(500))

    # Error handling
    error_message = Column(Text)
    error_traceback = Column(Text)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    # Timing
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    queued_at = Column(DateTime)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    # Relationships
    product_id = Column(Integer, ForeignKey("ci_products.id", ondelete="SET NULL"), index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    parent_job_id = Column(Integer, ForeignKey("queue_jobs.id", ondelete="SET NULL"), index=True)

    # Self-referential relationship for job chaining
    child_jobs = relationship(
        "QueueJob",
        backref="parent_job",
        remote_side=[id],
        foreign_keys=[parent_job_id]
    )

    def __repr__(self):
        return f"<QueueJob(id={self.id}, type={self.job_type}, status={self.status})>"

    @property
    def is_complete(self) -> bool:
        """Check if job has finished (success or failure)."""
        return self.status in (JobStatus.SUCCESS, JobStatus.FAILURE, JobStatus.CANCELLED)

    @property
    def is_running(self) -> bool:
        """Check if job is currently executing."""
        return self.status == JobStatus.RUNNING

    @property
    def duration_seconds(self) -> float | None:
        """Calculate job duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (datetime.utcnow() - self.started_at).total_seconds()
        return None

    def to_dict(self) -> dict:
        """Convert job to dictionary for API responses."""
        return {
            "id": self.id,
            "job_uuid": self.job_uuid,
            "job_type": self.job_type.value if self.job_type else None,
            "status": self.status.value if self.status else None,
            "priority": self.priority.value if self.priority else None,
            "progress_percent": self.progress_percent,
            "progress_message": self.progress_message,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "queued_at": self.queued_at.isoformat() if self.queued_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "product_id": self.product_id,
            "user_id": self.user_id,
            "parent_job_id": self.parent_job_id,
            "output_data": self.output_data,
        }
