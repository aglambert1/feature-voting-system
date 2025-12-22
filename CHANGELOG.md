# Changelog

All notable changes to the Feature Voting System will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2024-12-21

### Added

#### Two-Level Feature Extraction
- **Detailed Features System**: Product analysis now extracts features at two levels
  - Strategic core features (5-7 high-level capabilities)
  - Tactical detailed features (10-25 granular, verifiable features)
- **New Database Table**: `product_features` for storing detailed features
- **New API Endpoint**: `GET /product-intelligence/products/{product_id}/detailed-features`
- **Benefit**: Product and competitor features now extracted at same granularity for meaningful comparison

**Technical Details**:
- Updated `ProductAnalyzerAgent` with `DetailedProductFeature` schema
- Added `ProductFeature` model with analysis version tracking
- Integrated storage in `ProductService.analyze_product()`
- See [docs/development/DETAILED_FEATURES_IMPLEMENTATION.md](docs/development/DETAILED_FEATURES_IMPLEMENTATION.md)

#### Enhanced Extraction Mode Information
- **Specific Competitor Counts**: Shows exact number of competitors needing extraction
  - Previous: "Any other selected competitors without existing features will still be analyzed"
  - New: "The other 2 selected competitors will be analyzed with AI extraction"
- **Conditional "Instant" Label**: Only shows when ALL competitors have existing features
  - Removed misleading "(Instant)" when extraction is needed
- **Detailed Timing Information**: Clear breakdown of instant vs extraction counts
  - Example: "Instant for 3 • AI extraction for 2 competitors"
- **Proper Pluralization**: Handles singular/plural correctly (1 competitor vs 2 competitors)

**Technical Details**:
- Added `totalSelectedCompetitors` state tracking
- Calculate `competitorsNeedingExtraction` dynamically
- Conditional rendering based on extraction requirements
- See [docs/development/EXTRACTION_MODE_TEXT_IMPROVEMENT.md](docs/development/EXTRACTION_MODE_TEXT_IMPROVEMENT.md)

### Fixed

#### Features Ready Badge Not Showing
- **Issue**: Badge inconsistently displayed on competitor cards
  - When returning from Stage 3, no badges shown
  - Only appeared on initial load, not on navigation
- **Root Cause**: `fetchFeaturesAvailability()` not called when component restored from savedState
- **Fix**: Added `useEffect` hook to refresh availability on mount
  - Triggers when `competitors.length > 0` and `mode === 'reviewing'`
  - Dependency on `sessionId` ensures refresh on component mount
  - Works with both fresh loads and savedState scenarios

**Impact**: Badge now correctly shows "✓ Features Ready" when returning from Stage 3

**Technical Details**:
- File: `frontend/src/pages/CompetitorIntelligence/stages/Stage2_CompetitorDiscovery.tsx`
- Added lines 92-99
- See [docs/development/FEATURES_READY_LABEL_FIX.md](docs/development/FEATURES_READY_LABEL_FIX.md)

#### Domo Badge Not Showing (Dual-Table Architecture Issue)
- **Issue**: Specific competitor (Domo, ID: 63) never showed badge despite having 160 extracted features
- **Root Cause**: Features existed in `competitor_features` (session-specific) but not in `product_competitor_features` (global reusable)
  - Deduplication process failed or didn't run for this competitor
  - Badge check only looked at global table
- **Fix**: Updated badge check to look in BOTH tables
  - First: Check `product_competitor_features` (preferred)
  - Fallback: Check `competitor_features` if global check returns zero
  - Badge shows if features exist in EITHER table

**Architecture Discovery**:
- System uses two feature tables with different purposes:
  1. `competitor_features`: Session-specific with change tracking
  2. `product_competitor_features`: Deduplicated, reusable across sessions
- Deduplication is asynchronous and may fail silently
- Fallback check handles incomplete deduplication gracefully

**Impact**: Badge now works regardless of deduplication status

**Technical Details**:
- File: `backend/app/api/sessions.py` lines 474-483
- See [docs/development/DOMO_BADGE_FIX.md](docs/development/DOMO_BADGE_FIX.md)

