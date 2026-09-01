"""
Tests for unmapped competitor capabilities.

The job map is generated from our own product description, so it cannot contain jobs we
never addressed — which is exactly where opportunity hides. A competitor capability that
fits no job is evidence the map is incomplete, not evidence the capability is irrelevant.
Previously Stage 2 had nowhere to put such a finding, so it was silently dropped.
"""

import pytest

from app.agents.functional_audit_agent import (
    CompetitorFunctionalAuditAgent,
    generate_markdown_report,
)
from app.schemas.competitive_reports import (
    FunctionalAuditOutput,
    FunctionalAuditStage2Output,
    UnmappedCapability,
)


@pytest.fixture
def agent():
    """Bare instance — the prompt builders are pure, so skip __init__'s db/llm wiring."""
    return CompetitorFunctionalAuditAgent.__new__(CompetitorFunctionalAuditAgent)


def _minimal_output(**overrides):
    payload = {
        "competitor_context": {
            "positioning": "A positioning line",
            "core_differentiation": "A differentiator",
            "target_customer": "Someone",
        },
        "functional_comparison": [],
        "technical_constraints": {},
    }
    payload.update(overrides)
    return FunctionalAuditOutput(**payload)


class TestSchema:
    def test_defaults_to_empty(self):
        assert _minimal_output().unmapped_capabilities == []

    def test_round_trips_through_model_dump(self):
        # The task merges both stages and revalidates through FunctionalAuditOutput
        # before persisting, so the field has to survive that round trip.
        out = _minimal_output(unmapped_capabilities=[
            {
                "capability": "Spec generation from linked insights",
                "why_unmapped": "Closest is j3, which covers triage rather than drafting",
                "suggested_job_statement": "When I have decided what to build, I want a "
                                           "first draft spec, so I can start the "
                                           "conversation with engineering.",
            }
        ])
        dumped = out.model_dump()
        assert dumped["unmapped_capabilities"][0]["capability"] == (
            "Spec generation from linked insights"
        )
        assert FunctionalAuditOutput(**dumped).unmapped_capabilities[0].why_unmapped

    def test_optional_explanation_fields(self):
        # A capability with no rationale is still worth recording — better a bare finding
        # than a dropped one.
        cap = UnmappedCapability(capability="Something they do")
        assert cap.why_unmapped == ""
        assert cap.suggested_job_statement == ""

    def test_present_on_stage_2_output(self):
        # Stage 2 is where job-map fit is judged, so this is where it must be emitted.
        stage_2 = FunctionalAuditStage2Output(unmapped_capabilities=[
            {"capability": "OKR alignment"}
        ])
        assert stage_2.unmapped_capabilities[0].capability == "OKR alignment"

    def test_merged_stage_output_keeps_the_field(self):
        # The task builds the final payload as {**stage_1, **stage_2}; the merged dict
        # must validate with the capability intact.
        stage_1 = {
            "competitor_context": {
                "positioning": "p", "core_differentiation": "d", "target_customer": "t",
            },
            "functional_comparison": [],
            "technical_constraints": {},
        }
        stage_2 = FunctionalAuditStage2Output(
            unmapped_capabilities=[{"capability": "OKR alignment"}]
        ).model_dump()

        merged = FunctionalAuditOutput(**{**stage_1, **stage_2})

        assert len(merged.unmapped_capabilities) == 1


class TestStage2Prompt:
    def test_prompt_asks_for_unmapped_capabilities(self, agent):
        prompt = agent._build_stage2_system_prompt()
        assert "unmapped_capabilities" in prompt

    def test_prompt_forbids_forcing_into_the_nearest_job(self, agent):
        # The failure mode this exists to prevent: a capability crammed into whichever
        # job is closest, which both corrupts that job's assessment and hides the gap.
        prompt = agent._build_stage2_system_prompt()
        assert "Do not force them into" in prompt

    def test_prompt_forbids_dropping_them(self, agent):
        prompt = agent._build_stage2_system_prompt()
        assert "do not drop them" in prompt

    def test_prompt_explains_why_the_map_is_blind(self, agent):
        # Reasoning rather than a bare rule, so the model handles cases the rule missed.
        prompt = agent._build_stage2_system_prompt()
        assert "blind by construction" in prompt

    def test_prompt_guards_against_over_reporting(self, agent):
        # A feature serving an existing job unusually belongs in that job, not here.
        prompt = agent._build_stage2_system_prompt()
        assert "only if no job genuinely covers it" in prompt


