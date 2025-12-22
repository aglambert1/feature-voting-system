# Shell Scripts Analysis & Recommendations

## Executive Summary

The three shell scripts (`verify.sh`, `start.sh`, `setup_and_test.sh`) are **generally well-designed and functional** with the current codebase. However, several enhancements are recommended to make them more robust, comprehensive, and aligned with recent development changes.

**Status:**
- ✅ `verify.sh` - Works correctly, minor enhancements recommended
- ✅ `start.sh` - Works correctly, needs log rotation and health checks
- ⚠️ `setup_and_test.sh` - Works but doesn't leverage pytest, missing new test files

---

## Detailed Analysis

### 1. verify.sh - Quick Verification Script

**Current Functionality:**
- Checks for virtual environment (backend/venv)
- Verifies .env files exist (backend/.env, frontend/.env)
- Tests Python imports (can import app.main)
- Validates package files (requirements.txt, package.json)

**What It Does Well:**
- Fast execution (< 5 seconds)
- Clear color-coded output
- Non-destructive (no changes to system)
- Good error messages

**Issues Found:**
1. ❌ **Doesn't validate .env contents** - Only checks if file exists, not if required variables are set
2. ❌ **Missing database check** - Doesn't verify if database file exists or is initialized
3. ❌ **No API key validation** - Doesn't check if ANTHROPIC_API_KEY is set (critical for CI features)
4. ❌ **Import test only checks main app** - Doesn't verify competitive intelligence modules
5. ⚠️ **Hardcoded Python imports** - Imports specific models that may change

**Recommendations:**

#### High Priority:
1. **Validate critical environment variables:**
   ```bash
   # Check ANTHROPIC_API_KEY is set
   if grep -q "ANTHROPIC_API_KEY=your-anthropic-api-key-here" "${BACKEND_DIR}/.env" ||
      ! grep -q "ANTHROPIC_API_KEY=" "${BACKEND_DIR}/.env"; then
       print_warning "ANTHROPIC_API_KEY not configured - Competitive Intelligence features will not work"
   fi
   ```

2. **Check database initialization:**
   ```bash
   # Check if database exists and has tables
   if [ -f "${BACKEND_DIR}/feature_voting.db" ]; then
       TABLE_COUNT=$(sqlite3 "${BACKEND_DIR}/feature_voting.db" \
           "SELECT COUNT(*) FROM sqlite_master WHERE type='table';" 2>/dev/null || echo "0")
       if [ "$TABLE_COUNT" -gt 0 ]; then
           print_success "Database exists with $TABLE_COUNT tables"
       else
           print_warning "Database file exists but appears empty - may need initialization"
       fi
   else
       print_warning "Database not initialized - will be created on first run"
   fi
   ```

3. **Add more comprehensive import test:**
   ```bash
   # Test competitive intelligence imports
   python3 << 'EOF'
   import sys
   try:
       sys.path.insert(0, '.')
       from app.main import app
       from app.agents.base_agent import BaseAgent
       from app.services.llm_service import llm_service
       from app.models.competitor_intelligence import CIProduct
       print("\033[0;32m✓\033[0m All critical modules can be imported")
   except Exception as e:
       print(f"\033[0;31m✗\033[0m Import error: {e}")
       sys.exit(1)
   EOF
   ```

#### Medium Priority:
4. **Add version checks:**
   ```bash
   # Check Python version (requires 3.12+)
   PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
   if [[ $(echo "$PYTHON_VERSION 3.12" | awk '{print ($1 >= $2)}') -eq 1 ]]; then
       print_success "Python version: $PYTHON_VERSION"
   else
       print_error "Python 3.12+ required, found: $PYTHON_VERSION"
   fi

   # Check Node version (requires 18+)
   NODE_VERSION=$(node --version | cut -d'v' -f2)
   if [[ $(echo "$NODE_VERSION 18.0.0" | awk '{print ($1 >= $2)}') -eq 1 ]]; then
       print_success "Node version: $NODE_VERSION"
   else
       print_error "Node 18+ required, found: $NODE_VERSION"
   fi
   ```

