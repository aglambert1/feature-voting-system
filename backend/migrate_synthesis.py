#!/usr/bin/env python3
"""
Migration script for Opportunity Synthesis feature.

This migration creates new tables:
1. synthesis_runs - Tracks synthesis runs combining multiple sources
2. synthesized_opportunities - Opportunities identified from cross-source analysis

Usage:
    cd backend
    python migrate_synthesis.py
"""

import os
import sys

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.database import engine, SessionLocal


def check_table_exists(db, table_name: str) -> bool:
    """Check if a table exists in the database."""
    result = db.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=:name"
    ), {"name": table_name})
    return result.fetchone() is not None


def run_migration():
    """Run all migration steps."""
    db = SessionLocal()

    try:
        print("=" * 60)
        print("Opportunity Synthesis Migration")
        print("=" * 60)
        print()

        # === Create synthesis_runs table ===
        print("Creating synthesis tables...")

        if not check_table_exists(db, "synthesis_runs"):
            db.execute(text("""
                CREATE TABLE synthesis_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL REFERENCES ci_products(id) ON DELETE CASCADE,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    error_message TEXT,
                    source_snapshot JSON,
                    sources_used JSON,
                    summary_stats JSON,
                    analysis_summary TEXT,
                    job_uuid VARCHAR(36),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    completed_at DATETIME
                )
            """))
            db.execute(text("CREATE INDEX ix_synthesis_runs_product_id ON synthesis_runs(product_id)"))
            db.execute(text("CREATE INDEX ix_synthesis_runs_job_uuid ON synthesis_runs(job_uuid)"))
            print("  + Created synthesis_runs table")
        else:
            print("  - synthesis_runs already exists")

        # === Create synthesized_opportunities table ===
        if not check_table_exists(db, "synthesized_opportunities"):
            db.execute(text("""
                CREATE TABLE synthesized_opportunities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    synthesis_run_id INTEGER NOT NULL REFERENCES synthesis_runs(id) ON DELETE CASCADE,
                    product_id INTEGER NOT NULL REFERENCES ci_products(id) ON DELETE CASCADE,
                    opportunity_name VARCHAR(255) NOT NULL,
                    opportunity_summary TEXT,
                    priority_score REAL NOT NULL DEFAULT 0.0,
                    source_count INTEGER NOT NULL DEFAULT 1,
                    sources JSON,
                    competitive_evidence JSON,
                    customer_evidence JSON,
                    internal_evidence JSON,
                    recommended_action VARCHAR(100),
                    feature_keywords JSON,
                    embedding JSON,
                    linked_idea_id INTEGER REFERENCES ideas(id) ON DELETE SET NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            db.execute(text("CREATE INDEX ix_synthesized_opportunities_run_id ON synthesized_opportunities(synthesis_run_id)"))
            db.execute(text("CREATE INDEX ix_synthesized_opportunities_product_id ON synthesized_opportunities(product_id)"))
            db.execute(text("CREATE INDEX ix_synthesized_opportunities_linked_idea_id ON synthesized_opportunities(linked_idea_id)"))
            print("  + Created synthesized_opportunities table")
        else:
            print("  - synthesized_opportunities already exists")

        db.commit()

        print()
        print("=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)
        print()
        print("New tables created:")
        print("  - synthesis_runs")
        print("  - synthesized_opportunities")

    except Exception as e:
        print(f"\nError during migration: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    run_migration()
