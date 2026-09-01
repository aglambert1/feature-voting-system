# Competitive Intelligence — JTBD Redesign Plan

**Status: Phases 1-3 implemented** (2026-09-01). Phase 1 merged as PR #111; Phases 2-3 on
`feat/job-coverage-ui`. All four views built and verified in a browser against seeded data.
The plan is kept as written so the reasoning behind each decision stays legible; where
implementation diverged, the commit messages carry the correction.

**Originally: plan, not implemented.** Redesigns competitor reporting around jobs, with features
demoted to supporting evidence. Companion to
[evidence-interchange-schema.md](evidence-interchange-schema.md).

## The problem

`docs/getting-started/tour.md` claims the Competitor reports tab gives a *"unified view: each
job shows competitor positions (advantage, gap, parity) with supporting evidence."* It does
not. The tab renders `functional_comparison` (a flat feature table) and `gaps_deep_dive` —
both pre-JTBD structures.

The JTBD layer is **fully built server-side and entirely unrendered**:

| Data | Produced by | Rendered? |
|---|---|---|
| `CompetitorFunctionalReport.job_assessments` | per-competitor audit | ❌ no frontend reference at all |
| `SynthesisReport.job_scorecard` | unified synthesis | ❌ typed `unknown[]`, never read |
| `SynthesisReport.feature_cluster_matrix` | unified synthesis | ❌ same |
| `GET /synthesis/by-job/{job_id}` | API | ❌ no caller |

The frontend was never updated after the JTBD redesign. Nothing needs inventing; it needs
rendering — plus the backend corrections below.

A second, quieter defect found alongside it: the **gap → idea workflow is already dead for JTBD
products**. It is driven by `gaps_deep_dive`, which Stage 2 only reliably populates when there
is *no* job map, so a product with a job map gets an empty Gap Analysis section and silently
loses the "Create Ideas for Voting" action.

This plan does **not** carry that workflow to job level — see decision 6. It removes it. The
defect is worth recording because it explains why nobody has reported the loss, and because the
same investigation turned up the endpoints and models that removal will clean up.

## Decisions this plan encodes

1. **Comparison is factual, synthesis is judgment.** Per-competitor and all-tracked comparison
   views derive directly from audits, with no LLM synthesis step. Synthesis remains a single
   place for judgment across *all* evidence (competitive, internal, ideas, evidence) and owns
   investment recommendations.
2. **Comparison is never gated behind synthesis.** A PM who has audited three competitors can
   compare them immediately.
3. **Ranking leaves synthesis.** `best_in_class` / `our_rank` / `total_ranked` are removed.
   They are incoherent under a configurable-source synthesis — a run without the competitive
   source ranks against nothing — and they narrow the JTBD frame to discovered vendors when
   the real alternative is often a spreadsheet or doing nothing. Synthesis scores absolute
   quality-of-fit instead: an important job served poorly is a problem regardless of what
   competitors do.
4. **Our score is assessed once, not per audit.** Today each competitor audit independently
   scores our product, so the same job can carry three different "our" scores. A self-assessment
   step produces one score per job.
5. **The job map models the customer's jobs, not the product's coverage.** Jobs served badly or
   not at all belong in it. A map where everything scores 4-5 is a symptom, not a success.
6. **Ideas are created after synthesis, not from competitive reports.** Creating an idea
   directly from a competitor gap encodes "they have it, so we should build it" — feature-parity
   chasing, which is what the JTBD spine exists to prevent. The insight is not lost by waiting:
   in the JTBD model the gap is already a durable, job-keyed record that synthesis consumes,
   so capture is automatic. What a PM contributes at the comparison layer is judgment about the
   *evidence* (agree / override), not a proposed solution.

## Target flow

```
1. Market discovery          → competitor candidates
2. PM selects tracked        → roster
3. Self-assessment  (NEW)    → our score per job          ─┐
4. Per-competitor audits     → their score per job         ├─ facts
                             → unmapped capabilities (NEW) ─┘
5. Comparison views          → one competitor | all tracked   (aggregation, no LLM)
6. Unified synthesis         → opportunities + investment recs (judgment, all evidence)
```

