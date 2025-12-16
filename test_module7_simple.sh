#!/bin/bash
# Module 7 Simple Integration Test
# Tests key endpoints with manual database setup

set -e

echo "============================================================"
echo "  MODULE 7: SIMPLE INTEGRATION TEST"
echo "============================================================"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Test function
run_test() {
    local name="$1"
    local command="$2"

    echo ""
    echo "Testing: $name"
    echo "----------------------------------------"

    if eval "$command"; then
        echo -e "${GREEN}✅ PASSED${NC}"
        return 0
    else
        echo -e "${RED}❌ FAILED${NC}"
        return 1
    fi
}

# Setup test data in database
echo ""
echo "Setting up test data in database..."
echo "----------------------------------------"

sqlite3 backend/feature_voting.db <<EOF
-- Insert a test session with competitors and features
INSERT OR IGNORE INTO ci_products (id, product_name, product_description, product_source_type, created_by_user_id, status, created_at, updated_at)
VALUES (9999, 'Test Product', 'A test product for Module 7', 'text', 1, 'active', datetime('now'), datetime('now'));

UPDATE ci_products
SET structured_product_data = '{
    "product_category": "Project Management",
    "core_features": ["Task tracking", "Team collaboration"],
    "target_users": "Software teams",
    "value_propositions": ["Efficiency", "Collaboration"]
}'
WHERE id = 9999;

INSERT OR IGNORE INTO competitor_analysis_sessions (id, product_id, user_id, session_number, session_name, analysis_type, product_source_type, analyzed_product_structure, status, created_at, updated_at)
VALUES (9999, 9999, 1, 1, 'Test Session', 'full', 'text', '{
    "product_name": "Test Product",
    "product_category": "Project Management",
    "core_features": ["Task tracking", "Team collaboration"],
    "target_users": "Software development teams",
    "value_propositions": ["Efficiency", "Collaboration"]
}', 'active', datetime('now'), datetime('now'));

INSERT OR IGNORE INTO session_competitors (id, session_id, competitor_name, competitor_url, discovery_source, selected_by_user, created_at)
VALUES
(9999, 9999, 'Test Competitor 1', 'http://example.com', 'manual', 1, datetime('now')),
(9998, 9999, 'Test Competitor 2', 'http://example2.com', 'manual', 1, datetime('now'));

INSERT OR IGNORE INTO competitor_features (id, session_competitor_id, feature_name, feature_description, feature_category, selected_by_user, created_at)
VALUES
(9999, 9999, 'Dark Mode', 'Ability to switch to dark theme', 'UI/UX', 1, datetime('now')),
(9998, 9999, 'Keyboard Shortcuts', 'Hotkeys for common actions', 'Productivity', 1, datetime('now')),
(9997, 9998, 'Custom Templates', 'User-defined project templates', 'Customization', 1, datetime('now'));
EOF

echo "✅ Test data created"

