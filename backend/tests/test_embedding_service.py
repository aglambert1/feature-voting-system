"""
Tests for the Voyage AI embedding service.

Tests that the embedding service correctly generates embeddings via the
Voyage AI API (voyage-3.5-lite model, 1024 dimensions).
"""

import os
import pytest
import numpy as np


# Skip all tests in this module if VOYAGE_API_KEY is not set
pytestmark = pytest.mark.skipif(
    not os.environ.get("VOYAGE_API_KEY") or os.environ.get("VOYAGE_API_KEY") == "your-voyage-api-key-here",
    reason="VOYAGE_API_KEY not configured"
)


class TestGenerateEmbedding:
    """Test single embedding generation."""

    def test_returns_1024_dimensions(self):
        from app.services.embedding_service import generate_embedding

        embedding = generate_embedding("test document text", input_type="document")

        assert isinstance(embedding, list)
        assert len(embedding) == 1024

    def test_values_are_floats(self):
        from app.services.embedding_service import generate_embedding

        embedding = generate_embedding("test query text", input_type="query")

        assert all(isinstance(v, float) for v in embedding)

    def test_embedding_is_normalized(self):
        """Voyage embeddings should be L2-normalized (unit length)."""
        from app.services.embedding_service import generate_embedding

        embedding = generate_embedding("normalized vector check", input_type="document")
        norm = np.linalg.norm(embedding)

        assert abs(norm - 1.0) < 0.01, f"Expected L2 norm ~1.0, got {norm}"

    def test_similar_texts_have_high_similarity(self):
        """Semantically similar texts should produce similar embeddings."""
        from app.services.embedding_service import generate_embedding

        emb1 = generate_embedding("add dark mode to the application", input_type="document")
        emb2 = generate_embedding("implement a night theme for the UI", input_type="document")

        similarity = float(np.dot(emb1, emb2))

        assert similarity > 0.7, f"Expected similarity > 0.7 for similar texts, got {similarity}"

    def test_similar_texts_rank_higher_than_different(self):
        """Similar texts should have higher similarity than unrelated texts."""
        from app.services.embedding_service import generate_embedding

        base = generate_embedding("add dark mode to the application", input_type="document")
        similar = generate_embedding("implement a night theme for the UI", input_type="document")
        different = generate_embedding("the recipe calls for two cups of flour", input_type="document")

        sim_similar = float(np.dot(base, similar))
        sim_different = float(np.dot(base, different))

        assert sim_similar > sim_different, (
            f"Similar text ({sim_similar:.3f}) should score higher than "
            f"unrelated text ({sim_different:.3f})"
        )


class TestGenerateEmbeddingsBatch:
    """Test batch embedding generation."""

    def test_batch_returns_correct_count(self):
        from app.services.embedding_service import generate_embeddings_batch

        texts = ["first text", "second text", "third text"]
        embeddings = generate_embeddings_batch(texts, input_type="document")

        assert len(embeddings) == 3

    def test_batch_dimensions(self):
        from app.services.embedding_service import generate_embeddings_batch

        texts = ["text one", "text two"]
        embeddings = generate_embeddings_batch(texts, input_type="document")

        assert all(len(emb) == 1024 for emb in embeddings)
