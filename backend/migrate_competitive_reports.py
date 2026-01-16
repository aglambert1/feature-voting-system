#!/usr/bin/env python3
"""
Migration script for Competitive Reports feature.

This migration:
1. Creates new tables:
   - competitor_functional_reports
   - landscape_opportunity_reports
2. Removes deprecated columns from competitive_agent_configs:
   - enable_pricing_analysis
   - enable_positioning_analysis
   - enable_changes_tracking
   - enable_momentum_analysis
   - enable_financials_analysis
3. Drops deprecated tables (data will be lost):
   - competitor_pricing_analysis
   - competitor_positioning_analysis
   - competitor_change_events
   - competitor_momentum_analysis
   - competitor_financials_analysis

WARNING: This migration will DELETE existing strategic analysis data.
The database can be reinitialized if needed.

Usage:
    cd backend
    python migrate_competitive_reports.py
"""

import os
import sys

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.database import engine, SessionLocal


def check_column_exists(db, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    result = db.execute(text(f"PRAGMA table_info({table_name})"))
    columns = [row[1] for row in result.fetchall()]
    return column_name in columns


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
        print("Competitive Reports Migration")
        print("=" * 60)
        print()

        # === Create new tables ===
        print("Creating new tables...")

        if not check_table_exists(db, "competitor_functional_reports"):
            db.execute(text("""
                CREATE TABLE competitor_functional_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_competitor_id INTEGER NOT NULL REFERENCES product_competitors(id) ON DELETE CASCADE,
                    product_id INTEGER NOT NULL REFERENCES ci_products(id) ON DELETE CASCADE,
                    report_version INTEGER NOT NULL DEFAULT 1,
                    report_content_md TEXT,
                    competitor_context JSON,
                    functional_comparison JSON,
                    gaps_deep_dive JSON,
                    technical_constraints JSON,
                    raw_search_results JSON,
                    generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    queue_job_id INTEGER REFERENCES queue_jobs(id)
                )
            """))
            db.execute(text("CREATE INDEX ix_competitor_functional_reports_competitor_id ON competitor_functional_reports(product_competitor_id)"))
            db.execute(text("CREATE INDEX ix_competitor_functional_reports_product_id ON competitor_functional_reports(product_id)"))
            print("  + Created competitor_functional_reports table")
        else:
            print("  - competitor_functional_reports already exists")

        if not check_table_exists(db, "landscape_opportunity_reports"):
            db.execute(text("""
                CREATE TABLE landscape_opportunity_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL UNIQUE REFERENCES ci_products(id) ON DELETE CASCADE,
                    report_version INTEGER NOT NULL DEFAULT 1,
                    report_content_md TEXT,
                    feature_cluster_matrix JSON,
                    feature_opportunities JSON,
                    high_impact_gaps JSON,
                    source_competitor_report_ids JSON,
                    generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    queue_job_id INTEGER REFERENCES queue_jobs(id)
                )
            """))
            db.execute(text("CREATE INDEX ix_landscape_opportunity_reports_product_id ON landscape_opportunity_reports(product_id)"))
            print("  + Created landscape_opportunity_reports table")
        else:
            print("  - landscape_opportunity_reports already exists")

        db.commit()

        # === Drop deprecated tables ===
        print("\nDropping deprecated strategic analysis tables...")

        deprecated_tables = [
            "competitor_pricing_analysis",
            "competitor_positioning_analysis",
            "competitor_change_events",
            "competitor_momentum_analysis",
            "competitor_financials_analysis",
        ]

        for table_name in deprecated_tables:
            if check_table_exists(db, table_name):
                db.execute(text(f"DROP TABLE {table_name}"))
                print(f"  + Dropped {table_name}")
            else:
                print(f"  - {table_name} does not exist (skipped)")

        db.commit()

        # === Handle deprecated columns in competitive_agent_configs ===
        # SQLite doesn't support DROP COLUMN directly, so we need to recreate the table
        print("\nUpdating competitive_agent_configs table...")

        if check_table_exists(db, "competitive_agent_configs"):
            # Check if we need to update (if enable_pricing_analysis column exists)
            if check_column_exists(db, "competitive_agent_configs", "enable_pricing_analysis"):
                print("  Recreating table without deprecated columns...")

                # Create new table without deprecated columns
                db.execute(text("""
                    CREATE TABLE competitive_agent_configs_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        product_id INTEGER NOT NULL UNIQUE REFERENCES ci_products(id) ON DELETE CASCADE,

                        product_analysis_mode VARCHAR(20) NOT NULL DEFAULT 'manual',
                        product_analysis_schedule VARCHAR(50),
                        product_analysis_next_run DATETIME,
                        product_analysis_last_run DATETIME,

                        competitor_discovery_mode VARCHAR(20) NOT NULL DEFAULT 'manual',
                        competitor_discovery_schedule VARCHAR(50),
                        competitor_discovery_next_run DATETIME,
                        competitor_discovery_last_run DATETIME,
                        alert_on_new_competitors BOOLEAN NOT NULL DEFAULT 1,
                        alert_on_disappeared_competitors BOOLEAN NOT NULL DEFAULT 1,

                        deep_analysis_mode VARCHAR(20) NOT NULL DEFAULT 'manual',
                        deep_analysis_schedule VARCHAR(50),
                        deep_analysis_next_run DATETIME,
                        deep_analysis_last_run DATETIME,

                        intensity_similarity_threshold REAL NOT NULL DEFAULT 0.75,
                        intensity_idea_threshold INTEGER NOT NULL DEFAULT 3,

                        enabled BOOLEAN NOT NULL DEFAULT 1,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """))

                # Copy data (excluding deprecated columns)
                db.execute(text("""
                    INSERT INTO competitive_agent_configs_new (
                        id, product_id,
                        product_analysis_mode, product_analysis_schedule,
                        product_analysis_next_run, product_analysis_last_run,
                        competitor_discovery_mode, competitor_discovery_schedule,
                        competitor_discovery_next_run, competitor_discovery_last_run,
                        alert_on_new_competitors, alert_on_disappeared_competitors,
                        deep_analysis_mode, deep_analysis_schedule,
                        deep_analysis_next_run, deep_analysis_last_run,
                        intensity_similarity_threshold, intensity_idea_threshold,
                        enabled, created_at, updated_at
                    )
                    SELECT
                        id, product_id,
                        product_analysis_mode, product_analysis_schedule,
                        product_analysis_next_run, product_analysis_last_run,
                        competitor_discovery_mode, competitor_discovery_schedule,
                        competitor_discovery_next_run, competitor_discovery_last_run,
                        alert_on_new_competitors, alert_on_disappeared_competitors,
                        deep_analysis_mode, deep_analysis_schedule,
                        deep_analysis_next_run, deep_analysis_last_run,
                        intensity_similarity_threshold, intensity_idea_threshold,
                        enabled, created_at, updated_at
                    FROM competitive_agent_configs
                """))

                # Drop old table and rename new
                db.execute(text("DROP TABLE competitive_agent_configs"))
                db.execute(text("ALTER TABLE competitive_agent_configs_new RENAME TO competitive_agent_configs"))

                # Recreate index
                db.execute(text("CREATE INDEX ix_competitive_agent_configs_product_id ON competitive_agent_configs(product_id)"))

                print("  + Removed deprecated enable_* columns from competitive_agent_configs")
            else:
                print("  - competitive_agent_configs already updated (no deprecated columns)")
        else:
            print("  - competitive_agent_configs does not exist")

        db.commit()

        # === Create data directory for report exports ===
        print("\nCreating report export directory...")
        export_dir = os.path.join(os.path.dirname(__file__), "data", "competitive_reports")
        os.makedirs(export_dir, exist_ok=True)
        print(f"  + Created {export_dir}")

        print()
        print("=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)
        print()
        print("Deprecated tables dropped:")
        for table in deprecated_tables:
            print(f"  - {table}")
        print()
        print("New tables created:")
        print("  - competitor_functional_reports")
        print("  - landscape_opportunity_reports")
        print()
        print("Config columns removed:")
        print("  - enable_pricing_analysis")
        print("  - enable_positioning_analysis")
        print("  - enable_changes_tracking")
        print("  - enable_momentum_analysis")
        print("  - enable_financials_analysis")

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
