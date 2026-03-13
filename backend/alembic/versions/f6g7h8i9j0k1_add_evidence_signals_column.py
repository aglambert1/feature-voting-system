"""add evidence_signals column to synthesized_opportunities

Adds evidence_signals JSON column to store factbase evidence
that contributed to each synthesized opportunity (4th source).

Revision ID: f6g7h8i9j0k1
Revises: e5f6g7h8i9j0
Create Date: 2026-03-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f6g7h8i9j0k1"
down_revision: Union[str, None] = "e5f6g7h8i9j0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "synthesized_opportunities",
        sa.Column("evidence_signals", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("synthesized_opportunities", "evidence_signals")
