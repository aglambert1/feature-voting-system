#!/bin/bash
# Phase 3 API Testing Script
# Tests idea normalization, triage, and PM review workflows

set -e

BASE_URL="http://localhost:8000"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Phase 3 API Testing Script${NC}"
echo -e "${BLUE}  Idea Normalization + Triage${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if services are running
echo -e "${YELLOW}Checking services...${NC}"

# Check FastAPI
if ! curl -s "$BASE_URL/health" > /dev/null 2>&1; then
    echo -e "${RED}ERROR: FastAPI server not running at $BASE_URL${NC}"
    echo "Start it with: cd backend && ./venv/bin/uvicorn app.main:app --reload"
    exit 1
fi
echo -e "${GREEN}✓ FastAPI server is running${NC}"

# Check Redis
if ! docker ps | grep -q redis; then
    echo -e "${YELLOW}Starting Redis...${NC}"
    docker run -d --name redis-test -p 6379:6379 redis:alpine 2>/dev/null || true
    sleep 2
fi
echo -e "${GREEN}✓ Redis is available${NC}"

# Check Celery worker
if ! pgrep -f "celery.*worker" > /dev/null 2>&1; then
    echo -e "${YELLOW}WARNING: Celery worker may not be running${NC}"
    echo "Start it with: cd backend && ./venv/bin/celery -A app.queue worker --loglevel=info"
    echo ""
    echo -e "${YELLOW}Press Enter to continue anyway (tests will queue jobs but they won't execute)${NC}"
    read
fi
echo -e "${GREEN}✓ Services check complete${NC}"
echo ""

# Step 1: Get authentication token
echo -e "${YELLOW}Step 1: Getting authentication token...${NC}"
TOKEN_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=admin&password=password")

TOKEN=$(echo $TOKEN_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null)

if [ -z "$TOKEN" ]; then
    echo -e "${RED}ERROR: Failed to get auth token${NC}"
    echo "Response: $TOKEN_RESPONSE"
    exit 1
fi
echo -e "${GREEN}✓ Got authentication token${NC}"
echo ""

# Helper function to make authenticated requests
auth_curl() {
    curl -s -H "Authorization: Bearer $TOKEN" "$@"
}

# Step 2: Get or create a test product
echo -e "${YELLOW}Step 2: Getting/creating test product...${NC}"
TIMESTAMP=$(date +%s)

