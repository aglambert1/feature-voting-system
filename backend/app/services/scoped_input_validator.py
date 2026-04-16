"""
Validation for scoped-input params (`source_urls`) shared across MCP and REST surfaces.

Product analysis and competitor audit both accept a list of URLs to ground the
analysis in specific pages. This module enforces size caps and returns a
consistent, human-readable error shape for both callers.

Per-URL character caps are applied during URL fetch in the Celery task
(see `MAX_URL_EXTRACT_CHARS`) — oversized extracts are truncated, not rejected.
"""

from typing import List, Optional


MAX_SOURCE_URLS = 5
MAX_URL_EXTRACT_CHARS = 8_000


class ScopedInputError(ValueError):
    """Raised with structured details for REST 400 / MCP error dict."""

    def __init__(self, message: str, field: str, limit: int, got: int):
        super().__init__(message)
        self.payload = {
            "error": message,
            "error_code": "SCOPED_INPUT_LIMIT_EXCEEDED",
            "field": field,
            "limit": limit,
            "got": got,
        }


def validate_scoped_inputs(source_urls: Optional[List[str]]) -> List[str]:
    """Validate scoped inputs; raise ScopedInputError with a human-readable message on violation.

    Args:
        source_urls: Optional list of URLs to fetch for the analysis.

    Returns:
        The normalized list of URLs (never None).

    Raises:
        ScopedInputError: If the URL list exceeds MAX_SOURCE_URLS.
    """
    urls = source_urls or []
    if len(urls) > MAX_SOURCE_URLS:
        raise ScopedInputError(
            f"Too many source URLs (got {len(urls)}, max {MAX_SOURCE_URLS}). "
            f"Please trim the list.",
            field="source_urls",
            limit=MAX_SOURCE_URLS,
            got=len(urls),
        )
    return urls
