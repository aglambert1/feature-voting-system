# Evidence Interchange Schema (draft v0.2)

**Status: draft, not implemented.** The portable contract between evidence-producing skills
and any consumer — a local folder, Feature-IQ, or another tool. Design context in the
strategic record: Feature-IQ is the evidence blackboard; skills are producers; the schema is
what lets them coexist.

v0.2 incorporates findings from the baseline evaluation (2026-08-25, three fresh-context runs
against Productboard ×2 and Canny ×1). See *Why the diff design is what it is* below.

This file is the origin point. If the skills land in their own repo, the schema moves there
and Feature-IQ becomes one of two implementations that conform to it.

## What this schema has to do

It carries three loads at once. Every design rule below traces to one of them.

1. **Blackboard contract** — any producer writes it, any consumer reads it, no producer owns it.
2. **Sync contract** — the skill and Feature-IQ are deliberately separate implementations
   (accepted drift). Prose and analysis depth may diverge; *this schema may not*. A field
   mismatch is a break, not drift.
3. **Diff substrate** — run-over-run change detection has to report real capability change
   without model-variance noise.

This document is **descriptive**. It defines fields and what they mean. Behavioural rules that
consume these fields — when to suppress a change, when to escalate to a human, when to re-run —
belong to the implementation, not here.

## Design rules

- **Neutral naming.** The directory is `product-evidence/`, not `_feature-iq/`. The claim being
  staked is that JTBD is an industry interchange format, not a vendor schema — the folder name
  shouldn't contradict that.
- **Job keys are the coordinate system.** `job_id_key` (`j1`, `je1`, `js1`) is the join key
  everywhere. Producers never compute embeddings; they reference keys from the job map they
  were given.
- **Human-authored files are YAML, machine-authored are JSON.** The job map is PM-edited (YAML,
  comments allowed). Findings are machine-written and script-diffed (JSON, stdlib-only parsing,
  no dependency for a forked skill).
- **Every claim carries a citation, and every source carries a retrieval date.**
- **Low-cardinality fields for anything diffed; prose for everything else.**
- **No embeddings, no DB, no API keys in the file format.** A producer must be able to emit a
  valid file with nothing but a filesystem and web search.

## The shared directory

```
product-evidence/
├── job-map.yaml                  # the coordinate system (human-owned)
├── product.yaml                  # what we are analyzing
└── findings/
    ├── competitive/
    │   ├── <competitor-slug>.json      # latest, overwritten each run
    │   └── history/
    │       └── <competitor-slug>--<ISO8601>.json
    ├── interviews/               # future producers, same envelope
    └── crm/
```

## `job-map.yaml`

```yaml
schema_version: "0.2"
product_ref: "concur-invoice"        # matches product.yaml
updated_at: "2026-08-25"
map_version: 3                       # increment on ANY job add/remove/restatement

jobs:
  - job_id_key: "j1"                 # j*=functional, je*=emotional, js*=social
    job_type: "functional"           # functional | emotional | social
    statement: "When I'm preparing for a planning cycle, I want to produce a credible
                competitive view, so I can answer 'how do we stack up' without a week
                of manual research."
    importance: "critical"           # critical | high | medium | low
    desired_outcomes:
      - "Minimize time to a defensible competitive summary"
      - "Maximize confidence that the summary is current"
    status: "active"                 # active | retired
```

Field names, the `j`/`je`/`js` key convention, and both enums are lifted directly from
`ProductJob` so ingestion is a straight mapping rather than a translation.

`map_version` is the one addition. It exists because job-map versioning is an identified
unsolved problem: when the map changes, previously-linked evidence may be filed against jobs
that no longer mean the same thing. Findings record the `map_version` they were produced
against, so a consumer can at least *detect* the mismatch. Resolving it (re-link? invalidate?
flag?) is deliberately out of scope.

## `findings/competitive/<competitor-slug>.json`

