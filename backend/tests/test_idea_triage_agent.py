"""Unit tests for IdeaTriageAgent classification + threshold logic.

Covers two layers of triage status determination:
- classify_recommendation (module-level, pure mapping)
- IdeaTriageAgent.determine_triage_status (auto-execute threshold gate)

These tests use no DB / Celery — they validate the routing logic that
controls whether ideas land in FEATURE_EXISTS, NOT_APPROPRIATE, or
NEEDS_REVIEW after the LLM agent runs.
"""

from unittest.mock import MagicMock

import pytest

from app.agents.idea_triage import IdeaTriageAgent, classify_recommendation
from app.models.idea import IdeaStatus


def _result(action: str, confidence: float = 0.8, reasoning: str = "",
            existing_feature_info=None) -> dict:
    """Build a minimal triage agent result for the classifier."""
    return {
        "recommendation": {
            "action": action,
            "confidence": confidence,
            "reasoning": reasoning,
        },
        "existing_feature_info": existing_feature_info,
    }


class TestClassifyRecommendation:
    """Layer 1 — pure mapping logic, no thresholds."""

    def test_merge_action_returns_duplicate(self):
        assert classify_recommendation(_result("merge")) == IdeaStatus.DUPLICATE

    def test_approve_action_returns_accepted(self):
        assert classify_recommendation(_result("approve")) == IdeaStatus.ACCEPTED

    def test_review_action_returns_needs_review(self):
        assert classify_recommendation(_result("review")) == IdeaStatus.NEEDS_REVIEW

    def test_reject_with_existing_feature_info_returns_feature_exists(self):
        result = _result("reject", existing_feature_info={
            "feature_name": "X", "feature_description": "...",
            "similarity_score": 0.91,
        })
        assert classify_recommendation(result) == IdeaStatus.FEATURE_EXISTS

    def test_reject_with_deterministic_match_returns_feature_exists(self):
        """The Bug 2 regression: agent didn't populate existing_feature_info,
        but the deterministic similarity service flagged a 0.85+ match."""
        result = _result("reject", reasoning="seems like a low-quality idea")
        det_match = {
            "has_match": True,
            "best_match": {"feature_name": "Existing X", "similarity_score": 0.88},
        }
        assert classify_recommendation(result, det_match) == IdeaStatus.FEATURE_EXISTS

    def test_reject_with_existing_feature_keyword_returns_feature_exists(self):
        result = _result("reject", reasoning="this functionality already exists in the dashboard")
        assert classify_recommendation(result) == IdeaStatus.FEATURE_EXISTS

    def test_reject_with_duplicate_keyword_returns_duplicate(self):
        result = _result("reject", reasoning="this is a duplicate of idea #42")
        assert classify_recommendation(result) == IdeaStatus.DUPLICATE

    def test_reject_with_off_topic_keyword_returns_not_appropriate(self):
        result = _result("reject", reasoning="this is off-topic for an expense management product")
        assert classify_recommendation(result) == IdeaStatus.NOT_APPROPRIATE

    def test_reject_with_offensive_keyword_returns_not_appropriate(self):
        result = _result("reject", reasoning="contains offensive language")
        assert classify_recommendation(result) == IdeaStatus.NOT_APPROPRIATE

    def test_ambiguous_reject_returns_needs_review_not_not_appropriate(self):
        """NOT_APPROPRIATE must be rare. Ambiguous rejections without explicit
        off-topic/offensive signals default to NEEDS_REVIEW so the PM decides."""
        result = _result("reject", reasoning="this is a low-quality submission")
        assert classify_recommendation(result) == IdeaStatus.NEEDS_REVIEW

    def test_reject_with_no_reasoning_returns_needs_review(self):
        result = _result("reject", reasoning="")
        assert classify_recommendation(result) == IdeaStatus.NEEDS_REVIEW

    def test_unknown_action_returns_needs_review(self):
        result = {"recommendation": {"action": "ponder", "confidence": 0.7}}
        assert classify_recommendation(result) == IdeaStatus.NEEDS_REVIEW

    def test_handles_missing_recommendation_safely(self):
        assert classify_recommendation({}) == IdeaStatus.NEEDS_REVIEW

    def test_deterministic_match_does_not_promote_approve_path(self):
        """The deterministic signal only matters for reject actions —
        an approve action should still produce ACCEPTED."""
        det_match = {"has_match": True, "best_match": {"feature_name": "X", "similarity_score": 0.9}}
        assert classify_recommendation(_result("approve"), det_match) == IdeaStatus.ACCEPTED


