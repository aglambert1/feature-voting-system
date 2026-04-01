#!/bin/bash

# Feature Voting System - Quick Start Script
# This script starts both backend and frontend servers
# Use this for daily development after initial setup

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${PROJECT_ROOT}/backend"
FRONTEND_DIR="${PROJECT_ROOT}/frontend"
LOGS_DIR="${PROJECT_ROOT}/logs"

# Create logs directory if it doesn't exist
mkdir -p "${LOGS_DIR}"

# Use timestamped log files
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKEND_LOG="${LOGS_DIR}/backend_${TIMESTAMP}.log"
FRONTEND_LOG="${LOGS_DIR}/frontend_${TIMESTAMP}.log"

# Create symlinks to latest logs
ln -sf "backend_${TIMESTAMP}.log" "${LOGS_DIR}/backend_latest.log"
ln -sf "frontend_${TIMESTAMP}.log" "${LOGS_DIR}/frontend_latest.log"

# Clean old logs (keep last 20 logs or logs newer than 7 days)
find "${LOGS_DIR}" -name "*.log" -type f -mtime +7 -delete 2>/dev/null || true
LOG_COUNT=$(find "${LOGS_DIR}" -name "*.log" -type f 2>/dev/null | wc -l | tr -d ' ')
if [ "$LOG_COUNT" -gt 40 ]; then
    # Keep only the 20 most recent logs
    find "${LOGS_DIR}" -name "*.log" -type f -print0 | xargs -0 ls -t | tail -n +21 | xargs rm -f 2>/dev/null || true
fi

echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         Feature Voting System - Quick Start             ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if servers are already running
echo -e "${BLUE}==>${NC} Checking for existing server instances..."
EXISTING_BACKEND=$(lsof -ti :8000 2>/dev/null)
EXISTING_FRONTEND=$(lsof -ti :5173 2>/dev/null)

if [ ! -z "$EXISTING_BACKEND" ] || [ ! -z "$EXISTING_FRONTEND" ]; then
    echo -e "${YELLOW}⚠  WARNING: Servers already running!${NC}"
    if [ ! -z "$EXISTING_BACKEND" ]; then
        BACKEND_COUNT=$(echo "$EXISTING_BACKEND" | wc -l | tr -d ' ')
        echo -e "  ${YELLOW}Backend (port 8000):${NC} $BACKEND_COUNT instance(s) - PID(s): $EXISTING_BACKEND"
    fi
    if [ ! -z "$EXISTING_FRONTEND" ]; then
        FRONTEND_COUNT=$(echo "$EXISTING_FRONTEND" | wc -l | tr -d ' ')
        echo -e "  ${YELLOW}Frontend (port 5173):${NC} $FRONTEND_COUNT instance(s) - PID(s): $EXISTING_FRONTEND"
    fi
    echo ""
    echo -e "${BLUE}What would you like to do?${NC}"
    echo "  1) Stop existing servers and start fresh (recommended)"
    echo "  2) Exit and keep existing servers running"
    echo "  3) Try to start anyway (may fail if ports occupied)"
    echo ""
    read -p "Choose (1-3): " choice

    case $choice in
        1)
            echo -e "\n${YELLOW}Stopping existing servers...${NC}"
            for PID in $EXISTING_BACKEND $EXISTING_FRONTEND; do
                kill $PID 2>/dev/null && echo -e "${GREEN}✓${NC} Killed process $PID"
            done
            sleep 2
            # Verify they're stopped
            STILL_RUNNING=$(lsof -ti :8000 :5173 2>/dev/null)
            if [ ! -z "$STILL_RUNNING" ]; then
                echo -e "${YELLOW}Some processes still running, force killing...${NC}"
                for PID in $STILL_RUNNING; do
                    kill -9 $PID 2>/dev/null
                done
                sleep 1
            fi
            echo -e "${GREEN}✓${NC} All existing servers stopped\n"
            ;;
        2)
            echo -e "${GREEN}Keeping existing servers. Exiting.${NC}"
            echo -e "${BLUE}Tip:${NC} Use ./check_servers.sh to view server status"
            exit 0
            ;;
        3)
            echo -e "${YELLOW}Attempting to start anyway...${NC}"
            echo -e "${YELLOW}Note: This may fail if ports are occupied${NC}\n"
            ;;
        *)
            echo -e "${RED}Invalid choice. Exiting.${NC}"
            exit 1
            ;;
    esac
else
    echo -e "${GREEN}✓${NC} No existing servers detected\n"
fi

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down servers...${NC}"
    if [ ! -z "$BACKEND_PID" ] && ps -p $BACKEND_PID > /dev/null; then
        kill $BACKEND_PID 2>/dev/null
        echo -e "${GREEN}✓${NC} Backend server stopped"
    fi
    if [ ! -z "$FRONTEND_PID" ] && ps -p $FRONTEND_PID > /dev/null; then
        kill $FRONTEND_PID 2>/dev/null
        echo -e "${GREEN}✓${NC} Frontend dev server stopped"
    fi
    exit 0
}

