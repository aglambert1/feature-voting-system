"""Add unmapped_capabilities to competitor_functional_reports

Competitor capabilities that fit no job in our map. The map is generated from our own
product description, so it cannot contain jobs we never addressed — which is where
opportunity hides. A competitor serving a job the map lacks is evidence the map is
incomplete, and it arrives free with an audit already being run.

Nullable: reports generated before this existed have no such record, and an empty list
would falsely assert that the audit looked and found nothing.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-08-31
"""
from alembic import op
import sqlalchemy as sa


revision = 'c9d0e1f2a3b4'
down_revision = 'b8c9d0e1f2a3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('competitor_functional_reports') as batch_op:
        batch_op.add_column(sa.Column('unmapped_capabilities', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('competitor_functional_reports') as batch_op:
        batch_op.drop_column('unmapped_capabilities')
