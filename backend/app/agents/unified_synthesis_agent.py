"""
Unified Synthesis Agent.

This agent replaces both the LandscapeOpportunitySynthesizerAgent and the
OpportunitySynthesisAgent with a single Jobs-to-be-Done (JTBD) centric step
that can fuse up to four signal sources into a coherent strategy view:

1. Competitive intelligence (job_assessments from competitor functional reports)
2. Customer feedback (voted ideas with JTBD statements)
3. Internal feedback (win/loss + support themes with JTBD statements)
4. Evidence/research (non-competitive factbase evidence with JTBD statements)

The agent operates in several modes:
- Full synthesis: all four sources present
- Competitive + voice: competitive plus one or more of customer/internal/evidence
- Voice only: no competitors — produces self-assessment scores and source-matched
  opportunities with an empty feature_cluster_matrix
- No job map: produces source-matched opportunities without job_scorecard

Scoring uses the scoring_weights dict (merged with DEFAULT_SCORING_WEIGHTS by
the caller) plus a job-importance multiplier.
"""

from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel

from app.agents.base_agent import BaseAgent
from app.schemas.unified_synthesis import UnifiedSynthesisOutput
from app.services.scoring_defaults import (
    DEFAULT_SCORING_WEIGHTS,
    VOTE_THRESHOLDS,
    format_scoring_prompt,
)


# Job-importance multiplier applied on top of the base scoring weights.
JOB_IMPORTANCE_MULTIPLIER = {
    "critical": 1.3,
    "high": 1.15,
    "medium": 1.0,
    "low": 0.8,
}


