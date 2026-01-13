# UI Flow: Unified Product Insight System

## Navigation Structure

```
Product Intelligence (Multi-Product Summary) | Browse Ideas | Submit Idea
│
├── [+ New Product] → Product Setup Flow (/product-intelligence/products/create) → Product Dashboard
│
└── [Product Card] → Product Dashboard
                        │
                        ├── Agent Status
                        │   ├── Idea Triage Agent
                        │   ├── Market Discovery Agent
                        │   └── Competitor Analysis Agent
                        │
                        ├── Current Product Analysis
                        │
                        ├── Product Info (update anytime)
                        │
                        └──  Product Analysis History

```

---

## Level 0: Home / Multi-Product Summary

### Purpose

Entry point showing all products and aggregate action items.

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  Product Intelligence                      [+ New Product] │
├─────────────────────────────────────────────────────────────────┤
|                                                                 │
│  Products                                                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 🔵 Acme Analytics                                        │   │
│  │    3 product info sources │ 2 competitive alerts         │   │
│  │    5 ideas pending (7 auto-responded) │ Last analysis: 2h│   │
│  ├──────────────────────────────────────────────────────────┤   │
│  │ 🟢 DataFlow Pro                                          │   │
│  │    3 product info sources │ 2 competitive alerts         │   │
│  │    5 ideas pending (7 auto-responded) │ Last analysis: 2h│   │
│  ├─────────────────────────────────────────────────────────┤   │
│  │ 🟡 InsightHub                                            │   │
│  │    3 product info sources │ 2 competitive alerts         │   │
│  │    5 ideas pending (7 auto-responded) │ Last analysis: 2h│   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Interactions

- Click product card → Product Dashboard
- Click "+ New Product" → Product Setup Flow
- Note: product card should extend across screen to better display if only one product and more room for summary data displayed.

---

## Level 1: Product Setup Flow

### Purpose

Create new product OR update existing product definition. Add or remove product data sources. Same as existing.

### Define Product by adding or removing product information sources

```
┌─────────────────────────────────────────────────────────────────┐
│  {New Product Setup | Update Product}              Step 1 of 3  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Tell me about your product                                     │
│                                                                 │
│  ○ Describe it    ○ Upload document    ○ Paste URL             │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                                                         │   │
│  │  [Text area / Upload zone / URL input based on tab]     │   │
│  │                                                         │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Add one or more sources: type text directly, upload documents (PDF, DOCX, TXT, MD), or fetch content from URLs. All sources will be combined for AI analysis.
│                                                                 │
│                                   [Cancel]  [Analyze Product →] │
└─────────────────────────────────────────────────────────────────┘
```

### Interactions

- Add text, documents or URL and extract text
- Existing product info can be deleted with X on right side
- Click (Re-)Analyze Product to create (if new) and analyze product
- Next page (after interim analysis running page)→ Product Dashboard

---

## Level 2: Product Dashboard

### Purpose

Central hub for a single product's insights and actions.

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ ← All Products Acme Analytics [Settings] │
├─────────────────────────────────────────────────────────────────┤
│  Analyzed (v3)                                                  │
│  Category Name                                                  │
│  Description:
│  Acme Analytics is a business intelligence product providing    │
│  flexible analytics for smb companies. It competes in the       │
│  business intelligence platform market.                         │
│                                                                 │
│ Agent Status                                                    │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 🟢 Idea Triage Active Last run: 2 hours ago   [Setup]   │ │
│ │ 5 ideas pending response [Go to Ideas]                  │ │
│ │ 23 ideas responded to by Agent │ Automatic Responses On │ │
│ └─────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 🟢 Market Discovery Agent Last run: 2 hours ago[Run Now] [Setup] │ │
│ │ 11 competitors discovered; 1 new [Show Competitors]     │ │
│ │  5 competitors selected for deep analysis               │ │
│ └─────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 🟢 Competitive Analysis Agent Last run: 2 hours ago[Run Now] [Setup] │ │
│ │  3 new competitive alerts [Go To Report]                │ │
│ │  43 competitive features extracted                      │ │
│ │  5 competitive feature clusters; 3 ideas created        │ │
│ └─────────────────────────────────────────────────────────┘ │
│ Current Product Analysis                                    │
│ • Core Features (7)                                         │
│ ....                                                        │
│ • Target Users                                              │
│ ....                                                        │
│ • Value Propositions │
│  ....                                                     │
│ • Competitor Search Keywords │
│ ....
│                                                       │
│ Product Information Sources [Change Sources]          │
│ (List of sources with title and URL/file name if available) │
│                                                       │
│ Product Analysis History (3)                          │
│  Version 3 (Current) ...                                        │
└─────────────────────────────────────────────────────────────────┘

