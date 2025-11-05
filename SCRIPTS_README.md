# Setup and Start Scripts

This directory contains convenient scripts to manage the Feature Voting System development environment.

## Scripts Overview

### 1. `setup_and_test.sh` - Complete Setup and Testing

**Purpose:** Full initialization script that sets up and tests both backend and frontend.

**What it does:**
- Removes and recreates backend virtual environment
- Upgrades pip to latest version
- Installs all Python dependencies
- Creates .env from .env.example if needed
- Backs up and resets the database
- Runs backend tests:
  - Python module imports
  - FastAPI app initialization
  - Schema validation tests
  - API endpoint tests (/, /docs, /health, /ideas)
- Reinstalls frontend dependencies (removes node_modules first)
- Runs frontend tests:
  - Production build test
  - ESLint code quality check
  - Build output validation

**When to use:**
- First time setup
- After pulling major changes
- When dependencies are updated
- When something is broken and you want a fresh start
- When switching between branches with different dependencies
- After Python version upgrade

**Usage:**
```bash
./setup_and_test.sh
```

**Time:** ~2-5 minutes (depending on internet speed)

**Note:** This script creates a fresh database backup before resetting it.

### 2. `start.sh` - Quick Start for Daily Development

**Purpose:** Quickly start both backend and frontend servers for development.

**What it does:**
- Checks that setup has been completed
- Starts backend server (FastAPI with uvicorn)
- Starts frontend dev server (Vite)
- Shows URLs for both services
- Gracefully handles Ctrl+C to stop both servers

**When to use:**
- Daily development
- After initial setup is complete
- Quick testing

**Usage:**
```bash
./start.sh
```

Press `Ctrl+C` to stop both servers.

**Time:** ~5 seconds

### 3. `verify.sh` - Quick Environment Verification

**Purpose:** Fast checks to verify your environment is properly set up.

**What it does:**
- Checks backend virtual environment exists
- Checks backend .env file exists
- Checks frontend node_modules exists
- Checks frontend .env file exists
- Tests FastAPI app can be imported
- All checks complete in seconds

**When to use:**
- Before starting work to ensure environment is ready
- After git pull to check if setup is still valid
- To diagnose setup issues quickly
- After switching branches

**Usage:**
```bash
./verify.sh
```

**Time:** ~1-2 seconds

## Typical Workflow

### First Time Setup

```bash
# 1. Clone the repository
git clone <repository-url>
cd feature-voting-system

# 2. Run full setup and testing
./setup_and_test.sh

# 3. Edit backend/.env to add your ANTHROPIC_API_KEY
nano backend/.env

# 4. Verify everything is ready
./verify.sh

# 5. Start both servers
./start.sh
```

### Daily Development

```bash
# Quick verification
./verify.sh

# Start the servers
./start.sh

# When done, press Ctrl+C
```

### After Git Pull

```bash
# Quick check if environment is still valid
./verify.sh

# If verify fails, re-run full setup
./setup_and_test.sh

# Otherwise, just start
./start.sh
```

### After Updating Dependencies

```bash
# Re-run full setup
./setup_and_test.sh

# Verify it worked
./verify.sh

# Start working
./start.sh
```

## What Gets Tested

### Backend Tests (`setup_and_test.sh`)

1. **Python Imports** - Verifies all modules can be imported
2. **FastAPI Initialization** - Checks app starts correctly
3. **Schema Validation** - Runs Pydantic schema tests
4. **API Endpoints** - Tests HTTP endpoints:
   - `GET /` - Root endpoint
   - `GET /docs` - API documentation
   - `GET /ideas` - Ideas endpoint

### Frontend Tests (`setup_and_test.sh`)

1. **Build Process** - Ensures production build works
2. **ESLint** - Checks code quality
3. **Output Validation** - Verifies dist directory created

## URLs After Starting

When you run `./start.sh`, you can access:

- **Frontend Application:** http://localhost:5173
- **Backend API:** http://localhost:8000
- **API Documentation:** http://localhost:8000/docs (Swagger UI)

## Troubleshooting

### `./setup_and_test.sh` fails

**Issue:** "Permission denied"
```bash
chmod +x setup_and_test.sh
./setup_and_test.sh
```

**Issue:** Backend tests fail
- Check that Python 3.12+ is installed: `python3 --version`
- Check backend/.env file exists and has valid values
- Look at error messages - they're usually helpful

**Issue:** Frontend tests fail
- Check that Node.js 18+ is installed: `node --version`
- Check npm is installed: `npm --version`
- Try manually: `cd frontend && npm install`

### `./start.sh` fails

**Issue:** "Virtual environment not found"
- Run `./setup_and_test.sh` first

**Issue:** "Port already in use"
- Backend (port 8000): Check if another process is using it
  ```bash
  lsof -i :8000
  kill -9 <PID>
  ```
- Frontend (port 5173): Check if another Vite server is running
  ```bash
  lsof -i :5173
  kill -9 <PID>
  ```

**Issue:** Servers start but don't respond
- Check logs:
  ```bash
  tail -f /tmp/backend.log
  tail -f /tmp/frontend.log
  ```

## Manual Control

If you prefer to start servers manually:

### Backend Only
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload
```

### Frontend Only
```bash
cd frontend
npm run dev
```

## Environment Variables

### Backend (`backend/.env`)

Required:
- `ANTHROPIC_API_KEY` - Your Claude API key
- `SECRET_KEY` - JWT signing key (auto-generated in .env.example)

Optional:
- `DATABASE_URL` - Database connection string
- `ALLOWED_ORIGINS` - CORS origins
- See `backend/.env.example` for all options

### Frontend (`frontend/.env`)

Required:
- `VITE_API_URL` - Backend API URL (default: http://localhost:8000)

## What Gets Created

### During Setup

- `backend/venv/` - Python virtual environment
- `backend/feature_voting.db` - SQLite database
- `backend/.env` - Environment variables (if not exists)
- `frontend/node_modules/` - Node dependencies
- `frontend/dist/` - Production build output
- `frontend/.env` - Environment variables (if not exists)

### During Runtime

- `/tmp/backend.log` - Backend server logs (when using start.sh)
- `/tmp/frontend.log` - Frontend server logs (when using start.sh)
- `/tmp/backend_server.log` - Test server logs (during setup_and_test.sh)

## Tips

1. **First time?** Run `setup_and_test.sh` to ensure everything works
2. **Daily use?** Just use `start.sh`
3. **Updating code?** Git pull then run `start.sh` (run `setup_and_test.sh` if deps changed)
4. **Something broken?** Run `setup_and_test.sh` for a fresh start
5. **Check logs:** Use `tail -f /tmp/backend.log` or `/tmp/frontend.log`

## Script Options

Both scripts support standard bash options:

```bash
# Run with verbose output
bash -x ./setup_and_test.sh

# Run in debug mode
bash -xv ./setup_and_test.sh
```

## Contributing

When adding new dependencies:

1. Update `backend/requirements.txt` or `frontend/package.json`
2. Test with `./setup_and_test.sh`
3. Commit both the dependency file and these scripts if modified

## License

Same as the main project.
