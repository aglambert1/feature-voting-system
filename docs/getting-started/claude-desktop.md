# Connect Feature-IQ to Claude Desktop

Feature-IQ exposes 79 MCP tools. Connect Claude Desktop to your Feature-IQ account and you can run competitor audits, query ideas, generate synthesis, and explore your job map — all in plain English, with Claude's reasoning on top of Feature-IQ's data.

This is the most powerful way to use Feature-IQ. No coding required.

---

## What you'll need

- A Feature-IQ account with **Product Owner** role on at least one product
- [Claude Desktop](https://claude.ai/download) installed (Mac or Windows)
- 5 minutes

---

## Setup (3 steps)

> **Note**: this guide uses an API-key setup. The MCP server also supports OAuth, which is a smoother experience (no secret to copy-paste, browser-based login). OAuth instructions will replace this section after the path is verified end-to-end against Claude Desktop on prod. If you'd prefer to try OAuth now, contact the operator for the experimental config.

### 1. Generate an API key

1. Sign in at [https://feature-iq.onrender.com](https://feature-iq.onrender.com)
2. Click your profile (top-right) → **API Keys**
3. Click **Generate New Key**, give it a name like "Claude Desktop"
4. **Copy the key immediately** — it starts with `fiq_` and is only shown once

> If you don't see the **API Keys** tab, your account doesn't have Product Owner role. Ask your admin to update it.

### 2. Edit your Claude Desktop config

Open the config file:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

If the file doesn't exist, create it. Add this block (replace `fiq_your_key_here` with the key you just copied):

```json
{
  "mcpServers": {
    "feature-iq": {
      "url": "https://feature-iq-mcp.onrender.com/mcp",
      "headers": {
        "Authorization": "Bearer fiq_your_key_here"
      }
    }
  }
}
```

If you already have other MCP servers configured, add `feature-iq` as a sibling key inside `mcpServers`.

### 3. Restart Claude Desktop

Fully quit and reopen. You should see Feature-IQ tools available in the new chat window. Claude will use them automatically when relevant.

---

## Try these prompts

Once connected, try these — they each showcase a different part of the system. Replace `Concur Invoice` with whatever product is yours.

### 1. Get the lay of the land
> *"What products do I have in Feature-IQ? For my main one, give me a summary of the job map and the competitors I'm tracking."*

This calls `product_list`, `jobs_list`, and `ci_get_competitor_list`. Claude assembles the picture in one go.

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

The 79 tools are organized into ten domains. Claude knows them all — you don't need to memorize them — but here's the shape:

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
| Tools don't appear in Claude Desktop | Fully quit and reopen Claude Desktop (not just close window). Check the config file is valid JSON. |
| `Authentication failed` errors | Your API key is wrong, expired, or you didn't include `Bearer ` (with the space) before it |
| `Permission denied` on a product | You don't have a `ProductPermission` on that product — ask the owner |
| Tools work but data is empty | You may be querying the demo product without read access, or your own product has no data yet — start a product analysis first |
| Audit "kicks off" but never completes | The Celery worker may be down (operational issue, not yours) — contact the admin |

---

## Local development alternative

If you're a developer running Feature-IQ locally and don't want to go through the OAuth flow, you can run the MCP server via stdio. See [backend/scripts/README.md](../../backend/scripts/README.md) for the local config.

For everyone else, the HTTP setup above is the way.
