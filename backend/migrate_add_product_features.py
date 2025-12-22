"""
Migration script to add product_features table for storing detailed product features.

This migration adds:
- product_features table to store detailed features (10-25) from product analysis
- Relationship to ProductAnalysisHistory

Run this script to update the database schema.
"""

import sys
import os

# Add the backend directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from app.config import settings
from app.models.competitor_intelligence import Base, ProductFeature

def run_migration():
    """Run the migration to add product_features table."""
    print("Starting migration: Adding product_features table...")

    # Create engine
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False}
    )

    # Create the table
    print("Creating product_features table...")
    Base.metadata.tables['product_features'].create(engine, checkfirst=True)

    print("✓ Migration completed successfully!")
    print("\nNew table created:")
    print("  - product_features: Stores detailed features from product analysis")

if __name__ == "__main__":
    try:
        run_migration()
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)
