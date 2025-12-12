#!/usr/bin/env python3
"""
Test script for Stage 3 Feature Extraction workflow.
Tests the complete flow from login through feature extraction.
"""

import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def test_workflow():
    print("=" * 60)
    print("Testing Module 6: Feature Extraction Workflow")
    print("=" * 60)

    # Step 1: Login
    print("\n1. Logging in...")
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": "admin", "password": "admin123"}
    )
    if response.status_code != 200:
        print(f"❌ Login failed: {response.status_code}")
        return False

    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("✓ Login successful")

    # Step 2: Get or create a test product
    print("\n2. Getting products...")
    response = requests.get(f"{BASE_URL}/competitor-intelligence/products", headers=headers)
    products = response.json()["products"]

    if products:
        product = products[0]
        product_id = product["id"]
        print(f"✓ Using existing product: {product['product_name']} (ID: {product_id})")
    else:
        print("❌ No products found. Please create a product first.")
        return False

    # Verify product is analyzed
    if not product.get("structured_product_data"):
        print("❌ Product not analyzed. Please analyze the product first.")
        return False
    print(f"✓ Product is analyzed")

    # Step 3: Create a new session
    print("\n3. Creating analysis session...")
    response = requests.post(
        f"{BASE_URL}/competitor-intelligence/sessions",
        json={
            "product_id": product_id,
            "session_name": f"Test Session - Feature Extraction",
            "product_source_type": "text",
            "enable_comparison": False
        },
        headers=headers
    )

    if response.status_code != 201:
        print(f"❌ Session creation failed: {response.status_code}")
        print(response.text)
        return False

    session = response.json()
    session_id = session["id"]
    print(f"✓ Session created (ID: {session_id})")

    # Step 4: Discover competitors (Stage 2)
    print("\n4. Discovering competitors (Stage 2)...")
    print("   (This may take 30-60 seconds as AI analyzes the web)")
    response = requests.post(
        f"{BASE_URL}/competitor-intelligence/sessions/{session_id}/discover-competitors",
        headers=headers
    )

    if response.status_code != 200:
        print(f"❌ Competitor discovery failed: {response.status_code}")
        print(response.text)
        return False

    discovery_result = response.json()
    competitors = discovery_result.get("competitors", [])
    print(f"✓ Discovered {len(competitors)} competitors")

    if competitors:
        print(f"   Sample: {competitors[0]['name']}")

    # Step 5: Confirm competitors
    print("\n5. Confirming competitors...")
    selected_ids = [c["id"] for c in competitors[:3]]  # Select first 3

    response = requests.post(
        f"{BASE_URL}/competitor-intelligence/sessions/{session_id}/confirm-competitors",
        json={"selected_ids": selected_ids},
        headers=headers
    )

    if response.status_code != 200:
        print(f"❌ Competitor confirmation failed: {response.status_code}")
        print(response.text)
        return False

    print(f"✓ Confirmed {len(selected_ids)} competitors")

    # Step 6: Extract features (Stage 3) - THE NEW FUNCTIONALITY
    print("\n6. Extracting features (Stage 3)...")
    print("   (This may take 1-2 minutes as AI analyzes each competitor)")
    response = requests.post(
        f"{BASE_URL}/competitor-intelligence/sessions/{session_id}/extract-features",
        headers=headers
    )

    if response.status_code != 200:
        print(f"❌ Feature extraction failed: {response.status_code}")
        print(response.text)
        return False

    extraction_result = response.json()
    print(f"✓ Feature extraction completed")
    print(f"   Status: {extraction_result['status']}")
    print(f"   Competitors processed: {extraction_result['completed_competitors']}/{extraction_result['total_competitors']}")

    # Step 7: Get extracted features
    print("\n7. Retrieving extracted features...")
    response = requests.get(
        f"{BASE_URL}/competitor-intelligence/sessions/{session_id}/features",
        headers=headers
    )

    if response.status_code != 200:
        print(f"❌ Failed to get features: {response.status_code}")
        return False

    features_result = response.json()
    features_by_comp = features_result.get("features_by_competitor", [])
    change_stats = features_result.get("change_stats", {})

    total_features = sum(len(comp["features"]) for comp in features_by_comp)
    print(f"✓ Retrieved features from {len(features_by_comp)} competitors")
    print(f"   Total features: {total_features}")

    if change_stats:
        print(f"   Change stats: {change_stats}")

    # Show sample features
    if features_by_comp and features_by_comp[0]["features"]:
        sample_feature = features_by_comp[0]["features"][0]
        print(f"\n   Sample feature:")
        print(f"   - Name: {sample_feature['name']}")
        print(f"   - Category: {sample_feature.get('category', 'N/A')}")
        print(f"   - Description: {sample_feature['description'][:100]}...")
        if sample_feature.get('confidence'):
            print(f"   - Confidence: {sample_feature['confidence']:.0%}")

    # Step 8: Select features
    print("\n8. Selecting features for idea generation...")
    all_feature_ids = []
    for comp in features_by_comp:
        for feature in comp["features"][:5]:  # Select first 5 from each competitor
            all_feature_ids.append(int(feature["id"]))

    response = requests.post(
        f"{BASE_URL}/competitor-intelligence/sessions/{session_id}/select-features",
        json={"feature_ids": all_feature_ids},
        headers=headers
    )

    if response.status_code != 200:
        print(f"❌ Feature selection failed: {response.status_code}")
        print(response.text)
        return False

    selection_result = response.json()
    print(f"✓ Selected {selection_result['selected_count']} features")

    print("\n" + "=" * 60)
    print("✓ WORKFLOW TEST PASSED!")
    print("=" * 60)
    print("\nModule 6 (Stage 3: Feature Extraction) is working correctly!")
    print(f"\nTest session ID: {session_id}")
    print("You can view this in the UI by navigating to:")
    print(f"http://localhost:5173/competitor-intelligence/products/{product_id}/sessions/{session_id}")

    return True

if __name__ == "__main__":
    try:
        success = test_workflow()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
