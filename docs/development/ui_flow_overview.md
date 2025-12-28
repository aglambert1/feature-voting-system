# UI Flow: Unified Product Insight System

## Navigation Structure

```
Home (Multi-Product Summary)
│
├── [+ New Product] → Product Setup Flow → Product Dashboard
│
└── [Product Card] → Product Dashboard
                        │
                        ├── Review Queues
                        │   ├── Ideas Queue
                        │   ├── Competitive Alerts
                        │   └── Reports
                        │
                        ├── Views
                        │   ├── Comparison View
                        │   ├── All Ideas
                        │   └── All Competitors
                        │
                        └── Settings
                            ├── Product Info (update anytime)
                            ├── Agent Configuration
                            └── Report Configuration
```

---

## Level 0: Home / Multi-Product Summary

### Purpose
Entry point showing all products and aggregate action items.

### Layout
```
┌─────────────────────────────────────────────────────────────────┐
│  Product Insight Assistant                       [+ New Product] │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ⚡ Action Summary (All Products)                               │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐               │
│  │ 8 Ideas     │ │ 3 Competitive│ │ 2 Reports   │               │
│  │ need review │ │ alerts       │ │ ready       │               │
│  └─────────────┘ └─────────────┘ └─────────────┘               │
│                                                                 │
│  Products                                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 🔵 Acme Analytics                                        │   │
│  │    5 ideas pending │ 2 alerts │ Agents: ✓✓✓ │ Last: 2h   │→ │
│  ├─────────────────────────────────────────────────────────┤   │
│  │ 🟢 DataFlow Pro                                          │   │
│  │    3 ideas pending │ 1 alert  │ Agents: ✓✓○ │ Last: 1d   │→ │
│  ├─────────────────────────────────────────────────────────┤   │
│  │ 🟡 InsightHub                                            │   │
│  │    0 ideas pending │ 0 alerts │ Agents: ✓○○ │ Last: 5m   │→ │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Interactions
- Click product card → Product Dashboard
- Click "+ New Product" → Product Setup Flow
- Click action summary cards → Filtered queue view (all products)

---

## Level 1: Product Setup Flow

### Purpose
Create new product OR update existing product definition.

### Step 1/3: Define Product

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
│  {For updates only:}                                            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ℹ️ Current product definition shown below. The AI will   │   │
│  │   analyze what has changed.                              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│                                             [Analyze Product →] │
└─────────────────────────────────────────────────────────────────┘
```

### Step 1b/3: Review & Edit Structured Data

```
┌─────────────────────────────────────────────────────────────────┐
│  {New Product Setup | Update Product}              Step 1 of 3  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Here's what I understand:                                      │
│                                                                 │
│  Product Name                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Acme Analytics                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Category                                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Business Intelligence                                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Core Features                                           [+ Add]│
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ • Real-time dashboards                              [×] │   │
│  │ • SQL query builder                                 [×] │   │
│  │ • Embedded analytics                                [×] │   │
│  │ • Role-based access control                         [×] │   │
│  │ • Scheduled reports                                 [×] │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Target Users                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Data analysts, Product managers, Business executives    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  {For updates: Show diff highlighting what changed}             │
│                                                                 │
│                                   [← Back]  [Looks Good →]      │
└─────────────────────────────────────────────────────────────────┘
```

### Step 2/3: Configure Agents

```
┌─────────────────────────────────────────────────────────────────┐
│  {New Product Setup | Update Product}              Step 2 of 3  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  What should I help you with?                                   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ☑ Idea Triage Agent                          [Configure]│   │
│  │   Auto-respond to submissions, find duplicates,         │   │
│  │   recommend actions                                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ☑ Competitive Monitor                        [Configure]│   │
│  │   Track competitor changes, generate alerts             │   │
│  │                                                         │   │
│  │   {For new products:}                                   │   │
│  │   Found 12 competitors. [Select which to monitor →]     │   │
│  │                                                         │   │
│  │   {For updates:}                                        │   │
│  │   Currently monitoring 8 competitors. [Manage →]        │   │
│  │   ☐ Re-discover competitors based on updated product    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ☑ Report Generator                           [Configure]│   │
│  │   Scheduled reports on competitive intel, voting,       │   │
│  │   and customer feedback                                 │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│                                   [← Back]  [Set Up Agents →]   │
└─────────────────────────────────────────────────────────────────┘
```

### Step 3/3: Ready

