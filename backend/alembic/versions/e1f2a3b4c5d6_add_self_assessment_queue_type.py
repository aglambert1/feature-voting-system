"""Add SELF_ASSESSMENT to the queue JobType enum

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-08-31

"""
from alembic import op

revision = 'e1f2a3b4c5d6'
down_revision = 'd0e1f2a3b4c5'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        # SQLAlchemy's Enum column stores the member *name* (uppercase), not the value.
        # The existing queue_job_type labels are PRODUCT_ANALYSIS/FUNCTIONAL_AUDIT/etc.,
        # so a lowercase label here would pass on SQLite and 500 on Postgres with
        # "invalid input value for enum".
        op.execute("ALTER TYPE queue_job_type ADD VALUE IF NOT EXISTS 'SELF_ASSESSMENT'")


def downgrade():
    # PostgreSQL does not support removing enum values; downgrade is a no-op.
    pass
