"""
Internal Theme Merger Service.

This service merges themes from structured internal feedback (WinLossTheme, SupportTheme)
with activity-extracted insights (DealActivityInsight, SupportActivityInsight) into
unified evidence for the OpportunitySynthesisAgent.

When themes from different sources are semantically similar, they are merged
with combined metrics and marked as "high confidence" since multiple sources agree.
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.internal_feedback import (
    InternalFeedbackImport,
    WinLossTheme,
    SupportTheme
)
from app.models.activity_insights import (
    ActivityImport,
    DealActivityInsight,
    SupportActivityInsight
)

# Module-level embedding model (lazy-loaded)
_embedding_model = None


def get_embedding_model():
    """Get or load the embedding model."""
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            print("Loading SentenceTransformer model for theme merging...")
            _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            print(f"✓ Embedding model loaded ({_embedding_model.get_sentence_embedding_dimension()} dimensions)")
        except Exception as e:
            print(f"✗ Failed to load embedding model: {e}")
            raise
    return _embedding_model


@dataclass
class MergedWinLossTheme:
    """A merged win/loss theme from structured and/or activity sources."""
    theme_name: str
    outcome: str  # won, lost, both
    sources: List[str] = field(default_factory=list)  # ["structured", "activity"]
    confidence: str = "medium"  # high if both sources agree, medium otherwise

    # Combined metrics
    deal_count: int = 0
    total_value: float = 0.0

    # Evidence from each source
    structured_evidence: Optional[Dict[str, Any]] = None
    activity_evidence: Optional[Dict[str, Any]] = None

    # Combined evidence
    sample_quotes: List[str] = field(default_factory=list)
    feature_keywords: List[str] = field(default_factory=list)
    competitor_correlation: Optional[str] = None


@dataclass
class MergedSupportTheme:
    """A merged support theme from structured and/or activity sources."""
    theme_name: str
    category: str
    sources: List[str] = field(default_factory=list)
    confidence: str = "medium"

    # Combined metrics
    ticket_count: int = 0
    urgency_level: str = "medium"

    # Evidence from each source
    structured_evidence: Optional[Dict[str, Any]] = None
    activity_evidence: Optional[Dict[str, Any]] = None

    # Combined evidence
    sample_quotes: List[str] = field(default_factory=list)
    feature_keywords: List[str] = field(default_factory=list)
    accounts_affected: List[str] = field(default_factory=list)


@dataclass
class MergedInternalEvidence:
    """Complete merged internal evidence for synthesis."""
    winloss_themes: List[MergedWinLossTheme]
    support_themes: List[MergedSupportTheme]
    sources_used: List[str]  # Which import types were available

    # Source metadata
    structured_import_id: Optional[int] = None
    activity_import_id: Optional[int] = None


class InternalThemeMergerService:
    """
    Service for merging themes from structured and activity-based internal feedback.

    The merger:
    1. Collects themes from both structured and activity imports
    2. Computes semantic similarity between themes
    3. Merges similar themes (>0.85 similarity) into unified entries
    4. Marks merged themes as "high confidence"
    5. Combines metrics (deal counts, values, quotes)
    """

    MERGE_THRESHOLD = 0.85  # Similarity threshold for merging themes

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
        """Generate embedding for theme text."""
        embedding = self.embedding_model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def compute_similarity(self, emb1: List[float], emb2: List[float]) -> float:
        """Compute cosine similarity between two embeddings."""
        import numpy as np
        a = np.array(emb1)
        b = np.array(emb2)
        # Since embeddings are normalized, dot product = cosine similarity
        return float(np.dot(a, b))

    def merge_internal_evidence(self, product_id: int) -> MergedInternalEvidence:
        """
        Merge all internal evidence sources for a product.

        Args:
            product_id: The product to merge evidence for

        Returns:
            MergedInternalEvidence with unified themes
        """
        # Collect structured themes
        structured_winloss, structured_support, structured_import_id = self._get_structured_themes(product_id)

        # Collect activity insights
        activity_deal, activity_support, activity_import_id = self._get_activity_insights(product_id)

        # Track which sources are available
        sources_used = []
        if structured_import_id:
            sources_used.append("structured")
        if activity_import_id:
            sources_used.append("activity")

        # Merge win/loss themes
        merged_winloss = self._merge_winloss_themes(structured_winloss, activity_deal)

        # Merge support themes
        merged_support = self._merge_support_themes(structured_support, activity_support)

        return MergedInternalEvidence(
            winloss_themes=merged_winloss,
            support_themes=merged_support,
            sources_used=sources_used,
            structured_import_id=structured_import_id,
            activity_import_id=activity_import_id
        )

    def _get_structured_themes(self, product_id: int) -> Tuple[List[WinLossTheme], List[SupportTheme], Optional[int]]:
        """Get themes from the most recent structured import."""
        # Find most recent completed structured import
        import_record = self.db.query(InternalFeedbackImport).filter(
            InternalFeedbackImport.product_id == product_id,
            InternalFeedbackImport.themes_extracted == True
        ).order_by(desc(InternalFeedbackImport.imported_at)).first()

        if not import_record:
            return [], [], None

        winloss = self.db.query(WinLossTheme).filter(
            WinLossTheme.import_id == import_record.id
        ).all()

        support = self.db.query(SupportTheme).filter(
            SupportTheme.import_id == import_record.id
        ).all()

        return winloss, support, import_record.id

    def _get_activity_insights(self, product_id: int) -> Tuple[List[DealActivityInsight], List[SupportActivityInsight], Optional[int]]:
        """Get insights from the most recent activity import."""
        # Find most recent completed activity import
        import_record = self.db.query(ActivityImport).filter(
            ActivityImport.product_id == product_id,
            ActivityImport.status == "completed"
        ).order_by(desc(ActivityImport.imported_at)).first()

        if not import_record:
            return [], [], None

        deal_insights = self.db.query(DealActivityInsight).filter(
            DealActivityInsight.import_id == import_record.id
        ).all()

        support_insights = self.db.query(SupportActivityInsight).filter(
            SupportActivityInsight.import_id == import_record.id
        ).all()

        return deal_insights, support_insights, import_record.id

    def _merge_winloss_themes(
        self,
        structured: List[WinLossTheme],
        activity: List[DealActivityInsight]
    ) -> List[MergedWinLossTheme]:
        """Merge win/loss themes from both sources."""
        merged = []
        used_activity_ids = set()

        # Process structured themes
        for theme in structured:
            # Generate embedding for matching
            theme_text = f"{theme.theme_name} {' '.join(theme.feature_keywords or [])}"
            theme_emb = self.generate_embedding(theme_text)

            # Find matching activity insights
            matching_activity = []
            for insight in activity:
                if insight.id in used_activity_ids:
                    continue

                # Generate embedding for activity insight
                insight_text = f"{insight.theme_name} {' '.join(insight.feature_keywords or [])}"
                insight_emb = self.generate_embedding(insight_text)

                similarity = self.compute_similarity(theme_emb, insight_emb)
                if similarity >= self.MERGE_THRESHOLD:
                    matching_activity.append((insight, similarity))
                    used_activity_ids.add(insight.id)

            # Create merged theme
            merged_theme = MergedWinLossTheme(
                theme_name=theme.theme_name,
                outcome=theme.outcome,
                sources=["structured"],
                confidence="medium",
                deal_count=theme.deal_count,
                total_value=theme.total_value,
                structured_evidence={
                    "theme_id": theme.id,
                    "deal_count": theme.deal_count,
                    "total_value": theme.total_value,
                    "sample_reasons": theme.sample_reasons or []
                },
                sample_quotes=list(theme.sample_reasons or []),
                feature_keywords=list(theme.feature_keywords or []),
                competitor_correlation=theme.competitor_name
            )

            # Merge matching activity insights
            if matching_activity:
                merged_theme.sources.append("activity")
                merged_theme.confidence = "high"  # Both sources agree

                # Combine metrics from activity insights
                activity_deal_count = 0
                activity_value = 0.0
                activity_quotes = []
                activity_keywords = set(merged_theme.feature_keywords)

                for insight, _ in matching_activity:
                    activity_deal_count += 1
                    if insight.deal_value:
                        activity_value += insight.deal_value
                    activity_quotes.extend(insight.sample_quotes or [])
                    activity_keywords.update(insight.feature_keywords or [])

                merged_theme.activity_evidence = {
                    "deal_count": activity_deal_count,
                    "total_value": activity_value,
                    "sample_quotes": activity_quotes[:5]
                }

                # Update combined metrics
                merged_theme.deal_count += activity_deal_count
                merged_theme.total_value += activity_value
                merged_theme.sample_quotes.extend(activity_quotes)
                merged_theme.sample_quotes = merged_theme.sample_quotes[:5]  # Limit to 5
                merged_theme.feature_keywords = list(activity_keywords)

            merged.append(merged_theme)

        # Add remaining activity insights that didn't match
        for insight in activity:
            if insight.id in used_activity_ids:
                continue

            merged_theme = MergedWinLossTheme(
                theme_name=insight.theme_name,
                outcome=insight.deal_outcome,
                sources=["activity"],
                confidence="medium",
                deal_count=1,
                total_value=insight.deal_value or 0.0,
                activity_evidence={
                    "insight_id": insight.id,
                    "deal_name": insight.deal_name,
                    "sample_quotes": insight.sample_quotes or []
                },
                sample_quotes=list(insight.sample_quotes or [])[:5],
                feature_keywords=list(insight.feature_keywords or []),
                competitor_correlation=insight.competitor_mentioned
            )
            merged.append(merged_theme)

        return merged

    def _merge_support_themes(
        self,
        structured: List[SupportTheme],
        activity: List[SupportActivityInsight]
    ) -> List[MergedSupportTheme]:
        """Merge support themes from both sources."""
        merged = []
        used_activity_ids = set()

        # Process structured themes
        for theme in structured:
            # Generate embedding for matching
            theme_text = f"{theme.theme_name} {' '.join(theme.feature_keywords or [])}"
            theme_emb = self.generate_embedding(theme_text)

            # Find matching activity insights
            matching_activity = []
            for insight in activity:
                if insight.id in used_activity_ids:
                    continue

                insight_text = f"{insight.theme_name} {' '.join(insight.feature_keywords or [])}"
                insight_emb = self.generate_embedding(insight_text)

                similarity = self.compute_similarity(theme_emb, insight_emb)
                if similarity >= self.MERGE_THRESHOLD:
                    matching_activity.append((insight, similarity))
                    used_activity_ids.add(insight.id)

            # Create merged theme
            merged_theme = MergedSupportTheme(
                theme_name=theme.theme_name,
                category=theme.category,
                sources=["structured"],
                confidence="medium",
                ticket_count=theme.ticket_count,
                urgency_level=theme.urgency_indicator,
                structured_evidence={
                    "theme_id": theme.id,
                    "ticket_count": theme.ticket_count,
                    "sample_subjects": theme.sample_subjects or []
                },
                sample_quotes=list(theme.sample_subjects or []),
                feature_keywords=list(theme.feature_keywords or [])
            )

            # Merge matching activity insights
            if matching_activity:
                merged_theme.sources.append("activity")
                merged_theme.confidence = "high"

                activity_tickets = 0
                activity_quotes = []
                activity_keywords = set(merged_theme.feature_keywords)
                activity_accounts = set()

                for insight, _ in matching_activity:
                    activity_tickets += insight.ticket_count
                    activity_quotes.extend(insight.sample_quotes or [])
                    activity_keywords.update(insight.feature_keywords or [])
                    activity_accounts.update(insight.accounts_affected or [])

                merged_theme.activity_evidence = {
                    "ticket_count": activity_tickets,
                    "sample_quotes": activity_quotes[:5],
                    "accounts_affected": list(activity_accounts)
                }

                merged_theme.ticket_count += activity_tickets
                merged_theme.sample_quotes.extend(activity_quotes)
                merged_theme.sample_quotes = merged_theme.sample_quotes[:5]
                merged_theme.feature_keywords = list(activity_keywords)
                merged_theme.accounts_affected = list(activity_accounts)

                # Upgrade urgency if combined volume is higher
                if merged_theme.ticket_count >= 30:
                    merged_theme.urgency_level = "high"
                elif merged_theme.ticket_count >= 15:
                    merged_theme.urgency_level = "medium"

            merged.append(merged_theme)

        # Add remaining activity insights
        for insight in activity:
            if insight.id in used_activity_ids:
                continue

            merged_theme = MergedSupportTheme(
                theme_name=insight.theme_name,
                category=insight.category,
                sources=["activity"],
                confidence="medium",
                ticket_count=insight.ticket_count,
                urgency_level=insight.urgency_level,
                activity_evidence={
                    "insight_id": insight.id,
                    "sample_quotes": insight.sample_quotes or [],
                    "accounts_affected": insight.accounts_affected or []
                },
                sample_quotes=list(insight.sample_quotes or [])[:5],
                feature_keywords=list(insight.feature_keywords or []),
                accounts_affected=list(insight.accounts_affected or [])
            )
            merged.append(merged_theme)

        return merged

    def to_synthesis_format(self, merged: MergedInternalEvidence) -> Dict[str, Any]:
        """
        Convert merged evidence to the format expected by OpportunitySynthesisAgent.

        Returns a dict suitable for passing to the synthesis agent.
        """
        winloss_themes = []
        for theme in merged.winloss_themes:
            winloss_themes.append({
                "theme_name": theme.theme_name,
                "outcome": theme.outcome,
                "sources": theme.sources,
                "confidence": theme.confidence,
                "deal_count": theme.deal_count,
                "total_value": theme.total_value,
                "structured_evidence": theme.structured_evidence,
                "activity_evidence": theme.activity_evidence,
                "sample_quotes": theme.sample_quotes,
                "feature_keywords": theme.feature_keywords,
                "competitor_correlation": theme.competitor_correlation
            })

        support_themes = []
        for theme in merged.support_themes:
            support_themes.append({
                "theme_name": theme.theme_name,
                "category": theme.category,
                "sources": theme.sources,
                "confidence": theme.confidence,
                "ticket_count": theme.ticket_count,
                "urgency_level": theme.urgency_level,
                "structured_evidence": theme.structured_evidence,
                "activity_evidence": theme.activity_evidence,
                "sample_quotes": theme.sample_quotes,
                "feature_keywords": theme.feature_keywords,
                "accounts_affected": theme.accounts_affected
            })

        return {
            "winloss_themes": winloss_themes,
            "support_themes": support_themes,
            "sources_used": merged.sources_used,
            "structured_import_id": merged.structured_import_id,
            "activity_import_id": merged.activity_import_id
        }
