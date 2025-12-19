# Development Scripts Guide

Complete reference for all automation scripts in the Feature Voting System project.

## Quick Start

```bash
# First time setup
./setup_and_test.sh          # Full initialization (2-5 min)

# Daily development
./start.sh                   # Start both servers (5 sec)
./verify.sh                  # Quick health check (1-2 sec)

# Server management
./check_servers.sh           # Check server status
./kill_servers.sh            # Stop all servers
```

---

## Core Scripts

### 1. Setup Scripts

#### `setup_and_test.sh` - Complete System Initialization

**Purpose:** Full system setup from scratch with comprehensive testing

**When to use:**
- First time setup
- After major changes
- When environment is broken
- After pulling updates from repository

**What it does:**
1. Checks prerequisites (Python 3.11+, Node.js 18+)
2. Removes old backend virtual environment
3. Creates fresh venv and installs dependencies
4. Fixes bcrypt compatibility
5. Validates `.env` files and ANTHROPIC_API_KEY
6. Backs up and resets database
7. Runs backend tests:
   - Python imports
   - FastAPI initialization
   - Pytest test suite
   - Starts test server
   - Tests API endpoints
   - Tests product-centric workflow
8. Removes old node_modules
9. Installs frontend dependencies
10. Runs frontend tests:
    - Build test
    - ESLint
    - Validates dist directory
11. Cleans up test database

**Runtime:** 2-5 minutes (depending on download speeds)

**Output:**
- Colored progress indicators
- Test results summary
- Next steps instructions

**Example:**
```bash
./setup_and_test.sh
# Follow prompts if ANTHROPIC_API_KEY not configured
# Wait for all tests to complete
# System ready for development
```

---

#### `verify.sh` - Quick Environment Verification

**Purpose:** Fast health check without full reinstall

**When to use:**
- Before starting development
- After system restart
- To diagnose issues quickly
- Before running tests

**What it checks:**
1. Python version (3.11+)
2. Node.js version (18+)
3. Backend venv exists and has packages
4. Frontend node_modules exists
5. Required Python modules import correctly
6. Database file exists
7. `.env` files exist

**Runtime:** 1-2 seconds

**Exit codes:**
- `0` - Everything OK
- `1` - Critical issue found

**Example:**
```bash
./verify.sh
# ✓ Python 3.12 found
# ✓ Node.js 20.x found
# ✓ Backend venv exists (45 packages)
# ✓ Frontend node_modules exists
# ✓ All imports successful
# ✓ Database exists
# ✓ Environment files exist
```

---

### 2. Server Management Scripts

#### `start.sh` - Start Development Servers

**Purpose:** Start both backend and frontend servers with duplicate detection

**When to use:**
- Daily development workflow
- After stopping servers
- After system restart

**Features:**
- **Duplicate Detection:** Checks if servers already running
- **Interactive Menu:** Choose action if duplicates found
  1. Stop existing and start fresh (recommended)
  2. Keep existing running
  3. Try to start anyway (may fail)
- **Terminal Management:** Uses separate terminals for clean output
- **Activation Handling:** Auto-activates backend venv

**What it does:**
1. Checks for existing servers on ports 8000 and 5173
2. Shows interactive menu if servers found
3. Opens backend terminal (with venv activated)
4. Starts `uvicorn app.main:app --reload` on port 8000
5. Opens frontend terminal
6. Starts `npm run dev` on port 5173
7. Displays access URLs

**Runtime:** ~5 seconds

**Requirements:**
- Backend venv must exist
- Frontend node_modules must exist
- Ports 8000 and 5173 available (or user chooses to stop existing)

**Example:**
```bash
./start.sh
# ⚠  WARNING: Servers already running!
#   Backend: 2 processes on port 8000 (PIDs: 12345, 12346)
#   Frontend: 1 process on port 5173 (PID: 12347)
#
# What would you like to do?
#   1) Stop existing servers and start fresh (recommended)
#   2) Exit and keep existing servers running
#   3) Try to start anyway (may fail if ports occupied)
# Choose (1-3): 1
#
# ✓ Existing servers stopped
# Starting servers...
```

