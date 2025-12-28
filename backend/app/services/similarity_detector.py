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
from app.models.idea import Idea, IdeaStatus

# Module-level embedding model (lazy-loaded)
_embedding_model = None


def get_embedding_model():
    """Get or load the embedding model."""
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            print("Loading SentenceTransformer model for similarity detection...")
            _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            print(f"✓ Embedding model loaded ({_embedding_model.get_sentence_embedding_dimension()} dimensions)")
        except Exception as e:
            print(f"✗ Failed to load embedding model: {e}")
            raise
    return _embedding_model


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

    def __init__(self, db: Session):
        self.db = db
        self._model = None

    @property
    def embedding_model(self):
        """Get the embedding model (lazy-loaded)."""
        if self._model is None:
            self._model = get_embedding_model()
        return self._model

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using SentenceTransformer.

        Args:
            text: Text to embed (idea title + description)

        Returns:
            384-dimensional embedding vector
        """
        embedding = self.embedding_model.encode(text, show_progress_bar=False)
        return embedding.tolist()

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

    def find_competitive_matches(
        self,
        idea_text: str,
        product_id: int,
        limit: int = 5,
        similarity_threshold: float = 0.5
    ) -> Dict[str, Any]:
        """
        Find competitor features that match an idea using vector similarity
        and calculate competitive urgency.

        This provides structured competitive context for idea triage with
        deterministic urgency levels that help PMs understand priority.

        Uses vector embeddings for accurate semantic matching between ideas
        and competitor features.

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
        from app.models.competitor_intelligence import ProductCompetitor

        # Generate embedding for the idea
        embedding = self.generate_embedding(idea_text)

        # Get total active competitors for this product (for urgency calculation)
        total_competitors = self.db.query(ProductCompetitor).filter(
            ProductCompetitor.product_id == product_id,
            ProductCompetitor.status == 'active'
        ).count()

        if total_competitors == 0:
            # No competitors tracked - low urgency (potential differentiator)
            return {
                "matches": [],
                "urgency": CompetitiveUrgencyResult(
                    urgency=CompetitiveUrgency.LOW,
                    competitor_count=0,
                    total_competitors_analyzed=0,
                    competitors_with_feature=[],
                    reasoning="No competitors are being tracked for this product. This feature could be a differentiator."
                ).to_dict()
            }

        # Use vector similarity search to find matching features
        vector_results = VectorService.find_similar_competitor_features(
            db=self.db,
            query_embedding=embedding,
            product_id=product_id,
            limit=limit * 2,  # Get extra results in case of ties
            threshold=similarity_threshold
        )

        # Process results and track unique competitors
        matches = []
        competitors_with_feature = set()

        for result in vector_results:
            feature_id, feature_name, feature_description, competitor_id, competitor_name, distance = result

            # Convert distance to similarity score
            similarity = self._distance_to_similarity(distance)

            matches.append({
                'competitor_id': competitor_id,
                'competitor_name': competitor_name,
                'feature_id': feature_id,
                'feature_name': feature_name,
                'feature_description': feature_description,
                'similarity_score': round(similarity, 3),
            })
            competitors_with_feature.add(competitor_name)

        # If no vector matches found, fall back to text-based matching
        # This handles cases where competitor features don't have embeddings yet
        if not matches:
            matches, competitors_with_feature = self._text_based_feature_matching(
                idea_text=idea_text,
                product_id=product_id,
                limit=limit
            )

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

    def _text_based_feature_matching(
        self,
        idea_text: str,
        product_id: int,
        limit: int = 5
    ) -> Tuple[List[Dict[str, Any]], set]:
        """
        Fallback text-based feature matching when embeddings are not available.

        Uses word overlap similarity as a simple approximation.

        Args:
            idea_text: Text of the idea to match
            product_id: Product to search competitors for
            limit: Maximum feature matches to return

        Returns:
            Tuple of (matches list, set of competitor names with matches)
        """
        from app.models.competitor_intelligence import ProductCompetitor, ProductCompetitorFeature

        competitors = self.db.query(ProductCompetitor).filter(
            ProductCompetitor.product_id == product_id,
            ProductCompetitor.status == 'active'
        ).all()

        matches = []
        competitors_with_feature = set()

        for competitor in competitors:
            features = self.db.query(ProductCompetitorFeature).filter(
                ProductCompetitorFeature.product_competitor_id == competitor.id,
                ProductCompetitorFeature.status == 'active'
            ).all()

            for feature in features:
                feature_text = f"{feature.feature_name}\n{feature.feature_description or ''}"
                similarity = self._text_similarity(idea_text.lower(), feature_text.lower())

                if similarity > 0.3:
                    matches.append({
                        'competitor_id': competitor.id,
                        'competitor_name': competitor.competitor_name,
                        'feature_id': feature.id,
                        'feature_name': feature.feature_name,
                        'feature_description': feature.feature_description,
                        'feature_category': feature.feature_category,
                        'similarity_score': round(similarity, 3),
                    })
                    competitors_with_feature.add(competitor.competitor_name)

        # Sort by similarity and limit
        matches.sort(key=lambda x: x['similarity_score'], reverse=True)
        return matches[:limit], competitors_with_feature

    def store_competitor_feature_embedding(self, feature_id: int, feature_text: str) -> None:
        """
        Generate and store embedding for a competitor feature.

        Call this when extracting new features to enable vector similarity search.

        Args:
            feature_id: ID of the ProductCompetitorFeature
            feature_text: Combined text (name + description) for embedding
        """
        embedding = self.generate_embedding(feature_text)
        VectorService.store_competitor_feature_embedding(
            db=self.db,
            feature_id=feature_id,
            embedding=embedding
        )

    def bulk_store_competitor_feature_embeddings(self, product_id: int) -> int:
        """
        Generate and store embeddings for all competitor features for a product.

        Useful for backfilling embeddings for existing features.

        Args:
            product_id: Product ID to process features for

        Returns:
            Number of features processed
        """
        from app.models.competitor_intelligence import ProductCompetitor, ProductCompetitorFeature

        competitors = self.db.query(ProductCompetitor).filter(
            ProductCompetitor.product_id == product_id,
            ProductCompetitor.status == 'active'
        ).all()

        count = 0
        for competitor in competitors:
            features = self.db.query(ProductCompetitorFeature).filter(
                ProductCompetitorFeature.product_competitor_id == competitor.id,
                ProductCompetitorFeature.status == 'active'
            ).all()

            for feature in features:
                feature_text = f"{feature.feature_name}\n{feature.feature_description or ''}"
                self.store_competitor_feature_embedding(feature.id, feature_text)
                count += 1

        self.db.commit()
        return count

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