```json
{
  "schema_version": "0.2",
  "finding_type": "competitive_audit",
  "product_ref": "concur-invoice",
  "job_map_version": 3,

  "producer": {
    "name": "auditing-competitors",
    "version": "0.1.0",
    "model": "claude-sonnet-5",
    "run_id": "2026-08-25T14:22:03Z"
  },

  "subject": {
    "competitor_name": "Coupa",
    "competitor_url": "https://coupa.com",
    "competitor_description": "Spend management suite, enterprise segment"
  },

  "observed_at": "2026-08-25T14:22:03Z",
  "reconciled_against": "2026-05-19T09:03:11Z",

  "source_classes_consulted": ["vendor_docs", "roadmap", "pricing", "reviews"],

  "assessments": [
    {
      "job_id_key": "j1",
      "position": "gap",
      "confidence": "medium",
      "rationale": "Reporting is template-driven; no evidence of automated competitive summarization.",

      "prior_position": "parity",
      "change_justification": "New source: 2026-07 changelog shows the comparative reporting module was withdrawn.",

      "features": [
        {
          "feature_name": "Scheduled spend reports",
          "whose": "theirs",
          "position": "parity",
          "description": "Recurring report delivery on a fixed schedule."
        }
      ],
      "sources": [
        {
          "url": "https://coupa.com/products/analytics",
          "title": "Coupa Analytics",
          "source_class": "vendor_docs",
          "retrieved_at": "2026-08-25",
          "quote": "Schedule and distribute standard reports to stakeholders."
        }
      ]
    }
  ],

  "unmapped_observations": [
    {
      "observation": "Announced an AI agent marketplace in June 2026.",
      "why_unmapped": "No job in the current map covers ecosystem/extensibility.",
      "sources": [{"url": "...", "title": "...", "source_class": "vendor_docs", "retrieved_at": "2026-08-25"}]
    }
  ]
}
```

### Required vs optional

| Field | Required | Note |
|---|---|---|
| `confidence` | **Required** | Not optional. A consumer cannot weigh a verdict it can't qualify. |
| `sources` | **Required, non-empty** | An assessment with no sources is invalid, not merely weak. |
| `sources[].retrieved_at` | **Required** | Distinct from any date *in* the content. Freshness is computed from this. |
| `sources[].source_class` | **Required** | Enables coverage measurement across runs. |
| `source_classes_consulted` | **Required** | Run-level: which classes were checked at all, including ones that yielded nothing. |
| `prior_position` | Optional | Present only on a re-run. |
| `change_justification` | Optional | Required *if* `prior_position` is present and differs from `position`. |
| `reconciled_against` | Optional | `run_id` of the findings file this run was compared against. |
| `human_position` | Optional | A reviewer's override. See below. |

### Producer verdict vs. human verdict

`position` is always the **producer's** verdict, regenerated on every run. A
consumer may additionally hold a **human** verdict for the same
`(job_id_key, competitor)` pair — a reviewer disagreeing with the producer.

Two rules follow, and both matter more than they look:

- **A producer never overwrites a human verdict.** A re-run regenerates its own
  verdict *alongside* the human's, not on top of it. Silently reverting someone's
  correction on the next run destroys trust in the whole artifact.
- **Diffs compare producer-to-producer.** A human disagreeing with the model is
  not a competitor changing; folding overrides into change detection would report
  a correction as market movement.

Review is optional. `human_position: null` means unreviewed *or* tacitly agreed —
those are not distinguishable, and a consumer must not treat unreviewed as
suspect. A reviewer may accept every producer verdict without ever looking at it.

### Authored vs. derived position

A producer may either author `position` directly or derive it from an underlying
score. Feature-IQ derives it: Stage 2 scores each product 1-10 against a job, and
the position is a comparison of the two scores' **rubric bands** rather than the
raw numbers — a 7-vs-8 difference for the same capability is model noise, not
signal, and banding discards it.

Consequence worth knowing: a derived position yields only
`advantage`/`gap`/`parity` (plus `unknown` when a score is missing).
`differentiator` requires a judgement scores don't carry, so it remains a
feature-level value.

### Enums (closed vocabularies)

| Field | Values | Source |
|---|---|---|
| `position` | `advantage` · `gap` · `parity` · `differentiator` | matches `job_assessments[].features[].position` |
| `whose` | `ours` · `theirs` | matches `job_assessments[].features[].whose` |
| `confidence` | `high` · `medium` · `low` | new |
| `source_class` | `vendor_docs` · `roadmap` · `pricing` · `reviews` · `other` | new |
| `job_type` | `functional` · `emotional` · `social` | `JobType` |
| `importance` | `critical` · `high` · `medium` · `low` | `JobImportance` |

`unmapped_observations` is the pressure valve for the job-map single-point-of-failure risk:
when the map is wrong or incomplete, a producer must have somewhere to put a real finding
rather than force-fitting it to the nearest job. It doubles as the signal that the map needs
revision. All three baseline runs produced a section like this unprompted.

## The diff contract

**The stable identity of a finding is the pair `(job_id_key, competitor_name)`** — never the
feature name, which is model-generated prose that varies run to run. That pair is what a diff
matches on.

**Compared** (low-cardinality, stable):
- `position`
- `confidence`
- appearance/disappearance of a `(job_id_key, competitor_name)` pair
- `sources[].url` set

