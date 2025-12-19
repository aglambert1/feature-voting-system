# Makefile Guide - Optional Developer Tool

## What is a Makefile?

A **Makefile** is a special file used by the `make` command (a build automation tool originally created in 1976 for compiling C programs). While originally designed for building software, modern Makefiles are commonly used as **task runners** to simplify common development workflows.

### Why Developers Love Make

1. **Universal:** Pre-installed on virtually all Unix-like systems (macOS, Linux)
2. **Simple syntax:** Easy to read and write
3. **Self-documenting:** Built-in help system
4. **Tab completion:** Many shells support tab-completing make targets
5. **Familiar:** Industry standard that most developers already know
6. **Fast:** Minimal overhead, runs shell commands directly

---

## Is the Makefile Required?

**No, it's completely optional!**

Your project works perfectly fine using the shell scripts directly:
- `./setup_and_test.sh` → `make setup`
- `./verify.sh` → `make verify`
- `./start.sh` → `make start`
- `./kill_servers.sh` → `make stop`

The Makefile is a **convenience layer** that:
- Provides shorter, more memorable commands
- Groups related tasks
- Offers tab completion
- Follows industry conventions
- Makes the project feel more "professional"

**You can use either approach - they both work!**

---

## Quick Start with Make

### View All Available Commands
```bash
make help
```

### Common Workflows

**Daily development:**
```bash
make dev          # Verify environment + start servers
# Equivalent to: ./verify.sh && ./start.sh
```

**First time setup:**
```bash
make setup        # Full setup and testing
# Equivalent to: ./setup_and_test.sh
```

**Testing:**
```bash
make test         # Run all tests
# Equivalent to: backend tests + frontend lint + frontend build
```

**Server management:**
```bash
make start        # Start servers
make stop         # Stop servers
make restart      # Stop + start
make check        # Check server status
```

---

## Detailed Command Reference

### Setup & Initialization

#### `make setup`
Full system setup and testing (first time or after major changes)

**What it does:**
- Runs `./setup_and_test.sh`
- Creates venv, installs dependencies
- Runs comprehensive tests
- Sets up database

**When to use:**
- First time cloning the repo
- After pulling major updates
- When environment is broken

**Example:**
```bash
make setup
```

---

#### `make verify`
Quick environment verification

**What it does:**
- Runs `./verify.sh`
- Checks Python, Node.js versions
- Verifies venv and node_modules exist
- Tests imports

**When to use:**
- Before starting development
- After system restart
- To diagnose issues

**Example:**
```bash
make verify
```

---

### Server Management

#### `make start`
Start both development servers

**What it does:**
- Runs `./start.sh`
- Starts backend on port 8000
- Starts frontend on port 5173
- Checks for duplicate servers

**Example:**
```bash
make start
# Opens two terminals with running servers
```

---

#### `make stop`
Stop all running servers

**What it does:**
- Runs `./kill_servers.sh`
- Kills processes on ports 8000 and 5173
- Cleans up orphaned processes

**Example:**
```bash
make stop
```

---

#### `make restart`
Restart servers (stop + start)

**What it does:**
- Stops all servers
- Waits 2 seconds
- Starts servers fresh

**When to use:**
- After code changes requiring restart
- When servers are acting weird
- To clear server state

**Example:**
```bash
make restart
```

---

#### `make check`
Check server status

**What it does:**
- Runs `./check_servers.sh`
- Shows PIDs and ports
- Detects duplicate instances

**Example:**
```bash
make check
# ✓ Backend running (PID: 12345)
# ✓ Frontend running (PID: 67890)
```

---

#### `make dev`
Full development workflow

**What it does:**
- Runs `make verify` (health check)
- Runs `make start` (start servers)

**When to use:**
- Starting your work session
- One-command setup for the day

**Example:**
```bash
make dev
# Verifies environment, then starts servers
```

---

### Testing

#### `make test`
Run all tests

**What it does:**
- Runs backend pytest suite
- Runs frontend lint
- Runs frontend build test

**Example:**
```bash
make test
```

---

#### `make test-backend`
Run backend tests only

**What it does:**
- Activates venv
- Runs pytest on all test files

**Example:**
```bash
make test-backend
```

---

#### `make test-frontend`
Run frontend tests only

**What it does:**
- Runs ESLint
- Runs build test

**Example:**
```bash
make test-frontend
```

---

#### `make test-integration`
Run integration tests

**What it does:**
- Runs `./scripts/tests/test_module7_simple.sh`
- Runs `./scripts/tests/test_edit.sh`

**Requirements:**
- Backend server must be running

**Example:**
```bash
# Terminal 1
make start

# Terminal 2
make test-integration
```

---

### Cleanup

#### `make clean`
Clean build artifacts and stop servers

**What it does:**
- Stops all servers
- Removes database (`backend/feature_voting.db`)
- Removes frontend build (`frontend/dist`)

**When to use:**
- Fresh start needed
- Clearing old build artifacts
- Before running full setup

**Example:**
```bash
make clean
# Then run: make setup
```

