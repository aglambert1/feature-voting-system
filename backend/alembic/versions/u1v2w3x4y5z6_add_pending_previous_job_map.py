"""Add pending_job_map and previous_job_map to ci_products

Revision ID: u1v2w3x4y5z6
Revises: t0u1v2w3x4y5
Create Date: 2026-06-11

"""
from alembic import op
import sqlalchemy as sa

revision = 'u1v2w3x4y5z6'
down_revision = 't0u1v2w3x4y5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('ci_products') as batch_op:
        batch_op.add_column(sa.Column('pending_job_map', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('previous_job_map', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('ci_products') as batch_op:
        batch_op.drop_column('previous_job_map')
        batch_op.drop_column('pending_job_map')
