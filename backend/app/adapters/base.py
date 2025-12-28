"""
Base adapter class for source normalization.

Defines the interface that all source adapters must implement.

Phase 3: Idea Normalization + Triage
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from app.models.idea import SourceType


@dataclass
class NormalizedIdea:
    """
    Normalized idea format used across all sources.

    This is the intermediate representation that all adapters produce.
    It contains all fields needed to create an Idea record.
    """
    # Core content
    title: str
    what_description: str
    why_description: str
    use_case_description: str

    # Source tracking
    source_type: SourceType
    source_metadata: Dict[str, Any] = field(default_factory=dict)

    # Relationships
    product_id: int = 0
    submitter_id: Optional[int] = None

    # Categorization (may be set by adapter or triage)
    category: Optional[str] = None
    auto_categorized: bool = False

    # Additional context
    raw_input: Optional[str] = None  # Original input before normalization
    adaptation_notes: Optional[str] = None  # Notes from AI adaptation

    def to_idea_dict(self) -> Dict[str, Any]:
        """Convert to dictionary suitable for Idea model creation."""
        return {
            'title': self.title,
            'what_description': self.what_description,
            'why_description': self.why_description,
            'use_case_description': self.use_case_description,
            'source_type': self.source_type,
            'source_metadata': self.source_metadata,
            'product_id': self.product_id,
            'submitter_id': self.submitter_id,
            'category': self.category,
            'auto_categorized': self.auto_categorized,
        }


class BaseSourceAdapter(ABC):
    """
    Abstract base class for source adapters.

    Each adapter handles a specific source type and converts
    raw input into a NormalizedIdea.
    """

    @abstractmethod
    def get_source_type(self) -> SourceType:
        """
        Return the source type this adapter handles.

        Returns:
            SourceType enum value
        """
        pass

    @abstractmethod
    def normalize(self, raw_input: Dict[str, Any]) -> NormalizedIdea:
        """
        Normalize raw input into a NormalizedIdea.

        This method may call AI services for structuring
        if the input is freeform text.

        Args:
            raw_input: Raw input data from the source

        Returns:
            NormalizedIdea ready for triage

        Raises:
            ValueError: If input cannot be normalized
        """
        pass

    @abstractmethod
    def validate_input(self, raw_input: Dict[str, Any]) -> bool:
        """
        Validate that the input has required fields.

        Args:
            raw_input: Raw input data to validate

        Returns:
            True if valid, False otherwise
        """
        pass

    def get_required_fields(self) -> list:
        """
        Return list of required fields for this adapter.

        Override in subclass to specify required input fields.

        Returns:
            List of required field names
        """
        return []

    def extract_metadata(self, raw_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract source-specific metadata from input.

        Override in subclass for source-specific metadata.

        Args:
            raw_input: Raw input data

        Returns:
            Metadata dictionary
        """
        return {}