---

#### `make clean-deep`
Deep clean (removes venv and node_modules too)

**What it does:**
- Runs `make clean`
- Removes `backend/venv`
- Removes `frontend/node_modules`
- **Requires confirmation**

**When to use:**
- Complete fresh start needed
- Dependency corruption
- Disk space cleanup

**Example:**
```bash
make clean-deep
# WARNING: This will remove venv and node_modules.
# Continue? (y/N): y
# Then run: make setup
```

---

### Database

#### `make db-reset`
Reset database (backup current, create fresh)

**What it does:**
- Backs up current database with timestamp
- Removes current database
- Database recreated on next backend startup

**Example:**
```bash
make db-reset
# ✓ Database backed up to feature_voting.db.backup.20251219_103045
# ✓ Database removed
```

---

#### `make db-backup`
Backup current database

**What it does:**
- Copies database with timestamp
- Doesn't remove original

**Example:**
```bash
make db-backup
# ✓ Database backed up to feature_voting.db.backup.20251219_103045
```

---

### Utilities

#### `make fix-bcrypt`
Fix bcrypt compatibility issues

**What it does:**
- Runs `./fix_bcrypt.sh`
- Downgrades bcrypt to 4.0.1

**When to use:**
- Getting "password too long" errors
- After fresh venv creation

**Example:**
```bash
make fix-bcrypt
```

---

#### `make logs`
Show recent server logs

**What it does:**
- Shows last 20 lines of backend logs
- Shows last 20 lines of frontend logs

**Example:**
```bash
make logs
```

---

#### `make logs-follow`
Follow server logs in real-time

**What it does:**
- Tails all log files
- Updates in real-time
- Ctrl+C to stop

**Example:**
```bash
make logs-follow
# [Backend] Starting uvicorn...
# [Frontend] Vite server started...
```

---

### Backend-Specific

#### `make backend-shell`
Start backend shell with activated venv

**What it does:**
- Opens new shell
- Activates virtual environment
- Ready for Python commands

**Example:**
```bash
make backend-shell
# (venv) $ python
# >>> from app.main import app
```

---

#### `make backend-test`
Quick backend import test

**What it does:**
- Tests that backend imports work
- Fast sanity check

**Example:**
```bash
make backend-test
# ✓ Backend imports OK
```

---

### Frontend-Specific

#### `make frontend-build`
Build frontend for production

**What it does:**
- Runs `npm run build`
- Creates `frontend/dist/` directory

**Example:**
```bash
make frontend-build
```

---

#### `make frontend-preview`
Preview production build

**What it does:**
- Runs `npm run preview`
- Serves production build locally

**Example:**
```bash
make frontend-preview
# Preview at http://localhost:4173
```

---

### Dependencies

#### `make install`
Install/update all dependencies

**What it does:**
- Installs backend requirements.txt
- Installs frontend package.json

**When to use:**
- After pulling dependency changes
- After modifying requirements/package files

**Example:**
```bash
make install
```

---

#### `make update`
Update dependencies to latest versions

**What it does:**
- Updates backend dependencies
- Updates frontend dependencies

**Warning:** May break compatibility

**Example:**
```bash
make update
```

---

### Git Helpers

#### `make status`
Show git status

**Example:**
```bash
make status
# On branch main
# Changes not staged for commit:
#   modified: backend/app/api/votes.py
```

---

#### `make commit`
Interactive commit (staged files)

**What it does:**
- Shows git status
- Prompts for commit message
- Commits staged files

**Example:**
```bash
git add .
make commit
# Commit message: Fix voting bug
```

---

#### `make push`
Push to remote

**Example:**
```bash
make push
```

---

#### `make pull`
Pull from remote and reinstall dependencies if changed

**What it does:**
- Pulls from remote
- Checks if dependencies changed
- Reinstalls if needed

**Example:**
```bash
make pull
# Checking if dependencies changed...
# Backend dependencies changed, reinstalling...
```

---

## Make vs Shell Scripts Comparison

| Task | Shell Script | Make Command | Notes |
|------|--------------|--------------|-------|
| Setup | `./setup_and_test.sh` | `make setup` | Make is shorter |
| Verify | `./verify.sh` | `make verify` | Same length |
| Start | `./start.sh` | `make start` | Make is shorter |
| Stop | `./kill_servers.sh` | `make stop` | Make is clearer |
| Check status | `./check_servers.sh` | `make check` | Make is shorter |
| Fix bcrypt | `./fix_bcrypt.sh` | `make fix-bcrypt` | Same length |
| Integration test | `./scripts/tests/test_module7_simple.sh` | `make test-integration` | Make is much shorter |
| Clean everything | *Multiple commands* | `make clean` | Make combines tasks |
| Reset DB | *Manual steps* | `make db-reset` | Make simplifies |

---

## Advanced: How Make Works

### Makefile Syntax Basics

```makefile
target: dependencies  ## Description for help
	@command1          # @ suppresses echo
	command2           # Shows command before running
```

**Example:**
```makefile
start:  ## Start servers
	@echo "Starting servers..."
	./start.sh
```

