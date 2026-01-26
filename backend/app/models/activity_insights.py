"""
Activity Insights models for CRM activity stream analysis.

This module defines database models for:
1. ActivityImport - Tracks imported activity data files (JSON or Markdown)
2. DealActivityInsight - Insights extracted from sales deal activities
3. SupportActivityInsight - Insights extracted from support activities (aggregate)

These models support the Activity Insight Agent which processes
CRM activity exports to extract product-relevant themes from
unstructured conversation data (call notes, emails, meeting notes).
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey,
    JSON, Float
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class ActivityImport(Base):
    """
    Tracks an imported CRM activity data file.

    Each import represents a single file upload containing
    deal activities and/or support activities. Supports both
    JSON and Markdown formats. The import goes through
    processing states as the Activity Insight Agent extracts themes.
    """
    __tablename__ = "activity_imports"

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
        default="manual"
    )  # salesforce, hubspot, manual, etc.
    format_type = Column(
        String(20),
        nullable=False,
        default="json"
    )  # json or markdown

    # Processing status
    status = Column(
        String(20),
        nullable=False,
        default="pending"
    )  # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)

    # Counts from the imported data
    deals_count = Column(Integer, nullable=False, default=0)
    activities_count = Column(Integer, nullable=False, default=0)
    support_tickets_count = Column(Integer, nullable=False, default=0)

    # Raw imported data (normalized from JSON or parsed markdown)
    raw_content = Column(JSON, nullable=True)

    # Analysis summary from agent
    analysis_summary = Column(Text, nullable=True)

    # Aggregate analysis results
    top_loss_themes = Column(JSON, nullable=True)  # Themes correlated with losses
    top_win_themes = Column(JSON, nullable=True)   # Themes in won deals
    competitor_patterns = Column(JSON, nullable=True)  # Competitor -> themes mapping

    # Job tracking
    job_uuid = Column(String(36), nullable=True, index=True)

    # Timestamps
    imported_at = Column(DateTime, server_default=func.now(), nullable=False)
    processed_at = Column(DateTime, nullable=True)

    # Relationships
    deal_insights = relationship(
        "DealActivityInsight",
        back_populates="import_record",
        cascade="all, delete-orphan"
    )
    support_insights = relationship(
        "SupportActivityInsight",
        back_populates="import_record",
        cascade="all, delete-orphan"
    )


class DealActivityInsight(Base):
    """
    An insight extracted from sales deal activities.

    Insights are product-relevant themes identified from analyzing
    all activities within a deal (calls, emails, meetings, notes).
    Each insight is tied to a specific deal and its outcome,
    enabling correlation analysis (what themes appear in lost vs won deals).
    """
    __tablename__ = "deal_activity_insights"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    import_id = Column(
        Integer,
        ForeignKey("activity_imports.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    product_id = Column(
        Integer,
        ForeignKey("ci_products.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Deal context
    deal_id = Column(String(255), nullable=True)  # Original CRM deal ID
    deal_name = Column(String(255), nullable=True)
    deal_outcome = Column(
        String(20),
        nullable=False,
        default="unknown"
    )  # won, lost, open, unknown
    deal_value = Column(Float, nullable=True)
    competitor_mentioned = Column(String(255), nullable=True)

    # Extracted insight
    theme_name = Column(String(255), nullable=False)
    category = Column(
        String(50),
        nullable=False,
        default="feature_gap"
    )  # feature_gap, ux_friction, competitive_pressure, use_case_gap, integration_need
    sentiment = Column(
        String(20),
        nullable=False,
        default="neutral"
    )  # positive, negative, neutral
    urgency_level = Column(
        String(20),
        nullable=False,
        default="medium"
    )  # high, medium, low

    # Evidence
    sample_quotes = Column(JSON, nullable=True)  # 2-5 verbatim customer statements
    activity_count = Column(Integer, nullable=False, default=1)  # How many activities mentioned this theme

    # Keywords for matching with competitive features and other themes
    feature_keywords = Column(JSON, nullable=True)  # List of keywords

    # Embedding for semantic matching (stored as JSON array)
    embedding = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    import_record = relationship(
        "ActivityImport",
        back_populates="deal_insights"
    )


class SupportActivityInsight(Base):
    """
    An insight extracted from support activities (aggregate analysis).

    Unlike deal insights which are per-deal, support insights are
    aggregated across all support tickets/activities to identify
    common themes. This includes hidden feature requests in tickets
    marked as bugs or customer confusion.
    """
    __tablename__ = "support_activity_insights"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    import_id = Column(
        Integer,
        ForeignKey("activity_imports.id", ondelete="CASCADE"),
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
        default="feature_gap"
    )  # feature_gap, ux_friction, workaround_needed, integration_need

    # Metrics
    ticket_count = Column(Integer, nullable=False, default=0)
    urgency_level = Column(
        String(20),
        nullable=False,
        default="medium"
    )  # high, medium, low - based on volume + language signals

    # Evidence
    sample_quotes = Column(JSON, nullable=True)  # 2-5 verbatim customer statements
    accounts_affected = Column(JSON, nullable=True)  # List of account names/IDs

    # Keywords for matching with competitive features and other themes
    feature_keywords = Column(JSON, nullable=True)  # List of keywords

    # Embedding for semantic matching (stored as JSON array)
    embedding = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    import_record = relationship(
        "ActivityImport",
        back_populates="support_insights"
    )
