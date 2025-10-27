#!/usr/bin/env python3
"""
Database reset utility.

This script helps you reset the database to a clean state.
Useful for development and testing.

Usage:
    python reset_db.py              # Interactive mode (asks for confirmation)
    python reset_db.py --force      # Non-interactive mode (no confirmation)
"""

import os
import sys
import argparse


def reset_database(force=False):
    """Reset the database by deleting the SQLite file."""

    db_file = "feature_voting.db"

    if not os.path.exists(db_file):
        print(f"✓ Database file '{db_file}' does not exist. Nothing to reset.")
        return

    if not force:
        print(f"⚠️  WARNING: This will permanently delete the database file!")
        print(f"   File: {db_file}")
        print(f"   Size: {os.path.getsize(db_file)} bytes")
        print()
        response = input("Are you sure you want to continue? (yes/no): ")

        if response.lower() not in ['yes', 'y']:
            print("❌ Database reset cancelled.")
            return

    try:
        os.remove(db_file)
        print(f"✓ Database file deleted: {db_file}")
        print()
        print("Next steps:")
        print("1. Start the server: uvicorn app.main:app --reload")
        print("2. The database will be recreated automatically")
        print("3. The bootstrap admin user will be created from .env settings")
    except Exception as e:
        print(f"❌ Error deleting database: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Reset the database to a clean state",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python reset_db.py              # Interactive mode (asks for confirmation)
  python reset_db.py --force      # Skip confirmation prompt
  python reset_db.py -f           # Short form of --force
        """
    )

    parser.add_argument(
        '-f', '--force',
        action='store_true',
        help='Skip confirmation prompt'
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Database Reset Utility")
    print("=" * 60)
    print()

    reset_database(force=args.force)


if __name__ == "__main__":
    main()
