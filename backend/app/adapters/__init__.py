"""
Source adapters for idea normalization.

Each adapter converts a specific source type into a normalized idea format
that can be processed by the triage pipeline.

Phase 3: Idea Normalization + Triage
"""

from app.adapters.base import BaseSourceAdapter, NormalizedIdea
from app.adapters.customer_submission import CustomerSubmissionAdapter
from app.adapters.competitor_feature import CompetitorFeatureAdapter
from app.adapters.landscape_opportunity import LandscapeOpportunityAdapter
from app.adapters.competitor_gap import CompetitorGapAdapter

__all__ = [
    'BaseSourceAdapter',
    'NormalizedIdea',
    'CustomerSubmissionAdapter',
    'CompetitorFeatureAdapter',
    'LandscapeOpportunityAdapter',
    'CompetitorGapAdapter',
]