5. **Check for port conflicts:**
   ```bash
   # Check if ports 8000 and 5173 are available
   if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
       print_warning "Port 8000 already in use - backend may fail to start"
   fi
   if lsof -Pi :5173 -sTCP:LISTEN -t >/dev/null 2>&1; then
       print_warning "Port 5173 already in use - frontend may fail to start"
   fi
   ```

---

### 2. start.sh - Development Server Launcher

**Current Functionality:**
- Starts backend (uvicorn) and frontend (vite) in background
- Logs to /tmp/backend.log and /tmp/frontend.log
- Graceful shutdown on Ctrl+C
- PID tracking for process management

**What It Does Well:**
- Clean startup/shutdown
- Clear status messages
- Simultaneous server management
- Good error handling

**Issues Found:**
1. ❌ **Logs overwrite on each run** - No log rotation or timestamps
2. ❌ **No health check** - Doesn't verify servers are actually responding
3. ❌ **Fixed sleep timers** - May not be enough on slow systems
4. ❌ **No database migration check** - Doesn't warn if schema is outdated
5. ⚠️ **Log files in /tmp** - May be cleared on system reboot
6. ⚠️ **No way to view logs interactively** - User must tail manually

**Recommendations:**

#### High Priority:
1. **Implement log rotation with timestamps:**
   ```bash
   # Create logs directory if it doesn't exist
   mkdir -p "${PROJECT_ROOT}/logs"

   # Use timestamped log files
   TIMESTAMP=$(date +%Y%m%d_%H%M%S)
   BACKEND_LOG="${PROJECT_ROOT}/logs/backend_${TIMESTAMP}.log"
   FRONTEND_LOG="${PROJECT_ROOT}/logs/frontend_${TIMESTAMP}.log"

   # Also create symlinks to latest logs
   ln -sf "$BACKEND_LOG" "${PROJECT_ROOT}/logs/backend_latest.log"
   ln -sf "$FRONTEND_LOG" "${PROJECT_ROOT}/logs/frontend_latest.log"

   # Start servers with new log paths
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 > "$BACKEND_LOG" 2>&1 &
   ```

2. **Add health checks instead of fixed sleep:**
   ```bash
   # Wait for backend to be healthy (max 30 seconds)
   print_step "Waiting for backend to be healthy..."
   for i in {1..30}; do
       if curl -s http://localhost:8000/health > /dev/null 2>&1; then
           print_success "Backend is healthy"
           break
       fi
       if [ $i -eq 30 ]; then
           print_error "Backend failed to become healthy in 30 seconds"
           cat "$BACKEND_LOG"
           cleanup
           exit 1
       fi
       sleep 1
   done
   ```

3. **Add database migration check:**
   ```bash
   # Check if database needs migration
   print_step "Checking database status..."
   cd "${BACKEND_DIR}"
   source venv/bin/activate

   # Simple check: count expected tables
   EXPECTED_TABLES=11  # Update this if schema changes
   ACTUAL_TABLES=$(sqlite3 feature_voting.db \
       "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';" \
       2>/dev/null || echo "0")

   if [ "$ACTUAL_TABLES" -lt "$EXPECTED_TABLES" ]; then
       print_warning "Database may need migration (found $ACTUAL_TABLES/$EXPECTED_TABLES tables)"
       print_warning "Consider running: cd backend && python reset_db.py"
   fi
   ```

#### Medium Priority:
4. **Add interactive log viewing option:**
   ```bash
   # After servers start, offer to show logs
   echo ""
   echo "Available commands:"
   echo "  l  - View logs (tail -f both servers)"
   echo "  b  - View backend logs only"
   echo "  f  - View frontend logs only"
   echo "  q  - Quit (stop servers)"
   echo ""

   # Simple command loop
   while true; do
       read -t 1 -n 1 cmd 2>/dev/null
       case $cmd in
           l) tail -f "$BACKEND_LOG" "$FRONTEND_LOG" ;;
           b) tail -f "$BACKEND_LOG" ;;
           f) tail -f "$FRONTEND_LOG" ;;
           q) cleanup ;;
       esac
   done
   ```

5. **Add automatic browser opening:**
   ```bash
   # After frontend starts successfully
   if command -v open > /dev/null 2>&1; then
       print_step "Opening browser..."
       sleep 1
       open http://localhost:5173
   fi
   ```

