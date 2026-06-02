"""
Embedding service using the Voyage AI REST API.

Calls Voyage's HTTP embeddings endpoint directly with ``requests`` rather than
the ``voyageai`` SDK. The SDK transitively imports PyTorch + transformers
(~366 MB RSS) for local tokenization — which defeats the whole point of using
an API instead of a local SentenceTransformer model, and on a 512 MB instance
caused OOM kills the moment any worker/request first generated an embedding.
A plain POST has none of that footprint.

Usage:
    from app.services.embedding_service import generate_embedding, generate_embeddings_batch

    # For storing documents
    embedding = generate_embedding("some text", input_type="document")

    # For search queries
    embedding = generate_embedding("search query", input_type="query")
"""

import logging
from typing import List

import requests

from app.config import settings

logger = logging.getLogger(__name__)

MODEL = "voyage-3.5-lite"
_API_URL = "https://api.voyageai.com/v1/embeddings"


class EmbeddingServiceError(RuntimeError):
    """Raised when the Voyage embeddings API call fails."""


def _embed(texts: List[str], input_type: str) -> List[List[float]]:
    """POST to the Voyage embeddings endpoint and return vectors in input order.

    A finite ``timeout`` is essential: without it a single slow/stalled call
    blocks the calling worker indefinitely, which on a single-worker instance
    starves the health check and gets the instance restarted (surfacing as a
    502 to the browser). Retries are bounded so transient errors don't multiply
    the worst-case latency.
    """
    payload = {"input": texts, "model": MODEL, "input_type": input_type}
    headers = {
        "Authorization": f"Bearer {settings.voyage_api_key}",
        "Content-Type": "application/json",
    }

    last_err: Exception | None = None
    attempts = settings.voyage_max_retries + 1
    for attempt in range(attempts):
        try:
            resp = requests.post(
                _API_URL,
                json=payload,
                headers=headers,
                timeout=settings.voyage_timeout_seconds,
            )
            resp.raise_for_status()
            data = resp.json()
            # Response: {"data": [{"embedding": [...], "index": 0}, ...]}
            items = sorted(data["data"], key=lambda d: d["index"])
            return [item["embedding"] for item in items]
        except (requests.RequestException, KeyError, ValueError) as e:
            last_err = e
            if attempt < attempts - 1:
                logger.warning(
                    "Voyage embeddings call failed (attempt %s/%s): %s",
                    attempt + 1, attempts, e,
                )
                continue
            break

    raise EmbeddingServiceError(
        f"Voyage embeddings request failed after {attempts} attempt(s): {last_err}"
    ) from last_err


def generate_embedding(text: str, input_type: str = "document") -> List[float]:
    """
    Generate a 1024-dimensional embedding for a single text.

    Args:
        text: Text to embed.
        input_type: "document" when storing, "query" when searching.
            Voyage optimizes retrieval differently for each.

    Returns:
        1024-dimensional embedding vector.
    """
    return _embed([text], input_type)[0]


def generate_embeddings_batch(texts: List[str], input_type: str = "document") -> List[List[float]]:
    """
    Generate embeddings for multiple texts in a single API call.

    Args:
        texts: List of texts to embed.
        input_type: "document" when storing, "query" when searching.

    Returns:
        List of 1024-dimensional embedding vectors (same order as input).
    """
    if not texts:
        return []
    return _embed(texts, input_type)
