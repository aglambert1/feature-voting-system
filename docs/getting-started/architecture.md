# Feature-IQ Architecture

A high-level map of the system. For deep dives into specific subsystems (vector search, deployment, etc.), follow the links at the end.

## The mental model

Feature-IQ is organized around three pillars that share a single data model:

1. **Idea Management** — voters submit ideas, the triage agent classifies them, PMs review, the team votes
2. **Competitive Intelligence** — define a product, find competitors, audit them, see gaps and advantages per job
3. **Internal Feedback** — import CRM win/loss and support tickets, extract themes, link them to jobs

All three feed into **Unified Synthesis**, which combines signals across pillars and outputs prioritized opportunities — each grounded in a specific Job-to-be-Done.

## The JTBD lens

The analytical model is Clayton Christensen's Jobs-to-be-Done. Instead of "what features do competitors have," the question is "how well does each competitor serve each job our customers are trying to do."

- A **`CIProduct`** has a PO-owned **`job_map`** with functional, emotional, and social jobs
- Each job becomes a **`ProductJob`** row with a 1024-dim embedding (Voyage AI)
- Ideas, evidence, win/loss themes, and support themes are auto-linked to the closest job via cosine similarity (threshold 0.5)
- Audits and synthesis output `job_assessments` — one entry per job, with competitor positions (advantage/gap/parity) inside

This is the load-bearing concept. Everything else is plumbing.

## System diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                             FRONTEND (React + Vite)                        │
│   Landing · Welcome · Login · Register · Join · Forgot Password           │
│   Ideas board · Idea detail · Submit · Profile · PM Review                │
│   CI Hub · Product detail · Job Map editor · Synthesis Hub · Evidence     │
│   Admin: User Mgmt · Cost Reporting · Idea Lifecycle Settings             │
└────────────────────────────────┬───────────────────────────────────────────┘
                                 │ HTTPS / JWT (sliding session)
┌────────────────────────────────▼───────────────────────────────────────────┐
│                          FASTAPI BACKEND (app/)                            │
│                                                                             │
│   API routers (app/api/)                                                   │
│     /auth · /ideas · /votes · /submissions · /admin · /invites             │
│     /product-intelligence/products · /competitive-agents · /job-map         │
│     /pm-review · /monitoring · /internal-feedback                          │
│     /synthesis · /evidence · /jobs · /api-keys                             │
│                                                                             │
│   Services (app/services/)        Agents (app/agents/)                     │
│     queue_service                   ProductAnalyzerAgent                   │
│     embedding_service (Voyage)      CompetitorResearcherAgent              │
│     vector_service (pgvector)       CompetitorFunctionalAuditAgent (2-stage)│
│     llm_service (Claude)            IdeaTriageAgent                        │
│     search_service (Brave)          UnifiedSynthesisAgent                  │
│                                     JobMapExtractorAgent                   │
│                                     InternalDiscoveryAgent                 │
│                                     ActivityInsightAgent                   │
│                                     IdeaStructuringAgent                   │
└─────────┬──────────────────────────────────┬──────────────────────────────┘
          │                                   │
          │ enqueue                           │ read/write
          ▼                                   ▼
┌──────────────────────────────┐   ┌──────────────────────────────────────┐
│  CELERY WORKERS              │   │  POSTGRESQL + pgvector              │
│  (app/queue/)                │   │                                      │
│                              │   │  Users · Ideas · Votes · Comments    │
│   product_tasks              │   │  CIProduct · ProductCompetitor       │
│   competitor_tasks           │◀──│  ProductJob (embeddings)             │
│   triage_tasks               │   │  CompetitorFunctionalReport          │
│   synthesis_tasks            │   │  SynthesisConfig · SynthesisReport   │
│   internal_tasks             │   │  WinLossTheme · SupportTheme         │
│   jtbd_tasks                 │   │  Evidence · QueueJob                 │
│   email_tasks                │   │                                      │
│   scheduled_tasks (Beat)     │   │                                      │
│                              │   │  (SQLite for local dev)              │
└──────────┬───────────────────┘   └──────────────────────────────────────┘
           │
           │ broker
           ▼
   ┌────────────────┐
   │     REDIS      │
   └────────────────┘

           ┌────────────────────────────────────────────────────────────┐
           │  MCP SERVER (mcp_server/) — 78 tools across 10 files        │
           │  Stdio + HTTP/OAuth · exposes most of the API to Claude    │
           └────────────────────────────────────────────────────────────┘
