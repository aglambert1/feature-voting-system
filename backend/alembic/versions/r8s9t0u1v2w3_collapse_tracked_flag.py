"""collapse deep_analysis/synthesis flags into single tracked boolean

Replaces five per-competitor flags with one `tracked` boolean.
- tracked = True  → competitor is scheduled for audit + included in synthesis
- Data migrated: tracked = 1 if deep_analysis_enabled OR synthesis_included was 1
- Dropped: deep_analysis_enabled, deep_analysis_status, deep_analysis_last_run,
           audit_enabled, synthesis_included

Revision ID: r8s9t0u1v2w3
Revises: q7r8s9t0u1v2
Create Date: 2026-06-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "r8s9t0u1v2w3"
down_revision: Union[str, None] = "q7r8s9t0u1v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("product_competitors") as batch_op:
        batch_op.add_column(
            sa.Column(
                "tracked",
                sa.Boolean(),
                nullable=False,
                server_default="0",
            )
        )

    # Migrate existing data: tracked = True if either old flag was True
    op.execute(
        sa.text(
            "UPDATE product_competitors SET tracked = CASE "
            "WHEN deep_analysis_enabled OR synthesis_included THEN true "
            "ELSE false END"
        )
    )

    with op.batch_alter_table("product_competitors") as batch_op:
        batch_op.drop_column("deep_analysis_enabled")
        batch_op.drop_column("deep_analysis_status")
        batch_op.drop_column("deep_analysis_last_run")
        batch_op.drop_column("audit_enabled")
        batch_op.drop_column("synthesis_included")


def downgrade() -> None:
    with op.batch_alter_table("product_competitors") as batch_op:
        batch_op.add_column(
            sa.Column("synthesis_included", sa.Boolean(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("audit_enabled", sa.Boolean(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("deep_analysis_last_run", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("deep_analysis_status", sa.String(length=50), nullable=True)
        )
        batch_op.add_column(
            sa.Column("deep_analysis_enabled", sa.Boolean(), nullable=False, server_default="0")
        )

    # Restore old flags from tracked
    op.execute(
        sa.text(
            "UPDATE product_competitors SET "
            "deep_analysis_enabled = tracked, "
            "audit_enabled = tracked, "
            "synthesis_included = tracked"
        )
    )

    with op.batch_alter_table("product_competitors") as batch_op:
        batch_op.drop_column("tracked")
