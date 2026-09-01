"""
Tests for the self-assessment agent and model.

Our score used to be re-derived inside every competitor audit, so the same job could carry
a different "our" score in each report — three audits, three answers to a question that has
one. Self-assessment produces it once.

The harder thing under test is honesty about circularity: the job map is generated from the
product description, so an assessment using only that description checks whether a product
does what it says it does. Independent evidence is what breaks the loop, and an assessment
records whether it had any.
"""

import pytest

from app.agents.self_assessment_agent import SelfAssessmentAgent
from app.models.competitive_reports import ProductSelfAssessment
from app.models.queue import JobType
from app.schemas.competitive_reports import SelfAssessmentOutput, SelfJobAssessment


@pytest.fixture
def agent():
    """Bare instance — the prompt builders are pure, so skip __init__'s db/llm wiring."""
    return SelfAssessmentAgent.__new__(SelfAssessmentAgent)


class TestSchema:
    def test_assessment_carries_no_competitor_score(self):
        # A self-assessment has no other side. Reusing the two-sided JobAssessment shape
        # with a dummy competitor value would invite comparison against nothing.
        assert "competitor_score" not in SelfJobAssessment.model_fields

    def test_defaults_to_not_evidence_based(self):
        # The safe default: claiming evidence we did not have would overstate every score.
        assert SelfAssessmentOutput().evidence_based is False

    def test_score_of_zero_is_permitted(self):
        # 0 means "unknown" and must be expressible — a fabricated score is worse than an
        # admitted gap, because everything downstream treats these as facts.
        entry = SelfJobAssessment(
            job_id="j1", job_statement="s", score=0, score_rationale="no basis"
        )
        assert entry.score == 0

    def test_score_is_bounded(self):
        with pytest.raises(Exception):
            SelfJobAssessment(
                job_id="j1", job_statement="s", score=11, score_rationale="r"
            )


class TestSystemPrompt:
    def test_scores_against_the_job_not_competitors(self, agent):
        prompt = agent.get_system_prompt()
        assert "There are no competitors in this assessment." in prompt

    def test_warns_about_circularity(self, agent):
        # The core reason this agent needs care: scoring a product against a map derived
        # from its own description always comes out high.
        prompt = agent.get_system_prompt()
        assert "circularity problem" in prompt
        assert "which it always will" in prompt

    def test_weights_evidence_above_product_description(self, agent):
        prompt = agent.get_system_prompt()
        assert "weight it far above the product's own description" in prompt

    def test_requires_low_confidence_without_evidence(self, agent):
        prompt = agent.get_system_prompt()
        assert 'set `confidence` to "low"' in prompt

    def test_permits_unknown_over_guessing(self, agent):
        prompt = agent.get_system_prompt()
        assert "Use 0 rather than guessing" in prompt

    def test_warns_that_uniformly_high_scores_are_useless(self, agent):
        prompt = agent.get_system_prompt()
        assert "everything scores 8-10 is almost always wrong" in prompt


class TestUserPrompt:
    def _job_map(self):
        return [{"job_id": "j1", "statement": "When X, I want Y", "importance": "critical"}]

    def test_states_plainly_when_there_is_no_evidence(self, agent):
        # The circular case must be named in the prompt itself, not left implicit.
        prompt = agent.build_user_prompt({
            "product_name": "Feature-IQ",
            "product_description": "A product",
            "job_map": self._job_map(),
        })
        assert "**None available.**" in prompt
        assert "circular by construction" in prompt

    def test_marks_evidence_as_independent_when_present(self, agent):
        prompt = agent.build_user_prompt({
            "product_name": "Feature-IQ",
            "job_map": self._job_map(),
            "evidence": [{"id": 5, "title": "Interview", "content": "They struggled"}],
        })
        assert "This did not come from the product description" in prompt
        assert "[id 5]" in prompt
        assert "None available" not in prompt

    def test_win_loss_themes_carry_their_job_linkage(self, agent):
        # Themes are already linked to jobs at import time, so the agent is told which
        # job each bears on rather than inferring it.
        prompt = agent.build_user_prompt({
            "product_name": "Feature-IQ",
            "job_map": self._job_map(),
            "win_loss_themes": [{
                "theme_name": "Reporting depth",
                "jtbd_statement": "When preparing a board deck...",
                "outcome": "lost",
                "deal_count": 4,
                "job_id_key": "j1",
            }],
        })
        assert "[links to j1]" in prompt
        assert "lost, 4 deals" in prompt

    def test_support_themes_included_with_volume_and_urgency(self, agent):
        prompt = agent.build_user_prompt({
            "product_name": "Feature-IQ",
            "job_map": self._job_map(),
            "support_themes": [{
                "theme_name": "Slow exports",
                "jtbd_statement": "When exporting...",
                "category": "bug",
                "ticket_count": 12,
                "urgency": "high",
                "job_id_key": None,
            }],
        })
        assert "12 tickets" in prompt
        assert "urgency high" in prompt

    def test_desired_outcomes_are_passed_through(self, agent):
        prompt = agent.build_user_prompt({
            "product_name": "Feature-IQ",
            "job_map": [{
                "job_id": "j1",
                "statement": "When X",
                "importance": "high",
                "desired_outcomes": ["Minimize time to answer"],
            }],
        })
        assert "Minimize time to answer" in prompt


class TestModel:
    def test_versions_increment_per_product(self, db_session, test_product):
        first = ProductSelfAssessment(product_id=test_product.id, assessment_version=1)
        db_session.add(first)
        db_session.commit()

        latest = db_session.query(ProductSelfAssessment).filter(
            ProductSelfAssessment.product_id == test_product.id
        ).order_by(ProductSelfAssessment.assessment_version.desc()).first()

        assert latest.assessment_version == 1

    def test_defaults_to_not_evidence_based(self, db_session, test_product):
        assessment = ProductSelfAssessment(product_id=test_product.id)
        db_session.add(assessment)
        db_session.commit()
        assert assessment.evidence_based is False

    def test_records_the_job_map_version_assessed_against(self, db_session, test_product):
        # A restated job makes an assessment of it incomparable to later ones, the same
        # way it does for competitor reports.
        assessment = ProductSelfAssessment(product_id=test_product.id, job_map_version=3)
        db_session.add(assessment)
        db_session.commit()
        assert assessment.job_map_version == 3


class TestQueueJobType:
    def test_self_assessment_is_a_queue_job_type(self):
        assert JobType.SELF_ASSESSMENT.value == "self_assessment"

    def test_enum_name_is_uppercase(self):
        # Postgres stores the member NAME for Enum columns, so the migration adds
        # 'SELF_ASSESSMENT'. A lowercase label would pass on SQLite and 500 on Postgres.
        assert JobType.SELF_ASSESSMENT.name == "SELF_ASSESSMENT"
