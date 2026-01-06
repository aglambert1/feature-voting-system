#!/usr/bin/env python3
"""
Migration script for Competitive Agent restructuring.

This script adds new tables and columns for the agent-centric competitive
intelligence architecture:

New tables:
- competitive_agent_configs
- feature_clusters
- feature_cluster_members
- competitor_pricing_analysis
- competitor_positioning_analysis
- competitor_change_events
- competitor_momentum_analysis
- competitor_financials_analysis

New columns:
- product_competitors: deep_analysis_enabled, deep_analysis_last_run, deep_analysis_status
- ideas: source_cluster_id, source_feature_ids

Usage:
    cd backend
    python migrate_competitive_agents.py
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
        print("Competitive Agent Migration")
        print("=" * 60)
        print()

        # === Add columns to product_competitors ===
        print("Checking product_competitors table...")

        if not check_column_exists(db, "product_competitors", "deep_analysis_enabled"):
            db.execute(text("""
                ALTER TABLE product_competitors
                ADD COLUMN deep_analysis_enabled BOOLEAN NOT NULL DEFAULT 0
            """))
            print("  + Added deep_analysis_enabled column")
        else:
            print("  - deep_analysis_enabled already exists")

        if not check_column_exists(db, "product_competitors", "deep_analysis_last_run"):
            db.execute(text("""
                ALTER TABLE product_competitors
                ADD COLUMN deep_analysis_last_run DATETIME
            """))
            print("  + Added deep_analysis_last_run column")
        else:
            print("  - deep_analysis_last_run already exists")

        if not check_column_exists(db, "product_competitors", "deep_analysis_status"):
            db.execute(text("""
                ALTER TABLE product_competitors
                ADD COLUMN deep_analysis_status VARCHAR(50)
            """))
            print("  + Added deep_analysis_status column")
        else:
            print("  - deep_analysis_status already exists")

        # === Add columns to ideas ===
        print("\nChecking ideas table...")

        if not check_column_exists(db, "ideas", "source_cluster_id"):
            db.execute(text("""
                ALTER TABLE ideas
                ADD COLUMN source_cluster_id INTEGER REFERENCES feature_clusters(id)
            """))
            print("  + Added source_cluster_id column")
        else:
            print("  - source_cluster_id already exists")

        if not check_column_exists(db, "ideas", "source_feature_ids"):
            db.execute(text("""
                ALTER TABLE ideas
                ADD COLUMN source_feature_ids JSON
            """))
            print("  + Added source_feature_ids column")
        else:
            print("  - source_feature_ids already exists")

        # === Create new tables ===
        print("\nChecking new tables...")

        if not check_table_exists(db, "competitive_agent_configs"):
            db.execute(text("""
                CREATE TABLE competitive_agent_configs (
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

                    enable_pricing_analysis BOOLEAN NOT NULL DEFAULT 1,
                    enable_positioning_analysis BOOLEAN NOT NULL DEFAULT 1,
                    enable_changes_tracking BOOLEAN NOT NULL DEFAULT 1,
                    enable_momentum_analysis BOOLEAN NOT NULL DEFAULT 1,
                    enable_financials_analysis BOOLEAN NOT NULL DEFAULT 0,

                    intensity_similarity_threshold REAL NOT NULL DEFAULT 0.75,
                    intensity_idea_threshold INTEGER NOT NULL DEFAULT 3,

                    enabled BOOLEAN NOT NULL DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            db.execute(text("CREATE INDEX ix_competitive_agent_configs_product_id ON competitive_agent_configs(product_id)"))
            print("  + Created competitive_agent_configs table")
        else:
            print("  - competitive_agent_configs already exists")

        if not check_table_exists(db, "feature_clusters"):
            db.execute(text("""
                CREATE TABLE feature_clusters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL REFERENCES ci_products(id) ON DELETE CASCADE,
                    cluster_name VARCHAR(255) NOT NULL,
                    cluster_description TEXT,
                    centroid_embedding JSON,
                    competitor_count INTEGER NOT NULL DEFAULT 0,
                    feature_count INTEGER NOT NULL DEFAULT 0,
                    idea_generated BOOLEAN NOT NULL DEFAULT 0,
                    generated_idea_id INTEGER REFERENCES ideas(id),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            db.execute(text("CREATE INDEX ix_feature_clusters_product_id ON feature_clusters(product_id)"))
            print("  + Created feature_clusters table")
        else:
            print("  - feature_clusters already exists")

        if not check_table_exists(db, "feature_cluster_members"):
            db.execute(text("""
                CREATE TABLE feature_cluster_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cluster_id INTEGER NOT NULL REFERENCES feature_clusters(id) ON DELETE CASCADE,
                    feature_id INTEGER NOT NULL REFERENCES product_competitor_features(id) ON DELETE CASCADE,
                    similarity_score REAL,
                    added_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            db.execute(text("CREATE INDEX ix_feature_cluster_members_cluster_id ON feature_cluster_members(cluster_id)"))
            db.execute(text("CREATE INDEX ix_feature_cluster_members_feature_id ON feature_cluster_members(feature_id)"))
            print("  + Created feature_cluster_members table")
        else:
            print("  - feature_cluster_members already exists")

        if not check_table_exists(db, "competitor_pricing_analysis"):
            db.execute(text("""
                CREATE TABLE competitor_pricing_analysis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_competitor_id INTEGER NOT NULL REFERENCES product_competitors(id) ON DELETE CASCADE,
                    pricing_model VARCHAR(100),
                    has_free_tier BOOLEAN NOT NULL DEFAULT 0,
                    has_trial BOOLEAN NOT NULL DEFAULT 0,
                    trial_days INTEGER,
                    pricing_tiers JSON,
                    has_enterprise BOOLEAN NOT NULL DEFAULT 0,
                    enterprise_contact_required BOOLEAN NOT NULL DEFAULT 0,
                    source_url VARCHAR(500),
                    confidence REAL,
                    analyzed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    queue_job_id INTEGER REFERENCES queue_jobs(id)
                )
            """))
            db.execute(text("CREATE INDEX ix_competitor_pricing_analysis_competitor_id ON competitor_pricing_analysis(product_competitor_id)"))
            print("  + Created competitor_pricing_analysis table")
        else:
            print("  - competitor_pricing_analysis already exists")

        if not check_table_exists(db, "competitor_positioning_analysis"):
            db.execute(text("""
                CREATE TABLE competitor_positioning_analysis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_competitor_id INTEGER NOT NULL REFERENCES product_competitors(id) ON DELETE CASCADE,
                    tagline VARCHAR(500),
                    value_propositions JSON,
                    target_audience TEXT,
                    target_company_size VARCHAR(100),
                    target_industries JSON,
                    key_differentiators JSON,
                    positioning_statement TEXT,
                    market_segment VARCHAR(100),
                    source_urls JSON,
                    confidence REAL,
                    analyzed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    queue_job_id INTEGER REFERENCES queue_jobs(id)
                )
            """))
            db.execute(text("CREATE INDEX ix_competitor_positioning_analysis_competitor_id ON competitor_positioning_analysis(product_competitor_id)"))
            print("  + Created competitor_positioning_analysis table")
        else:
            print("  - competitor_positioning_analysis already exists")

        if not check_table_exists(db, "competitor_change_events"):
            db.execute(text("""
                CREATE TABLE competitor_change_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_competitor_id INTEGER NOT NULL REFERENCES product_competitors(id) ON DELETE CASCADE,
                    event_type VARCHAR(50) NOT NULL,
                    event_title VARCHAR(500) NOT NULL,
                    event_description TEXT,
                    event_date DATETIME,
                    source_url VARCHAR(500),
                    source_type VARCHAR(100),
                    impact_level VARCHAR(50),
                    detected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    queue_job_id INTEGER REFERENCES queue_jobs(id)
                )
            """))
            db.execute(text("CREATE INDEX ix_competitor_change_events_competitor_id ON competitor_change_events(product_competitor_id)"))
            db.execute(text("CREATE INDEX ix_competitor_change_events_event_type ON competitor_change_events(event_type)"))
            print("  + Created competitor_change_events table")
        else:
            print("  - competitor_change_events already exists")

        if not check_table_exists(db, "competitor_momentum_analysis"):
            db.execute(text("""
                CREATE TABLE competitor_momentum_analysis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_competitor_id INTEGER NOT NULL REFERENCES product_competitors(id) ON DELETE CASCADE,
                    customer_wins JSON,
                    customer_growth_trend VARCHAR(50),
                    notable_customers JSON,
                    new_markets JSON,
                    partnership_announcements JSON,
                    release_velocity VARCHAR(50),
                    major_launches_last_90_days INTEGER,
                    community_growth_signals JSON,
                    momentum_score REAL,
                    momentum_trend VARCHAR(50),
                    analysis_summary TEXT,
                    confidence REAL,
                    analyzed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    queue_job_id INTEGER REFERENCES queue_jobs(id)
                )
            """))
            db.execute(text("CREATE INDEX ix_competitor_momentum_analysis_competitor_id ON competitor_momentum_analysis(product_competitor_id)"))
            print("  + Created competitor_momentum_analysis table")
        else:
            print("  - competitor_momentum_analysis already exists")

        if not check_table_exists(db, "competitor_financials_analysis"):
            db.execute(text("""
                CREATE TABLE competitor_financials_analysis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_competitor_id INTEGER NOT NULL REFERENCES product_competitors(id) ON DELETE CASCADE,
                    company_type VARCHAR(50),
                    total_funding REAL,
                    last_funding_round JSON,
                    funding_stage VARCHAR(50),
                    market_cap REAL,
                    revenue_ttm REAL,
                    revenue_growth_yoy REAL,
                    employee_count INTEGER,
                    employee_growth_yoy REAL,
                    financial_health VARCHAR(50),
                    analysis_summary TEXT,
                    data_sources JSON,
                    confidence REAL,
                    analyzed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    queue_job_id INTEGER REFERENCES queue_jobs(id)
                )
            """))
            db.execute(text("CREATE INDEX ix_competitor_financials_analysis_competitor_id ON competitor_financials_analysis(product_competitor_id)"))
            print("  + Created competitor_financials_analysis table")
        else:
            print("  - competitor_financials_analysis already exists")

        db.commit()

        print()
        print("=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\nError during migration: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    run_migration()