```

### Interactions

- Setup goes to appropriate setup page for each agent
  Idea Triage Agent Setup provides option to enable automatic responses and confidence threshold
  Market Discovery Agent Setup provides options for scheduling (every X months), whether to automatically run after new product analysis, and enable/disable.
  Competitive Analysis Agent Setup provides options for schedule, strategic analysis components, feature similarity threshold, idea generation threshold, and enable/disable.
- Run Now initiates Agent as task in background. When complete the Agent Status tiles should update with results.
- Go to Ideas goes to Level 0 Ideas page for product with Pending Ideas at top
- Show Competitors goes to page listing all competitors found in last Market Discovery run and with existing selections of competitors selected for deep analysis. Similar to existing page, but "Extract Features" option removed and explanatory text that selecting competitors tags them for deep analysis and feature extraction.
- Go to Report goes to Competitive Report page with feature extraction and competitive analysis for each deep analysis competitor, and a list of feature clusters found. Recommend design for this page.
- Change Sources goes to the Re-Analyze product page where source data can be added or removed and product re-analyzed.

---

## Level 2 - Competitor Report Page

Hybrid layout: Cross-competitor summaries at top, then per-competitor full details in accordions

┌─────────────────────────────────────────────────────────────────┐
│ ← Product Dashboard [Product Name] │
│ Last updated: 2 hours ago │
├─────────────────────────────────────────────────────────────────┤
│ │
│ FEATURE CLUSTERS │
│ ┌─────────────────────────────┬─────────────────────────────┐ │
│ │ Dashboard Analytics [High] │ User Management [Medium]│ │
│ │ 5 competitors • 12 features │ 3 competitors • 8 features │ │
│ │ [Create Idea] [View Details]│ ✓ Idea generated [Details] │ │
│ └─────────────────────────────┴─────────────────────────────┘ │
│ │
│ STRATEGIC INSIGHTS SUMMARY │
│ ┌──────────────┬──────────────┬──────────────┐ │
│ │ Pricing │ Positioning │ Momentum │ ← tabs │
│ └──────────────┴──────────────┴──────────────┘ │
│ ┌─────────────────────────────────────────────────────────────┐│
│ │ Competitor │ Model │ Free │ Trial │ Enterprise ││
│ │───────────────┼──────────┼──────┼───────┼──────────────────││
│ │ Competitor A │ Freemium │ ✓ │ 14d │ ✓ ││
│ │ Competitor B │ Tiered │ ✗ │ 30d │ ✓ ││
│ └─────────────────────────────────────────────────────────────┘│
│ │
│ COMPETITOR DETAILS │
│ ┌─────────────────────────────────────────────────────────────┐│
│ │ ▼ Competitor A ││
│ │ ┌─────────────────────────────────────────────────────┐ ││
│ │ │ Strategic Insights │ ││
│ │ │ • Pricing: Freemium model, 3 tiers, 14-day trial │ ││
│ │ │ • Positioning: "Analytics for everyone" │ ││
│ │ │ • Momentum: ↑ Rising (Score: 78%) │ ││
│ │ │ • Recent: 2 changes in last 30 days │ ││
│ │ └─────────────────────────────────────────────────────┘ ││
│ │ ┌─────────────────────────────────────────────────────┐ ││
│ │ │ Features (12) [Select] │ ││
│ │ │ ☐ Real-time dashboards [NEW] - 92% confidence │ ││
│ │ │ ☐ Custom widgets [MODIFIED] - 87% confidence │ ││
│ │ │ ☐ Export to PDF - 95% confidence │ ││
│ │ │ ... │ ││
│ │ │ [Create Ideas from Selected (0)] │ ││
│ │ └─────────────────────────────────────────────────────┘ ││
│ ├─────────────────────────────────────────────────────────────┤│
│ │ ▶ Competitor B (8 features) ││
│ └─────────────────────────────────────────────────────────────┘│
│ │
└─────────────────────────────────────────────────────────────────┘
This design provides:
Quick comparison: Cross-competitor tables for pricing, positioning, momentum at a glance
Deep dive: Full details per competitor in expandable accordions
Dual idea creation: From clusters OR from individual selected features
