"""
Search Service using the Brave Search API.

Provides web search capability for product analysis, competitor research,
and functional audit agents. Uses the Brave REST API directly for
structured JSON results.

A Redis-backed per-query cache wraps every call, so repeated queries across
agents and tasks don't hit Brave twice within the TTL window. The cache is
transparent to callers — failures fall through to live fetches.
"""

import hashlib
import json
import logging
import re
import time
from typing import Dict, List, Any, Optional

import requests

try:
    import redis
except ImportError:  # pragma: no cover
    redis = None  # type: ignore[assignment]

from app.config import settings

logger = logging.getLogger(__name__)


# Brave's hard cap per request — always fetch this many and slice per caller so
# different max_results values for the same query share a single cache entry.
_BRAVE_MAX_COUNT = 20


def _normalize_query(query: str) -> str:
    """Normalize a query for cache keying: lowercase, trim, collapse whitespace."""
    return re.sub(r"\s+", " ", query.strip().lower())


class SearchService:
    """
    Web search via the Brave Search API with transparent Redis caching.

    Provides a clean interface for agents to search the web with error
    handling and graceful degradation on rate limits or outages.
    Enforces 1 req/sec rate limit for Brave free tier.
    """

    BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"
    MIN_REQUEST_INTERVAL = 1.1  # seconds between requests (Brave free tier: 1/sec)
    CACHE_KEY_PREFIX = "web_search:"

    def __init__(self, redis_client: Optional[Any] = None):
        """Initialize search service.

        Args:
            redis_client: Optional pre-built Redis client. If None, one is
                created from ``settings.redis_url``. Pass a mock or fake in
                tests. Pass ``False`` to disable caching entirely.
        """
        self._last_request_time = 0.0
        self.search_enabled = (
            settings.enable_web_search
            and settings.brave_api_key
            and settings.brave_api_key != "your-brave-api-key-here"
        )
        if settings.enable_web_search and not self.search_enabled:
            logger.warning("Web search disabled — BRAVE_API_KEY not configured")

        if redis_client is False:
            self._redis = None
        elif redis_client is not None:
            self._redis = redis_client
        else:
            self._redis = self._build_redis_client()

    @staticmethod
    def _build_redis_client() -> Optional[Any]:
        """Build the default Redis client from settings. Returns None on failure."""
        if redis is None:
            logger.warning("redis package not installed — search caching disabled")
            return None
        try:
            return redis.Redis.from_url(settings.redis_url, decode_responses=True)
        except Exception as e:
            logger.warning("Redis client init failed, caching disabled: %s", e)
            return None

    def _cache_key(self, query: str) -> str:
        """Build a stable cache key from a normalized query."""
        normalized = _normalize_query(query)
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
        return f"{self.CACHE_KEY_PREFIX}{digest}"

    def _cache_get(self, key: str) -> Optional[List[Dict[str, Any]]]:
        """Read a cache entry. Returns None on miss or on any Redis failure."""
        if self._redis is None:
            return None
        try:
            raw = self._redis.get(key)
        except Exception as e:
            logger.warning("Redis GET failed, falling back to live search: %s", e)
            return None
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (ValueError, TypeError) as e:
            logger.warning("Cache entry for %s malformed, discarding: %s", key, e)
            return None

    def _cache_set(self, key: str, results: List[Dict[str, Any]]) -> None:
        """Write a cache entry. Empty results get a shorter TTL.

        Swallows any Redis errors — caching is best-effort.
        """
        if self._redis is None:
            return
        ttl = (
            settings.web_search_cache_ttl_seconds
            if results
            else settings.web_search_cache_empty_ttl_seconds
        )
        try:
            self._redis.setex(key, ttl, json.dumps(results))
        except Exception as e:
            logger.warning("Redis SETEX failed for %s: %s", key, e)

    def search(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Search the web via Brave Search API (cached).

        Cache strategy: every unique normalized query is fetched at Brave's
        hard cap (20 results) once per TTL window and cached whole. Callers
        asking for fewer results get a slice from the cached set, so the
        same underlying query doesn't produce multiple cache entries for
        different ``max_results`` values.

        Args:
            query: Search query string.
            max_results: Maximum results to return (default 10, max 20).

        Returns:
            List of {"title", "url", "snippet"} dicts. Empty list on
            failure or when search is disabled.
        """
        if not self.search_enabled:
            return []

        limit = min(max_results, _BRAVE_MAX_COUNT)
        key = self._cache_key(query)

        cached = self._cache_get(key)
        if cached is not None:
            logger.info("Brave Search cache HIT: %d results for '%s'", len(cached), query[:80])
            return cached[:limit]

        results = self._fetch_from_brave(query)
        self._cache_set(key, results)
        return results[:limit]

    def _fetch_from_brave(self, query: str) -> List[Dict[str, Any]]:
        """Fetch a query from Brave at the full cap, no caching."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.MIN_REQUEST_INTERVAL:
            time.sleep(self.MIN_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.time()

        try:
            resp = requests.get(
                self.BRAVE_API_URL,
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": settings.brave_api_key,
                },
                params={"q": query, "count": _BRAVE_MAX_COUNT},
                timeout=10,
            )

            if resp.status_code == 429:
                logger.warning("Brave Search rate limited for query: %s", query)
                return []

            resp.raise_for_status()

            web_results = resp.json().get("web", {}).get("results", [])
            results = [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("description", ""),
                }
                for r in web_results[:_BRAVE_MAX_COUNT]
            ]

            logger.info("Brave Search: %d results for '%s'", len(results), query[:80])
            return results

        except requests.exceptions.Timeout:
            logger.warning("Brave Search timeout for query: %s", query)
            return []
        except Exception as e:
            logger.warning("Brave Search error for '%s': %s", query[:80], e)
            return []

    def is_available(self) -> bool:
        """Check if search service is configured and enabled."""
        return self.search_enabled

    def get_tool_definition(self) -> Dict[str, Any]:
        """
        Get Claude-compatible tool definition for web search.

        Returns a dictionary that can be passed to Claude's API to enable
        the LLM to request web searches.
        """
        return {
            "name": "web_search",
            "description": (
                "Search the web for current information about products, companies, "
                "features, pricing, integrations, and competitive intelligence. "
                "Returns a list of search results with titles, URLs, and snippets. "
                "Use targeted queries like '[product] features', '[product] pricing plans', "
                "or '[product] vs [competitor]' for best results."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query. Be specific — include product name and what you're looking for.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default 10, max 20).",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        }


# Global singleton instance
_search_service = None


def get_search_service() -> SearchService:
    """Get or create the global SearchService instance."""
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service
