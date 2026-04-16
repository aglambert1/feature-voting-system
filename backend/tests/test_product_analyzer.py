"""
Unit tests for Product Analyzer Agent.

Tests the ProductAnalyzerAgent's ability to analyze product descriptions
and extract structured information.
"""

import pytest
from unittest.mock import Mock

from app.agents.product_analyzer import ProductAnalyzerAgent, ProductAnalysisOutput
from app.services.llm_service import LLMService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.competitor_intelligence import Base


@pytest.fixture(scope="function")
def db_session():
    """Create a temporary in-memory database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def mock_llm_service():
    """Mock LLM service for testing."""
    service = Mock(spec=LLMService)
    return service


def test_product_analyzer_agent_successful_execution(db_session, mock_llm_service):
    """Test ProductAnalyzerAgent with successful execution."""
    # Mock LLM response
    mock_llm_service.call_agent.return_value = {
        "content": '''{
    "product_name": "Test CRM",
    "product_category": "CRM Software",
    "core_features": ["Contact Management", "Sales Pipeline", "Reporting", "Email Integration", "Mobile App"],
    "detailed_features": [
        {"name": "Contact Management", "description": "Manage customer contacts and accounts", "category": "Core", "confidence": 0.95, "source_reference": "product description"},
        {"name": "Sales Pipeline", "description": "Track deals through sales stages", "category": "Sales", "confidence": 0.95, "source_reference": "product description"},
        {"name": "Reporting Dashboard", "description": "Visual reports and analytics", "category": "Analytics", "confidence": 0.90, "source_reference": "product description"},
        {"name": "Email Integration", "description": "Sync with email providers", "category": "Integration", "confidence": 0.85, "source_reference": "product description"},
        {"name": "Mobile App", "description": "Access CRM on mobile devices", "category": "Platform", "confidence": 0.80, "source_reference": "product description"}
    ],
    "target_users": "Small to medium-sized B2B companies with 10-100 employees",
    "value_propositions": ["Easy to use", "Affordable pricing"],
    "competitor_search_keywords": ["crm software", "contact management", "sales pipeline", "customer relationship management", "small business crm"]
}''',
        "tokens_used": 200,
        "model": "claude-sonnet-4-5-20250929",
        "stop_reason": "end_turn"
    }

    # web_research_enabled=False → no tools registered → uses call_agent (not call_agent_with_tools)
    agent = ProductAnalyzerAgent(db=db_session, llm_service=mock_llm_service, web_research_enabled=False)

    result = agent.execute({
        'product_name': 'Test CRM',
        'product_description': 'A CRM system designed for small businesses with contact management and sales tracking',
        'source_type': 'text'
    })

    # Verify output structure
    assert result['product_name'] == 'Test CRM'
    assert result['product_category'] == 'CRM Software'
    assert len(result['core_features']) >= 3
    assert len(result['competitor_search_keywords']) >= 3
    assert len(result['value_propositions']) >= 1

    # Verify LLM was called
    mock_llm_service.call_agent.assert_called_once()
    call_args = mock_llm_service.call_agent.call_args
    assert call_args[1]["agent_name"] == "ProductAnalyzerAgent"


def test_product_analyzer_output_schema():
    """Test that ProductAnalysisOutput schema validates correctly."""
    # Valid output
    valid_data = {
        "product_name": "Test Product",
        "product_category": "Software",
        "core_features": ["Feature 1", "Feature 2", "Feature 3"],
        "detailed_features": [
            {"name": "Feature 1", "description": "First feature", "category": "Core", "confidence": 0.9, "source_reference": "desc"},
            {"name": "Feature 2", "description": "Second feature", "category": "Core", "confidence": 0.9, "source_reference": "desc"},
            {"name": "Feature 3", "description": "Third feature", "category": "Core", "confidence": 0.85, "source_reference": "desc"},
            {"name": "Feature 4", "description": "Fourth feature", "category": "UI", "confidence": 0.8, "source_reference": "desc"},
            {"name": "Feature 5", "description": "Fifth feature", "category": "API", "confidence": 0.75, "source_reference": "desc"},
        ],
        "target_users": "Developers",
        "value_propositions": ["Fast", "Reliable"],
        "competitor_search_keywords": ["software", "tool", "platform"]
    }

    output = ProductAnalysisOutput(**valid_data)
    assert output.product_name == "Test Product"
    assert len(output.core_features) == 3
    assert len(output.detailed_features) == 5
    assert len(output.competitor_search_keywords) == 3


def test_product_analyzer_stage_name(db_session, mock_llm_service):
    """Test that agent reports correct stage name."""
    agent = ProductAnalyzerAgent(db=db_session, llm_service=mock_llm_service)
    assert agent.get_stage() == "product_analysis"


def test_build_user_prompt_injects_fetched_sources(db_session, mock_llm_service):
    """fetched_sources should render as a '## Fetched Source Pages' block with URL + text."""
    agent = ProductAnalyzerAgent(db=db_session, llm_service=mock_llm_service, web_research_enabled=False)

    prompt = agent.build_user_prompt({
        'product_name': 'Test CRM',
        'product_description': 'A CRM',
        'source_type': 'text',
        'fetched_sources': [
            {
                'url': 'https://test-crm.com/features',
                'title': 'CRM Features',
                'text': 'Contact sync with Gmail and Outlook.',
            },
        ],
    })

    assert "## Fetched Source Pages" in prompt
    assert "https://test-crm.com/features" in prompt
    assert "Contact sync with Gmail and Outlook." in prompt


def test_build_user_prompt_no_fetched_sources_section_when_empty(db_session, mock_llm_service):
    agent = ProductAnalyzerAgent(db=db_session, llm_service=mock_llm_service, web_research_enabled=False)
    prompt = agent.build_user_prompt({
        'product_name': 'Test',
        'product_description': 'Thing',
        'source_type': 'text',
    })
    assert "## Fetched Source Pages" not in prompt


def test_build_concise_user_prompt_preserves_fetched_sources(db_session, mock_llm_service):
    """Truncation recovery must keep source data — only OUTPUT should shrink."""
    agent = ProductAnalyzerAgent(db=db_session, llm_service=mock_llm_service, web_research_enabled=False)

    concise = agent.build_concise_user_prompt({
        'product_name': 'Test CRM',
        'product_description': 'A CRM',
        'source_type': 'text',
        'fetched_sources': [
            {'url': 'https://test-crm.com/f', 'title': 'Features', 'text': 'Gmail sync.'},
        ],
    })

    assert concise is not None
    assert "Gmail sync." in concise
    assert "HARD LIMITS" in concise
