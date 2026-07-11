# Feature-IQ Tour

A feature inventory grouped by user role. Use this as a demo cheat-sheet — what to show, who it's for, and where it lives in the UI.

> Roles in the system: **Admin**, **Product Owner (PO)**, **Product Manager (PM)**, **Voter**. Permissions are also scoped per-product via `ProductPermission`.

---

## For Voters (anyone with an account)

The simplest experience — the "feature voting board" most products would call their whole offering. In Feature-IQ, this is layer one of three.

| Feature | Where | What it does |
|---|---|---|
| Browse ideas | Ideas page | Filter by status, lifecycle stage, source. Sort by votes, recency |
| Vote | Idea card or detail page | One vote per user per idea. Toggleable |
| Submit an idea | Submit page | Free-text input runs through `IdeaStructuringAgent` for clean formatting, then `IdeaTriageAgent` for classification |
| Comment | Idea detail page | Threaded comments |
| See competitive context | Idea detail page | If the triage agent found that competitors have this feature, it's shown inline |
| See job linkage | Idea detail page | Each idea is auto-tagged to the closest `ProductJob` via embedding similarity |
| Profile | Profile page | Settings, password change |

**What to demo for voters:** Submit an idea like *"add OCR for handwritten receipts"*, watch it get classified within seconds with competitive context and a job tag.

---

## For Product Managers (PMs)

PMs use everything voters use, plus the review and triage workflows.

| Feature | Where | What it does |
|---|---|---|
| PM Review queue | PM Review page | Ideas classified as `NEEDS_REVIEW` by the triage agent — PM is the arbiter |
| Override classifications | Idea detail page | Force-approve, mark as duplicate, change status |
| Lifecycle status | Idea Lifecycle Settings | Define custom statuses ("On Roadmap", "In Development", "Delivered") with colors and order |
| Idea status history | Idea detail page | Audit trail of every status change |
| Internal feedback themes | Internal Feedback page | View extracted themes from imported CRM/support data |
| Synthesis Hub | Synthesis Hub | Run unified synthesis, browse opportunities, download as markdown |

**What to demo for PMs:** The PM Review queue. The triage agent does the heavy lifting (classification, deduplication, job linkage), but ambiguous calls get routed here. The agent's classification rationale is visible inline so PMs can see *why* it flagged something — they're the arbiter, not the rubber stamp.

---

## For Product Owners (POs)

POs own the analytical spine — the job map, the competitor list, and the synthesis configuration. This is where Feature-IQ differentiates from a feature-voting tool.

### Product setup

| Feature | Where | What it does |
|---|---|---|
| Product list / create | Intelligence Hub | Add a `CIProduct` — your product under analysis |
| Product analysis | Analyze Product page | Runs `ProductAnalyzerAgent` to extract features and positioning from the product description |
| Job map editor | Job Map editor | The PO-owned model of customer jobs — functional, emotional, social. Hierarchical |
| Generate job map from product | Job Map editor | One-click → `JobMapExtractorAgent` infers a starter job map |
| Scoring weights | Product settings | Tune how synthesis weights ideas, competitor gaps, and internal feedback |

### Competitive intelligence

| Feature | Where | What it does |
|---|---|---|
| Competitor discovery | Product detail | Runs `CompetitorResearcherAgent` (web-augmented via Brave) to find competitors |
| Competitor inclusion toggles | Product detail | `audit_enabled` and `synthesis_included` are independent — different competitors can be in audits vs. synthesis |
| Run a competitor audit | Competitor card | Two-stage audit: web research → structured `job_assessments`. ~3 min total |
| Competitor functional reports | Competitor reports tab | Unified view: each job shows competitor positions (advantage, gap, parity) with supporting evidence |
| Alerts | Monitoring page | Flag changes in competitor reports across runs |
| Scheduled monitoring | Competitive Agent settings | Daily/weekly schedules for automated audits via Celery Beat |

### Synthesis

