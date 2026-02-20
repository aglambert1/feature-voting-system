# Go-to-Market Strategy

## Context
- **Product:** Feature voting system with AI-powered competitive analysis
- **Target user:** Product managers (startups/growth-stage)
- **Constraints:** Side project, minimize investment, cover LLM costs eventually
- **Current stage:** Pre-demo

---

## Phase Overview

| Phase | Duration | Users | Revenue | Primary Goal |
|-------|----------|-------|---------|--------------|
| 0. Instrument | 1 week | 0 | $0 | Understand unit economics |
| 1. Friends & Family | 2-4 weeks | 3-5 | $0 | Validate core value prop |
| 2. Private Beta | 1-3 months | 10-25 | $0 | Find product-market fit signals |
| 3. Paid Beta | 2-3 months | 25-100 | Covers costs | Validate willingness to pay |
| 4. Public Launch | Ongoing | 100+ | Profit | Scale what works |

---

## Phase 0: Instrument Costs (Do This First)

Before demos, add basic cost tracking so you know your unit economics.

**Why:** You can't price correctly without knowing costs. Some users may cost $2/month, others $50. You need visibility.

**Minimum instrumentation:**
```python
# In llm_service.py - track tokens per request
import logging

cost_logger = logging.getLogger("cost_tracking")

async def call_claude(prompt, ...):
    response = await client.messages.create(...)

    # Log cost data
    cost_logger.info({
        "user_id": current_user.id,
        "operation": "product_analysis",  # or "competitor_discovery", etc.
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "model": "claude-sonnet-4-20250514",
        "estimated_cost_usd": calculate_cost(response.usage)
    })

    return response
```

**Track by operation type:**
- Idea triage/structuring
- Product analysis
- Competitor discovery
- Competitor feature extraction
- Opportunity synthesis

**Expected insight:** "A full competitive analysis costs $X. Average user runs Y analyses/month = $Z/user/month."

---

## Phase 1: Friends & Family (Weeks 1-4)

**Goal:** Validate the core value proposition with 3-5 friendly PMs.

**Who to recruit:**
- PM friends at startups (most likely to feel the pain)
- Former colleagues
- People from PM communities you're part of

**What to learn:**
1. Which features do they actually use?
2. What's confusing or broken?
3. Would they pay for this? How much?
4. What's missing that would make it essential?

**How to run:**
- Live demo + walkthrough (30-60 min)
- Give them access to play with their own product/competitors
- Follow up in 1 week: "Did you use it? Why/why not?"

**Success criteria:**
- At least 2/5 users return unprompted to use it again
- You hear "I wish I had this at my last job" or similar
- You understand which feature is the "hook"

**Investment:** Your time only. Run on local or minimal Render deployment ($20/month).

---

## Phase 2: Private Beta (Months 1-3)

**Goal:** Find product-market fit signals with 10-25 users.

