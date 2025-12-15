#!/bin/bash

# Feature Voting System - Quick Verification Script
# Fast checks to verify setup is complete

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}!${NC} $1"
}

echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         Feature Voting System - Quick Verify            ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${PROJECT_ROOT}/backend"
FRONTEND_DIR="${PROJECT_ROOT}/frontend"

# Backend checks
echo "Backend Checks:"
echo "---------------"

if [ -d "${BACKEND_DIR}/venv" ]; then
    print_success "Virtual environment exists"
else
    print_error "Virtual environment missing - run ./setup_and_test.sh"
    exit 1
fi

if [ -f "${BACKEND_DIR}/.env" ]; then
    print_success ".env file exists"

    # Validate ANTHROPIC_API_KEY is configured
    if grep -q "ANTHROPIC_API_KEY=your-anthropic-api-key-here" "${BACKEND_DIR}/.env" 2>/dev/null || \
       ! grep -q "^ANTHROPIC_API_KEY=sk-ant-" "${BACKEND_DIR}/.env" 2>/dev/null; then
        print_warning "ANTHROPIC_API_KEY not configured - Competitive Intelligence features will not work"
        print_warning "Get your API key from: https://console.anthropic.com/"
    else
        print_success "ANTHROPIC_API_KEY configured"
    fi
else
    print_warning ".env file missing - will be created from .env.example"
fi

if [ -f "${BACKEND_DIR}/requirements.txt" ]; then
    print_success "requirements.txt found"
else
    print_error "requirements.txt missing"
    exit 1
fi

# Check database initialization
if [ -f "${BACKEND_DIR}/feature_voting.db" ]; then
    if command -v sqlite3 >/dev/null 2>&1; then
        TABLE_COUNT=$(sqlite3 "${BACKEND_DIR}/feature_voting.db" \
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';" 2>/dev/null || echo "0")
        if [ "$TABLE_COUNT" -gt 0 ]; then
            print_success "Database initialized with $TABLE_COUNT tables"
        else
            print_warning "Database file exists but appears empty - may need initialization"
        fi
    else
        print_success "Database file exists (sqlite3 not available to check contents)"
    fi
else
    print_warning "Database not initialized - will be created on first run"
fi

# Frontend checks
echo ""
echo "Frontend Checks:"
echo "----------------"

if [ -d "${FRONTEND_DIR}/node_modules" ]; then
    print_success "node_modules exists"
else
    print_error "node_modules missing - run ./setup_and_test.sh"
    exit 1
fi

if [ -f "${FRONTEND_DIR}/.env" ]; then
    print_success ".env file exists"
else
    print_warning ".env file missing - will be created with defaults"
fi

if [ -f "${FRONTEND_DIR}/package.json" ]; then
    print_success "package.json found"
else
    print_error "package.json missing"
    exit 1
fi

# Version checks
echo ""
echo "Version Checks:"
echo "---------------"

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f2)

if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 11 ]; then
    print_success "Python version: $PYTHON_VERSION"
else
    print_error "Python 3.11+ required, found: $PYTHON_VERSION"
fi

# Check Node version
if command -v node >/dev/null 2>&1; then
    NODE_VERSION=$(node --version 2>&1 | cut -d'v' -f2)
    NODE_MAJOR=$(echo "$NODE_VERSION" | cut -d'.' -f1)

    if [ "$NODE_MAJOR" -ge 18 ]; then
        print_success "Node version: $NODE_VERSION"
    else
        print_error "Node 18+ required, found: $NODE_VERSION"
    fi
else
    print_error "Node.js not found"
fi

# Port conflict checks
echo ""
echo "Port Availability:"
echo "------------------"

if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    print_warning "Port 8000 already in use - backend may fail to start"
else
    print_success "Port 8000 available"
fi

if lsof -Pi :5173 -sTCP:LISTEN -t >/dev/null 2>&1; then
    print_warning "Port 5173 already in use - frontend may fail to start"
else
    print_success "Port 5173 available"
fi

# Comprehensive import test
echo ""
echo "Import Tests:"
echo "-------------"

cd "${BACKEND_DIR}"
source venv/bin/activate

python3 << 'EOF'
import sys
try:
    sys.path.insert(0, '.')
    from app.main import app
    print("\033[0;32m✓\033[0m FastAPI app can be imported")
except Exception as e:
    print(f"\033[0;31m✗\033[0m Import error: {e}")
    sys.exit(1)

# Test Competitive Intelligence modules
try:
    from app.agents.base_agent import BaseAgent
    from app.services.llm_service import llm_service
    from app.models.competitor_intelligence import CIProduct, CompetitorAnalysisSession
    print("\033[0;32m✓\033[0m Competitive Intelligence modules can be imported")
except Exception as e:
    print(f"\033[0;33m!\033[0m CI module warning: {e}")
    # Not critical, don't exit
EOF

deactivate

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              Verification Complete!                      ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Your environment is ready! Run './start.sh' to start both servers."
