# Running Feature-IQ on Itself — Seed Draft

**Status: draft, not decided.** This is input for creating a "Feature-IQ" product inside Feature-IQ — the description and candidate job map you'd feed into `product_create` / `product_extract_job_map`, and the shape you'd want before running competitor discovery and inviting internal idea submission.

It deliberately does **not** name competitors. Competitor discovery (`CompetitorResearcherAgent` / `ci_run_discovery`) is supposed to find them from the problem, customer, and capabilities described below — that's the same process every other product in the system goes through, and it's a better test of the pipeline than hand-feeding it a list. `COMPETITIVE_POSITIONING.md` at the repo root already has a hand-researched competitor list (Aha!, Productboard, Crayon, Canny, Jira Product Discovery, ProductPlan, Linear, Asana) if you want a sanity check against what discovery surfaces — but treat that as an answer key, not an input.

**The bigger open question this doc surfaces rather than resolves: the ICP isn't settled.** `COMPETITIVE_POSITIONING.md` proposes two different tracks (startup PM teams vs. enterprise PLG individual PMs) without picking one, and that choice hasn't been made since. The job map below is written from the startup-team angle since that's the lower-friction motion described in that doc, but this is exactly the kind of call that should get a real strategy pass, not get quietly baked into a seed document. Flagging it here so it isn't decided by default.

---

## Product description (for `product_create`)

**Name:** Feature-IQ

**Category:** Competitive Product Intelligence Software (draft — category choice affects how discovery frames "competitors"; could also be scoped narrower as "AI Competitive Intelligence for Product Teams" or broader as "Product Management Software")

**Description (draft):**

> Feature-IQ helps product teams understand how well their product serves customers' real jobs-to-be-done — and how that compares to competitors — without the manual work of maintaining spreadsheets, running one-off competitor research, or losing track of why customer feedback matters strategically.
>
> Product teams define the jobs their customers are trying to accomplish (functional, emotional, and social). Feature-IQ then runs automated, AI-driven competitor research against that job model, imports internal signals (CRM win/loss notes, support tickets), and collects feature ideas from internal stakeholders — synthesizing all of it into prioritized opportunities, each grounded in a specific customer job rather than a raw feature request. The result replaces ad hoc competitive spreadsheets and disconnected feedback tools with one continuously-updated, AI-maintained fact base that a PM can query directly (including via natural language through Claude).
>
> Unlike general-purpose roadmapping tools, Feature-IQ doesn't try to own sprint planning or execution — it focuses specifically on the "what should we build and why" question, using jobs-to-be-done as the organizing structure and automated research/synthesis as the mechanism, so the answer stays current without someone manually refreshing it.

**Who it's for (draft — see ICP note above):**

> Product managers and product owners at B2B SaaS companies, roughly seed-to-Series-B stage, who don't currently have a systematic way to track competitors or connect customer feedback to product strategy — typically because they're too small for enterprise competitive-intelligence tools and are stitching the job together with spreadsheets and manual research today.

---

## Candidate job map (for `product_extract_job_map` / manual review)

Draft only — this is the kind of thing that should be edited by whoever owns the product, per the standard guidance in [welcome.md](welcome.md): *"the job map is load-bearing... spend the time to get it right."* Treat these as a first pass, not final statements.

### Functional jobs

- **j1** — *When I'm preparing for a board meeting or planning cycle, I want to quickly produce a credible view of how my product compares to competitors, so I can answer "how do we stack up" without a week of manual research.* (importance: critical)
- **j2** — *When customer feedback and support tickets pile up, I want them automatically connected to the underlying customer need, so I can tell which requests actually matter strategically vs. which are noise.* (importance: high)
- **j3** — *When I'm deciding what to build next, I want to see competitor gaps and customer demand in the same view, so I can prioritize based on real signal instead of gut feel or whoever asked loudest.* (importance: critical)
- **j4** — *When a competitor ships something new, I want to find out promptly rather than by accident, so I'm not caught flat-footed in a customer or exec conversation.* (importance: high)
- **j5** — *When I collect feature ideas from my team or customers, I want duplicates and already-shipped requests filtered automatically, so triage doesn't eat my week.* (importance: medium)

### Emotional jobs

- **je1** — *When someone asks me "why aren't we building X," I want to feel confident I have a defensible, evidence-based answer, so I don't feel like I'm guessing in front of stakeholders.* (importance: high)
- **je2** — *When I'm reviewing my competitive position, I want to feel like I'm seeing the current state rather than a stale snapshot, so I trust the analysis enough to act on it.* (importance: medium)

### Social jobs

- **js1** — *When I present roadmap rationale to leadership, I want to look rigorous and data-driven, so my recommendations carry more weight than a colleague's who's still working from spreadsheets.* (importance: medium)

---

## What happens after this doc

Standard flow from here, same as any other product (see [quickstart.md](quickstart.md) and [demo-recipe.md](demo-recipe.md)):

1. `product_create` with the description above (after review/edit)
2. `product_run_analysis` — let `ProductAnalyzerAgent` extract features/positioning from the description as a sanity check against what's written here
3. `product_extract_job_map`, then manually edit against the draft above
4. `ci_run_discovery` — let `CompetitorResearcherAgent` find competitors from the product description and job map. Compare results against `COMPETITIVE_POSITIONING.md`'s hand-researched list as a discovery-quality check, not as ground truth to force-match
5. Run audits on the competitors that surface, then unified synthesis
6. Open idea submission to internal stakeholders (AG, and anyone else with product access) to seed the triage/voting loop with real dogfooding feedback about Feature-IQ itself

## Known limitation

Running Feature-IQ on itself means its own competitive intelligence and idea triage pipeline is being asked to analyze a category (PM/competitive-intel tooling) that's likely well-represented in the LLM's training data, which could make discovery and audits easier than for an obscure B2B product — worth keeping in mind when judging how representative this dogfood exercise is of a typical customer's experience.