```
┌─────────────────────────────────────────────────────────────────┐
│  {New Product Setup | Update Product}              Step 3 of 3  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ✓ {Acme Analytics is set up | Acme Analytics updated}         │
│                                                                 │
│  Agents:                                                        │
│  • Idea Triage - Watching for new submissions                  │
│  • Competitive Monitor - {First scan | Next scan} running...   │
│  • Report Generator - Monthly report scheduled                  │
│                                                                 │
│  {For updates:}                                                 │
│  Changes applied:                                               │
│  • Product description updated                                  │
│  • 2 features added, 1 removed                                 │
│  • Competitor re-discovery triggered                            │
│                                                                 │
│  I'll notify you when there's something to review.             │
│                                                                 │
│                                        [Go to Dashboard →]      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Level 2: Product Dashboard

### Purpose
Central hub for a single product's insights and actions.

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  ← All Products    Acme Analytics                   [Settings]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Review Queues                                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐               │
│  │ Ideas       │ │ Competitive │ │ Reports     │               │
│  │ ●●●●●  5    │ │ ●●○○○  2    │ │ ●○○○○  1    │               │
│  │ [Review →]  │ │ [Review →]  │ │ [View →]    │               │
│  └─────────────┘ └─────────────┘ └─────────────┘               │
│                                                                 │
│  Agent Status                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 🟢 Idea Triage       Active     Last run: 2 hours ago   │   │
│  │ 🔄 Competitive       Running    Scanning CompetitorX... │   │
│  │ 🟢 Report Generator  Active     Next: Jan 1, 9:00 AM    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Recent Activity                                                │
│  • Auto-responded to "Dark mode support" - 2h ago              │
│  • Detected 3 new features at CompetitorX - 4h ago             │
│  • Monthly report generated - 1d ago                           │
│  • Merged duplicate ideas (#45, #47) - 2d ago                  │
│                                                                 │
│  Quick Actions                                                  │
│  [Run Competitive Scan] [View Comparison] [Generate Report]    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Level 3: Review Queues

### Ideas Queue

```
┌─────────────────────────────────────────────────────────────────┐
│  ← Dashboard    Ideas to Review (5)                 [Bulk Actions]│
├─────────────────────────────────────────────────────────────────┤
│  Filter: [All ▼]  Sort: [Newest ▼]                              │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ "Dark mode support"                      Submitted: 2h   │   │
│  │ Source: Customer (user@example.com)                      │   │
│  │                                                         │   │
│  │ Agent Assessment:                                       │   │
│  │ • Similar to 2 existing ideas                           │   │
│  │ • CompetitorX has this (detected 3 months ago)          │   │
│  │ • 4 previous submissions mention "dark mode"            │   │
│  │                                                         │   │
│  │ Auto-Response: ✓ Sent                                   │   │
│  │                                                         │   │
│  │ Recommendation: Merge with #42 (87% confidence)         │   │
│  │                                                         │   │
│  │ [Approve] [Merge →] [Edit & Approve] [Dismiss]         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ "Real-time collaboration"                Submitted: 4h   │   │
│  │ Source: Competitor (from CompetitorX scan)               │   │
│  │                                                         │   │
│  │ Agent Assessment:                                       │   │
│  │ • New capability - no similar existing ideas            │   │
│  │ • HIGH priority: 2 competitors have this               │   │
│  │                                                         │   │
│  │ Recommendation: Approve for voting (92% confidence)     │   │
│  │                                                         │   │
│  │ [Approve for Voting] [Edit First] [Dismiss]            │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Competitive Alerts Queue

