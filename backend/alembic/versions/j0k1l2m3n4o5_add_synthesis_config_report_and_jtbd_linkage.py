"""add synthesis_configs, synthesis_reports, and JTBD job_id_key linkage

Phase 3a of the JTBD competitive-analysis redesign:
- Create synthesis_configs table (per-product synthesis configuration)
- Create synthesis_reports table (unified synthesis output; replaces
  LandscapeOpportunityReport in a future phase)
- Extend synthesized_opportunities with Phase 3 linkage columns
  (synthesis_report_id, job_id_key, investment_tier, job_satisfaction_delta)
- Add job_id_key linkage column + index to ideas, winloss_themes, support_themes

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-04-14 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "j0k1l2m3n4o5"
down_revision: Union[str, None] = "i9j0k1l2m3n4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- synthesis_configs ---
    op.create_table(
        "synthesis_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("included_source_types", sa.JSON(), nullable=False),
        sa.Column(
            "auto_generate_ideas",
            sa.Boolean(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "idea_priority_threshold",
            sa.Float(),
            nullable=False,
            server_default="0.7",
        ),
        sa.Column("scoring_weight_overrides", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["ci_products.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", name="unique_synthesis_config_product"),
    )
    op.create_index(
        "ix_synthesis_configs_id", "synthesis_configs", ["id"]
    )
    op.create_index(
        "ix_synthesis_configs_product_id",
        "synthesis_configs",
        ["product_id"],
    )

    # --- synthesis_reports ---
    op.create_table(
        "synthesis_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column(
            "report_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column("included_source_types", sa.JSON(), nullable=False),
        sa.Column("job_scorecard", sa.JSON(), nullable=True),
        sa.Column("feature_cluster_matrix", sa.JSON(), nullable=True),
        sa.Column("opportunities", sa.JSON(), nullable=True),
        sa.Column("high_impact_items", sa.JSON(), nullable=True),
        sa.Column("innovation_whitespace", sa.Text(), nullable=True),
        sa.Column("analysis_summary", sa.Text(), nullable=True),
        sa.Column("source_stats", sa.JSON(), nullable=True),
        sa.Column("included_competitor_ids", sa.JSON(), nullable=True),
        sa.Column("source_competitor_report_ids", sa.JSON(), nullable=True),
        sa.Column("changes_from_previous", sa.JSON(), nullable=True),
        sa.Column("report_content_md", sa.Text(), nullable=True),
        sa.Column("queue_job_id", sa.Integer(), nullable=True),
        sa.Column(
            "generated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["ci_products.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["queue_job_id"], ["queue_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_synthesis_reports_id", "synthesis_reports", ["id"]
    )
    op.create_index(
        "ix_synthesis_reports_product_id",
        "synthesis_reports",
        ["product_id"],
    )

    # --- synthesized_opportunities: Phase 3 linkage columns ---
    # Inline FK on the column works for both SQLite and PostgreSQL
    # (SQLite can't ALTER TABLE ADD CONSTRAINT).
    op.add_column(
        "synthesized_opportunities",
        sa.Column(
            "synthesis_report_id",
            sa.Integer(),
            sa.ForeignKey(
                "synthesis_reports.id",
                name="fk_synthesized_opportunities_synthesis_report_id",
                ondelete="CASCADE",
            ),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_synthesized_opportunities_synthesis_report_id",
        "synthesized_opportunities",
        ["synthesis_report_id"],
    )
    op.add_column(
        "synthesized_opportunities",
        sa.Column("job_id_key", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "synthesized_opportunities",
        sa.Column("investment_tier", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "synthesized_opportunities",
        sa.Column("job_satisfaction_delta", sa.Float(), nullable=True),
    )

    # --- ideas: job_id_key linkage ---
    op.add_column(
        "ideas",
        sa.Column("job_id_key", sa.String(length=50), nullable=True),
    )
    op.create_index("ix_ideas_job_id_key", "ideas", ["job_id_key"])

    # --- winloss_themes: job_id_key linkage ---
    op.add_column(
        "winloss_themes",
        sa.Column("job_id_key", sa.String(length=50), nullable=True),
    )
    op.create_index(
        "ix_winloss_themes_job_id_key",
        "winloss_themes",
        ["job_id_key"],
    )

    # --- support_themes: job_id_key linkage ---
    op.add_column(
        "support_themes",
        sa.Column("job_id_key", sa.String(length=50), nullable=True),
    )
    op.create_index(
        "ix_support_themes_job_id_key",
        "support_themes",
        ["job_id_key"],
    )


def downgrade() -> None:
    # Reverse in opposite order of creation.

    # support_themes
    op.drop_index("ix_support_themes_job_id_key", table_name="support_themes")
    op.drop_column("support_themes", "job_id_key")

    # winloss_themes
    op.drop_index("ix_winloss_themes_job_id_key", table_name="winloss_themes")
    op.drop_column("winloss_themes", "job_id_key")

    # ideas
    op.drop_index("ix_ideas_job_id_key", table_name="ideas")
    op.drop_column("ideas", "job_id_key")

    # synthesized_opportunities
    op.drop_column("synthesized_opportunities", "job_satisfaction_delta")
    op.drop_column("synthesized_opportunities", "investment_tier")
    op.drop_column("synthesized_opportunities", "job_id_key")
    op.drop_index(
        "ix_synthesized_opportunities_synthesis_report_id",
        table_name="synthesized_opportunities",
    )
    # The FK was added inline with the column; dropping the column removes it
    # implicitly. Skip drop_constraint (not supported in SQLite ALTER TABLE).
    op.drop_column("synthesized_opportunities", "synthesis_report_id")

    # synthesis_reports
    op.drop_index(
        "ix_synthesis_reports_product_id", table_name="synthesis_reports"
    )
    op.drop_index("ix_synthesis_reports_id", table_name="synthesis_reports")
    op.drop_table("synthesis_reports")

    # synthesis_configs
    op.drop_index(
        "ix_synthesis_configs_product_id", table_name="synthesis_configs"
    )
    op.drop_index("ix_synthesis_configs_id", table_name="synthesis_configs")
    op.drop_table("synthesis_configs")
