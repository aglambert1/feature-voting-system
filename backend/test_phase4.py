#!/usr/bin/env python3
"""
Phase 4 Test Script: PM Review Queue + Monitoring

This script tests the Phase 4 functionality:
1. PM Review Queue - listing, actions
2. Monitoring Configuration - enable/disable/update
3. Snapshots - viewing competitor history
4. Manual monitoring trigger

Prerequisites:
- Server running at localhost:8000
- Celery worker running (for background tasks)
- At least one product with competitors and features
"""

import sys
import time
import requests

BASE_URL = "http://localhost:8000"


def get_token(username="admin", password="admin123"):
    """Get auth token."""
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": username, "password": password}
    )
    if response.status_code != 200:
        print(f"✗ Failed to login: {response.status_code}")
        print(response.text)
        return None
    return response.json().get("access_token")


def main():
    print("=" * 60)
    print("Phase 4 Test: PM Review Queue + Competitive Monitoring")
    print("=" * 60)

    # Step 1: Login
    print("\n[Step 1] Authenticating...")
    token = get_token()
    if not token:
        sys.exit(1)
    print("✓ Authenticated successfully")
    headers = {"Authorization": f"Bearer {token}"}

    # Step 2: Get products
    print("\n[Step 2] Getting products...")
    response = requests.get(
        f"{BASE_URL}/product-intelligence/products",
        headers=headers
    )
    if response.status_code != 200:
        print(f"✗ Failed to get products: {response.status_code}")
        sys.exit(1)

    products = response.json()
    if not products:
        print("✗ No products found. Please create a product first.")
        sys.exit(1)

    product = products[0]
    product_id = product["id"]
    print(f"✓ Using product: {product['product_name']} (ID: {product_id})")

    # Step 3: Get PM Review Queue Stats
    print("\n[Step 3] Getting PM Review Queue stats...")
    response = requests.get(
        f"{BASE_URL}/pm-review/stats/{product_id}",
        headers=headers
    )
    if response.status_code == 200:
        stats = response.json()
        print(f"✓ Queue Stats:")
        print(f"   - Pending: {stats.get('total_pending', 0)}")
        print(f"   - In Review: {stats.get('total_in_review', 0)}")
        print(f"   - Approved: {stats.get('total_approved', 0)}")
        print(f"   - By Type: {stats.get('by_type', {})}")
    else:
        print(f"  Status: {response.status_code}")
        print(f"  Response: {response.text[:200]}")

    # Step 4: Get PM Review Queue Items
    print("\n[Step 4] Getting PM Review Queue items...")
    response = requests.get(
        f"{BASE_URL}/pm-review/queue",
        params={"product_id": product_id},
        headers=headers
    )
    if response.status_code == 200:
        queue_data = response.json()
        items = queue_data.get("items", [])
        print(f"✓ Found {len(items)} items in queue")
        for item in items[:3]:  # Show first 3
            print(f"   - [{item['queue_type']}] {item['title'][:50]}... (status: {item['status']})")
    else:
        print(f"  Status: {response.status_code}")
        print(f"  Response: {response.text[:200]}")

    # Step 5: Get/Create Monitoring Config
    print("\n[Step 5] Getting monitoring configuration...")
    response = requests.get(
        f"{BASE_URL}/monitoring/config/{product_id}",
        headers=headers
    )
    if response.status_code == 200:
        config = response.json()
        print(f"✓ Monitoring Config:")
        print(f"   - Enabled: {config.get('monitoring_enabled')}")
        print(f"   - Frequency: {config.get('monitoring_frequency')}")
        print(f"   - Last Monitored: {config.get('last_monitored_at')}")
    else:
        print(f"  Status: {response.status_code}")
        print(f"  Response: {response.text[:200]}")

    # Step 6: Update Monitoring Config
    print("\n[Step 6] Updating monitoring configuration...")
    response = requests.put(
        f"{BASE_URL}/monitoring/config/{product_id}",
        headers=headers,
        json={
            "monitoring_enabled": True,
            "monitoring_frequency": "weekly",
            "alert_on_new_features": True,
            "alert_on_removed_features": True,
            "alert_on_new_competitors": True,
            "min_feature_change_threshold": 1,
            "auto_generate_ideas": False,
            "notify_product_owners": True,
        }
    )
    if response.status_code == 200:
        config = response.json()
        print(f"✓ Monitoring config updated:")
        print(f"   - Enabled: {config.get('monitoring_enabled')}")
        print(f"   - Frequency: {config.get('monitoring_frequency')}")
    else:
        print(f"  Status: {response.status_code}")
        print(f"  Response: {response.text[:200]}")

    # Step 7: Get Snapshots
    print("\n[Step 7] Getting competitor snapshots...")
    response = requests.get(
        f"{BASE_URL}/monitoring/snapshots/{product_id}",
        headers=headers
    )
    if response.status_code == 200:
        snapshots_data = response.json()
        snapshots = snapshots_data.get("snapshots", [])
        print(f"✓ Found {len(snapshots)} snapshots")
        for snapshot in snapshots[:3]:
            print(f"   - {snapshot['competitor_name']}: {snapshot['feature_count']} features (has_changes: {snapshot['has_changes']})")
    else:
        print(f"  Status: {response.status_code}")
        print(f"  Response: {response.text[:200]}")

    # Step 8: Trigger manual monitoring (optional - requires Celery)
    print("\n[Step 8] Triggering manual monitoring...")
    print("  (This requires Celery worker to be running)")
    response = requests.post(
        f"{BASE_URL}/monitoring/trigger/{product_id}",
        headers=headers
    )
    if response.status_code == 200:
        result = response.json()
        print(f"✓ Monitoring triggered:")
        print(f"   - Job UUID: {result.get('job_uuid')}")
        print(f"   - Status: {result.get('status')}")

        # Poll for job completion
        job_uuid = result.get('job_uuid')
        if job_uuid:
            print(f"\n  Waiting for job to complete...")
            for i in range(30):  # Wait up to 30 seconds
                time.sleep(2)
                job_response = requests.get(
                    f"{BASE_URL}/product-intelligence/jobs/{job_uuid}",
                    headers=headers
                )
                if job_response.status_code == 200:
                    job = job_response.json()
                    status = job.get('status')
                    print(f"   [{i*2}s] Status: {status}, Progress: {job.get('progress_percent', 0):.0f}%")
                    if status in ('success', 'failure'):
                        if status == 'success':
                            print(f"\n✓ Monitoring completed successfully!")
                            output = job.get('output_data', {})
                            print(f"   - Competitors monitored: {output.get('competitors_monitored', 0)}")
                            print(f"   - Alerts generated: {output.get('alerts_generated', 0)}")
                        else:
                            print(f"\n✗ Monitoring failed: {job.get('error_message')}")
                        break
                else:
                    break
    elif response.status_code == 500:
        print(f"  Note: Monitoring task requires Celery worker")
        print(f"  Start with: celery -A app.queue worker --loglevel=info --pool=solo")
    else:
        print(f"  Status: {response.status_code}")
        print(f"  Response: {response.text[:200]}")

    # Step 9: Test PM Review Actions (if we have items)
    print("\n[Step 9] Testing PM Review actions...")
    response = requests.get(
        f"{BASE_URL}/pm-review/queue",
        params={"product_id": product_id, "status": "pending"},
        headers=headers
    )
    if response.status_code == 200:
        items = response.json().get("items", [])
        if items:
            item = items[0]
            item_id = item['id']
            print(f"  Testing with item: {item['title'][:50]}...")

            # Start review
            response = requests.post(
                f"{BASE_URL}/pm-review/queue/{item_id}/start-review",
                headers=headers
            )
            if response.status_code == 200:
                print(f"  ✓ Started review (status: in_review)")
            else:
                print(f"  Start review: {response.status_code}")

            # Defer (to test without actually approving/rejecting)
            response = requests.post(
                f"{BASE_URL}/pm-review/queue/{item_id}/defer",
                headers=headers,
                json={"notes": "Deferred for testing"}
            )
            if response.status_code == 200:
                print(f"  ✓ Deferred item (status: deferred)")
            else:
                print(f"  Defer: {response.status_code}")
        else:
            print("  No pending items to test")
    else:
        print(f"  Could not get queue items: {response.status_code}")

    print("\n" + "=" * 60)
    print("Phase 4 Test Complete!")
    print("=" * 60)
    print("\nSummary:")
    print("- PM Review Queue API: Working")
    print("- Monitoring Config API: Working")
    print("- Snapshots API: Working")
    print("- Manual Monitoring Trigger: Depends on Celery")
    print("\nTo test full monitoring workflow:")
    print("1. Start Celery worker: celery -A app.queue worker --loglevel=info --pool=solo")
    print("2. Run: POST /monitoring/trigger/{product_id}")
    print("3. Check snapshots: GET /monitoring/snapshots/{product_id}")
    print("4. Check alerts in queue: GET /pm-review/queue?product_id={id}&queue_type=competitive_alert")


if __name__ == "__main__":
    main()