```
┌─────────────────────────────────────────────────────────────────┐
│  ← Dashboard    Competitive Alerts (2)               [Settings]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 🔴 HIGH: CompetitorX launched AI features               │   │
│  │ Detected: 4 hours ago                                   │   │
│  │                                                         │   │
│  │ Changes:                                                │   │
│  │ • NEW: AI-powered insights                              │   │
│  │ • NEW: Natural language queries                         │   │
│  │ • MODIFIED: Pricing (new AI tier)                       │   │
│  │                                                         │   │
│  │ Context:                                                │   │
│  │ • CompetitorY added similar features last month         │   │
│  │ • 2 customer ideas mention "AI"                         │   │
│  │                                                         │   │
│  │ Recommendation: Create ideas for voting                 │   │
│  │                                                         │   │
│  │ [Create Ideas (2)] [View Details] [Dismiss] [Snooze]   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 🟡 MEDIUM: CompetitorZ removed features                 │   │
│  │ Detected: 1 day ago                                     │   │
│  │                                                         │   │
│  │ Changes:                                                │   │
│  │ • REMOVED: Advanced API access                          │   │
│  │ • REMOVED: Custom integrations                          │   │
│  │                                                         │   │
│  │ Insight: Possible pivot or cost-cutting                 │   │
│  │                                                         │   │
│  │ [Note] [Dismiss] [Snooze]                              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Level 4: Comparison View

### Purpose
Side-by-side feature comparison: your product vs selected competitors.

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  ← Dashboard    Feature Comparison                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Compare with: ☑ CompetitorX  ☑ CompetitorY  ☐ CompetitorZ     │
│                                                        [Update] │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Your Advantages (features they lack)                     │   │
│  ├─────────────────────────────────────────────────────────┤   │
│  │ Feature          │ You │ CompX │ CompY │                │   │
│  │ ─────────────────┼─────┼───────┼───────┤                │   │
│  │ Embedded Analytics│ ✓   │ ✗     │ ✗     │                │   │
│  │ SOC2 Compliance  │ ✓   │ ✗     │ ✗     │                │   │
│  │ Custom Branding  │ ✓   │ ✗     │ ✓     │                │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Gaps (features you lack)                    Customer    │   │
│  │                                             Interest    │   │
│  ├─────────────────────────────────────────────────────────┤   │
│  │ Feature          │ You │ CompX │ CompY │ Votes         │   │
│  │ ─────────────────┼─────┼───────┼───────┼───────────────┤   │
│  │ AI Insights      │ ✗   │ ✓     │ ✓     │ 47 votes      │   │
│  │ Real-time Collab │ ✗   │ ✓     │ ✗     │ 31 votes      │   │
│  │ Mobile App       │ ✗   │ ✓     │ ✓     │ 28 votes      │   │
│  │                                                         │   │
│  │              [Create Idea from Gap →]                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Feature Parity (both have)                              │   │
│  ├─────────────────────────────────────────────────────────┤   │
│  │ • Dashboard Builder  • Data Export  • User Management   │   │
│  │ • API Access  • Scheduled Reports  • Alerts             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  [Export Comparison]  [Add to Report]                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Level 5: Settings

### Product Info (Editable Anytime)

```
┌─────────────────────────────────────────────────────────────────┐
│  ← Dashboard    Settings: Product Info                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Product Name                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Acme Analytics                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Description                                                    │
│  ○ Edit text    ○ Upload new document    ○ Paste URL           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Business intelligence platform for data teams...        │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Core Features                                          [+ Add] │
│  • Real-time dashboards                                    [×]  │
│  • SQL query builder                                       [×]  │
│  • Embedded analytics                                      [×]  │
│                                                                 │
│  When saving changes:                                           │
│  ☐ Re-analyze product with AI                                  │
│  ☐ Re-discover competitors                                     │
│  ☐ Trigger competitive scan                                    │
│                                                                 │
│  Last updated: Dec 15, 2024                                    │
│                                                                 │
│                                    [Cancel]  [Save Changes]     │
└─────────────────────────────────────────────────────────────────┘
```

### Agent Configuration

```
┌─────────────────────────────────────────────────────────────────┐
│  ← Dashboard    Settings: Agents                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Idea Triage Agent                               [Enabled ✓]    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Auto-response tone: [Professional ▼]                    │   │
│  │ Duplicate threshold: [95% ▼]                            │   │
│  │ Similar threshold: [85% ▼]                              │   │
│  │ ☑ Always queue for review (don't auto-approve)         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Competitive Monitor                             [Enabled ✓]    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Scan frequency: [Weekly ▼]  Day: [Monday ▼]            │   │
│  │ Competitors monitored: 8 [Manage →]                     │   │
│  │ ☑ Auto-generate ideas from new features                │   │
│  │ ☑ Alert on pricing changes                             │   │
│  │ Alert threshold: [Medium ▼]                            │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Report Generator                                [Enabled ✓]    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Configured reports: 2 [Manage Reports →]               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│                                              [Save All Changes] │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Summary

| Component | Purpose |
|-----------|---------|
| `ProductCard` | Summary card for product list |
| `ActionSummaryCard` | Aggregate pending actions |
| `AgentStatusIndicator` | Show agent state (active/running/error) |
| `ReviewQueueCard` | Pending items count with link |
| `IdeaReviewItem` | Single idea in review queue |
| `CompetitiveAlertItem` | Single alert in queue |
| `FeatureComparisonTable` | Side-by-side feature matrix |
| `GapAnalysisTable` | Features you lack with customer interest |
| `ProductSetupWizard` | Multi-step product setup/update |
| `AgentConfigPanel` | Per-agent settings |
| `ReportConfigPanel` | Report builder interface |