6. **Implement log cleanup:**
   ```bash
   # At startup, clean old logs (keep last 10)
   if [ -d "${PROJECT_ROOT}/logs" ]; then
       find "${PROJECT_ROOT}/logs" -name "*.log" -type f -mtime +7 -delete 2>/dev/null
       OLD_COUNT=$(find "${PROJECT_ROOT}/logs" -name "*.log" -type f | wc -l)
       if [ "$OLD_COUNT" -gt 20 ]; then
           print_warning "Many old log files found ($OLD_COUNT). Consider cleaning logs directory."
       fi
   fi
   ```

---

### 3. setup_and_test.sh - Complete Setup Script

**Current Functionality:**
- Checks prerequisites (python3, node, npm)
- Creates virtual environment
- Installs backend dependencies
- Runs backend tests (imports, schema validation, API endpoints)
- Installs frontend dependencies
- Runs frontend build and lint tests
- Comprehensive output with color coding

**What It Does Well:**
- Thorough prerequisite checking
- Clean reinstall capability
- Database backup before reset
- Good test coverage for basic functionality
- Helpful final summary

**Issues Found:**
1. ❌ **Doesn't use pytest** - Runs individual test files instead of pytest suite
2. ❌ **Missing new test directories** - Doesn't run tests in backend/tests/
3. ❌ **Doesn't test competitive intelligence** - No tests for CI features
4. ❌ **Schema test may not exist** - References test_schemas.py which may be outdated
5. ⚠️ **Hardcoded Python 3.12** - Should detect available version
6. ⚠️ **No parallel testing** - Tests run sequentially (slow)
7. ⚠️ **Frontend build is slow** - No skip option for quick setup

**Recommendations:**

#### High Priority:
1. **Use pytest for comprehensive testing:**
   ```bash
   # Replace individual test file execution with pytest
   print_step "Running pytest test suite..."
   cd "${BACKEND_DIR}"
   source venv/bin/activate

   # Run all tests with pytest
   pytest -v --tb=short --maxfail=5 tests/ || {
       print_warning "Some tests failed - check output above"
       print_warning "This is not critical for setup, but should be investigated"
   }

   # Run specific test modules if they exist
   if [ -f "test_schemas.py" ]; then
       pytest -v test_schemas.py
   fi

   # Summary
   TEST_RESULTS=$(pytest --collect-only -q 2>&1 | grep -E "test session|error")
   print_success "Test discovery: $TEST_RESULTS"
   ```

2. **Add competitive intelligence tests:**
   ```bash
   # Test CI module imports and basic functionality
   print_step "Testing Competitive Intelligence modules..."
   python3 << 'EOF'
   import sys
   try:
       sys.path.insert(0, '.')
       # Import all CI components
       from app.agents.product_analyzer import ProductAnalyzerAgent
       from app.agents.competitor_researcher import CompetitorResearcherAgent
       from app.agents.feature_extractor import FeatureExtractorAgent
       from app.services.feature_extraction_service import FeatureExtractionService
       from app.models.competitor_intelligence import (
           CIProduct, CompetitorAnalysisSession, ProductCompetitor
       )
       print("✓ All Competitive Intelligence modules imported successfully")
   except Exception as e:
       print(f"✗ CI module import error: {e}")
       sys.exit(1)
   EOF
   ```

3. **Detect Python version instead of hardcoding:**
   ```bash
   # Find best available Python version
   print_step "Detecting Python version..."

   if command_exists python3.12; then
       PYTHON_CMD="python3.12"
   elif command_exists python3.11; then
       PYTHON_CMD="python3.11"
       print_warning "Python 3.12 preferred, but 3.11 found - should work"
   elif command_exists python3; then
       PYTHON_CMD="python3"
       PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
       if [[ $(echo "$PYTHON_VERSION 3.11" | awk '{print ($1 >= $2)}') -eq 1 ]]; then
           print_success "Using Python $PYTHON_VERSION"
       else
           print_error "Python 3.11+ required, found: $PYTHON_VERSION"
           exit 1
       fi
   else
       print_error "Python 3 not found"
       exit 1
   fi

   # Use detected Python command
   $PYTHON_CMD -m venv venv
   ```

