"""
Landscape Opportunity Adapter.

Converts feature opportunities from landscape synthesis reports
into product-specific ideas.

Phase 3: Idea Normalization + Triage
"""

from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from app.adapters.base import BaseSourceAdapter, NormalizedIdea
from app.models.idea import SourceType
from app.models.competitive_reports import LandscapeOpportunityReport
from app.models.competitor_intelligence import CIProduct


class LandscapeOpportunityAdapter(BaseSourceAdapter):
    """
    Adapter for converting landscape feature opportunities into ideas.

    Feature opportunities come from the LandscapeOpportunitySynthesizerAgent
    and represent identified gaps in the competitive landscape.
    """

    def __init__(self, db: Session):
        """
        Initialize the adapter.

        Args:
            db: Database session
        """
        self.db = db

    def get_source_type(self) -> SourceType:
        return SourceType.COMPETITOR_AUTOMATED

    def get_required_fields(self) -> list:
        return ['product_id', 'opportunity_index']

    def validate_input(self, raw_input: Dict[str, Any]) -> bool:
        """
        Validate landscape opportunity input.

        Valid if has product_id and opportunity_index.
        """
        return (
            'product_id' in raw_input and
            'opportunity_index' in raw_input and
            isinstance(raw_input.get('opportunity_index'), int)
        )

    def extract_metadata(self, raw_input: Dict[str, Any]) -> Dict[str, Any]:
        """Extract landscape opportunity metadata."""
        opportunity = raw_input.get('opportunity', {})

        return {
            'source': 'landscape_synthesis',
            'opportunity_index': raw_input.get('opportunity_index'),
            'feature_name': opportunity.get('feature_name'),
            'priority_score': opportunity.get('priority_score'),
            'competitors_with_feature': opportunity.get('competitors_with_feature', []),
            'market_context': opportunity.get('market_context'),
            'source_evidence': opportunity.get('source_evidence', []),
            'landscape_report_id': raw_input.get('landscape_report_id'),
        }

    def normalize(self, raw_input: Dict[str, Any]) -> NormalizedIdea:
        """
        Normalize landscape opportunity to NormalizedIdea.

        Args:
            raw_input: Dictionary with product_id, opportunity_index, and optionally opportunity data

        Returns:
            NormalizedIdea

        Raises:
            ValueError: If input is invalid or opportunity not found
        """
        if not self.validate_input(raw_input):
            raise ValueError("Invalid input: requires product_id and opportunity_index")

        product_id = raw_input['product_id']
        opportunity_index = raw_input['opportunity_index']

        # If opportunity data is provided directly, use it
        if 'opportunity' in raw_input:
            opportunity = raw_input['opportunity']
        else:
            # Otherwise fetch from the landscape report
            report = self.db.query(LandscapeOpportunityReport).filter(
                LandscapeOpportunityReport.product_id == product_id
            ).first()

            if not report:
                raise ValueError(f"No landscape report found for product {product_id}")

            if not report.feature_opportunities:
                raise ValueError("No feature opportunities in landscape report")

            if opportunity_index < 0 or opportunity_index >= len(report.feature_opportunities):
                raise ValueError(
                    f"Invalid opportunity index {opportunity_index}. "
                    f"Valid range: 0-{len(report.feature_opportunities) - 1}"
                )

            opportunity = report.feature_opportunities[opportunity_index]
            raw_input['landscape_report_id'] = report.id

        # Store opportunity in raw_input for metadata extraction
        raw_input['opportunity'] = opportunity

        return NormalizedIdea(
            title=f"Add: {opportunity.get('feature_name', 'Unknown Feature')}",
            what_description=opportunity.get('summary', ''),
            why_description=opportunity.get('user_value', ''),
            use_case_description=opportunity.get('market_context', ''),
            source_type=self.get_source_type(),
            source_metadata=self.extract_metadata(raw_input),
            product_id=product_id,
            submitter_id=None,  # Automated, no human submitter
            category=None,  # Will be set by triage
            auto_categorized=False,
            raw_input=f"{opportunity.get('feature_name', '')}: {opportunity.get('summary', '')}",
            adaptation_notes=self._build_adaptation_notes(opportunity),
        )

    def normalize_batch(
        self,
        product_id: int,
        opportunity_indices: List[int]
    ) -> List[NormalizedIdea]:
        """
        Normalize multiple opportunities from a landscape report.

        Args:
            product_id: Product ID
            opportunity_indices: List of opportunity indices to process

        Returns:
            List of NormalizedIdea objects
        """
        # Get the landscape report
        report = self.db.query(LandscapeOpportunityReport).filter(
            LandscapeOpportunityReport.product_id == product_id
        ).first()

        if not report or not report.feature_opportunities:
            return []

        normalized = []
        max_index = len(report.feature_opportunities) - 1

        for idx in opportunity_indices:
            if idx < 0 or idx > max_index:
                continue

            opportunity = report.feature_opportunities[idx]

            raw_input = {
                'product_id': product_id,
                'opportunity_index': idx,
                'opportunity': opportunity,
                'landscape_report_id': report.id,
            }

            normalized.append(NormalizedIdea(
                title=f"Add: {opportunity.get('feature_name', 'Unknown Feature')}",
                what_description=opportunity.get('summary', ''),
                why_description=opportunity.get('user_value', ''),
                use_case_description=opportunity.get('market_context', ''),
                source_type=self.get_source_type(),
                source_metadata=self.extract_metadata(raw_input),
                product_id=product_id,
                submitter_id=None,
                category=None,
                auto_categorized=False,
                raw_input=f"{opportunity.get('feature_name', '')}: {opportunity.get('summary', '')}",
                adaptation_notes=self._build_adaptation_notes(opportunity),
            ))

        return normalized

    def normalize_all(self, product_id: int) -> List[NormalizedIdea]:
        """
        Normalize all opportunities from a landscape report.

        Args:
            product_id: Product ID

        Returns:
            List of NormalizedIdea objects for all opportunities
        """
        report = self.db.query(LandscapeOpportunityReport).filter(
            LandscapeOpportunityReport.product_id == product_id
        ).first()

        if not report or not report.feature_opportunities:
            return []

        indices = list(range(len(report.feature_opportunities)))
        return self.normalize_batch(product_id, indices)

    def _build_adaptation_notes(self, opportunity: Dict[str, Any]) -> str:
        """
        Build adaptation notes from opportunity data.

        Args:
            opportunity: Feature opportunity dictionary

        Returns:
            Adaptation notes string
        """
        notes_parts = []

        # Priority score
        if opportunity.get('priority_score') is not None:
            notes_parts.append(f"Priority Score: {opportunity['priority_score']:.2f}")

        # Competitors with this feature
        competitors = opportunity.get('competitors_with_feature', [])
        if competitors:
            notes_parts.append(f"Competitors with feature: {', '.join(competitors)}")

        # Source evidence
        evidence = opportunity.get('source_evidence', [])
        if evidence:
            evidence_str = "; ".join(evidence[:2])  # Limit to 2 pieces
            notes_parts.append(f"Evidence: {evidence_str}")

        return " | ".join(notes_parts) if notes_parts else ""

    def get_high_priority_opportunities(
        self,
        product_id: int,
        min_score: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Get high-priority opportunities that haven't been converted to ideas yet.

        Args:
            product_id: Product ID
            min_score: Minimum priority score (default 0.7)

        Returns:
            List of opportunity dictionaries with indices
        """
        report = self.db.query(LandscapeOpportunityReport).filter(
            LandscapeOpportunityReport.product_id == product_id
        ).first()

        if not report or not report.feature_opportunities:
            return []

        high_priority = []
        for idx, opp in enumerate(report.feature_opportunities):
            score = opp.get('priority_score', 0)
            if score >= min_score:
                high_priority.append({
                    'index': idx,
                    'feature_name': opp.get('feature_name'),
                    'priority_score': score,
                    'summary': opp.get('summary'),
                    'competitors_with_feature': opp.get('competitors_with_feature', []),
                })

        # Sort by priority score descending
        high_priority.sort(key=lambda x: x.get('priority_score', 0), reverse=True)

        return high_priority
