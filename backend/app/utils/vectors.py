"""Shared vector math utilities.

Importable from both services and queue task modules (no app.* imports here,
so no circular-import risk).
"""

from typing import Optional, Sequence


def cosine_similarity(a: Optional[Sequence[float]], b: Optional[Sequence[float]]) -> float:
    """Compute cosine similarity between two embedding vectors.

    Voyage AI embeddings are L2-normalized, so the dot product equals
    the cosine similarity. We still normalize defensively to handle
    embeddings from other sources or partially-corrupted vectors.

    Returns 0.0 for empty, mismatched-length, zero-norm, or invalid input.
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    try:
        import numpy as np
        va = np.array(a, dtype=float)
        vb = np.array(b, dtype=float)
        na = np.linalg.norm(va)
        nb = np.linalg.norm(vb)
        if na == 0.0 or nb == 0.0:
            return 0.0
        return float(np.dot(va, vb) / (na * nb))
    except Exception:
        return 0.0
