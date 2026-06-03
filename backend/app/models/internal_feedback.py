"""
Internal Feedback models for win/loss and support data analysis.

This module defines database models for:
1. InternalFeedbackImport - Tracks imported files and their processing status
2. WinLossTheme - Extracted themes from win/loss deal data
3. SupportTheme - Extracted themes from support ticket data

These models support the Internal Discovery Agent which processes
uploaded JSON files containing CRM and support system exports.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey,
    JSON, Boolean, Float, Enum
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class ImportStatus(enum.Enum):
    """Status of an internal feedback import."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class InternalFeedbackImport(Base):
    """
    Tracks an imported internal feedback file.

    Each import represents a single file upload containing
    deals and/or support tickets. The import goes through
    processing states as the Internal Discovery Agent
    extracts themes.
    """
    __tablename__ = "internal_feedback_imports"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_id = Column(
        Integer,
        ForeignKey("ci_products.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # File metadata
    filename = Column(String(255), nullable=False)
    source_type = Column(
        String(50),
        nullable=False,
        default="file_import"
    )  # file_import, hubspot, salesforce, etc.

    # Processing status
    status = Column(
        String(20),
        nullable=False,
        default="pending"
    )  # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)

    # Counts from the imported data
    deals_count = Column(Integer, nullable=False, default=0)
    tickets_count = Column(Integer, nullable=False, default=0)

    # Raw imported data (stored for reprocessing if needed)
    raw_deals = Column(JSON, nullable=True)
    raw_tickets = Column(JSON, nullable=True)

    # Whether themes have been extracted
    themes_extracted = Column(Boolean, nullable=False, default=False)

    # Analysis summary from agent
    analysis_summary = Column(Text, nullable=True)

    # Job tracking
    job_uuid = Column(String(36), nullable=True, index=True)

    # Timestamps
    imported_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    winloss_themes = relationship(
        "WinLossTheme",
        back_populates="import_record",
        cascade="all, delete-orphan"
    )
    support_themes = relationship(
        "SupportTheme",
        back_populates="import_record",
        cascade="all, delete-orphan"
    )


class WinLossTheme(Base):
    """
    A theme extracted from win/loss deal data.

    Themes are patterns identified across multiple deals,
    such as "Missing Time Tracking Feature" appearing in
    several lost deals against a specific competitor.
    """
    __tablename__ = "winloss_themes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    import_id = Column(
        Integer,
        ForeignKey("internal_feedback_imports.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    product_id = Column(
        Integer,
        ForeignKey("ci_products.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Theme identification
    theme_name = Column(String(255), nullable=False)
    outcome = Column(
        String(20),
        nullable=False
    )  # won, lost, or both

    # Competitor correlation
    competitor_name = Column(String(255), nullable=True)

    # Metrics
    deal_count = Column(Integer, nullable=False, default=0)
    total_value = Column(Float, nullable=False, default=0.0)

    # Evidence
    sample_reasons = Column(JSON, nullable=True)  # List of up to 5 sample quotes

    # Keywords for matching with competitive features
    feature_keywords = Column(JSON, nullable=True)  # List of keywords

    # Embedding for semantic matching (stored as JSON array)
    embedding = Column(JSON, nullable=True)

    # Jobs-to-be-Done extraction
    jtbd_statement = Column(Text, nullable=True)  # "When [situation], I want to [motivation], so I can [outcome]"

    # JTBD job linkage (set during import via embedding match to ProductJob)
    job_id_key = Column(String(50), nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    import_record = relationship(
        "InternalFeedbackImport",
        back_populates="winloss_themes"
    )


class SupportTheme(Base):
    """
    A theme extracted from support ticket data.

    Themes represent patterns in customer support requests,
    such as "PDF Export Functionality" appearing across
    multiple feature request tickets.
    """
    __tablename__ = "support_themes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    import_id = Column(
        Integer,
        ForeignKey("internal_feedback_imports.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    product_id = Column(
        Integer,
        ForeignKey("ci_products.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Theme identification
    theme_name = Column(String(255), nullable=False)
    category = Column(
        String(50),
        nullable=False,
        default="other"
    )  # feature_request, bug, support, other

    # Metrics
    ticket_count = Column(Integer, nullable=False, default=0)

    # Evidence
    sample_subjects = Column(JSON, nullable=True)  # List of up to 5 sample subjects

    # Keywords for matching with competitive features
    feature_keywords = Column(JSON, nullable=True)  # List of keywords

    # Urgency assessment
    urgency_indicator = Column(
        String(20),
        nullable=False,
        default="medium"
    )  # high, medium, low

    # Embedding for semantic matching (stored as JSON array)
    embedding = Column(JSON, nullable=True)

    # Jobs-to-be-Done extraction
    jtbd_statement = Column(Text, nullable=True)  # "When [situation], I want to [motivation], so I can [outcome]"

    # JTBD job linkage (set during import via embedding match to ProductJob)
    job_id_key = Column(String(50), nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    import_record = relationship(
        "InternalFeedbackImport",
        back_populates="support_themes"
    )