```

## Key data flows

### A. Submitting an idea
1. User submits raw text via `/ideas` or the Submit page — the `Idea` starts as `PENDING`
2. `submit_and_triage_idea_task` (Celery) creates the `Idea` row, then runs `IdeaTriageAgent`
3. Triage classifies (`ACCEPTED`, `NEEDS_REVIEW`, `DUPLICATE`, `FEATURE_EXISTS`, `NOT_APPROPRIATE`), checks for existing competitive coverage, and links to the closest `ProductJob` via embedding similarity
4. PMs review `NEEDS_REVIEW` ideas in the PM Review queue

### B. Running a competitor audit
1. PO clicks "Run audit" on a competitor with `tracked=True`
2. `functional_audit_task` runs `CompetitorFunctionalAuditAgent` in two stages:
   - **Stage 1** (~45s): web research + raw extraction
   - **Stage 2** (~90–150s): structured `job_assessments` per `ProductJob`
3. Result lands as `CompetitorFunctionalReport.job_assessments` — each entry has a position (advantage/gap/parity) and supporting evidence
4. Web research is cached in Redis (24h TTL) to make repeat runs cheap

### C. Running unified synthesis
1. `unified_synthesis_task` reads the `SynthesisConfig` (which source types to include, which competitors, idea-generation thresholds)
2. `UnifiedSynthesisAgent` combines competitor reports, internal feedback themes, and existing ideas
3. Output: a `SynthesisReport` with `SynthesizedOpportunity` rows — each scored, tier-classified, and tagged to a `ProductJob`
4. Opportunities above the priority threshold (default 0.8) auto-generate Ideas via the same triage path

### D. Idea ↔ Job linkage
Embeddings are how everything stays connected. When any text-bearing record (Idea, WinLossTheme, SupportTheme, Evidence) is created or updated, its `statement_embedding` is compared against `ProductJob.statement_embedding` and the best-match `job_id_key` is stored. This means synthesis can join across pillars by job without manual tagging.

## Major components at a glance

| Layer | What it does | Where |
|---|---|---|
| **Frontend** | React SPA — voters, PMs, POs all use the same UI with role-based features | `frontend/src/pages/` |
| **API** | FastAPI routers grouped by domain; shared product-access check in `deps.py` | `backend/app/api/` |
| **Models** | SQLAlchemy models — most domain logic is here | `backend/app/models/` |
| **Services** | Cross-cutting — embeddings, LLM, vector search, queue, search | `backend/app/services/` |
| **Agents** | LLM-driven analysts — each is a class subclassing `BaseAgent` | `backend/app/agents/` |
| **Celery tasks** | Background jobs — 8 domain files plus shared utilities in `helpers.py` (job-failure handling, job linkage, vector math via `app/utils/vectors.py`) | `backend/app/queue/` |
| **MCP server** | 78 tools exposing the API to Claude Desktop | `backend/mcp_server/` |
| **Migrations** | Alembic — must support SQLite (dev) and PostgreSQL (prod) | `backend/alembic/versions/` |

## Tech stack

- **Backend** — FastAPI, SQLAlchemy 2.0, Alembic, Celery 5.4
- **Database** — PostgreSQL 16 + pgvector (production), SQLite + sqlite-vec (local dev)
- **Broker** — Redis 7
- **AI** — Anthropic Claude (analysts), Voyage AI (embeddings, 1024 dims), Brave Search (web research)
- **Frontend** — React 19, Vite, TailwindCSS v4, React Router v7
- **Auth** — JWT with sliding-session refresh; optional TOTP MFA; account lockout; self-service password reset via SendGrid OTP

## Access control

The system has two layers: **system roles** (who you are) and **product permissions** (what you can do with a specific product).

### System roles (`UserRole`)

| Role | Can create products | Product visibility |
|---|---|---|
| **ADMIN** | Yes | Products they created + explicitly granted |
| **PRODUCT_OWNER** | Yes | Products they created + explicitly granted |
| **VOTER** | No | Only products with an explicit permission grant |

ADMINs have additional system-level powers (user management, cost reporting, password resets, account unlocks) but follow the same product-permission rules as everyone else — no implicit bypass.

### Product permissions (`ProductPermission`)

Each product has an access list. Permissions are hierarchical: **OWNER > EDIT > VIEW**.

| Level | View | Edit product / run analyses | Manage members / delete product |
|---|:---:|:---:|:---:|
| **VIEW** | ✓ | | |
| **EDIT** | ✓ | ✓ | |
| **OWNER** | ✓ | ✓ | ✓ |

**Resolution order** when checking access:

1. **Product creator** → implicit OWNER (no `ProductPermission` row required)
2. **Explicit grant** → `ProductPermission` row checked against the required level

### How users get access

- **Invite codes** — A user with EDIT+ creates a shareable code; redeeming it grants VIEW. Codes support max-use limits and expiration.
- **Direct grant** — A product OWNER can grant VIEW, EDIT, or OWNER to any registered user by email (`POST /products/{id}/members`).
- **Permission escalation** — OWNERs can update a member's level (`PATCH /products/{id}/members/{user_id}`). The last active OWNER cannot be demoted or removed.
- **Revocation** — OWNERs can remove a member's access (`DELETE /products/{id}/members/{user_id}`). The product creator's implicit OWNER cannot be revoked.

### Auth security

- JWT sliding-session with `tokens_valid_after` per user — admin password resets invalidate all existing sessions
- Optional TOTP MFA — users enable from Profile, login requires a second step when active
- Account lockout after 5 failed logins within 15 minutes; admin unlock via `/users/{id}/unlock`
- Self-service password reset via email OTP (SendGrid)

## Where to go next

- **Want to use the system?** → [Quickstart](quickstart.md)
- **Want to know what features exist?** → [Tour](tour.md)
- **Want to trace flows A–E step by step?** → [Sequence diagrams](sequence-diagrams.puml) (PlantUML; A–C browser flows, D MCP, E scheduled agents)
- **Want the full roles × entry-points map?** → [Use-case diagrams](use-case-diagrams.puml) (PlantUML; end-user and admin/system surfaces)
- **Want to deploy?** → [DEPLOYMENT_GUIDE.md](../../DEPLOYMENT_GUIDE.md)
- **Want to set up vector search?** → [backend/VECTOR_SEARCH_SETUP.md](../../backend/VECTOR_SEARCH_SETUP.md)
- **Want to use the MCP server?** → [backend/scripts/README.md](../../backend/scripts/README.md)
