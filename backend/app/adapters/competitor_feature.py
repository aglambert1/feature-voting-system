"""
Competitor Feature Adapter.

Converts competitor features into product-specific ideas.
Uses the IdeaStructuringAgent for intelligent adaptation.

Phase 3: Idea Normalization + Triage
"""

from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from app.adapters.base import BaseSourceAdapter, NormalizedIdea
from app.models.idea import SourceType
from app.models.competitor_intelligence import (
    CIProduct, ProductCompetitor, ProductCompetitorFeature
)
from app.services.llm_service import LLMService
from app.agents.idea_structuring_agent import IdeaStructuringAgent


class CompetitorFeatureAdapter(BaseSourceAdapter):
    """
    Adapter for converting competitor features into ideas.

    Uses AI to strategically adapt competitor features to fit
    the target product's context, users, and positioning.
    """

    def __init__(self, db: Session, llm_service: Optional[LLMService] = None):
        """
        Initialize the adapter.

        Args:
            db: Database session
            llm_service: Optional LLM service for AI processing
        """
        self.db = db
        self.llm_service = llm_service or LLMService()

    def get_source_type(self) -> SourceType:
        return SourceType.COMPETITOR_AUTOMATED

    def get_required_fields(self) -> list:
        return ['product_id', 'feature_id']

    def validate_input(self, raw_input: Dict[str, Any]) -> bool:
        """
        Validate competitor feature input.

        Valid if has product_id and feature_id.
        """
        return (
            'product_id' in raw_input and
            'feature_id' in raw_input
        )

    def extract_metadata(self, raw_input: Dict[str, Any]) -> Dict[str, Any]:
        """Extract competitor feature metadata."""
        feature = self._get_feature(raw_input.get('feature_id'))
        competitor = self._get_competitor(feature.product_competitor_id) if feature else None

        metadata = {
            'feature_id': raw_input.get('feature_id'),
            'competitor_id': competitor.id if competitor else None,
            'competitor_name': competitor.competitor_name if competitor else None,
            'competitor_url': competitor.competitor_url if competitor else None,
            'original_feature_name': feature.feature_name if feature else None,
            'original_feature_category': feature.feature_category if feature else None,
            'source_url': feature.source_url if feature else None,
        }

        # Include optional extraction context
        if raw_input.get('change_type'):
            metadata['change_type'] = raw_input['change_type']
        if raw_input.get('change_description'):
            metadata['change_description'] = raw_input['change_description']

        return metadata

    def normalize(self, raw_input: Dict[str, Any]) -> NormalizedIdea:
        """
        Normalize competitor feature to NormalizedIdea.

        Uses IdeaStructuringAgent to adapt the competitor feature
        to the target product's context.

        Args:
            raw_input: Dictionary with feature_id, product_id, etc.

        Returns:
            NormalizedIdea

        Raises:
            ValueError: If input is invalid or feature not found
        """
        if not self.validate_input(raw_input):
            raise ValueError("Invalid input: requires product_id and feature_id")

        product_id = raw_input['product_id']
        feature_id = raw_input['feature_id']

        # Get the feature
        feature = self._get_feature(feature_id)
        if not feature:
            raise ValueError(f"Feature {feature_id} not found")

        # Get the competitor
        competitor = self._get_competitor(feature.product_competitor_id)
        if not competitor:
            raise ValueError(f"Competitor for feature {feature_id} not found")

        # Get product context
        product_context = self._get_product_context(product_id)

        # Build feature data for the agent
        feature_data = {
            'id': feature.id,
            'competitor_name': competitor.competitor_name,
            'feature_name': feature.feature_name,
            'feature_description': feature.feature_description,
            'feature_category': feature.feature_category,
            'source_url': feature.source_url,
        }

        # Include change context if provided
        if raw_input.get('change_type'):
            feature_data['change_type'] = raw_input['change_type']
            feature_data['change_description'] = raw_input.get('change_description')

        # Use IdeaStructuringAgent to adapt the feature
        agent = IdeaStructuringAgent(
            db=self.db,
            llm_service=self.llm_service,
            product_id=product_id
        )

        agent_input = {
            'product_context': product_context,
            'features': [feature_data],
        }

        result = agent.execute(agent_input)

        # Extract the generated idea (agent returns list, we process one)
        ideas = result.get('ideas', [])
        if not ideas:
            raise ValueError("Agent did not generate any ideas from feature")

        generated = ideas[0]

        return NormalizedIdea(
            title=generated['title'],
            what_description=generated['what'],
            why_description=generated['why'],
            use_case_description=generated['use_case'],
            source_type=self.get_source_type(),
            source_metadata=self.extract_metadata(raw_input),
            product_id=product_id,
            submitter_id=None,  # Automated, no human submitter
            category=generated.get('category'),
            auto_categorized=True,
            raw_input=f"{feature.feature_name}: {feature.feature_description}",
            adaptation_notes=generated.get('adaptation_notes'),
        )

    def normalize_batch(
        self,
        product_id: int,
        feature_ids: List[int]
    ) -> List[NormalizedIdea]:
        """
        Normalize multiple features in a batch for efficiency.

        Uses single agent call to process all features.

        Args:
            product_id: Product ID
            feature_ids: List of feature IDs to process

        Returns:
            List of NormalizedIdea objects
        """
        # Get all features
        features = []
        for feature_id in feature_ids:
            feature = self._get_feature(feature_id)
            if feature:
                competitor = self._get_competitor(feature.product_competitor_id)
                if competitor:
                    features.append({
                        'id': feature.id,
                        'competitor_name': competitor.competitor_name,
                        'feature_name': feature.feature_name,
                        'feature_description': feature.feature_description,
                        'feature_category': feature.feature_category,
                        'source_url': feature.source_url,
                    })

        if not features:
            return []

        # Get product context
        product_context = self._get_product_context(product_id)

        # Use IdeaStructuringAgent for batch processing
        agent = IdeaStructuringAgent(
            db=self.db,
            llm_service=self.llm_service,
            product_id=product_id
        )

        agent_input = {
            'product_context': product_context,
            'features': features,
        }

        result = agent.execute(agent_input)

        # Convert results to NormalizedIdea objects
        normalized = []
        for generated in result.get('ideas', []):
            # Find corresponding feature
            feature_id = generated.get('feature_id')
            feature = self._get_feature(feature_id) if feature_id else None
            competitor = self._get_competitor(feature.product_competitor_id) if feature else None

            metadata = {
                'feature_id': feature_id,
                'competitor_id': competitor.id if competitor else None,
                'competitor_name': competitor.competitor_name if competitor else None,
                'original_feature_name': feature.feature_name if feature else None,
            }

            normalized.append(NormalizedIdea(
                title=generated['title'],
                what_description=generated['what'],
                why_description=generated['why'],
                use_case_description=generated['use_case'],
                source_type=self.get_source_type(),
                source_metadata=metadata,
                product_id=product_id,
                submitter_id=None,
                category=generated.get('category'),
                auto_categorized=True,
                raw_input=f"{feature.feature_name}: {feature.feature_description}" if feature else None,
                adaptation_notes=generated.get('adaptation_notes'),
            ))

        return normalized

    def _get_feature(self, feature_id: int) -> Optional[ProductCompetitorFeature]:
        """Get feature by ID."""
        return self.db.query(ProductCompetitorFeature).filter(
            ProductCompetitorFeature.id == feature_id
        ).first()

    def _get_competitor(self, competitor_id: int) -> Optional[ProductCompetitor]:
        """Get competitor by ID."""
        return self.db.query(ProductCompetitor).filter(
            ProductCompetitor.id == competitor_id
        ).first()

    def _get_product_context(self, product_id: int) -> Dict[str, Any]:
        """Get product context for AI adaptation."""
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
