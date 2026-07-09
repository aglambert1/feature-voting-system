"""Unit tests for app/utils/vectors.py — the shared cosine similarity."""

import math

from app.utils.vectors import cosine_similarity


class TestCosineSimilarity:
    def test_identical_vectors(self):
        assert math.isclose(cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]), 1.0)

    def test_orthogonal_vectors(self):
        assert math.isclose(cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0)

    def test_opposite_vectors(self):
        assert math.isclose(cosine_similarity([1.0, 0.0], [-1.0, 0.0]), -1.0)

    def test_non_normalized_inputs(self):
        # Same direction, different magnitudes → still 1.0
        assert math.isclose(cosine_similarity([1.0, 1.0], [10.0, 10.0]), 1.0)

    def test_empty_inputs(self):
        assert cosine_similarity([], []) == 0.0
        assert cosine_similarity(None, [1.0]) == 0.0
        assert cosine_similarity([1.0], None) == 0.0

    def test_length_mismatch(self):
        assert cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0]) == 0.0

    def test_zero_vector(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0

    def test_bad_input_returns_zero(self):
        assert cosine_similarity(["not", "numbers"], [1.0, 2.0]) == 0.0
