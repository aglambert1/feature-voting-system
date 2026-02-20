# V2 Competitive Analysis UX Mockups

## Overview

This document provides UX mockups for the V2 Competitive Analysis system. The mockups follow existing UI patterns from the product dashboard and Intelligence Hub to ensure visual consistency.

---

## Tab Structure Changes

**Current Tabs:**
1. Overview
2. Competitors
3. Features
4. Insights (deprecated)
5. Settings

**V2 Tabs:**
1. Overview
2. Competitors
3. Features
4. **Competitor Reports** (new - replaces Insights)
5. **Landscape Analysis** (new)
6. Settings

---

## 1. Settings Tab Updates

**Architecture:** Settings are per-agent, launched from agent cards on Product Dashboard.

- **Competitive Analysis Agent settings:** Only deep_analysis_mode/schedule
- **Market Discovery Agent settings:** competitor_discovery_mode/schedule, alerts (separate page)
- **Product Analysis:** Not an agent - triggered on product info upload

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ Competitive Analysis Agent Settings                              [Reset] [Save] │
│ Configure how the competitive analysis agent operates                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│ ┌─ Competitive Analysis ──────────────────────────────────────────────────────┐ │
│ │                                                                             │ │
│ │  Runs functional audits for each competitor, then synthesizes landscape     │ │
│ │  opportunities across all competitors.                                      │ │
│ │                                                                             │ │
│ │  Mode: [Scheduled ▼]       Schedule: [Weekly ▼]                             │ │
│ │                                                                             │ │
│ │  Last run: Jan 13, 2026 at 2:00 AM                                          │ │
│ └─────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Removed from V2:**
- Product Analysis section (not an agent)
- Competitor Discovery section (moved to Market Discovery Agent)
- Strategic Analysis Components section (pricing, positioning, etc. toggles)
- Competitive Intensity section (V2 uses LLM-based priority scoring)
- Agent Status toggle (redundant - if mode=manual, scheduled activities don't occur)

---

## 2. Competitor Reports Tab (New)

Shows individual functional audit reports for each competitor.

### 2a. Reports List View (Default)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ Competitor Reports                                                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  Functional audits compare each competitor's features against your product.    │
│                                                                                 │
│  Manage competitors in Market Discovery →                                       │
│                                                                                 │
│  ┌─ Competitor A ─────────────────────────────────────────────────────────────┐ │
│  │                                                                            │ │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐         │ │
│  │  │ Features Compared│  │ Gaps Identified  │  │ Last Updated     │         │ │
│  │  │       24         │  │       8          │  │  Jan 13, 2026    │         │ │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘         │ │
│  │                                                                            │ │
│  │                                [View Report] [Run Audit] [Export .md ↓]    │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ┌─ Competitor B ─────────────────────────────────────────────────────────────┐ │
│  │                                                                            │ │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐         │ │
│  │  │ Features Compared│  │ Gaps Identified  │  │ Last Updated     │         │ │
│  │  │       18         │  │       5          │  │  Jan 13, 2026    │         │ │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘         │ │
│  │                                                                            │ │
│  │                                [View Report] [Run Audit] [Export .md ↓]    │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ┌─ Competitor C ─────────────────────────────────────────────────────────────┐ │
│  │                                                                            │ │
│  │  ░░░ No report available ░░░                                               │ │
│  │                                                                            │ │
│  │  Run competitive analysis to generate a report for this competitor.        │ │
│  │                                                            [Run Audit]     │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │  ℹ️  Full competitive analysis (all competitors + landscape synthesis)     │ │
│  │      is triggered from the Competitive Analysis Agent card on the          │ │
│  │      Product Dashboard.                                                    │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Key changes from original:**
- Added "Manage competitors in Market Discovery →" link
- Removed "Run Analysis for All Competitors" button (triggered from Product Dashboard)
- Added individual "Run Audit" button per competitor card
- Info box explains where to trigger full analysis

### 2b. Report Detail View (Expanded/Modal)

Clicking "View Report" opens a detailed view (can be modal or inline expand):

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ Functional Audit: Competitor A                             [Export .md ↓] [✕]   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  Generated: Jan 13, 2026 at 2:15 AM • Version 3                                 │
│                                                                                 │
│ ─────────────────────────────────────────────────────────────────────────────── │
│                                                                                 │
│  ## Competitor Context                                                          │
│                                                                                 │
│  **Primary Focus:** Project management for agile teams                          │
│  **Target Market:** Mid-market SaaS companies (50-500 employees)                │
│  **Key Differentiator:** AI-powered sprint planning                             │
│                                                                                 │
│ ─────────────────────────────────────────────────────────────────────────────── │
│                                                                                 │
│  ## Feature Comparison                                                          │
│                                                                                 │
│  ┌─────────────────────┬─────────────┬─────────────┬────────────────────────┐   │
│  │ Feature             │ Your Product│ Competitor A│ Notes                  │   │
│  ├─────────────────────┼─────────────┼─────────────┼────────────────────────┤   │
│  │ Sprint Planning     │ ✓ Basic     │ ✓ Advanced  │ AI suggestions         │   │
│  │ Burndown Charts     │ ✓           │ ✓           │ Similar                │   │
│  │ Custom Workflows    │ ✓           │ ✓           │ Your more flexible     │   │
│  │ Time Tracking       │ ✗           │ ✓           │ Gap identified         │   │
│  │ Resource Management │ ✗           │ ✓           │ Gap identified         │   │
│  │ API Access          │ ✓           │ ✓ Limited   │ Your advantage         │   │
│  │ Slack Integration   │ ✓           │ ✓           │ Similar                │   │
│  │ Jira Import         │ ✗           │ ✓           │ Gap identified         │   │
│  └─────────────────────┴─────────────┴─────────────┴────────────────────────┘   │
│                                                                                 │
│ ─────────────────────────────────────────────────────────────────────────────── │
│                                                                                 │
│  ## Gap Analysis                                                                │
│                                                                                 │
│  Select gaps to create ideas for voting or export to another system.           │
│                                                                                 │
│  [Select All]  2 of 3 gaps selected                                             │
│                                                                                 │
│  ┌─ ☑ Time Tracking ─────────────────────────────────────────────────────────┐ │
│  │                                                                            │ │
│  │ **User Problem:** Teams need to track actual vs estimated time for better  │ │
│  │ sprint planning and client billing.                                        │ │
│  │                                                                            │ │
│  │ **Evidence:** "The time tracking integration saved us hours every week"    │ │
│  │ - G2 Review, 4.5★                                                          │ │
│  │                                                                            │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ┌─ ☑ Resource Management ─────────────────────── [Idea submitted for voting] ┐ │
│  │                                                                            │ │
│  │ **User Problem:** Managers need visibility into team capacity and workload │ │
│  │ distribution across projects.                                              │ │
│  │                                                                            │ │
│  │ **Evidence:** "Finally a tool that shows who's overloaded" - Capterra      │ │
│  │                                                                            │ │
│  │                                                            ✓ Idea created  │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ┌─ ☐ Jira Import ───────────────────────────────────────────────────────────┐ │
│  │                                                                            │ │
│  │ **User Problem:** Teams migrating from Jira need to bring historical data. │ │
│  │                                                                            │ │
│  │ **Evidence:** "Jira import saved us weeks of manual work" - G2 Review      │ │
│  │                                                                            │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │  2 gaps selected                                                         │   │
│  │                                                                          │   │
│  │  [Create Ideas for Voting]    [Export Selected as JSON]                  │   │
│  │                                                                          │   │
│  │  Note: 1 selected gap already has an idea - it will be skipped for       │   │
│  │  idea creation but included in export.                                   │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│ ─────────────────────────────────────────────────────────────────────────────── │
│                                                                                 │
│  ## Technical Constraints                                                       │
│                                                                                 │
│  - Time tracking would require database schema changes for time entries        │
│  - Resource management depends on having user capacity data                    │
│  - Jira import would need OAuth integration with Atlassian                     │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Key changes from original:**
- Removed "Implementation Complexity" (no reliable data source)
- Added "Evidence" field with user review quotes and sentiment
- Added checkbox selection on each gap (consistent with Landscape Analysis)
- Added "Select All" option with selection count
- Combined action box with both "Create Ideas for Voting" and "Export Selected as JSON"
- Export only exports selected gaps (not all)
- Note warns that already-submitted gaps will be skipped for idea creation but included in export
- Shows "Idea submitted for voting" badge when idea already created

---

## 3. Landscape Analysis Tab (New)

Shows synthesized analysis across all competitors with actionable opportunities.

### 3a. Overview Section

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ Landscape Analysis                                                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  Cross-competitor synthesis identifying feature opportunities and market gaps.  │
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │  Based on: 5 competitor reports • Generated: Jan 13, 2026 at 2:30 AM     │   │
│  │                                                     [Export Report .md ↓] │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌────────────────────┐  ┌────────────────────┐                                │
│  │  Feature Clusters  │  │  Opportunities     │                                │
│  │        12          │  │        8           │                                │
│  │  Identified        │  │  Found             │                                │
│  └────────────────────┘  └────────────────────┘                                │
│                                                                                 │
│ ─────────────────────────────────────────────────────────────────────────────── │
```

### 3b. Feature Opportunities Section (Main Focus)

High-impact gaps are combined with feature opportunities and sorted to the top.

```
│                                                                                 │
│  ## Feature Opportunities                                                       │
│                                                                                 │
│  Select opportunities to create ideas for customer voting, or export to        │
│  another system.                                                                │
│                                                                                 │
│  [Select All]  2 of 8 opportunities selected                                    │
│                                                                                 │
│  ┌─ ☑ Time Tracking ─────────────────────────────────── 🔴 HIGH IMPACT ───────┐ │
│  │                                                                            │ │
│  │  ┌─────────────────────────────────────────────────────────────────────┐   │ │
│  │  │ Priority: ████████████░░░░ 85%  │  Market: Table Stakes (4/5 have) │   │ │
│  │  └─────────────────────────────────────────────────────────────────────┘   │ │
│  │  **Why this score:** High prevalence (4/5 competitors) + frequently        │ │
│  │  cited in user reviews as switching reason.                                │ │
│  │                                                                            │ │
│  │  **Summary:** Track actual time spent on tasks and projects                │ │
│  │                                                                            │ │
│  │  **User Value:** Teams can improve estimation accuracy and enable          │ │
│  │  client billing based on actual hours worked.                              │ │
│  │                                                                            │ │
│  │  **User Sentiment:** ⭐ 4.6 avg rating across competitors                  │ │
│  │  "Time tracking is essential" - G2 | "Saves hours weekly" - Capterra       │ │
│  │                                                                            │ │
│  │  **Competitors with feature:** Competitor A, B, C, D                       │ │
│  │                                                                            │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ┌─ ☑ Jira Import/Migration ─────────────────────────── 🟡 HIGH IMPACT ───────┐ │
│  │                                                                            │ │
│  │  ┌─────────────────────────────────────────────────────────────────────┐   │ │
│  │  │ Priority: █████████░░░░░░░ 68%  │  Market: Table Stakes (3/5 have) │   │ │
│  │  └─────────────────────────────────────────────────────────────────────┘   │ │
│  │  **Why this score:** Reduces switching friction, mentioned in "why I       │ │
│  │  switched" posts.                                                          │ │
│  │                                                                            │ │
│  │  **Summary:** One-click import of projects and issues from Jira            │ │
│  │                                                                            │ │
│  │  **User Value:** Teams can switch from Jira without losing historical      │ │
│  │  data or disrupting workflows.                                             │ │
│  │                                                                            │ │
│  │  **User Sentiment:** ⭐ 4.2 avg | "Migration was painless" - G2            │ │
│  │                                                                            │ │
│  │  **Competitors with feature:** Competitor A, Competitor B, Competitor C    │ │
│  │                                                                            │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ┌─ ☐ Resource Capacity Planning ─────────────────────────────────────────────┐ │
│  │                                                                            │ │
│  │  ┌─────────────────────────────────────────────────────────────────────┐   │ │
│  │  │ Priority: ██████████░░░░░░ 72%  │  Market: Differentiator (2/5)    │   │ │
│  │  └─────────────────────────────────────────────────────────────────────┘   │ │
│  │  **Why this score:** Growing demand in enterprise segment, limited         │ │
│  │  competition.                                                              │ │
│  │                                                                            │ │
│  │  **Summary:** Visual capacity planning with workload distribution view     │ │
│  │                                                                            │ │
│  │  **User Value:** Managers can prevent burnout and optimize team            │ │
│  │  allocation across multiple projects.                                      │ │
│  │                                                                            │ │
│  │  **User Sentiment:** ⭐ 4.8 avg | "Game changer for resource planning"     │ │
│  │                                                                            │ │
│  │  **Competitors with feature:** Competitor A, Competitor E                  │ │
│  │                                                                            │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ┌─ AI Sprint Recommendations ─────────────────────── [Idea submitted] ───────┐ │
│  │                                                                            │ │
│  │  ┌─────────────────────────────────────────────────────────────────────┐   │ │
│  │  │ Priority: ████████░░░░░░░░ 65%  │  Market: Emerging (1/5 have)     │   │ │
│  │  └─────────────────────────────────────────────────────────────────────┘   │ │
│  │  **Why this score:** Emerging feature with high user enthusiasm despite    │ │
│  │  low prevalence.                                                           │ │
│  │                                                                            │ │
│  │  **Summary:** AI-powered suggestions for sprint composition and velocity   │ │
│  │                                                                            │ │
│  │  **User Value:** Product managers can make data-driven sprint planning     │ │
│  │  decisions without manual analysis.                                        │ │
│  │                                                                            │ │
│  │  **User Sentiment:** ⭐ 4.9 avg | "The AI suggestions are surprisingly     │ │
│  │  accurate" - G2                                                            │ │
│  │                                                                            │ │
│  │  **Competitors with feature:** Competitor A                                │ │
│  │                                                                            │ │
│  │                                                  ✓ Idea submitted for voting│ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ... (more opportunities)                                                       │
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │  2 opportunities selected                                                │   │
│  │                                                                          │   │
│  │  [Create Ideas for Voting]    [Export Selected as JSON]                  │   │
│  │                                                                          │   │
│  │  Note: Selected items with existing ideas will be skipped for idea       │   │
│  │  creation but included in export.                                        │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Key changes from original:**
- Combined "High-Impact Gaps" with Feature Opportunities (sorted to top with 🔴🟡 badges)
- Added "Select All" option with selection count
- Added "Why this score" explaining priority calculation (Market Gravity)
- Added "User Sentiment" with ratings and quotes from G2/Capterra/Reddit
- Changed button to "Create Ideas for Voting" (clarifies purpose)
- "Idea submitted for voting" badge shows on already-converted opportunities
- Combined action box with both "Create Ideas for Voting" and "Export Selected as JSON"
- Export only exports selected opportunities (not all)
- Note warns that already-submitted items will be skipped for idea creation but included in export
- Removed separate Export Options section (consolidated into action box)

### 3c. Feature Cluster Matrix (Expandable Section)

```
│                                                                                 │
│  ## Feature Cluster Matrix                                        [Collapse ▲] │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │                    │ Your   │Comp A │Comp B │Comp C │Comp D │Comp E │       ││
│  │                    │Product │       │       │       │       │       │       ││
│  ├────────────────────┼────────┼───────┼───────┼───────┼───────┼───────┤       ││
│  │ Sprint Planning    │   ✓    │  ✓+   │   ✓   │   ✓   │   ✓   │   ✗   │ 5/6   ││
│  │ Time Tracking      │   ✗    │   ✓   │   ✓   │   ✓   │   ✓   │   ✗   │ 4/6   ││
│  │ Burndown Charts    │   ✓    │   ✓   │   ✓   │   ✓   │   ✓   │   ✓   │ 6/6   ││
│  │ Custom Workflows   │   ✓    │   ✓   │   ✓   │   ✗   │   ✓   │   ✓   │ 5/6   ││
│  │ Resource Mgmt      │   ✗    │   ✓   │   ✗   │   ✗   │   ✗   │   ✓   │ 2/6   ││
│  │ API Access         │  ✓+    │   ◐   │   ✓   │   ✓   │   ✗   │   ✓   │ 5/6   ││
│  │ Integrations       │   ✓    │   ✓   │  ✓+   │   ✓   │   ✓   │   ✓   │ 6/6   ││
│  │ Jira Import        │   ✗    │   ✓   │   ✓   │   ✓   │   ✗   │   ✗   │ 3/6   ││
│  │ AI Features        │   ✗    │  ✓+   │   ✗   │   ✗   │   ✗   │   ✗   │ 1/6   ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│                                                                                 │
│  Legend: ✓ Has feature • ✓+ Best in class • ◐ Limited • ✗ Missing              │
│                                                                                 │
```

---

## 4. Empty States

### 4a. No Reports Yet

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ Competitor Reports                                                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│                           ┌───────────────────┐                                 │
│                           │       📊          │                                 │
│                           └───────────────────┘                                 │
│                                                                                 │
│                     No Competitor Reports Available                             │
│                                                                                 │
│         Run competitive analysis to generate functional audit reports           │
│         for each of your tracked competitors.                                   │
│                                                                                 │
│                     [Run Competitive Analysis]                                  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 4b. No Landscape Report Yet

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ Landscape Analysis                                                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│                           ┌───────────────────┐                                 │
│                           │       🌍          │                                 │
│                           └───────────────────┘                                 │
│                                                                                 │
│                     No Landscape Analysis Available                             │
│                                                                                 │
│         The landscape analysis synthesizes all competitor reports into          │
│         actionable feature opportunities. Run competitive analysis first.       │
│                                                                                 │
│         Status: 2 of 5 competitor reports available                             │
│                                                                                 │
│                [Run Full Analysis] or [Run Synthesis Only]                      │
│                                                                                 │
│         Note: "Run Synthesis Only" uses existing competitor reports.            │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Analysis In Progress States

Progress is shown in multiple locations:
- **Product Dashboard:** Single progress bar on Competitive Analysis Agent card (overall status)
- **Competitor Reports tab:** Per-competitor progress bars on individual cards
- **Landscape tab:** Pending message until all audits complete

### 5a. Competitor Reports Tab - Per-Competitor Progress

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ Competitor Reports                                                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  Functional audits compare each competitor's features against your product.    │
│                                                                                 │
│  Manage competitors in Market Discovery →                                       │
│                                                                                 │
│  ┌─ Competitor A ──────────────────────────────────────────────── ✓ Complete ─┐ │
│  │  Features: 24 │ Gaps: 8 │ Updated: Jan 13, 2026                            │ │
│  │                                [View Report] [Run Audit] [Export .md ↓]    │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ┌─ Competitor B ────────────────────────────────────────────── 🔄 Analyzing ─┐ │
│  │  ████████████████░░░░░░░░░░░░  Extracting features...                      │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ┌─ Competitor C ──────────────────────────────────────────────────── Queued ─┐ │
│  │  Waiting for analysis to start...                                          │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 5b. Landscape Tab - Pending State

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ Landscape Analysis                                                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │  ⏳ Landscape Analysis Pending                                            │   │
│  │                                                                          │   │
│  │  Waiting for competitor audits to complete before synthesizing...        │   │
│  │                                                                          │   │
│  │  3 of 5 competitor audits complete                                       │   │
│  │                                                                          │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 5c. Product Dashboard - Agent Card Progress

```
┌─ Competitive Analysis Agent ──────────────────────────────────────────────────┐
│                                                                               │
│  Analyzes competitors and identifies feature opportunities.                   │
│                                                                               │
│  🔄 Analysis in progress...                                                   │
│  ████████████░░░░░░░░░░░░░  3 of 5 competitors • Landscape pending            │
│                                                                               │
│                                              [View Details] [Settings]        │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Create Ideas Confirmation Modal

When user clicks "Create Ideas for Voting":

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ Create Ideas for Voting                                                   [✕]   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  Submit 3 opportunities to the customer voting queue?                           │
│                                                                                 │
│  Ideas will be created with:                                                    │
│  - Title prefixed with "Add: "                                                  │
│  - Source marked as "Competitive Analysis"                                      │
│  - Automatically processed by Idea Triage Agent                                 │
│                                                                                 │
│  Selected opportunities:                                                        │
│  1. Time Tracking                                                               │
│  2. Jira Import/Migration                                                       │
│  3. Resource Capacity Planning                                                  │
│                                                                                 │
│                                    [Cancel]  [Submit 3 Ideas for Voting]        │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Key changes:**
- Title changed to "Create Ideas for Voting"
- Description clarifies ideas go to voting queue (not backlog)
- Removed triage checkbox (always applied automatically)
- Button label updated to "Submit X Ideas for Voting"

---

## 7. Color and Style Reference

Following existing patterns from the codebase:

### Buttons
- **Primary:** `bg-blue-600 text-white hover:bg-blue-700`
- **Secondary:** `border border-gray-300 text-gray-700 hover:bg-gray-50`
- **Danger:** `bg-red-600 text-white hover:bg-red-700`

### Cards
- **Container:** `bg-gray-50 rounded-lg border border-gray-200 p-4`
- **White card:** `bg-white rounded-lg shadow p-4`

### Badges
- **High priority (red):** `bg-red-100 text-red-700`
- **Medium priority (yellow):** `bg-yellow-100 text-yellow-700`
- **Low priority (gray):** `bg-gray-100 text-gray-700`
- **Success (green):** `bg-green-100 text-green-700`

### Progress indicators
- **Bar background:** `bg-gray-200 rounded-full h-2`
- **Bar fill:** `bg-blue-600 h-2 rounded-full`

### Tables
- **Header:** `bg-gray-50 text-xs font-medium text-gray-500 uppercase`
- **Body:** `bg-white divide-y divide-gray-200`
- **Cell:** `px-4 py-4 text-sm`

---

## 8. Component Files to Create/Modify

### New Components
1. `CompetitorReportsTab.tsx` - List and view competitor functional reports with per-gap idea creation
2. `LandscapeTab.tsx` - Display landscape synthesis, feature opportunities (sorted by high-impact), create ideas or export
3. `ReportViewer.tsx` - Markdown rendering component with export
4. `FeatureOpportunityCard.tsx` - Individual opportunity card with checkbox, sentiment, priority explanation

### Modified Components
1. `AgentSettingsTab.tsx` - Remove strategic analysis toggles AND competitive intensity settings
2. `IntelligenceHubPage.tsx` - Update tabs (replace Insights with new tabs)
3. `ProductDashboardPage.tsx` - Progress bar on Competitive Analysis Agent card

### Remove/Deprecate
1. `InsightsTab.tsx` - No longer needed (deprecated strategic analysis)

---

## 9. API Integration Points

### Competitor Reports Tab
- `GET /product-intelligence/agents/{product_id}/functional-reports` - List all reports
- `GET /product-intelligence/agents/{product_id}/competitors/{competitor_id}/functional-report` - Get report detail
- `GET /product-intelligence/agents/{product_id}/competitors/{competitor_id}/functional-report/export` - Download .md
- `POST /product-intelligence/agents/{product_id}/competitors/{competitor_id}/functional-audit` - Trigger single audit
- `POST /product-intelligence/agents/{product_id}/competitors/{competitor_id}/gaps/{gap_index}/create-idea` - Create idea from single gap

### Landscape Tab
- `GET /product-intelligence/agents/{product_id}/landscape-report` - Get landscape report
- `GET /product-intelligence/agents/{product_id}/landscape-report/export` - Download full report .md
- `POST /product-intelligence/agents/{product_id}/landscape-report/create-ideas` - Create ideas for voting
- `POST /product-intelligence/agents/{product_id}/landscape-report/export-json` - Export for roadmap tools
- `POST /product-intelligence/agents/{product_id}/run-landscape-synthesis` - Trigger synthesis only

### Full Analysis (triggered from Product Dashboard)
- `POST /product-intelligence/agents/{product_id}/run-competitive-analysis-v2` - Trigger full V2 workflow

---

## 10. Summary of UX Changes from Feedback

| Original | Updated |
|----------|---------|
| Settings had Product Analysis, Competitor Discovery, Intensity thresholds | Settings only has Competitive Analysis schedule |
| "Run Analysis for All" button in Competitor Reports | Full analysis triggered from Product Dashboard agent card |
| Implementation Complexity in gap analysis | Removed (no reliable data source) |
| Separate High-Impact Gaps section | Combined with Feature Opportunities, sorted to top |
| Per-gap "Create Idea" buttons in Competitor Reports | Consistent checkbox selection pattern across both tabs |
| No "Select All" option | "Select All" added to both Competitor Reports and Landscape tabs |
| Separate Export section at bottom | Combined action box with both "Create Ideas" and "Export Selected" |
| Export exported all opportunities | Export only exports selected items |
| "Create Ideas from Selected" | "Create Ideas for Voting" (clarifies purpose) |
| Idea Triage checkbox option | Removed (always applied automatically) |
| "Ideas go to backlog" | "Ideas go to customer voting queue" |
| Full analysis progress bar in Competitor Reports | Per-competitor progress only; overall progress on Dashboard |
| No user sentiment data | User Sentiment with ratings and quotes added |
| No priority explanation | "Why this score" field explains Market Gravity calculation |
| No "Idea submitted" indicator | Badge shows when opportunity/gap already converted |
| No warning for already-submitted items | Note warns they'll be skipped for idea creation but included in export |
| No link to Market Discovery | "Manage competitors in Market Discovery →" link added |
