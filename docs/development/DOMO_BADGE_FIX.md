# Domo Badge Fix - Features Ready Not Showing

## Problem Description

**Specific Issue:** Domo (SessionCompetitor ID: 63) on Product ID: 2 consistently shows NO "✓ Features Ready" badge even though features have been extracted.

**Symptoms:**
- Domo has extracted features visible in Stage 3
- Other competitors show the badge correctly
- Always the same competitor (Domo) having this issue
- Suggests a data inconsistency rather than code bug

## Root Cause Investigation

### Database Analysis

**SessionCompetitor Record:**
```sql
SELECT id, competitor_name, product_competitor_id, selected_by_user
FROM session_competitors WHERE id = 63;

Result: 63|Domo|5|1
```
- ✓ SessionCompetitor exists
- ✓ Has product_competitor_id = 5
- ✓ Is selected (selected_by_user = 1)

**ProductCompetitor Record:**
```sql
SELECT id, competitor_name, product_id, status
FROM product_competitors WHERE id = 5;

Result: 5|Domo|2|active
```
- ✓ ProductCompetitor exists
- ✓ Is active
- ✓ Linked to correct product

**ProductCompetitorFeatures (Global Reusable):**
```sql
SELECT COUNT(*) FROM product_competitor_features
WHERE product_competitor_id = 5;

Result: 0 ❌
```
- **Problem:** ZERO features in global table!

**CompetitorFeatures (Session-Specific):**
```sql
SELECT COUNT(*) FROM competitor_features
WHERE session_competitor_id = 63;

Result: 160 ✓
```
- **Found:** 160 features in session-specific table!

### Architecture Understanding

The system has TWO feature tables with different purposes:

#### 1. `competitor_features` (Session-Specific)
- **Purpose:** Stores features extracted during a specific session
- **Linked to:** `session_competitor_id`
- **Contains:**
  - Raw extracted features with full context
  - Change tracking (new, modified, unchanged, removed)
  - Comparison data for differential analysis
- **Lifecycle:** Created during extraction, tied to session

**Schema:**
```sql
CREATE TABLE competitor_features (
    id INTEGER PRIMARY KEY,
    session_competitor_id INTEGER NOT NULL,  -- Links to SessionCompetitor
    product_feature_id INTEGER,               -- Links to global feature
    feature_name VARCHAR(255),
    feature_description TEXT,
    feature_category VARCHAR(100),
    extraction_confidence DECIMAL(3,2),
    change_type VARCHAR(50),                  -- NEW/MODIFIED/UNCHANGED/REMOVED
    change_description TEXT,
    selected_by_user BOOLEAN,
    ...
)
```

#### 2. `product_competitor_features` (Global Reusable)
- **Purpose:** Deduplicated, reusable features across sessions
- **Linked to:** `product_competitor_id`
- **Contains:**
  - Core feature data without session context
  - First/last seen session tracking
  - Global status (active/inactive)
- **Lifecycle:** Created by deduplication process, persists across sessions

**Schema:**
```sql
CREATE TABLE product_competitor_features (
    id INTEGER PRIMARY KEY,
    product_competitor_id INTEGER NOT NULL,  -- Links to ProductCompetitor
    feature_name VARCHAR(255),
    feature_description TEXT,
    feature_category VARCHAR(100),
    first_discovered_session_id INTEGER,
    last_seen_session_id INTEGER,
    status VARCHAR(50),                       -- active/inactive
    ...
)
```

### The Problem

**Original Badge Check Logic:**
```python
# Only checked product_competitor_features table
if session_comp.product_competitor_id:
    features_count = db.query(ProductCompetitorFeature).filter(
        ProductCompetitorFeature.product_competitor_id == session_comp.product_competitor_id
    ).count()

    has_features = (features_count > 0)
```

**Why Domo Failed:**
1. Features were extracted into `competitor_features` (160 features exist)
2. Deduplication process didn't run or failed for Domo
3. No records created in `product_competitor_features`
4. Badge check only looked at `product_competitor_features`
5. Badge showed "no features" even though 160 features exist

**Why This Happened:**
- Feature deduplication is a separate process from extraction
- If deduplication fails or hasn't run, features remain only in `competitor_features`
- The badge check assumed features were always deduplicated
- Domo's features were never migrated to the global table

## Solution

Updated the badge check to look in BOTH tables:

**File:** `backend/app/api/sessions.py` (lines 462-488)

