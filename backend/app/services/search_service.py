"""
Search Service using the Brave Search API.

Provides web search capability for product analysis, competitor research,
and functional audit agents. Uses the Brave REST API directly for
structured JSON results.
"""

import logging
from typing import Dict, List, Any

import requests

from app.config import settings

logger = logging.getLogger(__name__)


class SearchService:
    """
    Web search via the Brave Search API.

    Provides a clean interface for agents to search the web with error
    handling and graceful degradation on rate limits or outages.
    """

    BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self):
        """Initialize search service."""
        self.search_enabled = (
            settings.enable_web_search
            and settings.brave_api_key
            and settings.brave_api_key != "your-brave-api-key-here"
        )
        if settings.enable_web_search and not self.search_enabled:
            logger.warning("Web search disabled — BRAVE_API_KEY not configured")

    def search(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Search the web via Brave Search API.

        Args:
            query: Search query string.
            max_results: Maximum results to return (default 10, max 20).

        Returns:
            List of {"title", "url", "snippet"} dicts. Empty list on
            failure or when search is disabled.
        """
        if not self.search_enabled:
            return []

        try:
            resp = requests.get(
                self.BRAVE_API_URL,
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": settings.brave_api_key,
                },
                params={"q": query, "count": min(max_results, 20)},
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
                for r in web_results[:max_results]
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
