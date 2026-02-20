"""
Idea Normalizer Service.

Orchestrates the normalization of ideas from various sources using adapters.
Provides a unified interface for converting any source into a normalized idea.

Phase 3: Idea Normalization + Triage
"""

from typing import Dict, Any, Optional, List, Type
from sqlalchemy.orm import Session

from app.adapters.base import BaseSourceAdapter, NormalizedIdea
from app.adapters.customer_submission import CustomerSubmissionAdapter
from app.adapters.competitor_feature import CompetitorFeatureAdapter
from app.models.idea import Idea, SourceType, IdeaStatus
from app.services.llm_service import LLMService


class IdeaNormalizerService:
    """
    Service for normalizing ideas from various sources.

    Provides a unified interface that:
    1. Detects source type from input
    2. Routes to appropriate adapter
    3. Returns normalized idea ready for triage
    """

    # Registry of adapters by source type
    ADAPTER_REGISTRY: Dict[SourceType, Type[BaseSourceAdapter]] = {
        SourceType.CUSTOMER_SUBMISSION: CustomerSubmissionAdapter,
        SourceType.COMPETITOR_AUTOMATED: CompetitorFeatureAdapter,
    }

    def __init__(self, db: Session, llm_service: Optional[LLMService] = None):
        """
        Initialize the service.

        Args:
            db: Database session
            llm_service: Optional LLM service (created if not provided)
        """
        self.db = db
        self.llm_service = llm_service or LLMService()
        self._adapters: Dict[SourceType, BaseSourceAdapter] = {}

    def get_adapter(self, source_type: SourceType) -> BaseSourceAdapter:
        """
        Get or create adapter for source type.

        Args:
            source_type: The source type

        Returns:
            Adapter instance

        Raises:
            ValueError: If no adapter registered for source type
        """
        if source_type not in self._adapters:
            adapter_class = self.ADAPTER_REGISTRY.get(source_type)
            if not adapter_class:
                raise ValueError(f"No adapter registered for source type: {source_type}")
            self._adapters[source_type] = adapter_class(
                db=self.db,
                llm_service=self.llm_service
            )
        return self._adapters[source_type]

    def normalize(
        self,
        raw_input: Dict[str, Any],
        source_type: Optional[SourceType] = None
    ) -> NormalizedIdea:
        """
        Normalize input from any source.

        Args:
            raw_input: Raw input data
            source_type: Optional explicit source type (auto-detected if not provided)

        Returns:
            NormalizedIdea

        Raises:
            ValueError: If source type cannot be determined or input is invalid
        """
        # Determine source type
        if source_type is None:
            source_type = self._detect_source_type(raw_input)

        # Get adapter and normalize
        adapter = self.get_adapter(source_type)
        return adapter.normalize(raw_input)

    def normalize_customer_submission(
        self,
        product_id: int,
        submitter_id: Optional[int] = None,
        freeform_text: Optional[str] = None,
        title: Optional[str] = None,
        what_description: Optional[str] = None,
        why_description: Optional[str] = None,
        use_case_description: Optional[str] = None,
        category: Optional[str] = None
    ) -> NormalizedIdea:
        """
        Convenience method for customer submissions.

        Args:
            product_id: Product ID
            submitter_id: Optional submitter user ID
            freeform_text: Optional freeform text (uses AI structuring)
            title: Optional structured title
            what_description: Optional structured what
            why_description: Optional structured why
            use_case_description: Optional structured use case
            category: Optional category

        Returns:
            NormalizedIdea
        """
        raw_input = {
            'product_id': product_id,
            'submitter_id': submitter_id,
        }

        if freeform_text:
            raw_input['freeform_text'] = freeform_text
        else:
            raw_input['title'] = title
            raw_input['what_description'] = what_description
            raw_input['why_description'] = why_description
            raw_input['use_case_description'] = use_case_description

        if category:
            raw_input['category'] = category

        return self.normalize(raw_input, SourceType.CUSTOMER_SUBMISSION)

    def normalize_competitor_feature(
        self,
        product_id: int,
        feature_id: int,
        change_type: Optional[str] = None,
        change_description: Optional[str] = None
    ) -> NormalizedIdea:
        """
        Convenience method for competitor features.

        Args:
            product_id: Product ID
            feature_id: Competitor feature ID
            change_type: Optional change type (new, modified, etc.)
            change_description: Optional description of what changed

        Returns:
            NormalizedIdea
        """
        raw_input = {
            'product_id': product_id,
            'feature_id': feature_id,
        }

        if change_type:
            raw_input['change_type'] = change_type
        if change_description:
            raw_input['change_description'] = change_description

        return self.normalize(raw_input, SourceType.COMPETITOR_AUTOMATED)

    def create_idea_from_normalized(
        self,
        normalized: NormalizedIdea,
        status: IdeaStatus = IdeaStatus.PENDING
    ) -> Idea:
        """
        Create an Idea model instance from NormalizedIdea.

        Args:
            normalized: The normalized idea
            status: Initial idea status (default: PENDING)

        Returns:
            Idea model instance (not yet committed)
        """
        # Get product to determine is_active based on status
        from app.models.competitor_intelligence import CIProduct
        product = self.db.query(CIProduct).filter(CIProduct.id == normalized.product_id).first()
        is_active = product.get_is_active_for_status(status) if product else status == IdeaStatus.ACCEPTED

        idea = Idea(
            title=normalized.title,
            what_description=normalized.what_description,
            why_description=normalized.why_description,
            use_case_description=normalized.use_case_description,
            source_type=normalized.source_type,
            source_metadata=normalized.source_metadata,
            product_id=normalized.product_id,
            submitter_id=normalized.submitter_id,
            category=normalized.category,
            auto_categorized=normalized.auto_categorized,
            external_id=normalized.external_id,
            external_source=normalized.external_source,
            status=status,
            is_active=is_active,
        )
        return idea

    def normalize_and_create(
        self,
        raw_input: Dict[str, Any],
        source_type: Optional[SourceType] = None,
        commit: bool = True
    ) -> Idea:
        """
        Normalize input and create Idea in one step.

        Args:
            raw_input: Raw input data
            source_type: Optional explicit source type
            commit: Whether to commit to database

        Returns:
            Created Idea model instance
        """
        normalized = self.normalize(raw_input, source_type)
        idea = self.create_idea_from_normalized(normalized)

        self.db.add(idea)
        if commit:
            self.db.commit()
            self.db.refresh(idea)

        return idea

    def _detect_source_type(self, raw_input: Dict[str, Any]) -> SourceType:
        """
        Auto-detect source type from input.

        Args:
            raw_input: Raw input data

        Returns:
            Detected SourceType

        Raises:
            ValueError: If source type cannot be determined
        """
        # Check for explicit source type
        if 'source_type' in raw_input:
            source_type_str = raw_input['source_type']
            if isinstance(source_type_str, SourceType):
                return source_type_str
            return SourceType(source_type_str)

        # Detect based on input structure
        if 'feature_id' in raw_input:
            return SourceType.COMPETITOR_AUTOMATED

        if 'freeform_text' in raw_input or 'what_description' in raw_input:
            return SourceType.CUSTOMER_SUBMISSION

        raise ValueError(
            "Cannot determine source type from input. "
            "Provide 'source_type' explicitly or include type-specific fields."
        )

    def get_registered_source_types(self) -> List[SourceType]:
        """Get list of registered source types."""
        return list(self.ADAPTER_REGISTRY.keys())
