# Connect Feature-IQ to Claude Desktop

Feature-IQ exposes 78 MCP tools. Connect Claude Desktop to your Feature-IQ account and you can run competitor audits, query ideas, generate synthesis, and explore your job map — all in plain English, with Claude's reasoning on top of Feature-IQ's data.

This is the most powerful way to use Feature-IQ. No coding required.

---

## What you'll need

- A Feature-IQ account with **Product Owner** role on at least one product
- [Claude Desktop](https://claude.ai/download) installed (Mac or Windows)
- 5 minutes

---

## Setup (3 steps)

### 1. Edit your Claude Desktop config

Open the config file:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

If the file doesn't exist, create it. Add this block:

```json
{
  "mcpServers": {
    "feature-iq": {
      "url": "https://feature-iq-mcp.onrender.com/mcp"
    }
  }
}
```

If you already have other MCP servers configured, add `feature-iq` as a sibling key inside `mcpServers`.

### 2. Restart Claude Desktop

Fully quit and reopen.

### 3. Sign in when prompted

The first time you use a Feature-IQ tool, Claude Desktop will open a browser window asking you to sign in to Feature-IQ. Use the credentials you were given. Approve access. The browser will redirect back to Claude Desktop and the connection will be live.

You only do this once per device. Tokens are managed by Claude Desktop.

---

## Try these prompts

Once connected, try these — they each showcase a different part of the system. Replace `Concur Invoice` with whatever product is yours.

### 1. Get the lay of the land
> *"What products do I have in Feature-IQ? For my main one, give me a summary of the job map and the competitors I'm tracking."*

This calls `product_list`, `product_get_jobs`, and `ci_get_competitor_list`. Claude assembles the picture in one go.

### 2. Find the strategic gaps
> *"Look at my latest synthesis report for Concur Invoice. What are the top 3 opportunities I should invest in this quarter, and which jobs do they serve?"*

Calls `synthesis_get_unified_report` and `synthesis_get_investment_recommendations`. Claude reasons over the prioritized opportunities and explains the *why*.

### 3. Compare yourself to a specific competitor
> *"Pull the latest functional audit for Coupa. What advantages do they have over us, and what are our gaps? Which jobs are we losing on?"*

Calls `ci_get_competitor_report` and walks the `job_assessments`. Claude turns the structured data into a strategic narrative.

### 4. Explore the voter pulse
> *"What are the top 10 voted ideas right now? Group them by job and tell me where there's energy that we're not addressing in the roadmap."*

Calls `ideas_get_top_voted` and `ideas_get_by_category`. Combines voting data with job linkage from triage.

### 5. Run a fresh competitor audit
> *"There's a new player I'm worried about — Stampli. Add them as a competitor and run a full functional audit."*

Calls `ci_add_competitor` then `ci_run_competitor_audit`. The audit runs in the background (3-4 minutes); Claude will tell you when it kicks off.

### 6. Generate a Board-ready brief
> *"Write me a 1-page competitive brief for the Q3 board meeting. Use the latest synthesis report and the top voter ideas. Focus on jobs where we're behind."*

Pulls from synthesis, ideas, and the job map. This is the killer use case — Claude composes a finished artifact from grounded data.

### 7. Ask whatever
> *"Summarize all customer feedback themes from the last support data import and tell me which competitor reports back them up."*

Pulls internal feedback themes (`internal_*` tools) and cross-references competitor evidence. Mix and match — Claude figures out the right tools.

---

## What's available

The 78 tools are organized into ten domains. Claude knows them all — you don't need to memorize them — but here's the shape:

| Domain | What it can do |
|---|---|
| **Products** | List/create products, run product analysis, manage settings, scoring weights |
| **Competitive Intelligence** | Add competitors, discover competitors, run audits, view reports, alerts |
| **Synthesis** | Configure and run unified synthesis, get reports, investment recommendations, job scorecards |
| **Ideas** | Search, list, top-voted, vote, comment, respond, create from gaps |
| **Job Map** | List jobs, get job clusters, evaluate evidence against jobs |
| **Internal Feedback** | Import status, theme extraction, feedback queries |
| **PM Review** | List queue, update rank, manage triage decisions |
| **Evidence** | Add, search, list factbase entries |
| **Monitoring** | Get alerts, scheduled audit configs |
| **Composite** | Cross-domain queries (e.g., evaluate a feature against all evidence) |

Permission scoping applies — you can only use tools against products you have access to.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Tools don't appear in Claude Desktop | Fully quit and reopen Claude Desktop (not just close the window). Check the config file is valid JSON. |
| Sign-in browser window doesn't open | Trigger any tool use in a chat (e.g., ask Claude to list your products). The OAuth flow only kicks off on first tool use. |
| Sign-in succeeds but tools fail | Reconnect: remove the `feature-iq` block from your config, save, restart Claude Desktop, paste it back, restart again. This forces a fresh OAuth handshake. |
| `Permission denied` on a product | You don't have a `ProductPermission` on that product — ask the owner |
| Tools work but data is empty | You may be querying the demo product without read access, or your own product has no data yet — start a product analysis first |
| Audit "kicks off" but never completes | The Celery worker may be down (operational issue, not yours) — contact the admin |

---

## Alternatives to OAuth

OAuth is the recommended path for Claude Desktop. Two other options exist for specific cases:

**API key (for headless / CLI / scripted use)** — generate a key in the Feature-IQ web UI under Profile → API Keys. Use it as a `Authorization: Bearer fiq_...` header. Same MCP server, same tools — just a different auth mechanism. Useful if you're integrating Feature-IQ into a script or non-interactive client.

**Local stdio (for developers running Feature-IQ locally)** — see [backend/scripts/README.md](../../backend/scripts/README.md) for the stdio config. Uses the local Python install directly, no auth.