Steps 3 and 4 are structurally the same operation: **a self-assessment is an audit whose
subject is us.** Same job-keyed shape, same evidence citations, same rubric. That uniformity is
what makes step 5 an N+1 column table with no special-casing, and it lets our score inherit the
change detection, confidence, and review/override machinery already built for competitors.

## Proposed layouts

### View 1 — Per-competitor job report

Replaces the feature comparison table and the gap analysis section entirely.

```
← Back to Competitors                              [ Export .md ]
──────────────────────────────────────────────────────────────────
Productboard                                v3 · audited Aug 25
Feedback + roadmapping; agentic "Spark" layer
Target: product teams, mid-market → enterprise

⚠ 2 changes since v2 — 1 with new evidence, 1 without   [ Review ]
──────────────────────────────────────────────────────────────────
JOB COVERAGE                          Us    Them    Verdict
──────────────────────────────────────────────────────────────────
▸ j1  Credible competitive view        3      4      GAP
      for board prep                                 conf: low
      CRITICAL · product-derived                     unreviewed
──────────────────────────────────────────────────────────────────
▾ j2  Feedback connected to the        3      5      GAP
      underlying need                                conf: high
      HIGH · signal-derived                          ✓ agreed

      Why: auto-linking and topic clustering are native and
      mature; ours is embedding-based but narrower on ingest.

      THEIRS (4)                    OURS (2)
      · Insights auto-linking       · Embedding job linkage
      · Topic detection             · Idea triage
      · Pulse themes
      · Rule-based automations

      OUTCOMES                      Us         Them
      Reduce triage time            partial    full
      Know which requests matter    full       partial

      Evidence: 5 sources · newest Aug 24 · oldest Jun 11

      System says GAP.        [ Agree ]   [ Override ▾ ]
──────────────────────────────────────────────────────────────────
▸ j4  Prompt notice when a             4      1      ADVANTAGE
      competitor ships                               conf: med
      HIGH · competitor-derived                      ✓ agreed
──────────────────────────────────────────────────────────────────

UNMAPPED CAPABILITIES (2)                    [ Add to job map ]
Things Productboard does that fit no job in your map.
  · Spec generation from linked insights
  · Objective hierarchy / OKR alignment
```

Notes on the design:
- **Features appear only inside a job**, split by `whose`. They are evidence for the verdict,
  never the organizing principle, and never aggregated into it.
- **Provenance is on every job row.** A map that is uniformly `product-derived` is visible at a
  glance.
- **Review state is on every row** and unreviewed is styled as neutral, not as a warning. A PM
  may accept every system verdict without looking; that is a valid outcome.
- **Unmapped capabilities** are the audit's job-discovery output, feeding the need-suggestion
  queue.

### View 2 — All tracked competitors

Cheap aggregation over existing audits. No synthesis, no LLM call.

```
Job Coverage · All Tracked Competitors             [ Export .md ]
──────────────────────────────────────────────────────────────────
4 competitors audited · self-assessment Aug 20
Sorted by importance, then by weakest coverage
──────────────────────────────────────────────────────────────────
                             Us   Prodbrd   Canny   Aha!   JPD ⚠
                                  Aug 25   Aug 24  Aug 22  Jul 14
──────────────────────────────────────────────────────────────────
j1  Credible competitive      3       4        1      4      2
    view          CRITICAL           GAP      ADV    GAP    ADV
──────────────────────────────────────────────────────────────────
j2  Feedback → underlying     3       5        5      4      3
    need               HIGH         GAP      GAP    GAP    PAR
──────────────────────────────────────────────────────────────────
j4  Prompt notice when a      4       1        1      2      1
    competitor ships   HIGH         ADV      ADV    ADV    ADV
──────────────────────────────────────────────────────────────────
j5  Dedup / already           2       4        5      4      3
    shipped          MEDIUM         GAP      GAP    GAP    GAP
──────────────────────────────────────────────────────────────────
 ⚠ audit older than 30 days              click any cell → job detail
```

Staleness is a property of the **audit**, so it belongs in the competitor column header with
that audit's date — not on a job row, where it would read as though the job were stale.

`Us` is a single column — the payoff of the self-assessment step. Without it this column would
carry a different number per competitor.

