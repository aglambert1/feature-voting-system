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


# ---------------------------------------------------------------------------
# Phase C — staged execution (stage="full" | "stage1" | "stage2")
# ---------------------------------------------------------------------------

from app.schemas.competitive_reports import (
    FunctionalAuditStage1Output,
    FunctionalAuditStage2Output,
    FunctionalAuditOutput,
)


def test_default_stage_is_full(db_session, mock_llm_service):
    agent = CompetitorFunctionalAuditAgent(db=db_session, llm_service=mock_llm_service)
    assert agent.stage == "full"
    assert agent.get_output_schema() is FunctionalAuditOutput


def test_stage1_agent_uses_stage1_schema(db_session, mock_llm_service):
    agent = CompetitorFunctionalAuditAgent(
        db=db_session, llm_service=mock_llm_service, stage="stage1"
    )
    assert agent.get_output_schema() is FunctionalAuditStage1Output


def test_stage2_agent_uses_stage2_schema(db_session, mock_llm_service):
    agent = CompetitorFunctionalAuditAgent(
        db=db_session, llm_service=mock_llm_service, stage="stage2"
    )
    assert agent.get_output_schema() is FunctionalAuditStage2Output


def test_get_stage_disambiguates_split_stages(db_session, mock_llm_service):
    """AgentExecutionLog.stage must reflect which staged call produced each row,
    so per-stage token usage and latency can be attributed correctly."""
    full = CompetitorFunctionalAuditAgent(db=db_session, llm_service=mock_llm_service)
    stage1 = CompetitorFunctionalAuditAgent(db=db_session, llm_service=mock_llm_service, stage="stage1")
    stage2 = CompetitorFunctionalAuditAgent(db=db_session, llm_service=mock_llm_service, stage="stage2")

    assert full.get_stage() == "functional_audit"
    assert stage1.get_stage() == "functional_audit_stage1"
    assert stage2.get_stage() == "functional_audit_stage2"


def test_stage1_system_prompt_excludes_job_assessments(db_session, mock_llm_service):
    """Stage 1 system prompt must not ask for Stage 2 fields."""
    agent = CompetitorFunctionalAuditAgent(
        db=db_session, llm_service=mock_llm_service, stage="stage1"
    )
    sys_prompt = agent.get_system_prompt()
    assert "STAGE 1" in sys_prompt
    # Stage 1 must explicitly exclude Stage 2 sections
    assert "DO NOT produce job_assessments" in sys_prompt
    # Schema block includes Stage 1 fields
    assert "competitor_context" in sys_prompt
    assert "functional_comparison" in sys_prompt
    assert "technical_constraints" in sys_prompt


def test_stage2_system_prompt_assumes_stage1_context(db_session, mock_llm_service):
    agent = CompetitorFunctionalAuditAgent(
        db=db_session, llm_service=mock_llm_service, stage="stage2"
    )
    sys_prompt = agent.get_system_prompt()
    assert "STAGE 2" in sys_prompt
    # Stage 2 must tell the agent Stage 1 context is provided in the user prompt
    assert "Stage 1" in sys_prompt and "already complete" in sys_prompt
    # Stage 2 should still mention the fields it produces
    assert "job_assessments" in sys_prompt


def test_stage2_user_prompt_embeds_stage_1_output(db_session, mock_llm_service, base_input):
    """Stage 2 must render the provided stage_1_output as conditioning context."""
    agent = CompetitorFunctionalAuditAgent(
        db=db_session, llm_service=mock_llm_service, stage="stage2", web_research_enabled=False
    )
    stage_1 = {
        "competitor_context": {
            "positioning": "The best CRM",
            "core_differentiation": "AI-first",
            "target_customer": "mid-market",
            "key_features": ["A", "B"],
        },
        "functional_comparison": [
            {
                "feature_category": "Core",
                "competitor_feature_name": "Smart Routing",
                "functional_description": "Auto-assigns leads.",
                "mapping_status": "Gap",
                "job_id": None,
            },
        ],
        "technical_constraints": {
            "integrations": ["Slack"],
            "api_capabilities": None,
            "platform_requirements": None,
            "additional_notes": None,
        },
    }
    input_data = {**base_input, "stage_1_output": stage_1}

    prompt = agent.build_user_prompt(input_data)

    assert "## Stage 1 Context" in prompt
    assert "Smart Routing" in prompt  # content from stage_1 surfaced in prompt
    assert "AI-first" in prompt
    assert "STAGE 2" in prompt or "Stage 2 of 2" in prompt


def test_stage1_user_prompt_task_instruction_constrains_output(db_session, mock_llm_service, base_input):
    agent = CompetitorFunctionalAuditAgent(
        db=db_session, llm_service=mock_llm_service, stage="stage1", web_research_enabled=False
    )
    prompt = agent.build_user_prompt(base_input)
    assert "Stage 1 of 2" in prompt
    assert "DO NOT produce job_assessments" in prompt


def test_execute_stage_1_flips_stage_then_restores(db_session, mock_llm_service):
    """execute_stage_1 should temporarily set stage to 'stage1' but restore it
    so the agent can be reused."""
    from unittest.mock import patch

    agent = CompetitorFunctionalAuditAgent(db=db_session, llm_service=mock_llm_service)
    assert agent.stage == "full"

    captured_stage = {}

    def fake_execute(self, input_data, **kwargs):
        captured_stage["during"] = self.stage
        return {"dummy": True}

    with patch.object(CompetitorFunctionalAuditAgent.__mro__[1], "execute", fake_execute):
        agent.execute_stage_1({"competitor_name": "X"})

    assert captured_stage["during"] == "stage1"
    assert agent.stage == "full"  # restored


def test_execute_stage_2_flips_stage_then_restores(db_session, mock_llm_service):
    from unittest.mock import patch

    agent = CompetitorFunctionalAuditAgent(db=db_session, llm_service=mock_llm_service)
    captured_stage = {}

    def fake_execute(self, input_data, **kwargs):
        captured_stage["during"] = self.stage
        return {"dummy": True}

    with patch.object(CompetitorFunctionalAuditAgent.__mro__[1], "execute", fake_execute):
        agent.execute_stage_2({"stage_1_output": {}})

    assert captured_stage["during"] == "stage2"
    assert agent.stage == "full"  # restored


def test_execute_stage_1_restores_stage_on_exception(db_session, mock_llm_service):
    """If stage 1 raises, stage attribute must still be restored (try/finally)."""
    from unittest.mock import patch

    agent = CompetitorFunctionalAuditAgent(db=db_session, llm_service=mock_llm_service, stage="full")

    def fake_execute(self, input_data, **kwargs):
        raise RuntimeError("boom")

    with patch.object(CompetitorFunctionalAuditAgent.__mro__[1], "execute", fake_execute):
        with pytest.raises(RuntimeError):
            agent.execute_stage_1({})

    assert agent.stage == "full"
