"""
Search Service using LangChain's search tools.

This service provides a unified interface for web search across different providers.
Currently supports Brave Search, but can easily be extended to support Google, DuckDuckGo, etc.
"""

from typing import Dict, List, Optional, Any
from langchain_community.tools import BraveSearch
from app.config import settings


class SearchService:
    """
    Wrapper around LangChain search tools for competitor research.

    Provides a clean interface for web search with error handling and rate limiting awareness.
    """

    def __init__(self):
        """Initialize search service with configured provider."""
        self.search_enabled = settings.enable_web_search

        if self.search_enabled and settings.brave_api_key != "your-brave-api-key-here":
            try:
                self.brave_search = BraveSearch.from_api_key(
                    api_key=settings.brave_api_key,
                    search_kwargs={"count": 10}  # Number of results to return
                )
            except Exception as e:
                print(f"[SearchService] Warning: Failed to initialize Brave Search: {e}")
                self.brave_search = None
                self.search_enabled = False
        else:
            self.brave_search = None
            if settings.enable_web_search:
                print("[SearchService] Web search disabled - BRAVE_API_KEY not configured")

    def search(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Perform web search and return formatted results.

        Args:
            query: Search query string
            max_results: Maximum number of results to return (default 10)

        Returns:
            List of search results with title, url, and snippet

        Example:
            [
                {
                    "title": "Product Name - Official Site",
                    "url": "https://example.com",
                    "snippet": "Description of the product...",
                },
                ...
            ]
        """
        if not self.search_enabled or not self.brave_search:
            print(f"[SearchService] Search disabled, returning empty results for: {query}")
            return []

        try:
            # Execute search using LangChain's Brave Search tool
            raw_results = self.brave_search.run(query)

            # Parse and format results
            # Brave Search returns a string, we need to parse it
            # The actual return format depends on how BraveSearch is configured
            # For structured data, we might need to use the API directly

            # For now, return a structured format that matches what we need
            # In production, you'd parse the actual Brave API response
            results = self._parse_brave_results(raw_results, max_results)

            print(f"[SearchService] Found {len(results)} results for: {query}")
            return results

        except Exception as e:
            print(f"[SearchService] Search error for query '{query}': {str(e)}")
            return []

    def _parse_brave_results(self, raw_results: str, max_results: int) -> List[Dict[str, Any]]:
        """
        Parse raw Brave Search results into structured format.

        Note: BraveSearch.run() returns a formatted string, not structured data.
        For production use, consider using the Brave API directly via requests
        or using BraveSearch with result_parsing enabled.
        """
        # TODO: CRITICAL - Implement search result parsing to enable web search
        #
        # Current Status: Returns empty list (search always returns 0 results)
        # See: docs/search_integration_status.md for implementation options
        #
        # Option A: Parse LangChain BraveSearch string output
        # Option B: Use Brave API directly for structured JSON (RECOMMENDED)
        #
        # Example Brave API implementation:
        #   response = requests.get(
        #       "https://api.search.brave.com/res/v1/web/search",
        #       headers={"X-Subscription-Token": settings.brave_api_key},
        #       params={"q": query, "count": max_results}
        #   )
        #   return [{"title": r["title"], "url": r["url"], "snippet": r["description"]}
        #           for r in response.json().get("web", {}).get("results", [])]

        results = []
        return results

    def is_available(self) -> bool:
        """Check if search service is available and configured."""
        return self.search_enabled and self.brave_search is not None

    def get_tool_definition(self) -> Dict[str, Any]:
        """
        Get Claude-compatible tool definition for web search.

        Returns a dictionary that can be passed to Claude's API to enable
        the LLM to request web searches.
        """
        return {
            "name": "web_search",
            "description": (
                "Search the web for current information about products, companies, and competitors. "
                "Use this to find real, up-to-date information about competing products in a market. "
                "Returns a list of search results with titles, URLs, and snippets."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query. Be specific and include relevant keywords like product category, features, or market."
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default 10, max 20)",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        }


# Global singleton instance
_search_service = None


def get_search_service() -> SearchService:
    """Get or create the global SearchService instance."""
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service
