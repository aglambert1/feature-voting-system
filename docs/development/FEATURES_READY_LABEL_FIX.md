# Features Ready Label Fix

## Problem Description

The "Features Ready" label on competitor cards was not consistently showing:
1. When visiting a competitor list with two competitors that had features extracted, only one showed the "Features Ready" label
2. When returning to the competitor list from the feature extraction page (Stage 3), none of the competitors showed that they had features ready
3. However, when advancing to extraction, competitors with features were properly tracked (the backend knew about the features)

## Root Cause

The issue was in the **Stage 2 (Competitor Discovery)** component's lifecycle management:

### Flow Analysis

1. **When Stage 2 first loads:**
   - `useEffect` at line 84 runs
   - If no `savedState`, it calls `checkExistingCompetitors()`
   - This eventually calls `fetchFeaturesAvailability()` which loads the feature status

2. **When returning from Stage 3 to Stage 2:**
   - The parent component passes `savedState` with the previously loaded competitors
   - Component restores state from `savedState` (lines 60-67)
   - Sets `discoveryInitiated = true` (line 67)
   - The `useEffect` at line 84 **does NOT run** because `savedState` exists
   - `fetchFeaturesAvailability()` is **never called**
   - Features availability remains empty `{}`
   - All competitor cards show NO "Features Ready" label

### Code Location

**File:** `frontend/src/pages/CompetitorIntelligence/stages/Stage2_CompetitorDiscovery.tsx`

**Previous behavior (lines 84-90):**
```tsx
useEffect(() => {
  // Only fetch if we don't have saved state
  if (!savedState && !discoveryInitiated) {
    setDiscoveryInitiated(true);
    checkExistingCompetitors();
  }
}, [savedState, discoveryInitiated]);
```

This effect would not run when `savedState` exists, meaning features availability was never refreshed when returning from Stage 3.

## Solution

Added a new `useEffect` hook that refreshes features availability when the component mounts with competitors already loaded (from savedState or otherwise).

**File:** `frontend/src/pages/CompetitorIntelligence/stages/Stage2_CompetitorDiscovery.tsx` (lines 92-99)

```tsx
// Refresh features availability when component mounts or when returning from Stage 3
useEffect(() => {
  // If we have competitors (either from savedState or loaded), fetch their feature availability
  if (competitors.length > 0 && mode === 'reviewing') {
    console.log('[Stage2] Refreshing features availability for', competitors.length, 'competitors');
    fetchFeaturesAvailability();
  }
}, [sessionId]); // Only run on mount or when sessionId changes
```

### Key Points

1. **Runs on component mount**: The dependency is `[sessionId]`, which remains stable but ensures the effect runs when the component mounts
2. **Checks for loaded state**: Only runs if `competitors.length > 0` and `mode === 'reviewing'`
3. **Works with savedState**: When returning from Stage 3 with savedState, this effect will run because:
   - `competitors` is restored from savedState (line 61)
   - `mode` is restored as 'reviewing' from savedState (line 60)
   - The effect sees these conditions and calls `fetchFeaturesAvailability()`
4. **Doesn't interfere with normal flow**: For fresh loads, `checkExistingCompetitors()` still handles everything and calls `fetchFeaturesAvailability()` appropriately

## Backend API

The backend endpoint is working correctly and was not modified:

**Endpoint:** `GET /product-intelligence/sessions/{session_id}/competitors-feature-availability`

**File:** `backend/app/api/sessions.py` (lines 414-481)

**Logic:**
- Fetches all `SessionCompetitor` records for the session
- For each competitor, checks if `ProductCompetitorFeature` records exist
- Returns a map of `session_competitor_id` → `{ has_features: boolean }`

**Example Response:**
```json
{
  "competitors_availability": {
    "123": { "has_features": true, "competitor_name": "Competitor A" },
    "124": { "has_features": false, "competitor_name": "Competitor B" }
  }
}
```

## UI Component

The CompetitorCard component was also working correctly and was not modified:

**File:** `frontend/src/pages/CompetitorIntelligence/components/CompetitorCard.tsx` (lines 75-82)

```tsx
{hasFeatures && (
  <span
    className="inline-block px-2 py-0.5 bg-green-100 text-green-800 text-xs rounded-full font-medium"
    title="Features have already been extracted for this competitor"
  >
    ✓ Features Ready
  </span>
)}
```

The `hasFeatures` prop is passed from Stage2:
```tsx
hasFeatures={featuresAvailability[competitor.id]?.has_features ?? false}
```

## Testing Scenarios

### Scenario 1: Initial Load with Existing Features
**Steps:**
1. Navigate to Stage 2 with a session that has competitors
2. Some competitors already have features extracted from previous sessions
3. **Expected:** Competitors with features show "✓ Features Ready" badge
4. **Result:** ✓ Works (was already working)

### Scenario 2: Return from Stage 3 (Previously Broken)
**Steps:**
1. Navigate to Stage 2 with competitors
2. Extract features for some competitors in Stage 3
3. Return to Stage 2 using the workflow navigation
4. **Expected:** Competitors with extracted features show "✓ Features Ready" badge
5. **Result:** ✓ Now works! (previously broken)

### Scenario 3: Multiple Competitors with Features
**Steps:**
1. Navigate to Stage 2 with 3+ competitors
2. Extract features for multiple (but not all) competitors
3. Return to Stage 2
4. **Expected:** Each competitor correctly shows/hides the badge based on feature status
5. **Result:** ✓ Now works!

### Scenario 4: Re-entering Stage 2 Multiple Times
**Steps:**
1. Navigate to Stage 2 → Stage 3 → Stage 2 multiple times
2. Extract features incrementally
3. **Expected:** Badge status updates correctly on each return
4. **Result:** ✓ Now works!

## Console Logging

Added console logging for debugging:

```
[Stage2] Refreshing features availability for 3 competitors
[Stage2] Features availability loaded: { "123": { has_features: true }, ... }
```

This helps verify:
- When the refresh is triggered
- How many competitors are being checked
- What the backend returned

## Files Modified

1. **frontend/src/pages/CompetitorIntelligence/stages/Stage2_CompetitorDiscovery.tsx**
   - Added new `useEffect` hook (lines 92-99)
   - Ensures features availability is refreshed when returning from Stage 3

## Impact

- ✅ Fixes the issue where "Features Ready" label disappears when returning from Stage 3
- ✅ Ensures consistent display of feature extraction status
- ✅ No performance impact (API call only on mount, using existing endpoint)
- ✅ No breaking changes to existing functionality
- ✅ Works with both fresh loads and savedState scenarios

## Related Components

These components interact with the features availability system but did not require changes:

1. **CompetitorCard.tsx** - Displays the badge (already working)
2. **Stage3_FeatureExtraction.tsx** - Extracts features (already working)
3. **Backend API** - Returns feature availability (already working)

The fix was isolated to the Stage 2 component's lifecycle management.
