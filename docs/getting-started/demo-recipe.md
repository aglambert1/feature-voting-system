# Demo Recipe — Building the Sample Product on Prod

A step-by-step recipe for setting up a curated demo product on production at [https://feature-iq.onrender.com](https://feature-iq.onrender.com). Run this once per fresh prod environment. Total time: ~60–90 minutes (most of it waiting on background tasks).

> **Audience**: this doc is for the operator (the person who owns the Feature-IQ deployment). End users / prospects shouldn't need to read it.

---

## What you're building

A demo product that prospects can explore in read-only mode (`ProductPermissionLevel.VIEW`). Goal: prospects land on the product, see realistic content immediately, and can play with the analytical tools without breaking anything.

**Demo product target — Concur Invoice (AP automation)**:
- Job map with 5–7 jobs (functional + emotional + social mix)
- 4–5 competitors total:
  - **3 fully audited + included in synthesis** (so reports and synthesis are populated for the cold-open demo)
  - **1 unaudited but enabled** (for the live "watch it run" moment during demos)
  - **0–1 disabled** (to show toggle controls)
- 1 completed unified synthesis report with auto-generated opportunities
- ~15–20 ideas, mostly submitted via the live triage path (so they have job linkage and competitive context). A small minority can come from the seed script to inflate vote counts.
- Sample comments and votes on a handful of ideas
- Lifecycle statuses configured (On Roadmap / In Development / Delivered)

---

## Prerequisites

- Admin account on prod with full access
- All env vars configured on Render (ANTHROPIC_API_KEY, VOYAGE_API_KEY, BRAVE_API_KEY, REDIS_URL, DATABASE_URL)
- Both Render services running: `feature-iq` (FastAPI + frontend) and `feature-iq-mcp` (MCP HTTP)
- Celery worker service running (audits and triage will hang silently if not)
- ~$5–10 of Anthropic + Voyage + Brave credit available for the audits and synthesis

**Verify before starting**: log in as admin → check that you can browse the API at `/docs` and that any test request to a Celery-backed endpoint actually completes.

---

## Step 1 — Create the demo Product Owner user (~2 min)

In the admin user management page, create:
- **Username**: `demo_po`
- **Email**: `demo@featureiq.app` (or whatever you control)
- **Role**: `PRODUCT_OWNER`
- **Password**: store this in your password manager

You'll do all subsequent steps logged in as this user (not as admin) so the demo product is owned by `demo_po`. This makes the prospect experience cleaner.

> Why not admin? When you later share the demo product with prospects via `ProductPermission`, the *owner* can see it in their product list. If admin owns it, the demo accidentally appears in admin contexts.

---

## Step 2 — Create the product (~1 min)

Log in as `demo_po`. Go to **Competitive Intelligence → Create Product**:

- **Name**: `Concur Invoice`
- **Description**: *Concur Invoice is an accounts payable automation platform that helps organizations streamline invoice processing, automate approval workflows, and gain visibility into supplier spending. Features include invoice capture, three-way PO matching, configurable approval routing, and integration with major ERP systems.*
- **Category**: `Accounts Payable Automation Software`

Save. You'll land on the product detail page.

---

## Step 3 — Run product analysis (~30s)

On the product page, click **Run Product Analysis**. This calls `ProductAnalyzerAgent` and extracts structured features and positioning. Wait for it to finish (~30 seconds).

Checkpoint: refresh and verify the product now has extracted features visible.

---

## Step 4 — Generate the job map (~30s) and refine

Click **Job Map** in the product nav, then **Generate from product description**. This kicks off `JobMapExtractorAgent` (Celery task). It produces a starter job map.

When it completes, **review and edit the job map manually** to improve realism. Aim for:
- 3–4 functional jobs (e.g., *"Process invoices accurately and on time"*, *"Match invoices to POs without errors"*)
- 2 emotional jobs (e.g., *"Feel confident I'm not missing fraud"*)
- 1–2 social jobs (e.g., *"Look professional and modern to vendors"*)

Each job should have a clear `job_statement`, `importance` (critical/high/medium/low), and a brief description. **Save**.

> Why edit manually? The job map is the load-bearing analytical content — every audit, every synthesis output, every idea linkage flows from these statements. The auto-generated version is a starter, not finished.

---

## Step 5 — Add competitors (~5 min)

In the product detail, go to the Competitors tab. Either:

**Option A — Run discovery** (recommended): click **Run Discovery**. This calls `CompetitorResearcherAgent` (web-augmented via Brave) and surfaces 5–10 candidate competitors. Pick 4–5 to add. Takes ~1 minute.

**Option B — Add manually**: click **Add Competitor** and enter:
- `Coupa` — `https://www.coupa.com`
- `Stampli` — `https://www.stampli.com`
- `Tipalti` — `https://www.tipalti.com`
- `AvidXchange` — `https://www.avidxchange.com`
- `Bill.com` — `https://www.bill.com`

(These are real Concur Invoice competitors. Pick 4–5 of them.)

Set toggles — for the demo target:
- **3 of them**: `audit_enabled = true`, `synthesis_included = true`
- **1 of them**: `audit_enabled = true`, `synthesis_included = false` (this is the one we'll *not* audit yet — leave it enabled but don't run the audit so the live-demo button works)
- **1 of them** (optional): `audit_enabled = false` to show the toggle UI

---

## Step 6 — Run audits on the 3 "fully audited" competitors (~12–15 min)

For each of the 3 audit-target competitors, click **Run Audit** on the competitor card. The two-stage audit takes ~3 minutes per competitor:
- Stage 1 (~45s): web research + raw extraction
- Stage 2 (~90–150s): structured `job_assessments` per `ProductJob`

You can run them in parallel — kick off all 3 and wait. Total wall time: ~4 minutes if parallel, ~12 if sequential.

When each completes, **open the report and skim it**. If the `job_assessments` look thin (e.g., the LLM produced empty or nonsensical output), re-run. This happens occasionally on flaky web research — re-running with the cached research tends to produce better Stage 2 output.

Checkpoint: 3 competitors should have green "Report ready" indicators.

> **Do not** audit the 4th competitor. Leave it `audit_enabled=true` but no report — that's the live-demo target.

---

## Step 7 — Run unified synthesis (~2 min)

Go to **Synthesis Hub**. Verify the `SynthesisConfig` includes:
- `competitor_features` source type
- The 3 audited competitors
- `auto_generate_ideas = true`
- `idea_priority_threshold = 0.8` (default — leave as-is)

Click **Run Synthesis**. Wait ~1–2 minutes for `unified_synthesis_task` to complete.

When it lands, browse the opportunities table:
- Each row should have a job tag, score, tier, and (for high-priority items) a linked Idea
- Download the markdown report — verify it reads cleanly

If the report is empty or looks broken, re-run. This is rare but happens.

Checkpoint: synthesis report exists, opportunities are populated, some have linked ideas (those Ideas are auto-created via the triage path — they'll have job linkage).

---

## Step 8 — Submit the manual ideas (the bulk of the demo content) (~15–20 min)

This is where most demo-quality content comes from. **Submit each idea via the UI as the `demo_po` user (or as a voter — see step 9)**. Don't bulk-insert via script — the goal is to get triage rationale, job linkage, and competitive context on every idea.

Aim for **12–15 manually-submitted ideas** covering a mix of:

| Type | Example | Why |
|---|---|---|
| Feature-gap idea | *"Add OCR for handwritten receipts — vendors still send paper sometimes"* | Hits a job ("capture invoices accurately") + likely matches a competitor gap |
| Workflow idea | *"Bulk approval for low-dollar invoices under $500"* | Job-tagged, may or may not have competitive coverage |
| Emotional-job idea | *"Daily summary email of pending approvals so I don't have to log in just to check"* | Hits "feel confident I'm on top of things" emotional job |
| Integration idea | *"Native NetSuite sync for AP coding"* | Tests integration competitive context |
| Edge case | *"Multi-currency support for European subsidiary invoices"* | Tests how triage handles narrower scope |
| Likely duplicate | *"Receipt scanning"* (after submitting OCR earlier) | Demonstrates dedup |
| Likely NOT_APPROPRIATE | *"What's the weather like today"* | Demonstrates classifier rejection — keep this for the demo's "watch it triage" moment if you want, or skip if you don't want noise |

After each submission, wait ~10 seconds and refresh — verify the triage agent has run, the idea has a `job_id_key`, and (where applicable) competitive context is populated.

> If a submission stays in `pending` forever, the Celery worker is down. Don't keep submitting; fix the worker first.

---

## Step 9 — Add votes and comments (~10 min)

Create 5–6 voter accounts via the admin user management page (e.g., `voter01@featureiq.app` through `voter06@featureiq.app`, all with `VOTER` role). Use a memorable shared password.

For each voter, log in and:
- Vote on 4–6 of the manually-submitted ideas (mix it up so vote counts vary — the demo should show clear "hot" ideas vs. tail)
- Add 1–2 comments on the highest-vote ideas

Goal: when a prospect lands on the Ideas board, they see realistic vote distribution (e.g., top idea has 5–6 votes, tail has 1–2) and some social proof in the form of comments.

> Optional: if you want to inflate vote counts further without creating more accounts, run `seed_demo_data.py --product-id <demo_product_id>` (but be aware it won't be tied to the demo product's job map and will create extra ideas without triage — see [seed-script caveat in the quickstart](quickstart.md#3-seed-the-demo-data-30-sec)). Recommend skipping unless you really need higher numbers.

---

## Step 10 — Configure lifecycle statuses (~2 min)

As `demo_po`, go to **Idea Lifecycle Settings**:

| Name | Slug | Color | Position |
|---|---|---|---|
| On Roadmap | `on_roadmap` | `#3B82F6` (blue) | 0 |
| In Development | `in_development` | `#F59E0B` (amber) | 1 |
| Delivered | `delivered` | `#10B981` (green) | 2 |

Save. Then move 2–3 of the high-vote ideas into these statuses (e.g., one to "On Roadmap", one to "In Development") so the lifecycle column has variety.

---

## Step 11 — Grant prospects read access (when ready)

For each prospect you want to share the demo with:

1. Create their account (admin user management) with role `PRODUCT_OWNER` and a temporary password
2. On the demo product, add a `ProductPermission` for that user with level `VIEW`
3. Send them their credentials + the link to [the welcome page](welcome.md) (Track 2)

They can:
- Browse the demo product, audits, synthesis, ideas
- Vote, comment, submit new ideas to the demo product (these are clearly tagged as theirs and don't break the analytical content)
- Generate their own MCP API key (since they're `PRODUCT_OWNER`) and connect Claude Desktop
- Create their own product in their own workspace

They cannot:
- Run audits, synthesis, or analyses on the demo product
- Edit the demo product's job map, competitors, or settings
- Delete anything on the demo product

---

## Verification checklist

Before declaring the demo ready:

- [ ] Log out, log in as a fresh prospect-style account with VIEW permission. Confirm:
  - Demo product is visible in their product list
  - Job map is browseable (read-only)
  - 3 competitor reports load with populated `job_assessments`
  - 1 competitor has no report and the **Run Audit** button is visible (this is your live-demo target)
  - Synthesis Hub shows the report with opportunities and linked ideas
  - Ideas board has ~15–20 ideas with vote distribution and 2–3 in roadmap statuses
  - Clicking an idea shows triage classification rationale and competitive context
- [ ] Generate an API key as the prospect → connect Claude Desktop → ask *"What products do I have?"* — confirm Concur Invoice shows up
- [ ] Try one read-only MCP query (e.g., `synthesis_get_unified_report` via natural language)
- [ ] Try one write attempt (e.g., *"Run a new audit"*) — confirm it fails with permission error

If all checks pass, you're ready to demo from prod.

---

## Refreshing the demo

The demo isn't a static snapshot — over time, voter accounts will accumulate noise, ideas will pile up, and you may want to reset.

**Light refresh** (no data loss):
- Delete user-submitted ideas from prospect VIEW users (admin override)
- Re-run the synthesis if competitor reports have drifted

**Full reset** (start over): delete the demo product as `demo_po` (uses `delete_product.py` semantics) and re-run this recipe. Plan for ~90 minutes.

There's no automated demo refresh today. If demand grows, an admin endpoint at `/admin/demo/reset` would be a sensible next step — but YAGNI for now.

---

## Cost estimate

Approximate cost per full demo build (one-time):

| Item | Approx cost |
|---|---|
| Product analysis | $0.10 |
| Job map extraction | $0.10 |
| 3 × competitor audits (2-stage, with Brave research) | $0.50–$1.00 each |
| Unified synthesis | $0.30 |
| ~15 idea triages (LLM classification + embeddings) | $0.50 total |
| **Total** | **~$3–6** |

Subsequent prospect MCP usage adds incremental cost per query. Cap exposure by hand-issuing accounts (no public registration), per the cost-control plan.
