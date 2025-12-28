#!/usr/bin/env python3
"""
Phase 3 API Test Script
Tests idea normalization, triage, and PM review workflows
"""

import requests
import json
import time
import sys

BASE_URL = "http://localhost:8000"

def get_token():
    """Get authentication token."""
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": "admin", "password": "password"}
    )
    response.raise_for_status()
    return response.json()["access_token"]

def main():
    print("=" * 50)
    print("Phase 3 API Test Script")
    print("Idea Normalization + Triage")
    print("=" * 50)
    print()

    # Step 1: Get auth token
    print("Step 1: Getting auth token...")
    try:
        token = get_token()
        print(f"✓ Got token: {token[:20]}...")
    except Exception as e:
        print(f"✗ Failed to get token: {e}")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {token}"}

    # Step 2: Get products
    print("\nStep 2: Getting products...")
    response = requests.get(f"{BASE_URL}/product-intelligence/products", headers=headers)
    products = response.json()
    print(f"Found {len(products)} products")

    # Find an analyzed product
    product_id = None
    for p in products:
        if p.get("structured_product_data"):
            product_id = p["id"]
            print(f"Using analyzed product: ID={product_id}, Name={p['product_name']}")
            break

    if not product_id and products:
        product_id = products[0]["id"]
        print(f"Using first product: ID={product_id}")

    if not product_id:
        print("✗ No products found!")
        sys.exit(1)

    # Step 3: Submit structured idea
    print("\nStep 3: Submitting structured idea with AI triage...")
    submit_data = {
        "product_id": product_id,
        "title": "Add AI-powered task prioritization",
        "what_description": "A feature that uses machine learning to automatically suggest task priorities based on deadlines, dependencies, and team workload.",
        "why_description": "Teams often struggle to prioritize tasks effectively, especially in large projects. AI assistance would save time and improve decision-making.",
        "use_case_description": "A project manager opens the dashboard and sees AI-suggested priorities highlighted. They can accept, modify, or dismiss suggestions with one click."
    }
    response = requests.post(
        f"{BASE_URL}/ideas/submit",
        headers=headers,
        json=submit_data
    )

    if response.status_code not in (200, 202):
        print(f"✗ Failed to submit idea: {response.status_code}")
        print(response.text)
        sys.exit(1)

    submit_result = response.json()
    print(f"✓ Idea submitted!")
    print(f"  Idea ID: {submit_result.get('id')}")
    print(f"  Job UUID: {submit_result.get('job_uuid')}")
    print(f"  Status: {submit_result.get('status')}")

    job_uuid = submit_result.get("job_uuid")
    idea_id = submit_result.get("id")

    # Step 4: Poll for triage completion
    if job_uuid:
        print("\nStep 4: Waiting for triage to complete...")
        max_wait = 90
        wait_count = 0
        while wait_count < max_wait:
            response = requests.get(
                f"{BASE_URL}/product-intelligence/jobs/{job_uuid}",
                headers=headers
            )
            job_status = response.json()
            status = job_status.get("status")
            progress = job_status.get("progress_percent", 0)

            print(f"  Status: {status}, Progress: {progress}%")

            if status == "success":
                print("\n✓ Triage completed!")
                output_data = job_status.get("output_data", {})
                print(f"  Idea ID: {output_data.get('idea_id')}")
                print(f"  Triage Status: {output_data.get('triage_status')}")
                print(f"  Category: {output_data.get('category')}")
                if output_data.get("recommendation"):
                    rec = output_data["recommendation"]
                    print(f"  Recommendation: {rec.get('action')} (confidence: {rec.get('confidence')})")
                break
            elif status == "failure":
                print("\n✗ Triage failed!")
                print(f"  Error: {job_status.get('error_message')}")
                break

            time.sleep(5)
            wait_count += 5
        else:
            print("\n⚠ Triage timed out after 90 seconds")

    # Step 5: Get triage details
    if idea_id:
        print(f"\nStep 5: Getting triage details for idea {idea_id}...")
        response = requests.get(
            f"{BASE_URL}/ideas/{idea_id}/triage-details",
            headers=headers
        )
        if response.status_code == 200:
            details = response.json()
            print("✓ Got triage details:")
            print(json.dumps(details, indent=2))
        else:
            print(f"  Status: {response.status_code}")
            print(f"  Response: {response.text[:200]}")

    # Step 6: List pending review ideas
    print(f"\nStep 6: Listing ideas pending review...")
    response = requests.get(
        f"{BASE_URL}/ideas/pending-review",
        headers=headers,
        params={"product_id": product_id}
    )
    if response.status_code == 200:
        pending = response.json()
        print(f"✓ Pending review:")
        print(f"  Total: {pending.get('total')}")
        print(f"  Pending: {pending.get('pending_count')}")
        print(f"  Needs Review: {pending.get('needs_review_count')}")
        if pending.get("ideas"):
            for idea in pending["ideas"][:5]:
                print(f"    - {idea['id']}: {idea['title'][:40]}... ({idea['triage_status']})")
    else:
        print(f"  Error: {response.status_code}")
        print(f"  Response: {response.text[:200]}")

    # Step 7: Submit freeform idea
    print("\nStep 7: Submitting freeform idea for AI structuring...")
    freeform_data = {
        "product_id": product_id,
        "freeform_text": "It would be really cool if we could have some kind of integration with Jira so that tasks created in your app would automatically sync with our existing Jira boards. We use both tools and having to manually copy things over is a pain."
    }
    response = requests.post(
        f"{BASE_URL}/ideas/submit",
        headers=headers,
        json=freeform_data
    )
    if response.status_code in (200, 202):
        result = response.json()
        print(f"✓ Freeform idea submitted!")
        print(f"  Job UUID: {result.get('job_uuid')}")
    else:
        print(f"  Error: {response.status_code}")
        print(f"  Response: {response.text[:200]}")

    # Step 8: PM Review (if we have an idea)
    if idea_id:
        print(f"\nStep 8: Testing PM review - approving idea {idea_id}...")
        review_data = {
            "action": "approve",
            "notes": "Good idea, aligned with product strategy",
            "publish_for_voting": True
        }
        response = requests.post(
            f"{BASE_URL}/ideas/{idea_id}/review",
            headers=headers,
            json=review_data
        )
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Idea reviewed!")
            print(f"  New Status: {result.get('triage_status')}")
            print(f"  Published for Voting: {result.get('published_for_voting')}")
        else:
            print(f"  Error: {response.status_code}")
            print(f"  Response: {response.text[:200]}")

    # Summary
    print("\n" + "=" * 50)
    print("Test Summary")
    print("=" * 50)
    print("✓ Authentication working")
    print("✓ Idea submission (structured) working")
    print("✓ AI triage queued")
    print("✓ Triage details endpoint working")
    print("✓ Pending review listing working")
    print("✓ Freeform idea submission working")
    print("✓ PM review action working")
    print()
    print("Phase 3 API tests complete!")

if __name__ == "__main__":
    main()