---

#### `check_servers.sh` - Check Server Status

**Purpose:** Display status of running servers without starting/stopping

**When to use:**
- To see if servers are running
- To find PIDs of running processes
- To detect duplicate server instances
- Before starting new servers

**What it shows:**
- Backend processes on port 8000
- Frontend processes on port 5173
- PIDs for each process
- Warning if multiple instances detected

**Runtime:** < 1 second

**Example:**
```bash
./check_servers.sh
# ===================================================
#   SERVER STATUS
# ===================================================
#
# Backend (Port 8000):
# ✓ Running (PID: 12345)
#
# Frontend (Port 5173):
# ✓ Running (PID: 67890)
#
# ===================================================
# ✓ Both servers running normally
```

**With duplicates:**
```bash
./check_servers.sh
# Backend (Port 8000):
# ✓ Running (PIDs: 12345, 12346, 12347)
# ⚠  WARNING: Multiple backend instances detected!
#   This is unusual and may cause issues.
```

---

#### `kill_servers.sh` - Stop All Servers

**Purpose:** Stop all backend and frontend server processes

**When to use:**
- End of development session
- Before running `setup_and_test.sh`
- To clear redundant server instances
- Before system shutdown

**What it does:**
1. Kills all processes on port 8000 (backend)
2. Kills all processes on port 5173 (frontend)
3. Cleans up orphaned uvicorn processes
4. Cleans up orphaned vite processes

**Runtime:** < 1 second

**Example:**
```bash
./kill_servers.sh
# ===================================================
#   STOPPING SERVERS
# ===================================================
#
# ✓ Backend stopped (port 8000)
# ✓ Frontend stopped (port 5173)
# ✓ Uvicorn processes cleaned up
# ✓ Vite processes cleaned up
#
# ===================================================
# ✓ All servers stopped successfully
```

---

### 3. Utility Scripts

#### `fix_bcrypt.sh` - Fix bcrypt Compatibility

**Purpose:** Fix "password cannot be longer than 72 bytes" error

**When to use:**
- After fresh venv creation if bcrypt version incompatible
- When getting bcrypt-related errors during user registration
- Automatically run by `setup_and_test.sh`

**What it does:**
1. Stops running servers
2. Activates backend venv
3. Uninstalls current bcrypt
4. Installs bcrypt 4.0.1 (compatible with passlib)
5. Tests password hashing and verification
6. Deactivates venv

**Runtime:** 10-15 seconds

**Example:**
```bash
./fix_bcrypt.sh
# ╔══════════════════════════════════════════════════════════╗
# ║         Fixing bcrypt Compatibility Issue               ║
# ╚══════════════════════════════════════════════════════════╝
#
# Current bcrypt version: 4.2.1
# Installing compatible bcrypt version...
# ✓ bcrypt 4.0.1 installed
#
# Testing password hashing...
# ✓ Password hashing and verification work correctly!
#   Sample hash: $2b$12$abc123...
#
# ╔══════════════════════════════════════════════════════════╗
# ║                Fix Complete!                             ║
# ╚══════════════════════════════════════════════════════════╝
```

---

### 4. Testing Scripts

#### `scripts/tests/test_edit.sh` - Test Idea Editing Endpoint

**Purpose:** Quick test of competitive intelligence idea editing

**When to use:**
- Manual testing of idea editing functionality
- Debugging editing issues
- Verifying generated idea endpoints

**What it does:**
1. Authenticates as admin
2. Fetches generated ideas from session 9999
3. Edits the first idea with test data
4. Displays formatted JSON response

**Requirements:**
- Backend server running
- Session 9999 with generated ideas exists

**Runtime:** < 1 second

