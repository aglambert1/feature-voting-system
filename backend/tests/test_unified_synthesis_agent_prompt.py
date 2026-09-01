"""Unit tests for UnifiedSynthesisAgent prompt construction.

The synthesis agent renders product context (including existing core
features) into both system and user prompts. Two behaviors matter for the
"don't surface existing features as opportunities" rule:
1. The product-context block in the user prompt must list the features
   with both name and description so the agent has enough to recognize
   semantic matches.
2. The system prompt must explicitly forbid surfacing existing features.
"""

import pytest

from app.agents.unified_synthesis_agent import UnifiedSynthesisAgent


@pytest.fixture
def agent():
    """Bare instance — bypass __init__ since we only test pure prompt-building methods."""
    inst = UnifiedSynthesisAgent.__new__(UnifiedSynthesisAgent)
    # Required by get_system_prompt (which we test below)
    from app.services.scoring_defaults import DEFAULT_SCORING_WEIGHTS
    inst.scoring_weights = DEFAULT_SCORING_WEIGHTS
    return inst


class TestFormatProductContextRichFeatures:
    """Synthesis task now passes core_features as [{feature_name, feature_description}]
    so the agent can recognize semantic matches against existing features."""

    def test_renders_rich_feature_dicts_with_descriptions(self, agent):
        ctx = {
            "product_name": "Concur",
            "core_features": [
                {"feature_name": "Receipt Capture", "feature_description": "OCR-based receipt scanning"},
                {"feature_name": "Policy Enforcement", "feature_description": "Block out-of-policy expenses"},
            ],
        }
        rendered = agent._format_product_context(ctx)
        assert "Receipt Capture: OCR-based receipt scanning" in rendered
        assert "Policy Enforcement: Block out-of-policy expenses" in rendered

    def test_renders_rich_feature_without_description(self, agent):
        ctx = {
            "product_name": "X",
            "core_features": [
                {"feature_name": "Approvals", "feature_description": ""},
            ],
        }
        rendered = agent._format_product_context(ctx)
        assert "- Approvals" in rendered
        # No trailing colon when no description
        assert "Approvals:" not in rendered

    def test_back_compat_with_bare_string_feature_list(self, agent):
        """Older callers may still pass plain strings; rendering should still work."""
        ctx = {
            "product_name": "X",
            "core_features": ["Receipt Capture", "Approvals"],
        }
        rendered = agent._format_product_context(ctx)
        assert "- Receipt Capture" in rendered
        assert "- Approvals" in rendered

    def test_features_block_labels_them_as_existing_with_anti_duplication_hint(self, agent):
        ctx = {"product_name": "X", "core_features": [{"feature_name": "F", "feature_description": ""}]}
        rendered = agent._format_product_context(ctx)
        # The header must explicitly remind the agent these are existing
        assert "Existing Core Features" in rendered
        assert "DO NOT surface" in rendered

    def test_handles_missing_core_features(self, agent):
        ctx = {"product_name": "X"}
        rendered = agent._format_product_context(ctx)
        assert "Existing Core Features" not in rendered

    def test_truncates_to_20_features(self, agent):
        ctx = {
            "product_name": "X",
            "core_features": [{"feature_name": f"F{i}", "feature_description": ""} for i in range(30)],
        }
        rendered = agent._format_product_context(ctx)
        # F0..F19 should appear; F20 onwards should not
        assert "- F19" in rendered
        assert "- F20" not in rendered

    def test_handles_empty_product_context(self, agent):
        rendered = agent._format_product_context({})
        assert rendered == "No product context provided."


class TestSystemPromptAntiDuplicationRule:
    """The 'don't surface existing features' rule must be in the system prompt."""

    def test_system_prompt_includes_existing_features_rule(self, agent):
        prompt = agent.get_system_prompt()
        assert "DO NOT surface existing product features as opportunities" in prompt

    def test_system_prompt_allows_extension_opportunities(self, agent):
        """The rule must permit extensions (e.g., 'scheduled CSV import' when
        'CSV import' exists) — but require explicit naming of what they extend."""
        prompt = agent.get_system_prompt()
        assert "EXTENSION" in prompt or "extension" in prompt
        assert "explicitly name" in prompt or "must explicitly" in prompt


class TestSystemPromptScoresAbsolutely:
    """Synthesis scores how well a job is served, not where we place in a field.

    Ranking left synthesis for two reasons. It is incoherent under a configurable-source
    run — a synthesis without the competitive source would rank against nothing — and it
    narrows the JTBD frame to discovered vendors, when the customer's real alternative is
    often a spreadsheet or doing nothing. Deleting the fields is not enough on its own:
    if the prompt still instructs the model to rank, it keeps reasoning by rank and simply
    stops reporting it.
    """

    def test_prompt_does_not_ask_for_a_rank_or_a_winner(self, agent):
        prompt = agent.get_system_prompt()
        assert "best_in_class" not in prompt
        assert "our_rank" not in prompt
        assert "total_ranked" not in prompt

    def test_prompt_frames_our_score_against_the_job(self, agent):
        prompt = agent.get_system_prompt()
        assert "against the job itself" in prompt

    def test_prompt_says_an_important_job_served_poorly_is_a_problem_regardless(self, agent):
        # The substantive half of the change: importance and coverage drive the call,
        # competitive position is evidence for it.
        prompt = agent.get_system_prompt()
        assert "whether or not anyone else serves it well" in prompt

    def test_prompt_keeps_competitor_scores_as_context(self, agent):
        # Competitive signal is still an input to synthesis — it just stops being a
        # leaderboard.
        prompt = agent.get_system_prompt()
        assert "competitor_scores" in prompt
        assert "supporting context" in prompt
