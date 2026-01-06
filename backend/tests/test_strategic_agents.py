"""
Unit tests for Strategic Analysis Agents.

Tests the Pricing, Positioning, Changes, Momentum, and Financials agents.
"""

import pytest
from unittest.mock import Mock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.agents.pricing_analyzer import (
    PricingAnalyzerAgent,
    PricingAnalysisOutput,
    PricingTier
)
from app.agents.positioning_analyzer import (
    PositioningAnalyzerAgent,
    PositioningAnalysisOutput,
    ValueProposition
)
from app.agents.changes_tracker import (
    ChangesTrackerAgent,
    ChangesTrackingOutput,
    ChangeEvent
)
from app.agents.momentum_analyzer import (
    MomentumAnalyzerAgent,
    MomentumAnalysisOutput,
    CustomerWin,
    PartnershipInfo,
    MarketExpansion
)
from app.agents.financials_analyzer import (
    FinancialsAnalyzerAgent,
    FinancialsAnalysisOutput,
    FundingRound
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
    return Mock()


class TestPricingAnalyzerAgent:
    """Tests for PricingAnalyzerAgent."""

    def test_init(self, db_session, mock_llm_service):
        """Test agent initialization."""
        agent = PricingAnalyzerAgent(db=db_session, llm_service=mock_llm_service)
        assert agent.agent_name == "PricingAnalyzerAgent"

    def test_get_stage(self, db_session, mock_llm_service):
        """Test stage identification."""
        agent = PricingAnalyzerAgent(db=db_session, llm_service=mock_llm_service)
        assert agent.get_stage() == "pricing_analysis"

    def test_get_output_schema(self, db_session, mock_llm_service):
        """Test output schema."""
        agent = PricingAnalyzerAgent(db=db_session, llm_service=mock_llm_service)
        assert agent.get_output_schema() == PricingAnalysisOutput

    def test_get_system_prompt_contains_key_elements(self, db_session, mock_llm_service):
        """Test system prompt has required elements."""
        agent = PricingAnalyzerAgent(db=db_session, llm_service=mock_llm_service)
        prompt = agent.get_system_prompt()
        assert "Pricing Analyzer" in prompt
        assert "freemium" in prompt.lower()
        assert "subscription" in prompt.lower()

    def test_build_user_prompt(self, db_session, mock_llm_service):
        """Test user prompt building."""
        agent = PricingAnalyzerAgent(db=db_session, llm_service=mock_llm_service)
        input_data = {
            'competitor_name': 'Acme Inc',
            'competitor_url': 'https://acme.com',
            'pricing_url': 'https://acme.com/pricing',
            'pricing_content': 'Pro plan: $29/month. Enterprise: Contact sales.'
        }
        prompt = agent.build_user_prompt(input_data)
        assert 'Acme Inc' in prompt
        assert '$29/month' in prompt

    def test_validate_input_missing_name(self, db_session, mock_llm_service):
        """Test validation with missing competitor name."""
        agent = PricingAnalyzerAgent(db=db_session, llm_service=mock_llm_service)
        with pytest.raises(ValueError, match="competitor_name"):
            agent._validate_input({'pricing_content': 'test'})

    def test_validate_input_missing_content(self, db_session, mock_llm_service):
        """Test validation with missing content."""
        agent = PricingAnalyzerAgent(db=db_session, llm_service=mock_llm_service)
        with pytest.raises(ValueError, match="pricing_content"):
            agent._validate_input({'competitor_name': 'Test'})


class TestPositioningAnalyzerAgent:
    """Tests for PositioningAnalyzerAgent."""

    def test_init(self, db_session, mock_llm_service):
        """Test agent initialization."""
        agent = PositioningAnalyzerAgent(db=db_session, llm_service=mock_llm_service)
        assert agent.agent_name == "PositioningAnalyzerAgent"

    def test_get_stage(self, db_session, mock_llm_service):
        """Test stage identification."""
        agent = PositioningAnalyzerAgent(db=db_session, llm_service=mock_llm_service)
        assert agent.get_stage() == "positioning_analysis"

    def test_get_output_schema(self, db_session, mock_llm_service):
        """Test output schema."""
        agent = PositioningAnalyzerAgent(db=db_session, llm_service=mock_llm_service)
        assert agent.get_output_schema() == PositioningAnalysisOutput

    def test_get_system_prompt_contains_key_elements(self, db_session, mock_llm_service):
        """Test system prompt has required elements."""
        agent = PositioningAnalyzerAgent(db=db_session, llm_service=mock_llm_service)
        prompt = agent.get_system_prompt()
        assert "Positioning" in prompt
        assert "target audience" in prompt.lower()
        assert "value proposition" in prompt.lower()

    def test_build_user_prompt(self, db_session, mock_llm_service):
        """Test user prompt building."""
        agent = PositioningAnalyzerAgent(db=db_session, llm_service=mock_llm_service)
        input_data = {
            'competitor_name': 'Acme Inc',
            'competitor_url': 'https://acme.com',
            'homepage_content': 'The #1 project management tool for teams'
        }
        prompt = agent.build_user_prompt(input_data)
        assert 'Acme Inc' in prompt
        assert 'project management' in prompt

    def test_validate_input_missing_content(self, db_session, mock_llm_service):
        """Test validation with missing content."""
        agent = PositioningAnalyzerAgent(db=db_session, llm_service=mock_llm_service)
        with pytest.raises(ValueError, match="homepage_content"):
            agent._validate_input({'competitor_name': 'Test'})


class TestChangesTrackerAgent:
    """Tests for ChangesTrackerAgent."""

    def test_init(self, db_session, mock_llm_service):
        """Test agent initialization."""
        agent = ChangesTrackerAgent(db=db_session, llm_service=mock_llm_service)
        assert agent.agent_name == "ChangesTrackerAgent"

    def test_get_stage(self, db_session, mock_llm_service):
        """Test stage identification."""
        agent = ChangesTrackerAgent(db=db_session, llm_service=mock_llm_service)
        assert agent.get_stage() == "changes_tracking"

    def test_get_output_schema(self, db_session, mock_llm_service):
        """Test output schema."""
        agent = ChangesTrackerAgent(db=db_session, llm_service=mock_llm_service)
        assert agent.get_output_schema() == ChangesTrackingOutput

    def test_get_system_prompt_contains_key_elements(self, db_session, mock_llm_service):
        """Test system prompt has required elements."""
        agent = ChangesTrackerAgent(db=db_session, llm_service=mock_llm_service)
        prompt = agent.get_system_prompt()
        assert "Changes Tracker" in prompt
        assert "feature_launch" in prompt
        assert "release" in prompt.lower()

    def test_build_user_prompt(self, db_session, mock_llm_service):
        """Test user prompt building."""
        agent = ChangesTrackerAgent(db=db_session, llm_service=mock_llm_service)
        input_data = {
            'competitor_name': 'Acme Inc',
            'competitor_url': 'https://acme.com',
            'release_notes_content': 'v2.0: New AI search feature'
        }
        prompt = agent.build_user_prompt(input_data)
        assert 'Acme Inc' in prompt
        assert 'AI search' in prompt

    def test_validate_input_missing_content(self, db_session, mock_llm_service):
        """Test validation with missing content."""
        agent = ChangesTrackerAgent(db=db_session, llm_service=mock_llm_service)
        with pytest.raises(ValueError, match="release_notes_content"):
            agent._validate_input({'competitor_name': 'Test'})


class TestMomentumAnalyzerAgent:
    """Tests for MomentumAnalyzerAgent."""

    def test_init(self, db_session, mock_llm_service):
        """Test agent initialization."""
        agent = MomentumAnalyzerAgent(db=db_session, llm_service=mock_llm_service)
        assert agent.agent_name == "MomentumAnalyzerAgent"

    def test_get_stage(self, db_session, mock_llm_service):
        """Test stage identification."""
        agent = MomentumAnalyzerAgent(db=db_session, llm_service=mock_llm_service)
        assert agent.get_stage() == "momentum_analysis"

    def test_get_output_schema(self, db_session, mock_llm_service):
        """Test output schema."""
        agent = MomentumAnalyzerAgent(db=db_session, llm_service=mock_llm_service)
        assert agent.get_output_schema() == MomentumAnalysisOutput

    def test_get_system_prompt_contains_key_elements(self, db_session, mock_llm_service):
        """Test system prompt has required elements."""
        agent = MomentumAnalyzerAgent(db=db_session, llm_service=mock_llm_service)
        prompt = agent.get_system_prompt()
        assert "Momentum" in prompt
        assert "customer" in prompt.lower()
        assert "partnership" in prompt.lower()

    def test_build_user_prompt(self, db_session, mock_llm_service):
        """Test user prompt building."""
        agent = MomentumAnalyzerAgent(db=db_session, llm_service=mock_llm_service)
        input_data = {
            'competitor_name': 'Acme Inc',
            'competitor_url': 'https://acme.com',
            'customer_content': 'Trusted by Fortune 500 companies'
        }
        prompt = agent.build_user_prompt(input_data)
        assert 'Acme Inc' in prompt
        assert 'Fortune 500' in prompt

    def test_validate_input_no_error_without_content(self, db_session, mock_llm_service):
        """Test validation passes without specific content (more lenient)."""
        agent = MomentumAnalyzerAgent(db=db_session, llm_service=mock_llm_service)
        # Should not raise - momentum can work with limited data
        agent._validate_input({'competitor_name': 'Test'})


class TestFinancialsAnalyzerAgent:
    """Tests for FinancialsAnalyzerAgent."""

    def test_init(self, db_session, mock_llm_service):
        """Test agent initialization."""
        agent = FinancialsAnalyzerAgent(db=db_session, llm_service=mock_llm_service)
        assert agent.agent_name == "FinancialsAnalyzerAgent"

    def test_get_stage(self, db_session, mock_llm_service):
        """Test stage identification."""
        agent = FinancialsAnalyzerAgent(db=db_session, llm_service=mock_llm_service)
        assert agent.get_stage() == "financials_analysis"

    def test_get_output_schema(self, db_session, mock_llm_service):
        """Test output schema."""
        agent = FinancialsAnalyzerAgent(db=db_session, llm_service=mock_llm_service)
        assert agent.get_output_schema() == FinancialsAnalysisOutput

    def test_get_system_prompt_contains_key_elements(self, db_session, mock_llm_service):
        """Test system prompt has required elements."""
        agent = FinancialsAnalyzerAgent(db=db_session, llm_service=mock_llm_service)
        prompt = agent.get_system_prompt()
        assert "Financials" in prompt
        assert "funding" in prompt.lower()
        assert "revenue" in prompt.lower()

    def test_build_user_prompt(self, db_session, mock_llm_service):
        """Test user prompt building."""
        agent = FinancialsAnalyzerAgent(db=db_session, llm_service=mock_llm_service)
        input_data = {
            'competitor_name': 'Acme Inc',
            'competitor_url': 'https://acme.com',
            'crunchbase_content': 'Series B: $30M raised'
        }
        prompt = agent.build_user_prompt(input_data)
        assert 'Acme Inc' in prompt
        assert '$30M' in prompt


class TestOutputSchemas:
    """Tests for Pydantic output schemas."""

    def test_pricing_tier_schema(self):
        """Test PricingTier schema."""
        tier = PricingTier(
            name="Pro",
            price=29.0,
            billing_period="monthly",
            features=["Feature A", "Feature B"],
            limits={"users": 10}
        )
        assert tier.name == "Pro"
        assert tier.price == 29.0

    def test_pricing_analysis_output_schema(self):
        """Test PricingAnalysisOutput schema."""
        output = PricingAnalysisOutput(
            pricing_model="subscription",
            has_free_tier=True,
            has_trial=True,
            trial_days=14,
            confidence=0.85
        )
        assert output.pricing_model == "subscription"
        assert output.has_free_tier is True

    def test_value_proposition_schema(self):
        """Test ValueProposition schema."""
        prop = ValueProposition(
            claim="Save 50% of your time",
            supporting_evidence="Based on customer surveys",
            target_pain_point="Manual data entry"
        )
        assert prop.claim == "Save 50% of your time"

    def test_positioning_output_schema(self):
        """Test PositioningAnalysisOutput schema."""
        output = PositioningAnalysisOutput(
            target_audience="Enterprise IT teams",
            market_segment="enterprise",
            positioning_statement="For enterprise IT, Acme is the tool that saves time",
            confidence=0.8
        )
        assert output.market_segment == "enterprise"

    def test_change_event_schema(self):
        """Test ChangeEvent schema."""
        event = ChangeEvent(
            event_type="feature_launch",
            event_title="AI Search",
            event_description="New AI-powered search",
            impact_level="major"
        )
        assert event.event_type == "feature_launch"
        assert event.impact_level == "major"

    def test_changes_tracking_output_schema(self):
        """Test ChangesTrackingOutput schema."""
        output = ChangesTrackingOutput(
            total_changes=5,
            major_changes=2,
            analysis_period="last 30 days",
            release_velocity="high",
            confidence=0.9
        )
        assert output.total_changes == 5

    def test_customer_win_schema(self):
        """Test CustomerWin schema."""
        win = CustomerWin(
            customer_name="BigCorp",
            industry="Finance",
            company_size="enterprise",
            is_notable=True
        )
        assert win.customer_name == "BigCorp"
        assert win.is_notable is True

    def test_partnership_info_schema(self):
        """Test PartnershipInfo schema."""
        partnership = PartnershipInfo(
            partner_name="Salesforce",
            partnership_type="integration"
        )
        assert partnership.partner_name == "Salesforce"

    def test_market_expansion_schema(self):
        """Test MarketExpansion schema."""
        expansion = MarketExpansion(
            market_type="geographic",
            market_name="EMEA"
        )
        assert expansion.market_type == "geographic"

    def test_momentum_output_schema(self):
        """Test MomentumAnalysisOutput schema."""
        output = MomentumAnalysisOutput(
            momentum_score=0.75,
            momentum_trend="rising",
            analysis_summary="Strong growth signals",
            confidence=0.8
        )
        assert output.momentum_score == 0.75
        assert output.momentum_trend == "rising"

    def test_funding_round_schema(self):
        """Test FundingRound schema."""
        round = FundingRound(
            round_type="series_b",
            amount=30000000,
            investors=["Sequoia", "a16z"]
        )
        assert round.round_type == "series_b"
        assert round.amount == 30000000

    def test_financials_output_schema(self):
        """Test FinancialsAnalysisOutput schema."""
        output = FinancialsAnalysisOutput(
            company_type="private",
            funding_stage="series_b",
            financial_health="strong",
            analysis_summary="Well-funded startup",
            confidence=0.75
        )
        assert output.company_type == "private"
        assert output.financial_health == "strong"


class TestAgentExecution:
    """Tests for agent execution with mocked LLM."""

    def test_pricing_agent_execute(self, db_session, mock_llm_service):
        """Test pricing agent execution."""
        agent = PricingAnalyzerAgent(db=db_session, llm_service=mock_llm_service)

        mock_llm_service.call_agent.return_value = {
            'content': '''{
                "pricing_model": "subscription",
                "has_free_tier": true,
                "has_trial": true,
                "trial_days": 14,
                "pricing_tiers": [],
                "has_enterprise": true,
                "confidence": 0.85
            }''',
            'tokens_used': 300
        }

        result = agent.execute({
            'competitor_name': 'Test Corp',
            'pricing_content': 'Pro plan $29/mo'
        })

        assert result['pricing_model'] == "subscription"
        assert result['has_free_tier'] is True

    def test_positioning_agent_execute(self, db_session, mock_llm_service):
        """Test positioning agent execution."""
        agent = PositioningAnalyzerAgent(db=db_session, llm_service=mock_llm_service)

        mock_llm_service.call_agent.return_value = {
            'content': '''{
                "tagline": "The #1 Tool",
                "value_propositions": [],
                "target_audience": "Enterprise teams",
                "market_segment": "enterprise",
                "key_differentiators": ["Fast", "Secure"],
                "positioning_statement": "For enterprise teams, we are the best",
                "messaging_themes": ["speed", "security"],
                "social_proof": ["customer logos"],
                "competitive_claims": [],
                "source_urls": ["https://test.com"],
                "confidence": 0.8
            }''',
            'tokens_used': 350
        }

        result = agent.execute({
            'competitor_name': 'Test Corp',
            'homepage_content': 'The #1 tool for teams'
        })

        assert result['market_segment'] == "enterprise"
        assert result['tagline'] == "The #1 Tool"

    def test_changes_agent_execute(self, db_session, mock_llm_service):
        """Test changes tracker agent execution."""
        agent = ChangesTrackerAgent(db=db_session, llm_service=mock_llm_service)

        mock_llm_service.call_agent.return_value = {
            'content': '''{
                "changes": [
                    {
                        "event_type": "feature_launch",
                        "event_title": "AI Search",
                        "event_description": "New AI search",
                        "impact_level": "major",
                        "affected_areas": ["Search"],
                        "source_type": "release_notes"
                    }
                ],
                "total_changes": 1,
                "major_changes": 1,
                "analysis_period": "last 30 days",
                "release_velocity": "high",
                "notable_trends": ["AI focus"],
                "strategic_implications": ["Competitive threat"],
                "sources_analyzed": ["https://test.com/changelog"],
                "confidence": 0.9
            }''',
            'tokens_used': 400
        }

        result = agent.execute({
            'competitor_name': 'Test Corp',
            'release_notes_content': 'v2.0 AI Search launched'
        })

        assert result['total_changes'] == 1
        assert len(result['changes']) == 1
        assert result['changes'][0]['event_type'] == "feature_launch"
