# Competitive Intelligence — JTBD Redesign Plan

**Status: plan, not implemented.** Redesigns competitor reporting around jobs, with features
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

A second, quieter defect: the **gap → idea workflow is dead for JTBD products**. It is driven
by `gaps_deep_dive`, which Stage 2 only reliably populates when there is *no* job map. A
product with a job map gets an empty Gap Analysis section and silently loses the "Create Ideas
for Voting" action. Carrying that workflow to job level is a requirement, not an option.

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
4 competitors audited · oldest audit Aug 12 · 1 stale
Sorted by importance, then by weakest coverage
──────────────────────────────────────────────────────────────────
                             Us   Prodbrd   Canny   Aha!   JPD
──────────────────────────────────────────────────────────────────
j1  Credible competitive      3       4        1      4      2
    view          CRITICAL           GAP      ADV    GAP    ADV
──────────────────────────────────────────────────────────────────
j2  Feedback → underlying     3       5        5      4      3
    need               HIGH         GAP      GAP    GAP    PAR
──────────────────────────────────────────────────────────────────
j4  Prompt notice when a      4       1        1      2      1 ⚠
    competitor ships   HIGH         ADV      ADV    ADV    ADV
──────────────────────────────────────────────────────────────────
j5  Dedup / already           2       4        5      4      3
    shipped          MEDIUM         GAP      GAP    GAP    GAP
──────────────────────────────────────────────────────────────────
 ⚠ audit older than 30 days              click any cell → job detail
```

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
                                       [ Create idea from this gap ]
```

## Work breakdown

### Phase 1 — Facts (backend, no UI)

| # | Task | Notes |
|---|---|---|
| 1 | **Self-assessment capability** — agent + task scoring our product per job | Evidence-gated: draws on support themes, win/loss, evidence records. Marks itself provisional + low confidence when only product description is available. |
| 2 | **Stage 2 audit scores the competitor only** | Removes `our_score` from the audit's job. Coupled to task 1 — must land together. |
| 3 | **Audit emits `unmapped_capabilities`** | Competitor capabilities matching no job. Feeds need suggestions. |
| 4 | **`ProductJob.provenance`** + migration | `product_derived` / `signal_derived` / `competitor_derived` / `pm_authored` |
| 5 | **Remove `best_in_class` / `our_rank` / `total_ranked`** | Agent prompt, `schemas/unified_synthesis.py`, `job_scorecard` docstring |
| 6 | **Aggregation endpoint** — job coverage across tracked competitors | Pure join over existing audits + self-assessment. No LLM. |
| 7 | **Review/override API** — agree, override, and their persistence | Fields already exist on `StoredJobAssessment` from PR #110 |

### Phase 2 — Rendering (frontend)

| # | Task |
|---|---|
| 8 | TypeScript types for `job_assessments` (none exist today) |
| 9 | View 1 — per-competitor job report, replacing feature table + gap analysis |
| 10 | View 2 — all-tracked comparison |
| 11 | View 3 — one job across competitors |
| 12 | Review/override controls + unreviewed-as-neutral styling |
| 13 | Render `changes_from_previous`, distinguishing flips with and without new evidence |
| 14 | Carry the gap → idea workflow to job level |

### Phase 3 — Map quality (small pieces only)

| # | Task |
|---|---|
| 15 | Provenance breakdown on the job map page as a health indicator |
| 16 | "Add to job map" from unmapped capabilities → need-suggestion queue |

## Design consequences worth deciding during implementation

**Position becomes a join, not a stored value.** Today `system_position` is derived at persist
time from two scores in the same assessment. Once our score lives in the self-assessment,
position must be computed by joining audit + self-assessment — at read time, or recomputed when
either side changes.

The useful consequence: *"our position improved because we shipped something"* becomes
expressible, which it isn't today. The awkward one: a competitor report's diff can now flip
because **we** changed, not because they did. Change detection needs to distinguish those, or
it will attribute our own progress to competitor movement.

**Existing reports keep audit-era `our_score`.** After task 2 lands, older
`job_assessments` still carry a score that new ones won't. Not backfilling is the honest
choice — those numbers were really produced — but they need labelling rather than silent
mixing.

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

Also unresolved:

- **Job-map versioning.** A restated job invalidates prior reviews and makes positions
  incomparable. PR #110 detects and flags this; what a consumer should *do* about it is
  undecided.
- **`change_justification`** — the LLM-authored half of flip reconciliation, split out of
  PR #110 as higher-risk.
- **Deprecating `functional_comparison` / `gaps_deep_dive`.** Once views 1-3 ship, Stage 1's
  flat feature list has no UI consumer. Whether it stays as audit input, is exported only, or
  is removed is a follow-on decision.