### View 3 — One job across competitors

Reached from a cell in View 2 or a job row in View 1.

```
← Back                                          j2 · HIGH
──────────────────────────────────────────────────────────────────
"When customer feedback and support tickets pile up, I want them
 automatically connected to the underlying customer need, so I can
 tell which requests actually matter strategically."

Provenance: signal-derived — proposed from 3 support themes
──────────────────────────────────────────────────────────────────
US                    3/5    assessed Aug 20 · 6 evidence items
  Embedding-based linkage to jobs; ingest limited to manual
  import and MCP.
──────────────────────────────────────────────────────────────────
PRODUCTBOARD          5/5    GAP      conf high    ✓ agreed
  4 features · 5 sources                            [ expand ]
CANNY                 5/5    GAP      conf high    unreviewed
  6 features · 4 sources                            [ expand ]
AHA!                  4/5    GAP      conf med     ✓ agreed
JIRA PRODUCT DISC.    3/5    PARITY   conf low     ⚠ stale audit
──────────────────────────────────────────────────────────────────
This job is carried into synthesis, where it is weighed against
internal demand and evidence.  Confirmed verdicts weigh more.
```

**No idea creation here** (decision 6). A job-level gap is supported by several features across
several competitors, so "create an idea from this gap" has no well-defined subject — but that
is a symptom. The substantive reason is that acting on a competitor gap in isolation is
parity-chasing. The PM's contribution at this layer is agree/override on the evidence; synthesis
turns judgment into opportunities and ideas.

### View 4 — Map health

Provenance is shown per job in Views 1-3, but the *aggregate* is the number that matters, and
it has no home in those layouts. Its primary home is the Job Map page, where a PM can act on it.

```
Job Map · Concur Invoice               [ Generate from product info ]
──────────────────────────────────────────────────────────────────
MAP HEALTH
  8 jobs · 3 with a non-product source            38%
  ███████░░░░░░░░░░░░░

  product-derived, uncorroborated ··· 5   ⚠ came from the product's
  product-derived + signals ········· 2     own description with no
  competitor-derived ················ 1     independent support, so
  pm-authored ······················· 0     scoring against them is
  2 unvalidated · 1 out of target           partly circular
──────────────────────────────────────────────────────────────────
[ job list follows ]
```

It also appears as a **one-line caveat on the comparison views**, because that is where the
misleading conclusion actually gets drawn — a PM reading "we score 4-5 on everything" needs to
know the map came entirely from their own product copy:

```
⚠ Map is 100% product-derived — coverage scores may be optimistic.
```

Shown only when the ratio is poor; silent otherwise, so it stays a signal rather than furniture.

## Work breakdown

### Phase 1 — Facts (backend, no UI)

| # | Task | Notes |
|---|---|---|
| 1 | **Self-assessment capability** — agent + task scoring our product per job | Evidence-gated: draws on support themes, win/loss, evidence records. Marks itself provisional + low confidence when only product description is available. |
| 2 | **Stage 2 audit scores the competitor only** | Removes `our_score` from the audit's job. Coupled to task 1 — must land together. |
| 3 | **Audit emits `unmapped_capabilities`** | Competitor capabilities matching no job. Feeds need suggestions. |
| 4 | **`ProductJob` map fields** + migration | Entry `provenance` (with source ref); `validation_state`; `serve_intent`; `statement_updated_at`. Corroboration is derived, not stored. See below. |
| 5 | **Remove `best_in_class` / `our_rank` / `total_ranked`** | Agent prompt, `schemas/unified_synthesis.py`, `job_scorecard` docstring |
| 6 | **Aggregation endpoint** — job coverage across tracked competitors | Pure join over existing audits + self-assessment. No LLM. |
| 7 | **Review/override API** — agree, override, and their persistence | Fields already exist on `StoredJobAssessment` from PR #110 |
| 8 | **Deprecate idea creation from competitive reports** | Per decision 6. Removes `POST /competitors/{id}/features/create-ideas`, `POST /competitors/{id}/gaps/create-ideas`, `services/idea_generation_service.py`, the `CompetitorGeneratedIdea` model + its relationships, and the frontend call. Verify no other callers first. |