**Example:**
```bash
./scripts/tests/test_edit.sh
# IDEA_ID: 42
# {
#   "id": 42,
#   "what": "EDITED WHAT",
#   "why": "EDITED WHY",
#   "use_case": "EDITED USE CASE",
#   ...
# }
```

---

#### `scripts/tests/test_module7_simple.sh` - Module 7 Integration Test

**Purpose:** Comprehensive integration test for competitive intelligence workflow

**When to use:**
- After implementing Module 7 changes
- Before committing CI-related code
- Regression testing

**What it tests:**
1. **Test data creation:** Creates session 9999 with competitors and features
2. **Authentication:** Gets admin JWT token
3. **Generate ideas:** POST /sessions/9999/generate-ideas
4. **Get generated ideas:** GET /sessions/9999/generated-ideas
5. **Edit idea:** PUT /generated-ideas/{id}
6. **Approve ideas:** POST /generated-ideas/approve
7. **Finalize session:** POST /sessions/9999/finalize
8. **Verify database:** Checks ideas in SQLite database
9. **Cleanup:** Removes all test data

**Requirements:**
- Backend server running on port 8000
- SQLite database accessible
- Admin credentials (admin/password)

**Runtime:** 5-10 seconds (depends on AI generation)

**Example:**
```bash
./scripts/tests/test_module7_simple.sh
# ============================================================
#   MODULE 7: SIMPLE INTEGRATION TEST
# ============================================================
#
# Setting up test data in database...
# ✅ Test data created
#
# Getting authentication token...
# ✅ Got auth token
#
# Testing: Generate Ideas Endpoint
# Status: completed
# Ideas: 3
# ✅ PASSED
#
# Testing: Get Generated Ideas Endpoint
# Found 3 ideas
# ✅ PASSED
#
# [... more tests ...]
#
# ============================================================
#   TEST SUMMARY
# ============================================================
# ✅ All Module 7 endpoints working correctly!
#
# Cleanup: Removing test data...
# ✅ Cleanup complete
```

---

## Workflow Patterns

### First Time Setup

```bash
# 1. Clone repository
git clone <repo-url>
cd feature-voting-system

# 2. Run full setup and test
./setup_and_test.sh

# 3. Add your Anthropic API key
nano backend/.env
# ANTHROPIC_API_KEY=sk-ant-your-key-here

# 4. Verify everything works
./verify.sh

# 5. Start servers
./start.sh
```

---

### Daily Development

```bash
# Morning startup
./verify.sh              # Quick health check
./start.sh               # Start servers

# During development
./check_servers.sh       # Check server status if issues
./kill_servers.sh        # Restart if needed
./start.sh

# End of day
./kill_servers.sh        # Stop servers
```

---

### After Pulling Updates

```bash
# Stop servers
./kill_servers.sh

# Full rebuild (if dependencies changed)
./setup_and_test.sh

# Or quick verify (if only code changed)
./verify.sh
./start.sh
```

---

### Troubleshooting

```bash
# Problem: Servers won't start
./check_servers.sh       # Check for duplicates
./kill_servers.sh        # Stop all
./start.sh               # Restart

# Problem: Import errors
./verify.sh              # Diagnose issue
./setup_and_test.sh      # Full rebuild if needed

# Problem: bcrypt errors
./fix_bcrypt.sh          # Fix bcrypt version

# Problem: Can't register users
./fix_bcrypt.sh          # Fix password hashing
./kill_servers.sh
./start.sh
```

---

## Script Comparison