# Login to get token
echo ""
echo "Getting authentication token..."
echo "----------------------------------------"
TOKEN=$(curl -s -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=password" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

if [ -z "$TOKEN" ]; then
    echo -e "${RED}❌ Failed to get auth token${NC}"
    exit 1
fi

echo "✅ Got auth token"

# Test 1: Generate ideas
run_test "Generate Ideas Endpoint" \
  "curl -s -X POST 'http://localhost:8000/competitor-intelligence/sessions/9999/generate-ideas' \
    -H 'Authorization: Bearer $TOKEN' | \
   python3 -c \"import sys, json; d=json.load(sys.stdin); print('Status:', d.get('status')); print('Ideas:', d.get('ideas_generated')); exit(0 if d.get('status') == 'completed' else 1)\""

# Test 2: Get generated ideas
run_test "Get Generated Ideas Endpoint" \
  "curl -s -X GET 'http://localhost:8000/competitor-intelligence/sessions/9999/generated-ideas' \
    -H 'Authorization: Bearer $TOKEN' | \
   python3 -c \"import sys, json; d=json.load(sys.stdin); ideas=d.get('ideas', []); print('Found', len(ideas), 'ideas'); exit(0 if len(ideas) > 0 else 1)\""

# Test 3: Edit an idea
echo ""
echo "Getting first idea ID for edit test..."
IDEA_ID=$(curl -s -X GET "http://localhost:8000/competitor-intelligence/sessions/9999/generated-ideas" \
  -H "Authorization: Bearer $TOKEN" | python3 -c "import sys, json; ideas=json.load(sys.stdin).get('ideas', []); print(ideas[0]['id'] if ideas else '')")

if [ -n "$IDEA_ID" ]; then
  run_test "Edit Generated Idea Endpoint" \
    "curl -s -X PUT \"http://localhost:8000/competitor-intelligence/sessions/generated-ideas/$IDEA_ID\" \
      -H 'Authorization: Bearer $TOKEN' \
      -H 'Content-Type: application/json' \
      -d '{\"what\": \"EDITED WHAT\", \"why\": \"EDITED WHY\", \"use_case\": \"EDITED USE CASE\"}' | \
     python3 -c \"import sys, json; d=json.load(sys.stdin); print('Response:', d.keys()); exit(0 if d.get('id') == $IDEA_ID else 1)\""
else
  echo -e "${RED}❌ No idea ID found for edit test${NC}"
fi

# Test 4: Approve ideas
echo ""
echo "Getting idea IDs for approval test..."
IDEA_IDS=$(curl -s -X GET "http://localhost:8000/competitor-intelligence/sessions/9999/generated-ideas" \
  -H "Authorization: Bearer $TOKEN" | python3 -c "import sys, json; ideas=json.load(sys.stdin).get('ideas', []); print(json.dumps([i['id'] for i in ideas]))")

run_test "Approve Ideas Endpoint" \
  "curl -s -X POST 'http://localhost:8000/competitor-intelligence/sessions/generated-ideas/approve' \
    -H 'Authorization: Bearer $TOKEN' \
    -H 'Content-Type: application/json' \
    -d '{\"idea_ids\": $IDEA_IDS, \"approved\": true}' | \
   python3 -c \"import sys, json; d=json.load(sys.stdin); print('Approved:', d.get('updated_count')); exit(0 if d.get('updated_count', 0) > 0 else 1)\""

# Test 5: Finalize and submit to voting system
run_test "Finalize & Submit to Voting System" \
  "curl -s -X POST 'http://localhost:8000/competitor-intelligence/sessions/9999/finalize' \
    -H 'Authorization: Bearer $TOKEN' | \
   python3 -c \"import sys, json; d=json.load(sys.stdin); print('Status:', d.get('status')); print('Submitted:', d.get('submitted_count')); exit(0 if d.get('status') == 'success' else 1)\""

# Test 6: Verify ideas exist in database
run_test "Verify Ideas in Database" \
  "sqlite3 backend/feature_voting.db \"SELECT COUNT(*) FROM ideas WHERE source_type = 'COMPETITOR';\" | \
   python3 -c \"import sys; count = int(sys.stdin.read().strip()); print('Competitor ideas in DB:', count); exit(0 if count > 0 else 1)\""

echo ""
echo "============================================================"
echo "  TEST SUMMARY"
echo "============================================================"
echo -e "${GREEN}✅ All Module 7 endpoints working correctly!${NC}"
echo ""
echo "Cleanup: Removing test data..."
sqlite3 backend/feature_voting.db "DELETE FROM competitor_generated_ideas WHERE session_id = 9999;"
sqlite3 backend/feature_voting.db "DELETE FROM competitor_features WHERE session_competitor_id IN (9999, 9998);"
sqlite3 backend/feature_voting.db "DELETE FROM session_competitors WHERE session_id = 9999;"
sqlite3 backend/feature_voting.db "DELETE FROM competitor_analysis_sessions WHERE id = 9999;"
sqlite3 backend/feature_voting.db "DELETE FROM ci_products WHERE id = 9999;"
echo "✅ Cleanup complete"
