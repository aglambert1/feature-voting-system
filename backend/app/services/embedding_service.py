"""
Embedding service using Voyage AI API.

Replaces the local SentenceTransformer model (which required PyTorch ~300-400MB RAM)
with API-based embeddings via Voyage AI's voyage-3.5-lite model (1024 dimensions).

Usage:
    from app.services.embedding_service import generate_embedding, generate_embeddings_batch

    # For storing documents
    embedding = generate_embedding("some text", input_type="document")

    # For search queries
    embedding = generate_embedding("search query", input_type="query")
"""

import logging
from typing import List, Optional

import voyageai

from app.config import settings

logger = logging.getLogger(__name__)

# Lazy-initialized module-level client singleton.
# Works in both FastAPI and Celery contexts.
_client: Optional[voyageai.Client] = None

MODEL = "voyage-3.5-lite"


def _get_client() -> voyageai.Client:
    """Get or create the Voyage AI client singleton.

    A finite ``timeout`` is essential: without it a single slow embed call
    blocks the request worker indefinitely, which on a single-worker instance
    starves the health check and gets the instance restarted (surfacing as a
    502 to the browser). ``max_retries`` is bounded so transient errors don't
    multiply the worst-case latency.
    """
    global _client
    if _client is None:
        _client = voyageai.Client(
            api_key=settings.voyage_api_key,
            timeout=settings.voyage_timeout_seconds,
            max_retries=settings.voyage_max_retries,
        )
        logger.info(
            "Initialized Voyage AI client (model=%s, timeout=%ss, max_retries=%s)",
            MODEL, settings.voyage_timeout_seconds, settings.voyage_max_retries,
        )
    return _client


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
    client = _get_client()
    result = client.embed([text], model=MODEL, input_type=input_type)
    return result.embeddings[0]


def generate_embeddings_batch(texts: List[str], input_type: str = "document") -> List[List[float]]:
    """
    Generate embeddings for multiple texts in a single API call.

    Args:
        texts: List of texts to embed.
        input_type: "document" when storing, "query" when searching.

    Returns:
        List of 1024-dimensional embedding vectors (same order as input).
    """
    client = _get_client()
    result = client.embed(texts, model=MODEL, input_type=input_type)
    return result.embeddings
