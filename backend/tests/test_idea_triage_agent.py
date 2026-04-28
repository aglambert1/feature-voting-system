"""Unit tests for IdeaTriageAgent classification + threshold logic.

Covers two layers of triage status determination:
- classify_recommendation (module-level, pure mapping; agent is the arbiter)
- IdeaTriageAgent.determine_triage_status (auto-execute threshold gate)

These tests use no DB / Celery — they validate the routing logic that
controls whether ideas land in FEATURE_EXISTS, NOT_APPROPRIATE, or
NEEDS_REVIEW after the LLM agent runs.
"""

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
    """Layer 1 — agent is the arbiter. The classifier maps the agent's
    structured output to an IdeaStatus and does not second-guess it.

    Deterministic similarity signals are inputs to the agent's prompt;
    they are NOT consulted by this classifier. If the agent saw a high
    similarity hint and chose to reject without populating
    existing_feature_info, that means the agent disagreed that the idea
    actually duplicates the matched feature — we trust that judgment.
    """

    def test_merge_action_returns_duplicate(self):
        assert classify_recommendation(_result("merge")) == IdeaStatus.DUPLICATE

    def test_approve_action_returns_accepted(self):
        assert classify_recommendation(_result("approve")) == IdeaStatus.ACCEPTED

    def test_review_action_returns_needs_review(self):
        assert classify_recommendation(_result("review")) == IdeaStatus.NEEDS_REVIEW

    def test_reject_with_existing_feature_info_returns_feature_exists(self):
        """Agent affirmatively flagged feature-exists by populating the
        structured field. Classifier honors that."""
        result = _result("reject", existing_feature_info={
            "feature_name": "X", "feature_description": "...",
            "similarity_score": 0.91,
        })
        assert classify_recommendation(result) == IdeaStatus.FEATURE_EXISTS

    def test_reject_without_existing_feature_info_returns_needs_review(self):
        """Agent rejected without populating the feature-exists field — that
        means the agent disagreed that the idea actually duplicates the
        similarity-matched feature. Trust the agent's judgment; route to
        NEEDS_REVIEW for PM review (NOT FEATURE_EXISTS or NOT_APPROPRIATE)."""
        result = _result("reject", reasoning="similar wording but different need")
        assert classify_recommendation(result) == IdeaStatus.NEEDS_REVIEW

    def test_reject_with_off_topic_keyword_returns_not_appropriate(self):
        """Explicit off-topic signal in the agent's reasoning routes to
        NOT_APPROPRIATE. This is the only path to NOT_APPROPRIATE."""
        result = _result("reject", reasoning="this is off-topic for an expense management product")
        assert classify_recommendation(result) == IdeaStatus.NOT_APPROPRIATE

    def test_reject_with_offensive_keyword_returns_not_appropriate(self):
        result = _result("reject", reasoning="contains offensive language")
        assert classify_recommendation(result) == IdeaStatus.NOT_APPROPRIATE

    def test_ambiguous_reject_returns_needs_review_not_not_appropriate(self):
        """NOT_APPROPRIATE must be rare. Ambiguous rejections without explicit
        off-topic/offensive signals default to NEEDS_REVIEW."""
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


class TestDetermineTriageStatus:
    """Layer 2 — auto-execute threshold gate."""

    @pytest.fixture
    def agent(self):
        # determine_triage_status doesn't use self for anything beyond
        # delegation, so a bare instance is fine.
        return IdeaTriageAgent.__new__(IdeaTriageAgent)

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

    def test_feature_exists_above_threshold_returns_feature_exists(self, agent):
        """Agent rejected with existing_feature_info populated and high
        confidence — auto-execute as FEATURE_EXISTS."""
        result = _result("reject", confidence=0.95,
                        existing_feature_info={"feature_name": "X", "feature_description": "...",
                                              "similarity_score": 0.91})
        assert agent.determine_triage_status(
            result, auto_respond_enabled=True, auto_respond_threshold=0.9
        ) == IdeaStatus.FEATURE_EXISTS

    def test_feature_exists_below_threshold_returns_needs_review(self, agent):
        """Agent flagged feature-exists but with insufficient confidence —
        hold for PM review."""
        result = _result("reject", confidence=0.85,
                        existing_feature_info={"feature_name": "X", "feature_description": "...",
                                              "similarity_score": 0.91})
        assert agent.determine_triage_status(
            result, auto_respond_enabled=True, auto_respond_threshold=0.9
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
        return IdeaTriageAgent.__new__(IdeaTriageAgent)

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


class TestExistingFeatureMatchPromptRendering:
    """Verify the strengthened prompt for the deterministic similarity signal —
    the agent must explicitly consider it (agree or disagree)."""

    @pytest.fixture
    def agent(self):
        return IdeaTriageAgent.__new__(IdeaTriageAgent)

    def _input_with_match(self, has_match: bool):
        return {
            "idea": {
                "title": "X", "what_description": "w", "why_description": "y",
                "use_case_description": "u", "source_type": "customer_submission",
            },
            "product_context": {"product_name": "P", "product_category": "C"},
            "similar_ideas": [],
            "competitive_context": {},
            "existing_feature_match": {
                "has_match": has_match,
                "best_match": {
                    "feature_name": "Bulk Import",
                    "feature_description": "Imports records in bulk",
                    "similarity_score": 0.88,
                    "source_url": None,
                } if has_match else None,
                "all_matches": [],
            },
            "related_synthesis_opportunities": [],
        }

    def test_prompt_frames_match_as_input_not_directive(self, agent):
        prompt = agent.build_user_prompt(self._input_with_match(has_match=True))
        assert "POTENTIAL EXISTING FEATURE MATCH" in prompt
        assert "YOUR JUDGMENT decides" in prompt
        assert "If you AGREE" in prompt
        assert "If you DISAGREE" in prompt

    def test_prompt_omits_match_section_when_no_match(self, agent):
        prompt = agent.build_user_prompt(self._input_with_match(has_match=False))
        assert "POTENTIAL EXISTING FEATURE MATCH" not in prompt