#### Forward-compatibility for future job-map work

Improving job-map creation is a separate investment (see future work), but four cheap decisions
here determine whether it is easy or expensive later:

- **Entry provenance is stored; corroboration is derived.** These answer different questions
  and only the first needs a field.

  *Entry* — how the job got into the map (`product_derived` / `signal_derived` /
  `competitor_derived` / `pm_authored`), one event with a source reference so the originating
  interview, ticket, or competitor capability can be traced. This is what measures
  **circularity**, and it cannot be computed from linkage, which doesn't know where a job
  came from.

  *Corroboration* — the sources that establish the job is real. Already derivable: `Evidence`,
  `Idea`, `WinLossTheme`, `SupportTheme` and `SynthesizedOpportunity` all carry `job_id_key`,
  so every signal linked to a job is evidence for it. A query, not a stored list, which means
  it self-updates as signals arrive with no write path to maintain.

  Corroboration establishes a job **is real**, not that it is **described correctly**. Twelve
  support themes linking to a job say the job exists; they say nothing about whether the
  statement is worded right. That is what the optional validation pass addresses.
- **A serve-intent marker** distinguishing "not in our market model" from "in the model,
  deliberately out of our scope". This is behavioural, not cosmetic: the plan adds
  competitor-derived job suggestions precisely to de-circularize the map, but a job the PM
  doesn't intend to serve shows as a glaring gap and drags down every coverage view — so PMs
  will reject exactly the non-circular suggestions to keep their scores clean, defeating the
  mechanism. `ProductJob.status` (active/retired) does not express this.

  Binary for now (`in_target` / `out_of_target`). The natural expansion is per-segment — a job
  in target for enterprise and out for SMB — and `CIProduct.target_customer_profile` already
  exists as its home. Naming should not preclude that, but modelling segments now is exactly
  the friction the map-creation work has to avoid.
- **`statement_updated_at`** on `ProductJob`. `updated_at` moves on any field change and so
  cannot answer "when did this job's meaning last change" — the question that governs review
  invalidation and position comparability.
- **Unmapped capabilities route through the existing need-suggestion mechanism.** This plan
  adds a second job-proposer; if it builds its own path, later sources (interviews, lost deals)
  each will too, and nothing can dedupe a job proposed by both a support theme and a competitor.

Deliberately deferred: a first-class `ProposedJob` entity with cross-source dedupe by
embedding. Suggestions currently live as metadata on `PMReviewQueue`, which is fine for two
proposers and strains at four. Revisit when a third source lands.

#### Why provenance is set-valued

A job can arrive from several sources, and the overlap is the most informative case: one that
originated in product copy *but was independently corroborated by three support themes* is far
less circular than one that wasn't. A single value discards exactly the signal worth having.

So the health metric is **"% of jobs with at least one non-product source"**, not
"% product-derived".

**Editing is a separate axis from origin.** A PM rewriting a statement should not erase where
the job came from — both facts matter. Validation state (`unvalidated` / `validated` / `edited`)
is therefore its own field, and it is where the optional PM review process (future work) will
live. Note that editing a statement already carries consequences from PR #110: it invalidates
prior reviews on that job and makes its positions incomparable across versions.

### Phase 2 — Rendering (frontend)

| # | Task |
|---|---|
| 9 | TypeScript types for `job_assessments` (none exist today) |
| 10 | View 1 — per-competitor job report, replacing feature table + gap analysis |
| 11 | View 2 — all-tracked comparison, staleness in the competitor column header |
| 12 | View 3 — one job across competitors |
| 13 | Review/override controls + unreviewed-as-neutral styling |
| 14 | Render `changes_from_previous`, distinguishing flips with and without new evidence |
| 15 | Provenance badges on job rows |

### Phase 3 — Map quality (small pieces only)

| # | Task |
|---|---|
| 16 | **Map health panel** on the Job Map page — "% of jobs with a non-product source", provenance breakdown, unvalidated count |
| 17 | Map-health caveat line on comparison views, shown only when the ratio is poor |
| 18 | "Add to job map" from unmapped capabilities → **existing** need-suggestion queue |

## Design consequences worth deciding during implementation

