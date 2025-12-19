#!/bin/bash

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Server Status Check ===${NC}\n"

# Check Backend (port 8000)
echo -e "${YELLOW}Backend (FastAPI/Uvicorn - port 8000):${NC}"
BACKEND_PIDS=$(lsof -ti :8000 2>/dev/null)
if [ -z "$BACKEND_PIDS" ]; then
    echo -e "${RED}  ✗ Not running${NC}"
else
    BACKEND_COUNT=$(echo "$BACKEND_PIDS" | wc -l | tr -d ' ')
    if [ "$BACKEND_COUNT" -eq 1 ]; then
        echo -e "${GREEN}  ✓ Running (PID: $BACKEND_PIDS)${NC}"
    else
        echo -e "${RED}  ⚠ WARNING: Multiple instances detected!${NC}"
        echo -e "${RED}    PIDs: $(echo $BACKEND_PIDS | tr '\n' ' ')${NC}"
        echo -e "${YELLOW}    Consider killing duplicates${NC}"
    fi
    # Show process details
    ps -p $BACKEND_PIDS -o pid,ppid,command | grep -v "PID"
fi

echo ""

# Check Frontend (port 5173)
echo -e "${YELLOW}Frontend (Vite - port 5173):${NC}"
FRONTEND_PIDS=$(lsof -ti :5173 2>/dev/null)
if [ -z "$FRONTEND_PIDS" ]; then
    echo -e "${RED}  ✗ Not running${NC}"
else
    FRONTEND_COUNT=$(echo "$FRONTEND_PIDS" | wc -l | tr -d ' ')
    if [ "$FRONTEND_COUNT" -eq 1 ]; then
        echo -e "${GREEN}  ✓ Running (PID: $FRONTEND_PIDS)${NC}"
    else
        echo -e "${RED}  ⚠ WARNING: Multiple instances detected!${NC}"
        echo -e "${RED}    PIDs: $(echo $FRONTEND_PIDS | tr '\n' ' ')${NC}"
        echo -e "${YELLOW}    Consider killing duplicates${NC}"
    fi
    # Show process details
    ps -p $FRONTEND_PIDS -o pid,ppid,command | grep -v "PID"
fi

echo ""

# Check for orphaned uvicorn processes
echo -e "${YELLOW}All Uvicorn processes:${NC}"
UVICORN_PIDS=$(pgrep -f "uvicorn.*app.main:app" 2>/dev/null)
if [ -z "$UVICORN_PIDS" ]; then
    echo -e "  ${GREEN}None found${NC}"
else
    UVICORN_COUNT=$(echo "$UVICORN_PIDS" | wc -l | tr -d ' ')
    if [ "$UVICORN_COUNT" -gt 1 ]; then
        echo -e "${RED}  ⚠ Found $UVICORN_COUNT uvicorn processes:${NC}"
    else
        echo -e "${GREEN}  Found $UVICORN_COUNT uvicorn process:${NC}"
    fi
    ps -p $UVICORN_PIDS -o pid,ppid,etime,command 2>/dev/null | grep -v "PID"
fi

echo ""

# Check for orphaned vite/node processes
echo -e "${YELLOW}All Vite/Node processes:${NC}"
VITE_PIDS=$(pgrep -f "vite|node.*vite" 2>/dev/null)
if [ -z "$VITE_PIDS" ]; then
    echo -e "  ${GREEN}None found${NC}"
else
    VITE_COUNT=$(echo "$VITE_PIDS" | wc -l | tr -d ' ')
    if [ "$VITE_COUNT" -gt 1 ]; then
        echo -e "${RED}  ⚠ Found $VITE_COUNT vite/node processes:${NC}"
    else
        echo -e "${GREEN}  Found $VITE_COUNT vite/node process:${NC}"
    fi
    ps -p $VITE_PIDS -o pid,ppid,etime,command 2>/dev/null | grep -v "PID"
fi

echo ""
echo -e "${BLUE}=== Summary ===${NC}"

# Overall status
TOTAL_ISSUES=0
if [ ! -z "$BACKEND_PIDS" ]; then
    BACKEND_COUNT=$(echo "$BACKEND_PIDS" | wc -l | tr -d ' ')
    if [ "$BACKEND_COUNT" -gt 1 ]; then
        TOTAL_ISSUES=$((TOTAL_ISSUES + BACKEND_COUNT - 1))
    fi
fi

if [ ! -z "$FRONTEND_PIDS" ]; then
    FRONTEND_COUNT=$(echo "$FRONTEND_PIDS" | wc -l | tr -d ' ')
    if [ "$FRONTEND_COUNT" -gt 1 ]; then
        TOTAL_ISSUES=$((TOTAL_ISSUES + FRONTEND_COUNT - 1))
    fi
fi

if [ "$TOTAL_ISSUES" -gt 0 ]; then
    echo -e "${RED}⚠ WARNING: $TOTAL_ISSUES redundant server instance(s) detected${NC}"
    echo -e "${YELLOW}Run './kill_servers.sh' to stop all servers${NC}"
else
    if [ -z "$BACKEND_PIDS" ] && [ -z "$FRONTEND_PIDS" ]; then
        echo -e "${YELLOW}No servers currently running${NC}"
    else
        echo -e "${GREEN}✓ All servers running normally (no duplicates)${NC}"
    fi
fi

echo ""
