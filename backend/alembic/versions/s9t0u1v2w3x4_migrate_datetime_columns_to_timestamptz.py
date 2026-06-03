"""Migrate all DateTime columns to TIMESTAMP WITH TIME ZONE

Converts every naive DATETIME column to TIMESTAMPTZ so that
datetime.now(timezone.utc) values round-trip without type errors.
PostgreSQL only — SQLite stores datetimes as TEXT regardless of
column type, so no DDL change is needed there.

Revision ID: s9t0u1v2w3x4
Revises: r8s9t0u1v2w3
Create Date: 2026-06-03 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "s9t0u1v2w3x4"
down_revision: Union[str, None] = "r8s9t0u1v2w3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (table, column, nullable) for every DateTime column being converted.
# nullable=True means the column accepts NULLs (affects USING cast safety).
_COLUMNS = [
    ("activity_imports", "imported_at", False),
    ("activity_imports", "processed_at", True),
    ("deal_activity_insights", "created_at", False),
    ("support_activity_insights", "created_at", False),
    ("user_api_keys", "created_at", False),
    ("user_api_keys", "expires_at", False),
    ("user_api_keys", "last_used_at", True),
    ("competitive_agent_configs", "product_analysis_next_run", True),
    ("competitive_agent_configs", "product_analysis_last_run", True),
    ("competitive_agent_configs", "competitor_discovery_next_run", True),
    ("competitive_agent_configs", "competitor_discovery_last_run", True),
    ("competitive_agent_configs", "deep_analysis_next_run", True),
    ("competitive_agent_configs", "deep_analysis_last_run", True),
    ("competitive_agent_configs", "created_at", False),
    ("competitive_agent_configs", "updated_at", False),
    ("competitor_functional_reports", "generated_at", False),
    ("competitor_alerts", "created_at", False),
    ("ci_products", "last_analyzed_at", True),
    ("ci_products", "job_map_last_updated", True),
    ("ci_products", "created_at", False),
    ("ci_products", "updated_at", False),
    ("product_jobs", "created_at", False),
    ("product_jobs", "updated_at", False),
    ("competitor_analysis_sessions", "created_at", False),
    ("competitor_analysis_sessions", "updated_at", False),
    ("competitor_analysis_sessions", "completed_at", True),
    ("product_competitors", "last_monitored_at", True),
    ("product_competitors", "audit_last_run", True),
    ("product_competitors", "cached_search_at", True),
    ("product_competitors", "created_at", False),
    ("product_competitors", "updated_at", False),
    ("session_competitors", "created_at", False),
    ("product_competitor_features", "first_seen_at", True),
    ("product_competitor_features", "last_seen_at", True),
    ("product_competitor_features", "created_at", False),
    ("product_competitor_features", "updated_at", False),
    ("competitor_features", "created_at", False),
    ("competitor_generated_ideas", "created_at", False),
    ("competitor_generated_ideas", "edited_at", True),
    ("agent_execution_logs", "created_at", False),
    ("product_permissions", "granted_at", False),
    ("product_analysis_history", "created_at", False),
    ("product_features", "created_at", False),
    ("product_features", "updated_at", False),
    ("llm_usage_logs", "created_at", False),
    ("evidence", "created_at", False),
    ("evidence", "updated_at", False),
    ("ideas", "created_at", False),
    ("ideas", "updated_at", False),
    ("idea_comments", "created_at", False),
    ("idea_lifecycle_statuses", "created_at", False),
    ("idea_status_history", "created_at", False),
    ("internal_feedback_imports", "imported_at", False),
    ("internal_feedback_imports", "processed_at", True),
    ("winloss_themes", "created_at", False),
    ("support_themes", "created_at", False),
    ("password_reset_tokens", "expires_at", False),
    ("password_reset_tokens", "created_at", False),
    ("password_reset_tokens", "used_at", True),
    ("pm_review_queue", "reviewed_at", True),
    ("pm_review_queue", "created_at", False),
    ("pm_review_queue", "updated_at", False),
    ("pm_review_queue", "due_by", True),
    ("competitor_snapshots", "snapshot_date", False),
    ("competitor_snapshots", "created_at", False),
    ("monitoring_configs", "last_monitored_at", True),
    ("monitoring_configs", "next_scheduled_at", True),
    ("monitoring_configs", "created_at", False),
    ("monitoring_configs", "updated_at", False),
    ("product_invite_codes", "expires_at", True),
    ("product_invite_codes", "created_at", False),
    ("queue_jobs", "created_at", False),
    ("queue_jobs", "queued_at", True),
    ("queue_jobs", "started_at", True),
    ("queue_jobs", "completed_at", True),
    ("submissions", "submitted_at", False),
    ("synthesis_runs", "created_at", False),
    ("synthesis_runs", "completed_at", True),
    ("synthesized_opportunities", "created_at", False),
    ("synthesis_configs", "created_at", False),
    ("synthesis_configs", "updated_at", False),
    ("synthesis_reports", "generated_at", False),
    ("users", "created_at", False),
    ("users", "updated_at", False),
    ("votes", "voted_at", False),
    ("votes", "updated_at", False),
]


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return

    for table, column, nullable in _COLUMNS:
        op.alter_column(
            table,
            column,
            type_=sa.TIMESTAMP(timezone=True),
            existing_type=sa.DateTime(),
            existing_nullable=nullable,
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return

    for table, column, nullable in reversed(_COLUMNS):
        op.alter_column(
            table,
            column,
            type_=sa.DateTime(),
            existing_type=sa.TIMESTAMP(timezone=True),
            existing_nullable=nullable,
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )
