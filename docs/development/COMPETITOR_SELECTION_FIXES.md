# Competitor Selection and Feature Badge Fixes

## Problems Identified

### Problem 1: Extracted Features List Shows Deselected Competitors

**Issue:** When you select 3 competitors, go to Stage 3, then go back to Stage 2 and deselect one, the feature extraction results still show all 3 competitors with their features.

**Expected Behavior:** The extraction results should only show features for currently selected competitors.

**Root Cause:** The `/sessions/{session_id}/features` endpoint was calling `get_session_features()` with the default parameter `include_unselected=True`, which returns features for ALL competitors in the session, regardless of their selection status.

### Problem 2: Features Ready Badge Not Showing on Some Competitors

**Issue:** Some competitors that have features extracted don't show the "✓ Features Ready" green badge in Stage 2.

**Potential Causes:**
1. Timing issue - badge data not loaded yet when component renders
2. ID mismatch between competitor ID and features availability keys
3. Feature extraction completed but badge not refreshing

**Investigation Added:** Enhanced console logging to debug which competitors have features and which IDs are being checked.

## Solutions Implemented

### Fix 1: Only Return Features for Selected Competitors

**File:** `backend/app/api/sessions.py` (line 825)

**Change:**
```python
# Before (returned all competitors)
result = await service.get_session_features(session_id)

# After (only selected competitors)
result = await service.get_session_features(session_id, include_unselected=False)
```

**Impact:**
- The `get_session_features` method already had the logic to filter by `selected_by_user=True`
- The endpoint just wasn't using it (defaulted to `include_unselected=True`)
- Now only returns features for competitors where `selected_by_user=True`

**Flow:**
1. User selects 3 competitors in Stage 2
2. User confirms and moves to Stage 3
3. Features are extracted for all 3 selected competitors
4. User goes back to Stage 2
5. User deselects 1 competitor (updates `selected_by_user=False` in database)
6. User returns to Stage 3
7. **Now:** Only 2 competitors with features are shown
8. **Before:** All 3 competitors were still shown

### Fix 2: Enhanced Debug Logging for Badge Issue

**File:** `frontend/src/pages/CompetitorIntelligence/stages/Stage2_CompetitorDiscovery.tsx` (lines 110-119)

**Added Logging:**
```typescript
// Debug: Log which competitors have features vs which don't
const withFeatures = Object.entries(response.data.competitors_availability)
  .filter(([_, data]) => data.has_features)
  .map(([id, data]) => `${data.competitor_name} (ID: ${id})`);
const withoutFeatures = Object.entries(response.data.competitors_availability)
  .filter(([_, data]) => !data.has_features)
  .map(([id, data]) => `${data.competitor_name} (ID: ${id})`);

console.log('[Stage2] Competitors WITH features:', withFeatures);
console.log('[Stage2] Competitors WITHOUT features:', withoutFeatures);
```

**Purpose:**
- Shows exactly which competitors the backend says have features
- Shows the IDs being used to look up feature availability
- Helps identify if the issue is:
  - Backend not detecting features correctly
  - ID mismatch between competitor and availability data
  - Timing issue with data loading

**How to Debug Badge Issue:**
1. Open browser console
2. Navigate to Stage 2
3. Look for console logs:
   - `[Stage2] Refreshing features availability for X competitors`
   - `[Stage2] Features availability loaded: {...}`
   - `[Stage2] Competitors WITH features: [...]`
   - `[Stage2] Competitors WITHOUT features: [...]`
4. Compare:
   - Does the competitor showing/missing badge appear in the correct list?
   - Does the ID in the availability data match the `competitor.id` in the UI?
   - Is the data even being fetched (check for API errors)?

## Database Query Flow

### Features Availability Check

**Endpoint:** `GET /sessions/{session_id}/competitors-feature-availability`

**Query Logic:**
```python
# Get all SessionCompetitor records for this session
session_competitors = db.query(SessionCompetitor).filter(
    SessionCompetitor.session_id == session_id
).all()

# For each competitor
for session_comp in session_competitors:
    if session_comp.product_competitor_id:
        # Check if ProductCompetitorFeature records exist
        features_count = db.query(ProductCompetitorFeature).filter(
            ProductCompetitorFeature.product_competitor_id == session_comp.product_competitor_id
        ).count()

        has_features = (features_count > 0)
```

**Returns:**
```json
{
  "competitors_availability": {
    "123": { "has_features": true, "competitor_name": "Competitor A" },
    "124": { "has_features": false, "competitor_name": "Competitor B" }
  }
}
```

**Key:** The key is `str(session_comp.id)` - the SessionCompetitor ID

### Get Session Features

