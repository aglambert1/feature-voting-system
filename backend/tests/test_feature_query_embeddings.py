"""Regression tests for the feature-query / feature-match embedding path.

Background: a queued product analysis created ProductFeature rows WITHOUT
embeddings (the synchronous path did populate them). Queue-analyzed products
therefore had NULL feature embeddings, so the fast vector lookup returned
nothing and every feature query fell through to a slow per-feature on-the-fly
embedding loop with no Voyage client timeout — blocking the request worker
until the instance was restarted (a 502).

These tests lock in the fixes:
1. The Voyage client is configured with a finite timeout.
2. The shared helper populates embeddings via a single batched call, and both
   analysis paths use it.
3. find_product_feature_matches uses core_features only as a fallback (skips it
   when detailed matches exist), and _check_core_features batches its embeds.
"""

from unittest.mock import patch, MagicMock

import pytest

from app.models.competitor_intelligence import (
    CIProduct, ProductAnalysisHistory, ProductFeature,
)
from app.models.user import User, UserRole


def _make_product(db):
    user = User(email="fq@example.com", username="fq", hashed_password="h",
                role=UserRole.PRODUCT_OWNER)
    db.add(user)
    db.flush()
    product = CIProduct(product_name="FQ Product", product_description="desc",
                        created_by_user_id=user.id, status="active")
    db.add(product)
    db.flush()
    history = ProductAnalysisHistory(
        product_id=product.id, analysis_version=1, analyzed_by_user_id=user.id,
        product_description="desc", product_source_type="text",
        analyzed_structure={},
    )
    db.add(history)
    db.flush()
    return user, product, history


class TestVoyageClientTimeout:
    def test_client_configured_with_timeout(self):
        """The Voyage client must have a finite timeout so an embed call can
        never hang a request worker indefinitely."""
        import app.services.embedding_service as es
        from app.config import settings

        es._client = None  # reset singleton
        captured = {}

        def fake_client(**kwargs):
            captured.update(kwargs)
            return MagicMock()

        with patch.object(es.voyageai, "Client", side_effect=fake_client):
            es._get_client()

        assert captured.get("timeout") == settings.voyage_timeout_seconds
        assert captured.get("timeout") is not None
        assert captured.get("max_retries") == settings.voyage_max_retries
        es._client = None  # leave clean


class TestSharedFeatureHelper:
    def test_creates_features_and_batches_embeddings(self, db_session):
        """The shared helper creates rows and stores embeddings in ONE batch
        call (not one call per feature)."""
        from app.services.product_service import create_product_features_with_embeddings

        _user, product, history = _make_product(db_session)
        detailed = [
            {"name": "Export to CSV", "description": "Export data as CSV"},
            {"name": "Dark mode", "description": "Night theme"},
            {"name": "SSO", "description": "Single sign-on"},
        ]

        with patch(
            "app.services.embedding_service.generate_embeddings_batch",
            return_value=[[0.1] * 1024, [0.2] * 1024, [0.3] * 1024],
        ) as mock_batch, patch(
            "app.services.vector_service.VectorService.store_product_feature_embedding"
        ) as mock_store:
            created = create_product_features_with_embeddings(
                db_session,
                product_id=product.id,
                analysis_history_id=history.id,
                analysis_version=1,
                detailed_features=detailed,
            )

        # Rows created with ids
        assert len(created) == 3
        assert all(pf.id is not None for pf in created)
        rows = db_session.query(ProductFeature).filter_by(product_id=product.id).all()
        assert len(rows) == 3

        # Exactly ONE batch embedding call for all three features
        assert mock_batch.call_count == 1
        texts_arg = mock_batch.call_args[0][0]
        assert len(texts_arg) == 3
        # Stored once per feature
        assert mock_store.call_count == 3

    def test_embedding_failure_does_not_abort_feature_creation(self, db_session):
        """If embedding generation fails, rows are still created (degrade
        gracefully; backfill via re-analysis)."""
        from app.services.product_service import create_product_features_with_embeddings

        _user, product, history = _make_product(db_session)
        detailed = [{"name": "Feature A", "description": "desc A"}]

        with patch(
            "app.services.embedding_service.generate_embeddings_batch",
            side_effect=RuntimeError("voyage down"),
        ):
            created = create_product_features_with_embeddings(
                db_session,
                product_id=product.id,
                analysis_history_id=history.id,
                analysis_version=1,
                detailed_features=detailed,
            )

        assert len(created) == 1
        assert db_session.query(ProductFeature).filter_by(product_id=product.id).count() == 1


class TestCoreFeaturesFallback:
    def test_core_features_skipped_when_detailed_matches_exist(self, db_session):
        """When the fast detailed-feature path returns matches, the slow
        core_features path must not run at all."""
        from app.services.similarity_detector import (
            SimilarityDetectorService, ProductFeatureMatch,
        )

        _user, product, _history = _make_product(db_session)
        svc = SimilarityDetectorService(db_session)

        detailed_match = ProductFeatureMatch(
            feature_id=1, feature_name="Export", feature_description="d",
            similarity_score=0.9, source_url=None,
        )

        with patch.object(svc, "generate_embedding", return_value=[0.1] * 1024), \
             patch(
                 "app.services.vector_service.VectorService.find_similar_product_features",
                 return_value=[(1, "Export", "d", None, 0.2)],
             ), \
             patch.object(svc, "_check_core_features") as mock_core:
            result = svc.find_product_feature_matches(
                idea_text="export my data", product_id=product.id,
            )

        assert result.has_match
        mock_core.assert_not_called()

    def test_check_core_features_uses_single_batch_call(self, db_session):
        """_check_core_features must embed idea + all core features in one
        batched call, not one call per feature."""
        from app.services.similarity_detector import SimilarityDetectorService

        _user, product, _history = _make_product(db_session)
        product.structured_product_data = {
            "core_features": ["alpha", "beta", "gamma", "delta"]
        }
        db_session.flush()

        svc = SimilarityDetectorService(db_session)
        # 1 idea + 4 features = 5 vectors; orthogonal-ish so none match the high
        # threshold (we only assert call count / batching here)
        fake_vecs = [[0.0] * 1024 for _ in range(5)]
        for i in range(5):
            fake_vecs[i][i] = 1.0

        with patch(
            "app.services.embedding_service.generate_embeddings_batch",
            return_value=fake_vecs,
        ) as mock_batch:
            matches = svc._check_core_features(
                idea_text="zeta", product_id=product.id, similarity_threshold=0.85,
            )

        assert mock_batch.call_count == 1
        # one batch containing idea + 4 features
        assert len(mock_batch.call_args[0][0]) == 5
        assert matches == []