class UnifiedSynthesisAgent(BaseAgent):
    """
    Unified synthesis agent applying Job Theory across all signal sources.

    Usage:
        agent = UnifiedSynthesisAgent(
            db=db,
            llm_service=llm_service,
            scoring_weights=merged_weights,  # optional
        )
        result = agent.execute({
            'product_context': {
                'product_name': 'Acme',
                'product_description': '...',
                'product_category': '...',
                'job_map': {...},                 # optional
                'target_customer_profile': {...}, # optional
            },
            'included_source_types': ['competitive', 'customer', 'internal', 'evidence'],
            'competitor_reports': [               # list of {competitor_name, audit}
                {'competitor_name': 'Beta', 'audit': {...}},
            ],
            'customer_ideas': [...],
            'winloss_themes': [...],
            'support_themes': [...],
            'evidence_items': [...],
        })
    """

    def __init__(
        self,
        scoring_weights: Optional[dict] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.scoring_weights = scoring_weights or DEFAULT_SCORING_WEIGHTS

    # ------------------------------------------------------------------
    # BaseAgent plumbing
    # ------------------------------------------------------------------

    def get_stage(self) -> str:
        return "unified_synthesis"

    def get_output_schema(self) -> Type[BaseModel]:
        return UnifiedSynthesisOutput

    def get_system_prompt(self) -> str:
        """Build the system prompt with dynamic scoring guidance."""
        scoring_section = format_scoring_prompt(self.scoring_weights)

        return (
            """You are a Principal Product Strategist applying Jobs-to-be-Done (JTBD) theory to synthesize signals across multiple sources into a single, actionable strategy view.

You will receive one or more of the following input sources:
1. **Competitive intelligence** — per-competitor functional reports that score our product and the competitor against each job in the product's job map (job_assessments).
2. **Customer feedback** — ideas submitted and voted on by customers, each with an optional job_id_key and JTBD statement.
3. **Internal feedback** — win/loss themes (especially losses) and support themes, each with confidence levels, JTBD statements, and optional job_id_key.
4. **Evidence/research** — curated factbase evidence items (customer interviews, market signals, research notes), each with an optional job_id_key and JTBD statement.

Only the sources listed in `included_source_types` are in scope — ignore any section that is not included.

## Your Objective

Produce one unified output that covers:

1. **Job scorecard** — for each job in the job map:
   - Aggregate scores for us and each competitor (1-10) based on their job_assessments.
   - Rank all products (us + competitors) by their job score.
   - Set `best_in_class` to the highest scorer (use 'us' if we lead).
   - Recommend an investment level:
     * `invest_heavily` when we lag on a critical or high-importance job
     * `invest` when we lag on a medium-importance job, or when multiple voice sources corroborate customer demand
     * `defend` when we lead a critical/high job (protect the moat)
     * `maintain` when we are at parity and the job is not differentiating
     * `deprioritize` when the job is low-importance and we are not lagging
   - Include evidence_ids from competitor reports and/or evidence items that informed the call.

   If a job map is NOT provided, return an empty job_scorecard.

   If NO competitors are included (self-assessment mode), leave `competitor_scores` as an empty dict and infer `our_score` from the voice sources (customer/internal/evidence). Still populate investment_recommendation based on voice-only signal strength.

2. **Feature cluster matrix** — group features under their parent job. For each feature:
   - `prevalence`: Table Stakes (80%+ of competitors have it), Common (50-79%), Emerging (25-49%), Frontier (<25%).
   - `our_status`: Have / Gap / Partial.
   - List of competitors with the feature.

   If there are no competitors in scope, the feature_cluster_matrix may be empty.

3. **Unified opportunities** — when the same underlying capability appears in multiple sources, merge the signals into a single opportunity:
   - `source_count` = number of distinct sources contributing (1-4).
   - `sources` = any of 'competitive', 'customer', 'internal', 'evidence_research'.
   - Include source-specific evidence blobs (competitive_evidence, customer_evidence, internal_evidence, evidence_signals) — set to null when that source did not contribute.
   - `job_id_key` when the opportunity maps to a job.
   - `job_satisfaction_delta` — projected improvement (points on the 1-10 scale) to our_score on the linked job if this opportunity ships.
   - `investment_tier` — mirror the job scorecard recommendation when linked to a job.
   - `feature_keywords` — short keywords useful for semantic matching.
   - `jtbd_statement` — unified JTBD: "When [situation], I want to [motivation], so I can [outcome]".

   If a job map is NOT provided, still produce source-matched opportunities but leave job_id_key, job_satisfaction_delta, and investment_tier empty.

4. **High-impact items** — the top gaps to close and top advantages to defend:
   - `type` = "gap" or "advantage".
   - `rank` 1-10 (1 highest priority).
   - Include market_gravity explaining why it matters.

5. **Innovation whitespace** — a persistent unsolved problem across the landscape, if one is evident.

6. **Analysis summary** — 2-3 sentence narrative.

## Semantic Matching

Use SEMANTIC matching, not exact string matching, when fusing signals across sources:
- "Time Tracking" ≈ "Timesheet" ≈ "Billable Hours"
- "API" ≈ "Integration" ≈ "REST API" ≈ "Developer Tools"
- "Export" ≈ "PDF Export" ≈ "Data Export"

Use the job_id_key on ideas/themes/evidence as the strongest matching signal. Fall back to JTBD statement similarity and feature keywords when job_id_key is missing. Match based on the underlying CAPABILITY, not specific wording.

"""
            + scoring_section
            + """

## Job-Importance Multiplier

After computing the base priority_score from the factors above, multiply by the importance multiplier of the linked job:
- critical = 1.3
- high = 1.15
- medium = 1.0
- low = 0.8

Cap the result at 100. If the opportunity has no job_id_key, do not apply the multiplier.

## Internal Feedback Confidence

Internal themes may arrive with confidence levels:
- **High confidence**: theme appears in BOTH structured data (CRM reasons) AND activity analysis (call notes, emails). Strongest internal signal — add the confidence_bonus.
- **Medium confidence**: theme appears in only one internal source.

## Recommended Actions on Opportunities

- `high_priority` — multi-source match OR single source with very strong signal on a critical/high job.
- `investigate` — strong single signal that needs validation.
- `monitor` — worth tracking but not immediately actionable.
- `quick_win` — low effort, moderate signal (e.g., customer votes but no competitive pressure).

## Output Format

You MUST respond with ONLY a valid JSON object matching this exact structure:

```json
{
  "job_scorecard": [
    {
      "job_id": "j1",
      "job_statement": "When onboarding a new supplier, ...",
      "importance": "high",
      "our_score": 5,
      "competitor_scores": {"Competitor A": 8, "Competitor B": 7},
      "best_in_class": "Competitor A",
      "our_rank": 3,
      "total_ranked": 3,
      "investment_recommendation": "invest_heavily",
      "rationale": "We lag the market leader by 3 points on a high-importance job.",
      "evidence_ids": [12, 18]
    }
  ],
  "feature_cluster_matrix": [
    {
      "job_id": "j1",
      "job_statement": "When onboarding a new supplier, ...",
      "features": [
        {
          "feature_name": "Bulk supplier import",
          "prevalence": "Table Stakes",
          "our_status": "Gap",
          "competitors_with_feature": ["Competitor A", "Competitor B"],
          "notes": null
        }
      ]
    }
  ],
  "opportunities": [
    {
      "opportunity_name": "Bulk supplier import",
      "opportunity_summary": "...",
      "priority_score": 88,
      "source_count": 3,
      "sources": ["competitive", "customer", "internal"],
      "job_id_key": "j1",
      "job_satisfaction_delta": 2.5,
      "investment_tier": "invest_heavily",
      "competitive_evidence": {
        "feature_name": "Bulk supplier import",
        "prevalence": "Table Stakes",
        "competitors": ["Competitor A", "Competitor B"],
        "competitor_count": 2,
        "our_status": "Gap",
        "priority_score": 80
      },
      "customer_evidence": {
        "idea_id": 42,
        "idea_title": "CSV import for suppliers",
        "vote_count": 85,
        "status": "under_review"
      },
      "internal_evidence": {
        "winloss": {
          "theme_id": 5,
          "theme_name": "Bulk onboarding gap",
          "outcome": "lost",
          "deal_count": 4,
          "total_value": 180000,
          "competitor_correlation": "Competitor A"
        },
        "support": null
      },
      "evidence_signals": null,
      "recommended_action": "high_priority",
      "feature_keywords": ["bulk import", "csv", "supplier onboarding"],
      "jtbd_statement": "When onboarding a batch of new suppliers, I want to import them in bulk, so I can go live in days instead of weeks."
    }
  ],
  "high_impact_items": [
    {
      "type": "gap",
      "job_id": "j1",
      "rank": 1,
      "title": "Bulk supplier import",
      "description": "Competitors allow CSV-based bulk onboarding; we require per-supplier entry.",
      "market_gravity": "Table-stakes on a high-importance job, cited in 4 lost deals.",
      "competitors": ["Competitor A", "Competitor B"]
    }
  ],
  "innovation_whitespace": "No competitor surfaces AI-assisted supplier risk scoring during onboarding.",
  "analysis_summary": "..."
}
```

## Important Rules

1. DO NOT create duplicate opportunities — consolidate semantically similar signals.
2. Set evidence blobs to null for sources that did not contribute to a given opportunity.
3. Sort opportunities by priority_score descending.
4. Limit to the top 15 opportunities.
5. Only output valid JSON — no explanatory text outside the JSON object."""
        )

    # ------------------------------------------------------------------
    # User prompt construction
    # ------------------------------------------------------------------

    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        """Build the user prompt from all configured sources."""
        product_context = input_data.get("product_context") or {}
        included = [s.lower() for s in input_data.get("included_source_types", [])]

        competitor_reports = input_data.get("competitor_reports") or []
        customer_ideas = input_data.get("customer_ideas") or []
        winloss_themes = input_data.get("winloss_themes") or []
        support_themes = input_data.get("support_themes") or []
        evidence_items = input_data.get("evidence_items") or []

        # Determine effective sources — "included" gates what we render.
        has_competitive = "competitive" in included and bool(competitor_reports)
        has_customer = "customer" in included and bool(customer_ideas)
        has_internal = "internal" in included and bool(winloss_themes or support_themes)
        has_evidence = "evidence" in included and bool(evidence_items)

        product_section = self._format_product_context(product_context)
        job_map_section = self._format_job_map(product_context.get("job_map"))

        competitive_section = (
            self._format_competitor_reports(competitor_reports)
            if has_competitive
            else "Not in scope for this synthesis."
        )
        customer_section = (
            self._format_ideas(customer_ideas)
            if has_customer
            else "Not in scope for this synthesis."
        )
        internal_section = (
            self._format_internal(winloss_themes, support_themes)
            if has_internal
            else "Not in scope for this synthesis."
        )
        evidence_section = (
            self._format_evidence(evidence_items)
            if has_evidence
            else "Not in scope for this synthesis."
        )

        # Mode hint for the model
        mode_parts = []
        if has_competitive:
            mode_parts.append(f"{len(competitor_reports)} competitor(s)")
        if has_customer:
            mode_parts.append(f"{len(customer_ideas)} customer idea(s)")
        if has_internal:
            mode_parts.append(
                f"{len(winloss_themes)} win/loss theme(s), {len(support_themes)} support theme(s)"
            )
        if has_evidence:
            mode_parts.append(f"{len(evidence_items)} evidence item(s)")
        scope_summary = ", ".join(mode_parts) if mode_parts else "no signal sources"

        has_job_map = bool(
            product_context.get("job_map")
            and (
                product_context["job_map"].get("jobs")
                or product_context["job_map"].get("functional_jobs")
                or product_context["job_map"].get("emotional_jobs")
                or product_context["job_map"].get("social_jobs")
            )
        )

        job_map_note = (
            "A job map is available — you MUST produce a job_scorecard entry per job "
            "and organize the feature_cluster_matrix by job."
            if has_job_map
            else "No job map is available — leave job_scorecard empty and omit job_id_key "
            "from opportunities. Still produce source-matched opportunities."
        )

        self_assessment_note = (
            "Self-assessment mode — no competitors in scope. Leave competitor_scores "
            "empty and infer our_score from the voice sources. feature_cluster_matrix "
            "may be empty."
            if not has_competitive
            else ""
        )

        prompt = f"""# Unified Synthesis Request

## Scope

Included sources: {', '.join(included) if included else 'none'}
Signal volume: {scope_summary}

{job_map_note}
{self_assessment_note}

## Our Product
{product_section}

{job_map_section}

---

## Source 1: Competitive Intelligence
{competitive_section}

---

## Source 2: Customer Feedback (Voted Ideas)
{customer_section}

---

## Source 3: Internal Feedback (Win/Loss + Support)
{internal_section}

---

## Source 4: Evidence / Research
{evidence_section}

---

## Your Task

1. Build the job_scorecard (if a job map exists) — one entry per job, with our score and each competitor's score, a rank, a best_in_class label, and an investment recommendation.
2. Build the feature_cluster_matrix grouped by job (if competitors and a job map are in scope).
3. Merge semantically equivalent signals into unified opportunities. Use job_id_key first, then JTBD similarity, then feature keywords.
4. Score each opportunity per the scoring guidelines (include the job-importance multiplier where applicable, cap at 100).
5. Rank the top high-impact gaps and advantages.
6. Identify the innovation whitespace (if any) and write a 2-3 sentence analysis_summary.

Respond with ONLY a valid JSON object matching the schema in the system prompt."""

        return prompt

    # ------------------------------------------------------------------
    # Formatters
    # ------------------------------------------------------------------

    def _format_product_context(self, product_context: Dict[str, Any]) -> str:
        if not product_context:
            return "No product context provided."

        parts = []
        if product_context.get("product_name"):
            parts.append(f"**Name:** {product_context['product_name']}")
        if product_context.get("product_description"):
            parts.append(f"**Description:** {product_context['product_description']}")
        if product_context.get("product_category"):
            parts.append(f"**Category:** {product_context['product_category']}")

        tcp = product_context.get("target_customer_profile")
        if tcp:
            persona = tcp.get("persona_name") or ""
            company = tcp.get("company_characteristics") or ""
            pains = tcp.get("pain_points") or []
            if persona:
                parts.append(f"**Target Persona:** {persona}")
            if company:
                parts.append(f"**Company Fit:** {company}")
            if pains:
                parts.append("**Pain Points:**")
                for pain in pains[:5]:
                    parts.append(f"  - {pain}")

        if product_context.get("core_features"):
            features = product_context["core_features"]
            if isinstance(features, list) and features:
                feat_list = "\n".join(f"  - {f}" for f in features[:15])
                parts.append(f"**Core Features:**\n{feat_list}")

        return "\n".join(parts) if parts else "No product context provided."

    def _format_job_map(self, job_map: Optional[Dict[str, Any]]) -> str:
        """Format the job map section (parallel to FunctionalAuditAgent)."""
        if not job_map:
            return ""

        all_jobs: List[Dict[str, Any]] = []
        if job_map.get("jobs"):
            all_jobs = list(job_map["jobs"])
        else:
            all_jobs.extend(job_map.get("functional_jobs", []) or [])
            all_jobs.extend(job_map.get("emotional_jobs", []) or [])
            all_jobs.extend(job_map.get("social_jobs", []) or [])

        if not all_jobs:
            return ""

        parts = ["## Customer Job Map", ""]
        if job_map.get("main_job"):
            parts.append(f"**Main Job:** {job_map['main_job']}")
            parts.append("")
        if job_map.get("target_customer"):
            parts.append(f"**Target Customer:** {job_map['target_customer']}")
            parts.append("")

        parts.append("### Jobs")
        for job in all_jobs:
            job_id = job.get("job_id", "unknown")
            job_type = job.get("job_type", "")
            statement = job.get("statement", "")
            importance = job.get("importance", "medium")

            type_label = f" ({job_type})" if job_type else ""
            parts.append(
                f"- **{job_id}{type_label}** [importance: {importance}]: {statement}"
            )
            outcomes = job.get("desired_outcomes", []) or []
            for outcome in outcomes:
                if isinstance(outcome, dict):
                    parts.append(f"  - Outcome: {outcome.get('outcome', outcome)}")
                else:
                    parts.append(f"  - Outcome: {outcome}")

        return "\n".join(parts)

    def _format_competitor_reports(self, reports: List[Dict[str, Any]]) -> str:
        """Format competitor functional reports, emphasizing job_assessments."""
        if not reports:
            return "No competitor reports provided."

        blocks: List[str] = []
        for i, report in enumerate(reports, 1):
            name = report.get("competitor_name", f"Competitor {i}")
            audit = report.get("audit", {}) or {}

            lines = [f"### {name}", ""]

            ctx = audit.get("competitor_context") or {}
            if ctx:
                if ctx.get("positioning"):
                    lines.append(f"**Positioning:** {ctx['positioning']}")
                if ctx.get("core_differentiation"):
                    lines.append(f"**Differentiation:** {ctx['core_differentiation']}")
                if ctx.get("target_customer"):
                    lines.append(f"**Target:** {ctx['target_customer']}")
                lines.append("")

            job_assessments = audit.get("job_assessments") or []
            if job_assessments:
                lines.append("**Job Assessments:**")
                for ja in job_assessments:
                    job_id = ja.get("job_id", "?")
                    job_stmt = ja.get("job_statement", "")
                    importance = ja.get("importance", "medium")
                    our_score = ja.get("our_score", 0)
                    comp_score = ja.get("competitor_score", 0)
                    rationale = ja.get("score_rationale", "")
                    lines.append(
                        f"- **{job_id}** [{importance}]: us={our_score}/10, them={comp_score}/10"
                    )
                    if job_stmt:
                        lines.append(f"  Statement: {job_stmt}")
                    if rationale:
                        lines.append(f"  Why: {rationale[:250]}")

                    features = ja.get("features") or []
                    gaps = [f for f in features if f.get("position") == "gap"]
                    advs = [f for f in features if f.get("position") == "advantage"]
                    diffs = [f for f in features if f.get("position") == "differentiator"]
                    if gaps:
                        gap_names = ", ".join(
                            f.get("feature_name", "?") for f in gaps[:6]
                        )
                        lines.append(f"  Gaps: {gap_names}")
                    if advs:
                        adv_names = ", ".join(
                            f.get("feature_name", "?") for f in advs[:6]
                        )
                        lines.append(f"  Advantages: {adv_names}")
                    if diffs:
                        diff_names = ", ".join(
                            f.get("feature_name", "?") for f in diffs[:6]
                        )
                        lines.append(f"  Differentiators: {diff_names}")

                    ev_ids = []
                    for f in features:
                        ev_ids.extend(f.get("evidence_ids", []) or [])
                    if ev_ids:
                        # dedupe while preserving order
                        seen = set()
                        uniq = [e for e in ev_ids if not (e in seen or seen.add(e))]
                        lines.append(f"  Evidence IDs: {uniq[:10]}")
                lines.append("")
            else:
                # Fallback to flat functional_comparison
                comparisons = audit.get("functional_comparison") or []
                if comparisons:
                    by_status: Dict[str, List[Dict[str, Any]]] = {}
                    for c in comparisons:
                        by_status.setdefault(c.get("mapping_status", "Unknown"), []).append(c)
                    lines.append(f"**Feature Summary:** {len(comparisons)} features")
                    for status, items in by_status.items():
                        names = ", ".join(
                            c.get("competitor_feature_name", "?") for c in items[:8]
                        )
                        lines.append(f"- {status} ({len(items)}): {names}")
                    lines.append("")

            evidence = report.get("evidence") or []
            if evidence:
                lines.append(f"**Curated Evidence ({len(evidence)}):**")
                for ev in evidence[:5]:
                    title = ev.get("title", "Untitled")
                    ev_type = ev.get("evidence_type", "")
                    ev_id = ev.get("id", ev.get("evidence_id", ""))
                    lines.append(f"- [ID:{ev_id}] **{title}** ({ev_type})")
                lines.append("")

            blocks.append("\n".join(lines))

        return "\n---\n".join(blocks)

    def _format_ideas(self, ideas: List[Dict[str, Any]]) -> str:
        if not ideas:
            return "No customer ideas available."

        lines = []
        sorted_ideas = sorted(
            ideas, key=lambda x: x.get("vote_count", 0), reverse=True
        )
        for idea in sorted_ideas:
            idea_id = idea.get("id", 0)
            title = idea.get("title", "Unknown")
            votes = idea.get("vote_count", 0)
            status = idea.get("status", "unknown")
            description = idea.get("description", "")
            jtbd = idea.get("jtbd_statement", "")
            job_id_key = idea.get("job_id_key", "")

            lines.append(f"**[ID:{idea_id}] {title}** ({votes} votes)")
            lines.append(f"  Status: {status}")
            if job_id_key:
                lines.append(f"  Job: {job_id_key}")
            if jtbd:
                lines.append(f"  JTBD: {jtbd}")
            if description:
                lines.append(f"  Description: {description[:200]}")
            lines.append("")

        lines.append(
            f"(Vote buckets: {VOTE_THRESHOLDS['high']}+ high, "
            f"{VOTE_THRESHOLDS['medium']}-{VOTE_THRESHOLDS['high'] - 1} medium, "
            f"{VOTE_THRESHOLDS['low']}-{VOTE_THRESHOLDS['medium'] - 1} low)"
        )
        return "\n".join(lines)

    def _format_internal(
        self,
        winloss_themes: List[Dict[str, Any]],
        support_themes: List[Dict[str, Any]],
    ) -> str:
        """Format win/loss + support themes with confidence signals."""
        parts: List[str] = []

        if winloss_themes:
            parts.append("### Win/Loss Themes")
            lost = [t for t in winloss_themes if t.get("outcome") == "lost"]
            won = [t for t in winloss_themes if t.get("outcome") == "won"]

            if lost:
                lost_sorted = sorted(
                    lost,
                    key=lambda x: (
                        0 if x.get("confidence") == "high" else 1,
                        -x.get("deal_count", 0),
                    ),
                )
                parts.append("**Lost Deal Themes:**")
                for theme in lost_sorted:
                    name = theme.get("theme_name", "Unknown")
                    theme_id = theme.get("id", theme.get("theme_id", "?"))
                    dc = theme.get("deal_count", 0)
                    tv = theme.get("total_value", 0) or 0
                    comp = theme.get("competitor_name", theme.get("competitor_correlation"))
                    conf = theme.get("confidence", "medium")
                    sources = theme.get("sources", []) or []
                    jtbd = theme.get("jtbd_statement", "")
                    job_id_key = theme.get("job_id_key", "")
                    keywords = theme.get("feature_keywords", []) or []
                    quotes = theme.get("sample_quotes", []) or []

                    conf_tag = "HIGH CONFIDENCE" if conf == "high" else "medium"
                    src_tag = " + ".join(sources) if sources else "unknown"
                    parts.append(f"- [ID:{theme_id}] **{name}** [{conf_tag}]")
                    parts.append(f"  Sources: {src_tag}; Deals: {dc}; Value: ${tv:,.0f}")
                    if comp:
                        parts.append(f"  Competitor: {comp}")
                    if job_id_key:
                        parts.append(f"  Job: {job_id_key}")
                    if jtbd:
                        parts.append(f"  JTBD: {jtbd}")
                    if keywords:
                        parts.append(f"  Keywords: {', '.join(keywords[:5])}")
                    if quotes:
                        parts.append(f"  Voice: \"{quotes[0][:150]}\"")
                parts.append("")

            if won:
                won_sorted = sorted(
                    won,
                    key=lambda x: (
                        0 if x.get("confidence") == "high" else 1,
                        -x.get("deal_count", 0),
                    ),
                )
                parts.append("**Won Deal Themes (Differentiators):**")
                for theme in won_sorted:
                    name = theme.get("theme_name", "Unknown")
                    theme_id = theme.get("id", theme.get("theme_id", "?"))
                    dc = theme.get("deal_count", 0)
                    tv = theme.get("total_value", 0) or 0
                    conf = theme.get("confidence", "medium")
                    sources = theme.get("sources", []) or []
                    job_id_key = theme.get("job_id_key", "")
                    conf_tag = "HIGH" if conf == "high" else "medium"
                    parts.append(
                        f"- [ID:{theme_id}] **{name}** [{conf_tag}] "
                        f"Deals: {dc}; Value: ${tv:,.0f}; Sources: "
                        f"{' + '.join(sources) if sources else 'unknown'}"
                        + (f"; Job: {job_id_key}" if job_id_key else "")
                    )
                parts.append("")

        if support_themes:
            parts.append("### Support Themes")
            by_category: Dict[str, List[Dict[str, Any]]] = {}
            for theme in support_themes:
                by_category.setdefault(theme.get("category", "other"), []).append(theme)

            for category, cat_themes in by_category.items():
                parts.append(f"**{category.replace('_', ' ').title()}:**")
                sorted_cat = sorted(
                    cat_themes,
                    key=lambda x: (
                        0 if x.get("confidence") == "high" else 1,
                        -x.get("ticket_count", 0),
                    ),
                )
                for theme in sorted_cat:
                    name = theme.get("theme_name", "Unknown")
                    theme_id = theme.get("id", theme.get("theme_id", "?"))
                    tc = theme.get("ticket_count", 0)
                    urgency = theme.get(
                        "urgency_level", theme.get("urgency_indicator", "medium")
                    )
                    conf = theme.get("confidence", "medium")
                    sources = theme.get("sources", []) or []
                    jtbd = theme.get("jtbd_statement", "")
                    job_id_key = theme.get("job_id_key", "")
                    keywords = theme.get("feature_keywords", []) or []
                    quotes = theme.get("sample_quotes", []) or []
                    accounts = theme.get("accounts_affected", []) or []

                    conf_tag = "HIGH CONFIDENCE" if conf == "high" else "medium"
                    src_tag = " + ".join(sources) if sources else "unknown"
                    parts.append(
                        f"- [ID:{theme_id}] **{name}** ({tc} tickets) [{conf_tag}]"
                    )
                    parts.append(f"  Sources: {src_tag}; Urgency: {urgency}")
                    if job_id_key:
                        parts.append(f"  Job: {job_id_key}")
                    if jtbd:
                        parts.append(f"  JTBD: {jtbd}")
                    if keywords:
                        parts.append(f"  Keywords: {', '.join(keywords[:5])}")
                    if quotes:
                        parts.append(f"  Voice: \"{quotes[0][:150]}\"")
                    if accounts:
                        parts.append(f"  Accounts: {', '.join(accounts[:3])}")
                parts.append("")

        return "\n".join(parts) if parts else "No internal themes available."

    def _format_evidence(self, evidence_items: List[Dict[str, Any]]) -> str:
        """Format non-competitive evidence items."""
        if not evidence_items:
            return "No evidence/research available."

        lines = []
        for item in evidence_items:
            ev_id = item.get("id", item.get("evidence_id", 0))
            title = item.get("title", "Untitled")
            ev_type = item.get("evidence_type", "unknown")
            content = item.get("content", "")
            source_url = item.get("source_url", "")
            source_desc = item.get("source_description", "")
            jtbd = item.get("jtbd_statement", "")
            job_id_key = item.get("job_id_key", "")

            lines.append(f"**[ID:{ev_id}] {title}** (type: {ev_type})")
            if source_desc:
                lines.append(f"  Source: {source_desc}")
            if source_url:
                lines.append(f"  URL: {source_url}")
            if job_id_key:
                lines.append(f"  Job: {job_id_key}")
            if jtbd:
                lines.append(f"  JTBD: {jtbd}")
            if content:
                lines.append(f"  Content: {content[:300]}")
            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Validation & recovery
    # ------------------------------------------------------------------

    def _validate_input(self, input_data: Dict[str, Any]) -> None:
        super()._validate_input(input_data)

        included = input_data.get("included_source_types") or []
        if not included:
            raise ValueError(
                "included_source_types must be a non-empty list "
                "(e.g., ['competitive', 'customer', 'internal', 'evidence'])"
            )

        valid_sources = {"competitive", "customer", "internal", "evidence"}
        unknown = {s for s in included if s.lower() not in valid_sources}
        if unknown:
            raise ValueError(
                f"Unknown source type(s) in included_source_types: {sorted(unknown)}. "
                f"Must be a subset of {sorted(valid_sources)}."
            )

        # Ensure at least one listed source actually has data.
        has_any_data = False
        included_lower = {s.lower() for s in included}
        if "competitive" in included_lower and input_data.get("competitor_reports"):
            has_any_data = True
        if "customer" in included_lower and input_data.get("customer_ideas"):
            has_any_data = True
        if "internal" in included_lower and (
            input_data.get("winloss_themes") or input_data.get("support_themes")
        ):
            has_any_data = True
        if "evidence" in included_lower and input_data.get("evidence_items"):
            has_any_data = True

        if not has_any_data:
            raise ValueError(
                "At least one included source must provide data for synthesis."
            )

    def build_concise_user_prompt(
        self, input_data: Dict[str, Any]
    ) -> Optional[str]:
        """Truncation-recovery prompt: ask for a reduced-scope synthesis."""
        product_context = input_data.get("product_context") or {}
        included = input_data.get("included_source_types", [])
        product_name = product_context.get("product_name", "Our product")

        return f"""# Concise Unified Synthesis (Reduced Scope)

**Product:** {product_name}
**Sources in scope:** {', '.join(included) if included else 'none'}

The previous response was too long. Please produce a CONCISE version:
- job_scorecard: Limit to the top 5 jobs by importance.
- feature_cluster_matrix: Limit to the top 3 features per job.
- opportunities: Top 8 maximum, 1-sentence summaries.
- high_impact_items: Top 3 gaps + top 2 advantages.
- Keep all descriptions to one sentence.

Use the same JSON schema from the system prompt. Respond with ONLY valid JSON."""
