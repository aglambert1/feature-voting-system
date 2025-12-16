#!/bin/bash
TOKEN=$(curl -s -X POST "http://localhost:8000/auth/login" -H "Content-Type: application/x-www-form-urlencoded" -d "username=admin&password=password" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

IDEA_ID=$(curl -s -X GET "http://localhost:8000/competitor-intelligence/sessions/9999/generated-ideas" -H "Authorization: Bearer $TOKEN" | python3 -c "import sys, json; ideas=json.load(sys.stdin).get('ideas', []); print(ideas[0]['id'] if ideas else '')")

echo "IDEA_ID: $IDEA_ID"

curl -s -X PUT "http://localhost:8000/competitor-intelligence/generated-ideas/$IDEA_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"what": "EDITED WHAT", "why": "EDITED WHY", "use_case": "EDITED USE CASE"}' | python3 -m json.tool
