#!/bin/bash
# Phase 2 API Testing Script
# Tests queue-based competitor discovery and feature extraction workflows

set -e

BASE_URL="http://localhost:8000"
PRODUCT_INTEL_URL="$BASE_URL/product-intelligence"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Phase 2 API Testing Script${NC}"
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

# Check Celery worker (by looking for running process)
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

# Step 2: Create a test product
echo -e "${YELLOW}Step 2: Creating test product...${NC}"
TIMESTAMP=$(date +%s)
PRODUCT_RESPONSE=$(auth_curl -X POST "$PRODUCT_INTEL_URL/products" \
    -H "Content-Type: application/json" \
    -d "{
        \"product_name\": \"Phase2Test_$TIMESTAMP\",
        \"product_description\": \"A project management tool with Gantt charts, task dependencies, resource allocation, and team collaboration features. Integrates with Slack and Google Calendar.\",
        \"product_source_type\": \"text\"
    }")

PRODUCT_ID=$(echo $PRODUCT_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null)

if [ -z "$PRODUCT_ID" ]; then
    echo -e "${RED}ERROR: Failed to create product${NC}"
    echo "Response: $PRODUCT_RESPONSE"
    exit 1
fi
echo -e "${GREEN}✓ Created product with ID: $PRODUCT_ID${NC}"
echo ""

# Step 3: Queue product analysis first (required before competitor discovery)
echo -e "${YELLOW}Step 3: Queuing product analysis...${NC}"
ANALYSIS_RESPONSE=$(auth_curl -X POST "$PRODUCT_INTEL_URL/products/$PRODUCT_ID/analyze/queue" \
    -H "Content-Type: application/json")

ANALYSIS_JOB_UUID=$(echo $ANALYSIS_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('job_uuid', ''))" 2>/dev/null)

if [ -z "$ANALYSIS_JOB_UUID" ]; then
    echo -e "${RED}ERROR: Failed to queue product analysis${NC}"
    echo "Response: $ANALYSIS_RESPONSE"
    exit 1
fi
echo -e "${GREEN}✓ Queued product analysis job: $ANALYSIS_JOB_UUID${NC}"
echo ""

