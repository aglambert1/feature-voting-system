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
    - ADMIN: Can delete product, manage permissions
    """
    VIEW = "view"
    EDIT = "edit"
    ADMIN = "admin"


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
    last_analyzed_at = Column(DateTime)
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

    status = Column(String(50), default="active", index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    sessions = relationship("CompetitorAnalysisSession", back_populates="product", cascade="all, delete-orphan")
    competitors = relationship("ProductCompetitor", back_populates="product", cascade="all, delete-orphan")
    generated_ideas = relationship("CompetitorGeneratedIdea", back_populates="product")
    agent_logs = relationship("AgentExecutionLog", back_populates="product")
    permissions = relationship("ProductPermission", back_populates="product", cascade="all, delete-orphan")
    analysis_history = relationship("ProductAnalysisHistory", back_populates="product", cascade="all, delete-orphan")

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


class CompetitorAnalysisSession(Base):
    """
    A single analysis session for a product.

    Each time a user runs competitor analysis, a new session is created.
    Sessions can be "full" (new analysis) or "differential" (compare to previous).
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
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    completed_at = Column(DateTime)

    # Relationships
    product = relationship("CIProduct", back_populates="sessions")
    session_competitors = relationship("SessionCompetitor", back_populates="session", cascade="all, delete-orphan")
    generated_ideas = relationship("CompetitorGeneratedIdea", back_populates="session")
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
    # Monitoring fields
    monitoring_enabled = Column(Boolean, default=False)
    last_monitored_at = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=False, default="active", index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

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
    Competitor discovered in a specific analysis session.

    Links to persistent ProductCompetitor if it's a known competitor,
    or represents a new discovery.
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
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    session = relationship("CompetitorAnalysisSession", back_populates="session_competitors")
    product_competitor = relationship("ProductCompetitor", back_populates="session_instances")
    features = relationship("CompetitorFeature", back_populates="session_competitor", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<SessionCompetitor(id={self.id}, name='{self.competitor_name}', session_id={self.session_id})>"


class ProductCompetitorFeature(Base):
    """
    Persistent record of a feature from a competitor.

    Tracks features across multiple analysis sessions.
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
    first_seen_at = Column(DateTime, server_default=func.now())
    last_seen_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    status = Column(String(50), nullable=False, default="active", index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    competitor = relationship("ProductCompetitor", back_populates="features")
    session_instances = relationship("CompetitorFeature", back_populates="product_feature")

    def __repr__(self):
        return f"<ProductCompetitorFeature(id={self.id}, name='{self.feature_name}', competitor_id={self.product_competitor_id})>"


class CompetitorFeature(Base):
    """
    Feature extracted from a competitor in a specific session.

    Links to persistent ProductCompetitorFeature if it's a known feature,
    or represents a new discovery.
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
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    session_competitor = relationship("SessionCompetitor", back_populates="features")
    product_feature = relationship("ProductCompetitorFeature", back_populates="session_instances")
    generated_idea = relationship("CompetitorGeneratedIdea", back_populates="feature", uselist=False)

    def __repr__(self):
        return f"<CompetitorFeature(id={self.id}, name='{self.feature_name}', session_competitor_id={self.session_competitor_id})>"


class CompetitorGeneratedIdea(Base):
    """
    AI-generated idea based on a competitor feature.

    These ideas can be edited by users and then submitted to the main ideas table.
    """
    __tablename__ = "competitor_generated_ideas"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    feature_id = Column(Integer, ForeignKey("competitor_features.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("competitor_analysis_sessions.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("ci_products.id"), nullable=False, index=True)
    idea_what = Column(Text, nullable=False)
    idea_why = Column(Text, nullable=False)
    idea_use_case = Column(Text, nullable=False)
    is_differential = Column(Boolean, default=False)
    user_edited = Column(Boolean, default=False)
    user_approved = Column(Boolean, default=False)
    submitted_to_ideas = Column(Boolean, default=False, index=True)
    final_idea_id = Column(Integer, ForeignKey("ideas.id"))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    edited_at = Column(DateTime)

    # Relationships
    feature = relationship("CompetitorFeature", back_populates="generated_idea")
    session = relationship("CompetitorAnalysisSession", back_populates="generated_ideas")
    product = relationship("CIProduct", back_populates="generated_ideas")

    def __repr__(self):
        return f"<CompetitorGeneratedIdea(id={self.id}, feature_id={self.feature_id}, submitted={self.submitted_to_ideas})>"


class AgentExecutionLog(Base):
    """
    Log of AI agent executions for debugging and monitoring.

    Tracks all AI operations, token usage, and errors.
    """
    __tablename__ = "agent_execution_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("competitor_analysis_sessions.id"), index=True)
    product_id = Column(Integer, ForeignKey("ci_products.id"), index=True)
    agent_name = Column(String(100), nullable=False, index=True)
    stage = Column(String(50), nullable=False)
    input_data = Column(JSON)
    output_data = Column(JSON)
    llm_tokens_used = Column(Integer)
    execution_time_ms = Column(Integer)
    status = Column(String(50), nullable=False, index=True)
    error_message = Column(Text)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    session = relationship("CompetitorAnalysisSession", back_populates="agent_logs")
    product = relationship("CIProduct", back_populates="agent_logs")

    def __repr__(self):
        return f"<AgentExecutionLog(id={self.id}, agent='{self.agent_name}', status='{self.status}')>"


class ProductPermission(Base):
    """
    Permission grants for product access.

    Defines which users can access which products and at what level.
    Creators get implicit ADMIN access without needing a row in this table.
    """
    __tablename__ = "product_permissions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("ci_products.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    permission_level = Column(Enum(ProductPermissionLevel), nullable=False)
    granted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    granted_at = Column(DateTime, server_default=func.now(), nullable=False)

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
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

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
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    analysis_history = relationship("ProductAnalysisHistory", back_populates="detailed_features")

    def __repr__(self):
        return f"<ProductFeature(id={self.id}, name='{self.feature_name}', product_id={self.product_id}, version={self.analysis_version})>"