class TestDetermineTriageStatus:
    """Layer 2 — auto-execute threshold gate."""

    @pytest.fixture
    def agent(self):
        # determine_triage_status doesn't use self for anything beyond delegation,
        # so a bare instance is fine. We bypass __init__ by constructing with mocks.
        agent = IdeaTriageAgent.__new__(IdeaTriageAgent)
        return agent

    def test_auto_respond_disabled_always_needs_review(self, agent):
        """Off-state: even a confident approval is held for PM review."""
        result = _result("approve", confidence=0.99)
        assert agent.determine_triage_status(
            result, auto_respond_enabled=False
        ) == IdeaStatus.NEEDS_REVIEW

    def test_auto_respond_disabled_with_feature_exists_signal_still_needs_review(self, agent):
        result = _result("reject", confidence=0.95,
                        existing_feature_info={"feature_name": "X", "feature_description": "...",
                                              "similarity_score": 0.95})
        assert agent.determine_triage_status(
            result, auto_respond_enabled=False
        ) == IdeaStatus.NEEDS_REVIEW

    def test_approve_above_threshold_returns_accepted(self, agent):
        result = _result("approve", confidence=0.95)
        assert agent.determine_triage_status(
            result, auto_respond_enabled=True, auto_respond_threshold=0.9
        ) == IdeaStatus.ACCEPTED

    def test_approve_below_threshold_returns_needs_review(self, agent):
        result = _result("approve", confidence=0.85)
        assert agent.determine_triage_status(
            result, auto_respond_enabled=True, auto_respond_threshold=0.9
        ) == IdeaStatus.NEEDS_REVIEW

    def test_merge_unconditional_when_auto_enabled(self, agent):
        """DUPLICATE doesn't gate behind threshold — merge target ID is itself
        a deterministic check."""
        result = _result("merge", confidence=0.55)
        assert agent.determine_triage_status(
            result, auto_respond_enabled=True, auto_respond_threshold=0.9
        ) == IdeaStatus.DUPLICATE

    def test_feature_exists_above_threshold_via_deterministic_signal(self, agent):
        """Bug 2 regression: agent rejected without existing_feature_info, but
        deterministic similarity flagged a match. Above threshold → FEATURE_EXISTS."""
        result = _result("reject", confidence=0.95)
        det_match = {"has_match": True, "best_match": {"feature_name": "X", "similarity_score": 0.9}}
        assert agent.determine_triage_status(
            result, auto_respond_enabled=True, auto_respond_threshold=0.9,
            deterministic_existing_feature_match=det_match,
        ) == IdeaStatus.FEATURE_EXISTS

    def test_feature_exists_below_threshold_returns_needs_review(self, agent):
        result = _result("reject", confidence=0.85)
        det_match = {"has_match": True, "best_match": {"feature_name": "X", "similarity_score": 0.9}}
        assert agent.determine_triage_status(
            result, auto_respond_enabled=True, auto_respond_threshold=0.9,
            deterministic_existing_feature_match=det_match,
        ) == IdeaStatus.NEEDS_REVIEW

    def test_off_topic_reject_above_threshold_returns_not_appropriate(self, agent):
        result = _result("reject", confidence=0.95,
                        reasoning="this is off-topic for a finance product")
        assert agent.determine_triage_status(
            result, auto_respond_enabled=True, auto_respond_threshold=0.9
        ) == IdeaStatus.NOT_APPROPRIATE

    def test_ambiguous_reject_returns_needs_review_even_above_threshold(self, agent):
        """The classifier returns NEEDS_REVIEW for ambiguous rejects, and that
        cannot be promoted by the threshold layer."""
        result = _result("reject", confidence=0.99,
                        reasoning="this is a low-quality submission")
        assert agent.determine_triage_status(
            result, auto_respond_enabled=True, auto_respond_threshold=0.9
        ) == IdeaStatus.NEEDS_REVIEW


class TestBuildUserPromptRelatedOpportunities:
    """Bug 3 — verify the agent prompt renders related synthesis opportunities."""

    @pytest.fixture
    def agent(self):
        agent = IdeaTriageAgent.__new__(IdeaTriageAgent)
        return agent

    def _input(self, related_opps=None):
        return {
            "idea": {
                "title": "Bulk supplier import",
                "what_description": "what",
                "why_description": "why",
                "use_case_description": "use",
                "source_type": "customer_submission",
            },
            "product_context": {
                "product_name": "TestProduct",
                "product_category": "Procurement",
            },
            "similar_ideas": [],
            "competitive_context": {},
            "existing_feature_match": {"has_match": False, "best_match": None, "all_matches": []},
            "related_synthesis_opportunities": related_opps or [],
        }

    def test_prompt_includes_related_opportunity_section(self, agent):
        opps = [{
            "opportunity_id": 7,
            "opportunity_name": "Bulk supplier onboarding",
            "priority_score": 88.0,
            "investment_tier": "invest_heavily",
            "job_id_key": "j1",
            "has_linked_idea": False,
            "sources": ["competitive", "customer"],
        }]
        prompt = agent.build_user_prompt(self._input(related_opps=opps))
        assert "Related Synthesis Opportunities" in prompt
        assert "Bulk supplier onboarding" in prompt
        assert "Opp #7" in prompt
        assert "invest_heavily" in prompt

    def test_prompt_omits_section_when_no_related_opps(self, agent):
        prompt = agent.build_user_prompt(self._input(related_opps=[]))
        assert "Related Synthesis Opportunities" not in prompt

    def test_prompt_marks_already_linked_opportunity(self, agent):
        opps = [{
            "opportunity_id": 9,
            "opportunity_name": "X",
            "priority_score": 50.0,
            "investment_tier": "invest",
            "job_id_key": None,
            "has_linked_idea": True,
            "sources": [],
        }]
        prompt = agent.build_user_prompt(self._input(related_opps=opps))
        assert "already has linked Idea" in prompt
