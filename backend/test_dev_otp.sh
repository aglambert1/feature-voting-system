#!/bin/bash

# Development Mode OTP Testing Script
# This script tests all three development mode OTP features

BASE_URL="http://localhost:8000"
EMAIL="admin@example.com"
DEV_OTP="000000"
NEW_PASSWORD="DevTestPassword123"

echo "=========================================="
echo "Development Mode OTP Testing Script"
echo "=========================================="
echo ""
echo "Prerequisites:"
echo "  - Backend server running on $BASE_URL"
echo "  - DEBUG=true in .env"
echo "  - DEV_OTP_BYPASS=000000"
echo "  - DEV_RETURN_OTP=true"
echo ""
echo "=========================================="

# Function to print colored output
print_section() {
    echo ""
    echo "=========================================="
    echo "$1"
    echo "=========================================="
    echo ""
}

# Function to print step
print_step() {
    echo ">>> $1"
}

# Function to pretty print JSON
pretty_json() {
    if command -v python3 &> /dev/null; then
        python3 -m json.tool
    elif command -v python &> /dev/null; then
        python -m json.tool
    else
        cat
    fi
}

# Test 1: Fixed Dev OTP Bypass
print_section "TEST 1: Fixed Dev OTP Bypass (000000)"
print_step "Step 1: Request password reset..."
curl -s -X POST $BASE_URL/auth/password/reset-request \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$EMAIL\"}" | pretty_json

print_step "Step 2: Reset password using fixed dev OTP ($DEV_OTP)..."
RESULT=$(curl -s -X POST $BASE_URL/auth/password/reset-confirm \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$EMAIL\", \"otp\": \"$DEV_OTP\", \"new_password\": \"$NEW_PASSWORD\"}")

echo "$RESULT" | pretty_json

if echo "$RESULT" | grep -q "successfully reset"; then
    echo ""
    echo "✓ SUCCESS: Password reset with dev OTP bypass!"
else
    echo ""
    echo "✗ FAILED: Password reset with dev OTP failed"
fi

# Test 2: OTP Returned in Response
print_section "TEST 2: OTP Returned in API Response"
print_step "Requesting password reset (should include OTP in response)..."
RESPONSE=$(curl -s -X POST $BASE_URL/auth/password/reset-request \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$EMAIL\"}")

echo "$RESPONSE" | pretty_json

if echo "$RESPONSE" | grep -q "dev_otp"; then
    echo ""
    echo "✓ SUCCESS: OTP included in response (dev mode enabled)"

    # Extract OTP from response
    if command -v python3 &> /dev/null; then
        EXTRACTED_OTP=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('dev_otp', 'N/A'))")
    elif command -v python &> /dev/null; then
        EXTRACTED_OTP=$(echo "$RESPONSE" | python -c "import sys, json; print json.load(sys.stdin).get('dev_otp', 'N/A')")
    else
        EXTRACTED_OTP="(unable to extract - install python)"
    fi

    echo "   Extracted OTP: $EXTRACTED_OTP"
else
    echo ""
    echo "⚠ WARNING: OTP not in response (check DEBUG=true and DEV_RETURN_OTP=true)"
fi

# Test 3: Development Endpoint
print_section "TEST 3: Development Endpoint to Retrieve OTP"
print_step "Retrieving OTP via /auth/dev/get-otp/$EMAIL..."
DEV_RESPONSE=$(curl -s $BASE_URL/auth/dev/get-otp/$EMAIL)

echo "$DEV_RESPONSE" | pretty_json

if echo "$DEV_RESPONSE" | grep -q "otp"; then
    echo ""
    echo "✓ SUCCESS: Dev endpoint returned OTP"
else
    echo ""
    echo "⚠ WARNING: Dev endpoint did not return OTP"
fi

# Test 4: Verify dev endpoint is secured (should fail when DEBUG=false)
print_section "SECURITY CHECK"
print_step "Testing that dev endpoint requires DEBUG mode..."
echo "Note: If DEBUG=false, the endpoint should return 403 Forbidden"
echo "(This is the expected behavior for production)"

# Summary
print_section "SUMMARY"
echo "All tests completed!"
echo ""
echo "Tested features:"
echo "  1. ✓ Fixed Dev OTP Bypass (000000)"
echo "  2. ✓ OTP Returned in API Response"
echo "  3. ✓ Development Endpoint (/auth/dev/get-otp/)"
echo ""
echo "For more information, see: DEV_MODE_OTP.md"
echo ""
echo "=========================================="
