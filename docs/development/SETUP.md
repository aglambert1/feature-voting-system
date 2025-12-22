# Development Setup Guide

This guide covers environment setup, database management, and development workflows.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Database Management](#database-management)
4. [Development Scripts](#development-scripts)
5. [Configuration](#configuration)
6. [Testing](#testing)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

- **Python**: 3.11+ (3.12 recommended)
- **Node.js**: 18+ with npm
- **SQLite**: 3.x (usually pre-installed on macOS/Linux)
- **Git**: For version control

### API Keys

- **Anthropic API Key**: Required for Competitive Intelligence features
  - Get yours at: https://console.anthropic.com/
  - Format: `sk-ant-...`
  - Add to `backend/.env`

### System Requirements

- **RAM**: 4GB minimum (8GB recommended)
- **Disk Space**: 2GB for dependencies and virtual environment
- **OS**: macOS, Linux, or Windows WSL2

---

## Quick Start

### Option 1: Full Setup (First Time)

Use this for initial setup or complete environment reset:

```bash
# From project root
./setup_and_test.sh
```

**What This Does**:
1. Checks prerequisites (Python 3.11+, Node.js, npm)
2. Removes old virtual environment and node_modules
3. Creates fresh Python virtual environment
4. Installs backend dependencies
5. Creates `.env` from `.env.example` if needed
6. **Backs up and deletes database** (creates fresh state)
7. Runs comprehensive test suite (pytest, API tests)
8. Sets up frontend with npm install
9. Tests frontend build
10. Leaves system ready for development

**Time Required**: 3-5 minutes

**Output**:
- Fresh virtual environment in `backend/venv/`
- Fresh node_modules in `frontend/node_modules/`
- Clean database (removed after tests)
- Test results and validation

### Option 2: Quick Start (Daily Development)

Use this for daily development after initial setup:

```bash
# From project root
./start.sh
```

**What This Does**:
1. Checks for existing server instances on ports 8000/5173
2. Offers to stop existing servers cleanly
3. Validates virtual environment and node_modules exist
4. Checks database health (warns if tables < 10)
5. Starts backend server (uvicorn) in background
6. Waits for backend health check
7. Starts frontend dev server (npm) in background
8. Waits for frontend readiness
9. Displays access URLs and log locations
10. Waits for Ctrl+C to stop both servers

**Time Required**: 10-20 seconds

**Output**:
- Backend: http://localhost:8000
- Frontend: http://localhost:5173
- API Docs: http://localhost:8000/docs
- Logs: `logs/backend_latest.log`, `logs/frontend_latest.log`

**To Stop**:
- Press `Ctrl+C` once (gracefully stops both servers)

**Log Management**:
- Logs stored in `logs/` with timestamps
- Symlinks to latest: `backend_latest.log`, `frontend_latest.log`
- Auto-cleanup: Keeps last 20 logs or logs < 7 days old
- View live: `tail -f logs/backend_latest.log`

---

## Database Management

The system uses SQLite for simplicity. You have three options for database reinitialization:

### Option 1: Quick Database Reset (Recommended)

Use when you want to reset database without reinstalling dependencies:

```bash
cd backend
python reset_db.py
```

**Interactive Mode** (asks for confirmation):
```
⚠️  WARNING: This will permanently delete the database file!
   File: feature_voting.db
   Size: 1234567 bytes

Are you sure you want to continue? (yes/no):
```

**Force Mode** (no confirmation):
```bash
python reset_db.py --force
# or
python reset_db.py -f
```

**What This Does**:
- Deletes `feature_voting.db`
- Database recreates automatically on next server start
- Bootstrap admin user created from `.env` settings

**When to Use**:
- Testing database migrations
- Clearing test data
- Fixing database corruption
- Starting fresh without full environment reset

### Option 2: Full Environment Reset

Use when you want to reset everything (environment + database):

```bash
./setup_and_test.sh
```

**What This Does** (in addition to database reset):
- Recreates virtual environment
- Reinstalls all dependencies
- Runs full test suite
- Validates entire system

**When to Use**:
- Dependency conflicts
- Python version upgrade
- Major package updates
- Complete fresh start

### Option 3: Manual Database Reset

Use for scripting or custom workflows:

```bash
cd backend
rm feature_voting.db

# Database recreates on next server start
uvicorn app.main:app --reload
```

### Database Migrations

**Current Migration Scripts**:
- `backend/migrate_add_product_features.py` - Adds detailed features table

**Running Migrations**:
```bash
cd backend
source venv/bin/activate
python migrate_add_product_features.py
```

**Creating New Migrations**:
1. Modify models in `app/models/`
2. Create migration script following pattern:
   ```python
   from app.database import engine
   from app.models.base import Base

   def run_migration():
       # Create specific table
       Base.metadata.tables['table_name'].create(engine, checkfirst=True)
   ```
3. Test migration on clean database
4. Document in CHANGELOG.md

---

## Development Scripts

The project includes three core scripts for different scenarios.

### [start.sh](../../start.sh) - Daily Development

**Purpose**: Quick start for daily development work

**Usage**:
```bash
./start.sh
```

**Features**:
- Detects and manages existing server instances
- Health checks for backend and frontend
- Background server execution with log files
- Graceful shutdown on Ctrl+C
- Log rotation (keeps last 20 logs)

**Interactive Prompts**:
- If servers already running: Stop/Keep/Try Anyway
- Handles port conflicts gracefully

**Log Files**:
- Location: `logs/backend_YYYYMMDD_HHMMSS.log`
- Symlinks: `logs/backend_latest.log`, `logs/frontend_latest.log`
- View live: `tail -f logs/*.log`

**Stopping Servers**:
- Press `Ctrl+C` once (both servers stop gracefully)
- Or manually: `kill $(lsof -ti :8000 :5173)`

### [setup_and_test.sh](../../setup_and_test.sh) - Full Setup & Testing

**Purpose**: Complete environment initialization and validation

**Usage**:
```bash
./setup_and_test.sh
```

**What It Does**:

**Backend Setup**:
1. Removes old virtual environment
2. Detects best Python version (3.12 → 3.11 → 3.x)
3. Creates fresh virtual environment
4. Upgrades pip
5. Installs dependencies from `requirements.txt`
6. Fixes bcrypt compatibility (installs bcrypt 4.0.1)
7. Creates `.env` from `.env.example` if needed
8. Validates `ANTHROPIC_API_KEY` configuration
9. Backs up and removes existing database

**Backend Testing**:
1. **Test 1**: Python imports (core + CI modules)
2. **Test 2**: FastAPI app initialization
3. **Test 3**: Pytest test suite
4. **Test 4**: Live server endpoint testing
   - Root endpoint (/)
   - Docs endpoint (/docs)
   - Health check (/health)
   - Ideas endpoint (/ideas)
   - Product-centric workflow (create product → create idea → filter by product)

**Frontend Setup**:
1. Removes old node_modules
2. Runs `npm install`
3. Creates `.env` with `VITE_API_URL=http://localhost:8000`

**Frontend Testing**:
1. **Test 1**: Frontend build (`npm run build`)
2. **Test 2**: ESLint (`npm run lint`)
3. **Test 3**: Dist directory validation

**Cleanup**:
- Removes test database (leaves system in fresh state)

**When to Use**:
- Initial project setup
- After major dependency updates
- Before releases (validation)
- When environment is broken

**Time**: 3-5 minutes

### [backend/reset_db.py](../../backend/reset_db.py) - Database Reset

**Purpose**: Quick database-only reset without full environment rebuild

**Usage**:
```bash
cd backend
python reset_db.py              # Interactive
python reset_db.py --force      # Non-interactive
```

**Options**:
- No arguments: Interactive mode (asks for confirmation)
- `--force` or `-f`: Skip confirmation prompt

**When to Use**:
- Quick database reset during development
- Testing migrations
- Clearing test data
- Fixing database issues

---

## Configuration

### Backend Configuration

**File**: `backend/.env`

**Required Variables**:
```bash
# Database
DATABASE_URL=sqlite:///./feature_voting.db

# Security
SECRET_KEY=your-secret-key-here  # Generate: openssl rand -hex 32
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080  # 7 days

# Admin Bootstrap
ADMIN_USERNAME=admin
ADMIN_PASSWORD=password  # CHANGE THIS!
ADMIN_EMAIL=admin@example.com

# AI Integration (Required for Competitive Intelligence)
ANTHROPIC_API_KEY=sk-ant-your-api-key-here

# Optional
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

**Creating `.env`**:
1. Copy from example: `cp .env.example .env`
2. Generate secret key: `openssl rand -hex 32`
3. Add your Anthropic API key
4. Change admin password

**API Key Validation**:
- Format: Must start with `sk-ant-`
- Validation: Checked during `setup_and_test.sh`
- Warning: Script warns if key is placeholder or invalid
- Get Key: https://console.anthropic.com/

### Frontend Configuration

**File**: `frontend/.env`

**Required Variables**:
```bash
VITE_API_URL=http://localhost:8000
```

**Production**:
```bash
VITE_API_URL=https://your-production-domain.com
```

**Auto-Creation**:
- Created automatically by `setup_and_test.sh`
- Points to localhost:8000 by default

---

## Testing

### Running Tests

**Full Test Suite**:
```bash
./setup_and_test.sh  # Runs complete test suite
```

**Backend Tests Only**:
```bash
cd backend
source venv/bin/activate
pytest -v tests/ test_*.py
```

**Specific Test File**:
```bash
pytest tests/test_auth.py -v
```

**With Coverage**:
```bash
pytest --cov=app --cov-report=html
open htmlcov/index.html  # View coverage report
```

**Frontend Tests**:
```bash
cd frontend
npm run lint     # ESLint
npm run build    # Build test
```

### Test Files

**Backend** (`backend/tests/` and `backend/test_*.py`):
- `test_detailed_features.py` - Integration test for two-level feature extraction
- `tests/` - Unit and integration tests (pytest)

**Shell Scripts** (legacy, still functional):
- Various `test_*.sh` scripts in backend/

### Writing Tests

**Pytest Example**:
```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_read_ideas():
    response = client.get("/ideas/")
    assert response.status_code == 200
    assert "total" in response.json()
```

**Running New Tests**:
```bash
pytest test_my_feature.py -v
```

---

## Troubleshooting

### Server Won't Start

**Symptoms**:
- `start.sh` fails with port errors
- "Address already in use"

**Solutions**:
```bash
# Check what's using the ports
lsof -ti :8000 :5173

# Kill existing processes
./start.sh  # Will prompt to stop existing servers

# Or manually
kill $(lsof -ti :8000 :5173)

# Force kill if needed
kill -9 $(lsof -ti :8000 :5173)
```

### Virtual Environment Issues

**Symptoms**:
- Import errors
- Module not found
- Wrong Python version

**Solutions**:
```bash
# Recreate virtual environment
cd backend
rm -rf venv
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Database Errors

**Symptoms**:
- "table not found"
- "database is locked"
- Integrity errors

**Solutions**:
```bash
# Option 1: Quick reset
cd backend
python reset_db.py --force

# Option 2: Manual reset
rm backend/feature_voting.db
./start.sh  # Database recreates automatically

# Option 3: Full reset
./setup_and_test.sh
```

### Frontend Build Errors

**Symptoms**:
- npm install fails
- Build errors
- TypeScript errors

**Solutions**:
```bash
# Clear cache and reinstall
cd frontend
rm -rf node_modules package-lock.json
npm install

# Clear build cache
rm -rf dist
npm run build
```

### API Key Issues

**Symptoms**:
- "Unauthorized" errors from Anthropic
- Feature extraction fails
- Rate limit errors

**Solutions**:
```bash
# Verify key in .env
grep ANTHROPIC_API_KEY backend/.env

# Should output: ANTHROPIC_API_KEY=sk-ant-...

# Test key validity (if available)
# Check quota at: https://console.anthropic.com/

# If invalid, get new key and update .env
```

### Permission Denied Errors

**Symptoms**:
- Can't execute scripts
- "Permission denied: ./start.sh"

**Solutions**:
```bash
# Make scripts executable
chmod +x start.sh setup_and_test.sh
chmod +x backend/reset_db.py
```

### Log Files

**View Recent Errors**:
```bash
# Backend logs
tail -50 logs/backend_latest.log

# Frontend logs
tail -50 logs/frontend_latest.log

# Live view
tail -f logs/*.log
```

**Log Locations**:
- Backend: `logs/backend_YYYYMMDD_HHMMSS.log`
- Frontend: `logs/frontend_YYYYMMDD_HHMMSS.log`
- Test server: `/tmp/backend_server.log` (during `setup_and_test.sh`)

---

## Development Workflow

### Typical Day

```bash
# Morning: Start servers
./start.sh

# Open in browser
# Backend: http://localhost:8000/docs
# Frontend: http://localhost:5173

# Make changes to code
# Backend auto-reloads (uvicorn --reload)
# Frontend auto-reloads (Vite HMR)

# Run tests as needed
cd backend && pytest tests/test_my_feature.py

# End of day: Stop servers
# Press Ctrl+C in terminal running start.sh
```

### Making Changes

**Backend Changes**:
1. Edit files in `backend/app/`
2. Server auto-reloads (watch logs for errors)
3. Test with API docs or curl
4. Write tests in `backend/tests/`
5. Run tests: `pytest`

**Frontend Changes**:
1. Edit files in `frontend/src/`
2. Browser auto-reloads (Vite HMR)
3. Check browser console for errors
4. Test in UI
5. Run lint: `npm run lint`

**Database Changes**:
1. Update models in `backend/app/models/`
2. Create migration script
3. Test migration on clean database
4. Run migration: `python migrate_xxx.py`
5. Update schema docs

### Before Committing

```bash
# Run linters
cd frontend && npm run lint
cd backend && pytest

# Test build
cd frontend && npm run build

# Optional: Full validation
./setup_and_test.sh
```

---

## Additional Resources

**Documentation**:
- [User Guide](../USER_GUIDE.md) - Complete user documentation
- [Architecture](../ARCHITECTURE.md) - System architecture
- [Database Schema](../database_schema.sql) - Database reference
- [CHANGELOG](../../CHANGELOG.md) - Version history

**API Documentation**:
- Interactive docs: http://localhost:8000/docs (when running)
- ReDoc: http://localhost:8000/redoc

**Development Tools**:
- Database viewer: [DB Browser for SQLite](https://sqlitebrowser.org/)
- API testing: [Postman](https://www.postman.com/) or curl
- Python debugging: VS Code Python extension

---

## Quick Reference

### Common Commands

```bash
# Start servers (daily use)
./start.sh

# Reset database only
cd backend && python reset_db.py --force

# Full environment reset
./setup_and_test.sh

# Run tests
cd backend && pytest -v

# View logs
tail -f logs/*.log

# Check ports
lsof -ti :8000 :5173

# Kill servers
kill $(lsof -ti :8000 :5173)
```

### Important Files

| File | Purpose |
|------|---------|
| `start.sh` | Daily development server start |
| `setup_and_test.sh` | Full setup and validation |
| `backend/reset_db.py` | Database reset utility |
| `backend/.env` | Backend configuration |
| `frontend/.env` | Frontend configuration |
| `logs/backend_latest.log` | Latest backend logs |
| `logs/frontend_latest.log` | Latest frontend logs |

### Port Reference

| Port | Service |
|------|---------|
| 8000 | Backend API |
| 5173 | Frontend Dev Server |

---

**End of Setup Guide**

For user documentation, see [docs/USER_GUIDE.md](../USER_GUIDE.md).
