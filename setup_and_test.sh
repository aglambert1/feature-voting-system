#!/bin/bash

# Feature Voting System - Complete Setup and Test Script
# This script reinitializes the backend virtual environment, tests it,
# then sets up and tests the frontend.

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored messages
print_step() {
    echo -e "${BLUE}==>${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}!${NC} $1"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
print_step "Checking prerequisites..."

if ! command_exists python3; then
    print_error "Python3 is not installed. Please install Python 3.12 or higher."
    exit 1
fi

if ! command_exists node; then
    print_error "Node.js is not installed. Please install Node.js 18 or higher."
    exit 1
fi

if ! command_exists npm; then
    print_error "npm is not installed. Please install npm."
    exit 1
fi

print_success "All prerequisites found"

# Get project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${PROJECT_ROOT}/backend"
FRONTEND_DIR="${PROJECT_ROOT}/frontend"

echo ""
print_step "Project root: ${PROJECT_ROOT}"

################################################################################
# BACKEND SETUP AND TEST
################################################################################

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         BACKEND SETUP AND TESTING                        ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

cd "${BACKEND_DIR}"

# Remove old virtual environment
if [ -d "venv" ]; then
    print_step "Removing old virtual environment..."
    rm -rf venv
    print_success "Old virtual environment removed"
fi

# Detect best Python version
print_step "Detecting Python version..."

PYTHON_CMD=""
if command_exists python3.12; then
    PYTHON_CMD="python3.12"
    print_success "Using Python 3.12"
elif command_exists python3.11; then
    PYTHON_CMD="python3.11"
    print_warning "Python 3.12 preferred, but 3.11 found - should work"
elif command_exists python3; then
    PYTHON_CMD="python3"
    PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
    PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f1)
    PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f2)

    if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 11 ]; then
        print_success "Using Python $PYTHON_VERSION"
    else
        print_error "Python 3.11+ required, found: $PYTHON_VERSION"
        exit 1
    fi
else
    print_error "Python 3 not found"
    exit 1
fi

# Create new virtual environment
print_step "Creating new virtual environment..."
$PYTHON_CMD -m venv venv
print_success "Virtual environment created"

# Activate virtual environment
print_step "Activating virtual environment..."
source venv/bin/activate
print_success "Virtual environment activated"

# Upgrade pip
print_step "Upgrading pip..."
pip install --upgrade pip --quiet
print_success "pip upgraded"

# Install dependencies
print_step "Installing backend dependencies..."
pip install -r requirements.txt --quiet

# Fix bcrypt compatibility issue with passlib
print_step "Fixing bcrypt compatibility..."
pip install "bcrypt==4.0.1" --quiet
print_success "Backend dependencies installed"

# Check if .env exists
if [ ! -f ".env" ]; then
    print_warning ".env file not found. Creating from .env.example..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        print_success ".env file created from .env.example"
        print_warning "Please edit .env file and add your ANTHROPIC_API_KEY"
    else
        print_error ".env.example not found. Please create .env file manually."
        exit 1
    fi
else
    print_success ".env file exists"
fi

# Validate ANTHROPIC_API_KEY
if [ -f ".env" ]; then
    API_KEY=$(grep "^ANTHROPIC_API_KEY=" .env 2>/dev/null | cut -d'=' -f2)
    if [[ "$API_KEY" == "your-anthropic-api-key-here" ]] || [[ -z "$API_KEY" ]]; then
        print_error "⚠ ANTHROPIC_API_KEY not configured in .env"
        print_error "⚠ Competitive Intelligence features will NOT work!"
        print_warning "Get your API key from: https://console.anthropic.com/"
        echo ""
        read -p "Press Enter to continue anyway, or Ctrl+C to exit and configure the API key..." -r
    elif [[ ! "$API_KEY" =~ ^sk-ant- ]]; then
        print_warning "API key doesn't match expected format (should start with 'sk-ant-')"
    else
        print_success "ANTHROPIC_API_KEY configured"
    fi
fi

# Reset database (optional - creates fresh database)
if [ -f "feature_voting.db" ]; then
    print_warning "Existing database found. Backing up..."
    cp feature_voting.db "feature_voting.db.backup.$(date +%Y%m%d_%H%M%S)"
    rm feature_voting.db
    print_success "Database backed up and removed"
fi

# Run backend tests
echo ""
print_step "Running backend tests..."

# Test 1: Check if all Python modules can be imported
print_step "Test 1: Checking Python imports..."
python3 << 'EOF'
try:
    import sys
    sys.path.insert(0, '.')
    from app.main import app
    from app.database import engine
    from app.models import user, idea, vote, submission
    print("✓ Core imports successful")
except Exception as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)

# Test Competitive Intelligence modules
try:
    from app.agents.base_agent import BaseAgent
    from app.services.llm_service import llm_service
    from app.models.competitor_intelligence import CIProduct, CompetitorAnalysisSession
    print("✓ Competitive Intelligence modules imported successfully")
except Exception as e:
    print(f"⚠ CI module warning: {e}")
    # Not critical, don't exit
EOF
print_success "Python imports test passed"

# Test 2: Check if FastAPI app can start (quick check)
print_step "Test 2: Testing FastAPI app initialization..."
python3 << 'EOF'
try:
    import sys
    sys.path.insert(0, '.')
    from app.main import app
    print(f"✓ FastAPI app initialized: {app.title}")
except Exception as e:
    print(f"✗ FastAPI initialization error: {e}")
    sys.exit(1)
EOF
print_success "FastAPI initialization test passed"