4. **Add quick setup mode:**
   ```bash
   # Accept --quick flag to skip slow tests
   QUICK_MODE=false
   if [[ "$1" == "--quick" ]]; then
       QUICK_MODE=true
       print_warning "Quick mode: Skipping frontend build test"
   fi

   # Later in script
   if [ "$QUICK_MODE" = false ]; then
       print_step "Test 1: Testing frontend build (this may take a minute)..."
       npm run build --silent
   else
       print_step "Skipping frontend build test (quick mode)"
   fi
   ```

#### Medium Priority:
5. **Add parallel test execution:**
   ```bash
   # Run tests in parallel with pytest-xdist
   print_step "Running tests in parallel..."
   pytest -n auto -v tests/ || print_warning "Some tests failed"
   ```

6. **Validate ANTHROPIC_API_KEY:**
   ```bash
   # After creating .env, validate API key format
   if [ -f ".env" ]; then
       API_KEY=$(grep "^ANTHROPIC_API_KEY=" .env | cut -d'=' -f2)
       if [[ "$API_KEY" == "your-anthropic-api-key-here" ]] || [[ -z "$API_KEY" ]]; then
           print_error "ANTHROPIC_API_KEY not configured in .env"
           print_error "Competitive Intelligence features will NOT work!"
           print_warning "Get your API key from: https://console.anthropic.com/"
           read -p "Press Enter to continue anyway, or Ctrl+C to exit..."
       elif [[ ! "$API_KEY" =~ ^sk-ant- ]]; then
           print_warning "API key doesn't match expected format (should start with 'sk-ant-')"
       else
           print_success "ANTHROPIC_API_KEY configured"
       fi
   fi
   ```

7. **Add test result summary:**
   ```bash
   # At end of script, create test report
   echo ""
   echo -e "${BLUE}Test Results Summary:${NC}"
   echo "---------------------"

   # Count tests
   TOTAL_TESTS=$(pytest --collect-only -q 2>&1 | grep -oE "[0-9]+ tests" | cut -d' ' -f1)
   PASSED_TESTS=$(pytest --tb=no -q 2>&1 | grep -oE "[0-9]+ passed" | cut -d' ' -f1 || echo "0")
   FAILED_TESTS=$(pytest --tb=no -q 2>&1 | grep -oE "[0-9]+ failed" | cut -d' ' -f1 || echo "0")

   print_success "Total tests: $TOTAL_TESTS"
   if [ "$PASSED_TESTS" -gt 0 ]; then
       print_success "Passed: $PASSED_TESTS"
   fi
   if [ "$FAILED_TESTS" -gt 0 ]; then
       print_error "Failed: $FAILED_TESTS"
   fi
   ```

---

## New Script Recommendations

### 4. test.sh - Dedicated Test Runner (NEW)

Create a new script specifically for running tests during development:

```bash
#!/bin/bash
# test.sh - Run project tests

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${PROJECT_ROOT}/backend"

# Parse arguments
VERBOSE=false
COVERAGE=false
SPECIFIC_TEST=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose) VERBOSE=true; shift ;;
        -c|--coverage) COVERAGE=true; shift ;;
        *) SPECIFIC_TEST="$1"; shift ;;
    esac
done

cd "${BACKEND_DIR}"
source venv/bin/activate

echo "Running tests..."

if [ -n "$SPECIFIC_TEST" ]; then
    # Run specific test
    pytest -v "$SPECIFIC_TEST"
elif [ "$COVERAGE" = true ]; then
    # Run with coverage
    pytest --cov=app --cov-report=html --cov-report=term tests/
    echo "Coverage report: ${BACKEND_DIR}/htmlcov/index.html"
elif [ "$VERBOSE" = true ]; then
    # Run all tests verbosely
    pytest -v tests/
else
    # Run all tests with summary
    pytest tests/
fi
```

### 5. check_health.sh - System Health Check (NEW)

