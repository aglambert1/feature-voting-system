# Stage 3: Feature Extraction - Testing Guide

**Status:** Implementation Complete, Ready for Testing
**Last Updated:** December 12, 2024

---

## Overview

Module 6 - Feature Extraction enables AI-powered feature discovery from competitor websites with:
- ✅ Fresh extraction (first analysis)
- ✅ Comparative analysis (detect changes from previous analysis)
- ✅ Multi-URL research (homepage, features, pricing, docs, etc.)
- ✅ Feature expansion on demand
- ⏸️ Celery parallel processing (deferred for MVP)

---

## Architecture Notes

### ⚠️ Current Implementation Adjustments

Based on MVP requirements:

**1. Celery Deferral**
- Document specifies Celery for parallel extraction
- **MVP approach:** Synchronous extraction (one competitor at a time)
- **Rationale:** Simpler setup, avoids Redis/Celery dependencies for MVP
- **Future:** Enable Celery when scaling to 10+ competitors per analysis

**2. Frontend Framework**
- Module spec shows TypeScript (`.tsx`)
- **Actual:** JavaScript/JSX (`.jsx`)
- **Status:** Already implemented correctly in codebase

**3. Brave Search Integration**
- Feature extraction benefits from web search for multi-URL research
- **Current:** Agent uses training knowledge only
- **Consideration:** Could integrate Brave Search we just implemented
- **Recommendation:** Test first without search, add search support in follow-up

---

## Testing Checklist

### Phase 1: Backend Unit Tests

**Location:** Create `backend/tests/test_feature_extraction.py`

- [ ] Test FeatureExtractorAgent in fresh mode
  - Input: competitor_name, competitor_url, no previous_features
  - Expected: 10-25 features extracted with categories, confidence scores

- [ ] Test FeatureExtractorAgent in comparative mode
  - Input: competitor_name, competitor_url, with previous_features
  - Expected: Features marked as new/modified/unchanged/removed

- [ ] Test FeatureDetailExpanderAgent
  - Input: feature name, description, competitor info
  - Expected: Expanded description with use cases, benefits, limitations

- [ ] Test JSON parsing with multi-line descriptions
  - Edge case: Features with long descriptions
  - Expected: Clean JSON parsing without errors

- [ ] Test database storage
  - Features should save to CompetitorFeature table
  - Change types should be tracked
  - Source URLs should be persisted

---

### Phase 2: API Endpoint Tests

**Files to Test:**
- `POST /sessions/{session_id}/extract-features` - Start extraction
- `GET /sessions/{session_id}/features` - Get extracted features
- `GET /features/{feature_id}/details` - Get expanded details
- `POST /sessions/{session_id}/select-features` - Select features

**Test Cases:**

1. **Start Extraction (Synchronous)**
   ```bash
   POST /api/competitor-intelligence/sessions/{sessionId}/extract-features

   Expected Response:
   {
     "status": "completed",  # Synchronous, completes immediately
     "total_competitors": 3,
     "features_by_competitor": { ... }
   }
   ```

2. **Get Features**
   ```bash
   GET /api/competitor-intelligence/sessions/{sessionId}/features

   Expected:
   - Features grouped by competitor
   - Change stats (new, modified, unchanged, removed)
   - Each feature has: name, description, category, confidence, source_url
   ```

3. **Expand Feature Details**
   ```bash
   GET /api/competitor-intelligence/features/{featureId}/details

   Expected:
   - expanded_description
   - technical_details
   - use_cases: []
   - benefits: []
   - limitations: []
   ```

4. **Select Features**
   ```bash
   POST /api/competitor-intelligence/sessions/{sessionId}/select-features
   Body: ["feature-id-1", "feature-id-2", ...]

   Expected:
   {
     "selected_count": 2
   }
   ```

---

### Phase 3: Frontend Manual Testing

**Test Scenario 1: Fresh Extraction (First Analysis)**

1. Complete Stages 1-2 to reach Stage 3
2. Observe loading state:
   - [ ] Spinner animates
   - [ ] "Extracting Features..." message displays
   - [ ] Extraction completes in 30-60 seconds
3. Review extracted features:
   - [ ] Features grouped by competitor
   - [ ] Feature names are concise (2-5 words)
   - [ ] Descriptions are clear (1-2 sentences)
   - [ ] Categories are logical (Core Functionality, Integration, etc.)
   - [ ] Confidence scores visible (0.0-1.0)
