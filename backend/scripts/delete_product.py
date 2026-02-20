#!/usr/bin/env python3
"""
Delete a product and all associated data.

Usage:
    python scripts/delete_product.py <product_id> [--dry-run] [--yes]

Examples:
    # Preview what would be deleted
    python scripts/delete_product.py 2 --dry-run

    # Delete with confirmation prompt
    python scripts/delete_product.py 2

    # Delete without confirmation
    python scripts/delete_product.py 2 --yes
"""

import argparse
import json
import sys
from pathlib import Path

# Add backend to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.services.product_service import ProductService
from app.services.permission_service import PermissionService
from app.models.competitor_intelligence import CIProduct


def main():
    parser = argparse.ArgumentParser(description="Delete a product and all associated data")
    parser.add_argument("product_id", type=int, help="ID of the product to delete")
    parser.add_argument("--dry-run", action="store_true", help="Preview deletion without making changes")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        service = ProductService(db)

        # Always show preview first
        preview = service.get_delete_preview(args.product_id)
        if preview is None:
            print(f"Product {args.product_id} not found.")
            sys.exit(1)

        print(f"\nProduct: {preview['product']['name']} (id={preview['product']['id']})")
        print(f"Status: {preview['product']['status']}")
        print(f"Created: {preview['product']['created_at']}")

        print("\nRows to delete:")
        for table, count in preview["will_delete"].items():
            if count > 0:
                print(f"  {table}: {count}")

        preserved = {k: v for k, v in preview["will_preserve_with_null_product_id"].items() if v > 0}
        if preserved:
            print("\nRows preserved (product_id set to NULL):")
            for table, count in preserved.items():
                print(f"  {table}: {count}")

        embeddings = {k: v for k, v in preview["embeddings"].items() if v > 0}
        if embeddings:
            print("\nEmbeddings to delete:")
            for name, count in embeddings.items():
                print(f"  {name}: {count}")

        if preview["files"]["directory_exists"]:
            print(f"\nReport files: {preview['files'].get('report_runs', '?')} analysis runs")
            print(f"  Directory: {preview['files']['reports_directory']}")

        if args.dry_run:
            print("\n[DRY RUN] No changes made.")
            sys.exit(0)

        # Confirm deletion
        if not args.yes:
            response = input(f"\nDelete product '{preview['product']['name']}' and all associated data? [y/N] ")
            if response.lower() != "y":
                print("Cancelled.")
                sys.exit(0)

        # Find an admin user to perform the deletion (script bypasses auth)
        from app.models.user import User, UserRole
        admin = db.query(User).filter(User.role == UserRole.ADMIN, User.is_active == True).first()
        if not admin:
            print("No active admin user found. Cannot perform deletion.")
            sys.exit(1)

        result = service.delete_product(args.product_id, admin.id)
        if result:
            print(f"\nProduct '{preview['product']['name']}' deleted successfully.")
        else:
            print("\nDeletion failed.")
            sys.exit(1)

    finally:
        db.close()


if __name__ == "__main__":
    main()
