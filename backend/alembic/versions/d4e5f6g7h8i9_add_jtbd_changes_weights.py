"""add jtbd, change detection, and scoring weight fields

Add fields across multiple tables for:
- JTBD extraction: jtbd_statement + jtbd_embedding on ideas,
  synthesized_opportunities, winloss_themes, support_themes
- Structured change detection: changes_from_previous on both report tables
- Configurable scoring weights: scoring_weights on ci_products

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-03-07 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4e5f6g7h8i9"
down_revision: Union[str, None] = "c3d4e5f6g7h8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- JTBD fields ---

    # ideas: jtbd_statement + jtbd_embedding
    op.add_column("ideas", sa.Column("jtbd_statement", sa.Text(), nullable=True))
    op.add_column("ideas", sa.Column("jtbd_embedding", sa.JSON(), nullable=True))

    # synthesized_opportunities: jtbd_statement + jtbd_embedding
    op.add_column(
        "synthesized_opportunities",
        sa.Column("jtbd_statement", sa.Text(), nullable=True),
    )
    op.add_column(
        "synthesized_opportunities",
        sa.Column("jtbd_embedding", sa.JSON(), nullable=True),
    )

    # winloss_themes: jtbd_statement
    op.add_column(
        "winloss_themes", sa.Column("jtbd_statement", sa.Text(), nullable=True)
    )

    # support_themes: jtbd_statement
    op.add_column(
        "support_themes", sa.Column("jtbd_statement", sa.Text(), nullable=True)
    )

    # --- Structured change detection ---

    # competitor_functional_reports: changes_from_previous
    op.add_column(
        "competitor_functional_reports",
        sa.Column("changes_from_previous", sa.JSON(), nullable=True),
    )

    # landscape_opportunity_reports: changes_from_previous
    op.add_column(
        "landscape_opportunity_reports",
        sa.Column("changes_from_previous", sa.JSON(), nullable=True),
    )

    # --- Configurable scoring weights ---

    # ci_products: scoring_weights
    op.add_column(
        "ci_products", sa.Column("scoring_weights", sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    # Reverse order of additions
    op.drop_column("ci_products", "scoring_weights")

    op.drop_column("landscape_opportunity_reports", "changes_from_previous")
    op.drop_column("competitor_functional_reports", "changes_from_previous")

    op.drop_column("support_themes", "jtbd_statement")
    op.drop_column("winloss_themes", "jtbd_statement")

    op.drop_column("synthesized_opportunities", "jtbd_embedding")
    op.drop_column("synthesized_opportunities", "jtbd_statement")

    op.drop_column("ideas", "jtbd_embedding")
    op.drop_column("ideas", "jtbd_statement")
