"""drop landscape_opportunity_reports table

Phase 4b cleanup: remove the legacy LandscapeOpportunityReport model and
its table. Cross-competitor synthesis is now handled by the unified
SynthesisReport model (added in Phase 3a).

This is a one-way migration for practical purposes — the downgrade
recreates a barebones table but does not restore any data.

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-04-14 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "l2m3n4o5p6q7"
down_revision: Union[str, None] = "k1l2m3n4o5p6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the table. Alembic's drop_table removes the associated indexes
    # and FK references automatically for both SQLite and PostgreSQL.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    if "landscape_opportunity_reports" in tables:
        op.drop_table("landscape_opportunity_reports")


def downgrade() -> None:
    # Recreate a minimal version of the table so the downgrade is
    # structurally reversible. This will NOT restore lost data.
    op.create_table(
        "landscape_opportunity_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("report_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("report_content_md", sa.Text(), nullable=True),
        sa.Column("feature_cluster_matrix", sa.JSON(), nullable=True),
        sa.Column("feature_opportunities", sa.JSON(), nullable=True),
        sa.Column("high_impact_gaps", sa.JSON(), nullable=True),
        sa.Column("changes_from_previous", sa.JSON(), nullable=True),
        sa.Column("source_competitor_report_ids", sa.JSON(), nullable=True),
        sa.Column("source_competitor_names", sa.JSON(), nullable=True),
        sa.Column(
            "generated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("queue_job_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["product_id"], ["ci_products.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["queue_job_id"], ["queue_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id"),
    )
    op.create_index(
        "ix_landscape_opportunity_reports_id",
        "landscape_opportunity_reports",
        ["id"],
    )
    op.create_index(
        "ix_landscape_opportunity_reports_product_id",
        "landscape_opportunity_reports",
        ["product_id"],
    )
