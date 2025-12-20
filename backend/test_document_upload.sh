#!/bin/bash

# Test document upload and URL fetching

# Get token
TOKEN=$(curl -s -X POST 'http://localhost:8000/auth/login' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=admin&password=password' | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

echo "=== Testing URL fetching ==="
URL_RESULT=$(curl -s -X POST 'http://localhost:8000/product-intelligence/products/fetch-url' \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com"}')

echo "$URL_RESULT" | python3 -m json.tool | head -30

echo ""
echo "=== Creating a simple test text file ==="
echo "This is a test product specification document.

Product Name: Advanced Analytics Platform

Features:
- Real-time data visualization
- Custom dashboard creation
- API access for data export
- Machine learning integration
- Automated reporting

Target Users: Data analysts, business intelligence teams, and product managers who need to make data-driven decisions." > /tmp/test_spec.txt

echo "=== Testing document upload ==="
UPLOAD_RESULT=$(curl -s -X POST 'http://localhost:8000/product-intelligence/products/upload-document' \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/tmp/test_spec.txt")

echo "$UPLOAD_RESULT" | python3 -m json.tool

echo ""
echo "=== Test complete ==="
