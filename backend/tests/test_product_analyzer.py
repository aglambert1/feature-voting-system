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
    "target_users": "Small to medium-sized B2B companies with 10-100 employees",
    "value_propositions": ["Easy to use", "Affordable pricing"],
    "competitor_search_keywords": ["crm software", "contact management", "sales pipeline", "customer relationship management", "small business crm"]
}''',
        "tokens_used": 200,
        "model": "claude-sonnet-4-5-20250929",
        "stop_reason": "end_turn"
    }

    agent = ProductAnalyzerAgent(db=db_session, llm_service=mock_llm_service)

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
        "target_users": "Developers",
        "value_propositions": ["Fast", "Reliable"],
        "competitor_search_keywords": ["software", "tool", "platform"]
    }

    output = ProductAnalysisOutput(**valid_data)
    assert output.product_name == "Test Product"
    assert len(output.core_features) == 3
    assert len(output.competitor_search_keywords) == 3


def test_product_analyzer_stage_name(db_session, mock_llm_service):
    """Test that agent reports correct stage name."""
    agent = ProductAnalyzerAgent(db=db_session, llm_service=mock_llm_service)
    assert agent.get_stage() == "product_analysis"
