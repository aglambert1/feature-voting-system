"""
Similarity Detector Service for idea duplicate detection.

Enhanced from vector_service with specific thresholds and confidence scoring
for the idea triage workflow.

Phase 3: Idea Normalization + Triage
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import text
import sqlite_vec
import enum

from app.services.vector_service import VectorService
from app.services.embedding_service import generate_embedding as _generate_embedding
from app.models.idea import Idea, IdeaStatus


class CompetitiveUrgency(str, enum.Enum):
    """
    Structured urgency levels for competitive context.

    These levels help PMs understand what the urgency means:
    - LOW: No competitors have this feature - potential differentiator
    - MEDIUM: 1-2 competitors have this feature - competitive parity
    - HIGH: 3+ competitors have this feature - catching up
    - CRITICAL: Most/all major competitors have this - table stakes
    """
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class CompetitiveUrgencyResult:
    """
    Structured competitive urgency with reasoning.

    Provides PMs with clear, deterministic urgency assessment.
    """
    urgency: CompetitiveUrgency
    competitor_count: int
    total_competitors_analyzed: int
    competitors_with_feature: List[str]
    reasoning: str

    def to_dict(self) -> dict:
        return {
            "urgency": self.urgency.value,
            "competitor_count": self.competitor_count,
            "total_competitors_analyzed": self.total_competitors_analyzed,
            "competitors_with_feature": self.competitors_with_feature,
            "reasoning": self.reasoning,
        }


@dataclass
class SimilarIdea:
    """Represents a similar idea found during duplicate detection."""
    idea_id: int
    title: str
    what_description: str
    similarity_score: float  # 0.0-1.0 (higher = more similar)
    is_duplicate: bool  # True if above duplicate threshold
    is_similar: bool  # True if above similar threshold


@dataclass
class SimilarityResult:
    """Result of similarity detection for an idea."""
    has_duplicates: bool
    has_similar: bool
    similar_ideas: List[SimilarIdea]
    best_match: Optional[SimilarIdea]
    recommendation: str  # "approve", "merge", "review"
    confidence: float  # 0.0-1.0


@dataclass
class ProductFeatureMatch:
    """Represents a matching product feature."""
    feature_id: int
    feature_name: str
    feature_description: str
    similarity_score: float  # 0.0-1.0 (higher = more similar)
    source_url: Optional[str] = None


@dataclass
class ProductFeatureMatchResult:
    """Result of product feature matching for an idea."""
    has_match: bool
    matches: List[ProductFeatureMatch]
    best_match: Optional[ProductFeatureMatch]


class SimilarityDetectorService:
    """
    Service for detecting duplicate and similar ideas using vector similarity.

    Thresholds (from spec):
    - 0.95+ similarity = Duplicate (recommend merge/reject)
    - 0.85+ similarity = Similar (recommend review)
    - Below 0.85 = Unique (recommend approve)
    """

    # Thresholds for similarity detection
    DUPLICATE_THRESHOLD = 0.95  # Almost certainly the same idea
    SIMILAR_THRESHOLD = 0.85    # Related but not duplicate
    FEATURE_EXISTS_THRESHOLD = 0.85  # Detection threshold for existing product features

    def __init__(self, db: Session):
        self.db = db

    def generate_embedding(self, text: str, input_type: str = "document") -> List[float]:
        """
        Generate embedding for text via Voyage AI API.

        Args:
            text: Text to embed (idea title + description)
            input_type: "document" for storage, "query" for search

        Returns:
            1024-dimensional embedding vector
        """
        return _generate_embedding(text, input_type=input_type)

    def _distance_to_similarity(self, distance: float) -> float:
        """
        Convert cosine distance to similarity score.

        Cosine distance: 0 = identical, 2 = opposite
        Similarity: 1 = identical, 0 = opposite

        Formula: similarity = 1 - (distance / 2)
        """
        return 1.0 - (distance / 2.0)

    def find_similar_ideas(
        self,
        query_embedding: List[float],
        product_id: int,
        exclude_idea_id: Optional[int] = None,
        limit: int = 10
    ) -> List[SimilarIdea]:
        """
        Find similar ideas in a product using vector similarity.

        Args:
            query_embedding: Embedding of the idea to compare
            product_id: Product to search within
            exclude_idea_id: ID of idea to exclude (if checking existing idea)
            limit: Maximum results to return

        Returns:
            List of SimilarIdea objects sorted by similarity (highest first)
        """
        # Use VectorService for the actual search
        raw_results = VectorService.find_similar(
            db=self.db,
            query_embedding=query_embedding,
            product_id=product_id,
            limit=limit + 1  # Get one extra in case we need to exclude
        )

        similar_ideas = []
        for idea_id, title, what_description, distance in raw_results:
            # Skip the excluded idea
            if exclude_idea_id and idea_id == exclude_idea_id:
                continue

            similarity = self._distance_to_similarity(distance)

            similar_ideas.append(SimilarIdea(
                idea_id=idea_id,
                title=title,
                what_description=what_description,
                similarity_score=similarity,
                is_duplicate=similarity >= self.DUPLICATE_THRESHOLD,
                is_similar=similarity >= self.SIMILAR_THRESHOLD,
            ))

        # Limit to requested number
        return similar_ideas[:limit]

    def detect_duplicates(
        self,
        idea_text: str,
        product_id: int,
        exclude_idea_id: Optional[int] = None
    ) -> SimilarityResult:
        """
        Detect duplicates for an idea based on its text content.

        Args:
            idea_text: Combined text of the idea (title + what + why + use_case)
            product_id: Product to search within
            exclude_idea_id: ID to exclude (when checking existing idea)

        Returns:
            SimilarityResult with duplicates, similar ideas, and recommendation
        """
        # Generate embedding for the idea
        embedding = self.generate_embedding(idea_text)

        # Find similar ideas
        similar_ideas = self.find_similar_ideas(
            query_embedding=embedding,
            product_id=product_id,
            exclude_idea_id=exclude_idea_id,
            limit=5
        )

        # Analyze results
        duplicates = [s for s in similar_ideas if s.is_duplicate]
        similar = [s for s in similar_ideas if s.is_similar and not s.is_duplicate]

        has_duplicates = len(duplicates) > 0
        has_similar = len(similar) > 0

        # Get best match
        best_match = similar_ideas[0] if similar_ideas else None

        # Determine recommendation and confidence
        if has_duplicates:
            recommendation = "merge"
            confidence = duplicates[0].similarity_score
        elif has_similar:
            recommendation = "review"
            # Confidence is lower when we're uncertain
            confidence = 0.5 + (similar[0].similarity_score - self.SIMILAR_THRESHOLD) / 2
        else:
            recommendation = "approve"
            # High confidence if no similar ideas found
            if best_match:
                confidence = 0.8 + (1.0 - best_match.similarity_score) * 0.2
            else:
                confidence = 0.95  # Very confident if no matches at all

        return SimilarityResult(
            has_duplicates=has_duplicates,
            has_similar=has_similar,
            similar_ideas=similar_ideas,
            best_match=best_match,
            recommendation=recommendation,
            confidence=confidence,
        )

    def detect_duplicates_for_idea(
        self,
        idea: Idea,
        exclude_self: bool = True
    ) -> SimilarityResult:
        """
        Detect duplicates for an existing Idea model instance.

        Args:
            idea: The Idea to check for duplicates
            exclude_self: Whether to exclude the idea itself from results

        Returns:
            SimilarityResult
        """
        # Combine idea text for embedding
        idea_text = f"{idea.title}\n\n{idea.what_description}\n\n{idea.why_description}\n\n{idea.use_case_description}"

        return self.detect_duplicates(
            idea_text=idea_text,
            product_id=idea.product_id,
            exclude_idea_id=idea.id if exclude_self else None
        )

    def store_idea_embedding(self, idea: Idea) -> None:
        """
        Store embedding for an idea in the vector store.

        Args:
            idea: The Idea to store embedding for
        """
        # Combine idea text for embedding
        idea_text = f"{idea.title}\n\n{idea.what_description}\n\n{idea.why_description}\n\n{idea.use_case_description}"

        # Generate embedding
        embedding = self.generate_embedding(idea_text)

        # Store using VectorService
        VectorService.store_embedding(
            db=self.db,
            idea_id=idea.id,
            embedding=embedding
        )

    # DEPRECATED: find_competitive_matches has been removed.
    # It used VectorService.find_similar_competitor_features and ProductCompetitorFeature
    # which are part of the legacy system.
    # Use find_competitive_matches_from_reports() instead, which reads from V2 functional reports.

    def find_competitive_matches_from_reports(
        self,
        idea_text: str,
        product_id: int,
        limit: int = 5,
        similarity_threshold: float = 0.5
    ) -> Dict[str, Any]:
        """
        Find competitor features that match an idea using CompetitorFunctionalReport data (V2).

        This method queries the V2 functional reports instead of the legacy
        ProductCompetitorFeature table, providing more accurate competitive
        context from the latest functional audits.

        Args:
            idea_text: Text of the idea to match
            product_id: Product to search competitors for
            limit: Maximum feature matches to return
            similarity_threshold: Minimum similarity score (0-1, default 0.5)

        Returns:
            Dict with:
            - matches: List of matching competitor features with similarity scores
            - urgency: CompetitiveUrgencyResult with structured assessment
        """
        from app.models.competitive_reports import CompetitorFunctionalReport
        from app.models.competitor_intelligence import ProductCompetitor

        # Get all functional reports for this product
        reports = self.db.query(CompetitorFunctionalReport).filter(
            CompetitorFunctionalReport.product_id == product_id
        ).all()

        # Count total competitors with reports (this is the denominator for V2)
        total_competitors = len(reports)

        if total_competitors == 0:
            # No functional reports - return empty result
            # Caller can fall back to legacy method if desired
            return {
                "matches": [],
                "urgency": CompetitiveUrgencyResult(
                    urgency=CompetitiveUrgency.LOW,
                    competitor_count=0,
                    total_competitors_analyzed=0,
                    competitors_with_feature=[],
                    reasoning="No functional reports available. Run competitive analysis first."
                ).to_dict()
            }

        # Generate embedding for the idea
        embedding = self.generate_embedding(idea_text)

        # Extract all features from functional_comparison arrays and match
        all_features = []
        competitor_names = {}

        for report in reports:
            # Get competitor name
            competitor = self.db.query(ProductCompetitor).filter(
                ProductCompetitor.id == report.product_competitor_id
            ).first()

            if not competitor:
                continue

            competitor_name = competitor.competitor_name
            competitor_names[report.product_competitor_id] = competitor_name

            # Extract features from functional_comparison
            functional_comparison = report.functional_comparison or []
            for feature in functional_comparison:
                # Only include features where competitor has the feature (Gap = they have it, we don't)
                # or Parity (both have it) - these are features the competitor offers
                mapping_status = feature.get('mapping_status', '')
                if mapping_status in ['Gap', 'Parity', 'Differentiator']:
                    all_features.append({
                        'competitor_id': report.product_competitor_id,
                        'competitor_name': competitor_name,
                        'feature_name': feature.get('competitor_feature_name', ''),
                        'feature_description': feature.get('functional_description', ''),
                        'feature_category': feature.get('feature_category', ''),
                        'mapping_status': mapping_status,
                    })

        # Match features using vector similarity
        matches = []
        competitors_with_feature = set()

        for feature in all_features:
            feature_text = f"{feature['feature_name']}\n{feature['feature_description']}"
            feature_embedding = self.generate_embedding(feature_text)

            # Calculate cosine similarity
            similarity = self._cosine_similarity(embedding, feature_embedding)

            if similarity >= similarity_threshold:
                matches.append({
                    'competitor_id': feature['competitor_id'],
                    'competitor_name': feature['competitor_name'],
                    'feature_name': feature['feature_name'],
                    'feature_description': feature['feature_description'],
                    'feature_category': feature['feature_category'],
                    'mapping_status': feature['mapping_status'],
                    'similarity_score': round(similarity, 3),
                })
                competitors_with_feature.add(feature['competitor_name'])

        # Sort by similarity and limit
        matches.sort(key=lambda x: x['similarity_score'], reverse=True)

        # Calculate structured urgency
        urgency_result = self._calculate_competitive_urgency(
            competitor_count=len(competitors_with_feature),
            total_competitors=total_competitors,
            competitors_with_feature=list(competitors_with_feature)
        )

        return {
            "matches": matches[:limit],
            "urgency": urgency_result.to_dict()
        }

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.

        Args:
            vec1: First embedding vector
            vec2: Second embedding vector

        Returns:
            Similarity score between 0 and 1
        """
        import numpy as np
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)

        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    # DEPRECATED: _text_based_feature_matching, store_competitor_feature_embedding,
    # and bulk_store_competitor_feature_embeddings have been removed.
    # Use find_competitive_matches_from_reports() which reads from V2 functional reports.

    def _calculate_competitive_urgency(
        self,
        competitor_count: int,
        total_competitors: int,
        competitors_with_feature: List[str]
    ) -> CompetitiveUrgencyResult:
        """
        Calculate structured competitive urgency based on competitor data.

        Urgency levels with clear PM meaning:
        - LOW (0 competitors): No one has this - potential differentiator opportunity
        - MEDIUM (1-2 competitors): Some competition - competitive parity consideration
        - HIGH (3+ competitors): Many have this - catching up to market
        - CRITICAL (>50% of competitors): Most/all have it - table stakes feature

        Args:
            competitor_count: Number of competitors with similar feature
            total_competitors: Total competitors being tracked
            competitors_with_feature: Names of competitors with the feature

        Returns:
            CompetitiveUrgencyResult with deterministic assessment
        """
        if competitor_count == 0:
            return CompetitiveUrgencyResult(
                urgency=CompetitiveUrgency.LOW,
                competitor_count=0,
                total_competitors_analyzed=total_competitors,
                competitors_with_feature=[],
                reasoning=f"None of the {total_competitors} tracked competitors have this feature. "
                         f"This could be a differentiator opportunity."
            )

        # Calculate what percentage of competitors have this feature
        percentage = (competitor_count / total_competitors * 100) if total_competitors > 0 else 0

        if percentage > 50 or competitor_count >= 4:
            # Critical: Most competitors have this - table stakes
            urgency = CompetitiveUrgency.CRITICAL
            reasoning = (
                f"{competitor_count} of {total_competitors} competitors ({percentage:.0f}%) have this feature. "
                f"This is likely a table stakes feature that customers expect. "
                f"Competitors: {', '.join(competitors_with_feature)}."
            )
        elif competitor_count >= 3:
            # High: 3+ competitors have this - catching up
            urgency = CompetitiveUrgency.HIGH
            reasoning = (
                f"{competitor_count} of {total_competitors} competitors have this feature. "
                f"Multiple competitors are offering this - consider prioritizing to stay competitive. "
                f"Competitors: {', '.join(competitors_with_feature)}."
            )
        elif competitor_count >= 1:
            # Medium: 1-2 competitors have this - competitive parity
            urgency = CompetitiveUrgency.MEDIUM
            reasoning = (
                f"{competitor_count} of {total_competitors} competitors have this feature. "
                f"Some competitive pressure exists. "
                f"Competitors: {', '.join(competitors_with_feature)}."
            )
        else:
            # Low: Edge case (should not hit due to count==0 check above)
            urgency = CompetitiveUrgency.LOW
            reasoning = "No competitors have this feature."

        return CompetitiveUrgencyResult(
            urgency=urgency,
            competitor_count=competitor_count,
            total_competitors_analyzed=total_competitors,
            competitors_with_feature=competitors_with_feature,
            reasoning=reasoning
        )

    def _text_similarity(self, text1: str, text2: str) -> float:
        """
        Simple word overlap similarity for basic matching.
        Used as fallback when embeddings aren't available.
        """
        words1 = set(text1.split())
        words2 = set(text2.split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union)

    # ============================================================================
    # Product Feature Matching (Detect if idea overlaps with existing feature)
    # ============================================================================

    def find_product_feature_matches(
        self,
        idea_text: str,
        product_id: int,
        limit: int = 3,
        similarity_threshold: float = None
    ) -> ProductFeatureMatchResult:
        """
        Find product's own features that match an idea.

        This detects when a submitted idea describes functionality that
        already exists in the product.

        Args:
            idea_text: Text of the idea to match
            product_id: Product ID to search within
            limit: Maximum feature matches to return
            similarity_threshold: Minimum similarity (default: FEATURE_EXISTS_THRESHOLD)

        Returns:
            ProductFeatureMatchResult with matching features
        """
        if similarity_threshold is None:
            similarity_threshold = self.FEATURE_EXISTS_THRESHOLD

        # Generate embedding for the idea
        embedding = self.generate_embedding(idea_text)

        # Search using vector similarity against ProductFeature table
        vector_results = VectorService.find_similar_product_features(
            db=self.db,
            query_embedding=embedding,
            product_id=product_id,
            limit=limit,
            threshold=similarity_threshold
        )

        # Process results from detailed features
        matches = []
        for result in vector_results:
            feature_id, feature_name, feature_description, source_url, distance = result

            # Convert distance to similarity score
            similarity = self._distance_to_similarity(distance)

            matches.append(ProductFeatureMatch(
                feature_id=feature_id,
                feature_name=feature_name,
                feature_description=feature_description or "",
                similarity_score=round(similarity, 3),
                source_url=source_url
            ))

        # Fallback: only check core_features (which embed on-the-fly) when the
        # fast path found nothing. Detailed ProductFeature embeddings are the
        # primary, precomputed source; when they return matches we skip the
        # slower core_features path entirely.
        if not matches:
            core_feature_matches = self._check_core_features(
                idea_text=idea_text,
                product_id=product_id,
                similarity_threshold=similarity_threshold
            )
            existing_names = {m.feature_name.lower() for m in matches}
            for cm in core_feature_matches:
                if cm.feature_name.lower() not in existing_names:
                    matches.append(cm)

        # Sort by similarity and limit
        matches.sort(key=lambda x: x.similarity_score, reverse=True)
        matches = matches[:limit]

        has_match = len(matches) > 0
        best_match = matches[0] if matches else None

        return ProductFeatureMatchResult(
            has_match=has_match,
            matches=matches,
            best_match=best_match
        )

    def _check_core_features(
        self,
        idea_text: str,
        product_id: int,
        similarity_threshold: float
    ) -> List[ProductFeatureMatch]:
        """
        Check idea against core_features stored in structured_product_data.

        Core features are high-level strings without embeddings, so we
        generate embeddings on-the-fly for comparison.

        Args:
            idea_text: Text of the idea to match
            product_id: Product ID
            similarity_threshold: Minimum similarity score

        Returns:
            List of matching ProductFeatureMatch objects
        """
        from app.models.competitor_intelligence import CIProduct
        import numpy as np

        product = self.db.query(CIProduct).filter(CIProduct.id == product_id).first()
        if not product or not product.structured_product_data:
            return []

        core_features = product.structured_product_data.get('core_features', [])
        if not core_features:
            return []

        # Embed the idea + all core features in ONE batched call. The previous
        # implementation made one Voyage call per core feature in a loop, which
        # (with no client timeout) could block a request worker long enough to
        # get the instance restarted (a 502). core_features are 5-7 strings, so
        # one batch is cheap. This path is a FALLBACK for products whose
        # detailed ProductFeature embeddings aren't populated yet.
        from app.services.embedding_service import generate_embeddings_batch
        all_embeddings = generate_embeddings_batch(
            [idea_text] + list(core_features), input_type="document"
        )
        idea_embedding = all_embeddings[0]
        feature_embeddings = all_embeddings[1:]

        matches = []
        for feature_name, feature_embedding in zip(core_features, feature_embeddings):
            # Voyage embeddings are L2-normalized, so dot product = cosine similarity
            similarity = float(np.dot(idea_embedding, feature_embedding))

            if similarity >= similarity_threshold:
                # Determine source URL from product source
                source_url = None
                if product.product_source_type == 'url' and product.product_source_data:
                    source_url = product.product_source_data.get('url')

                matches.append(ProductFeatureMatch(
                    feature_id=0,  # Core features don't have IDs
                    feature_name=feature_name,
                    feature_description=f"Core product feature: {feature_name}",
                    similarity_score=round(similarity, 3),
                    source_url=source_url
                ))

        return matches

    def store_product_feature_embedding(self, feature_id: int, feature_text: str) -> None:
        """
        Generate and store embedding for a product feature.

        Call this when storing new ProductFeature records during analysis.

        Args:
            feature_id: ID of the ProductFeature
            feature_text: Combined text (name + description) for embedding
        """
        embedding = self.generate_embedding(feature_text)
        VectorService.store_product_feature_embedding(
            db=self.db,
            feature_id=feature_id,
            embedding=embedding
        )

    def store_product_feature_embeddings_batch(
        self, items: List[Tuple[int, str]]
    ) -> None:
        """
        Generate and store embeddings for many product features in ONE API call.

        Prefer this over calling store_product_feature_embedding in a loop:
        it makes a single Voyage batch request instead of N sequential ones,
        which is both faster and far less likely to hit rate limits.

        Args:
            items: List of (feature_id, feature_text) tuples.
        """
        if not items:
            return
        from app.services.embedding_service import generate_embeddings_batch

        texts = [text for _, text in items]
        embeddings = generate_embeddings_batch(texts, input_type="document")
        for (feature_id, _), embedding in zip(items, embeddings):
            VectorService.store_product_feature_embedding(
                db=self.db,
                feature_id=feature_id,
                embedding=embedding,
            )
