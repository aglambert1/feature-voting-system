# Feature Voting System - Claude Code Instructions

## Code Conventions

### Process (always follow)
Before writing code that references existing models or services:
1. Read the model/service definition file to verify exact field/method names
2. Check imports at top of the file being edited to see what's already available
3. Look at similar existing code in the same file for patterns to follow

For any feature development or code change, evaluate whether new or updated CI tests are needed:
- New endpoints or services → add tests
- Changed business logic or data flows → update existing tests or add new ones
- Bug fixes → add a regression test when feasible
- If no tests are needed, briefly explain why

### Quick Reference (update when changing these)
Common patterns - verify against source if unsure:

**Models** (`backend/app/models/`):
- Product: `CIProduct` → `product_name`, `product_description`, `product_category`
- Competitor: `ProductCompetitor` → `competitor_name`, `competitor_url`, `tracked`
- Feature: `ProductFeature` → `feature_name`, `feature_description`
- Report: `CompetitorFunctionalReport`, `LandscapeOpportunityReport`

**Services** (`backend/app/services/`):
- `QueueService` → `mark_running()`, `mark_success()`, `mark_failure()`, `get_job()`
- `embedding_service` → `generate_embedding(text, input_type)`, `generate_embeddings_batch(texts, input_type)` — Voyage AI API, 1024 dims, input_type: "document" or "query"

**Celery Tasks** (`backend/app/queue/tasks.py`):
- Use `@shared_task` decorator (not `@celery_app.task`)
- Import models inside task functions to avoid circular imports

**Database Migrations** (`backend/alembic/versions/`):
- When adding, removing, or modifying SQLAlchemy models, always create an Alembic migration file
- Migration runs automatically on local startup (`start.sh`) and Render deploy (`preDeployCommand`)
- Follow existing naming pattern: `{revision_id}_{description}.py`
- Register new models in `backend/app/models/__init__.py` so `Base.metadata` picks them up
- **Must support both SQLite (local dev) and PostgreSQL (prod)**:
  - Use `sa.String()` instead of `sa.Enum()` in migration DDL (ORM `Enum` type handles both automatically)
  - Use `sa.text('CURRENT_TIMESTAMP')` not `sa.text('now()')`
  - Use `server_default='0'` for booleans, not `server_default=sa.text('false')`
  - Avoid PG-specific syntax (e.g., `CREATE TYPE`, `USING` casts)
  - In `op.execute`/`sa.text` DML, **never compare boolean columns with integers** (`= 1`, `= 0`, `THEN 1`). PostgreSQL has a strict boolean type and rejects these. Use bare column references (`deep_analysis_enabled`) or `true`/`false` literals instead. SQLite accepts both, so this bug passes locally but fails on prod.
  - In `op.execute`/`sa.text` DML, **always use uppercase enum member NAMES** (e.g., `'ADMIN'`, `'OWNER'`) not lowercase Python values (`'admin'`, `'owner'`). No model in this codebase uses `values_callable`, so PG stores enum labels as the uppercase `.name`, not the `.value`. SQLite stores strings and accepts either casing, so this bug passes locally but 500s on prod.

**When to update this section:**
- Adding/renaming model fields
- Adding/renaming service methods
- Changing patterns used in 3+ places

### Documentation upkeep
When adding, removing, or changing scripts, migrations, or CLI tools, update the relevant README:
- `backend/scripts/README.md` — management scripts, DB utilities, migrations

## Git Workflow (always follow)

- **Never push directly to `main`** — all changes go through a PR
- Create a feature branch, commit, push, and open a PR via `gh pr create`
- CI tests must pass before merging
- This applies to all changes, including one-line fixes and .gitignore updates
- Production (Render) deploys from `main`, so treat it as protected

### Branch cleanup
At the start of each new piece of work, prompt AG to clean up merged local branches:
1. `git fetch --prune` — removes local refs to remote branches GitHub already deleted
2. `git branch -vv` — show what's left so AG can decide what to delete
3. `git branch -D <branch>` — delete branches whose remotes are gone (squash-merge repos always need `-D`)

Don't run cleanup automatically — show AG the branch list and let them confirm.

## Security (always follow)

**The GitHub repo is PUBLIC.** Every commit is world-readable, forever, including from history.

Before staging or pushing, verify the diff contains:
- No API keys, tokens, or secrets of any kind (Anthropic, Voyage, Brave, JWT signing keys, OAuth client secrets, OTP codes, database passwords)
- No `.env`, `.env.local`, `.env.production`, or any file that resembles one
- No real user emails, PII, credentials, or customer data
- No prod URLs/IPs/hostnames that aren't already documented publicly
- No internal monitoring dashboards, admin URLs, or anything that gives an attacker reconnaissance value
- No hardcoded passwords in tests, fixtures, or seed scripts (use placeholders)

Treat `.gitignore` as load-bearing. If a file might contain secrets in any environment, gitignore it.

If a secret is accidentally committed: rotate it immediately (assume compromised), then scrub from history. Don't just delete the file in a follow-up commit — git history retains it.

## Project Structure

- `backend/` - FastAPI backend with SQLAlchemy models
- `frontend/` - React TypeScript frontend
- `docs/development/` - Design documents and prompts

## Development Commands

```bash
# Backend
cd backend && ./venv/bin/python -m uvicorn app.main:app --reload --port 8000

# Celery worker
cd backend && ./venv/bin/celery -A app.queue worker --loglevel=info --pool=solo

# Frontend
cd frontend && npm run dev
```
