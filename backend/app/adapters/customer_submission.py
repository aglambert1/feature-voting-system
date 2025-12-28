"""
Customer Submission Adapter.

Handles manual idea submissions from customers/users.
Can process both structured input and freeform text.

Phase 3: Idea Normalization + Triage
"""

from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.adapters.base import BaseSourceAdapter, NormalizedIdea
from app.models.idea import SourceType
from app.services.llm_service import LLMService


class CustomerSubmissionAdapter(BaseSourceAdapter):
    """
    Adapter for customer-submitted ideas.

    Handles two input modes:
    1. Structured: Pre-formatted with title, what, why, use_case
    2. Freeform: Raw text that needs AI structuring
    """

    def __init__(self, db: Session, llm_service: Optional[LLMService] = None):
        """
        Initialize the adapter.

        Args:
            db: Database session
            llm_service: Optional LLM service for freeform text processing
        """
        self.db = db
        self.llm_service = llm_service or LLMService()

    def get_source_type(self) -> SourceType:
        return SourceType.CUSTOMER_SUBMISSION

    def get_required_fields(self) -> list:
        return ['product_id']  # Either structured fields or freeform_text

    def validate_input(self, raw_input: Dict[str, Any]) -> bool:
        """
        Validate customer submission input.

        Valid if:
        - Has product_id AND
        - Either has freeform_text OR has all structured fields
        """
        if 'product_id' not in raw_input:
            return False

        has_freeform = bool(raw_input.get('freeform_text', '').strip())
        has_structured = all([
            raw_input.get('title', '').strip(),
            raw_input.get('what_description', '').strip(),
            raw_input.get('why_description', '').strip(),
            raw_input.get('use_case_description', '').strip(),
        ])

        return has_freeform or has_structured

    def extract_metadata(self, raw_input: Dict[str, Any]) -> Dict[str, Any]:
        """Extract customer submission metadata."""
        metadata = {
            'submission_type': 'structured' if raw_input.get('title') else 'freeform',
        }

        # Include optional fields if provided
        if raw_input.get('submitter_email'):
            metadata['submitter_email'] = raw_input['submitter_email']
        if raw_input.get('submission_channel'):
            metadata['submission_channel'] = raw_input['submission_channel']
        if raw_input.get('priority_hint'):
            metadata['priority_hint'] = raw_input['priority_hint']

        return metadata

    def normalize(self, raw_input: Dict[str, Any]) -> NormalizedIdea:
        """
        Normalize customer submission to NormalizedIdea.

        If freeform_text is provided, uses AI to structure it.
        Otherwise, uses provided structured fields directly.

        Args:
            raw_input: Dictionary with submission data

        Returns:
            NormalizedIdea

        Raises:
            ValueError: If input is invalid
        """
        if not self.validate_input(raw_input):
            raise ValueError("Invalid input: requires product_id and either structured fields or freeform_text")

        product_id = raw_input['product_id']
        submitter_id = raw_input.get('submitter_id')

        # Check if we have freeform text to process
        freeform_text = raw_input.get('freeform_text', '').strip()

        if freeform_text and not raw_input.get('title'):
            # Use AI to structure freeform text
            structured = self._structure_freeform_text(
                freeform_text=freeform_text,
                product_id=product_id
            )
            title = structured['title']
            what = structured['what']
            why = structured['why']
            use_case = structured['use_case']
            category = structured.get('category')
            adaptation_notes = structured.get('adaptation_notes')
        else:
            # Use provided structured fields
            title = raw_input['title']
            what = raw_input['what_description']
            why = raw_input['why_description']
            use_case = raw_input['use_case_description']
            category = raw_input.get('category')
            adaptation_notes = None

        return NormalizedIdea(
            title=title,
            what_description=what,
            why_description=why,
            use_case_description=use_case,
            source_type=self.get_source_type(),
            source_metadata=self.extract_metadata(raw_input),
            product_id=product_id,
            submitter_id=submitter_id,
            category=category,
            auto_categorized=bool(category and freeform_text),
            raw_input=freeform_text or None,
            adaptation_notes=adaptation_notes,
        )

    def _structure_freeform_text(
        self,
        freeform_text: str,
        product_id: int
    ) -> Dict[str, Any]:
        """
        Use AI to structure freeform text into idea components.

        Args:
            freeform_text: Raw user input
            product_id: Product ID for context

        Returns:
            Dictionary with title, what, why, use_case, etc.
        """
        # Get product context for better structuring
        product_context = self._get_product_context(product_id)

        # Use LLM service to structure the idea
        result = self.llm_service.structure_idea(
            freeform_text=freeform_text,
            product_context=product_context
        )

        return {
            'title': result.get('title', ''),
            'what': result.get('what', ''),
            'why': result.get('why', ''),
            'use_case': result.get('use_case', ''),
            'category': result.get('category'),
            'adaptation_notes': result.get('adaptation_notes'),
        }

    def _get_product_context(self, product_id: int) -> Dict[str, Any]:
        """
        Get product context for AI structuring.

        Args:
            product_id: Product ID

        Returns:
            Product context dictionary
        """
        from app.models.competitor_intelligence import CIProduct

        product = self.db.query(CIProduct).filter(CIProduct.id == product_id).first()
        if not product:
            return {}

        context = {
            'product_name': product.product_name,
            'product_description': product.product_description,
            'product_category': product.product_category,
        }

        # Add structured data if available
        if product.structured_product_data:
            data = product.structured_product_data
            context['core_features'] = data.get('core_features', [])
            context['detailed_features'] = data.get('detailed_features', [])
            context['target_users'] = data.get('target_users', '')
            context['value_propositions'] = data.get('value_propositions', [])

        return context
