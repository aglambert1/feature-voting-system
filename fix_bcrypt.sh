#!/bin/bash

# Quick fix for bcrypt compatibility issue
# This fixes the "password cannot be longer than 72 bytes" error

set -e

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         Fixing bcrypt Compatibility Issue               ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Stop running servers
echo -e "${YELLOW}Stopping running servers...${NC}"
pkill -f "uvicorn app.main:app" 2>/dev/null && echo -e "${GREEN}✓${NC} Backend stopped" || echo -e "${YELLOW}!${NC} Backend not running"
pkill -f "vite" 2>/dev/null && echo -e "${GREEN}✓${NC} Frontend stopped" || echo -e "${YELLOW}!${NC} Frontend not running"

# Navigate to backend
cd "$(dirname "$0")/backend"

# Activate venv
echo ""
echo -e "${BLUE}Activating virtual environment...${NC}"
source venv/bin/activate

# Check current bcrypt version
CURRENT_BCRYPT=$(pip show bcrypt 2>/dev/null | grep Version | awk '{print $2}')
echo -e "${BLUE}Current bcrypt version:${NC} $CURRENT_BCRYPT"

# Fix bcrypt version
echo ""
echo -e "${BLUE}Installing compatible bcrypt version...${NC}"
pip uninstall bcrypt -y --quiet 2>/dev/null || true
pip install "bcrypt==4.0.1" --quiet

echo -e "${GREEN}✓${NC} bcrypt 4.0.1 installed"

# Test that it works
echo ""
echo -e "${BLUE}Testing password hashing...${NC}"
python3 << 'EOF'
try:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    # Test hashing
    hashed = pwd_context.hash("test123")

    # Test verification
    is_valid = pwd_context.verify("test123", hashed)

    if is_valid:
        print("\033[0;32m✓\033[0m Password hashing and verification work correctly!")
        print(f"  Sample hash: {hashed[:40]}...")
    else:
        print("\033[0;31m✗\033[0m Verification failed")
        exit(1)
except Exception as e:
    print(f"\033[0;31m✗\033[0m Error: {e}")
    exit(1)
EOF

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                Fix Complete!                             ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}Next steps:${NC}"
    echo "1. Start servers: ${BLUE}./start.sh${NC}"
    echo "2. Open frontend: ${BLUE}http://localhost:5173${NC}"
    echo "3. Register a user through the UI"
    echo ""
else
    echo ""
    echo -e "${RED}Fix failed. Check the error above.${NC}"
    exit 1
fi

deactivate