**Position becomes a join, not a stored value.** Today `system_position` is derived at persist
time from two scores in the same assessment. Once our score lives in the self-assessment,
position must be computed by joining audit + self-assessment — at read time, or recomputed when
either side changes.

The useful consequence: *"our position improved because we shipped something"* becomes
expressible, which it isn't today. The awkward one: a competitor report's diff can now flip
because **we** changed, not because they did. Change detection needs to distinguish those, or
it will attribute our own progress to competitor movement.

**Existing audits do not need to survive.** Usage on feature-iq.app is still minimal, so
pre-change `job_assessments` carrying an audit-era `our_score` can simply be discarded or left
to be overwritten by the next audit. No backfill, no labelling of mixed-era scores, no
compatibility shim. Migrations only — avoid anything requiring a database reset.

**The rubric's top band is comparative.** "Best-in-class" cannot be judged without reference to
a class, so a self-assessment against that anchor isn't fully independent. The anchors need
rewording toward absolute terms for the self-assessment path.

## Unresolved — future work

**Job mapping is a product problem, not a task.** The map is generated from product
information, so scoring our product against it is circular: the jobs were derived from what the
product already does, which makes high scores near-tautological and renders unserved jobs
invisible — precisely where opportunity lives. Nothing in this plan fixes that; the plan only
makes it *visible* (provenance) and adds two passive de-circularizing sources (unmapped
competitor capabilities, existing need suggestions from signals).

Directions considered, none scoped:

- **Lost deals / churn reasons** — jobs customers hired someone else for. The strongest
  evidence of unserved jobs; an import path already exists.
- **Competitor-derived maps** — extract the union of jobs the *category* serves, then propose
  the ones we don't address.
- **Review-site mining** — G2/Capterra complaints describe unmet jobs in customer language.
- **Negative-space prompting** — instruct the extractor to propose jobs the product does *not*
  serve, flagged as candidates.
- **Guided customer interviews** — the highest-value source, and the one with no Feature-IQ
  equivalent today. An interview about features reproduces the product's frame; an interview
  about the struggling moment, the workaround, and the switch trigger surfaces jobs independent
  of any solution. Requires an interview processor.

The binding constraint on all of these is **PM friction**. A map that demands a research
project up front will not get made. The plan's stance — ship a fast product-derived draft,
label it, and let signals improve it passively — is a deliberate trade, not a solution.

**Optional PM validation pass (follow-on).** A review flow where the PM walks the map job by
job, editing statements or confirming that each belongs. It must be *optional* — a PM who never
runs it should still get a working map, and the UI must not nag. This is where the
`unvalidated` / `validated` / `edited` state earns its keep, and it pairs naturally with the
provenance metric: validating the product-derived jobs is the cheapest way to reduce
circularity without new data sources. Deliberately not scoped here.

More generally, **making job-map creation robust without adding friction is its own investment**
— closer to a product in its own right than a task on this plan.

**Legacy session-model cluster.** Removing idea creation (task 8) took
`CompetitorGeneratedIdea` and `services/idea_generation_service.py` with it, which
unblocked one item on a long-standing legacy-cleanup list. Four models remain —
`CompetitorAnalysisSession`, `SessionCompetitor`, `ProductCompetitorFeature`,
`CompetitorFeature` — still read by `session_service.py`, `adapters/competitor_feature.py`
and `api/products.py`. They are a connected subsystem rather than a prune, and unrelated
to this redesign, so they are deliberately not bundled here: this work already spans eight
tasks, and mixing in a subsystem retirement would make it hard to review and hard to
revert. The real blocker is a decision about whether those flows are being deprecated at
all, not the code.

Also unresolved:

- **Job-map versioning.** A restated job invalidates prior reviews and makes positions
  incomparable. PR #110 detects and flags this; what a consumer should *do* about it is
  undecided.
- **`change_justification`** — the LLM-authored half of flip reconciliation, split out of
  PR #110 as higher-risk.
- **Deprecating `functional_comparison` / `gaps_deep_dive`.** Once views 1-3 ship, Stage 1's
  flat feature list has no UI consumer. Whether it stays as audit input, is exported only, or
  is removed is a follow-on decision.