4. Test feature selection:
   - [ ] Click checkbox to select features
   - [ ] Selected count updates at top
   - [ ] Can select/deselect multiple
5. Test request details:
   - [ ] Click "Request Details" on a feature
   - [ ] Modal opens with loading spinner
   - [ ] Expanded information displays:
     - Expanded description
     - Technical details
     - Use cases
     - Benefits
     - Limitations
6. Test confirmation:
   - [ ] Select at least one feature
   - [ ] Click "Generate Ideas (N) →"
   - [ ] Proceeds to Stage 4

**Test Scenario 2: Comparative Analysis (With Previous Data)**

1. Run first analysis (Scenario 1)
2. Create new session for same product
3. Run analysis again
4. In Stage 3, verify change detection:
   - [ ] Change Summary Dashboard displays:
     - Total Features count
     - New Features (green)
     - Modified Features (orange)
     - Unchanged Features (gray)
     - Removed Features (red)
   - [ ] Each feature shows change type badge
   - [ ] Features can be filtered by change type toggle:
     - "Show only new/modified features"
     - Removed features appear grayed out and unchecked
5. Verify feature status:
   - [ ] NEW: Feature not in previous analysis
   - [ ] MODIFIED: Feature changed (description, capability)
   - [ ] UNCHANGED: Feature same as before
   - [ ] REMOVED: Previous feature no longer found

**Test Scenario 3: Edge Cases**

1. **No features extracted:**
   - Product with unknown competitors
   - Expected: Empty features list with message
   - Should still allow proceeding (0 features selected)

2. **Very short product description:**
   - Minimal text
   - Expected: Agent works with limited info, may find fewer features

3. **Large number of features:**
   - 25+ features extracted
   - Expected: Table scrolls, all features display correctly

4. **Long feature descriptions:**
   - Multi-line descriptions
   - Expected: Text wraps correctly in table

---

### Phase 4: Integration Testing

**Full Workflow: Stages 1 → 2 → 3 → Confirmation**

1. Create new analysis session
2. Add product with description
3. AI discovers competitors (Stage 2)
4. Select 3-4 competitors
5. AI extracts features for each (Stage 3)
6. Verify extraction completed for ALL competitors
7. Select features from multiple competitors
8. Confirm and proceed to Stage 4

**Parallel Competitor Testing:**
- Create analysis with 5+ competitors
- All features extracted for each
- Feature count correct per competitor
- No data mixing between competitors

---

## Running the Tests

### Backend Unit Tests

```bash
cd backend

# Run all feature extraction tests
pytest tests/test_feature_extraction.py -v

# Run specific test
pytest tests/test_feature_extraction.py::test_feature_extractor_fresh_mode -v

# Run with coverage
pytest tests/test_feature_extraction.py --cov=app/agents --cov=app/services
```

### API Testing with curl

```bash
# Start extraction
curl -X POST http://localhost:8000/api/competitor-intelligence/sessions/{sessionId}/extract-features \
  -H "Authorization: Bearer {token}"

# Get features
curl -X GET http://localhost:8000/api/competitor-intelligence/sessions/{sessionId}/features \
  -H "Authorization: Bearer {token}"

# Get feature details
curl -X GET http://localhost:8000/api/competitor-intelligence/features/{featureId}/details \
  -H "Authorization: Bearer {token}"
```

### Frontend Testing

```bash
# Start both frontend and backend
cd frontend && npm run dev   # Terminal 1
cd backend && python -m uvicorn app.main:app --reload  # Terminal 2

# Navigate to: http://localhost:5173/competitor-intelligence
# Complete Stages 1 → 2 → 3
```

---

## Known Issues & Workarounds

### Issue 1: Synchronous Extraction (No Celery)
- **Current Behavior:** Features extract one competitor at a time
- **Expected:** Takes 30-60 seconds for 3 competitors
- **Workaround:** None needed for MVP
- **Future:** Add Celery for parallel when needed

### Issue 2: Limited Web Search
- **Current:** Agent uses training knowledge only
- **Enhancement:** Could integrate Brave Search for current URLs
- **Recommendation:** Test first, then add in follow-up if needed
- **Impact:** May have outdated URLs in training knowledge

