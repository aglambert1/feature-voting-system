# Test Scripts

Manual integration test scripts for specific API features and workflows.

## Overview

These scripts provide quick, manual testing of specific backend endpoints and workflows. They are designed for:
- Manual verification during development
- Quick smoke tests after changes
- Debugging specific features
- Integration testing of API workflows

**Note:** These are manual test utilities, not automated test suites. For automated testing, see `backend/tests/` and use pytest.

---

## Available Tests

### `test_edit.sh`

**Purpose:** Quick test of competitive intelligence idea editing endpoint

**What it tests:**
- Authentication (admin login)
- Fetching generated ideas from a session
- Editing idea fields (what, why, use_case)
- API response format

**Requirements:**
- Backend server running on `http://localhost:8000`
- Session 9999 must exist with generated ideas
- Admin credentials: `admin/password`

**Usage:**
```bash
./scripts/tests/test_edit.sh
```

**Expected Output:**
```
IDEA_ID: 42
{
  "id": 42,
  "what": "EDITED WHAT",
  "why": "EDITED WHY",
  "use_case": "EDITED USE CASE",
  ...
}
```

---

### `test_module7_simple.sh`

**Purpose:** Comprehensive integration test for Module 7 (Competitive Intelligence workflow)

**What it tests:**
Complete end-to-end workflow:
1. **Test Data Setup** - Creates session 9999 with test product, competitors, and features
2. **Authentication** - Gets JWT token for admin user
3. **Generate Ideas** - `POST /competitor-intelligence/sessions/9999/generate-ideas`
4. **Get Generated Ideas** - `GET /competitor-intelligence/sessions/9999/generated-ideas`
5. **Edit Ideas** - `PUT /competitor-intelligence/generated-ideas/{id}`
6. **Approve Ideas** - `POST /competitor-intelligence/generated-ideas/approve`
7. **Finalize Session** - `POST /competitor-intelligence/sessions/9999/finalize`
8. **Verify Database** - Checks ideas exist in SQLite database
9. **Cleanup** - Removes all test data

**Requirements:**
- Backend server running on `http://localhost:8000`
- SQLite database accessible at `backend/feature_voting.db`
- Admin credentials: `admin/password`
- Anthropic API key configured (for AI idea generation)

**Runtime:** 5-10 seconds (depends on AI generation time)

**Usage:**
```bash
./scripts/tests/test_module7_simple.sh
```

**Expected Output:**
```
============================================================
  MODULE 7: SIMPLE INTEGRATION TEST
============================================================

Setting up test data in database...
✅ Test data created

Getting authentication token...
✅ Got auth token

Testing: Generate Ideas Endpoint
Status: completed
Ideas: 3
✅ PASSED

Testing: Get Generated Ideas Endpoint
Found 3 ideas
✅ PASSED

Testing: Edit Generated Idea Endpoint
Response: dict_keys([...])
✅ PASSED

Testing: Approve Ideas Endpoint
Approved: 3
✅ PASSED

Testing: Finalize & Submit to Voting System
Status: success
Submitted: 3
✅ PASSED

Testing: Verify Ideas in Database
Competitor ideas in DB: 3
✅ PASSED

============================================================
  TEST SUMMARY
============================================================
✅ All Module 7 endpoints working correctly!

Cleanup: Removing test data...
✅ Cleanup complete
```

---

## Running Tests

### From Project Root

**Run individual test:**
```bash
./scripts/tests/test_edit.sh
./scripts/tests/test_module7_simple.sh
```

**Run all tests:**
```bash
for test in ./scripts/tests/test_*.sh; do
    echo "Running $test..."
    "$test"
    echo ""
done
```

---

### From scripts/tests Directory

```bash
cd scripts/tests
./test_edit.sh
./test_module7_simple.sh
```

---

## Prerequisites

Before running these tests, ensure:

1. **Backend server is running:**
   ```bash
   cd backend
   source venv/bin/activate
   uvicorn app.main:app --reload
   ```

2. **Database exists:**
   - Database file should exist at `backend/feature_voting.db`
   - Will be created automatically on first backend startup

3. **Admin user exists:**
   - Username: `admin`
   - Password: `password`
   - Created automatically on first backend startup

4. **Environment configured:**
   - `backend/.env` exists with valid `ANTHROPIC_API_KEY`
   - Required for AI-powered idea generation in Module 7 test

---

## Troubleshooting

### "Connection refused" errors

**Problem:** Backend server not running

**Solution:**
```bash
# Check if backend is running
curl http://localhost:8000/

# If not, start it
cd backend
source venv/bin/activate
uvicorn app.main:app --reload
```

---

### "Failed to get auth token"

**Problem:** Admin user doesn't exist or credentials wrong

**Solution:**
```bash
# Check backend logs for user creation
# Admin user should be created automatically on startup

# Or reset database to recreate admin user
cd backend
rm feature_voting.db
# Restart backend - database and admin user will be recreated
```

---

### "Session 9999 not found" (test_edit.sh)

**Problem:** Test session doesn't exist

**Solution:**
Run `test_module7_simple.sh` first - it creates the test data, or manually create session 9999 with ideas.

---

### "No ideas found" errors

**Problem:** AI generation may have failed or returned no ideas

**Solution:**
```bash
# Check Anthropic API key is configured
cat backend/.env | grep ANTHROPIC_API_KEY

# Check backend logs for AI errors
tail -f logs/backend_latest.log

# Verify API key is valid at https://console.anthropic.com/
```

---

## Adding New Test Scripts

When creating new test scripts:

1. **Create script** in `scripts/tests/`
   ```bash
   touch scripts/tests/test_new_feature.sh
   chmod +x scripts/tests/test_new_feature.sh
   ```

2. **Follow naming convention:** `test_<feature>.sh`

3. **Use standard format:**
   ```bash
   #!/bin/bash
   # Brief description of what this tests

   set -e  # Exit on error

   # Authentication
   TOKEN=$(curl -s -X POST "http://localhost:8000/auth/login" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=admin&password=password" | \
     python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

   # Test your endpoint
   curl -s -X GET "http://localhost:8000/your-endpoint" \
     -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
   ```

4. **Document in this README:**
   - Add section describing the test
   - Include purpose, requirements, usage
   - Add expected output example

5. **Test it thoroughly:**
   ```bash
   ./scripts/tests/test_new_feature.sh
   ```

---

## Relationship to Automated Tests

These manual test scripts complement (but don't replace) the automated test suite:

**Manual Test Scripts (`scripts/tests/`):**
- Quick manual verification
- Integration testing with real backend
- Debugging specific workflows
- Easy to run for smoke tests

**Automated Tests (`backend/tests/`):**
- Comprehensive test coverage
- Run in CI/CD pipeline
- Unit and integration tests
- Automated regression testing

**Best Practice:**
- Use manual scripts during development for quick checks
- Use automated tests (pytest) for comprehensive validation
- Run both before committing significant changes

**Run automated tests:**
```bash
cd backend
source venv/bin/activate
pytest -v tests/
```

---

## See Also

- [SCRIPTS.md](../../SCRIPTS.md) - Complete automation scripts reference
- [TESTING_GUIDE.md](../../TESTING_GUIDE.md) - Comprehensive testing documentation
- `backend/tests/` - Automated test suite (pytest)

---

**Last Updated:** 2025-12-19
