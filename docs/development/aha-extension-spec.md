# Project Spec: Aha! AI Idea Assistant Extension

## Pre-work (delete when using spec)

Install the Aha! CLI and get sandbox ready, then prompt Claude Code with:
"Using the attached spec, help me initialize a new Aha! extension project and write a package.json that includes a custom sidebar contribution for 'Idea Insights'."

## 1. Objective

Develop a "packaged" Aha! extension that automates idea management by:

- Monitoring new submissions for AI-driven auto-responses/PM recommendations.
- Identifying themes and duplicates across large datasets via GraphQL extraction.
- Enabling programmatic insertion of ideas from external sources.

## 2. Tech Stack & Infrastructure

- **Development Framework:** [Aha! Develop Extensions](https://support.aha.io) (JavaScript/React).
- **Tooling:** [Aha! Develop CLI](https://github.com) for scaffolding, watching, and building.
- **APIs:**
  - **GraphQL API:** Primary method for bulk data extraction and complex queries.
  - **REST API:** For specific record creation/updates (e.g., Ideas, Votes).
- **Sandbox Environment:**
  - Personal **Aha! Develop Essentials** account ($9–$12/mo).
  - Initial 30-day trial of **Aha! Roadmaps/Ideas Advanced** to test Automation Triggers.

## 3. Core Requirements & Implementation

### A. Idea Monitoring & Auto-Response

- **Strategy:** Use `Activity Webhooks` (Account Settings) to trigger an external endpoint or internal extension logic.
- **Logic:** Fetch idea text → Send to external DB/LLM → Post `Admin Response` via `PUT /api/v1/ideas/:id`.

### B. Bulk Data Extraction

- **Strategy:** Utilize the [GraphQL API](https://support.aha.io).
- **Focus:** Query `ideas` node with sub-fields: `description`, `votes`, `comments`, and `workflowStatus`.
- **Portability:** Use `aha.graphQuery` within the extension to ensure it runs against the local client's data.

### C. Standardized Packaging

- **Manifest:** Define unique identifier in `package.json`.
- **Configuration:** Use `Extension Fields` to allow clients to enter their own API keys/DB endpoints without modifying code.

## 4. Development Commands (CLI)

- `npm install -g @aha-app/aha-cli` (Install CLI)
- `aha auth:login` (Connect to personal sandbox)
- `aha extension:create` (Scaffold project)
- `aha extension:watch` (Sync local changes to sandbox)
- `aha extension:build` (Generate `.gz` file for client distribution)

## 5. Cost Summary

- **Dev Instance:** ~$9/mo (Aha! Develop Essentials).
- **Client Requirement:** Client must have an active Aha! subscription (Advanced tier recommended for full automation).
