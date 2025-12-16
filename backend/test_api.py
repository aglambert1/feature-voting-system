"""
Simple script to test the API.

This shows you how to interact with your API using Python.
Run this after starting the server to test that everything works!

Usage:
    python test_api.py
"""

import requests
from pprint import pprint
import pytest

# Base URL of your API
BASE_URL = "http://localhost:8000"


def check_server_running():
    """Check if the backend server is running."""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=1)
        return response.status_code == 200
    except:
        return False


@pytest.mark.skipif(not check_server_running(), reason="Backend server not running on localhost:8000")
def test_api():
    """Test the main API endpoints."""

    print("=" * 60)
    print("Testing Feature Voting System API")
    print("=" * 60)

    # Test 1: Health Check
    print("\n1. Testing health check endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    pprint(response.json())

    # Test 2: Register a new user
    print("\n2. Registering a new user...")
    user_data = {
        "email": "demo@example.com",
        "username": "demouser",
        "password": "SecurePassword123",
        "full_name": "Demo User"
    }

    response = requests.post(f"{BASE_URL}/auth/register", json=user_data)

    if response.status_code == 201:
        print(f"✓ User registered successfully!")
        pprint(response.json())
    elif response.status_code == 400:
        print(f"ℹ User already exists (that's okay!)")
        print(f"  {response.json()['detail']}")
    else:
        print(f"✗ Registration failed: {response.status_code}")
        pprint(response.json())

    # Test 3: Login
    print("\n3. Logging in...")
    login_data = {
        "username": user_data["username"],
        "password": user_data["password"]
    }

    response = requests.post(f"{BASE_URL}/auth/login", data=login_data)

    if response.status_code == 200:
        print(f"✓ Login successful!")
        token_data = response.json()
        access_token = token_data["access_token"]
        print(f"  Token type: {token_data['token_type']}")
        print(f"  Access token: {access_token[:50]}...")
    else:
        print(f"✗ Login failed: {response.status_code}")
        pprint(response.json())
        return

    # Test 4: Get current user info (protected route)
    print("\n4. Getting current user info (protected route)...")
    headers = {"Authorization": f"Bearer {access_token}"}

    response = requests.get(f"{BASE_URL}/auth/me", headers=headers)

    if response.status_code == 200:
        print(f"✓ Successfully accessed protected route!")
        pprint(response.json())
    else:
        print(f"✗ Failed to access protected route: {response.status_code}")
        pprint(response.json())

    # Test 5: Try accessing without token (should fail)
    print("\n5. Testing security - accessing protected route without token...")
    response = requests.get(f"{BASE_URL}/auth/me")

    if response.status_code == 401:
        print(f"✓ Security working correctly! Unauthorized access denied.")
        print(f"  {response.json()['detail']}")
    else:
        print(f"⚠ Warning: Protected route accessible without token!")

    # Test 6: Login as admin
    print("\n6. Testing admin login...")
    admin_login_data = {
        "username": "admin",
        "password": "change-this-secure-password"
    }

    response = requests.post(f"{BASE_URL}/auth/login", data=admin_login_data)

    if response.status_code == 200:
        print(f"✓ Admin login successful!")
        admin_token = response.json()["access_token"]
        print(f"  Admin token: {admin_token[:50]}...")
    else:
        print(f"ℹ Admin login failed (may need to update credentials in .env)")
        print(f"  Status: {response.status_code}")
        admin_token = None

    # Test 7: Get all users (admin only)
    if admin_token:
        print("\n7. Getting all users (admin endpoint)...")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        response = requests.get(f"{BASE_URL}/auth/users", headers=admin_headers)

        if response.status_code == 200:
            print(f"✓ Successfully retrieved all users!")
            users = response.json()
            print(f"  Total users: {len(users)}")
            for user in users:
                print(f"  - {user['username']}: {user['role']}")
        else:
            print(f"✗ Failed to get users: {response.status_code}")
            pprint(response.json())

        # Test 8: Try admin endpoint with regular user token (should fail)
        print("\n8. Testing admin-only security - regular user accessing admin endpoint...")
        response = requests.get(f"{BASE_URL}/auth/users", headers=headers)

        if response.status_code == 403:
            print(f"✓ Security working correctly! Non-admin access denied.")
            print(f"  {response.json()['detail']}")
        else:
            print(f"⚠ Warning: Admin endpoint accessible to non-admin user!")

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)
    print("\nNext steps:")
    print("- Visit http://localhost:8000/docs to explore the interactive API")
    print("- Read the code comments in app/ to understand how it works")
    print("- Try adding more endpoints and features!")


if __name__ == "__main__":
    try:
        test_api()
    except requests.exceptions.ConnectionError:
        print("✗ Error: Could not connect to the API")
        print("\nMake sure the server is running:")
        print("  cd backend")
        print("  source venv/bin/activate")
        print("  uvicorn app.main:app --reload")
    except Exception as e:
        print(f"✗ Error: {e}")