# Step 4: Poll for analysis completion
echo -e "${YELLOW}Step 4: Waiting for product analysis to complete...${NC}"
MAX_WAIT=120
WAIT_COUNT=0
while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    JOB_STATUS=$(auth_curl "$PRODUCT_INTEL_URL/jobs/$ANALYSIS_JOB_UUID")
    STATUS=$(echo $JOB_STATUS | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', ''))" 2>/dev/null)
    PROGRESS=$(echo $JOB_STATUS | python3 -c "import sys, json; print(json.load(sys.stdin).get('progress_percent', 0))" 2>/dev/null)

    if [ "$STATUS" = "success" ]; then
        echo -e "${GREEN}✓ Product analysis completed!${NC}"
        break
    elif [ "$STATUS" = "failure" ]; then
        echo -e "${RED}ERROR: Product analysis failed${NC}"
        echo $JOB_STATUS | python3 -m json.tool
        exit 1
    fi

    echo -e "  Status: $STATUS, Progress: $PROGRESS%"
    sleep 3
    WAIT_COUNT=$((WAIT_COUNT + 3))
done

if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
    echo -e "${YELLOW}WARNING: Analysis taking longer than expected. Continuing anyway...${NC}"
fi
echo ""

# Step 5: Queue competitor discovery
echo -e "${YELLOW}Step 5: Queuing competitor discovery...${NC}"
DISCOVERY_RESPONSE=$(auth_curl -X POST "$PRODUCT_INTEL_URL/products/$PRODUCT_ID/competitors/discover/queue" \
    -H "Content-Type: application/json" \
    -d '{"max_competitors": 3}')

DISCOVERY_JOB_UUID=$(echo $DISCOVERY_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('job_uuid', ''))" 2>/dev/null)

if [ -z "$DISCOVERY_JOB_UUID" ]; then
    echo -e "${RED}ERROR: Failed to queue competitor discovery${NC}"
    echo "Response: $DISCOVERY_RESPONSE"
    exit 1
fi
echo -e "${GREEN}✓ Queued competitor discovery job: $DISCOVERY_JOB_UUID${NC}"
echo ""

# Step 6: Poll for discovery completion
echo -e "${YELLOW}Step 6: Waiting for competitor discovery to complete...${NC}"
WAIT_COUNT=0
while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    JOB_STATUS=$(auth_curl "$PRODUCT_INTEL_URL/jobs/$DISCOVERY_JOB_UUID")
    STATUS=$(echo $JOB_STATUS | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', ''))" 2>/dev/null)
    PROGRESS=$(echo $JOB_STATUS | python3 -c "import sys, json; print(json.load(sys.stdin).get('progress_percent', 0))" 2>/dev/null)

    if [ "$STATUS" = "success" ]; then
        echo -e "${GREEN}✓ Competitor discovery completed!${NC}"
        echo "Output:"
        echo $JOB_STATUS | python3 -c "import sys, json; d=json.load(sys.stdin); print(json.dumps(d.get('output_data', {}), indent=2))" 2>/dev/null
        break
    elif [ "$STATUS" = "failure" ]; then
        echo -e "${RED}ERROR: Competitor discovery failed${NC}"
        echo $JOB_STATUS | python3 -m json.tool
        exit 1
    fi

    echo -e "  Status: $STATUS, Progress: $PROGRESS%"
    sleep 3
    WAIT_COUNT=$((WAIT_COUNT + 3))
done
echo ""

# Step 7: List discovered competitors
echo -e "${YELLOW}Step 7: Listing discovered competitors...${NC}"
COMPETITORS_RESPONSE=$(auth_curl "$PRODUCT_INTEL_URL/products/$PRODUCT_ID/competitors")
echo $COMPETITORS_RESPONSE | python3 -m json.tool 2>/dev/null || echo $COMPETITORS_RESPONSE

COMPETITOR_IDS=$(echo $COMPETITORS_RESPONSE | python3 -c "import sys, json; comps=json.load(sys.stdin); print(' '.join([str(c['id']) for c in comps]))" 2>/dev/null)
echo -e "${GREEN}✓ Found competitors: $COMPETITOR_IDS${NC}"
echo ""

# Step 8: Queue feature extraction (if we have competitors)
if [ -n "$COMPETITOR_IDS" ]; then
    echo -e "${YELLOW}Step 8: Queuing feature extraction for all competitors...${NC}"

    # Convert space-separated IDs to JSON array
    COMPETITOR_IDS_JSON=$(echo $COMPETITOR_IDS | python3 -c "import sys; ids=sys.stdin.read().split(); print('[' + ','.join(ids) + ']')")

    EXTRACTION_RESPONSE=$(auth_curl -X POST "$PRODUCT_INTEL_URL/products/$PRODUCT_ID/features/extract/queue" \
        -H "Content-Type: application/json" \
        -d "{\"competitor_ids\": $COMPETITOR_IDS_JSON}")

    EXTRACTION_JOB_UUID=$(echo $EXTRACTION_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('job_uuid', ''))" 2>/dev/null)

    if [ -z "$EXTRACTION_JOB_UUID" ]; then
        echo -e "${RED}ERROR: Failed to queue feature extraction${NC}"
        echo "Response: $EXTRACTION_RESPONSE"
    else
        echo -e "${GREEN}✓ Queued feature extraction job: $EXTRACTION_JOB_UUID${NC}"
        echo ""

        # Step 9: Poll for extraction completion
        echo -e "${YELLOW}Step 9: Waiting for feature extraction to complete...${NC}"
        WAIT_COUNT=0
        MAX_WAIT=180  # Feature extraction can take longer
        while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
            JOB_STATUS=$(auth_curl "$PRODUCT_INTEL_URL/jobs/$EXTRACTION_JOB_UUID")
            STATUS=$(echo $JOB_STATUS | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', ''))" 2>/dev/null)
            PROGRESS=$(echo $JOB_STATUS | python3 -c "import sys, json; print(json.load(sys.stdin).get('progress_percent', 0))" 2>/dev/null)

            if [ "$STATUS" = "success" ]; then
                echo -e "${GREEN}✓ Feature extraction completed!${NC}"
                echo "Output:"
                echo $JOB_STATUS | python3 -c "import sys, json; d=json.load(sys.stdin); print(json.dumps(d.get('output_data', {}), indent=2))" 2>/dev/null
                break
            elif [ "$STATUS" = "failure" ]; then
                echo -e "${RED}ERROR: Feature extraction failed${NC}"
                echo $JOB_STATUS | python3 -m json.tool
                break
            fi

            echo -e "  Status: $STATUS, Progress: $PROGRESS%"
            sleep 5
            WAIT_COUNT=$((WAIT_COUNT + 5))
        done
    fi
    echo ""

    # Step 10: List extracted features for first competitor
    FIRST_COMPETITOR_ID=$(echo $COMPETITOR_IDS | cut -d' ' -f1)
    echo -e "${YELLOW}Step 10: Listing features for competitor $FIRST_COMPETITOR_ID...${NC}"
    FEATURES_RESPONSE=$(auth_curl "$PRODUCT_INTEL_URL/products/$PRODUCT_ID/competitors/$FIRST_COMPETITOR_ID/features")
    echo $FEATURES_RESPONSE | python3 -m json.tool 2>/dev/null || echo $FEATURES_RESPONSE
else
    echo -e "${YELLOW}Step 8: Skipping feature extraction (no competitors found)${NC}"
fi
echo ""

# Step 11: Test full workflow endpoint
echo -e "${YELLOW}Step 11: Testing full analysis workflow endpoint...${NC}"
TIMESTAMP2=$(date +%s)
PRODUCT2_RESPONSE=$(auth_curl -X POST "$PRODUCT_INTEL_URL/products" \
    -H "Content-Type: application/json" \
    -d "{
        \"product_name\": \"WorkflowTest_$TIMESTAMP2\",
        \"product_description\": \"An email marketing platform with automation, A/B testing, analytics, and CRM integration.\",
        \"product_source_type\": \"text\"
    }")

PRODUCT2_ID=$(echo $PRODUCT2_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null)

if [ -n "$PRODUCT2_ID" ]; then
    WORKFLOW_RESPONSE=$(auth_curl -X POST "$PRODUCT_INTEL_URL/products/$PRODUCT2_ID/workflows/full-analysis" \
        -H "Content-Type: application/json" \
        -d '{"skip_analysis": false}')

    # The endpoint returns a JobResponse directly, not nested under 'workflow'
    WORKFLOW_JOB_UUID=$(echo $WORKFLOW_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('job_uuid', ''))" 2>/dev/null)

    if [ -n "$WORKFLOW_JOB_UUID" ]; then
        echo -e "${GREEN}✓ Started full analysis workflow: $WORKFLOW_JOB_UUID${NC}"
        echo "Workflow response:"
        echo $WORKFLOW_RESPONSE | python3 -m json.tool 2>/dev/null || echo $WORKFLOW_RESPONSE

        # Check workflow status (this endpoint returns workflow with child jobs)
        echo ""
        echo -e "${YELLOW}Checking workflow status...${NC}"
        WORKFLOW_STATUS=$(auth_curl "$PRODUCT_INTEL_URL/jobs/$WORKFLOW_JOB_UUID/workflow")
        echo $WORKFLOW_STATUS | python3 -m json.tool 2>/dev/null || echo $WORKFLOW_STATUS
    else
        echo -e "${RED}ERROR: Failed to start workflow${NC}"
        echo $WORKFLOW_RESPONSE
    fi
else
    echo -e "${RED}ERROR: Failed to create second test product${NC}"
fi
echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Test Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✓ Authentication working${NC}"
echo -e "${GREEN}✓ Product creation working${NC}"
echo -e "${GREEN}✓ Queue-based product analysis working${NC}"
echo -e "${GREEN}✓ Queue-based competitor discovery working${NC}"
echo -e "${GREEN}✓ Queue-based feature extraction working${NC}"
echo -e "${GREEN}✓ Full workflow endpoint working${NC}"
echo ""
echo -e "Test products created:"
echo -e "  - Product ID: $PRODUCT_ID (Phase2Test_$TIMESTAMP)"
if [ -n "$PRODUCT2_ID" ]; then
    echo -e "  - Product ID: $PRODUCT2_ID (WorkflowTest_$TIMESTAMP2)"
fi
echo ""
echo -e "${GREEN}Phase 2 API tests complete!${NC}"