# Set up trap to catch Ctrl+C
trap cleanup SIGINT SIGTERM

# Check if virtual environment exists
if [ ! -d "${BACKEND_DIR}/venv" ]; then
    echo -e "${RED}✗${NC} Backend virtual environment not found!"
    echo -e "${YELLOW}Run ./setup_and_test.sh first to set up the project.${NC}"
    exit 1
fi

# Check if node_modules exists
if [ ! -d "${FRONTEND_DIR}/node_modules" ]; then
    echo -e "${RED}✗${NC} Frontend node_modules not found!"
    echo -e "${YELLOW}Run ./setup_and_test.sh first to set up the project.${NC}"
    exit 1
fi

# Check database status before starting
if [ -f "${BACKEND_DIR}/feature_voting.db" ]; then
    if command -v sqlite3 >/dev/null 2>&1; then
        TABLE_COUNT=$(sqlite3 "${BACKEND_DIR}/feature_voting.db" \
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';" 2>/dev/null || echo "0")
        if [ "$TABLE_COUNT" -lt 10 ]; then
            echo -e "${YELLOW}!${NC} Database may need migration (found $TABLE_COUNT tables, expected 11+)"
            echo -e "${YELLOW}!${NC} Consider running: cd backend && python reset_db.py"
        fi
    fi
fi

# Run database migrations
echo -e "${BLUE}==>${NC} Running database migrations..."
cd "${BACKEND_DIR}"
source venv/bin/activate
alembic upgrade head 2>&1 | tail -5
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Database migrations up to date"
else
    echo -e "${YELLOW}!${NC} Migration warning (may be OK if already up to date)"
fi

# Start backend server
echo -e "${BLUE}==>${NC} Starting backend server..."
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

# Wait for backend to be healthy (max 30 seconds)
echo -e "${BLUE}==>${NC} Waiting for backend to be healthy..."
BACKEND_HEALTHY=false
for i in {1..30}; do
    if ps -p $BACKEND_PID > /dev/null 2>&1; then
        # Process is running, check if it's responding
        if curl -s http://localhost:8000/ > /dev/null 2>&1 || \
           curl -s http://localhost:8000/docs > /dev/null 2>&1; then
            BACKEND_HEALTHY=true
            break
        fi
    else
        # Process died
        echo -e "${RED}✗${NC} Backend server failed to start"
        echo "Check $BACKEND_LOG for details"
        tail -20 "$BACKEND_LOG"
        exit 1
    fi
    sleep 1
done

if [ "$BACKEND_HEALTHY" = false ]; then
    echo -e "${RED}✗${NC} Backend did not become healthy in 30 seconds"
    echo "Check $BACKEND_LOG for details"
    tail -20 "$BACKEND_LOG"
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

echo -e "${GREEN}✓${NC} Backend server started (PID: $BACKEND_PID)"
echo -e "  ${BLUE}API:${NC}  http://localhost:8000"
echo -e "  ${BLUE}Docs:${NC} http://localhost:8000/docs"

# Start frontend dev server
echo ""
echo -e "${BLUE}==>${NC} Starting frontend dev server..."
cd "${FRONTEND_DIR}"
npm run dev > "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

# Wait for frontend to be healthy (max 15 seconds)
echo -e "${BLUE}==>${NC} Waiting for frontend to be ready..."
FRONTEND_HEALTHY=false
for i in {1..15}; do
    if ps -p $FRONTEND_PID > /dev/null 2>&1; then
        # Process is running, check if it's responding
        if curl -s http://localhost:5173 > /dev/null 2>&1; then
            FRONTEND_HEALTHY=true
            break
        fi
    else
        # Process died
        echo -e "${RED}✗${NC} Frontend dev server failed to start"
        echo "Check $FRONTEND_LOG for details"
        tail -20 "$FRONTEND_LOG"
        kill $BACKEND_PID 2>/dev/null
        exit 1
    fi
    sleep 1
done

if [ "$FRONTEND_HEALTHY" = false ]; then
    echo -e "${YELLOW}!${NC} Frontend is starting (may take a few more seconds)"
fi

echo -e "${GREEN}✓${NC} Frontend dev server started (PID: $FRONTEND_PID)"
echo -e "  ${BLUE}App:${NC} http://localhost:5173"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              All servers are running!                    ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Backend:${NC}  http://localhost:8000"
echo -e "${YELLOW}Frontend:${NC} http://localhost:5173"
echo -e "${YELLOW}API Docs:${NC} http://localhost:8000/docs"
echo ""
echo -e "${BLUE}Press Ctrl+C to stop both servers${NC}"
echo ""
echo "Log files:"
echo "  Backend:  $BACKEND_LOG"
echo "  Frontend: $FRONTEND_LOG"
echo ""
echo "View logs:"
echo "  Backend:  tail -f ${LOGS_DIR}/backend_latest.log"
echo "  Frontend: tail -f ${LOGS_DIR}/frontend_latest.log"
echo "  Both:     tail -f ${LOGS_DIR}/*.log"
echo ""

# Wait for user to press Ctrl+C
wait
