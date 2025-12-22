"""
Feature Extraction Service

Manages feature extraction operations without Celery (simplified MVP version).
This version does sequential extraction - can be upgraded to parallel with Celery later.
"""

from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from difflib import SequenceMatcher
from app.models.competitor_intelligence import (
    CompetitorAnalysisSession,
    SessionCompetitor,
    CompetitorFeature,
    ProductCompetitorFeature
)
from app.agents.feature_extractor import FeatureExtractorAgent, FeatureDetailExpanderAgent
from app.services.llm_service import LLMService
import asyncio


class FeatureExtractionService:
    """Service for managing feature extraction operations"""

    def __init__(self, db: Session):
        self.db = db

    async def extract_features_for_session(
        self,
        session_id: int,
        llm_service: LLMService,
        reuse_existing: bool = False
    ) -> Dict:
        """
        Extract features for all selected competitors in a session.
        Sequential processing (simplified MVP - no Celery).

        Args:
            session_id: Session ID
            llm_service: LLM service for AI extraction
            reuse_existing: If True, reuse existing ProductCompetitorFeature without AI extraction
        """
        # Get session
        session = self.db.query(CompetitorAnalysisSession).filter(
            CompetitorAnalysisSession.id == session_id
        ).first()

        if not session:
            raise ValueError("Session not found")

        # Get selected competitors
        competitors = self.db.query(SessionCompetitor).filter(
            SessionCompetitor.session_id == session_id,
            SessionCompetitor.selected_by_user == True
        ).all()

        if not competitors:
            raise ValueError("No competitors selected")

        # Determine if comparison mode
        compare_to_previous = session.analysis_type == "differential"

        # Extract features for each competitor
        results = []
        for competitor in competitors:
            result = await self._extract_features_for_competitor(
                session_competitor=competitor,
                session_id=session_id,
                compare_to_previous=compare_to_previous,
                llm_service=llm_service,
                reuse_existing=reuse_existing
            )
            results.append(result)

        return {
            'status': 'completed',
            'total_competitors': len(competitors),
            'completed_competitors': len(results),
            'comparison_mode': compare_to_previous,
            'results': results
        }

    async def _extract_features_for_competitor(
        self,
        session_competitor: SessionCompetitor,
        session_id: int,
        compare_to_previous: bool,
        llm_service: LLMService,
        reuse_existing: bool = False
    ) -> Dict:
        """
        Extract features for a single competitor.

        Supports three modes:
        1. Product-scoped reuse: Reuse from the same ProductCompetitor (same product, same competitor)
        2. Cross-product reuse: Reuse from a ProductCompetitor with the same competitor name in another product
        3. Fresh extraction: Run AI extraction

        Args:
            session_competitor: Competitor to extract features for
            session_id: Current session ID
            compare_to_previous: Whether to compare to previous analysis
            llm_service: LLM service for AI extraction
            reuse_existing: If True, copy existing ProductCompetitorFeature without AI extraction
        """
        # Check if we should reuse existing features
        if reuse_existing and session_competitor.product_competitor_id:
            # First try: product-scoped features (same ProductCompetitor)
            existing_features = self._load_product_competitor_features(
                product_competitor_id=session_competitor.product_competitor_id
            )

            if existing_features:
                # Copy existing features to session-specific CompetitorFeature
                feature_ids = self._copy_existing_features(
                    session_competitor_id=session_competitor.id,
                    session_id=session_id,
                    existing_features=existing_features,
                    is_comparative=compare_to_previous,
                    link_product_feature=True  # Link to ProductCompetitorFeature
                )

                return {
                    'competitor_id': session_competitor.id,
                    'competitor_name': session_competitor.competitor_name,
                    'feature_count': len(feature_ids),
                    'change_summary': None,
                    'status': 'reused',
                    'reused': True
                }
            else:
                # Second try: cross-product features (same competitor name in other products)
                cross_product_features = self._load_cross_product_features(
                    competitor_name=session_competitor.competitor_name,
                    current_product_id=session_competitor.session.product_id
                )

                if cross_product_features:
                    # Copy cross-product features (don't link to ProductCompetitorFeature)
                    feature_ids = self._copy_existing_features(
                        session_competitor_id=session_competitor.id,
                        session_id=session_id,
                        existing_features=cross_product_features,
                        is_comparative=compare_to_previous,
                        link_product_feature=False  # Don't link (belongs to different ProductCompetitor)
                    )

                    return {
                        'competitor_id': session_competitor.id,
                        'competitor_name': session_competitor.competitor_name,
                        'feature_count': len(feature_ids),
                        'change_summary': None,
                        'status': 'reused',
                        'reused': True
                    }

        # Otherwise, run AI extraction as normal
        # Load previous features if comparison enabled
        previous_features = None
        if compare_to_previous and session_competitor.product_competitor_id:
            previous_features = self._load_previous_features(
                product_competitor_id=session_competitor.product_competitor_id,
                current_session_id=session_id
            )

        # Execute feature extraction agent
        agent = FeatureExtractorAgent(
            db=self.db,
            llm_service=llm_service,
            session_id=session_id,
            product_id=session_competitor.session.product_id
        )

        agent_result = agent.execute({
            'competitor_name': session_competitor.competitor_name,
            'competitor_url': session_competitor.competitor_url,
            'previous_features': previous_features
        })

        # Store extracted features
        feature_ids = self._store_features(
            session_competitor_id=session_competitor.id,
            session_id=session_id,
            features_data=agent_result['features'],
            is_comparative=compare_to_previous
        )

        return {
            'competitor_id': session_competitor.id,
            'competitor_name': session_competitor.competitor_name,
            'feature_count': len(feature_ids),
            'change_summary': agent_result.get('summary', None),
            'status': 'completed',
            'reused': False
        }

    def _load_product_competitor_features(
        self,
        product_competitor_id: int
    ) -> Optional[List['ProductCompetitorFeature']]:
        """Load persistent ProductCompetitorFeature records for product-scoped reuse."""
        features = self.db.query(ProductCompetitorFeature).filter(
            ProductCompetitorFeature.product_competitor_id == product_competitor_id,
            ProductCompetitorFeature.status == 'active'
        ).all()

        return features if features else None

    def _load_cross_product_features(
        self,
        competitor_name: str,
        current_product_id: int
    ) -> Optional[List['ProductCompetitorFeature']]:
        """
        Load ProductCompetitorFeature records for the same competitor from OTHER products.
        This enables cross-product feature reuse.
        """
        from app.models.competitor_intelligence import ProductCompetitor

        # Find ProductCompetitor records with same name in other products
        other_product_competitors = self.db.query(ProductCompetitor).filter(
            ProductCompetitor.product_id != current_product_id,
            ProductCompetitor.competitor_name == competitor_name,
            ProductCompetitor.status == 'active'
        ).all()

        if not other_product_competitors:
            return None

        # Collect features from any matching ProductCompetitor
        all_features = []
        for pc in other_product_competitors:
            features = self.db.query(ProductCompetitorFeature).filter(
                ProductCompetitorFeature.product_competitor_id == pc.id,
                ProductCompetitorFeature.status == 'active'
            ).all()

            if features:
                all_features.extend(features)
                break  # Use features from first match

        return all_features if all_features else None

    def _copy_existing_features(
        self,
        session_competitor_id: int,
        session_id: int,
        existing_features: List['ProductCompetitorFeature'],
        is_comparative: bool = False,
        link_product_feature: bool = True
    ) -> List[int]:
        """
        Copy existing ProductCompetitorFeature records to session-specific CompetitorFeature.
        This avoids running AI extraction when reusing features from previous extractions
        or from cross-product feature reuse.

        Args:
            session_competitor_id: Session competitor ID
            session_id: Current session ID
            existing_features: Features to copy
            is_comparative: If True, don't mark as new (in comparative mode). If False, mark as new.
            link_product_feature: If True, link to the ProductCompetitorFeature. If False (cross-product),
                                 copy but don't link (since it belongs to a different ProductCompetitor).
        """
        feature_ids = []

        for product_feature in existing_features:
            # For first extraction (not comparative), mark reused features as 'new'
            change_type = None if is_comparative else 'new'

            # Create session-specific feature copy
            competitor_feature = CompetitorFeature(
                session_competitor_id=session_competitor_id,
                product_feature_id=product_feature.id if link_product_feature else None,
                feature_name=product_feature.feature_name,
                feature_description=product_feature.feature_description,
                feature_category=product_feature.feature_category,
                extraction_confidence=0.9,  # High confidence since it's existing data
                source_url=None,
                raw_context=None,
                change_type=change_type,
                change_description=None,
                comparison_to_feature_id=None,
                selected_by_user=False,
                detail_requested=False
            )

            self.db.add(competitor_feature)
            self.db.flush()

            feature_ids.append(competitor_feature.id)

        # Update last_seen for all copied features
        for product_feature in existing_features:
            product_feature.last_seen_session_id = session_id

        self.db.commit()
        return feature_ids

    def _load_previous_features(
        self,
        product_competitor_id: int,
        current_session_id: int
    ) -> Optional[List[Dict]]:
        """Load features from previous analysis for comparison."""
        # Get most recent previous session for this competitor
        previous_features = self.db.query(CompetitorFeature).join(
            SessionCompetitor
        ).filter(
            SessionCompetitor.product_competitor_id == product_competitor_id,
            SessionCompetitor.session_id != current_session_id,
            SessionCompetitor.selected_by_user == True
        ).order_by(
            SessionCompetitor.created_at.desc()
        ).limit(50).all()  # Limit to most recent 50 features

        if not previous_features:
            return None

        return [
            {
                'id': str(feat.id),
                'name': feat.feature_name,
                'description': feat.feature_description,
                'category': feat.feature_category
            }
            for feat in previous_features
        ]

    def _store_features(
        self,
        session_competitor_id: int,
        session_id: int,
        features_data: List[Dict],
        is_comparative: bool
    ) -> List[int]:
        """Store extracted features in database."""
        feature_ids = []

        session_competitor = self.db.query(SessionCompetitor).filter(
            SessionCompetitor.id == session_competitor_id
        ).first()

        for feat_data in features_data:
            # Create or update product-level feature
            product_feature = None
            if session_competitor.product_competitor_id:
                product_feature = self._get_or_create_product_feature(
                    product_competitor_id=session_competitor.product_competitor_id,
                    feature_name=feat_data['name'],
                    feature_description=feat_data['description'],
                    feature_category=feat_data['category'],
                    session_id=session_id
                )

            # Create session-specific feature
            # For first extraction (not comparative), mark all features as 'new'
            change_type = None
            if is_comparative:
                change_type = feat_data.get('change_type')
            else:
                # First extraction - all features are new
                change_type = 'new'

            competitor_feature = CompetitorFeature(
                session_competitor_id=session_competitor_id,
                product_feature_id=product_feature.id if product_feature else None,
                feature_name=feat_data['name'],
                feature_description=feat_data['description'],
                feature_category=feat_data['category'],
                extraction_confidence=feat_data.get('confidence', 0.8),
                source_url=feat_data.get('source_url'),
                raw_context=feat_data.get('raw_context'),
                change_type=change_type,
                change_description=feat_data.get('change_description'),
                comparison_to_feature_id=int(feat_data['previous_feature_id']) if feat_data.get('previous_feature_id') else None,
                selected_by_user=False,
                detail_requested=False
            )

            self.db.add(competitor_feature)
            self.db.flush()

            feature_ids.append(competitor_feature.id)

        self.db.commit()
        return feature_ids

    def _get_or_create_product_feature(
        self,
        product_competitor_id: int,
        feature_name: str,
        feature_description: str,
        feature_category: str,
        session_id: int
    ) -> 'ProductCompetitorFeature':
        """Get or create product-level feature."""
        # Try to find existing by name
        existing = self.db.query(ProductCompetitorFeature).filter(
            ProductCompetitorFeature.product_competitor_id == product_competitor_id,
            ProductCompetitorFeature.feature_name == feature_name
        ).first()

        if existing:
            # Update last_seen
            existing.last_seen_session_id = session_id
            existing.feature_description = feature_description  # Update description
            existing.status = "active"
            self.db.commit()
            return existing

        # Create new
        product_feature = ProductCompetitorFeature(
            product_competitor_id=product_competitor_id,
            feature_name=feature_name,
            feature_description=feature_description,
            feature_category=feature_category,
            first_discovered_session_id=session_id,
            last_seen_session_id=session_id,
            status="active"
        )

        self.db.add(product_feature)
        self.db.commit()
        self.db.refresh(product_feature)

        return product_feature

    def _normalize_feature_name(self, name: str) -> str:
        """Normalize a feature name for comparison (lowercase, strip whitespace)."""
        return name.lower().strip()

    def _similarity_ratio(self, str1: str, str2: str) -> float:
        """Calculate similarity ratio between two strings (0.0 to 1.0)."""
        return SequenceMatcher(None, str1, str2).ratio()

    def _deduplicate_features(self, features_list: List[Dict]) -> List[Dict]:
        """
        Deduplicate features by combining those with similar names.
        Preserves all source URLs and descriptions from duplicates.

        Args:
            features_list: List of feature dicts

        Returns:
            Deduplicated list of features with combined source URLs
        """
        if not features_list:
            return []

        # Track processed features
        deduplicated = []
        processed_indices = set()

        for i, feature in enumerate(features_list):
            if i in processed_indices:
                continue

            current_feature = feature.copy()
            # Initialize source_urls list (may be None or single URL)
            source_urls = []
            if feature.get('source_url'):
                source_urls.append(feature['source_url'])

            # Collect descriptions from duplicates
            descriptions = [feature['description']] if feature.get('description') else []

            # Find similar features and merge them
            normalized_current = self._normalize_feature_name(feature['name'])

            for j in range(i + 1, len(features_list)):
                if j in processed_indices:
                    continue

                other_feature = features_list[j]
                normalized_other = self._normalize_feature_name(other_feature['name'])

                # Use 0.85 similarity threshold (features should be very similar)
                similarity = self._similarity_ratio(normalized_current, normalized_other)
                if similarity >= 0.85:
                    # Mark as processed and merge
                    processed_indices.add(j)

                    if other_feature.get('source_url') and other_feature['source_url'] not in source_urls:
                        source_urls.append(other_feature['source_url'])

                    if other_feature.get('description') and other_feature['description'] not in descriptions:
                        descriptions.append(other_feature['description'])

            # Update feature with deduplicated data
            if source_urls:
                # If multiple sources, combine them into a comma-separated string
                current_feature['source_url'] = ', '.join(source_urls)

            if descriptions:
                # If multiple descriptions, combine them with a separator
                if len(descriptions) > 1:
                    current_feature['description'] = ' | '.join(descriptions)
                else:
                    current_feature['description'] = descriptions[0]

            deduplicated.append(current_feature)
            processed_indices.add(i)

        return deduplicated

    async def get_session_features(
        self,
        session_id: int,
        include_unselected: bool = True
    ) -> Dict:
        """
        Get all features for a session, grouped by competitor.
        Features are deduplicated per competitor (combining similar features from multiple sources).
        """
        query = self.db.query(CompetitorFeature).join(
            SessionCompetitor
        ).filter(
            SessionCompetitor.session_id == session_id
        )

        if not include_unselected:
            query = query.filter(SessionCompetitor.selected_by_user == True)

        features = query.all()

        # Group by competitor
        by_competitor = {}
        change_stats = {
            'new': 0,
            'modified': 0,
            'unchanged': 0,
            'removed': 0,
            'total': len(features)
        }

        for feature in features:
            comp_id = str(feature.session_competitor_id)

            if comp_id not in by_competitor:
                by_competitor[comp_id] = {
                    'competitor_id': comp_id,
                    'competitor_name': feature.session_competitor.competitor_name,
                    'competitor_url': feature.session_competitor.competitor_url,
                    'features': []
                }

            by_competitor[comp_id]['features'].append({
                'id': str(feature.id),
                'name': feature.feature_name,
                'description': feature.feature_description,
                'category': feature.feature_category,
                'confidence': float(feature.extraction_confidence) if feature.extraction_confidence else None,
                'source_url': feature.source_url,
                'change_type': feature.change_type,
                'change_description': feature.change_description,
                'selected': feature.selected_by_user,
                'has_details': feature.detail_requested and feature.expanded_description is not None
            })

            # Track change stats
            if feature.change_type:
                change_stats[feature.change_type] = change_stats.get(feature.change_type, 0) + 1

        # Deduplicate features per competitor
        for competitor in by_competitor.values():
            competitor['features'] = self._deduplicate_features(competitor['features'])

        return {
            'features_by_competitor': list(by_competitor.values()),
            'change_stats': change_stats
        }

    async def expand_feature_details(
        self,
        feature_id: int,
        llm_service: LLMService
    ) -> Dict:
        """
        Get expanded details for a specific feature using AI.
        """
        feature = self.db.query(CompetitorFeature).filter(
            CompetitorFeature.id == feature_id
        ).first()

        if not feature:
            raise ValueError("Feature not found")

        # Check if already expanded
        if feature.expanded_description:
            return {
                'feature_id': str(feature_id),
                'expanded_description': feature.expanded_description,
                'cached': True
            }

        # Use agent to expand
        agent = FeatureDetailExpanderAgent(
            db=self.db,
            llm_service=llm_service,
            session_id=feature.session_competitor.session_id,
            product_id=feature.session_competitor.session.product_id
        )

        result = await agent.execute({
            'feature_name': feature.feature_name,
            'feature_description': feature.feature_description,
            'competitor_name': feature.session_competitor.competitor_name,
            'competitor_url': feature.session_competitor.competitor_url
        })

        # Store expanded description (just the main description for now)
        feature.expanded_description = result['expanded_description']
        feature.detail_requested = True
        self.db.commit()

        return {
            'feature_id': str(feature_id),
            **result,
            'cached': False
        }

    async def select_features(
        self,
        session_id: int,
        feature_ids: List[int]
    ) -> Dict:
        """
        User selects which features to use for idea generation.
        """
        # Reset all selections for this session
        # Get all feature IDs for this session first (can't use update with join)
        feature_ids_to_reset = self.db.query(CompetitorFeature.id).join(
            SessionCompetitor
        ).filter(
            SessionCompetitor.session_id == session_id
        ).all()

        feature_ids_to_reset = [f[0] for f in feature_ids_to_reset]

        if feature_ids_to_reset:
            self.db.query(CompetitorFeature).filter(
                CompetitorFeature.id.in_(feature_ids_to_reset)
            ).update({"selected_by_user": False}, synchronize_session=False)

        # Set selected features
        if feature_ids:
            self.db.query(CompetitorFeature).filter(
                CompetitorFeature.id.in_(feature_ids)
            ).update({"selected_by_user": True}, synchronize_session=False)

        self.db.commit()

        return {
            'selected_count': len(feature_ids)
        }