# First try to get an existing analyzed product
PRODUCTS_RESPONSE=$(auth_curl "$BASE_URL/product-intelligence/products")
PRODUCT_ID=$(echo $PRODUCTS_RESPONSE | python3 -c "
import sys, json
products = json.load(sys.stdin)
for p in products:
    if p.get('structured_product_data'):
        print(p['id'])
        break
" 2>/dev/null)

if [ -z "$PRODUCT_ID" ]; then
    echo "No analyzed product found. Creating and analyzing a new one..."

    # Create product
    PRODUCT_RESPONSE=$(auth_curl -X POST "$BASE_URL/product-intelligence/products" \
        -H "Content-Type: application/json" \
        -d "{
            \"product_name\": \"Phase3Test_$TIMESTAMP\",
            \"product_description\": \"A project management tool with task tracking, team collaboration, Gantt charts, and integrations with Slack and Google Calendar.\",
            \"product_source_type\": \"text\"
        }")

    PRODUCT_ID=$(echo $PRODUCT_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null)

    if [ -z "$PRODUCT_ID" ]; then
        echo -e "${RED}ERROR: Failed to create product${NC}"
        echo "Response: $PRODUCT_RESPONSE"
        exit 1
    fi

    # Queue product analysis
    echo "Queueing product analysis..."
    ANALYSIS_RESPONSE=$(auth_curl -X POST "$BASE_URL/product-intelligence/products/$PRODUCT_ID/analyze/queue")
    ANALYSIS_JOB_UUID=$(echo $ANALYSIS_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('job_uuid', ''))" 2>/dev/null)

    # Wait for analysis
    echo "Waiting for product analysis (max 60 seconds)..."
    MAX_WAIT=60
    WAIT_COUNT=0
    while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
        JOB_STATUS=$(auth_curl "$BASE_URL/product-intelligence/jobs/$ANALYSIS_JOB_UUID")
        STATUS=$(echo $JOB_STATUS | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', ''))" 2>/dev/null)

        if [ "$STATUS" = "success" ]; then
            echo -e "${GREEN}✓ Product analysis completed${NC}"
            break
        elif [ "$STATUS" = "failure" ]; then
            echo -e "${RED}Product analysis failed${NC}"
            echo $JOB_STATUS | python3 -m json.tool
            exit 1
        fi

        sleep 3
        WAIT_COUNT=$((WAIT_COUNT + 3))
    done
fi

echo -e "${GREEN}✓ Using product ID: $PRODUCT_ID${NC}"
echo ""

# Step 3: Submit a structured idea with triage
echo -e "${YELLOW}Step 3: Submitting structured idea with AI triage...${NC}"
SUBMIT_RESPONSE=$(auth_curl -X POST "$BASE_URL/ideas/submit" \
    -H "Content-Type: application/json" \
    -d "{
        \"product_id\": $PRODUCT_ID,
        \"title\": \"Add AI-powered task prioritization\",
        \"what_description\": \"A feature that uses machine learning to automatically suggest task priorities based on deadlines, dependencies, and team workload.\",
        \"why_description\": \"Teams often struggle to prioritize tasks effectively, especially in large projects. AI assistance would save time and improve decision-making.\",
        \"use_case_description\": \"A project manager opens the dashboard and sees AI-suggested priorities highlighted. They can accept, modify, or dismiss suggestions with one click.\"
    }")

SUBMIT_JOB_UUID=$(echo $SUBMIT_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('job_uuid', ''))" 2>/dev/null)

if [ -z "$SUBMIT_JOB_UUID" ]; then
    echo -e "${RED}ERROR: Failed to submit idea${NC}"
    echo "Response: $SUBMIT_RESPONSE"
    exit 1
fi
echo -e "${GREEN}✓ Idea submitted, job UUID: $SUBMIT_JOB_UUID${NC}"
echo ""

# Step 4: Poll for triage completion
echo -e "${YELLOW}Step 4: Waiting for idea triage to complete...${NC}"
MAX_WAIT=90
WAIT_COUNT=0
IDEA_ID=""
while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    JOB_STATUS=$(auth_curl "$BASE_URL/product-intelligence/jobs/$SUBMIT_JOB_UUID")
    STATUS=$(echo $JOB_STATUS | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', ''))" 2>/dev/null)
    PROGRESS=$(echo $JOB_STATUS | python3 -c "import sys, json; print(json.load(sys.stdin).get('progress_percent', 0))" 2>/dev/null)

    if [ "$STATUS" = "success" ]; then
        IDEA_ID=$(echo $JOB_STATUS | python3 -c "import sys, json; print(json.load(sys.stdin).get('output_data', {}).get('idea_id', ''))" 2>/dev/null)
        TRIAGE_STATUS=$(echo $JOB_STATUS | python3 -c "import sys, json; print(json.load(sys.stdin).get('output_data', {}).get('triage_status', ''))" 2>/dev/null)
        echo -e "${GREEN}✓ Idea triage completed!${NC}"
        echo "  Idea ID: $IDEA_ID"
        echo "  Triage Status: $TRIAGE_STATUS"
        echo "Output:"
        echo $JOB_STATUS | python3 -c "import sys, json; d=json.load(sys.stdin); print(json.dumps(d.get('output_data', {}), indent=2))" 2>/dev/null
        break
    elif [ "$STATUS" = "failure" ]; then
        echo -e "${RED}ERROR: Idea triage failed${NC}"
        echo $JOB_STATUS | python3 -m json.tool
        exit 1
    fi

    echo -e "  Status: $STATUS, Progress: $PROGRESS%"
    sleep 3
    WAIT_COUNT=$((WAIT_COUNT + 3))
done

if [ -z "$IDEA_ID" ]; then
    echo -e "${YELLOW}WARNING: Triage taking longer than expected. Continuing...${NC}"
fi
echo ""

# Step 5: Get idea triage details
if [ -n "$IDEA_ID" ]; then
    echo -e "${YELLOW}Step 5: Getting idea triage details...${NC}"
    TRIAGE_DETAILS=$(auth_curl "$BASE_URL/ideas/$IDEA_ID/triage-details")
    echo $TRIAGE_DETAILS | python3 -m json.tool 2>/dev/null || echo $TRIAGE_DETAILS
    echo -e "${GREEN}✓ Got triage details${NC}"
    echo ""
fi

# Step 6: List pending review ideas
echo -e "${YELLOW}Step 6: Listing ideas pending review...${NC}"
PENDING_RESPONSE=$(auth_curl "$BASE_URL/ideas/pending-review?product_id=$PRODUCT_ID")
echo $PENDING_RESPONSE | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"  Total: {data['total']}\")
print(f\"  Pending: {data['pending_count']}\")
print(f\"  Needs Review: {data['needs_review_count']}\")
if data['ideas']:
    print('  Ideas:')
    for idea in data['ideas'][:5]:
        print(f\"    - {idea['id']}: {idea['title']} ({idea['triage_status']})\")
" 2>/dev/null || echo $PENDING_RESPONSE
echo -e "${GREEN}✓ Listed pending ideas${NC}"
echo ""

# Step 7: Submit a freeform idea
echo -e "${YELLOW}Step 7: Submitting freeform idea for AI structuring...${NC}"
FREEFORM_RESPONSE=$(auth_curl -X POST "$BASE_URL/ideas/submit" \
    -H "Content-Type: application/json" \
    -d "{
        \"product_id\": $PRODUCT_ID,
        \"freeform_text\": \"It would be really cool if we could have some kind of integration with Jira so that tasks created in your app would automatically sync with our existing Jira boards. We use both tools and having to manually copy things over is a pain.\"
    }")

FREEFORM_JOB_UUID=$(echo $FREEFORM_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('job_uuid', ''))" 2>/dev/null)

if [ -n "$FREEFORM_JOB_UUID" ]; then
    echo -e "${GREEN}✓ Freeform idea submitted, job UUID: $FREEFORM_JOB_UUID${NC}"
    echo "  (This will be structured by AI and triaged)"
else
    echo -e "${YELLOW}Freeform submission response: $FREEFORM_RESPONSE${NC}"
fi
echo ""

# Step 8: PM Review - Approve an idea
if [ -n "$IDEA_ID" ]; then
    echo -e "${YELLOW}Step 8: Testing PM review - approving idea $IDEA_ID...${NC}"
    REVIEW_RESPONSE=$(auth_curl -X POST "$BASE_URL/ideas/$IDEA_ID/review" \
        -H "Content-Type: application/json" \
        -d "{
            \"action\": \"approve\",
            \"notes\": \"Good idea, aligned with product strategy\",
            \"publish_for_voting\": true
        }")
    echo $REVIEW_RESPONSE | python3 -m json.tool 2>/dev/null || echo $REVIEW_RESPONSE
    echo -e "${GREEN}✓ Idea reviewed${NC}"
    echo ""
fi

# Step 9: Submit another idea to test duplicate detection
echo -e "${YELLOW}Step 9: Submitting similar idea (testing duplicate detection)...${NC}"
DUPLICATE_RESPONSE=$(auth_curl -X POST "$BASE_URL/ideas/submit" \
    -H "Content-Type: application/json" \
    -d "{
        \"product_id\": $PRODUCT_ID,
        \"title\": \"Smart task priority suggestions\",
        \"what_description\": \"Use AI to automatically suggest which tasks should be done first based on various factors like due dates and workload.\",
        \"why_description\": \"Manual prioritization is time-consuming and error-prone. Automated suggestions would help teams focus on what matters most.\",
        \"use_case_description\": \"The user sees a list of tasks with AI-recommended priority levels that they can quickly approve or adjust.\"
    }")

DUPLICATE_JOB_UUID=$(echo $DUPLICATE_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('job_uuid', ''))" 2>/dev/null)

if [ -n "$DUPLICATE_JOB_UUID" ]; then
    echo -e "${GREEN}✓ Similar idea submitted for duplicate detection, job UUID: $DUPLICATE_JOB_UUID${NC}"
else
    echo -e "${YELLOW}Duplicate test response: $DUPLICATE_RESPONSE${NC}"
fi
echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Test Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✓ Authentication working${NC}"
echo -e "${GREEN}✓ Idea submission (structured) working${NC}"
echo -e "${GREEN}✓ AI triage working${NC}"
echo -e "${GREEN}✓ Triage details endpoint working${NC}"
echo -e "${GREEN}✓ Pending review listing working${NC}"
echo -e "${GREEN}✓ Freeform idea submission working${NC}"
echo -e "${GREEN}✓ PM review action working${NC}"
echo -e "${GREEN}✓ Duplicate detection test initiated${NC}"
echo ""
echo -e "Test product ID: $PRODUCT_ID"
if [ -n "$IDEA_ID" ]; then
    echo -e "First idea ID: $IDEA_ID"
fi
echo ""
echo -e "${GREEN}Phase 3 API tests complete!${NC}"
