"""
Test script for detailed product features extraction.

Tests the complete flow:
1. Create product
2. Analyze product (extracts both core and detailed features)
3. Retrieve detailed features via API
"""

import requests
import json

BASE_URL = "http://localhost:8000"

# Test credentials
ADMIN_CREDENTIALS = {
    "username": "admin",
    "password": "password"
}

def get_auth_token():
    """Get authentication token."""
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data=ADMIN_CREDENTIALS
    )
    response.raise_for_status()
    return response.json()["access_token"]

def test_detailed_features_extraction():
    """Test the complete detailed features flow."""

    # Get auth token
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    print("\n" + "="*80)
    print("TEST: Detailed Product Features Extraction")
    print("="*80)

    # Step 1: Create product
    print("\n[1/4] Creating product...")
    import time
    product_data = {
        "product_name": f"Test CRM System {int(time.time())}",
        "product_description": """
        Our CRM system is designed for small to medium businesses.

        Core capabilities include:
        - Contact management with custom fields
        - Sales pipeline tracking with drag-and-drop interface
        - Email integration with Gmail and Outlook
        - Automated follow-up reminders
        - Activity logging and timeline
        - Reporting and analytics dashboard
        - Mobile apps for iOS and Android
        - Team collaboration features
        - Task management
        - Calendar integration
        - Document storage
        - Custom workflows
        - API access for integrations
        - Role-based permissions
        - Data import/export
        """,
        "source_type": "text"
    }

    response = requests.post(
        f"{BASE_URL}/product-intelligence/products",
        headers=headers,
        json=product_data
    )
    response.raise_for_status()
    product = response.json()
    product_id = product["id"]
    print(f"✓ Created product: {product['product_name']} (ID: {product_id})")

    # Step 2: Analyze product
    print("\n[2/4] Analyzing product (extracting core + detailed features)...")
    analyze_data = {
        "product_description": product_data["product_description"],
        "source_type": "text"
    }

    response = requests.post(
        f"{BASE_URL}/product-intelligence/products/{product_id}/analyze",
        headers=headers,
        json=analyze_data
    )
    response.raise_for_status()
    analysis_response = response.json()

    # The analysis is returned in the analyzed_structure field
    analysis_result = analysis_response.get('analyzed_structure', {})

    print(f"✓ Analysis complete")
    print(f"\n  Product Name: {analysis_result.get('product_name', 'N/A')}")
    print(f"  Category: {analysis_result.get('product_category', 'N/A')}")

    print(f"\n  Core Features ({len(analysis_result.get('core_features', []))}):")
    for i, feature in enumerate(analysis_result.get('core_features', []), 1):
        print(f"    {i}. {feature}")

    detailed_features = analysis_result.get('detailed_features', [])
    print(f"\n  Detailed Features ({len(detailed_features)}):")
    for i, feature in enumerate(detailed_features[:5], 1):  # Show first 5
        print(f"    {i}. {feature['name']} ({feature['category']})")
        print(f"       {feature['description'][:80]}...")
    if len(detailed_features) > 5:
        print(f"    ... and {len(detailed_features) - 5} more")

    # Step 3: Retrieve detailed features via API
    print("\n[3/4] Retrieving detailed features from database...")
    response = requests.get(
        f"{BASE_URL}/product-intelligence/products/{product_id}/detailed-features",
        headers=headers
    )
    response.raise_for_status()
    stored_features = response.json()

    print(f"✓ Retrieved {len(stored_features)} detailed features from database")

    # Group by category
    by_category = {}
    for feature in stored_features:
        category = feature['feature_category']
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(feature)

    print(f"\n  Features by Category:")
    for category, features in sorted(by_category.items()):
        print(f"    {category}: {len(features)} features")

    # Step 4: Validate results
    print("\n[4/4] Validating results...")

    # Check that we got detailed features
    if len(stored_features) == 0:
        print("❌ No detailed features stored!")
        return False

    # Check that detailed features have required fields
    sample_feature = stored_features[0]
    required_fields = ['feature_name', 'feature_description', 'feature_category', 'extraction_confidence']
    missing_fields = [f for f in required_fields if f not in sample_feature or sample_feature[f] is None]

    if missing_fields:
        print(f"❌ Sample feature missing fields: {missing_fields}")
        return False

    # Check that we have a reasonable number of features
    if len(stored_features) < 5:
        print(f"⚠ Only {len(stored_features)} features extracted (expected 10-25)")
    elif len(stored_features) > 30:
        print(f"⚠ Too many features extracted: {len(stored_features)} (expected 10-25)")
    else:
        print(f"✓ Good number of features: {len(stored_features)}")

    # Check categorization
    if len(by_category) < 2:
        print(f"⚠ Features not well categorized (only {len(by_category)} categories)")
    else:
        print(f"✓ Features well categorized ({len(by_category)} categories)")

    print("\n" + "="*80)
    print("✓ TEST PASSED: Detailed features extraction working correctly")
    print("="*80)

    print("\n📊 Summary:")
    print(f"  - Core features: {len(analysis_result.get('core_features', []))}")
    print(f"  - Detailed features: {len(stored_features)}")
    print(f"  - Categories: {len(by_category)}")
    print(f"  - Product ID: {product_id}")

    return True

if __name__ == "__main__":
    try:
        success = test_detailed_features_extraction()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
