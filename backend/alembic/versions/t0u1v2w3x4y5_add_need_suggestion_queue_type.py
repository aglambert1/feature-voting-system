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
        # SQLAlchemy's Enum column maps to the member *name* (uppercase), not the
        # value — the existing reviewqueuetype labels are IDEA/COMPETITIVE_ALERT/
        # REPORT. The new member must match that convention or every query filtering
        # on NEED_SUGGESTION 500s with "invalid input value for enum".
        op.execute("ALTER TYPE reviewqueuetype ADD VALUE IF NOT EXISTS 'NEED_SUGGESTION'")


def downgrade():
    # PostgreSQL does not support removing enum values; downgrade is a no-op.
    pass