### Issue 3: Feature Expansion Performance
- **Current:** Each expanded detail requires LLM call
- **Optimization:** Cache expanded descriptions in database
- **Status:** Already implemented (see `expanded_description` field)

---

## Expected Results

### Successful Test Results

**Fresh Extraction:**
- ✅ 10-25 features extracted per competitor
- ✅ Categories: Core Functionality, Integration, Analytics, Pricing, Security, etc.
- ✅ Confidence scores: 0.7-1.0 (high confidence)
- ✅ Source URLs provided (from training knowledge)
- ✅ Each feature 2-5 word name, 1-2 sentence description

**Comparative Analysis:**
- ✅ Previous features identified and matched
- ✅ NEW: 2-5 new features found
- ✅ MODIFIED: 1-3 features changed
- ✅ UNCHANGED: Majority remain same
- ✅ REMOVED: 0-2 previous features not found

**Change Detection:**
- ✅ Dashboard shows accurate counts
- ✅ Badges correctly color-coded
- ✅ Filter toggle hides/shows changes
- ✅ Feature selection works correctly

---

## Debugging Tips

### If features aren't extracting:
1. Check LLM service logs for API errors
2. Verify Anthropic API key is valid
3. Check competitor URLs are accessible (in theory)
4. Verify JSON response is valid

### If change detection not working:
1. Verify previous features loaded from database
2. Check session IDs match correctly
3. Ensure `change_type` field is populated

### If expansion not working:
1. Check FeatureDetailExpanderAgent system prompt
2. Verify LLM response includes all required fields
3. Check feature expanded_description field saves

### Database verification:
```python
# Check if features stored correctly
python
>>> from app.database import SessionLocal
>>> from app.models import CompetitorFeature
>>> db = SessionLocal()
>>> features = db.query(CompetitorFeature).limit(5).all()
>>> for f in features:
...     print(f"Feature: {f.feature_name}, Change: {f.change_type}")
```

---

## Testing Timeline

- **Phase 1 (Unit Tests):** 1-2 hours
- **Phase 2 (API Tests):** 1-2 hours
- **Phase 3 (Frontend Manual):** 2-3 hours
- **Phase 4 (Integration):** 1-2 hours
- **Total:** 5-9 hours

---

## Acceptance Criteria Checklist

### Backend ✅
- [ ] FeatureExtractorAgent extracts 10-25 features
- [ ] Comparative mode detects changes correctly
- [ ] FeatureDetailExpanderAgent provides expanded details
- [ ] Features stored in database with all fields
- [ ] Product-level features tracked across sessions
- [ ] Change type field populated correctly
- [ ] All unit tests pass
- [ ] API endpoints return correct responses

### Frontend ✅
- [ ] Stage 3 UI loads correctly
- [ ] Extraction completes and displays features
- [ ] Features grouped by competitor
- [ ] Feature selection works
- [ ] Request details shows expanded info
- [ ] Change summary dashboard displays (when applicable)
- [ ] Change type badges color-coded correctly
- [ ] Filter toggle works
- [ ] Confirmation proceeds to Stage 4

### Integration ✅
- [ ] End-to-end: Stages 1→2→3→complete
- [ ] Multiple competitors extracted properly
- [ ] Change detection accurate
- [ ] Selected features passed to next stage
- [ ] No data loss between stages
- [ ] Error handling works for edge cases

---

## Next Steps After Testing

1. **Document Any Findings**
   - Note issues encountered
   - Record timing (how long extraction takes)
   - Capture sample outputs

2. **Consider Future Enhancements**
   - Add Brave Search for multi-URL research (already have infrastructure)
   - Enable Celery for parallel extraction (when needed)
   - Add feature categorization suggestions from training data
   - Implement feature similarity detection

3. **Proceed to Module 7**
   - Idea Generation & Finalization
   - Convert selected features to improvement ideas
   - Submit ideas to main voting system

---

## References

- **Module 6 Specification:** `docs/module_6_feature_extraction_prompt-2.md`
- **Search Integration:** `docs/search_integration_status.md`
- **Database Schema:** Backend models for CompetitorFeature, ProductCompetitorFeature
- **API Docs:** Competitor Intelligence API endpoints
