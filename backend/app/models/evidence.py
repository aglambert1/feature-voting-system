"""
Evidence model for the product factbase.

Evidence records are flexible, source-agnostic containers for any
product-relevant information that doesn't fit existing pipelines
(competitor reports, ideas, win/loss themes). Examples include:
- Competitive intelligence found during research
- Customer interview insights
- Market signals and analyst reports
- Ad-hoc notes from Claude or PM conversations

Evidence feeds into synthesis as either:
- Competitive source (competitive_intel, pricing_change, partnership, product_launch)
- Fourth "evidence/research" source (all other types)
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, JSON, Enum
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class EvidenceType(str, enum.Enum):
    """Types of evidence that can be stored in the factbase."""
    COMPETITIVE_INTEL = "competitive_intel"
    CUSTOMER_INTERVIEW = "customer_interview"
    MARKET_SIGNAL = "market_signal"
    INTERNAL_NOTE = "internal_note"
    RESEARCH = "research"
    PRICING_CHANGE = "pricing_change"
    PARTNERSHIP = "partnership"
    PRODUCT_LAUNCH = "product_launch"
    ANALYST_REPORT = "analyst_report"


# Evidence types that route to the competitive source in synthesis
COMPETITIVE_EVIDENCE_TYPES = {
    EvidenceType.COMPETITIVE_INTEL,
    EvidenceType.PRICING_CHANGE,
    EvidenceType.PARTNERSHIP,
    EvidenceType.PRODUCT_LAUNCH,
}


class Evidence(Base):
    """
    A piece of product-relevant evidence in the factbase.

    Evidence is a flexible container for information that doesn't fit
    the structured pipelines (competitor reports, ideas, internal feedback).
    Each record gets embedded for semantic search and optionally has a
    JTBD statement extracted for synthesis integration.
    """
    __tablename__ = "evidence"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_id = Column(
        Integer,
        ForeignKey("ci_products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Classification
    evidence_type = Column(
        Enum(EvidenceType),
        nullable=False,
        index=True,
    )

    # Content
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)

    # Source tracking
    source_url = Column(String(500), nullable=True)
    source_description = Column(String(255), nullable=True)

    # Optional link to a known competitor
    competitor_id = Column(
        Integer,
        ForeignKey("product_competitors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Flexible metadata
    tags = Column(JSON, nullable=True)  # ["pricing", "enterprise", "AI"]
    extra_data = Column("extra_data", JSON, nullable=True)  # Type-specific structured data

    # JTBD extraction (populated on create)
    jtbd_statement = Column(Text, nullable=True)

    # Embeddings (populated on create)
    jtbd_embedding = Column(JSON, nullable=True)  # 1024-dim Voyage AI
    content_embedding = Column(JSON, nullable=True)  # 1024-dim Voyage AI

    # Provenance
    created_by = Column(String(100), nullable=False, default="api")

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    product = relationship("CIProduct", backref="evidence")
    competitor = relationship("ProductCompetitor", backref="evidence")

    def __repr__(self):
        return f"<Evidence(id={self.id}, type={self.evidence_type}, title='{self.title}')>"

    def is_competitive(self) -> bool:
        """Whether this evidence routes to the competitive source in synthesis."""
        return self.evidence_type in COMPETITIVE_EVIDENCE_TYPES

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "product_id": self.product_id,
            "evidence_type": self.evidence_type.value if self.evidence_type else None,
            "title": self.title,
            "content": self.content,
            "source_url": self.source_url,
            "source_description": self.source_description,
            "competitor_id": self.competitor_id,
            "tags": self.tags,
            "extra_data": self.extra_data,
            "jtbd_statement": self.jtbd_statement,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_summary_dict(self) -> dict:
        """Compact representation for search results and lists."""
        return {
            "id": self.id,
            "evidence_type": self.evidence_type.value if self.evidence_type else None,
            "title": self.title,
            "source_url": self.source_url,
            "source_description": self.source_description,
            "competitor_id": self.competitor_id,
            "tags": self.tags,
            "jtbd_statement": self.jtbd_statement,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