```bash
#!/bin/bash
# check_health.sh - Verify system health

# Check if servers are running
echo "Checking server health..."

# Backend
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✓ Backend healthy"
else
    echo "✗ Backend not responding"
fi

# Frontend
if curl -s http://localhost:5173 > /dev/null 2>&1; then
    echo "✓ Frontend healthy"
else
    echo "✗ Frontend not responding"
fi

# Database
if [ -f "backend/feature_voting.db" ]; then
    TABLES=$(sqlite3 backend/feature_voting.db \
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table';" 2>/dev/null)
    echo "✓ Database: $TABLES tables"
else
    echo "✗ Database not found"
fi

# API Key
if grep -q "ANTHROPIC_API_KEY=sk-ant-" backend/.env 2>/dev/null; then
    echo "✓ API key configured"
else
    echo "⚠ API key not configured"
fi
```

---

## Migration Path

### Immediate Actions (Do First):
1. ✅ Add .env validation to verify.sh
2. ✅ Add database check to verify.sh
3. ✅ Switch setup_and_test.sh to use pytest
4. ✅ Add health checks to start.sh
5. ✅ Implement log rotation in start.sh

### Short-term (Next Week):
6. Create test.sh for development testing
7. Create check_health.sh for quick health checks
8. Add ANTHROPIC_API_KEY validation to setup_and_test.sh
9. Add Python version detection to setup_and_test.sh

### Long-term (Next Month):
10. Add interactive log viewer to start.sh
11. Implement parallel testing in setup_and_test.sh
12. Add CI/CD integration tests
13. Create deployment scripts

---

## Testing Recommendations

### Current Test Suite Status:
```
backend/tests/
├── test_base_agent.py (9,379 bytes)
├── test_ci_models.py (15,610 bytes)
├── test_feature_extraction.py (34,159 bytes) ← NEW, not in scripts
├── test_feature_extraction_api.py (19,326 bytes) ← NEW, not in scripts
├── test_llm_service_extended.py (8,898 bytes)
└── test_product_analyzer.py (3,470 bytes)

backend/ (root level)
├── test_api.py (5,421 bytes) ← Referenced in setup script
├── test_schemas.py (4,545 bytes) ← Referenced in setup script
├── test_complete_api.py (15,826 bytes)
├── test_knowledge_only.py (3,869 bytes) ← NEW
└── test_search.py (3,657 bytes) ← NEW
```

**Key Finding:** The setup script runs individual files but misses:
- All tests in backend/tests/ directory
- Newer test files (test_knowledge_only.py, test_search.py)
- Feature extraction tests (34 tests passing per docs)

**Recommended pytest command:**
```bash
# Run ALL tests
pytest -v tests/ test_*.py

# Or with coverage
pytest --cov=app --cov-report=html tests/ test_*.py

# Quick smoke test
pytest -v -k "not slow" tests/
```

---

## Summary of Changes Needed

### verify.sh (5 changes):
1. ✅ Add .env validation (ANTHROPIC_API_KEY check)
2. ✅ Add database existence and table count check
3. ✅ Add comprehensive import test (include CI modules)
4. ✅ Add Python/Node version checks
5. ✅ Add port conflict detection

### start.sh (6 changes):
1. ✅ Implement timestamped log rotation
2. ✅ Replace fixed sleep with health checks
3. ✅ Add database migration warning
4. ⚠️ Optional: Interactive log viewer
5. ⚠️ Optional: Auto-open browser
6. ✅ Log cleanup on startup

### setup_and_test.sh (7 changes):
1. ✅ Replace individual test runs with pytest
2. ✅ Add tests from backend/tests/ directory
3. ✅ Add CI module import tests
4. ✅ Auto-detect Python version (not hardcode 3.12)
5. ✅ Add ANTHROPIC_API_KEY validation
6. ⚠️ Add --quick flag for fast setup
7. ✅ Add test result summary

### New Scripts:
1. ⚠️ test.sh - Dedicated test runner with coverage
2. ⚠️ check_health.sh - Quick health check utility

**Legend:**
- ✅ High priority, should implement
- ⚠️ Medium priority, nice to have
- ❌ Current issue/problem

---

## Conclusion

The scripts are functional but outdated. The most critical updates needed are:

1. **setup_and_test.sh** - Switch to pytest to run all 34 tests (currently missing)
2. **verify.sh** - Add API key and database validation (critical for CI features)
3. **start.sh** - Add health checks and log rotation (improves reliability)

Implementing these changes will make the development workflow more robust and catch issues earlier.
