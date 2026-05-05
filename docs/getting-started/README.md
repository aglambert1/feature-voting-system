# Getting Started with Feature-IQ

Feature-IQ is a competitive product intelligence platform built around **Jobs-to-be-Done** (JTBD). Product teams define the jobs their customers are trying to do, then run automated competitor audits and synthesis pipelines that surface gaps, advantages, and opportunity ideas — grounded in those jobs.

This kit is the entry point for new users and demo audiences.

## Read these in order

1. **[Architecture](architecture.md)** — what the system does, the JTBD model, the major components, and how they fit together. ~5 min read.
2. **[Quickstart](quickstart.md)** — a hands-on 10-minute walkthrough using the seeded demo product. Log in, view a job map, run an audit, view synthesis, submit an idea.
3. **[Tour](tour.md)** — feature inventory grouped by user role (Admin, Product Owner, PM, Voter). Use this to figure out *what to show* in a demo, or *what's available* once you're set up.

## What problem does Feature-IQ solve?

PMs lose hours stitching together spreadsheets of competitor features, customer feedback, and roadmap priorities — and the result is usually stale before it's done. Feature-IQ replaces that with:

- **Job maps** — a PO-owned model of what customers are trying to do (functional/emotional/social jobs), not what features they're asking for
- **Automated audits** — run a two-stage LLM analysis of each competitor against the job map to surface gaps and advantages
- **Unified synthesis** — combine competitor signals, internal feedback (CRM/support), and customer ideas into prioritized opportunities — auto-linked to the jobs they serve
- **Triaged ideas** — every submitted idea is classified, deduplicated, and tagged to a job by the triage agent

## What this kit doesn't cover

- **Deployment / production setup** — see [DEPLOYMENT_GUIDE.md](../../DEPLOYMENT_GUIDE.md)
- **Vector search internals** — see [backend/VECTOR_SEARCH_SETUP.md](../../backend/VECTOR_SEARCH_SETUP.md)
- **MCP server (Claude Desktop integration)** — see [backend/scripts/README.md](../../backend/scripts/README.md)
- **Demo interview script (validating PMF with prospects)** — see [DEMO_INTERVIEW_GUIDE.md](../../DEMO_INTERVIEW_GUIDE.md)
- **GTM / positioning** — see [GTM_STRATEGY.md](../../GTM_STRATEGY.md), [COMPETITIVE_POSITIONING.md](../../COMPETITIVE_POSITIONING.md)
