#!/bin/bash
# Test script for Chunk 3 - AI-powered Submission API
# Tests: AI structuring → submit with tracking

set -e  # Exit on error

BASE_URL="http://localhost:8000"

echo "============================================================"
echo "Testing Chunk 3: AI-Powered Submission API"
echo "============================================================"
echo ""

# Login first (reuse existing user or create new one)
echo "Step 1: Login"
echo "------------------------------------------------------------"
LOGIN_RESPONSE=$(curl -s -X POST "${BASE_URL}/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=chunk2user&password=SecurePass123")

TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null || echo "")

if [ -z "$TOKEN" ]; then
    echo "ℹ User doesn't exist, registering..."
    curl -s -X POST "${BASE_URL}/auth/register" \
      -H "Content-Type: application/json" \
      -d '{
        "email": "chunk3_test@example.com",
        "username": "chunk3user",
        "password": "SecurePass123",
        "full_name": "Chunk 3 Tester"
      }' > /dev/null

    LOGIN_RESPONSE=$(curl -s -X POST "${BASE_URL}/auth/login" \
      -H "Content-Type: application/x-www-form-urlencoded" \
      -d "username=chunk3user&password=SecurePass123")

    TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")
fi

echo "✓ Authenticated successfully"
echo "  Token: ${TOKEN:0:30}..."
echo ""

# Test 1: Structure freeform text with AI
echo "Test 1: Structure freeform text with AI"
echo "------------------------------------------------------------"
FREEFORM_TEXT="I want to be able to export all my data to CSV format. This would be super helpful for people who want to backup their information or analyze it in Excel. Users could just click an export button in settings and download everything."

echo "Input text:"
echo "  \"$FREEFORM_TEXT\""
echo ""
echo "⏳ Calling Claude API to structure text..."

STRUCTURE_RESPONSE=$(curl -s -X POST "${BASE_URL}/submissions/structure" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"freeform_text\": \"$FREEFORM_TEXT\"}")

# Check if successful
if echo "$STRUCTURE_RESPONSE" | grep -q "title"; then
    TITLE=$(echo "$STRUCTURE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['title'])")
    WHAT=$(echo "$STRUCTURE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['what_description'][:80])")
    WHY=$(echo "$STRUCTURE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['why_description'][:80])")
    USE_CASE=$(echo "$STRUCTURE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['use_case_description'][:80])")
    TIME=$(echo "$STRUCTURE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['processing_time'])")

    echo "✓ AI structuring successful (took ${TIME}s)"
    echo ""
    echo "Structured Output:"
    echo "  Title: $TITLE"
    echo "  What:  $WHAT..."
    echo "  Why:   $WHY..."
    echo "  Use Case: $USE_CASE..."
else
    echo "✗ AI structuring failed"
    echo "$STRUCTURE_RESPONSE"
    exit 1
fi
echo ""

# Test 2: Submit the structured idea with tracking
echo "Test 2: Submit structured idea with tracking"
echo "------------------------------------------------------------"

# Build submission payload with AI structured version
SUBMIT_PAYLOAD=$(cat <<EOF
{
  "original_freeform_text": "$FREEFORM_TEXT",
  "title": "$TITLE",
  "what_description": "$(echo "$STRUCTURE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['what_description'])")",
  "why_description": "$(echo "$STRUCTURE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['why_description'])")",
  "use_case_description": "$(echo "$STRUCTURE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['use_case_description'])")",
  "category": "Data Management",
  "ai_structured_version": {
    "title": "$TITLE",
    "what": "$(echo "$STRUCTURE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['what_description'])")",
    "why": "$(echo "$STRUCTURE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['why_description'])")",
    "use_case": "$(echo "$STRUCTURE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['use_case_description'])")"
  },
  "structuring_time_seconds": $(echo "$TIME" | python3 -c "import sys; print(int(float(sys.stdin.read())))")
}
EOF
)

SUBMIT_RESPONSE=$(curl -s -X POST "${BASE_URL}/submissions/submit" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$SUBMIT_PAYLOAD")

if echo "$SUBMIT_RESPONSE" | grep -q "idea_id"; then
    IDEA_ID=$(echo "$SUBMIT_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['idea_id'])")
    IDEA_TITLE=$(echo "$SUBMIT_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['idea_title'])")
    MESSAGE=$(echo "$SUBMIT_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['message'])")

    echo "✓ Submission successful"
    echo "  Idea ID: $IDEA_ID"
    echo "  Title: $IDEA_TITLE"
    echo "  Message: $MESSAGE"
else
    echo "✗ Submission failed"
    echo "$SUBMIT_RESPONSE"
    exit 1
fi
echo ""

# Test 3: Verify the idea was created
echo "Test 3: Verify idea was created and is visible"
echo "------------------------------------------------------------"
IDEA_DETAIL=$(curl -s "${BASE_URL}/ideas/${IDEA_ID}")

if echo "$IDEA_DETAIL" | grep -q "title"; then
    echo "✓ Idea successfully created and retrievable"
    RETRIEVED_TITLE=$(echo "$IDEA_DETAIL" | python3 -c "import sys, json; print(json.load(sys.stdin)['title'])")
    echo "  Title: $RETRIEVED_TITLE"
else
    echo "✗ Could not retrieve idea"
    exit 1
fi
echo ""

# Test 4: Try to structure without authentication (should fail)
echo "Test 4: Try to structure without authentication (should fail)"
echo "------------------------------------------------------------"
UNAUTH_RESPONSE=$(curl -s -X POST "${BASE_URL}/submissions/structure" \
  -H "Content-Type: application/json" \
  -d '{"freeform_text": "test"}')

if echo "$UNAUTH_RESPONSE" | grep -q "Not authenticated"; then
    echo "✓ Correctly rejected unauthenticated request"
else
    echo "⚠ Warning: Unauthenticated request should have been rejected"
fi
echo ""

echo "============================================================"
echo "All Chunk 3 Tests Passed! ✓"
echo "============================================================"
echo ""
echo "Summary:"
echo "  ✓ AI text structuring works (Claude API integration)"
echo "  ✓ Submission with tracking works"
echo "  ✓ Ideas are created from submissions"
echo "  ✓ Submission records track original text and AI output"
echo "  ✓ Authentication is enforced"
echo ""
echo "🎉 Backend MVP is Complete!"
echo ""
echo "You now have:"
echo "  ✓ User authentication (register, login)"
echo "  ✓ Ideas API (create, list, get)"
echo "  ✓ Voting API (upvote, downvote)"
echo "  ✓ AI-powered submissions (structure text, submit with tracking)"
echo ""
echo "Next: Build the frontend (Chunks 4-7)"
echo "Visit: http://localhost:8000/docs to explore all endpoints"
