"""
Competitor Gap Adapter.

Converts individual competitor gaps from functional audit reports
into product-specific ideas.

Phase 3: Idea Normalization + Triage
"""

from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from app.adapters.base import BaseSourceAdapter, NormalizedIdea
from app.models.idea import SourceType
from app.models.competitive_reports import CompetitorFunctionalReport
from app.models.competitor_intelligence import ProductCompetitor


class CompetitorGapAdapter(BaseSourceAdapter):
    """
    Adapter for converting individual competitor gaps into ideas.

    Competitor gaps come from the CompetitorFunctionalAuditAgent
    and represent specific features that a competitor has but we don't.

    This adapter allows creating ideas from individual gaps in a
    competitor functional report, separate from the landscape synthesis.
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
        return ['product_id', 'competitor_id', 'gap_index']

    def validate_input(self, raw_input: Dict[str, Any]) -> bool:
        """
        Validate competitor gap input.

        Valid if has product_id, competitor_id, and gap_index.
        """
        return (
            'product_id' in raw_input and
            'competitor_id' in raw_input and
            'gap_index' in raw_input and
            isinstance(raw_input.get('gap_index'), int)
        )

    def extract_metadata(self, raw_input: Dict[str, Any]) -> Dict[str, Any]:
        """Extract competitor gap metadata."""
        gap = raw_input.get('gap', {})

        return {
            'source': 'competitor_gap',
            'competitor_id': raw_input.get('competitor_id'),
            'competitor_name': raw_input.get('competitor_name'),
            'gap_index': raw_input.get('gap_index'),
            'feature_name': gap.get('feature_name'),
            'user_problem': gap.get('user_problem'),
            'evidence': gap.get('evidence'),
            'functional_report_id': raw_input.get('functional_report_id'),
        }

    def normalize(self, raw_input: Dict[str, Any]) -> NormalizedIdea:
        """
        Normalize competitor gap to NormalizedIdea.

        Args:
            raw_input: Dictionary with product_id, competitor_id, gap_index,
                       and optionally gap data

        Returns:
            NormalizedIdea

        Raises:
            ValueError: If input is invalid or gap not found
        """
        if not self.validate_input(raw_input):
            raise ValueError("Invalid input: requires product_id, competitor_id, and gap_index")

        product_id = raw_input['product_id']
        competitor_id = raw_input['competitor_id']
        gap_index = raw_input['gap_index']

        # If gap data is provided directly, use it
        if 'gap' in raw_input:
            gap = raw_input['gap']
            competitor_name = raw_input.get('competitor_name', 'Unknown Competitor')
        else:
            # Otherwise fetch from the functional report
            report = self.db.query(CompetitorFunctionalReport).filter(
                CompetitorFunctionalReport.product_competitor_id == competitor_id,
                CompetitorFunctionalReport.product_id == product_id
            ).first()

            if not report:
                raise ValueError(f"No functional report found for competitor {competitor_id}")

            if not report.gaps_deep_dive:
                raise ValueError("No gaps in functional report")

            if gap_index < 0 or gap_index >= len(report.gaps_deep_dive):
                raise ValueError(
                    f"Invalid gap index {gap_index}. "
                    f"Valid range: 0-{len(report.gaps_deep_dive) - 1}"
                )

            gap = report.gaps_deep_dive[gap_index]
            raw_input['functional_report_id'] = report.id

            # Get competitor name
            competitor = self.db.query(ProductCompetitor).filter(
                ProductCompetitor.id == competitor_id
            ).first()
            competitor_name = competitor.competitor_name if competitor else 'Unknown Competitor'
            raw_input['competitor_name'] = competitor_name

        # Store gap in raw_input for metadata extraction
        raw_input['gap'] = gap

        feature_name = gap.get('feature_name', 'Unknown Feature')
        user_problem = gap.get('user_problem', '')
        evidence = gap.get('evidence', '')

        return NormalizedIdea(
            title=f"Add: {feature_name}",
            what_description=f"Implement {feature_name} similar to {competitor_name}'s offering.",
            why_description=user_problem,
            use_case_description=f"Based on competitive analysis of {competitor_name}: {evidence}",
            source_type=self.get_source_type(),
            source_metadata=self.extract_metadata(raw_input),
            product_id=product_id,
            submitter_id=None,  # Automated, no human submitter
            category=None,  # Will be set by triage
            auto_categorized=False,
            raw_input=f"{feature_name}: {user_problem}",
            adaptation_notes=self._build_adaptation_notes(gap, competitor_name),
        )

    def normalize_batch(
        self,
        product_id: int,
        competitor_id: int,
        gap_indices: List[int]
    ) -> List[NormalizedIdea]:
        """
        Normalize multiple gaps from a competitor functional report.

        Args:
            product_id: Product ID
            competitor_id: Competitor ID
            gap_indices: List of gap indices to process

        Returns:
            List of NormalizedIdea objects
        """
        # Get the functional report
        report = self.db.query(CompetitorFunctionalReport).filter(
            CompetitorFunctionalReport.product_competitor_id == competitor_id,
            CompetitorFunctionalReport.product_id == product_id
        ).first()

        if not report or not report.gaps_deep_dive:
            return []

        # Get competitor name
        competitor = self.db.query(ProductCompetitor).filter(
            ProductCompetitor.id == competitor_id
        ).first()
        competitor_name = competitor.competitor_name if competitor else 'Unknown Competitor'

        normalized = []
        max_index = len(report.gaps_deep_dive) - 1

        for idx in gap_indices:
            if idx < 0 or idx > max_index:
                continue

            gap = report.gaps_deep_dive[idx]

            raw_input = {
                'product_id': product_id,
                'competitor_id': competitor_id,
                'gap_index': idx,
                'gap': gap,
                'competitor_name': competitor_name,
                'functional_report_id': report.id,
            }

            feature_name = gap.get('feature_name', 'Unknown Feature')
            user_problem = gap.get('user_problem', '')
            evidence = gap.get('evidence', '')

            normalized.append(NormalizedIdea(
                title=f"Add: {feature_name}",
                what_description=f"Implement {feature_name} similar to {competitor_name}'s offering.",
                why_description=user_problem,
                use_case_description=f"Based on competitive analysis of {competitor_name}: {evidence}",
                source_type=self.get_source_type(),
                source_metadata=self.extract_metadata(raw_input),
                product_id=product_id,
                submitter_id=None,
                category=None,
                auto_categorized=False,
                raw_input=f"{feature_name}: {user_problem}",
                adaptation_notes=self._build_adaptation_notes(gap, competitor_name),
            ))

        return normalized

    def normalize_all(
        self,
        product_id: int,
        competitor_id: int
    ) -> List[NormalizedIdea]:
        """
        Normalize all gaps from a competitor functional report.

        Args:
            product_id: Product ID
            competitor_id: Competitor ID

        Returns:
            List of NormalizedIdea objects for all gaps
        """
        report = self.db.query(CompetitorFunctionalReport).filter(
            CompetitorFunctionalReport.product_competitor_id == competitor_id,
            CompetitorFunctionalReport.product_id == product_id
        ).first()

        if not report or not report.gaps_deep_dive:
            return []

        indices = list(range(len(report.gaps_deep_dive)))
        return self.normalize_batch(product_id, competitor_id, indices)

    def _build_adaptation_notes(self, gap: Dict[str, Any], competitor_name: str) -> str:
        """
        Build adaptation notes from gap data.

        Args:
            gap: Gap dictionary from functional report
            competitor_name: Name of the competitor

        Returns:
            Adaptation notes string
        """
        notes_parts = [f"Source: {competitor_name} Functional Audit"]

        # Feature name
        if gap.get('feature_name'):
            notes_parts.append(f"Feature: {gap['feature_name']}")

        # Evidence summary
        evidence = gap.get('evidence', '')
        if evidence:
            # Truncate if too long
            if len(evidence) > 100:
                evidence = evidence[:97] + "..."
            notes_parts.append(f"Evidence: {evidence}")

        return " | ".join(notes_parts)

    def get_gaps_for_competitor(
        self,
        product_id: int,
        competitor_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get all gaps for a competitor with their indices.

        Args:
            product_id: Product ID
            competitor_id: Competitor ID

        Returns:
            List of gap dictionaries with indices
        """
        report = self.db.query(CompetitorFunctionalReport).filter(
            CompetitorFunctionalReport.product_competitor_id == competitor_id,
            CompetitorFunctionalReport.product_id == product_id
        ).first()

        if not report or not report.gaps_deep_dive:
            return []

        gaps = []
        for idx, gap in enumerate(report.gaps_deep_dive):
            gaps.append({
                'index': idx,
                'feature_name': gap.get('feature_name'),
                'user_problem': gap.get('user_problem'),
                'evidence': gap.get('evidence'),
            })

        return gaps