**Recruitment channels (low effort):**
- LinkedIn posts to your network
- PM Slack communities (Lenny's, Product School, Mind the Product)
- Indie Hackers
- Word of mouth from Phase 1

**Qualification criteria:**
- Currently a PM at a B2B SaaS company
- Has at least 2-3 known competitors
- Willing to give feedback (15-min call monthly)

**What to learn:**
1. Retention: Do users come back weekly?
2. Activation: What % complete a full competitive analysis?
3. Value: What do they do with the output? (Roadmap decisions, exec presentations, etc.)
4. Costs: What does an active user cost you?

**Operational setup:**
- Render deployment (~$50-100/month with more usage)
- Simple onboarding (Loom video + docs)
- Feedback channel (Slack, Discord, or just email)
- Weekly usage review (who's active, who churned, why)

**Success criteria:**
- 40%+ weekly active rate among onboarded users
- Net Promoter Score > 30 (or qualitative equivalent)
- You can articulate the "aha moment" clearly
- You know your cost per active user

---

## Phase 3: Paid Beta (Months 3-6)

**Goal:** Validate willingness to pay. Cover your costs.

**Transition approach:**
- Grandfather Phase 2 users with extended free access (loyalty)
- New users join paid beta
- Position as "early adopter pricing" (50% off eventual price)

**Pricing options (see Revenue Models below):**
- Start with usage-based to match your costs
- Or flat rate if you've validated predictable usage patterns

**What to learn:**
1. Conversion: What % of trials convert to paid?
2. Price sensitivity: Do people push back? Ask for discounts?
3. Churn: Why do paying users leave?
4. Expansion: Do users want more (seats, analyses, features)?

**Success criteria:**
- 20%+ trial-to-paid conversion
- Revenue covers infrastructure + LLM costs
- <10% monthly churn
- At least one user asks to pay annually

---

## Phase 4: Public Launch

Only enter this phase when:
- You have predictable unit economics
- Conversion and retention are validated
- You have capacity to handle support load

This is beyond "side project" scope — revisit when Phase 3 succeeds.

---

## Revenue Models

### Model A: Usage-Based (Recommended for Start)

**How it works:** Charge per analysis or per "AI credit"

**Example pricing:**
| Action | Credits | Approx. Cost to You |
|--------|---------|---------------------|
| Analyze 1 competitor | 1 credit | ~$0.50-2.00 |
| Full market analysis (5 competitors) | 5 credits | ~$3-10 |
| Opportunity synthesis | 2 credits | ~$1-3 |

**Packages:**
- Starter: 10 credits/month — $29/month
- Growth: 30 credits/month — $79/month
- Pro: 100 credits/month — $199/month

**Pros:**
- Directly ties revenue to your costs
- Low barrier to entry (buy small package)
- Heavy users pay more (fair)

**Cons:**
- Users may hoard credits, reducing engagement
- Harder to predict revenue
- Requires metering infrastructure

**Best for:** Unknown usage patterns, cost-conscious early stage

---

### Model B: Flat Rate Per Seat

**How it works:** Monthly fee per user

**Example pricing:**
- $49/user/month (early adopter)
- $79/user/month (standard)

**Pros:**
- Predictable revenue
- Simple to understand
- No metering needed

**Cons:**
- Risk: Heavy users cost you more than they pay
- May need usage caps as guardrails

**Guardrails to add:**
- "Up to 10 competitor analyses/month" in lower tier
- "Unlimited" in higher tier (accept some subsidy)

**Best for:** After you understand usage patterns

---

### Model C: Freemium + Premium Features

**How it works:** Core features free, advanced features paid

**Free tier:**
- Idea submission & voting (low cost to you)
- 1 product, 2 competitor analyses/month
- Basic gap analysis

**Paid tier ($49-99/month):**
- Unlimited competitors
- Full market analysis
- Opportunity synthesis
- API access
- Team features

**Pros:**
- Low friction for adoption
- Free tier = marketing
- Upsell path clear

**Cons:**
- Free users cost you money (LLM costs)
- Need volume to make unit economics work
- Risk of "free forever" users

**Mitigation:** Make free tier genuinely limited (enough to see value, not enough to fully use).

**Best for:** When you want growth over immediate revenue

---

### Model D: Bring Your Own Key (BYOK)

**How it works:** Users provide their own Anthropic API key

**Your pricing:** $19-29/month for platform access (no LLM costs to you)

**Pros:**
- Zero LLM cost risk for you
- Can price purely for platform value
- Appeals to cost-conscious / privacy-focused users

**Cons:**
- Friction: Users need Anthropic account
- Support burden: "Why is my API key not working?"
- Limits market to technically sophisticated users

**Hybrid approach:** Offer both:
- BYOK: $29/month (use your key)
- Managed: $79/month (we handle it, includes X credits)

**Best for:** Technical users, enterprises with existing API contracts

---

## Recommended Path

### Start with: Usage-Based (Model A)

**Why:**
- Matches your cost structure directly
- Low commitment for early users
- You learn usage patterns

**Initial pricing (Phase 3):**
- $29/month for 10 credits (starter)
- $79/month for 30 credits (growth)
- Additional credits: $3 each

**Messaging:** "Pay for what you use. Most PMs need 5-10 competitor analyses/month."

### Evolve to: Flat Rate (Model B)

Once you know:
- Average user consumes X credits/month
- 80th percentile user consumes Y credits/month

Set flat rate price at Y + margin, with soft caps.

---

## Cost Management Tactics

### Reduce LLM costs:
1. **Cache common queries** — Same competitor analyzed by multiple users? Cache the features.
2. **Use smaller models for simple tasks** — Haiku for classification, Sonnet for analysis.
3. **Batch operations** — Combine multiple small prompts into one.
4. **Prompt optimization** — Shorter prompts, fewer examples needed.

### Protect against abuse:
1. **Rate limits** — Max 5 analyses per day on free/starter tier.
2. **Soft caps with warnings** — "You've used 80% of your credits."
3. **Hard caps** — Block at limit, prompt upgrade.
4. **Anomaly detection** — Flag users with unusual patterns.

---

## Metrics to Track

### Phase 1-2 (Validation):
- Activation rate: % who complete first analysis
- Retention: Weekly active users / total users
- Feature usage: Which features used most?
- Qualitative NPS: Would you recommend this?

### Phase 3+ (Revenue):
- Trial-to-paid conversion rate
- Monthly recurring revenue (MRR)
- Average revenue per user (ARPU)
- LLM cost per user (CPU — your "cost of goods sold")
- Gross margin: (ARPU - CPU) / ARPU
- Monthly churn rate

**Target gross margin:** 60-70% (typical for SaaS with compute costs)

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| LLM costs exceed revenue | Usage-based pricing; hard caps; BYOK option |
| No one uses it | Kill in Phase 1-2 before real investment |
| Heavy user subsidized by light users | Usage-based pricing; tier structure |
| Can't support users as side project | Self-serve docs; async support only; set expectations |
| Competitor launches similar tool | Focus on niche (PMs at startups); move fast |
| API costs spike (Anthropic price change) | Track costs closely; pricing flexibility in ToS |

---

## Action Items

### This week:
1. [ ] Add cost instrumentation to LLM service
2. [ ] Identify 5 PM friends for Phase 1 demos
3. [ ] Create simple demo script / Loom video

### Before Phase 2:
1. [ ] Deploy to Render (or similar)
2. [ ] Set up basic analytics (who's using what)
3. [ ] Write onboarding docs
4. [ ] Create feedback channel

### Before Phase 3:
1. [ ] Implement usage metering
2. [ ] Integrate payment (Stripe)
3. [ ] Build billing UI (usage dashboard, upgrade prompts)
4. [ ] Set up terms of service

---

## Key Decisions to Make

1. **When to charge?** Recommend: After 20+ beta users, 2+ months of usage data.

2. **What to charge?** Start usage-based at $29-79/month range. Adjust based on data.

3. **Free tier or not?** Recommend: Yes, but very limited (drives awareness, low cost if capped).

4. **When to quit?** If Phase 2 shows <20% weekly retention and no strong qualitative signal, reconsider.
