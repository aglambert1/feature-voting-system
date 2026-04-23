"""Tests for SearchService Redis cache layer.

Covers cache HIT/MISS paths, query normalization, max_results slicing,
TTL differentiation for empty results, and graceful fallback when Redis
is unavailable or returns errors.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.search_service import SearchService, _normalize_query


# --- Helpers ---


def _fake_brave_response(results: list[dict]) -> MagicMock:
    """Build a MagicMock mimicking a successful Brave API response."""
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "web": {
            "results": [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "description": r.get("snippet", ""),
                }
                for r in results
            ]
        }
    }
    return resp


def _build_service(redis_client, search_enabled=True) -> SearchService:
    """Build a SearchService with search_enabled forced on, regardless of env."""
    svc = SearchService(redis_client=redis_client)
    # The real constructor may disable search if BRAVE_API_KEY is unset in the
    # test env. Force-enable for cache behavior tests.
    svc.search_enabled = search_enabled
    return svc


# --- Query normalization ---


def test_normalize_query_lowercases_and_trims():
    assert _normalize_query("  Expensify Features  ") == "expensify features"


def test_normalize_query_collapses_whitespace():
    assert _normalize_query("concur\t\texpense\n  alternatives") == "concur expense alternatives"


def test_cache_key_is_stable_across_case_and_whitespace():
    svc = _build_service(redis_client=False)
    k1 = svc._cache_key("Expensify features")
    k2 = svc._cache_key("  EXPENSIFY   features ")
    assert k1 == k2
    assert k1.startswith("web_search:")


# --- Cache HIT path ---


def test_cache_hit_skips_brave_fetch():
    fake_cached = [{"title": "T", "url": "https://u.com", "snippet": "S"}]
    redis_mock = MagicMock()
    redis_mock.get.return_value = json.dumps(fake_cached)

    svc = _build_service(redis_client=redis_mock)

    with patch("app.services.search_service.requests.get") as http_get:
        results = svc.search("Expensify features", max_results=5)

    assert results == fake_cached
    http_get.assert_not_called()


def test_cache_hit_slices_to_max_results():
    # Cache holds 20 full results; caller asks for 5.
    cached = [{"title": f"t{i}", "url": f"https://u{i}.com", "snippet": "s"} for i in range(20)]
    redis_mock = MagicMock()
    redis_mock.get.return_value = json.dumps(cached)

    svc = _build_service(redis_client=redis_mock)
    results = svc.search("Expensify", max_results=5)

    assert len(results) == 5
    assert results == cached[:5]


# --- Cache MISS path writes full 20-result payload ---


def test_cache_miss_fetches_brave_at_cap_and_writes_full_payload():
    redis_mock = MagicMock()
    redis_mock.get.return_value = None

    # Simulate Brave returning 20 results even though caller asked for 5.
    brave_payload = [
        {"title": f"t{i}", "url": f"https://u{i}.com", "snippet": f"s{i}"} for i in range(20)
    ]

    svc = _build_service(redis_client=redis_mock)
    svc._last_request_time = 0  # far enough in the past that the rate-limit sleep is skipped

    with patch(
        "app.services.search_service.requests.get",
        return_value=_fake_brave_response(brave_payload),
    ) as http_get:
        results = svc.search("Zoho Expense", max_results=5)

    # Caller got its 5.
    assert len(results) == 5

    # Brave was called with count=20 (the internal cap), not 5.
    assert http_get.call_count == 1
    call_kwargs = http_get.call_args.kwargs
    assert call_kwargs["params"]["count"] == 20

    # All 20 were written to cache — the cache stores the full set.
    assert redis_mock.setex.call_count == 1
    key, ttl, stored_json = redis_mock.setex.call_args.args
    assert key.startswith("web_search:")
    assert ttl > 0
    stored = json.loads(stored_json)
    assert len(stored) == 20


def test_cache_miss_caches_empty_results_with_shorter_ttl():
    redis_mock = MagicMock()
    redis_mock.get.return_value = None

    svc = _build_service(redis_client=redis_mock)
    svc._last_request_time = 0

    with patch(
        "app.services.search_service.requests.get",
        return_value=_fake_brave_response([]),
    ):
        results = svc.search("totally empty query that returns nothing")

    assert results == []
    assert redis_mock.setex.call_count == 1
    _, ttl, stored_json = redis_mock.setex.call_args.args
    assert json.loads(stored_json) == []

    # Default non-empty TTL is 86400, empty is 3600 — confirm we used the short one.
    from app.config import settings
    assert ttl == settings.web_search_cache_empty_ttl_seconds
    assert ttl < settings.web_search_cache_ttl_seconds


# --- Redis failure graceful fallback ---


def test_redis_get_failure_falls_through_to_live_fetch():
    redis_mock = MagicMock()
    redis_mock.get.side_effect = RuntimeError("Redis is down")

    brave_payload = [{"title": "Live", "url": "https://live.com", "snippet": "x"}]

    svc = _build_service(redis_client=redis_mock)
    svc._last_request_time = 0

    with patch(
        "app.services.search_service.requests.get",
        return_value=_fake_brave_response(brave_payload),
    ):
        results = svc.search("something")

    # Got live results despite Redis GET blowing up.
    assert len(results) == 1
    assert results[0]["url"] == "https://live.com"


def test_redis_setex_failure_does_not_crash_search():
    redis_mock = MagicMock()
    redis_mock.get.return_value = None
    redis_mock.setex.side_effect = RuntimeError("Redis SET failed")

    brave_payload = [{"title": "Live", "url": "https://live.com", "snippet": "x"}]

    svc = _build_service(redis_client=redis_mock)
    svc._last_request_time = 0

    with patch(
        "app.services.search_service.requests.get",
        return_value=_fake_brave_response(brave_payload),
    ):
        results = svc.search("something")

    # SETEX error is swallowed — caller still gets the live results.
    assert len(results) == 1


def test_no_redis_client_still_works_live():
    # redis_client=False disables caching entirely.
    svc = _build_service(redis_client=False)
    svc._last_request_time = 0

    brave_payload = [{"title": "T", "url": "https://u.com", "snippet": "s"}]
    with patch(
        "app.services.search_service.requests.get",
        return_value=_fake_brave_response(brave_payload),
    ):
        results = svc.search("anything")

    assert len(results) == 1


def test_malformed_cache_entry_treated_as_miss():
    redis_mock = MagicMock()
    redis_mock.get.return_value = "not valid json {{{"

    brave_payload = [{"title": "T", "url": "https://u.com", "snippet": "s"}]
    svc = _build_service(redis_client=redis_mock)
    svc._last_request_time = 0

    with patch(
        "app.services.search_service.requests.get",
        return_value=_fake_brave_response(brave_payload),
    ):
        results = svc.search("something")

    assert len(results) == 1  # lived through the malformed entry


# --- Disabled search short-circuits before Redis ---


def test_search_disabled_returns_empty_without_touching_redis():
    redis_mock = MagicMock()
    svc = _build_service(redis_client=redis_mock, search_enabled=False)

    with patch("app.services.search_service.requests.get") as http_get:
        results = svc.search("anything")

    assert results == []
    http_get.assert_not_called()
    redis_mock.get.assert_not_called()
