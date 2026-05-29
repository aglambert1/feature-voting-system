# Feature-IQ

A competitive product intelligence platform built around **Jobs-to-be-Done**. Define the jobs your customers are trying to do, run automated competitor audits and synthesis, and surface prioritized opportunities — grounded in those jobs.

Three pillars:

- **Idea Management** — submit, vote on, and triage feature ideas
- **Competitive Intelligence** — discover competitors, run two-stage functional audits, see gaps and advantages per job
- **Internal Feedback** — import CRM/support data, extract themes, link them to jobs

Everything feeds **Unified Synthesis**, which combines signals across pillars into prioritized, job-tagged opportunities.

## Start here

→ **[docs/getting-started/](docs/getting-started/)**

- [Architecture](docs/getting-started/architecture.md) — system overview, JTBD model, components
- [Quickstart](docs/getting-started/quickstart.md) — 10-minute hands-on walkthrough
- [Tour](docs/getting-started/tour.md) — feature inventory by user role

## Tech stack

FastAPI · SQLAlchemy · Alembic · Celery 5.4 · PostgreSQL 16 + pgvector (or SQLite locally) · Redis 7 · React 19 + Vite + TailwindCSS · Anthropic Claude · Voyage AI (embeddings) · Brave Search

## Project layout

```
backend/         FastAPI backend, agents, Celery tasks, MCP server
frontend/        React TypeScript SPA
docs/            Documentation
  getting-started/    Start here
  development/        Design archive (prompts, specs)
  archive/            Superseded docs
```

## Other documentation

| Topic | Doc |
|---|---|
| Deployment | [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) |
| Vector search setup | [backend/VECTOR_SEARCH_SETUP.md](backend/VECTOR_SEARCH_SETUP.md) |
| Scripts and MCP server | [backend/scripts/README.md](backend/scripts/README.md) |
| Password / OTP flows | [backend/PASSWORD_MANAGEMENT.md](backend/PASSWORD_MANAGEMENT.md) · [backend/DEV_MODE_OTP.md](backend/DEV_MODE_OTP.md) |
| Demo conversation guide | [DEMO_INTERVIEW_GUIDE.md](DEMO_INTERVIEW_GUIDE.md) |
| Positioning / GTM | [COMPETITIVE_POSITIONING.md](COMPETITIVE_POSITIONING.md) · [GTM_STRATEGY.md](GTM_STRATEGY.md) |
| Release history | [CHANGELOG.md](CHANGELOG.md) |

## License

MIT — see [LICENSE](LICENSE).
