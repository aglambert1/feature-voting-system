#!/bin/bash

# Test script for product embedding functionality

# Get token
echo "=== Getting auth token ==="
TOKEN=$(curl -s -X POST 'http://localhost:8000/auth/login' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=admin&password=password' | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

echo "Token: ${TOKEN:0:20}..."

# Create product
echo ""
echo "=== Creating product ==="
PRODUCT=$(curl -s -X POST 'http://localhost:8000/product-intelligence/products' \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"product_name":"Test Product for Embeddings","product_description":"A comprehensive task management application that helps teams organize their work efficiently."}')

echo "$PRODUCT" | python3 -m json.tool

PRODUCT_ID=$(echo "$PRODUCT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', 0))")
echo "Product ID: $PRODUCT_ID"

if [ "$PRODUCT_ID" = "0" ]; then
  echo "Failed to create product!"
  exit 1
fi

# Analyze product (this should generate embeddings)
echo ""
echo "=== Analyzing product (should generate embeddings) ==="
ANALYSIS=$(curl -s -X POST "http://localhost:8000/product-intelligence/products/$PRODUCT_ID/analyze" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"product_description":"A comprehensive task management application that helps teams organize their work efficiently. Features include: kanban boards for visual project management, time tracking for productivity insights, real-time collaboration for seamless teamwork, custom workflows to match your process, and integrations with popular tools.","source_type":"text"}')

echo "$ANALYSIS" | python3 -m json.tool | head -50

# Test product search
echo ""
echo "=== Testing product search ==="
SEARCH=$(curl -s -X GET "http://localhost:8000/product-intelligence/products/$PRODUCT_ID/search?q=kanban%20board%20for%20project%20management&threshold=0.5" \
  -H "Authorization: Bearer $TOKEN")

echo "$SEARCH" | python3 -m json.tool

echo ""
echo "=== Test complete ==="
