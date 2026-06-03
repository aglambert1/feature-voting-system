"""Tests for CompetitorResearchCache — TTL logic, refresh, dedupe."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.competitor_intelligence import CIProduct, ProductCompetitor
from app.models.user import User, UserRole
from app.services.competitor_research_cache import CompetitorResearchCache
from app.services.search_service import SearchService


@pytest.fixture(scope="function")
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def owner(db_session):
    u = User(
        email="owner@test.com",
        username="owner",
        hashed_password="h",
        full_name="Owner",
        role=UserRole.PRODUCT_OWNER,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def product(db_session, owner):
    p = CIProduct(
        product_name="VoteFlow",
        product_description="x" * 60,
        product_category="Feature Voting",
        created_by_user_id=owner.id,
        status="active",
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture
def competitor(db_session, product):
    c = ProductCompetitor(
        product_id=product.id,
        competitor_name="Acme",
        competitor_url="https://acme.com",
        status="active",
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def mock_search():
    return Mock(spec=SearchService)


def test_get_fresh_returns_none_when_cache_empty(db_session, competitor, mock_search):
    cache = CompetitorResearchCache(db_session, search_service=mock_search)
    assert cache.get_fresh(competitor) is None


def test_get_fresh_returns_none_when_cached_at_missing(db_session, competitor, mock_search):
    # Results present but no timestamp — treat as no cache.
    competitor.cached_search_results = [{"url": "https://a.com", "title": "a", "snippet": "x"}]
    competitor.cached_search_at = None
    db_session.commit()
    cache = CompetitorResearchCache(db_session, search_service=mock_search)
    assert cache.get_fresh(competitor) is None


def test_get_fresh_returns_none_when_cache_stale(db_session, competitor, mock_search):
    competitor.cached_search_results = [{"url": "https://a.com", "title": "a", "snippet": "x"}]
    competitor.cached_search_at = datetime.now(timezone.utc) - timedelta(hours=48)
    db_session.commit()
    cache = CompetitorResearchCache(db_session, search_service=mock_search)
    cache.ttl_hours = 24  # Explicit so this test is independent of settings
    assert cache.get_fresh(competitor) is None


def test_get_fresh_returns_cached_when_within_ttl(db_session, competitor, mock_search):
    payload = [{"url": "https://a.com", "title": "a", "snippet": "x"}]
    competitor.cached_search_results = payload
    competitor.cached_search_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db_session.commit()
    cache = CompetitorResearchCache(db_session, search_service=mock_search)
    cache.ttl_hours = 24
    assert cache.get_fresh(competitor) == payload


def test_refresh_writes_results_and_timestamp(db_session, competitor, mock_search):
    mock_search.search.return_value = [
        {"url": "https://acme.com/features", "title": "Features", "snippet": "s1"},
    ]
    cache = CompetitorResearchCache(db_session, search_service=mock_search)

    before = datetime.now(timezone.utc)
    results = cache.refresh(competitor, {"product_name": "VoteFlow"})
    after = datetime.now(timezone.utc)

    # Refreshed payload persisted on the competitor row
    db_session.refresh(competitor)
    assert competitor.cached_search_results == results
    assert len(results) > 0
    cached_at = competitor.cached_search_at
    if cached_at.tzinfo is None:
        cached_at = cached_at.replace(tzinfo=timezone.utc)
    assert before <= cached_at <= after


def test_refresh_dedupes_by_url(db_session, competitor, mock_search):
    # SearchService returns overlapping results across queries.
    duplicate_hit = {"url": "https://acme.com/dup", "title": "Dup", "snippet": "x"}
    unique_hit = {"url": "https://acme.com/unique", "title": "Unique", "snippet": "y"}
    mock_search.search.return_value = [duplicate_hit, unique_hit]

    cache = CompetitorResearchCache(db_session, search_service=mock_search)
    results = cache.refresh(competitor, {"product_name": "VoteFlow"})

    urls = [r["url"] for r in results]
    assert urls.count("https://acme.com/dup") == 1
    assert urls.count("https://acme.com/unique") == 1


def test_refresh_handles_empty_search_results(db_session, competitor, mock_search):
    """When SearchService returns [] (e.g. rate-limited or disabled), still
    write a fresh timestamp so we don't spin in a retry loop."""
    mock_search.search.return_value = []
    cache = CompetitorResearchCache(db_session, search_service=mock_search)

    results = cache.refresh(competitor, {"product_name": "VoteFlow"})

    assert results == []
    db_session.refresh(competitor)
    assert competitor.cached_search_results == []
    assert competitor.cached_search_at is not None


def test_refresh_calls_progress_cb_once_per_query(db_session, competitor, mock_search):
    mock_search.search.return_value = []
    cache = CompetitorResearchCache(db_session, search_service=mock_search)
    calls: list[tuple[int, int]] = []

    cache.refresh(
        competitor, {"product_name": "VoteFlow"},
        progress_cb=lambda i, total: calls.append((i, total)),
    )

    # Progress increments from 1..N, total is consistent
    assert len(calls) > 0
    totals = {t for _, t in calls}
    assert len(totals) == 1
    assert calls[0][0] == 1
    assert calls[-1][0] == calls[-1][1]


def test_build_queries_skips_vs_when_product_name_missing(db_session, competitor, mock_search):
    cache = CompetitorResearchCache(db_session, search_service=mock_search)

    with_product = cache._build_queries(competitor, {"product_name": "VoteFlow"})
    without_product = cache._build_queries(competitor, {})

    # "vs" query only appears when product_name is set
    assert any("vs VoteFlow" in q for q in with_product)
    assert not any(" vs " in q for q in without_product)


def test_refresh_queries_include_competitor_name(db_session, competitor, mock_search):
    mock_search.search.return_value = []
    cache = CompetitorResearchCache(db_session, search_service=mock_search)

    cache.refresh(competitor, {"product_name": "VoteFlow"})

    # Every query sent to SearchService mentions the competitor name
    queries_sent = [call.args[0] for call in mock_search.search.call_args_list]
    assert all("Acme" in q for q in queries_sent)
    assert any("features" in q for q in queries_sent)
    assert any("pricing" in q for q in queries_sent)