**Never compared:** `rationale`, `description`, `features[]` contents, any other prose. These
regenerate fresh each run and are expected to differ in wording while meaning the same thing.

**A position flip is a candidate change, not a confirmed one.** Two runs of the same producer,
on the same subject, on the same day, can disagree. The `prior_position` /
`change_justification` fields exist so a producer must either substantiate a flip against new
evidence or carry the prior verdict forward. What a consumer *does* with an unsubstantiated
flip — suppress it, downgrade confidence, escalate to a human — is implementation behaviour,
not schema.

### Why the diff design is what it is

From the 2026-08-25 baseline evaluation:

- Two runs with **identical input on the same day** agreed on only 3 of 8 job verdicts. One was
  a flat factual contradiction: one run found the vendor's public roadmap showing a feature
  *under consideration* and scored it weak; the other found a support doc describing the same
  feature and scored it strong. Neither found both sources.
- Verdict divergence traced to **source divergence**, not reasoning divergence — hence
  `source_class` and `source_classes_consulted`.
- The two runs shared essentially no sentences, and differed even in section titles. A naive
  text diff would be ~100% noise. This is why prose is explicitly excluded from comparison.
- All three runs invented their own verdict scale and then violated it within the same
  document (`Partial → Strong`, `None (for competitive position)`, `Very strong`). Hence a
  closed vocabulary is pinned rather than assumed.

## Mapping to Feature-IQ

Ingestion is a field mapping, not a transformation:

| Schema | Feature-IQ | Note |
|---|---|---|
| `job-map.yaml` job entry | `ProductJob` | Direct: `job_id_key`, `job_type`, `statement`, `desired_outcomes`, `importance`, `status`. Embedding computed server-side on ingest. |
| `assessments[]` | `CompetitorFunctionalReport.job_assessments` | Server adds `our_score` / `competitor_score` / `outcome_coverage` — a producer has no basis to score "ours" without product data it doesn't hold. |
| `subject` | `ProductCompetitor` | `competitor_name`, `competitor_url`, `competitor_description` |
| `sources[]` | `Evidence` | `source_url`, `source_description`←`title`, `content`←`quote`, `evidence_type: competitive_intel`, `job_id_key` from the parent assessment, `created_by`←`producer.name` |
| `prior_position` / `change_justification` | `changes_from_previous` | See defect below. |
| `producer` | — | New. No field for external-producer provenance. |
| `observed_at` / `retrieved_at` | — | `generated_at` exists on the report; per-source freshness does not. |
| `confidence` | — | New. No per-assessment confidence today. |
| `source_class` | — | New. |

**Known defect this schema prescribes a fix for.**
`ChangeDetectionService.compute_functional_report_diff`
(`backend/app/services/change_detection_service.py:30-59`) keys its diff on
`competitor_feature_name` and computes a set difference over those strings. Any rewording of a
feature name between runs is reported as one removal plus one addition. It also diffs
`functional_comparison` (the flat Stage-1 feature list) rather than `job_assessments`, so the
stable coordinate exists in the data model but is unused.

**Other gaps on the Feature-IQ side** — all lifecycle-layer concerns, i.e. the substrate's job:
no external-producer provenance; no per-source `retrieved_at`; no per-assessment `confidence`;
no source-class recording.

## Versioning

`schema_version` governs the sync contract:

- **Patch** — clarifying docs, no field change.
- **Minor** — additive optional fields only. Both implementations keep working; consumers
  ignore unknown fields (required behaviour, not optional).
- **Major** — a field is removed, renamed, made required, or an enum value's meaning changes.
  Requires both implementations to move together.

Enum values are append-only within a major version.

## Decisions and open questions

**Decided:**
- **Repo home** — one family repo containing several narrow skills plus this shared schema,
  rather than one repo per skill. A skill's unit of install is a directory, so "use them
  separately" survives; a single schema home prevents silent drift across independent forks.

**Open:**
- **Job-map versioning semantics** — the schema only *detects* a mismatch. What a consumer
  should do about it is undecided.
- **`product.yaml`** — sketched, not specified. Possibly near-empty for the competitive
  producer, which only assesses "theirs".
- **Scoring** — deliberately excluded. `our_score`/`competitor_score` need product data a
  standalone producer doesn't have.

## Next step

The baseline evaluation is complete; its findings are folded in above. Next is fixing the four
gaps on the Feature-IQ side — diff key, source dates, confidence, reconciliation — against real
data and CI, then porting the proven methodology outward into `SKILL.md`. Schema and app fix
are one loop: the app fix is the first real consumer of this contract and is expected to
correct it.
