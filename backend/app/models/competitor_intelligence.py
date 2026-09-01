"""
Competitor Intelligence models for database.

This defines the database structure for the CI system that analyzes
competitor products and generates feature ideas.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, ForeignKey,
    DECIMAL, UniqueConstraint, JSON, Enum
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class ProductPermissionLevel(str, enum.Enum):
    """
    Permission levels for product access.

    - VIEW: Can view product and analyses
    - EDIT: Can modify product, run analyses
    - OWNER: Can delete product, manage permissions
    """
    VIEW = "view"
    EDIT = "edit"
    OWNER = "owner"


class SessionStage(str, enum.Enum):
    """
    Stages of an analysis session lifecycle.

    - PRODUCT_ANALYSIS: Stage 1 - Product analyzed
    - COMPETITOR_DISCOVERY: Stage 2 - Competitors discovered
    - FEATURE_EXTRACTION: Stage 3 - Features extracted
    - IDEA_GENERATION: Stage 4 - Ideas generated
    """
    PRODUCT_ANALYSIS = "product_analysis"
    COMPETITOR_DISCOVERY = "competitor_discovery"
    FEATURE_EXTRACTION = "feature_extraction"
    IDEA_GENERATION = "idea_generation"


class CIProduct(Base):
    """
    Product being analyzed for competitive intelligence.

    Products are shared team resources with permission-based access.
    Audit fields track who created/modified the product, but ownership
    is managed through the ProductPermission table.
    """
    __tablename__ = "ci_products"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_name = Column(String(255), nullable=False, unique=True, index=True)
    product_description = Column(Text, nullable=False)
    product_category = Column(String(100))
    structured_product_data = Column(JSON)

    # Source information - tracks where description came from
    product_source_type = Column(String(50), default="text")
    product_source_data = Column(JSON)  # Store {"url": "..."} or {"filename": "..."}

    # Audit tracking (who did what, not ownership)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    last_modified_by_user_id = Column(Integer, ForeignKey("users.id"), index=True)
    last_analyzed_by_user_id = Column(Integer, ForeignKey("users.id"), index=True)

    # Analysis versioning
    analysis_version = Column(Integer, default=0)
    last_analyzed_at = Column(DateTime(timezone=True))
    analysis_count = Column(Integer, default=0)

    # Source change tracking
    last_source_hash = Column(String(64))

    # Idea Triage Automation Settings
    idea_triage_auto_enabled = Column(Boolean, default=False, nullable=False)
    idea_triage_auto_threshold = Column(DECIMAL(3, 2), default=0.90, nullable=False)  # Confidence threshold (0.00-1.00)

    # Status visibility configuration - maps idea status to is_active
    # Default: only ACCEPTED is visible. null = use defaults
    # Example: {"pending": false, "accepted": true, "needs_review": false, ...}
    status_visibility_config = Column(JSON, nullable=True)

    # Configurable scoring weights for synthesis priority scoring
    # null = use defaults from scoring_defaults.py
    scoring_weights = Column(JSON, nullable=True)

    # JTBD Job Map - the analytical lens for competitive analysis
    target_customer_profile = Column(JSON, nullable=True)  # Structured persona
    job_map = Column(JSON, nullable=True)  # Hierarchical JTBD map
    job_map_version = Column(Integer, default=0, nullable=False)
    job_map_last_updated = Column(DateTime(timezone=True), nullable=True)
    pending_job_map = Column(JSON, nullable=True)  # LLM-generated map awaiting PM review
    previous_job_map = Column(JSON, nullable=True)  # Last committed map before most recent change

    status = Column(String(50), default="active", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    sessions = relationship("CompetitorAnalysisSession", back_populates="product", cascade="all, delete-orphan")
    competitors = relationship("ProductCompetitor", back_populates="product", cascade="all, delete-orphan")
    agent_logs = relationship("AgentExecutionLog", back_populates="product")
    permissions = relationship("ProductPermission", back_populates="product", cascade="all, delete-orphan")
    analysis_history = relationship("ProductAnalysisHistory", back_populates="product", cascade="all, delete-orphan")
    competitive_agent_config = relationship("CompetitiveAgentConfig", back_populates="product", uselist=False, cascade="all, delete-orphan")
    jobs = relationship("ProductJob", back_populates="product", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<CIProduct(id={self.id}, name='{self.product_name}', created_by={self.created_by_user_id})>"

    def get_is_active_for_status(self, status: "IdeaStatus") -> bool:
        """
        Return is_active value for a status based on product config.

        Uses product-specific visibility config if set, otherwise falls back
        to default visibility mapping.

        Args:
            status: The IdeaStatus enum value

        Returns:
            True if ideas with this status should be visible (is_active=True)
        """
        from app.models.idea import DEFAULT_STATUS_VISIBILITY

        # Get status value as string
        status_value = status.value if hasattr(status, 'value') else str(status)

        # Check product-specific config first
        if self.status_visibility_config:
            if status_value in self.status_visibility_config:
                return self.status_visibility_config[status_value]

        # Fall back to default visibility
        return DEFAULT_STATUS_VISIBILITY.get(status, False)


class JobType(str, enum.Enum):
    FUNCTIONAL = "functional"
    EMOTIONAL = "emotional"
    SOCIAL = "social"


class JobImportance(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# How a job entered the map. Plain strings rather than a SQLAlchemy Enum, matching
# ProductJob.status alongside them — and avoiding the PG-stores-the-uppercase-NAME
# trap that has bitten enum migrations in this codebase before.
JOB_PROVENANCE_PRODUCT = "product_derived"      # extracted from the product description
JOB_PROVENANCE_SIGNAL = "signal_derived"        # from an idea/evidence/theme matching no job
JOB_PROVENANCE_COMPETITOR = "competitor_derived"  # from a competitor capability fitting no job
JOB_PROVENANCE_PM = "pm_authored"               # written by hand

JOB_PROVENANCE_TYPES = {
    JOB_PROVENANCE_PRODUCT,
    JOB_PROVENANCE_SIGNAL,
    JOB_PROVENANCE_COMPETITOR,
    JOB_PROVENANCE_PM,
}

# Provenance types that are independent of the product's own description. A map built
# only from JOB_PROVENANCE_PRODUCT entries, with nothing else supporting it, is circular:
# the jobs were derived from what the product already does, which makes high coverage
# scores near-tautological and renders unserved jobs invisible.
JOB_PROVENANCE_INDEPENDENT = {
    JOB_PROVENANCE_SIGNAL,
    JOB_PROVENANCE_COMPETITOR,
    JOB_PROVENANCE_PM,
}

# Whether a PM has reviewed the job's wording.
JOB_UNVALIDATED = "unvalidated"
JOB_VALIDATED = "validated"
JOB_EDITED = "edited"

# Whether we intend to serve the job. Out-of-target jobs stay in the map.
JOB_IN_TARGET = "in_target"
JOB_OUT_OF_TARGET = "out_of_target"


class ProductJob(Base):
    """
    Individual job from a product's JTBD job map.

    Separate table enables embedding-based search and FK references
    from other models (ideas, themes, evidence).
    """
    __tablename__ = "product_jobs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("ci_products.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id_key = Column(String(50), nullable=False)  # "j1", "je1", "js1" etc.
    job_type = Column(Enum(JobType, name="jtbd_job_type"), nullable=False)
    statement = Column(Text, nullable=False)  # "When [situation], I want to [action], so I can [outcome]"
    desired_outcomes = Column(JSON, nullable=True)  # List of outcome statements
    importance = Column(Enum(JobImportance), nullable=False, default=JobImportance.MEDIUM)
    statement_embedding = Column(JSON, nullable=True)  # 1024-dim Voyage AI embedding

    # How this job entered the map: {"type": ..., "source_ref": ..., "added_at": ...}
    # Type is one of JOB_PROVENANCE_TYPES. Null means unknown (predates tracking).
    #
    # This records ENTRY only, and is deliberately not a growing list. The sources
    # that establish a job is *real* are derivable — Evidence, Idea, WinLossTheme and
    # SupportTheme all carry job_id_key, so corroboration is a query that self-updates
    # as signals arrive (see app.services.job_provenance). Entry earns its own column
    # because it is the only thing that measures circularity: a job extracted from the
    # product's own description, with nothing independent supporting it, is the case
    # worth flagging — and linkage cannot tell you that, because linkage does not know
    # where a job came from.
    provenance = Column(JSON, nullable=True)

    # Whether a PM has reviewed the wording. Corroboration shows a job is real; it says
    # nothing about whether the statement is worded correctly, which is what this tracks.
    # Optional by design — a PM may accept the map without ever reviewing it.
    validation_state = Column(String(50), nullable=False, default=JOB_UNVALIDATED, server_default=JOB_UNVALIDATED)

    # Whether the job is one we intend to serve. Jobs we deliberately don't serve still
    # belong in the map — it models the customer's jobs, not our coverage — but without
    # somewhere to say so they read as glaring gaps, and a PM would reject exactly the
    # competitor- and signal-derived suggestions that make the map less circular.
    serve_intent = Column(String(50), nullable=False, default=JOB_IN_TARGET, server_default=JOB_IN_TARGET)

    # When the statement itself last changed. Distinct from updated_at, which moves on
    # any field: a restatement invalidates prior reviews and makes positions
    # incomparable across report versions, so it needs its own timestamp.
    statement_updated_at = Column(DateTime(timezone=True), nullable=True)

    status = Column(String(50), default="active", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    product = relationship("CIProduct", back_populates="jobs")

    __table_args__ = (
        UniqueConstraint('product_id', 'job_id_key', name='unique_product_job_key'),
    )

    def __repr__(self):
        return f"<ProductJob(id={self.id}, product_id={self.product_id}, key='{self.job_id_key}', type='{self.job_type}')>"


class CompetitorAnalysisSession(Base):
    """
    DEPRECATED: This model is part of the legacy session-based workflow.

    Use the V2 Competitive Intelligence Agent workflow instead:
    - CompetitorFunctionalReport for competitor analysis
    - SynthesisReport (unified synthesis) for opportunity synthesis

    This model is kept for backward compatibility during migration.
    The database should be reinitialized to drop this table.
    """
    __tablename__ = "competitor_analysis_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("ci_products.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    session_number = Column(Integer, nullable=False)
    session_name = Column(String(255))
    analysis_type = Column(String(50), nullable=False, default="full")
    comparison_to_session_id = Column(Integer, ForeignKey("competitor_analysis_sessions.id"), index=True)
    product_source_type = Column(String(50), nullable=False)
    product_source_data = Column(JSON)
    analyzed_product_structure = Column(JSON)

    # Unified session architecture fields
    analysis_version = Column(Integer)  # Links to ProductAnalysisHistory.analysis_version
    stage_completed = Column(Enum(SessionStage), nullable=False, default=SessionStage.PRODUCT_ANALYSIS)
    product_source_hash = Column(String(64))  # SHA-256 hash for change detection

    status = Column(String(50), nullable=False, default="active", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True))

    # Relationships
    product = relationship("CIProduct", back_populates="sessions")
    session_competitors = relationship("SessionCompetitor", back_populates="session", cascade="all, delete-orphan")
    agent_logs = relationship("AgentExecutionLog", back_populates="session")

    def __repr__(self):
        return f"<CompetitorAnalysisSession(id={self.id}, product_id={self.product_id}, session_number={self.session_number})>"


class ProductCompetitor(Base):
    """
    Persistent record of a competitor for a product.

    Tracks competitors discovered across multiple analysis sessions.
    """
    __tablename__ = "product_competitors"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("ci_products.id", ondelete="CASCADE"), nullable=False, index=True)
    competitor_name = Column(String(255), nullable=False)
    competitor_url = Column(String(500))
    competitor_description = Column(Text)  # Added for queue-based discovery
    # Session references - nullable for queue-based workflows (Phase 2+)
    first_discovered_session_id = Column(Integer, ForeignKey("competitor_analysis_sessions.id"), nullable=True)
    last_seen_session_id = Column(Integer, ForeignKey("competitor_analysis_sessions.id"), nullable=True)
    # Queue job reference for queue-based workflows
    first_discovered_job_id = Column(Integer, ForeignKey("queue_jobs.id"), nullable=True)
    # Monitoring fields (legacy - kept for backward compatibility)
    monitoring_enabled = Column(Boolean, default=False)
    last_monitored_at = Column(DateTime(timezone=True), nullable=True)

    # Single tracking flag: tracked = scheduled for audit + included in synthesis
    tracked = Column(Boolean, nullable=False, default=False)
    audit_status = Column(String(50), nullable=True)  # pending, running, completed, failed
    audit_last_run = Column(DateTime(timezone=True), nullable=True)

    # Cached web research (populated per-competitor, reused across audits within TTL)
    cached_search_results = Column(JSON, nullable=True)
    cached_search_at = Column(DateTime(timezone=True), nullable=True)

    status = Column(String(50), nullable=False, default="active", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    product = relationship("CIProduct", back_populates="competitors")
    features = relationship("ProductCompetitorFeature", back_populates="competitor", cascade="all, delete-orphan")
    session_instances = relationship("SessionCompetitor", back_populates="product_competitor")

    __table_args__ = (
        UniqueConstraint('product_id', 'competitor_name', name='unique_product_competitor'),
    )

    def __repr__(self):
        return f"<ProductCompetitor(id={self.id}, name='{self.competitor_name}', product_id={self.product_id})>"


class SessionCompetitor(Base):
    """
    DEPRECATED: This model is part of the legacy session-based workflow.

    Use ProductCompetitor directly (without session linkage) in V2.
    The database should be reinitialized to drop this table.
    """
    __tablename__ = "session_competitors"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("competitor_analysis_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    product_competitor_id = Column(Integer, ForeignKey("product_competitors.id"), index=True)
    competitor_name = Column(String(255), nullable=False)
    competitor_url = Column(String(500))
    ai_summary = Column(Text)
    discovery_source = Column(String(50), nullable=False)
    is_new_discovery = Column(Boolean, default=False, index=True)
    selected_by_user = Column(Boolean, default=False, index=True)
    discovery_rank = Column(Integer)
    status_change = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    session = relationship("CompetitorAnalysisSession", back_populates="session_competitors")
    product_competitor = relationship("ProductCompetitor", back_populates="session_instances")
    features = relationship("CompetitorFeature", back_populates="session_competitor", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<SessionCompetitor(id={self.id}, name='{self.competitor_name}', session_id={self.session_id})>"


class ProductCompetitorFeature(Base):
    """
    DEPRECATED: This model is part of the legacy session-based workflow.

    Use CompetitorFunctionalReport.functional_comparison for competitor features in V2.
    Feature data is stored directly in the JSON field of functional reports.
    The database should be reinitialized to drop this table.
    """
    __tablename__ = "product_competitor_features"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_competitor_id = Column(Integer, ForeignKey("product_competitors.id", ondelete="CASCADE"), nullable=False, index=True)
    feature_name = Column(String(255), nullable=False)
    feature_description = Column(Text)
    feature_category = Column(String(100))
    # Additional fields for queue-based extraction
    extraction_confidence = Column(DECIMAL(3, 2), nullable=True)  # 0.00-1.00
    source_url = Column(String(500), nullable=True)
    # Session references - nullable for queue-based workflows (Phase 2+)
    first_discovered_session_id = Column(Integer, ForeignKey("competitor_analysis_sessions.id"), nullable=True)
    last_seen_session_id = Column(Integer, ForeignKey("competitor_analysis_sessions.id"), nullable=True)
    # Queue job reference for queue-based workflows
    first_discovered_job_id = Column(Integer, ForeignKey("queue_jobs.id"), nullable=True)
    # Tracking fields
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    status = Column(String(50), nullable=False, default="active", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    competitor = relationship("ProductCompetitor", back_populates="features")
    session_instances = relationship("CompetitorFeature", back_populates="product_feature")

    def __repr__(self):
        return f"<ProductCompetitorFeature(id={self.id}, name='{self.feature_name}', competitor_id={self.product_competitor_id})>"


class CompetitorFeature(Base):
    """
    DEPRECATED: This model is part of the legacy session-based workflow.

    Use CompetitorFunctionalReport.functional_comparison for competitor features in V2.
    The database should be reinitialized to drop this table.
    """
    __tablename__ = "competitor_features"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_competitor_id = Column(Integer, ForeignKey("session_competitors.id", ondelete="CASCADE"), nullable=False, index=True)
    product_feature_id = Column(Integer, ForeignKey("product_competitor_features.id"), index=True)
    feature_name = Column(String(255), nullable=False)
    feature_description = Column(Text)
    feature_category = Column(String(100))
    extraction_confidence = Column(DECIMAL(3, 2))
    source_url = Column(String(500))
    raw_context = Column(Text)
    change_type = Column(String(50), index=True)
    change_description = Column(Text)
    comparison_to_feature_id = Column(Integer, ForeignKey("competitor_features.id"))
    selected_by_user = Column(Boolean, default=False, index=True)
    detail_requested = Column(Boolean, default=False)
    expanded_description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    session_competitor = relationship("SessionCompetitor", back_populates="features")
    product_feature = relationship("ProductCompetitorFeature", back_populates="session_instances")

    def __repr__(self):
        return f"<CompetitorFeature(id={self.id}, name='{self.feature_name}', session_competitor_id={self.session_competitor_id})>"


class AgentExecutionLog(Base):
    """
    Log of AI agent executions for debugging and monitoring.

    Tracks all AI operations, token usage, and errors.
    """
    __tablename__ = "agent_execution_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("competitor_analysis_sessions.id"), index=True)
    product_id = Column(Integer, ForeignKey("ci_products.id", ondelete="SET NULL"), index=True)
    agent_name = Column(String(100), nullable=False, index=True)
    stage = Column(String(50), nullable=False)
    input_data = Column(JSON)
    output_data = Column(JSON)
    llm_tokens_used = Column(Integer)
    execution_time_ms = Column(Integer)
    status = Column(String(50), nullable=False, index=True)
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    session = relationship("CompetitorAnalysisSession", back_populates="agent_logs")
    product = relationship("CIProduct", back_populates="agent_logs")

    def __repr__(self):
        return f"<AgentExecutionLog(id={self.id}, agent='{self.agent_name}', status='{self.status}')>"


class ProductPermission(Base):
    """
    Permission grants for product access.

    Defines which users can access which products and at what level.
    Creators get implicit OWNER access without needing a row in this table.
    """
    __tablename__ = "product_permissions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("ci_products.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    permission_level = Column(Enum(ProductPermissionLevel), nullable=False)
    granted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    granted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    product = relationship("CIProduct", back_populates="permissions")

    __table_args__ = (
        UniqueConstraint('product_id', 'user_id', name='unique_product_user_permission'),
    )

    def __repr__(self):
        return f"<ProductPermission(product_id={self.product_id}, user_id={self.user_id}, level='{self.permission_level}')>"


class ProductAnalysisHistory(Base):
    """
    History of product analyses.

    Tracks each time a product is analyzed, creating a versioned history.
    This allows users to see how the product analysis has evolved over time.
    """
    __tablename__ = "product_analysis_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("ci_products.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_version = Column(Integer, nullable=False)
    analyzed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    product_description = Column(Text, nullable=False)
    product_source_type = Column(String(50), nullable=False)
    product_source_data = Column(JSON)
    analyzed_structure = Column(JSON)
    tokens_used = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    product = relationship("CIProduct", back_populates="analysis_history")
    detailed_features = relationship("ProductFeature", back_populates="analysis_history", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('product_id', 'analysis_version', name='unique_product_analysis_version'),
    )

    def __repr__(self):
        return f"<ProductAnalysisHistory(product_id={self.product_id}, version={self.analysis_version})>"


class ProductFeature(Base):
    """
    Detailed features extracted from product analysis.

    Stores the granular feature list (10-25 features) for each product analysis version.
    This complements the core_features (5-7 strategic features) stored in analyzed_structure.
    """
    __tablename__ = "product_features"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("ci_products.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_history_id = Column(Integer, ForeignKey("product_analysis_history.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_version = Column(Integer, nullable=False, index=True)

    # Feature details
    feature_name = Column(String(255), nullable=False)
    feature_description = Column(Text)
    feature_category = Column(String(100))
    extraction_confidence = Column(DECIMAL(3, 2))
    source_reference = Column(Text)
    source_url = Column(String(500), nullable=True)  # URL source when product analyzed from URL

    # Metadata
    status = Column(String(50), nullable=False, default="active", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    analysis_history = relationship("ProductAnalysisHistory", back_populates="detailed_features")

    def __repr__(self):
        return f"<ProductFeature(id={self.id}, name='{self.feature_name}', product_id={self.product_id}, version={self.analysis_version})>"
