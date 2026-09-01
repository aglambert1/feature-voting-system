"""
Self-Assessment Agent — scores our own product against its job map.

Structurally this is a competitor audit whose subject is us. Same job-keyed output, same
rubric, same evidence citations. That symmetry is the point: it lets a comparison view put
our column beside the competitors with no special-casing, and lets our score inherit the
change detection and review machinery already built for competitor reports.

It exists because our score used to be re-derived inside every competitor audit, so the
same job could carry a different "our" score in each report — three audits, three answers
to a question that has one.

The harder problem it only partly addresses: the job map is usually generated from the
product's own description, so scoring the product against that map using that same
description is circular. Independent evidence — support themes, win/loss notes, evidence
records — is what breaks the loop, which is why an assessment records whether it had any.
"""

from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel

from app.agents.base_agent import BaseAgent
from app.models.cost_tracking import OperationType
from app.schemas.competitive_reports import SelfAssessmentOutput


class SelfAssessmentAgent(BaseAgent):
    """Scores our product against each job in its map, grounded in available evidence."""

    def get_stage(self) -> str:
        return "self_assessment"

    def get_operation_type(self) -> OperationType:
        return OperationType.SELF_ASSESSMENT

    def get_output_schema(self) -> Type[BaseModel]:
        return SelfAssessmentOutput

    def get_system_prompt(self) -> str:
        return """You are a Product Strategist assessing how well a product serves the customer jobs in its own job map.

## Framework

Products compete on how well they help customers make progress on specific jobs. Score each
job on how completely it gets done for the customer — not on how the product compares to
anyone else. There are no competitors in this assessment.

## Scoring Principles (1-10 scale)
- 9-10: Fully addresses the job end to end, with no notable gaps in the desired outcomes
- 7-8: Strong coverage; minor gaps in some desired outcomes
- 5-6: Adequate for the core of the job, with notable capabilities missing
- 3-4: Minimal coverage; the customer does substantial work themselves
- 1-2: Barely addresses the job
- 0: Unknown — you have no basis to judge

Use 0 rather than guessing. A fabricated score is worse than an admitted gap, because
everything downstream treats these as facts.

## The circularity problem — read this carefully

The job map you are scoring against was, in most cases, generated from the product
description you are being given. If you score the product using only that description, you
are checking whether a product does the things it says it does — which it always will.
Every score comes out high and the assessment is worthless.

So:
- Where independent evidence exists (support themes, win/loss notes, evidence records,
  customer signals), weight it far above the product's own description. A support theme
  describing users struggling with a job is stronger evidence than marketing copy claiming
  the job is solved.
- Where evidence contradicts the product description, follow the evidence and say so in the
  rationale.
- Where you have nothing but the product description for a job, set `confidence` to "low"
  and say in the rationale that the score rests on the product's own claims. Do not inflate
  the score to match the copy, and do not deflate it to seem rigorous — say what you can
  see and mark it uncertain.

Set `evidence_based` to true only if independent evidence informed at least some
assessments. If the only input was the product description, set it to false. This is not a
quality score; it tells a reader how much weight the whole assessment can carry.

## Being useful

An assessment where everything scores 8-10 is almost always wrong, and it is useless either
way — it tells the reader nothing about where to invest. Jobs a product serves poorly, or
does not serve at all, belong in the map and should be scored honestly. Look specifically
for jobs where the product's coverage is partial, indirect, or requires the customer to work
around it.

## Evidence citation

Cite `evidence_ids` on any assessment an evidence record informed. Features listed under a
job are ours by definition — set `whose` to "ours" and `position` to "advantage" for
capabilities that serve the job well, "gap" where the job is under-served.

## Output

Respond with a valid JSON object matching this structure (and nothing else):

```json
{
  "job_assessments": [
    {
      "job_id": "j1",
      "job_statement": "When [situation], I want to [action], so I can [outcome]",
      "importance": "critical",
      "score": 6,
      "confidence": "high",
      "score_rationale": "What carries the job today and where it falls short",
      "features": [
        {
          "feature_name": "Feature A",
          "description": "What it does functionally",
          "whose": "ours",
          "position": "advantage",
          "evidence_ids": [5]
        }
      ],
      "outcome_coverage": [
        {"desired_outcome": "Minimize time to X", "our_coverage": "partial", "competitor_coverage": "none"}
      ],
      "evidence_ids": [5, 12]
    }
  ],
  "evidence_based": true,
  "assessment_summary": "Two or three sentences on where the product is strong and weak across the map."
}
```

Produce one entry per job in the map, including jobs the product serves poorly or not at
all. `competitor_coverage` in outcome_coverage is unused here — set it to "none"."""

    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        product_name = input_data.get("product_name", "the product")
        product_description = input_data.get("product_description") or "(none provided)"
        job_map = input_data.get("job_map") or []
        evidence = input_data.get("evidence") or []
        support_themes = input_data.get("support_themes") or []
        win_loss_themes = input_data.get("win_loss_themes") or []

        parts = [
            f"# Product: {product_name}",
            "",
            "## Product description",
            "",
            product_description,
            "",
            "## Job map — assess each of these",
            "",
        ]

        for job in job_map:
            parts.append(
                f"- **{job.get('job_id')}** ({job.get('importance', 'medium')}): "
                f"{job.get('statement', '')}"
            )
            for outcome in (job.get("desired_outcomes") or []):
                parts.append(f"    - desired outcome: {outcome}")
        parts.append("")

        has_independent = bool(evidence or support_themes or win_loss_themes)

        if has_independent:
            parts.append("## Independent evidence")
            parts.append("")
            parts.append(
                "This did not come from the product description. Weight it above the "
                "description wherever they disagree."
            )
            parts.append("")

            if evidence:
                parts.append("### Evidence records")
                for item in evidence:
                    parts.append(
                        f"- [id {item.get('id')}] {item.get('title', '')}: "
                        f"{(item.get('content') or '')[:400]}"
                    )
                parts.append("")

            if support_themes:
                parts.append("### Support themes")
                parts.append(
                    "Customers hitting friction. Weight these heavily — a theme is direct "
                    "evidence of a job going badly."
                )
                for theme in support_themes:
                    linked = f" [links to {theme['job_id_key']}]" if theme.get("job_id_key") else ""
                    parts.append(
                        f"- {theme.get('theme_name', '')}{linked} "
                        f"({theme.get('ticket_count', 0)} tickets, "
                        f"urgency {theme.get('urgency', 'medium')}): "
                        f"{theme.get('jtbd_statement') or ''}"
                    )
                parts.append("")

            if win_loss_themes:
                parts.append("### Win/loss themes")
                parts.append(
                    "Why deals were won or lost. A lost-deal theme is the strongest "
                    "available evidence that a job is under-served."
                )
                for theme in win_loss_themes:
                    linked = f" [links to {theme['job_id_key']}]" if theme.get("job_id_key") else ""
                    parts.append(
                        f"- {theme.get('theme_name', '')}{linked} "
                        f"({theme.get('outcome', 'both')}, "
                        f"{theme.get('deal_count', 0)} deals): "
                        f"{theme.get('jtbd_statement') or ''}"
                    )
                parts.append("")
        else:
            parts.extend([
                "## Independent evidence",
                "",
                "**None available.** You have only the product's own description, and the "
                "job map was derived from it — so this assessment is circular by "
                "construction. Score what the description supports, set every confidence "
                "to \"low\", set `evidence_based` to false, and say plainly in each "
                "rationale that the score rests on the product's own claims.",
                "",
            ])

        return "\n".join(parts)
