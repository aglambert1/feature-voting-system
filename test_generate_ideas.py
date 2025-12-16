#!/usr/bin/env python3
"""Quick test of generate-ideas endpoint"""

import requests

# Login
login_response = requests.post(
    "http://localhost:8000/auth/login",
    data={"username": "admin", "password": "password"}
)
token = login_response.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Test generate-ideas
response = requests.post(
    "http://localhost:8000/competitor-intelligence/sessions/9999/generate-ideas",
    headers=headers
)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")
