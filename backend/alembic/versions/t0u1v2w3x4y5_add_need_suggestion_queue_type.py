"""Add NEED_SUGGESTION to ReviewQueueType enum

Revision ID: t0u1v2w3x4y5
Revises: s9t0u1v2w3x4
Create Date: 2026-06-08

"""
from alembic import op

revision = 't0u1v2w3x4y5'
down_revision = 's9t0u1v2w3x4'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute("ALTER TYPE reviewqueuetype ADD VALUE IF NOT EXISTS 'need_suggestion'")


def downgrade():
    # PostgreSQL does not support removing enum values; downgrade is a no-op.
    pass
