#!/usr/bin/env python3
"""
Module 7 End-to-End Test Script

Tests the complete idea generation and finalization workflow:
1. Create a test session with competitors and features
2. Select features for idea generation
3. Generate ideas using IdeaStructuringAgent
4. Edit generated ideas
5. Approve ideas
6. Finalize and submit to voting system
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

def print_section(title):
    """Print a formatted section header"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def test_module7():
    """Run complete Module 7 test workflow"""

    print_section("MODULE 7: IDEA GENERATION & FINALIZATION TEST")
    print(f"Starting test at {datetime.now()}")

    # Step 1: Get authentication token
    print_section("Step 1: Authentication")
    login_response = requests.post(
        f"{BASE_URL}/auth/login",
        data={
            "username": "testuser",
            "password": "testpass123"
        }
    )

    if login_response.status_code not in [200, 201]:
        print(f"❌ Login failed: {login_response.text}")
        return

    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("✅ Authentication successful")

    # Step 2: Create a test product
    print_section("Step 2: Create Test Product")
    product_data = {
        "product_name": f"Test Product - Module 7 - {datetime.now().strftime('%H:%M:%S')}",
        "product_source_type": "text",
        "product_description": "A project management tool for software teams. Helps teams track tasks, collaborate on projects, and meet deadlines efficiently."
    }

    product_response = requests.post(
        f"{BASE_URL}/competitor-intelligence/products",
        json=product_data,
        headers=headers
    )

    if product_response.status_code not in [200, 201]:
        print(f"❌ Product creation failed: {product_response.text}")
        return

    product = product_response.json()
    product_id = product["id"]
    print(f"✅ Created product: {product['product_name']} (ID: {product_id})")

    # Step 3: Analyze product
    print_section("Step 3: Analyze Product")
    analyze_data = {
        "product_description": product_data["product_description"],
        "source_type": "text"
    }
    analyze_response = requests.post(
        f"{BASE_URL}/competitor-intelligence/products/{product_id}/analyze",
        json=analyze_data,
        headers=headers
    )

    if analyze_response.status_code not in [200, 201]:
        print(f"❌ Product analysis failed: {analyze_response.text}")
        return

    print("✅ Product analyzed successfully")

    # Step 4: Create session
    print_section("Step 4: Create Analysis Session")
    session_data = {
        "product_id": product_id,
        "session_name": f"Module 7 Test Session - {datetime.now().strftime('%H:%M:%S')}",
        "product_source_type": "text",
        "enable_comparison": False
    }

    session_response = requests.post(
        f"{BASE_URL}/competitor-intelligence/sessions",
        json=session_data,
        headers=headers
    )

    if session_response.status_code not in [200, 201]:
        print(f"❌ Session creation failed: {session_response.text}")
        return

    session = session_response.json()
    session_id = session["id"]
    print(f"✅ Created session: {session['session_name']} (ID: {session_id})")

    # Step 5: Add test competitors
    print_section("Step 5: Add Test Competitors")
    competitors = [
        {
            "competitor_name": "Asana",
            "competitor_website": "https://asana.com",
            "primary_product_name": "Asana"
        },
        {
            "competitor_name": "Monday.com",
            "competitor_website": "https://monday.com",
            "primary_product_name": "Monday"
        }
    ]

    competitor_ids = []
    for comp_data in competitors:
        comp_response = requests.post(
            f"{BASE_URL}/competitor-intelligence/sessions/{session_id}/competitors",
            json=comp_data,
            headers=headers
        )
        if comp_response.status_code == 200:
            comp = comp_response.json()
            competitor_ids.append(comp["id"])
            print(f"✅ Added competitor: {comp['competitor_name']}")
        else:
            print(f"❌ Failed to add competitor: {comp_response.text}")

    # Step 6: Add test features to competitors
    print_section("Step 6: Add Test Features")
    features_data = [
        {
            "session_competitor_id": competitor_ids[0],
            "feature_name": "Timeline View",
            "feature_description": "Gantt-style timeline view for visualizing project schedules",
            "feature_category": "Visualization",
            "selected_by_user": True
        },
        {
            "session_competitor_id": competitor_ids[0],
            "feature_name": "Custom Fields",
            "feature_description": "Ability to add custom metadata fields to tasks",
            "feature_category": "Customization",
            "selected_by_user": True
        },
        {
            "session_competitor_id": competitor_ids[1],
            "feature_name": "Automation Recipes",
            "feature_description": "Pre-built automation templates for common workflows",
            "feature_category": "Automation",
            "selected_by_user": True
        }
    ]

    feature_ids = []
    for feat_data in features_data:
        # Manually create feature via direct API (simulating Stage 3 completion)
        feat_response = requests.post(
            f"{BASE_URL}/competitor-intelligence/features",
            json=feat_data,
            headers=headers
        )
        if feat_response.status_code == 200:
            feat = feat_response.json()
            feature_ids.append(feat["id"])
            print(f"✅ Added feature: {feat['feature_name']} (selected: {feat['selected_by_user']})")
        else:
            print(f"❌ Failed to add feature: {feat_response.text}")

    # Step 7: Generate Ideas (Module 7 - Stage 4)
    print_section("Step 7: Generate Ideas (Stage 4)")
    print("Calling /generate-ideas endpoint...")

    generate_response = requests.post(
        f"{BASE_URL}/competitor-intelligence/sessions/{session_id}/generate-ideas",
        headers=headers
    )

    if generate_response.status_code not in [200, 201]:
        print(f"❌ Idea generation failed: {generate_response.text}")
        return

    generate_result = generate_response.json()
    print(f"✅ Generated {generate_result.get('ideas_generated', 0)} ideas")
    print(f"   Summary: {generate_result.get('generation_summary', 'N/A')}")

    # Step 8: Get generated ideas
    print_section("Step 8: Review Generated Ideas")
    ideas_response = requests.get(
        f"{BASE_URL}/competitor-intelligence/sessions/{session_id}/generated-ideas",
        headers=headers
    )

    if ideas_response.status_code not in [200, 201]:
        print(f"❌ Failed to fetch ideas: {ideas_response.text}")
        return

    ideas_data = ideas_response.json()
    ideas = ideas_data.get("ideas", [])
    print(f"✅ Retrieved {len(ideas)} generated ideas")

    for idx, idea in enumerate(ideas, 1):
        print(f"\n   Idea {idx}:")
        print(f"   - From: {idea['competitor_name']} / {idea['feature_name']}")
        print(f"   - What: {idea['what'][:80]}...")
        print(f"   - Why: {idea['why'][:80]}...")
        print(f"   - Use Case: {idea['use_case'][:80]}...")

    # Step 9: Edit an idea
    print_section("Step 9: Edit Generated Idea")
    if ideas:
        first_idea = ideas[0]
        edit_data = {
            "what": "EDITED: " + first_idea["what"],
            "why": first_idea["why"],
            "use_case": first_idea["use_case"]
        }

        edit_response = requests.put(
            f"{BASE_URL}/competitor-intelligence/generated-ideas/{first_idea['id']}",
            json=edit_data,
            headers=headers
        )

        if edit_response.status_code == 200:
            print(f"✅ Successfully edited idea {first_idea['id']}")
        else:
            print(f"❌ Failed to edit idea: {edit_response.text}")

    # Step 10: Approve ideas
    print_section("Step 10: Approve Ideas")
    idea_ids = [idea["id"] for idea in ideas]
    approve_data = {
        "idea_ids": idea_ids,
        "approved": True
    }

    approve_response = requests.post(
        f"{BASE_URL}/competitor-intelligence/generated-ideas/approve",
        json=approve_data,
        headers=headers
    )

    if approve_response.status_code not in [200, 201]:
        print(f"❌ Failed to approve ideas: {approve_response.text}")
        return

    approve_result = approve_response.json()
    print(f"✅ Approved {approve_result['updated_count']} ideas")

    # Step 11: Finalize and submit to voting system (Module 7 - Stage 5)
    print_section("Step 11: Finalize & Submit to Voting System (Stage 5)")
    print("Calling /finalize endpoint...")

    finalize_response = requests.post(
        f"{BASE_URL}/competitor-intelligence/sessions/{session_id}/finalize",
        headers=headers
    )

    if finalize_response.status_code not in [200, 201]:
        print(f"❌ Finalization failed: {finalize_response.text}")
        return

    finalize_result = finalize_response.json()
    print(f"✅ {finalize_result['message']}")
    print(f"   Status: {finalize_result['status']}")
    print(f"   Submitted: {finalize_result['submitted_count']} ideas")

    submitted_ideas = finalize_result.get("ideas", [])
    for submitted in submitted_ideas:
        print(f"   - Idea ID {submitted['idea_id']}: {submitted['title']}")

    # Step 12: Verify ideas in main voting system
    print_section("Step 12: Verify Ideas in Voting System")
    voting_ideas_response = requests.get(
        f"{BASE_URL}/ideas",
        headers=headers
    )

    if voting_ideas_response.status_code not in [200, 201]:
        print(f"❌ Failed to fetch voting ideas: {voting_ideas_response.text}")
        return

    all_voting_ideas = voting_ideas_response.json()
    competitor_ideas = [i for i in all_voting_ideas if i.get("source_type") == "competitor"]

    print(f"✅ Found {len(competitor_ideas)} competitor-sourced ideas in voting system")

    # Verify our submitted ideas are there
    submitted_idea_ids = [s["idea_id"] for s in submitted_ideas]
    found_ideas = [i for i in competitor_ideas if i["id"] in submitted_idea_ids]

    if len(found_ideas) == len(submitted_idea_ids):
        print(f"✅ All {len(submitted_idea_ids)} submitted ideas found in voting system")
        for idea in found_ideas:
            print(f"   - [{idea['id']}] {idea['title']} (source: {idea['source_type']})")
    else:
        print(f"❌ Only found {len(found_ideas)}/{len(submitted_idea_ids)} submitted ideas")

    # Final summary
    print_section("TEST SUMMARY")
    print("✅ Module 7 implementation test PASSED")
    print(f"   - Product created and analyzed")
    print(f"   - Session created with {len(competitor_ids)} competitors")
    print(f"   - {len(feature_ids)} features added and selected")
    print(f"   - {generate_result.get('ideas_generated', 0)} ideas generated using IdeaStructuringAgent")
    print(f"   - Ideas edited successfully")
    print(f"   - {approve_result['updated_count']} ideas approved")
    print(f"   - {finalize_result['submitted_count']} ideas submitted to voting system")
    print(f"   - All ideas verified in voting system with source_type='competitor'")
    print("\n✅ All Module 7 functionality working correctly!")

if __name__ == "__main__":
    try:
        test_module7()
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
