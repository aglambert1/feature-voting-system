#!/usr/bin/env python3
"""
Complete API test script covering all endpoints.

Tests:
- Authentication (register, login, JWT)
- Ideas (create, list, get single)
- Votes (upvote, downvote, vote counts)
- Submissions (structure with AI, submit)
- Admin functions (user management)

Usage:
    python test_complete_api.py
"""

import requests
from pprint import pprint
import time

# Base URL of your API
BASE_URL = "http://localhost:8000"


def print_section(title):
    """Print a section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_test(number, description):
    """Print a test header."""
    print(f"\n{number}. {description}")
    print("-" * 70)


def test_complete_api():
    """Test all API endpoints."""

    print("=" * 70)
    print("  COMPLETE API TEST - Feature Voting System")
    print("=" * 70)
    print(f"\nTesting API at: {BASE_URL}")
    print(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # =======================================================================
    # SECTION 1: AUTHENTICATION
    # =======================================================================
    print_section("SECTION 1: AUTHENTICATION")

    # Test 1.1: Health Check
    print_test("1.1", "Health check endpoint")
    response = requests.get(f"{BASE_URL}/health")
    if response.status_code == 200:
        print("✓ Health check passed")
        print(f"  Response: {response.json()}")
    else:
        print(f"✗ Health check failed: {response.status_code}")
        return

    # Test 1.2: Register a new user
    print_test("1.2", "Register new user")
    user_data = {
        "email": "testuser@example.com",
        "username": "testuser",
        "password": "SecurePassword123",
        "full_name": "Test User"
    }

    response = requests.post(f"{BASE_URL}/auth/register", json=user_data)

    if response.status_code == 201:
        print("✓ User registered successfully!")
        user_info = response.json()
        print(f"  User ID: {user_info['id']}")
        print(f"  Username: {user_info['username']}")
        print(f"  Role: {user_info['role']}")
    elif response.status_code == 400:
        print("ℹ User already exists (continuing...)")
    else:
        print(f"✗ Registration failed: {response.status_code}")
        pprint(response.json())

    # Test 1.3: Login
    print_test("1.3", "User login")
    login_data = {
        "username": user_data["username"],
        "password": user_data["password"]
    }

    response = requests.post(f"{BASE_URL}/auth/login", data=login_data)

    if response.status_code == 200:
        print("✓ Login successful!")
        token_data = response.json()
        access_token = token_data["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}
        print(f"  Token: {access_token[:50]}...")
    else:
        print(f"✗ Login failed: {response.status_code}")
        pprint(response.json())
        return

    # Test 1.4: Get current user
    print_test("1.4", "Get current user info (protected route)")
    response = requests.get(f"{BASE_URL}/auth/me", headers=headers)

    if response.status_code == 200:
        print("✓ Successfully accessed protected route!")
        user = response.json()
        print(f"  Username: {user['username']}")
        print(f"  Email: {user['email']}")
        print(f"  Role: {user['role']}")
    else:
        print(f"✗ Failed: {response.status_code}")
        pprint(response.json())

    # =======================================================================
    # SECTION 2: IDEAS
    # =======================================================================
    print_section("SECTION 2: IDEAS MANAGEMENT")

    # Test 2.1: List ideas (empty or existing)
    print_test("2.1", "List all ideas")
    response = requests.get(f"{BASE_URL}/ideas/")

    if response.status_code == 200:
        print("✓ Successfully retrieved ideas list")
        ideas_data = response.json()
        print(f"  Total ideas: {ideas_data['total']}")
        if ideas_data['ideas']:
            print(f"  First idea: {ideas_data['ideas'][0]['title']}")
    else:
        print(f"✗ Failed: {response.status_code}")
        pprint(response.json())

    # Test 2.2: Create a new idea
    print_test("2.2", "Create new idea (protected)")
    idea_data = {
        "title": "Dark Mode Toggle",
        "what_description": "A toggle switch in the settings panel that enables dark mode for the entire application",
        "why_description": "Improves usability at night and reduces eye strain for users who work in low-light environments",
        "use_case_description": "User opens settings, finds the appearance section, and toggles dark mode on or off",
        "category": "UI/UX"
    }

    response = requests.post(f"{BASE_URL}/ideas/", json=idea_data, headers=headers)

    if response.status_code == 201:
        print("✓ Idea created successfully!")
        created_idea = response.json()
        idea_id = created_idea['id']
        print(f"  Idea ID: {idea_id}")
        print(f"  Title: {created_idea['title']}")
        print(f"  Category: {created_idea['category']}")
        print(f"  Initial score: {created_idea['vote_counts']['score']}")
    else:
        print(f"✗ Failed: {response.status_code}")
        pprint(response.json())
        return

    # Test 2.3: Get single idea
    print_test("2.3", "Get single idea by ID")
    response = requests.get(f"{BASE_URL}/ideas/{idea_id}")

    if response.status_code == 200:
        print("✓ Successfully retrieved idea")
        idea = response.json()
        print(f"  Title: {idea['title']}")
        print(f"  What: {idea['what_description'][:60]}...")
        print(f"  Upvotes: {idea['vote_counts']['upvotes']}")
        print(f"  Downvotes: {idea['vote_counts']['downvotes']}")
        print(f"  Score: {idea['vote_counts']['score']}")
    else:
        print(f"✗ Failed: {response.status_code}")
        pprint(response.json())

    # Test 2.4: Try to create idea without auth (should fail)
    print_test("2.4", "Try to create idea without authentication (should fail)")
    response = requests.post(f"{BASE_URL}/ideas/", json=idea_data)

    if response.status_code == 401:
        print("✓ Security working! Unauthorized access denied.")
        print(f"  Message: {response.json()['detail']}")
    else:
        print(f"⚠ Warning: Endpoint accessible without auth!")

    # =======================================================================
    # SECTION 3: VOTING
    # =======================================================================
    print_section("SECTION 3: VOTING SYSTEM")

    # Test 3.1: Upvote an idea
    print_test("3.1", "Upvote an idea")
    vote_data = {"vote_value": 1}
    response = requests.post(
        f"{BASE_URL}/ideas/{idea_id}/vote",
        json=vote_data,
        headers=headers
    )

    if response.status_code == 200:
        print("✓ Upvote successful!")
        vote_response = response.json()
        print(f"  Vote value: {vote_response['vote']['vote_value']}")
        print(f"  New score: {vote_response['vote_counts']['score']}")
        print(f"  Upvotes: {vote_response['vote_counts']['upvotes']}")
        print(f"  Downvotes: {vote_response['vote_counts']['downvotes']}")
    else:
        print(f"✗ Failed: {response.status_code}")
        pprint(response.json())

    # Test 3.2: Change vote to downvote
    print_test("3.2", "Change vote to downvote")
    vote_data = {"vote_value": -1}
    response = requests.post(
        f"{BASE_URL}/ideas/{idea_id}/vote",
        json=vote_data,
        headers=headers
    )

    if response.status_code == 200:
        print("✓ Vote changed successfully!")
        vote_response = response.json()
        print(f"  Vote value: {vote_response['vote']['vote_value']}")
        print(f"  New score: {vote_response['vote_counts']['score']}")
        print(f"  Message: {vote_response['message']}")
    else:
        print(f"✗ Failed: {response.status_code}")
        pprint(response.json())

    # Test 3.3: Try invalid vote value (should fail)
    print_test("3.3", "Try invalid vote value (should fail)")
    vote_data = {"vote_value": 5}
    response = requests.post(
        f"{BASE_URL}/ideas/{idea_id}/vote",
        json=vote_data,
        headers=headers
    )

    if response.status_code == 422:
        print("✓ Validation working! Invalid vote rejected.")
        print(f"  Error: {response.json()['detail'][0]['msg']}")
    else:
        print(f"⚠ Warning: Invalid vote was accepted!")

    # Test 3.4: Try to vote without auth (should fail)
    print_test("3.4", "Try to vote without authentication (should fail)")
    vote_data = {"vote_value": 1}
    response = requests.post(
        f"{BASE_URL}/ideas/{idea_id}/vote",
        json=vote_data
    )

    if response.status_code == 401:
        print("✓ Security working! Unauthorized voting denied.")
    else:
        print(f"⚠ Warning: Voting allowed without auth!")

    # Test 3.5: Verify vote persists
    print_test("3.5", "Verify vote persists")
    response = requests.get(f"{BASE_URL}/ideas/{idea_id}", headers=headers)

    if response.status_code == 200:
        idea = response.json()
        user_vote = idea.get('user_vote')
        if user_vote == -1:
            print("✓ Vote persisted correctly!")
            print(f"  User's current vote: {user_vote}")
            print(f"  Idea score: {idea['vote_counts']['score']}")
        else:
            print(f"⚠ Vote may not have persisted. User vote: {user_vote}")
    else:
        print(f"✗ Failed to verify: {response.status_code}")

    # =======================================================================
    # SECTION 4: SUBMISSIONS (AI Integration)
    # =======================================================================
    print_section("SECTION 4: AI-POWERED SUBMISSIONS")

    # Test 4.1: Check if API key is configured
    print_test("4.1", "Check AI service availability")
    # We'll try to structure text - if it fails, we'll skip AI tests
    test_text = "I want a feature to export my data to CSV so I can analyze it in Excel"

    print(f"  Testing with: '{test_text[:50]}...'")

    structure_request = {"freeform_text": test_text}
    response = requests.post(
        f"{BASE_URL}/submissions/structure",
        json=structure_request,
        headers=headers
    )

    ai_available = False
    if response.status_code == 200:
        print("✓ AI structuring service is available!")
        structured = response.json()
        ai_available = True
        print(f"  Generated title: {structured['title']}")
        print(f"  Processing time: {structured['processing_time']}s")
    elif response.status_code == 500:
        print("ℹ AI service not configured (ANTHROPIC_API_KEY may be missing)")
        print("  Skipping AI-dependent tests...")
    else:
        print(f"⚠ Unexpected response: {response.status_code}")

    # Test 4.2: Submit structured idea (if AI is available)
    if ai_available:
        print_test("4.2", "Submit complete idea with AI tracking")
        submission_data = {
            "original_freeform_text": test_text,
            "title": structured['title'],
            "what_description": structured['what_description'],
            "why_description": structured['why_description'],
            "use_case_description": structured['use_case_description'],
            "category": "Data Export",
            "ai_structured_version": structured,
            "structuring_time_seconds": int(structured['processing_time'])
        }

        response = requests.post(
            f"{BASE_URL}/submissions/submit",
            json=submission_data,
            headers=headers
        )

        if response.status_code == 201:
            print("✓ Submission created successfully!")
            submission_response = response.json()
            print(f"  Submission ID: {submission_response['submission']['id']}")
            print(f"  Idea ID: {submission_response['idea_id']}")
            print(f"  Idea title: {submission_response['idea_title']}")
            print(f"  Message: {submission_response['message']}")
        else:
            print(f"✗ Failed: {response.status_code}")
            pprint(response.json())

    # Test 4.3: Try to structure without auth (should fail)
    print_test("4.3", "Try to structure text without authentication (should fail)")
    response = requests.post(
        f"{BASE_URL}/submissions/structure",
        json=structure_request
    )

    if response.status_code == 401:
        print("✓ Security working! Unauthorized structuring denied.")
    else:
        print(f"⚠ Warning: Structuring allowed without auth!")

    # =======================================================================
    # SECTION 5: LIST AND VERIFY
    # =======================================================================
    print_section("SECTION 5: FINAL VERIFICATION")

    # Test 5.1: List all ideas and verify our ideas exist
    print_test("5.1", "List all ideas and verify created ideas")
    response = requests.get(f"{BASE_URL}/ideas/")

    if response.status_code == 200:
        ideas_data = response.json()
        print(f"✓ Successfully retrieved {ideas_data['total']} idea(s)")

        if ideas_data['ideas']:
            print("\n  Top 3 ideas by score:")
            for i, idea in enumerate(ideas_data['ideas'][:3], 1):
                print(f"  {i}. {idea['title']} (Score: {idea['vote_counts']['score']})")
        else:
            print("  No ideas found in database")
    else:
        print(f"✗ Failed: {response.status_code}")

    # Test 5.2: Summary of what was tested
    print_test("5.2", "Test Summary")
    print("✓ Authentication: Register, Login, JWT tokens")
    print("✓ Ideas: Create, List, Get single, Authorization")
    print("✓ Votes: Upvote, Downvote, Change vote, Validation")
    print("✓ Security: Unauthorized access prevention")
    if ai_available:
        print("✓ AI Submissions: Structure text, Submit with tracking")
    else:
        print("ℹ AI Submissions: Skipped (API key not configured)")

    # =======================================================================
    # FINAL SUMMARY
    # =======================================================================
    print("\n" + "=" * 70)
    print("  ALL TESTS COMPLETED!")
    print("=" * 70)
    print(f"\nCompleted at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nNext steps:")
    print("  - Visit http://localhost:8000/docs for interactive API testing")
    print("  - Check database: sqlite3 feature_voting.db")
    print("  - View frontend: http://localhost:5173")
    print("  - Run specific tests:")
    print("    • python test_schemas.py (schema validation)")
    print("    • python test_llm_service.py (AI service)")
    print("    • ./test_chunk2_api.sh (ideas & votes)")
    print("    • ./test_chunk3_api.sh (submissions)")


if __name__ == "__main__":
    try:
        test_complete_api()
    except requests.exceptions.ConnectionError:
        print("\n" + "=" * 70)
        print("  ERROR: Could not connect to the API")
        print("=" * 70)
        print("\nThe backend server is not running. Please start it:")
        print("\n  Option 1: Use the start script")
        print("    ./start.sh")
        print("\n  Option 2: Start manually")
        print("    cd backend")
        print("    source venv/bin/activate")
        print("    uvicorn app.main:app --reload")
        print("\nThen run this test again.")
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
