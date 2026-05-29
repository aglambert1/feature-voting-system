# Welcome to Feature-IQ

You've been given access to Feature-IQ. This page tells you what to try first and where the value is.

> If you're a developer setting up a local environment, this isn't the right doc — see [Quickstart](quickstart.md) instead.

---

## What Feature-IQ does in one sentence

It runs automated competitive analysis against your customers' Jobs-to-be-Done, then synthesizes the results with your customer feedback into prioritized opportunities that flow into a voting board.

You bring: a product description and a list of competitors.

You get: a populated job map, audited competitor reports, a synthesis report, and a triaged feature voting board — all reasoning over the same JTBD spine.

---

## What you can do today

Your account has two scopes:

- **Read access to the demo product** (Concur Invoice — an AP automation platform). Browse it, vote on its ideas, ask Claude Desktop questions about it. You can't run audits or change settings, but you can feel the full surface.
- **Full ownership of any products you create.** Create your own product, add your competitors, run the analysis pipelines, invite voters.

---

## Try this in the next 15 minutes

### 1. Browse the demo product (3 min)

Go to **Competitive Intelligence**. Open **Concur Invoice**.

- Look at the **Job Map** — the analytical spine. Note the mix of functional, emotional, and social jobs
- Open one of the **Competitor Reports** — read the `job_assessments`. Notice there are no separate "gaps" and "advantages" sections; positions are grouped by job
- Visit the **Synthesis Hub** — see the prioritized opportunities, their tier, and which ones became Ideas

### 2. Connect Claude Desktop (5 min)

This is where Feature-IQ gets fun. Follow the [Claude Desktop setup guide](claude-desktop.md). Five minutes from key generation to working tools.

Then ask Claude things like:
- *"What are the top 3 opportunities in my latest synthesis report, and which jobs do they serve?"*
- *"Compare my competitor Coupa to me — what advantages do they have?"*
- *"What ideas are most popular right now, grouped by job?"*

This is the showcase use case. Most prospect feedback says "wait, I can just *ask*?" — yes, you can.

### 3. Create your own product (5 min)

Click **Create Product**. Fill in:
- Name
- A real description (this drives quality of the auto-generated job map)
- Category

Then run **Product Analysis** (~30s) and **Generate Job Map** (~30s). Edit the job map until it looks right — *this matters*. Bad job statements produce bad audits.

### 4. Add a competitor and run an audit (4 min wall time)

On your product, add one competitor by name + URL. Run the audit. It takes ~3 minutes (Stage 1 web research + Stage 2 structured assessment).

When it lands, open the report — you'll see your first competitor's positions across your job map.

---

## What's worth knowing

- **The job map is load-bearing.** If you create a product and skip the job map, every downstream artifact (audits, synthesis, idea linkage) will be weaker. Spend the time to get it right.
- **The system is async.** Audits, synthesis, and triage all run on a background queue. Watch the progress badges — clicking a button doesn't mean the work is done.
- **Triage runs on every idea.** When you submit an idea, the triage agent classifies it, links it to the closest job, and surfaces existing competitive coverage. This isn't decoration — it's how the loop closes.
- **Costs are real.** Each audit is ~$0.50–$1.00 in API costs (Anthropic + Voyage + Brave). Synthesis is ~$0.30. Don't run them in a loop unless you mean to.

---

## Who can do what

- **Voters** — vote, comment, submit ideas. That's it. Cannot see the analytical content.
- **Product Owners** (you) — full control of your own products. Can invite voters via product invite codes (in Product Settings).
- **Admins** — system-wide; user management, cost tracking, queue inspection.

To invite voters to your product, go to your product's settings and generate an invite code. They register with the code, get auto-permissioned to your product, and can submit + vote.

---

## When you have questions

- **How does X work?** → [Architecture](architecture.md) explains the JTBD model and major components
- **What features exist?** → [Tour](tour.md) is a feature inventory by role
- **How do I connect Claude Desktop?** → [Claude Desktop setup](claude-desktop.md)
- **Something's broken or surprising** → contact the operator who gave you access

---

## What this isn't

- **A roadmapping tool.** Feature-IQ informs roadmap decisions; it doesn't replace Jira / Productboard / Aha. Export the synthesis report and bring it into your existing planning process.
- **A customer-facing portal.** Voters are internal stakeholders. There's no public idea board.
- **A live CRM integration.** Internal feedback comes in via bulk import, not real-time sync.

These are deliberate scope choices.

---

## What we're betting on

Most "feature voting" tools collect the *what* (features customers ask for) but lose the *why* (the job they're trying to do). Most "competitive intelligence" tools track *what* competitors are doing but don't connect it to your product strategy. Feature-IQ assumes both signals are weaker without the JTBD spine to hang them on, and bets that AI agents can do the JTBD-grounded work cheaply enough to be worth it.

Whether that bet pays off depends on whether the spine actually changes how you make decisions. We'd love to hear what you find.
