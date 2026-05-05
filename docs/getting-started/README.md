# Getting Started with Feature-IQ

Feature-IQ is a competitive product intelligence platform built around **Jobs-to-be-Done** (JTBD). Product teams define the jobs their customers are trying to do, then run automated competitor audits and synthesis pipelines that surface gaps, advantages, and opportunity ideas — grounded in those jobs.

This kit serves three audiences. Pick the one that fits.

## If you've been given access to a Feature-IQ instance

You're a prospect or end user. Read this:

- **[Welcome](welcome.md)** — what you can do today, what to try first, and where the value is. The same content also lives at `/welcome` inside the app.
- **[Claude Desktop setup](claude-desktop.md)** — connect Claude to Feature-IQ via MCP. This is the showcase use case. 5 minutes from API key to working tools.

## If you're evaluating Feature-IQ as a developer

You want to understand what's there and run it locally:

- **[Architecture](architecture.md)** — what the system does, the JTBD model, components, and data flows
- **[Quickstart](quickstart.md)** — hands-on 10-minute setup and walkthrough on localhost
- **[Tour](tour.md)** — feature inventory grouped by user role (Admin, Product Owner, PM, Voter)

## If you operate the Feature-IQ deployment

You're setting up demo content or running prod:

- **[Demo recipe](demo-recipe.md)** — step-by-step recipe for building the curated demo product on prod. Covers the full chain: product creation, job map, competitors, audits, synthesis, ideas, and prospect access.

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
