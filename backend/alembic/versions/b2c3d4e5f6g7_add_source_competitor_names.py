"""add_source_competitor_names

Add source_competitor_names column to landscape_opportunity_reports table
to display which competitors were included in the landscape synthesis.

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('landscape_opportunity_reports') as batch_op:
        batch_op.add_column(sa.Column('source_competitor_names', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('landscape_opportunity_reports') as batch_op:
        batch_op.drop_column('source_competitor_names')
