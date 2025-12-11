# Competitor Intelligence: Modular Implementation Guide

## Overview

This guide breaks down the competitor intelligence system into **8 independent modules** that can be implemented and tested separately. Each module has its own prompt file, dependencies, and testing criteria.

## Implementation Order & Dependencies

```
Module 1: Database Schema (Foundation)
    ↓
Module 2: Product Management (Core entity CRUD)
    ↓
Module 3: Base Agent Infrastructure (AI foundation)
    ↓
    ├─→ Module 4: Product Analysis (Stage 1 of wizard)
    ├─→ Module 5: Competitor Discovery (Stage 2 of wizard)
    ├─→ Module 6: Feature Extraction (Stage 3 of wizard)
    └─→ Module 7: Idea Generation (Stages 4-5 of wizard)
         ↓
Module 8: Frontend Integration (Complete UI)
```

## Module Breakdown

### Module 1: Database Schema & Models
**Status**: Independent - Can be fully implemented and tested
**Files**: 
- Database migration
- SQLAlchemy models
- Pydantic schemas

**Deliverable**: Complete database ready to store all CI data

---

### Module 2: Product Management API
**Status**: Depends on Module 1
**Files**: 
- ProductService
- Product API endpoints
- Product frontend pages (list, detail)

**Deliverable**: Users can create/view/edit products

---

### Module 3: Base Agent Infrastructure
**Status**: Depends on Module 1 (for logging)
**Files**: 
- BaseAgent class
- LLMService extensions
- Agent execution logging

**Deliverable**: Framework for all AI agents to use

---

### Module 4: Product Analysis Agent & Session Start
**Status**: Depends on Modules 1, 2, 3
**Files**: 
- ProductAnalyzerAgent
- Session creation logic
- Stage 1 frontend component

**Deliverable**: Users can start analysis and AI structures product

---

### Module 5: Competitor Discovery with Differential Analysis
**Status**: Depends on Modules 1-4
**Files**: 
- CompetitorResearcherAgent
- DifferentialAnalysisAgent
- Competitor confirmation API
- Stage 2 frontend component

**Deliverable**: AI discovers competitors, shows changes if previous analysis exists

---

### Module 6: Feature Extraction with Change Detection
**Status**: Depends on Modules 1-5
**Files**: 
- FeatureExtractorAgent (with comparison mode)
- FeatureDetailExpanderAgent
- Celery tasks for parallel extraction
- Stage 3 frontend component

**Deliverable**: AI extracts features in parallel, detects changes

---

### Module 7: Idea Generation & Finalization
**Status**: Depends on Modules 1-6
**Files**: 
- IdeaStructuringAgent
- Idea generation/editing API
- Finalization logic (link to main ideas table)
- Stages 4-5 frontend components

**Deliverable**: AI converts features to ideas, submits to voting system

---

### Module 8: Frontend Wizard Integration
**Status**: Depends on all backend modules
**Files**: 
- WizardContainer component
- Navigation logic
- Change indicator components
- Polish and responsive design

**Deliverable**: Complete end-to-end user experience

---

## How to Use This Guide

### For Each Module:

1. **Read the dedicated prompt file** (e.g., `module_1_database_prompt.md`)
2. **Implement the module** using Claude Code
3. **Run the module-specific tests**
4. **Verify the acceptance criteria**
5. **Move to next module** only after current one passes all tests

### Testing Strategy Per Module:

- **Unit tests**: Test individual functions/methods
- **Integration tests**: Test module interaction with dependencies
- **Manual tests**: Verify through API/UI as described
- **Regression tests**: Ensure previous modules still work

### Rollback Strategy:

Each module is independent enough that you can:
- Work on multiple modules in parallel (if dependencies allow)
- Roll back a module without affecting others
- Skip optional modules (marked as "Nice to Have")

---

## Quick Reference Table

| Module | Time Est. | Must Have? | Can Test Independently? |
|--------|-----------|------------|------------------------|
| 1. Database | 1-2 days | ✅ Yes | ✅ Yes (migrations) |
| 2. Product API | 2-3 days | ✅ Yes | ✅ Yes (CRUD operations) |
| 3. Agent Base | 1-2 days | ✅ Yes | ✅ Yes (mock agents) |
| 4. Product Analysis | 2-3 days | ✅ Yes | ✅ Yes (with mock Claude API) |
| 5. Competitor Discovery | 3-4 days | ✅ Yes | ✅ Yes (with mock data) |
| 6. Feature Extraction | 4-5 days | ✅ Yes | ⚠️ Partial (needs Celery) |
| 7. Idea Generation | 2-3 days | ✅ Yes | ✅ Yes |
| 8. Frontend Polish | 3-5 days | ⚠️ Nice to have | ✅ Yes |

**Total Estimated Time**: 18-27 days (3.5-5.5 weeks)

---

## Sample Implementation Schedule

### Week 1: Foundation
- **Mon-Tue**: Module 1 (Database)
- **Wed-Fri**: Module 2 (Product API)
- **Weekend**: Module 3 (Agent Base)

### Week 2: Core AI Agents
- **Mon-Tue**: Module 4 (Product Analysis)
- **Wed-Thu**: Module 5 (Competitor Discovery)
- **Fri**: Testing & Integration

### Week 3: Feature Extraction
- **Mon-Thu**: Module 6 (Feature Extraction + Celery)
- **Fri**: Testing

### Week 4: Idea Generation & Frontend
- **Mon-Tue**: Module 7 (Idea Generation)
- **Wed-Fri**: Module 8 (Frontend Polish)

### Week 5: Testing & Refinement
- **Mon-Thu**: End-to-end testing, bug fixes
- **Fri**: Documentation, deployment prep

---

## Next Steps

1. Review the individual module prompts (see files listed below)
2. Choose starting module (recommend: Module 1)
3. Copy the relevant prompt to Claude Code
4. Implement, test, verify
5. Move to next module

## Module Prompt Files

Created separately for your use:
- `module_1_database_prompt.md` - Database schema and models
- `module_2_product_api_prompt.md` - Product management backend + frontend
- `module_3_agent_base_prompt.md` - Agent infrastructure
- `module_4_product_analysis_prompt.md` - Product analyzer + session start
- `module_5_competitor_discovery_prompt.md` - Competitor research + differential analysis
- `module_6_feature_extraction_prompt.md` - Feature extraction + Celery tasks
- `module_7_idea_generation_prompt.md` - Idea structuring + finalization
- `module_8_frontend_wizard_prompt.md` - Complete frontend wizard

Each prompt is self-contained with:
- Clear objectives
- Required dependencies
- Implementation steps
- Testing requirements
- Acceptance criteria
- Sample code/examples
