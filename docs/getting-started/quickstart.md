# Feature-IQ Quickstart

A hands-on 10-minute walkthrough. Goal: get the system running locally, log in, and touch every major feature once.

## Prerequisites

- Python 3.11+ (3.12 recommended)
- Node.js 18+
- Redis running locally (`redis-server` or `brew services start redis`)
- An [Anthropic API key](https://console.anthropic.com/) and a [Voyage API key](https://dash.voyageai.com/)
- Optional: a [Brave Search API key](https://brave.com/search/api/) for web-augmented competitor research

PostgreSQL is optional for local dev — SQLite works out of the box.

---

## 1. Set up the environment (~3 min)

```bash
# From the project root
cp backend/.env.example backend/.env
# Edit backend/.env and fill in:
#   SECRET_KEY        (run: python -c "import secrets; print(secrets.token_urlsafe(32))")
#   ANTHROPIC_API_KEY
#   VOYAGE_API_KEY
#   BRAVE_API_KEY     (optional but recommended)

./setup_and_test.sh
```

`setup_and_test.sh` creates the venv, installs backend + frontend dependencies, runs migrations, and runs the test suite. First run takes a few minutes.

## 2. Start the services (~1 min)

You need three processes running. Open three terminal tabs:

**Tab 1 — Backend**
```bash
cd backend && ./venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

**Tab 2 — Celery worker** (required for any background work — audits, triage, synthesis)
```bash
cd backend && ./venv/bin/celery -A app.queue worker --loglevel=info --pool=solo
```
> The `--pool=solo` flag is required on macOS. Linux can use the default pool.

**Tab 3 — Frontend**
```bash
cd frontend && npm run dev
```

Open http://localhost:5173.

> **Shortcut**: `./start.sh` from the project root starts the backend + frontend together. It does **not** start Celery — you still need Tab 2 for any audit/triage/synthesis work.

## 3. Seed the demo data (~30 sec)

```bash
cd backend && ./venv/bin/python -m scripts.seed_demo_data
```

This creates a demo product (Concur Invoice — an AP automation platform), 15 demo users, a set of pre-classified ideas with votes and comments, and lifecycle statuses. The script is idempotent — safe to re-run. To remove: `./venv/bin/python -m scripts.seed_demo_data --cleanup`.

> **Known limitation**: the seed script creates ideas directly without running them through the triage agent, so they don't have triage metadata (job linkage, classification rationale, duplicate links). The demo product, users, and votes are correct — but ideas won't show competitive context or job tags until you submit new ones manually. See [tour.md](tour.md) for what to demo around this.

## 4. Log in

Use the bootstrap admin from `backend/.env`:
- Email: `admin@example.com` (or whatever you set in `ADMIN_EMAIL`)
- Password: whatever you set in `ADMIN_PASSWORD`

Or log in as one of the seeded demo users:
- Admin: `demo_admin@voteflow.dev` / `demo1234`
- Product Owner: `po1@voteflow.dev` / `demo1234`
- Voter: `voter01@voteflow.dev` / `demo1234`

## 5. The 10-minute tour

### Step 1 — Browse the ideas board (1 min)
Land on the Ideas page. You'll see the seeded ideas with vote counts and lifecycle statuses. Click into one to see the detail view, comments, and competitive context panel.

### Step 2 — Open the Job Map editor (2 min)
Navigate to **Competitive Intelligence → Concur Invoice → Job Map**. The job map is the analytical spine of the system. Edit a job, add a new functional or emotional job, see how the structure shapes downstream analysis.

If the demo product doesn't have a job map yet, click **"Generate from product description"** — this kicks off `JobMapExtractorAgent` (Celery task `extract_job_map_task`). Takes ~30 seconds.

### Step 3 — Submit a new idea and watch triage (2 min)
Go to **Submit Idea**, write something like *"We need OCR for handwritten receipts"*. Submit. Within a few seconds the triage agent runs (`submit_and_triage_idea_task` in Celery) and:
- Classifies the idea (`ACCEPTED`, `NEEDS_REVIEW`, `DUPLICATE`, `FEATURE_EXISTS`, or `NOT_APPROPRIATE`)
- Links it to the closest job via embedding similarity
- Surfaces competitive context if competitors already have this feature

This is the canonical proof that the system isn't a glorified voting board — every idea is grounded in jobs and competitive reality.

### Step 4 — Run a competitor audit (3 min)
On the product page, find a competitor with `tracked=True`. Click **Run audit**. This kicks off the two-stage audit (`functional_audit_task`):
- Stage 1 (~45s): web research + raw extraction
- Stage 2 (~90–150s): structured `job_assessments` per job

When it finishes, click into the report. You'll see one assessment per job, with the competitor's position (advantage/gap/parity) and supporting evidence. **This is the unified comparison view** — there are no separate "gaps" and "advantages" sections. They're positions inside one structure.

> If you don't have a Brave API key, audits will still run but with weaker signal.

### Step 5 — Run synthesis (1 min)
Go to **Synthesis Hub**. Click **Run synthesis**. The `unified_synthesis_task` reads the `SynthesisConfig`, combines all included sources (competitor reports, internal feedback themes, existing ideas), and produces a `SynthesisReport` with prioritized opportunities — each scored, tier-classified, tagged to a job, and (above the threshold) auto-converted into Ideas via the triage path.

### Step 6 — Browse the Synthesis output (1 min)
Each opportunity row links to its underlying evidence and (for high-priority items) the auto-generated Idea. Click through to see how the loop closes: synthesis → idea → triage → board.

---

## What just happened

In ten minutes you used:
- **4 of the 10 LLM agents** — JobMapExtractor, FunctionalAudit (2-stage), IdeaTriage, UnifiedSynthesis
- **5 of the 8 Celery task files** — product, competitor, triage, synthesis, jtbd
- **All 3 pillars** — Idea Management, Competitive Intelligence, (Internal Feedback if you imported any)
- **The full closed loop** — competitor signal → synthesized opportunity → idea → triage → vote

For a feature-by-feature inventory, see [tour.md](tour.md). For how the pieces fit together, see [architecture.md](architecture.md).

---

## Troubleshooting

| Problem | Likely cause |
|---|---|
| Celery task stays "pending" forever | Worker not running (Tab 2) or Redis isn't running |
| `429 too many requests` from Anthropic | Rate limit — wait or use a higher-tier key |
| Audit produces empty `job_assessments` | Stage 2 LLM hit the token cap or the source data was stripped — check `AgentExecutionLog` |
| `Embedding service error` | Missing or invalid `VOYAGE_API_KEY` in `.env` |
| Frontend can't reach backend | Check `ALLOWED_ORIGINS` in `.env` includes `http://localhost:5173` |

For more, run `./verify.sh` from the project root for a fast environment check.
