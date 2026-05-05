# Feature-IQ Backend

FastAPI backend for Feature-IQ — competitive product intelligence built around Jobs-to-be-Done.

## Start here

For getting started, architecture, and a guided walkthrough:

→ **[../docs/getting-started/](../docs/getting-started/)**

The quickstart covers fresh setup, running the server, running Celery, and a 10-minute tour of the major features.

## Backend layout

```
app/
  api/            FastAPI routers (auth, ideas, votes, products, synthesis, etc.)
  agents/         LLM-driven analysts (10 agents, all subclassing BaseAgent)
  models/         SQLAlchemy models (User, Idea, CIProduct, ProductJob, ...)
  queue/          Celery tasks (split across 7 domain files)
  schemas/        Pydantic request/response schemas
  services/       Cross-cutting services (LLM, embeddings, vector, queue, search)
  utils/          Shared utilities

alembic/          Database migrations (must support SQLite + PostgreSQL)
mcp_server/       MCP server for Claude Desktop (79 tools across 10 files)
scripts/          Management scripts (see scripts/README.md)
tests/            Pytest test suite
```

## Common commands

```bash
# Run the API server
./venv/bin/python -m uvicorn app.main:app --reload --port 8000

# Run the Celery worker (required for any background work)
./venv/bin/celery -A app.queue worker --loglevel=info --pool=solo  # macOS
./venv/bin/celery -A app.queue worker --loglevel=info              # Linux

# Run the test suite
./venv/bin/python -m pytest tests/ -v

# Apply migrations
./venv/bin/alembic upgrade head

# Create a migration
./venv/bin/alembic revision --autogenerate -m "description"
```

## Environment variables

Copy `.env.example` to `.env` and fill in:

| Key | Required | Purpose |
|---|---|---|
| `SECRET_KEY` | yes | JWT signing key |
| `ANTHROPIC_API_KEY` | yes | Claude API for agents |
| `VOYAGE_API_KEY` | yes | Embeddings (1024 dims) |
| `BRAVE_API_KEY` | recommended | Web research for competitor audits |
| `DATABASE_URL` | yes | SQLite for local dev, PostgreSQL for prod |
| `REDIS_URL` | yes | Celery broker |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | yes | Bootstrap admin user |
| `DEV_OTP_BYPASS` | dev only | Fixed OTP code when `DEBUG=true` |

## Other docs

- **[scripts/README.md](scripts/README.md)** — management scripts, demo seeding, MCP server, migrations
- **[VECTOR_SEARCH_SETUP.md](VECTOR_SEARCH_SETUP.md)** — Voyage AI + pgvector setup
- **[PASSWORD_MANAGEMENT.md](PASSWORD_MANAGEMENT.md)** — password reset / OTP flow
- **[DEV_MODE_OTP.md](DEV_MODE_OTP.md)** — dev-only OTP bypass