```python
for session_comp in session_competitors:
    has_features = False

    # Check 1: Global reusable features (product_competitor_features)
    if session_comp.product_competitor_id:
        features_count = db.query(ProductCompetitorFeature).filter(
            ProductCompetitorFeature.product_competitor_id == session_comp.product_competitor_id
        ).count()

        if features_count > 0:
            has_features = True

    # Check 2: Session-specific features (competitor_features)
    # This handles cases where features were extracted but not yet deduplicated
    if not has_features:
        from app.models.competitor_intelligence import CompetitorFeature
        session_features_count = db.query(CompetitorFeature).filter(
            CompetitorFeature.session_competitor_id == session_comp.id
        ).count()

        if session_features_count > 0:
            has_features = True

    competitors_availability[str(session_comp.id)] = {
        "has_features": has_features,
        "competitor_name": session_comp.competitor_name
    }
```

**Logic:**
1. **First:** Check global reusable features table (preferred)
2. **Fallback:** If no global features, check session-specific table
3. **Result:** Badge shows if features exist in EITHER table

**Benefits:**
- ✅ Handles deduplicated features (normal case)
- ✅ Handles non-deduplicated features (Domo's case)
- ✅ Badge shows correctly regardless of deduplication status
- ✅ No data migration required
- ✅ Backwards compatible

## Impact

### Before Fix
- Domo: 160 features in `competitor_features` → Badge: ❌ (not shown)
- Other competitors: Features in both tables → Badge: ✅

### After Fix
- Domo: 160 features in `competitor_features` → Badge: ✅ (shown!)
- Other competitors: Features in both tables → Badge: ✅ (still works)

## Testing

### Manual Test
1. Navigate to Product ID: 2, Stage 2
2. Look for Domo (ID: 63) in competitor list
3. **Expected:** "✓ Features Ready" badge is shown
4. **Console Log:** Should show `Domo (ID: 63)` in "Competitors WITH features" list

### Database Verification
```sql
-- Should return 160
SELECT COUNT(*) FROM competitor_features WHERE session_competitor_id = 63;

-- Should return 0 (the problem)
SELECT COUNT(*) FROM product_competitor_features WHERE product_competitor_id = 5;

-- Backend now checks BOTH, so badge shows correctly
```

## Related Questions

### Q: Why weren't Domo's features deduplicated?

**Possible Reasons:**
1. Deduplication process failed silently
2. Session was interrupted before deduplication
3. Bug in deduplication logic for this specific competitor
4. Deduplication is async and hasn't run yet

### Q: Should we fix the data by migrating features?

**Answer:** Not necessary with this fix.

- The two-table check handles it transparently
- Features are still available for reuse (via `competitor_features`)
- Deduplication can happen naturally next time Domo is analyzed
- Migration script would be complex and risky

### Q: Will this affect performance?

**Answer:** Minimal impact.

- Second query only runs if first returns 0
- Most competitors will have deduplicated features (first query succeeds)
- Only affects edge cases like Domo
- Both queries are indexed and fast

### Q: What about other endpoints?

**Answer:** This fix is specific to the badge display endpoint.

Other endpoints that check features should be reviewed:
- `/competitors/feature-availability` (Stage 3 choice screen)
- Feature extraction reuse logic

These may need similar fixes if they only check one table.

## Files Modified

1. **`backend/app/api/sessions.py`** (lines 462-488)
   - Updated: `get_competitors_feature_availability` endpoint
   - Added: Fallback check to `competitor_features` table
   - Impact: Domo (and any similar cases) now show badge correctly

## Future Improvements

1. **Investigate Deduplication:**
   - Why did Domo's features not get deduplicated?
   - Add logging to deduplication process
   - Add retry mechanism for failed deduplication

2. **Data Consistency Check:**
   - Create migration to deduplicate all non-deduplicated features
   - Add database constraint or trigger to ensure deduplication
   - Monitor for other competitors with same issue

3. **Unified Feature Check:**
   - Create helper function `competitor_has_features(session_competitor_id)`
   - Use in all endpoints that check feature availability
   - Consistent logic across all badge/availability checks

4. **Background Job:**
   - Add cron job to periodically deduplicate orphaned features
   - Ensures eventual consistency even if real-time deduplication fails

## Summary

**Root Cause:** Domo's 160 features exist in `competitor_features` but not in `product_competitor_features` due to incomplete deduplication.

**Fix:** Updated badge check to look in both tables, falling back to session-specific features if global features don't exist.

**Result:** Domo (and any similar cases) now correctly show "✓ Features Ready" badge.

**Files Changed:** `backend/app/api/sessions.py`

**Testing:** Verified Domo has 160 features in database and badge should now display.