**Running:**
```bash
make start
# Starting servers...
# [output from start.sh]
```

---

### .PHONY Targets

`.PHONY` tells Make these aren't actual files:

```makefile
.PHONY: clean test start
```

This prevents conflicts if you have a file named `test` or `clean`.

---

### Variables

```makefile
BACKEND_DIR = backend
FRONTEND_DIR = frontend

test:
	cd $(BACKEND_DIR) && pytest
	cd $(FRONTEND_DIR) && npm test
```

---

### Calling Other Targets

```makefile
restart:
	$(MAKE) stop
	$(MAKE) start
```

Equivalent to:
```bash
make stop
make start
```

---

## Tab Completion

Many shells support tab completion for Make targets:

```bash
make <TAB><TAB>
# Shows all available targets

make te<TAB>
# Completes to: make test

make test-<TAB><TAB>
# Shows: test-backend  test-frontend  test-integration
```

---

## When NOT to Use Make

**Don't use Make if:**
1. **Your team doesn't know it** - Shell scripts are more universal
2. **You need complex logic** - Shell scripts have better conditionals
3. **You need interactive prompts** - Make targets should be non-interactive (though our examples break this rule for safety prompts)
4. **Cross-platform support critical** - Make behaves differently on Windows

**Stick with shell scripts if:**
- You prefer being explicit (`./script.sh` vs `make target`)
- Your workflow is already working fine
- You don't want to learn another tool

---

## Customizing the Makefile

### Add Your Own Targets

```makefile
my-task:  ## My custom task
	@echo "Running my custom task..."
	# Your commands here
```

### Override Existing Targets

Just edit the Makefile and change the commands.

### Remove Unwanted Targets

Delete or comment out targets you don't need:
```makefile
# commit:  ## Interactive commit
# 	@git commit
```

---

## Makefile Best Practices

1. **Keep targets simple** - Complex logic goes in shell scripts
2. **Use .PHONY** - For all non-file targets
3. **Add help descriptions** - Use `## Description` format
4. **Use @ for clean output** - Suppress command echo with `@`
5. **Test each target** - Ensure they work independently
6. **Document in help** - Every target should have a description

---

## Troubleshooting Make

### "make: command not found"

**Solution:** Install build tools
```bash
# macOS
xcode-select --install

# Ubuntu/Debian
sudo apt install build-essential

# Most systems already have it
```

---

### "Makefile:X: *** missing separator"

**Problem:** Must use TABS, not spaces for indentation

**Solution:** Configure your editor to use tabs in Makefiles
- VS Code: Automatically detects
- Vim: `set noexpandtab`
- Emacs: Automatically handles

---

### Target doesn't run commands

**Problem:** Commands must be indented with TAB character

**Check:**
```bash
cat -A Makefile | grep "^I"
# Should show ^I (tab character) at start of command lines
```

---

## Migration Guide: Scripts → Make

If you want to switch from shell scripts to Make:

**Week 1:** Try Make alongside scripts
```bash
make start    # Try Make version
./start.sh    # Fall back to script if issues
```

**Week 2:** Use Make primarily
```bash
make dev      # Use Make by default
```

**Week 3:** Decide if you want to keep using Make

**Rollback anytime:** Just delete `Makefile`, scripts still work!

---

## Summary

### Pros of Using Make
✅ Shorter commands (`make start` vs `./start.sh`)
✅ Industry standard (familiar to most developers)
✅ Tab completion in many shells
✅ Self-documenting with `make help`
✅ Groups related tasks (e.g., `make test` runs multiple test types)
✅ Easy to extend with custom targets
✅ No dependencies - already installed on most systems

### Cons of Using Make
❌ Another layer of abstraction
❌ Not all developers know Make
❌ Tab vs spaces issues in Makefiles
❌ Less intuitive than `./script_name.sh`
❌ Overkill for simple projects

### Our Recommendation

**Try it!** The Makefile is provided but completely optional. Use it if you like the workflow, ignore it if you prefer direct shell scripts. Both approaches work perfectly.

**Best approach:** Use whatever you find most comfortable:
- Prefer explicit commands? → Use shell scripts
- Like convenience and shortcuts? → Use Make
- Want both? → Use both! They don't conflict.

---

## Quick Reference Card

Print this section and tape it to your monitor:

```
# Daily Development
make dev          # Verify + start servers
make stop         # Stop servers
make restart      # Restart servers
make check        # Check server status
make logs         # View recent logs

# Setup & Maintenance
make setup        # Full setup (first time)
make verify       # Quick health check
make clean        # Clean build artifacts
make install      # Install dependencies

# Testing
make test         # Run all tests
make test-backend # Backend only
make test-integration # Integration tests

# Database
make db-reset     # Reset database
make db-backup    # Backup database

# Help
make help         # Show all commands
```

---

**Last Updated:** 2025-12-19

**See Also:**
- [SCRIPTS.md](./SCRIPTS.md) - Complete shell script reference
- [README.md](./README.md) - Project overview
