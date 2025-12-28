# Unified Product Insight System: Agent Architecture

## Overview

This system transforms the application from a wizard-based tool into an autonomous agent system that acts on behalf of Product Managers. Agents run in the background, process multiple insight sources, and prepare actions for PM review.

## Core Principles

1. **Unified Feedback Loop**: All insight sources (customer ideas, competitor features, future: CRM/support) normalize into a single ideas format
2. **Customer Validation**: Competitor-sourced ideas are anonymized and voted on by customers alongside their own submissions
3. **Agents Act, PMs Decide**: Agents handle routine processing; PMs review and approve

## System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        INSIGHT SOURCES                          │
├─────────────────┬─────────────────┬─────────────────────────────┤
│ Customer Ideas  │ Competitor Intel │ Future: CRM, Support, Calls │
└────────┬────────┴────────┬────────┴─────────────────────────────┘
         │                 │
         ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                     SOURCE ADAPTERS                              │
│  (Normalize all sources to unified idea format)                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PROCESSING AGENTS                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Idea Triage  │  │ Competitive  │  │ Report       │          │
│  │ Agent        │  │ Monitor      │  │ Generator    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PM REVIEW QUEUES                             │
│  • Ideas to Review    • Competitive Alerts    • Reports Ready   │
└─────────────────────────────────────────────────────────────────┘
```

## Agent Inventory

| Agent | Purpose | Trigger | Output |
|-------|---------|---------|--------|
| **Product Analyzer** | Structure product descriptions | Product create/update | Structured product data |
| **Competitor Discovery** | Find competitors for a product | On-demand / product update | Competitor list |
| **Competitive Monitor** | Track competitor changes over time | Scheduled (configurable) | Alerts + feature changes |
| **Feature Extractor** | Extract features from competitor | Per-competitor during monitoring | Feature list with change detection |
| **Idea Normalizer** | Convert any source to idea format | New insight from any source | Normalized idea |
| **Idea Triage** | Auto-respond, dedupe, categorize | New idea submission | Triage recommendation |
| **Similarity Detector** | Find related/duplicate ideas | New idea created | Similar idea links |
| **Report Generator** | Create scheduled/on-demand reports | Schedule or PM request | Exportable report |

## Data Flow Summary

1. **Ingest**: Sources push/pull data into system
2. **Normalize**: Source adapters convert to unified idea format
3. **Enrich**: Agents add similarity scores, categories, recommendations
4. **Queue**: Items appear in appropriate PM review queue
5. **Validate**: Approved ideas enter customer voting
6. **Synthesize**: Reports combine sources + validation data
7. **Output**: PM gets actionable, sourced, validated insights

## Key Design Decisions

### Anonymization of Competitor Features
- Competitor-sourced ideas are stripped of branding before voting
- Customers evaluate ideas on merit, not origin
- Source metadata preserved for PM traceability

### PM Review Gates
- Agents prepare and recommend; they don't auto-publish to voting
- PM approves ideas before customer visibility
- Exception: Idea Triage auto-responds but queues for PM review

### Extensible Source Pattern
- All sources implement same adapter interface
- Normalize to: What / Why / Use Case + source metadata
- Future sources (CRM, support) plug into same flow

## File Index

- `agent_system_overview.md` - This file
- `agent_idea_triage.md` - Idea Triage Agent specification
- `agent_competitive_monitor.md` - Competitive Monitor Agent specification  
- `agent_report_generator.md` - Report Generator Agent specification
- `agent_shared_components.md` - Shared utilities (normalizer, similarity, etc.)
- `ui_flow_overview.md` - Updated UI/UX flow
- `source_adapter_pattern.md` - Pattern for future source integrations
