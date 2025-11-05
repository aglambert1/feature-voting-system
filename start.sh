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

echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         Feature Voting System - Quick Start             ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

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

# Start backend server
echo -e "${BLUE}==>${NC} Starting backend server..."
cd "${BACKEND_DIR}"
source venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 > /tmp/backend.log 2>&1 &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Check if backend started successfully
if ! ps -p $BACKEND_PID > /dev/null; then
    echo -e "${RED}✗${NC} Backend server failed to start"
    echo "Check /tmp/backend.log for details"
    exit 1
fi

echo -e "${GREEN}✓${NC} Backend server started (PID: $BACKEND_PID)"
echo -e "  ${BLUE}API:${NC}  http://localhost:8000"
echo -e "  ${BLUE}Docs:${NC} http://localhost:8000/docs"

# Start frontend dev server
echo ""
echo -e "${BLUE}==>${NC} Starting frontend dev server..."
cd "${FRONTEND_DIR}"
npm run dev > /tmp/frontend.log 2>&1 &
FRONTEND_PID=$!

# Wait for frontend to start
sleep 3

# Check if frontend started successfully
if ! ps -p $FRONTEND_PID > /dev/null; then
    echo -e "${RED}✗${NC} Frontend dev server failed to start"
    echo "Check /tmp/frontend.log for details"
    kill $BACKEND_PID 2>/dev/null
    exit 1
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
echo "Logs:"
echo "  Backend:  tail -f /tmp/backend.log"
echo "  Frontend: tail -f /tmp/frontend.log"
echo ""

# Wait for user to press Ctrl+C
wait
