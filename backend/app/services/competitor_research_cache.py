"""
CompetitorResearchCache — per-competitor Brave search result cache.

Brave web-search results are fetched once per competitor and reused for
subsequent audits within a TTL window (default 24h, configurable via
`settings.competitor_research_cache_ttl_hours`). This eliminates:

- Repeat Brave API calls on re-audits within the TTL
- The tool-use loop round-trips during the audit LLM call (when cached
  results are passed directly into the prompt as structured context)

Each refresh runs a small set of targeted queries (features, pricing,
integrations, reviews, vs-product). Results are merged and deduped by URL,
then written to `ProductCompetitor.cached_search_results` with a timestamp.

Typical usage from `functional_audit_task`:

    cache = CompetitorResearchCache(db)
    cached = cache.get_fresh(competitor)
    if cached is not None:
        web_search_results = cached
    elif web_research_enabled:
        web_search_results = cache.refresh(competitor, product_context)
    else:
        web_search_results = []
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.competitor_intelligence import ProductCompetitor
from app.services.search_service import SearchService, get_search_service


# Maximum number of queries to run per refresh. Keeping this bounded caps
# Brave API usage and latency per refresh.
MAX_QUERIES_PER_REFRESH = 5

# Per-query result cap. Each query returns up to this many results before
# deduping across all queries.
PER_QUERY_MAX_RESULTS = 5


class CompetitorResearchCache:
    """Read/refresh Brave search cache on ProductCompetitor."""

    def __init__(self, db: Session, search_service: Optional[SearchService] = None):
        self.db = db
        self.search_service = search_service or get_search_service()
        self.ttl_hours = settings.competitor_research_cache_ttl_hours

    def get_fresh(self, competitor: ProductCompetitor) -> Optional[List[Dict[str, Any]]]:
        """Return cached results if within TTL and non-empty, else None.

        Returns None (not []) on cache miss so callers can distinguish
        "no cache" from "cache ran but found no results".
        """
        if not competitor.cached_search_at or not competitor.cached_search_results:
            return None
        cached_at = competitor.cached_search_at
        if cached_at.tzinfo is None:
            cached_at = cached_at.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - cached_at
        if age > timedelta(hours=self.ttl_hours):
            return None
        return competitor.cached_search_results

    def refresh(
        self,
        competitor: ProductCompetitor,
        product_context: Dict[str, Any],
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Run targeted queries, merge+dedupe by URL, persist, and return.

        Always writes a fresh timestamp to `cached_search_at` so an empty
        result set still counts as "recently checked" — prevents tight retry
        loops when the search service is down.

        Args:
            competitor: The ProductCompetitor to refresh.
            product_context: Dict with at least `product_name` for the
                "vs" query.
            progress_cb: Optional callback invoked as `(i, total)` after
                each query; lets callers emit progress updates.

        Returns:
            Deduped list of `{title, url, snippet}` dicts.
        """
        queries = self._build_queries(competitor, product_context)
        merged: List[Dict[str, Any]] = []
        seen_urls: set[str] = set()

        for i, query in enumerate(queries, 1):
            if progress_cb is not None:
                progress_cb(i, len(queries))
            results = self.search_service.search(query, max_results=PER_QUERY_MAX_RESULTS)
            for r in results:
                url = r.get("url")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                merged.append(r)

        competitor.cached_search_results = merged
        competitor.cached_search_at = datetime.now(timezone.utc)
        self.db.commit()
        return merged

    def _build_queries(
        self,
        competitor: ProductCompetitor,
        product_context: Dict[str, Any],
    ) -> List[str]:
        """Build the targeted query list for a refresh.

        Order matters: most-useful queries first, so if rate limiting kicks
        in mid-refresh we still have the highest-signal results cached.
        """
        name = competitor.competitor_name
        product_name = (product_context or {}).get("product_name", "")

        queries = [
            f"{name} features",
            f"{name} pricing",
            f"{name} integrations",
            f"{name} reviews G2",
        ]
        # Only add the comparison query when we actually have a product name.
        if product_name:
            queries.append(f"{name} vs {product_name}")

        return queries[:MAX_QUERIES_PER_REFRESH]
