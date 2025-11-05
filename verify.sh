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
else
    print_warning ".env file missing - will be created from .env.example"
fi

if [ -f "${BACKEND_DIR}/requirements.txt" ]; then
    print_success "requirements.txt found"
else
    print_error "requirements.txt missing"
    exit 1
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

# Quick import test
echo ""
echo "Quick Import Test:"
echo "------------------"

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
EOF

deactivate

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              Verification Complete!                      ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Your environment is ready! Run './start.sh' to start both servers."
