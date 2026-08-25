"""Add retrieved_at to evidence

Records when a source was actually read, as distinct from when the evidence row
was written (created_at) or any date appearing inside the content. Freshness —
"this assessment rests on evidence a year old" — cannot be computed without it.

Nullable with no backfill: existing rows have no honest value to give, and
guessing created_at would assert a retrieval that may never have happened.

Revision ID: a7b8c9d0e1f2
Revises: z6a7b8c9d0e1
Create Date: 2026-08-25
"""
from alembic import op
import sqlalchemy as sa


revision = 'a7b8c9d0e1f2'
down_revision = 'z6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('evidence') as batch_op:
        batch_op.add_column(
            sa.Column('retrieved_at', sa.DateTime(timezone=True), nullable=True)
        )


def downgrade():
    with op.batch_alter_table('evidence') as batch_op:
        batch_op.drop_column('retrieved_at')