| Script | Purpose | Runtime | When to Use | Output |
|--------|---------|---------|-------------|--------|
| `setup_and_test.sh` | Full initialization | 2-5 min | First time, major changes, broken env | Comprehensive test results |
| `verify.sh` | Quick health check | 1-2 sec | Before development, diagnose issues | Pass/fail for each check |
| `start.sh` | Start servers | ~5 sec | Daily development | Server URLs |
| `check_servers.sh` | Server status | <1 sec | Check if running | PIDs and status |
| `kill_servers.sh` | Stop servers | <1 sec | End session, clear duplicates | Confirmation |
| `fix_bcrypt.sh` | Fix password hashing | 10-15 sec | bcrypt errors | Test results |
| `test_edit.sh` | Test idea editing | <1 sec | Manual endpoint testing | JSON response |
| `test_module7_simple.sh` | CI workflow test | 5-10 sec | Integration testing | Pass/fail per test |

---

## Environment Requirements

### Prerequisites

- **Python:** 3.11+ (3.12 recommended)
- **Node.js:** 18+ (20+ recommended)
- **npm:** Bundled with Node.js
- **curl:** For API testing scripts
- **SQLite:** For database (usually pre-installed)

### Environment Files

#### `backend/.env`
```env
# Required
ANTHROPIC_API_KEY=sk-ant-your-key-here
DATABASE_URL=sqlite:///./feature_voting.db
SECRET_KEY=your-secret-key

# Optional (has defaults)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=password
ALLOWED_ORIGINS=["http://localhost:5173"]
```

#### `frontend/.env`
```env
VITE_API_URL=http://localhost:8000
```

---

## Common Issues

### Multiple Server Instances

**Symptom:** `start.sh` shows warning about existing servers

**Solution:**
```bash
./kill_servers.sh        # Stop all
./start.sh               # Restart clean
```

---

### Import Errors (Backend)

**Symptom:** `ModuleNotFoundError` when starting backend

**Solution:**
```bash
./verify.sh              # Check venv exists
# If venv missing:
./setup_and_test.sh      # Rebuild everything
```

---

### bcrypt Password Error

**Symptom:** "password cannot be longer than 72 bytes" during registration

**Solution:**
```bash
./fix_bcrypt.sh          # Fix bcrypt version
./kill_servers.sh
./start.sh
```

---

### ANTHROPIC_API_KEY Not Found

**Symptom:** AI structuring fails in submission flow

**Solution:**
```bash
nano backend/.env
# Add: ANTHROPIC_API_KEY=sk-ant-your-key-here
./kill_servers.sh
./start.sh
```

---

### Port Already in Use

**Symptom:** Server won't start, port 8000 or 5173 occupied

**Solution:**
```bash
./check_servers.sh       # Find PIDs
./kill_servers.sh        # Stop all
./start.sh
```

---

## Advanced Usage

### Running Individual Components

**Backend only:**
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload
```

**Frontend only:**
```bash
cd frontend
npm run dev
```

---

### Custom Ports

**Backend on different port:**
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8001
```

**Frontend on different port:**
```bash
cd frontend
npm run dev -- --port 5174
```

Don't forget to update `frontend/.env`:
```env
VITE_API_URL=http://localhost:8001
```

---

### Running Backend Tests

**All tests:**
```bash
cd backend
source venv/bin/activate
python -m pytest tests/ test_*.py -v
```

**Specific test file:**
```bash
python -m pytest test_complete_api.py -v
```

---

### Frontend Build

**Development build:**
```bash
cd frontend
npm run build
```

**Preview production build:**
```bash
npm run preview
```

---

## Script Maintenance

### When to Update Scripts

1. **setup_and_test.sh** - When adding new dependencies or tests
2. **verify.sh** - When adding new required components
3. **start.sh** - When changing server ports or commands
4. **Test scripts** - When API endpoints change

### Adding New Scripts

1. Create script in project root
2. Make executable: `chmod +x script_name.sh`
3. Document in this file
4. Update README.md Quick Start section if user-facing

---

## Related Documentation

- [README.md](./README.md) - Project overview and manual setup
- [TESTING_GUIDE.md](./TESTING_GUIDE.md) - Comprehensive testing documentation
- [TESTING_SUMMARY.md](./TESTING_SUMMARY.md) - Quick testing reference

---

**Last Updated:** 2025-12-19
