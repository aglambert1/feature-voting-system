# Feature Extraction Mode Text Improvement

## Problem Description

When the feature extraction choice screen was shown (with the option to reuse existing features), the recommendation text had two issues:

1. **Vague warning about additional competitors**: The text said "Any other selected competitors without existing features will still be analyzed" without specifying HOW MANY competitors would need extraction
2. **Misleading "(Instant)" label**: The heading showed "Use Existing Features (Instant)" even when there were competitors that would require AI extraction, making the process NOT instant

### Example of Previous Text

```
Use Existing Features (Instant)
Reuse the 70 feature(s) from these 3 competitor(s).
Any other selected competitors without existing features will still be analyzed.

⏱️ Instant for existing • AI extraction only for new competitors
```

**Problem:** User doesn't know if this means 1 additional competitor or 10 additional competitors needs extraction.

## Solution

Updated the UI to calculate and display the exact number of competitors that need extraction, and conditionally show the "(Instant)" label only when all competitors have existing features.

### Changes Made

**File:** `frontend/src/pages/CompetitorIntelligence/stages/Stage3_FeatureExtraction.tsx`

#### 1. Added State to Track Total Selected Competitors (Line 83)

```tsx
const [totalSelectedCompetitors, setTotalSelectedCompetitors] = useState<number>(0);
```

#### 2. Store Total Count When Checking Features (Lines 123-124)

```tsx
// Store total selected count for UI calculations
setTotalSelectedCompetitors(total_selected);
```

The API already returns `total_selected` (total number of selected competitors) and `with_features` (number with existing features).

#### 3. Calculate Competitors Needing Extraction (Lines 234-236)

```tsx
const totalFeatures = existingFeatures.reduce((sum, comp) => sum + (comp.features_count || 0), 0);
const competitorsNeedingExtraction = totalSelectedCompetitors - existingFeatures.length;
const isInstant = competitorsNeedingExtraction === 0;
```

#### 4. Updated Heading to Conditionally Show "(Instant)" (Lines 291-293)

**Before:**
```tsx
<h3 className="text-lg font-semibold text-gray-900">Use Existing Features (Instant)</h3>
```

**After:**
```tsx
<h3 className="text-lg font-semibold text-gray-900">
  Use Existing Features{isInstant ? ' (Instant)' : ''}
</h3>
```

**Result:**
- Shows "Use Existing Features (Instant)" when ALL competitors have features
- Shows "Use Existing Features" when some competitors need extraction

#### 5. Updated Description with Specific Count (Lines 295-300)

**Before:**
```tsx
<p className="text-gray-700 mb-3">
  Reuse the {totalFeatures} feature(s) from these {existingFeatures.length} competitor(s).
  Any other selected competitors without existing features will still be analyzed.
</p>
```

**After:**
```tsx
<p className="text-gray-700 mb-3">
  Reuse the {totalFeatures} feature(s) from these {existingFeatures.length} competitor(s).
  {competitorsNeedingExtraction > 0 && (
    <> The other {competitorsNeedingExtraction} selected competitor{competitorsNeedingExtraction !== 1 ? 's' : ''} will be analyzed with AI extraction.</>
  )}
</p>
```

**Result:**
- Specific number: "The other 2 selected competitors will be analyzed..."
- Proper pluralization: "competitor" vs "competitors"
- Only shows when there ARE competitors needing extraction

#### 6. Updated Timing Information (Lines 305-310)

**Before:**
```tsx
<span className="font-medium">Instant for existing • AI extraction only for new competitors</span>
```

**After:**
```tsx
<span className="font-medium">
  {isInstant
    ? 'Instant - all competitors have existing features'
    : `Instant for ${existingFeatures.length} • AI extraction for ${competitorsNeedingExtraction} competitor${competitorsNeedingExtraction !== 1 ? 's' : ''}`
  }
</span>
```

**Result:**
- When all have features: "Instant - all competitors have existing features"
- When mixed: "Instant for 3 • AI extraction for 2 competitors"

## Examples of New Text

### Scenario 1: All Competitors Have Features (3 competitors, all with features)

```
Use Existing Features (Instant)                    ← Shows "(Instant)"
Reuse the 70 feature(s) from these 3 competitor(s).  ← No mention of extraction

⏱️ Instant - all competitors have existing features  ← Clear message
```

### Scenario 2: Mixed (3 have features, 2 need extraction)

```
Use Existing Features                              ← No "(Instant)"
Reuse the 70 feature(s) from these 3 competitor(s).
The other 2 selected competitors will be analyzed   ← Specific count!
with AI extraction.

⏱️ Instant for 3 • AI extraction for 2 competitors  ← Clear breakdown
```

### Scenario 3: Mixed (1 has features, 1 needs extraction)

```
Use Existing Features
Reuse the 25 feature(s) from these 1 competitor(s).
The other 1 selected competitor will be analyzed    ← Proper singular
with AI extraction.

⏱️ Instant for 1 • AI extraction for 1 competitor   ← Proper singular
```

### Scenario 4: Mixed (2 have features, 10 need extraction)

```
Use Existing Features
Reuse the 45 feature(s) from these 2 competitor(s).
The other 10 selected competitors will be analyzed  ← Shows large number
with AI extraction.

⏱️ Instant for 2 • AI extraction for 10 competitors ← User knows what to expect
```

## Benefits

1. **Transparency**: Users know exactly how many competitors will require AI extraction
2. **Accurate Expectations**: "(Instant)" only shows when it's truly instant
3. **Better Planning**: Users can decide whether to proceed based on knowing 2 vs 10 competitors need extraction
4. **Professional**: Specific counts are more informative than vague warnings
5. **Proper Grammar**: Handles singular/plural correctly (1 competitor vs 2 competitors)

## Data Flow

1. **Backend API** (`/product-intelligence/sessions/{id}/competitors/feature-availability`):
   - Returns `total_selected`: Total selected competitors
   - Returns `with_features`: Number with existing features
   - Returns `competitors_with_features`: Array of competitors with features

2. **Frontend Calculation**:
   - `existingFeatures.length` = Number with features (from array length)
   - `competitorsNeedingExtraction` = `total_selected - existingFeatures.length`
   - `isInstant` = `competitorsNeedingExtraction === 0`

3. **UI Display**:
   - Conditional "(Instant)" in heading
   - Specific count in description
   - Detailed breakdown in timing info

## Files Modified

- **frontend/src/pages/CompetitorIntelligence/stages/Stage3_FeatureExtraction.tsx**
  - Added `totalSelectedCompetitors` state (line 83)
  - Updated `checkExistingFeatures` to store total (line 124)
  - Calculate `competitorsNeedingExtraction` and `isInstant` (lines 234-236)
  - Updated heading with conditional "(Instant)" (lines 291-293)
  - Updated description with specific count (lines 295-300)
  - Updated timing info with breakdown (lines 305-310)

## Testing Scenarios

To verify the changes work correctly:

1. **All competitors have features**: Verify "(Instant)" shows and no extraction count mentioned
2. **Mixed features**: Verify no "(Instant)" and correct count of competitors needing extraction
3. **Single competitor needing extraction**: Verify proper singular "competitor" (not "competitors")
4. **Many competitors needing extraction**: Verify large numbers display correctly
5. **Zero competitors needing extraction**: Same as scenario 1

All scenarios should show clear, specific information about what will happen.
