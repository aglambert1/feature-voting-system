# Server Management Scripts

Quick reference for managing your backend and frontend servers.

## Available Scripts

### 🚀 `./start.sh` (Main Script - Use This!)
**Smart server starter with duplicate detection**

**NEW**: Now checks for existing servers automatically!
- Detects running servers before starting
- Warns if duplicates found
- Interactive menu to handle conflicts
- Starts both backend and frontend
- Health checks and log management

When you run it:
1. Checks ports 8000 and 5173
2. If servers found → asks what to do:
   - Stop and restart (recommended)
   - Keep running (exit)
   - Try anyway (may fail)
3. Starts servers with health monitoring
4. Creates timestamped logs

### 🔍 `./check_servers.sh`
**Check server status anytime**

Shows:
- Backend server status (port 8000)
- Frontend server status (port 5173)
- Warning if multiple instances detected
- Process IDs and runtime info

Example output:
```
✓ Running (PID: 12345)
⚠ WARNING: Multiple instances detected!
```

### 🛑 `./kill_servers.sh`
**Emergency stop - kill all servers**

Safely stops:
- All processes on port 8000 (backend)
- All processes on port 5173 (frontend)
- Orphaned uvicorn processes
- Orphaned vite processes

Use when you need to clean everything up.

## Common Workflows

### Starting Work (Recommended)
```bash
# Just run this - it handles everything!
./start.sh

# It will:
# 1. Check for existing servers
# 2. Ask what to do if found
# 3. Start fresh servers
```

### Quick Status Check
```bash
# See what's running anytime
./check_servers.sh
```

### During Work
```bash
# Check status anytime
./check_servers.sh

# If you see "WARNING: Multiple instances detected"
./kill_servers.sh
./start.sh
```

### End of Work
```bash
# Stop everything
./kill_servers.sh
```

## What Ports Are Used?

- **Port 8000**: Backend (FastAPI/Uvicorn)
- **Port 5173**: Frontend (Vite dev server)

## Troubleshooting

### "Multiple instances detected"
**Problem**: You have redundant servers running (wasting resources)

**Solution**:
```bash
./kill_servers.sh
./start.sh
```

### "Port already in use" error
**Problem**: Server trying to start on occupied port

**Solution**:
```bash
./check_servers.sh  # See what's running
./kill_servers.sh   # Kill all servers
./start.sh          # Start fresh
```

### Servers won't stop
**Problem**: Processes are stuck

**Solution**:
```bash
# Force kill by PID (use PID from check_servers.sh)
kill -9 <PID>

# Or nuclear option (kills ALL Python and Node processes)
pkill -9 python
pkill -9 node
```

## Quick Command Reference

```bash
# Status check
./check_servers.sh

# Safe start (recommended)
./safe_start.sh

# Stop all
./kill_servers.sh

# Manual port check
lsof -i :8000  # Backend
lsof -i :5173  # Frontend

# Kill specific port
kill $(lsof -ti :8000)  # Backend
kill $(lsof -ti :5173)  # Frontend
```

## Script Locations

All scripts are in the project root:
```
/Users/aglambert/projects/feature-voting-system/
├── start.sh            # Main script - use this! (with safety checks)
├── check_servers.sh    # Status checker
└── kill_servers.sh     # Emergency stop
```

## What Changed?

**Old**: `start.sh` would create duplicates if servers already running
**New**: `start.sh` checks first and asks what to do

No need for separate `safe_start.sh` - your main start script is now smart!