| Feature | Where | What it does |
|---|---|---|
| Synthesis Hub | Synthesis Hub | Latest report, opportunities table, markdown download |
| Synthesis config | Synthesis Hub | Select source types, included competitors, idea-generation threshold (default 0.8) |
| Run unified synthesis | Synthesis Hub | `UnifiedSynthesisAgent` combines competitor reports + internal feedback themes + existing ideas → `SynthesizedOpportunity` rows |
| Linked ideas | Synthesis Hub | High-priority opportunities (above threshold) auto-generate Ideas via the triage path. The "View Idea #N" button jumps to the linked idea |
| Manual create-from-opportunity | Synthesis Hub | For opportunities below threshold, PO can edit fields and create an Idea manually — same triage path |

### Internal feedback

| Feature | Where | What it does |
|---|---|---|
| Import CRM data | Internal Feedback page | Bulk import of deals/win-loss data |
| Import support data | Internal Feedback page | Bulk import of support tickets |
| Extracted themes | Internal Feedback page | `InternalDiscoveryAgent` and `ActivityInsightAgent` extract patterns and link to jobs |

### Evidence

| Feature | Where | What it does |
|---|---|---|
| Evidence factbase | Evidence page | Manually-curated factbase. Citations from agents auto-increment evidence counts |
| Evidence search | Evidence page | Semantic search via embeddings |

**What to demo for POs:** The complete loop. Open the job map, point out it's PO-owned and editable. Run a competitor audit. Open the report — show that there are no separate "gaps" and "advantages" sections, just job-by-job positions. Run synthesis. Show how an opportunity becomes a triaged idea on the board. The job-tagged thread runs through everything.

---

## For Admins

Admins manage users, see system-level data, and configure org-wide settings.

| Feature | Where | What it does |
|---|---|---|
| User management | User Management page | Create, edit, deactivate users; assign roles |
| Invite codes | Product detail / admin | Generate one-time invite codes that auto-grant `ProductPermission` on registration |
| Cost tracking | Admin page | Per-product LLM cost tracking (`CostRecord` model) |
| Agent execution logs | Admin / queue | Inspect every agent run, prompt, response, and timing |
| API keys | API Keys page | Create per-user keys for the MCP server |
| Queue jobs | Admin / queue | Inspect Celery job state, retry, cancel |

**What to demo for Admins:** Cost tracking and the agent execution log. Every LLM call is recorded with token counts, cost, and timing. Useful for proving that ROI is real and that agent runs are observable.

---

## For Claude Desktop / MCP users

The MCP server (`backend/mcp_server/`) exposes 75 tools across 10 files. Most of the API surface is available to Claude Desktop, scoped per user via `APIKey`.

| Tool group | Examples | Use case |
|---|---|---|
| `product_*` | `product_list`, `product_create`, `product_run_analysis` | "Add a product called Notion to my CI pipeline" |
| `ci_*` | `ci_run_discovery`, `ci_run_competitor_audit`, `ci_get_competitor_report` | "Find competitors for Linear and audit the top 3" |
| `ideas_*` | `ideas_list`, `ideas_search`, `ideas_create` | "What's the highest-voted idea this month?" |
| `synthesis_*` | `synthesis_run_unified`, `synthesis_configure` | "Run synthesis on Concur Invoice with all sources included" |
| `evidence_*` | `evidence_add`, `evidence_search` | "Add this customer quote to the evidence factbase" |
| `pm_review_*`, `monitoring_*`, `internal_*`, `jobs_*`, `composite` | various | Workflow tools for PMs |

To connect, see [backend/scripts/README.md](../../backend/scripts/README.md).

---

## What's intentionally excluded

- **Roadmap planning** — Feature-IQ informs roadmap decisions, it doesn't replace roadmapping tools
- **Customer-facing portals** — voters are internal users (employees, internal stakeholders); there's no public idea portal
- **Direct CRM integration** — internal feedback comes in via bulk import, not live API integration
- **Direct competitor scraping** — competitor research is web-search-augmented (Brave), not scraping their product

These are deliberate scope choices, not gaps to fill.

---

## Where to go next

- Want to actually use it? → [Quickstart](quickstart.md)
- Want to understand how it works? → [Architecture](architecture.md)
- Want to deploy it? → [DEPLOYMENT_GUIDE.md](../../DEPLOYMENT_GUIDE.md)
- Running a demo? → [DEMO_INTERVIEW_GUIDE.md](../../DEMO_INTERVIEW_GUIDE.md) for post-demo PMF questions
