"""
Unit tests for Intensity Idea Generator Agent.

Tests the agent's prompt building, output schema, and urgency calculation.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.user import User, UserRole
from app.models.competitor_intelligence import CIProduct, ProductCompetitor
from app.models.competitive_agent import FeatureCluster
from app.agents.intensity_idea_generator import (
    IntensityIdeaGeneratorAgent,
    GeneratedIdeaOutput,
    CompetitiveFeatureInfo
)


@pytest.fixture(scope="function")
def db_session():
    """Create a temporary database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    yield session

    session.close()


@pytest.fixture
def mock_llm_service():
    """Create a mock LLM service."""
    service = Mock()
    return service


@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password="hashed123",
        full_name="Test User",
        role=UserRole.ADMIN
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_product(db_session, test_user):
    """Create a test product."""
    product = CIProduct(
        created_by_user_id=test_user.id,
        product_name="Test Product",
        product_description="A test product for idea generation tests",
        analyzed_category="Project Management"
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


class TestIntensityIdeaGeneratorAgent:
    """Tests for IntensityIdeaGeneratorAgent."""

    def test_init(self, db_session, mock_llm_service):
        """Test agent initialization."""
        agent = IntensityIdeaGeneratorAgent(
            db=db_session,
            llm_service=mock_llm_service,
            product_id=1
        )

        assert agent.db == db_session
        assert agent.llm_service == mock_llm_service
        assert agent.product_id == 1
        assert agent.agent_name == "IntensityIdeaGeneratorAgent"

    def test_get_system_prompt(self, db_session, mock_llm_service):
        """Test system prompt generation."""
        agent = IntensityIdeaGeneratorAgent(
            db=db_session,
            llm_service=mock_llm_service
        )

        prompt = agent.get_system_prompt()

        # Should contain key instructions
        assert "Intensity Idea Generator" in prompt
        assert "Feature Synthesis" in prompt
        assert "Urgency Assessment" in prompt
        assert "CRITICAL" in prompt
        assert "HIGH" in prompt
        assert "MEDIUM" in prompt
        assert "LOW" in prompt
        assert "Differentiation" in prompt

    def test_get_stage(self, db_session, mock_llm_service):
        """Test stage identification."""
        agent = IntensityIdeaGeneratorAgent(
            db=db_session,
            llm_service=mock_llm_service
        )

        assert agent.get_stage() == "intensity_idea_generation"

    def test_get_output_schema(self, db_session, mock_llm_service):
        """Test output schema."""
        agent = IntensityIdeaGeneratorAgent(
            db=db_session,
            llm_service=mock_llm_service
        )

        schema = agent.get_output_schema()
        assert schema == GeneratedIdeaOutput

    def test_build_user_prompt_basic(self, db_session, mock_llm_service):
        """Test user prompt building with basic input."""
        agent = IntensityIdeaGeneratorAgent(
            db=db_session,
            llm_service=mock_llm_service
        )

        input_data = {
            'cluster_name': 'AI Search',
            'cluster_description': 'Search using AI',
            'competitor_count': 3,
            'total_competitors': 5,
            'features': [
                {
                    'competitor_name': 'Competitor A',
                    'feature_name': 'AI Search',
                    'feature_description': 'Smart search with AI'
                },
                {
                    'competitor_name': 'Competitor B',
                    'feature_name': 'Intelligent Search',
                    'feature_description': 'ML-powered search'
                }
            ],
            'product_context': {
                'product_name': 'Test Product',
                'product_category': 'SaaS',
                'product_description': 'A test product'
            }
        }

        prompt = agent.build_user_prompt(input_data)

        # Should contain cluster info
        assert 'AI Search' in prompt
        assert 'Search using AI' in prompt

        # Should contain competitor info
        assert 'Competitor A' in prompt
        assert 'Competitor B' in prompt

        # Should contain product context
        assert 'Test Product' in prompt

        # Should calculate percentage (60%)
        assert '60%' in prompt

        # Should suggest urgency (HIGH for 60% which is 50-74% range)
        assert 'HIGH' in prompt

    def test_build_user_prompt_high_urgency(self, db_session, mock_llm_service):
        """Test user prompt with high urgency situation."""
        agent = IntensityIdeaGeneratorAgent(
            db=db_session,
            llm_service=mock_llm_service
        )

        input_data = {
            'cluster_name': 'Core Feature',
            'cluster_description': 'Essential feature',
            'competitor_count': 8,
            'total_competitors': 10,
            'features': [{'competitor_name': f'Comp {i}', 'feature_name': 'Feature', 'feature_description': ''} for i in range(8)],
            'product_context': {
                'product_name': 'Product',
                'product_category': 'Category',
                'product_description': ''
            }
        }

        prompt = agent.build_user_prompt(input_data)

        # 80% coverage = CRITICAL
        assert 'CRITICAL' in prompt
        assert '80%' in prompt

    def test_build_user_prompt_low_urgency(self, db_session, mock_llm_service):
        """Test user prompt with low urgency situation."""
        agent = IntensityIdeaGeneratorAgent(
            db=db_session,
            llm_service=mock_llm_service
        )

        input_data = {
            'cluster_name': 'Niche Feature',
            'cluster_description': 'Rare feature',
            'competitor_count': 1,
            'total_competitors': 10,
            'features': [{'competitor_name': 'Comp', 'feature_name': 'Feature', 'feature_description': ''}],
            'product_context': {
                'product_name': 'Product',
                'product_category': 'Category',
                'product_description': ''
            }
        }

        prompt = agent.build_user_prompt(input_data)

        # 10% coverage = LOW
        assert 'LOW' in prompt
        assert '10%' in prompt

    def test_calculate_urgency_critical(self, db_session, mock_llm_service):
        """Test urgency calculation for critical level."""
        agent = IntensityIdeaGeneratorAgent(
            db=db_session,
            llm_service=mock_llm_service
        )

        # 75%+ = critical
        assert agent.calculate_urgency(8, 10) == "critical"
        assert agent.calculate_urgency(10, 10) == "critical"

    def test_calculate_urgency_high(self, db_session, mock_llm_service):
        """Test urgency calculation for high level."""
        agent = IntensityIdeaGeneratorAgent(
            db=db_session,
            llm_service=mock_llm_service
        )

        # 50-74% = high
        assert agent.calculate_urgency(5, 10) == "high"
        assert agent.calculate_urgency(7, 10) == "high"

    def test_calculate_urgency_medium(self, db_session, mock_llm_service):
        """Test urgency calculation for medium level."""
        agent = IntensityIdeaGeneratorAgent(
            db=db_session,
            llm_service=mock_llm_service
        )

        # 30-49% = medium
        assert agent.calculate_urgency(3, 10) == "medium"
        assert agent.calculate_urgency(4, 10) == "medium"

    def test_calculate_urgency_low(self, db_session, mock_llm_service):
        """Test urgency calculation for low level."""
        agent = IntensityIdeaGeneratorAgent(
            db=db_session,
            llm_service=mock_llm_service
        )

        # <30% = low
        assert agent.calculate_urgency(2, 10) == "low"
        assert agent.calculate_urgency(1, 10) == "low"

    def test_calculate_urgency_zero_competitors(self, db_session, mock_llm_service):
        """Test urgency calculation with zero total competitors."""
        agent = IntensityIdeaGeneratorAgent(
            db=db_session,
            llm_service=mock_llm_service
        )

        # Edge case: zero competitors
        assert agent.calculate_urgency(0, 0) == "low"

    def test_validate_input_missing_cluster_name(self, db_session, mock_llm_service):
        """Test input validation with missing cluster_name."""
        agent = IntensityIdeaGeneratorAgent(
            db=db_session,
            llm_service=mock_llm_service
        )

        with pytest.raises(ValueError, match="cluster_name"):
            agent._validate_input({
                'features': [{'competitor_name': 'A', 'feature_name': 'F', 'feature_description': ''}],
                'competitor_count': 1,
                'total_competitors': 5
            })

    def test_validate_input_missing_features(self, db_session, mock_llm_service):
        """Test input validation with missing features."""
        agent = IntensityIdeaGeneratorAgent(
            db=db_session,
            llm_service=mock_llm_service
        )

        with pytest.raises(ValueError, match="features"):
            agent._validate_input({
                'cluster_name': 'Test',
                'competitor_count': 1,
                'total_competitors': 5
            })

    def test_validate_input_empty_features(self, db_session, mock_llm_service):
        """Test input validation with empty features list."""
        agent = IntensityIdeaGeneratorAgent(
            db=db_session,
            llm_service=mock_llm_service
        )

        with pytest.raises(ValueError, match="features"):
            agent._validate_input({
                'cluster_name': 'Test',
                'features': [],
                'competitor_count': 1,
                'total_competitors': 5
            })

    def test_validate_input_missing_counts(self, db_session, mock_llm_service):
        """Test input validation with missing counts."""
        agent = IntensityIdeaGeneratorAgent(
            db=db_session,
            llm_service=mock_llm_service
        )

        with pytest.raises(ValueError, match="competitor_count"):
            agent._validate_input({
                'cluster_name': 'Test',
                'features': [{'competitor_name': 'A', 'feature_name': 'F', 'feature_description': ''}],
                'total_competitors': 5
            })

        with pytest.raises(ValueError, match="total_competitors"):
            agent._validate_input({
                'cluster_name': 'Test',
                'features': [{'competitor_name': 'A', 'feature_name': 'F', 'feature_description': ''}],
                'competitor_count': 1
            })

    def test_validate_input_valid(self, db_session, mock_llm_service):
        """Test input validation with valid input."""
        agent = IntensityIdeaGeneratorAgent(
            db=db_session,
            llm_service=mock_llm_service
        )

        # Should not raise
        agent._validate_input({
            'cluster_name': 'Test Cluster',
            'features': [{'competitor_name': 'A', 'feature_name': 'F', 'feature_description': 'Desc'}],
            'competitor_count': 1,
            'total_competitors': 5
        })


class TestGeneratedIdeaOutput:
    """Tests for GeneratedIdeaOutput Pydantic model."""

    def test_valid_output(self):
        """Test creating valid output."""
        output = GeneratedIdeaOutput(
            title="AI-Powered Search with Natural Language Queries",
            what_description="A search feature that uses AI to understand natural language",
            why_description="3 of 5 competitors have this, representing 60% market coverage",
            use_case_description="User types a question, gets relevant results",
            category="Search",
            competitive_urgency="medium",
            urgency_reasoning="60% competitor coverage indicates growing market expectation",
            differentiation_opportunities=["Add voice search", "Better UX"],
            confidence=0.85
        )

        assert output.title == "AI-Powered Search with Natural Language Queries"
        assert output.competitive_urgency == "medium"
        assert len(output.differentiation_opportunities) == 2
        assert output.confidence == 0.85

    def test_output_title_max_length(self):
        """Test title max length validation."""
        long_title = "A" * 300

        with pytest.raises(Exception):  # Pydantic validation error
            GeneratedIdeaOutput(
                title=long_title,
                what_description="What",
                why_description="Why",
                use_case_description="Use case",
                category="Category",
                urgency_reasoning="Reasoning",
                confidence=0.5
            )

    def test_output_confidence_bounds(self):
        """Test confidence value bounds."""
        # Valid confidence
        output = GeneratedIdeaOutput(
            title="Test",
            what_description="What",
            why_description="Why",
            use_case_description="Use case",
            category="Category",
            urgency_reasoning="Reasoning",
            confidence=0.0
        )
        assert output.confidence == 0.0

        output = GeneratedIdeaOutput(
            title="Test",
            what_description="What",
            why_description="Why",
            use_case_description="Use case",
            category="Category",
            urgency_reasoning="Reasoning",
            confidence=1.0
        )
        assert output.confidence == 1.0

        # Invalid confidence
        with pytest.raises(Exception):
            GeneratedIdeaOutput(
                title="Test",
                what_description="What",
                why_description="Why",
                use_case_description="Use case",
                category="Category",
                urgency_reasoning="Reasoning",
                confidence=1.5
            )

    def test_output_defaults(self):
        """Test default values."""
        output = GeneratedIdeaOutput(
            title="Test",
            what_description="What",
            why_description="Why",
            use_case_description="Use case",
            category="Category",
            urgency_reasoning="Reasoning",
            confidence=0.5
        )

        assert output.competitive_urgency == "medium"  # default
        assert output.differentiation_opportunities == []  # default


class TestCompetitiveFeatureInfo:
    """Tests for CompetitiveFeatureInfo model."""

    def test_valid_feature_info(self):
        """Test creating valid feature info."""
        info = CompetitiveFeatureInfo(
            competitor_name="Competitor A",
            feature_name="Smart Search",
            feature_description="AI-powered search functionality"
        )

        assert info.competitor_name == "Competitor A"
        assert info.feature_name == "Smart Search"
        assert info.feature_description == "AI-powered search functionality"

    def test_feature_info_default_description(self):
        """Test default empty description."""
        info = CompetitiveFeatureInfo(
            competitor_name="Competitor A",
            feature_name="Smart Search"
        )

        assert info.feature_description == ""


class TestAgentExecution:
    """Tests for agent execution with mocked LLM."""

    def test_execute_success(self, db_session, mock_llm_service):
        """Test successful agent execution."""
        agent = IntensityIdeaGeneratorAgent(
            db=db_session,
            llm_service=mock_llm_service,
            product_id=1
        )

        # Mock successful LLM response
        mock_llm_service.call_agent.return_value = {
            'content': '''{
                "title": "AI-Powered Search",
                "what_description": "Implement AI search",
                "why_description": "Competitors have it",
                "use_case_description": "User searches",
                "category": "Search",
                "competitive_urgency": "high",
                "urgency_reasoning": "Many competitors",
                "differentiation_opportunities": ["Better UX"],
                "confidence": 0.85
            }''',
            'tokens_used': 500
        }

        input_data = {
            'cluster_name': 'AI Search',
            'cluster_description': 'Search with AI',
            'competitor_count': 5,
            'total_competitors': 8,
            'features': [
                {'competitor_name': 'A', 'feature_name': 'Search', 'feature_description': 'Desc'}
            ],
            'product_context': {
                'product_name': 'Product',
                'product_category': 'SaaS',
                'product_description': 'Description'
            }
        }

        result = agent.execute(input_data)

        assert result['title'] == "AI-Powered Search"
        assert result['competitive_urgency'] == "high"
        assert result['confidence'] == 0.85
        mock_llm_service.call_agent.assert_called_once()

    def test_execute_with_markdown_response(self, db_session, mock_llm_service):
        """Test agent execution with markdown-wrapped JSON response."""
        agent = IntensityIdeaGeneratorAgent(
            db=db_session,
            llm_service=mock_llm_service,
            product_id=1
        )

        # Mock LLM response with markdown
        mock_llm_service.call_agent.return_value = {
            'content': '''```json
{
    "title": "Real-time Collaboration",
    "what_description": "Live editing",
    "why_description": "Market demand",
    "use_case_description": "Users edit together",
    "category": "Collaboration",
    "competitive_urgency": "critical",
    "urgency_reasoning": "80% of competitors",
    "differentiation_opportunities": ["Better conflict resolution"],
    "confidence": 0.9
}
```''',
            'tokens_used': 400
        }

        input_data = {
            'cluster_name': 'Collab',
            'cluster_description': 'Collaboration features',
            'competitor_count': 8,
            'total_competitors': 10,
            'features': [
                {'competitor_name': 'A', 'feature_name': 'Collab', 'feature_description': ''}
            ],
            'product_context': {
                'product_name': 'Product',
                'product_category': 'SaaS',
                'product_description': ''
            }
        }

        result = agent.execute(input_data)

        assert result['title'] == "Real-time Collaboration"
        assert result['competitive_urgency'] == "critical"