#### Extraction List Showing Deselected Competitors
- **Issue**: After deselecting competitors in Stage 2, they still appeared in Stage 3 extraction results
  - Example: Select 3 competitors → extract features → go back → deselect 1 → still see all 3
- **Root Cause**: `get_session_features()` called with default `include_unselected=True`
- **Fix**: Changed API call to `get_session_features(session_id, include_unselected=False)`
  - Now only returns features for competitors with `selected_by_user=True`
  - Respects current selection state

**Impact**: Extraction results now match selected competitors

**Technical Details**:
- File: `backend/app/api/sessions.py` line 825
- See [docs/development/COMPETITOR_SELECTION_FIXES.md](docs/development/COMPETITOR_SELECTION_FIXES.md)

#### Enhanced Debug Logging for Badge Issues
- **Added**: Console logging to diagnose badge display issues
  - Shows which competitors have features vs don't
  - Shows IDs being used for availability lookup
  - Helps identify timing issues, ID mismatches, or data problems
- **Log Format**:
  ```
  [Stage2] Refreshing features availability for 3 competitors
  [Stage2] Features availability loaded: {...}
  [Stage2] Competitors WITH features: ["CompA (ID: 123)", ...]
  [Stage2] Competitors WITHOUT features: ["CompB (ID: 124)", ...]
  ```

**Technical Details**:
- File: `frontend/src/pages/CompetitorIntelligence/stages/Stage2_CompetitorDiscovery.tsx` lines 110-119
- See [docs/development/COMPETITOR_SELECTION_FIXES.md](docs/development/COMPETITOR_SELECTION_FIXES.md)

---

## [0.9.0] - 2024-12 (Pre-Release)

### Added
- Complete 5-stage competitive intelligence workflow
- User voting module with idea submission and voting
- Product-centric idea management
- Session-based differential analysis
- AI-powered feature extraction
- Semantic feature matching with vector embeddings
- Role-based access control (RBAC)
- Product-level permissions (ADMIN, EDIT, VIEW)
- JWT authentication with 7-day token expiry
- Simplified password management for development

### Technical Debt
- Badge refresh required manual testing to identify savedState issue
- Deduplication process failure mode not well documented
- Feature table architecture (dual tables) may confuse new developers
- No automated tests for badge display logic

---

## Migration Guide

### Upgrading to 1.0.0

**Database Migration**:
```bash
cd backend
python migrate_add_product_features.py
```

This creates the `product_features` table without affecting existing data.

**API Changes**:
- New endpoint: `GET /product-intelligence/products/{product_id}/detailed-features`
- Existing endpoints unchanged (backward compatible)

**Frontend Changes**:
- No breaking changes
- Badge and extraction list fixes automatic
- Enhanced logging visible in browser console

**Testing**:
```bash
# Test detailed features
cd backend
source venv/bin/activate
python test_detailed_features.py

# Full test suite
./setup_and_test.sh
```

---

## Known Issues

### Fixed in 1.0.0
- ✅ Features Ready badge not showing on return from Stage 3
- ✅ Domo badge not showing (dual-table architecture issue)
- ✅ Extraction list showing deselected competitors
- ✅ Vague extraction mode text (now shows specific counts)
- ✅ Misleading "(Instant)" label when extraction needed

### In Progress
- None

### Future Enhancements
- Automated deduplication retry mechanism
- Background job for orphaned feature deduplication
- Unified feature check helper function across all endpoints
- Automated tests for badge display logic
- Performance monitoring for large feature sets

---

## Acknowledgments

- **AI Engine**: Powered by Anthropic Claude 4.5
- **Vector Search**: sentence-transformers/all-MiniLM-L6-v2
- **Framework**: FastAPI + React + TypeScript

---

For detailed technical documentation, see:
- [docs/USER_GUIDE.md](docs/USER_GUIDE.md) - Comprehensive user guide
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - System architecture
- [docs/development/](docs/development/) - Development documentation
