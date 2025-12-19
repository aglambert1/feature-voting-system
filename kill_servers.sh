#!/bin/bash

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Stopping All Servers ===${NC}\n"

# Kill backend servers (port 8000)
echo -e "${YELLOW}Stopping backend servers (port 8000)...${NC}"
BACKEND_PIDS=$(lsof -ti :8000 2>/dev/null)
if [ -z "$BACKEND_PIDS" ]; then
    echo -e "${GREEN}  No backend servers running${NC}"
else
    for PID in $BACKEND_PIDS; do
        kill $PID 2>/dev/null
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}  ✓ Killed process $PID${NC}"
        else
            echo -e "${RED}  ✗ Failed to kill process $PID${NC}"
        fi
    done
fi

# Kill frontend servers (port 5173)
echo -e "\n${YELLOW}Stopping frontend servers (port 5173)...${NC}"
FRONTEND_PIDS=$(lsof -ti :5173 2>/dev/null)
if [ -z "$FRONTEND_PIDS" ]; then
    echo -e "${GREEN}  No frontend servers running${NC}"
else
    for PID in $FRONTEND_PIDS; do
        kill $PID 2>/dev/null
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}  ✓ Killed process $PID${NC}"
        else
            echo -e "${RED}  ✗ Failed to kill process $PID${NC}"
        fi
    done
fi

# Kill any orphaned uvicorn processes
echo -e "\n${YELLOW}Checking for orphaned uvicorn processes...${NC}"
UVICORN_PIDS=$(pgrep -f "uvicorn.*app.main:app" 2>/dev/null)
if [ -z "$UVICORN_PIDS" ]; then
    echo -e "${GREEN}  No orphaned uvicorn processes${NC}"
else
    for PID in $UVICORN_PIDS; do
        kill $PID 2>/dev/null
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}  ✓ Killed orphaned uvicorn process $PID${NC}"
        fi
    done
fi

# Kill any orphaned vite processes
echo -e "\n${YELLOW}Checking for orphaned vite processes...${NC}"
VITE_PIDS=$(pgrep -f "vite" | grep -v $$ 2>/dev/null)
if [ -z "$VITE_PIDS" ]; then
    echo -e "${GREEN}  No orphaned vite processes${NC}"
else
    for PID in $VITE_PIDS; do
        # Only kill if it's actually a vite dev server, not this script
        if ps -p $PID -o command | grep -q "vite.*dev\|node.*vite"; then
            kill $PID 2>/dev/null
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}  ✓ Killed orphaned vite process $PID${NC}"
            fi
        fi
    done
fi

# Wait a moment for processes to terminate
echo -e "\n${YELLOW}Waiting for processes to terminate...${NC}"
sleep 2

# Verify all stopped
echo -e "\n${BLUE}=== Verification ===${NC}"
REMAINING_BACKEND=$(lsof -ti :8000 2>/dev/null)
REMAINING_FRONTEND=$(lsof -ti :5173 2>/dev/null)

if [ -z "$REMAINING_BACKEND" ] && [ -z "$REMAINING_FRONTEND" ]; then
    echo -e "${GREEN}✓ All servers successfully stopped${NC}"
else
    echo -e "${RED}⚠ Some processes may still be running:${NC}"
    if [ ! -z "$REMAINING_BACKEND" ]; then
        echo -e "${RED}  Backend: PIDs $REMAINING_BACKEND${NC}"
        echo -e "${YELLOW}  Try: kill -9 $REMAINING_BACKEND${NC}"
    fi
    if [ ! -z "$REMAINING_FRONTEND" ]; then
        echo -e "${RED}  Frontend: PIDs $REMAINING_FRONTEND${NC}"
        echo -e "${YELLOW}  Try: kill -9 $REMAINING_FRONTEND${NC}"
    fi
fi

echo ""