**Endpoint:** `GET /sessions/{session_id}/features`

**Query Logic (After Fix):**
```python
query = self.db.query(CompetitorFeature).join(
    SessionCompetitor
).filter(
    SessionCompetitor.session_id == session_id
)

# NOW: Only include selected competitors
if not include_unselected:  # include_unselected=False from API
    query = query.filter(SessionCompetitor.selected_by_user == True)

features = query.all()
```

**Before Fix:** Returned all competitors' features
**After Fix:** Only returns features for selected competitors

## Testing Scenarios

### Scenario 1: Deselect Competitor After Extraction

**Steps:**
1. Select 3 competitors in Stage 2
2. Confirm and move to Stage 3
3. Extract features for all 3
4. Go back to Stage 2
5. Deselect 1 competitor
6. Return to Stage 3

**Expected Result (After Fix):**
- Only 2 competitors shown in extraction results
- Features from deselected competitor are hidden

**Previous Behavior:**
- All 3 competitors shown
- Deselected competitor's features still visible

### Scenario 2: Badge Shows After Extraction

**Steps:**
1. Select 3 new competitors (no features yet)
2. Extract features in Stage 3
3. Return to Stage 2

**Expected Result:**
- All 3 competitors show "✓ Features Ready" badge
- Console shows: `[Stage2] Competitors WITH features: ["CompA (ID: 123)", "CompB (ID: 124)", "CompC (ID: 125)"]`

**If Badge Missing:**
- Check console for ID mismatch
- Verify backend is returning `has_features: true`
- Check if `fetchFeaturesAvailability()` was called

### Scenario 3: Mixed Selection States

**Steps:**
1. Have 5 competitors total
2. 3 have features extracted
3. Select only 2 of the 3 with features
4. Move to Stage 3

**Expected Result (After Fix):**
- Only the 2 selected competitors shown
- Unselected competitor (even with features) is not shown

**Previous Behavior:**
- All 3 competitors with features shown
- Selection state ignored

## Files Modified

### Backend

1. **`backend/app/api/sessions.py`** (line 825)
   - Changed: `get_session_features(session_id, include_unselected=False)`
   - Effect: Only returns features for selected competitors

### Frontend

2. **`frontend/src/pages/CompetitorIntelligence/stages/Stage2_CompetitorDiscovery.tsx`** (lines 110-119)
   - Added: Enhanced debug logging for feature availability
   - Effect: Better visibility into badge data for debugging

## Known Remaining Issues

### Badge Issue Diagnosis

The badge issue requires live debugging with the enhanced logging. The most likely causes are:

1. **Timing Issue:**
   - `fetchFeaturesAvailability()` might complete AFTER the component renders
   - The useEffect with `[sessionId]` dependency should handle this
   - Check if the effect is running (look for console logs)

2. **ID Mismatch:**
   - The `competitor.id` in the UI might not match the key in `featuresAvailability`
   - Backend returns `str(session_comp.id)` as key
   - Frontend uses `competitor.id` to look up data
   - Check console to compare IDs

3. **Database Inconsistency:**
   - Features might exist but `product_competitor_id` is null
   - Features might exist in `CompetitorFeature` but not `ProductCompetitorFeature`
   - The backend queries `ProductCompetitorFeature` table specifically

### Debugging Steps

1. **Check Console Logs:**
   ```
   [Stage2] Refreshing features availability for 3 competitors
   [Stage2] Features availability loaded: {...}
   [Stage2] Competitors WITH features: ["CompA (ID: 123)", ...]
   [Stage2] Competitors WITHOUT features: ["CompB (ID: 124)", ...]
   ```

2. **Verify API Response:**
   - Open Network tab
   - Find request to `/competitors-feature-availability`
   - Check response structure

3. **Check Component State:**
   - Add breakpoint in CompetitorCard render
   - Inspect `hasFeatures` prop value
   - Inspect `featuresAvailability` state

4. **Database Check:**
   ```sql
   -- Check if features exist for competitor
   SELECT pc.id, pc.competitor_name, COUNT(pcf.id) as features_count
   FROM product_competitor pc
   LEFT JOIN product_competitor_feature pcf ON pcf.product_competitor_id = pc.id
   WHERE pc.competitor_name = 'CompetitorName'
   GROUP BY pc.id, pc.competitor_name;
   ```

## Next Steps

1. **Monitor Console Logs:** Use the enhanced logging to identify badge issues
2. **Test Selection Changes:** Verify deselected competitors don't appear in extraction
3. **Report Findings:** If badge issue persists, provide console logs for further debugging

The extraction list fix is complete and should work immediately. The badge issue requires monitoring the enhanced logging to identify the root cause.