class TestMarkdownReport:
    def test_capabilities_appear_in_the_export(self):
        out = _minimal_output(unmapped_capabilities=[
            {
                "capability": "Objective hierarchy",
                "why_unmapped": "No job covers goal alignment",
                "suggested_job_statement": "When planning a quarter, I want...",
            }
        ])
        md = generate_markdown_report("Productboard", out)

        assert "Capabilities Outside the Job Map" in md
        assert "Objective hierarchy" in md
        assert "No job covers goal alignment" in md
        assert "When planning a quarter, I want..." in md

    def test_section_omitted_when_there_are_none(self):
        md = generate_markdown_report("Productboard", _minimal_output())
        assert "Capabilities Outside the Job Map" not in md


class TestNeedSuggestionsFromCapabilities:
    """Unmapped capabilities route into the SAME queue as signal-derived suggestions.

    A second path would mean later sources (interviews, lost deals) each invent their
    own, and nothing could dedupe a need proposed by both a support theme and a
    competitor.
    """

    def _caps(self):
        return [{
            "capability": "Objective hierarchy and OKR alignment",
            "why_unmapped": "No job covers connecting roadmap work to company goals.",
            "suggested_job_statement": "When I plan a quarter, I want to show how the "
                                       "roadmap ladders to our objectives.",
        }]

    def test_files_into_the_need_suggestion_queue(self, db_session, test_product):
        from app.models.pm_review import PMReviewQueue, ReviewQueueType
        from app.queue.helpers import suggest_needs_from_unmapped_capabilities

        filed = suggest_needs_from_unmapped_capabilities(
            db_session, test_product.id, "Productboard", self._caps()
        )

        items = db_session.query(PMReviewQueue).filter(
            PMReviewQueue.product_id == test_product.id,
            PMReviewQueue.queue_type == ReviewQueueType.NEED_SUGGESTION,
        ).all()
        assert filed == 1
        assert len(items) == 1
        # The suggested statement becomes the candidate need, so approving it does not
        # require the PM to write one from scratch.
        assert "ladders to our objectives" in items[0].item_metadata["signal_content"]
        assert items[0].item_metadata["competitor_name"] == "Productboard"

    def test_re_auditing_does_not_regrow_the_queue(self, db_session, test_product):
        # Audits re-run on a schedule and surface the same gaps each time. A queue that
        # regrows every run stops being read.
        from app.queue.helpers import suggest_needs_from_unmapped_capabilities

        suggest_needs_from_unmapped_capabilities(
            db_session, test_product.id, "Productboard", self._caps()
        )
        second = suggest_needs_from_unmapped_capabilities(
            db_session, test_product.id, "Productboard", self._caps()
        )

        assert second == 0

    def test_empty_input_is_a_no_op(self, db_session, test_product):
        from app.queue.helpers import suggest_needs_from_unmapped_capabilities

        assert suggest_needs_from_unmapped_capabilities(
            db_session, test_product.id, "Productboard", None
        ) == 0
        assert suggest_needs_from_unmapped_capabilities(
            db_session, test_product.id, "Productboard", []
        ) == 0

    def test_a_failure_here_never_breaks_the_audit(self, db_session, test_product):
        # The finding is a byproduct of the audit; losing it must not lose the audit.
        from app.queue.helpers import suggest_needs_from_unmapped_capabilities

        assert suggest_needs_from_unmapped_capabilities(
            db_session, test_product.id, "Productboard", [{"not_a_capability": True}]
        ) == 0
