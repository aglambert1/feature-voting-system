"""Tests for CompetitorFunctionalAuditAgent — scoped inputs + prompt construction."""

from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.functional_audit_agent import CompetitorFunctionalAuditAgent
from app.models.competitor_intelligence import Base
from app.services.llm_service import LLMService


@pytest.fixture(scope="function")
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def mock_llm_service():
    return Mock(spec=LLMService)


@pytest.fixture
def base_input():
    return {
        'competitor_name': 'Acme',
        'competitor_url': 'https://acme.com',
        'product_context': {
            'product_name': 'VoteFlow',
            'product_category': 'Feature Voting',
            'core_features': ['Voting', 'Triage'],
        },
        'web_search_results': [],
        'user_provided_evidence': [],
    }


def test_get_tools_empty_when_web_research_disabled(db_session, mock_llm_service):
    """With web_research_enabled=False, no tools should be registered even if search service is available."""
    agent = CompetitorFunctionalAuditAgent(
        db=db_session, llm_service=mock_llm_service, web_research_enabled=False
    )
    with patch.object(agent.search_service, 'is_available', return_value=True):
        assert agent.get_tools() == []


def test_get_tools_populated_when_web_research_enabled_and_service_available(db_session, mock_llm_service):
    agent = CompetitorFunctionalAuditAgent(
        db=db_session, llm_service=mock_llm_service, web_research_enabled=True
    )
    with patch.object(agent.search_service, 'is_available', return_value=True), \
         patch.object(agent.search_service, 'get_tool_definition', return_value={"name": "web_search"}):
        tools = agent.get_tools()
    assert len(tools) == 1
    assert tools[0]["name"] == "web_search"


def test_get_tools_empty_when_search_service_unavailable(db_session, mock_llm_service):
    agent = CompetitorFunctionalAuditAgent(
        db=db_session, llm_service=mock_llm_service, web_research_enabled=True
    )
    with patch.object(agent.search_service, 'is_available', return_value=False):
        assert agent.get_tools() == []


def test_user_prompt_omits_web_research_section_when_disabled(db_session, mock_llm_service, base_input):
    agent = CompetitorFunctionalAuditAgent(
        db=db_session, llm_service=mock_llm_service, web_research_enabled=False
    )
    with patch.object(agent.search_service, 'is_available', return_value=True):
        prompt = agent.build_user_prompt(base_input)
    assert "Web Research Instructions" not in prompt


def test_user_prompt_includes_web_research_section_when_enabled(db_session, mock_llm_service, base_input):
    agent = CompetitorFunctionalAuditAgent(
        db=db_session, llm_service=mock_llm_service, web_research_enabled=True
    )
    with patch.object(agent.search_service, 'is_available', return_value=True):
        prompt = agent.build_user_prompt(base_input)
    assert "Web Research Instructions" in prompt


def test_user_prompt_injects_fetched_sources(db_session, mock_llm_service, base_input):
    """fetched_sources should render as a '## Fetched Source Pages' block with URL + text."""
    agent = CompetitorFunctionalAuditAgent(
        db=db_session, llm_service=mock_llm_service, web_research_enabled=False
    )
    base_input['fetched_sources'] = [
        {
            'url': 'https://acme.com/pricing',
            'title': 'Acme Pricing',
            'text': 'Starter: $49/mo. Pro: $199/mo. Enterprise: custom.',
        },
    ]

    prompt = agent.build_user_prompt(base_input)

    assert "## Fetched Source Pages" in prompt
    assert "https://acme.com/pricing" in prompt
    assert "Acme Pricing" in prompt
    assert "Starter: $49/mo" in prompt
    assert "authoritative" in prompt.lower()


def test_user_prompt_no_fetched_sources_section_when_empty(db_session, mock_llm_service, base_input):
    agent = CompetitorFunctionalAuditAgent(
        db=db_session, llm_service=mock_llm_service, web_research_enabled=False
    )
    prompt = agent.build_user_prompt(base_input)
    assert "## Fetched Source Pages" not in prompt


def test_system_prompt_omits_research_strategy_when_web_research_disabled(db_session, mock_llm_service):
    agent = CompetitorFunctionalAuditAgent(
        db=db_session, llm_service=mock_llm_service, web_research_enabled=False
    )
    with patch.object(agent.search_service, 'is_available', return_value=True):
        sys_prompt = agent.get_system_prompt()
    assert "## Research Strategy" not in sys_prompt


def test_concise_user_prompt_preserves_fetched_sources(db_session, mock_llm_service, base_input):
    """Truncation recovery must keep source data — only OUTPUT should shrink."""
    agent = CompetitorFunctionalAuditAgent(
        db=db_session, llm_service=mock_llm_service, web_research_enabled=False
    )
    base_input['fetched_sources'] = [
        {'url': 'https://acme.com/f', 'title': 'Features', 'text': 'Contact sync, email integration.'},
    ]

    concise = agent.build_concise_user_prompt(base_input)

    assert concise is not None
    assert "Contact sync, email integration." in concise
    assert "CONCISE RECOVERY" in concise
    assert "HARD LIMITS" in concise


def test_default_web_research_enabled_is_true(db_session, mock_llm_service):
    agent = CompetitorFunctionalAuditAgent(db=db_session, llm_service=mock_llm_service)
    assert agent.web_research_enabled is True
