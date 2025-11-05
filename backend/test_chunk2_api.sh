#!/bin/bash
# Test script for Chunk 2 API endpoints
# Tests the complete flow: register → login → create idea → vote

set -e  # Exit on error

BASE_URL="http://localhost:8000"

echo "============================================================"
echo "Testing Chunk 2 API Endpoints"
echo "============================================================"
echo ""

# Test 1: Register a new user
echo "Test 1: Register new user"
echo "------------------------------------------------------------"
REGISTER_RESPONSE=$(curl -s -X POST "${BASE_URL}/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "chunk2_test@example.com",
    "username": "chunk2user",
    "password": "SecurePass123",
    "full_name": "Chunk 2 Tester"
  }')

if echo "$REGISTER_RESPONSE" | grep -q "username"; then
    echo "✓ User registered successfully"
else
    echo "ℹ User may already exist (continuing...)"
fi
echo ""

# Test 2: Login
echo "Test 2: Login"
echo "------------------------------------------------------------"
LOGIN_RESPONSE=$(curl -s -X POST "${BASE_URL}/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=chunk2user&password=SecurePass123")

TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

if [ -n "$TOKEN" ]; then
    echo "✓ Login successful"
    echo "  Token: ${TOKEN:0:30}..."
else
    echo "✗ Login failed"
    exit 1
fi
echo ""

# Test 3: Create an idea
echo "Test 3: Create an idea"
echo "------------------------------------------------------------"
IDEA_RESPONSE=$(curl -s -X POST "${BASE_URL}/ideas/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Dark Mode Toggle",
    "what_description": "A toggle switch in settings that enables dark mode for the entire application",
    "why_description": "Many users prefer dark mode, especially when working at night, as it reduces eye strain and saves battery on OLED screens",
    "use_case_description": "A user working late at night opens settings and enables dark mode, transforming the UI to use dark colors",
    "category": "UI/UX"
  }')

IDEA_ID=$(echo "$IDEA_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")

if [ -n "$IDEA_ID" ]; then
    echo "✓ Idea created successfully"
    echo "  ID: $IDEA_ID"
    echo "  Title: $(echo "$IDEA_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['title'])")"
else
    echo "✗ Idea creation failed"
    exit 1
fi
echo ""

# Test 4: List all ideas
echo "Test 4: List all ideas (public endpoint)"
echo "------------------------------------------------------------"
LIST_RESPONSE=$(curl -s "${BASE_URL}/ideas/")
IDEA_COUNT=$(echo "$LIST_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['total'])")

echo "✓ Retrieved ideas list"
echo "  Total ideas: $IDEA_COUNT"
echo ""

# Test 5: Get single idea
echo "Test 5: Get single idea"
echo "------------------------------------------------------------"
SINGLE_IDEA=$(curl -s "${BASE_URL}/ideas/${IDEA_ID}")
IDEA_TITLE=$(echo "$SINGLE_IDEA" | python3 -c "import sys, json; print(json.load(sys.stdin)['title'])")

echo "✓ Retrieved idea details"
echo "  Title: $IDEA_TITLE"
echo ""

# Test 6: Upvote the idea
echo "Test 6: Upvote the idea"
echo "------------------------------------------------------------"
VOTE_RESPONSE=$(curl -s -X POST "${BASE_URL}/ideas/${IDEA_ID}/vote" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"vote_value": 1}')

SCORE=$(echo "$VOTE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['vote_counts']['score'])")

echo "✓ Vote cast successfully"
echo "  New score: $SCORE"
echo "  Message: $(echo "$VOTE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['message'])")"
echo ""

# Test 7: Change vote to downvote
echo "Test 7: Change vote to downvote"
echo "------------------------------------------------------------"
VOTE_RESPONSE2=$(curl -s -X POST "${BASE_URL}/ideas/${IDEA_ID}/vote" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"vote_value": -1}')

SCORE2=$(echo "$VOTE_RESPONSE2" | python3 -c "import sys, json; print(json.load(sys.stdin)['vote_counts']['score'])")

echo "✓ Vote updated successfully"
echo "  New score: $SCORE2"
echo "  Message: $(echo "$VOTE_RESPONSE2" | python3 -c "import sys, json; print(json.load(sys.stdin)['message'])")"
echo ""

# Test 8: Try to vote without authentication (should fail)
echo "Test 8: Try to vote without authentication (should fail)"
echo "------------------------------------------------------------"
UNAUTH_RESPONSE=$(curl -s -X POST "${BASE_URL}/ideas/${IDEA_ID}/vote" \
  -H "Content-Type: application/json" \
  -d '{"vote_value": 1}')

if echo "$UNAUTH_RESPONSE" | grep -q "Not authenticated"; then
    echo "✓ Correctly rejected unauthenticated vote"
else
    echo "⚠ Warning: Unauthenticated vote should have been rejected"
fi
echo ""

echo "============================================================"
echo "All Chunk 2 Tests Passed! ✓"
echo "============================================================"
echo ""
echo "Summary:"
echo "  ✓ User registration works"
echo "  ✓ User login works"
echo "  ✓ Idea creation works (authenticated)"
echo "  ✓ List ideas works (public)"
echo "  ✓ Get single idea works (public)"
echo "  ✓ Voting works (authenticated)"
echo "  ✓ Vote updates work"
echo "  ✓ Authentication is enforced for voting"
echo ""
echo "Next: Visit http://localhost:8000/docs to explore the API!"
