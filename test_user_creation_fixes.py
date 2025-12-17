#!/usr/bin/env python3
"""
Test script to verify the user creation fixes:
1. Full name should be optional
2. Role should be respected when creating a user
"""

import requests
import sys
import random
import string

BASE_URL = "http://127.0.0.1:8000"

def random_string(length=8):
    """Generate random string for unique usernames"""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def login_as_admin():
    """Login as admin and get token"""
    print("🔐 Logging in as admin...")
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={
            "username": "admin",
            "password": "password"
        }
    )

    if response.status_code != 200:
        print(f"❌ Failed to login as admin: {response.text}")
        sys.exit(1)

    token = response.json()["access_token"]
    print("✅ Admin login successful")
    return token

def test_create_user_without_full_name(token):
    """Test 1: Create user without full_name (should work)"""
    print("\n📝 Test 1: Creating user without full_name...")

    username = f"testuser_{random_string()}"
    response = requests.post(
        f"{BASE_URL}/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "password123",
            "role": "voter"
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    if response.status_code == 201:
        user = response.json()
        if user["full_name"] is None:
            print(f"✅ Test 1 PASSED: User created without full_name")
            print(f"   - Username: {user['username']}")
            print(f"   - Full Name: {user['full_name']}")
            return True
        else:
            print(f"❌ Test 1 FAILED: full_name should be None but got: {user['full_name']}")
            return False
    else:
        print(f"❌ Test 1 FAILED: Status {response.status_code}")
        print(f"   Response: {response.text}")
        return False

def test_create_user_with_role(token):
    """Test 2: Create user with specific role (should work)"""
    print("\n📝 Test 2: Creating user with product_owner role...")

    username = f"po_{random_string()}"
    response = requests.post(
        f"{BASE_URL}/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "password123",
            "full_name": "Product Owner Test",
            "role": "product_owner"
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    if response.status_code == 201:
        user = response.json()
        if user["role"] == "product_owner":
            print(f"✅ Test 2 PASSED: User created with product_owner role")
            print(f"   - Username: {user['username']}")
            print(f"   - Role: {user['role']}")
            return True
        else:
            print(f"❌ Test 2 FAILED: Expected role 'product_owner' but got '{user['role']}'")
            return False
    else:
        print(f"❌ Test 2 FAILED: Status {response.status_code}")
        print(f"   Response: {response.text}")
        return False

def test_create_admin_user(token):
    """Test 3: Create user with admin role (should work)"""
    print("\n📝 Test 3: Creating user with admin role...")

    username = f"admin_{random_string()}"
    response = requests.post(
        f"{BASE_URL}/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "password123",
            "role": "admin"
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    if response.status_code == 201:
        user = response.json()
        if user["role"] == "admin":
            print(f"✅ Test 3 PASSED: User created with admin role")
            print(f"   - Username: {user['username']}")
            print(f"   - Role: {user['role']}")
            return True
        else:
            print(f"❌ Test 3 FAILED: Expected role 'admin' but got '{user['role']}'")
            return False
    else:
        print(f"❌ Test 3 FAILED: Status {response.status_code}")
        print(f"   Response: {response.text}")
        return False

def test_default_role_without_specifying(token):
    """Test 4: Create user without specifying role (should default to voter)"""
    print("\n📝 Test 4: Creating user without specifying role (should default to voter)...")

    username = f"default_{random_string()}"
    response = requests.post(
        f"{BASE_URL}/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "password123",
            "full_name": "Default Role Test"
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    if response.status_code == 201:
        user = response.json()
        if user["role"] == "voter":
            print(f"✅ Test 4 PASSED: User defaulted to voter role")
            print(f"   - Username: {user['username']}")
            print(f"   - Role: {user['role']}")
            return True
        else:
            print(f"❌ Test 4 FAILED: Expected role 'voter' but got '{user['role']}'")
            return False
    else:
        print(f"❌ Test 4 FAILED: Status {response.status_code}")
        print(f"   Response: {response.text}")
        return False

def main():
    print("=" * 60)
    print("Testing User Creation Fixes")
    print("=" * 60)

    # Login
    token = login_as_admin()

    # Run tests
    results = []
    results.append(test_create_user_without_full_name(token))
    results.append(test_create_user_with_role(token))
    results.append(test_create_admin_user(token))
    results.append(test_default_role_without_specifying(token))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Tests Passed: {passed}/{total}")

    if passed == total:
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        print("⚠️  Some tests failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