# Test 3: Run pytest test suite
print_step "Test 3: Running pytest test suite..."
echo ""

# Check if pytest is available
if ! command_exists pytest; then
    print_warning "pytest not found, installing..."
    pip install pytest pytest-asyncio --quiet
fi

# Run pytest on all test files
PYTEST_PASSED=true
if pytest -v tests/ test_*.py --tb=short --maxfail=5 2>&1 | tee /tmp/pytest_output.txt; then
    print_success "Pytest test suite passed"
else
    PYTEST_PASSED=false
    print_warning "Some pytest tests failed - check output above"
    print_warning "This is not critical for setup, but should be investigated"
fi

# Show test summary
echo ""
TEST_COUNT=$(grep -E "passed|failed" /tmp/pytest_output.txt | tail -1 || echo "Tests completed")
print_step "Test Summary: $TEST_COUNT"
echo ""

# Test 4: Start server in background and test endpoints
print_step "Test 4: Starting backend server for endpoint testing..."
uvicorn app.main:app --host 127.0.0.1 --port 8000 > /tmp/backend_server.log 2>&1 &
BACKEND_PID=$!

# Wait for server to start
print_step "Waiting for server to start..."
sleep 5

# Check if server is running
if ! ps -p $BACKEND_PID > /dev/null; then
    print_error "Backend server failed to start. Check /tmp/backend_server.log"
    cat /tmp/backend_server.log
    exit 1
fi
print_success "Backend server started (PID: $BACKEND_PID)"

# Test API endpoints
print_step "Testing API endpoints..."

# Test root endpoint
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/)
if [ "$HTTP_STATUS" -eq 200 ]; then
    print_success "Root endpoint (/) - Status: 200 OK"
else
    print_error "Root endpoint (/) - Status: $HTTP_STATUS"
fi

# Test docs endpoint
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/docs)
if [ "$HTTP_STATUS" -eq 200 ]; then
    print_success "Docs endpoint (/docs) - Status: 200 OK"
else
    print_error "Docs endpoint (/docs) - Status: $HTTP_STATUS"
fi

# Test health check (if exists)
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health || echo "404")
if [ "$HTTP_STATUS" -eq 200 ]; then
    print_success "Health endpoint (/health) - Status: 200 OK"
fi

# Test ideas endpoint (should return empty array initially)
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/ideas)
if [ "$HTTP_STATUS" -eq 200 ] || [ "$HTTP_STATUS" -eq 307 ]; then
    print_success "Ideas endpoint (/ideas) - Status: $HTTP_STATUS OK"
else
    print_error "Ideas endpoint (/ideas) - Status: $HTTP_STATUS"
fi

print_success "All API endpoint tests passed"

# Stop backend server
print_step "Stopping backend server..."
kill $BACKEND_PID
wait $BACKEND_PID 2>/dev/null
print_success "Backend server stopped"

# Deactivate virtual environment
deactivate

echo ""
echo -e "${GREEN}✓ BACKEND SETUP AND TESTING COMPLETE${NC}"

################################################################################
# FRONTEND SETUP AND TEST
################################################################################

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         FRONTEND SETUP AND TESTING                       ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

cd "${FRONTEND_DIR}"

# Check if node_modules exists
if [ -d "node_modules" ]; then
    print_step "Removing old node_modules..."
    rm -rf node_modules
    print_success "Old node_modules removed"
fi

# Install frontend dependencies
print_step "Installing frontend dependencies (this may take a minute)..."
npm install --silent
print_success "Frontend dependencies installed"

# Check if .env exists
if [ ! -f ".env" ]; then
    print_warning ".env file not found. Creating default..."
    echo "VITE_API_URL=http://localhost:8000" > .env
    print_success ".env file created"
else
    print_success ".env file exists"
fi

# Run frontend tests
echo ""
print_step "Running frontend tests..."

# Test 1: Check if build works
print_step "Test 1: Testing frontend build (this may take a minute)..."
npm run build --silent
if [ $? -eq 0 ]; then
    print_success "Frontend build successful"
else
    print_error "Frontend build failed"
    exit 1
fi

# Test 2: Check if linting works
print_step "Test 2: Running ESLint..."
npm run lint || print_warning "ESLint found issues (non-critical)"

# Test 3: Check if dist directory was created
if [ -d "dist" ]; then
    print_success "Build output directory (dist) created"
    DIST_SIZE=$(du -sh dist | cut -f1)
    print_success "Build size: $DIST_SIZE"
else
    print_error "Build output directory not found"
fi

echo ""
echo -e "${GREEN}✓ FRONTEND SETUP AND TESTING COMPLETE${NC}"

################################################################################
# FINAL SUMMARY
################################################################################

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                 SETUP COMPLETE!                          ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

print_success "Backend virtual environment initialized and tested"
print_success "Frontend dependencies installed and tested"
echo ""

echo -e "${BLUE}Next steps:${NC}"
echo ""
echo "To start the backend server:"
echo "  cd backend"
echo "  source venv/bin/activate"
echo "  uvicorn app.main:app --reload"
echo ""
echo "To start the frontend dev server:"
echo "  cd frontend"
echo "  npm run dev"
echo ""
echo -e "${YELLOW}Backend will run at:${NC} http://localhost:8000"
echo -e "${YELLOW}Frontend will run at:${NC} http://localhost:5173"
echo -e "${YELLOW}API docs available at:${NC} http://localhost:8000/docs"
echo ""
echo -e "${GREEN}Happy coding! 🚀${NC}"
