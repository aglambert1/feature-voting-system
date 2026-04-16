"""add job map to ciproduct and product_jobs table

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-04-14 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'h8i9j0k1l2m3'
down_revision: Union[str, None] = 'g7h8i9j0k1l2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enums for PostgreSQL (no-op on SQLite)
    jobtype_enum = sa.Enum('functional', 'emotional', 'social', name='jobtype')
    jobimportance_enum = sa.Enum('critical', 'high', 'medium', 'low', name='jobimportance')

    # Add JTBD columns to ci_products
    op.add_column('ci_products', sa.Column('target_customer_profile', sa.JSON(), nullable=True))
    op.add_column('ci_products', sa.Column('job_map', sa.JSON(), nullable=True))
    op.add_column('ci_products', sa.Column('job_map_version', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('ci_products', sa.Column('job_map_last_updated', sa.DateTime(), nullable=True))

    # Create product_jobs table
    op.create_table(
        'product_jobs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('job_id_key', sa.String(50), nullable=False),
        sa.Column('job_type', jobtype_enum, nullable=False),
        sa.Column('statement', sa.Text(), nullable=False),
        sa.Column('desired_outcomes', sa.JSON(), nullable=True),
        sa.Column('importance', jobimportance_enum, nullable=False, server_default='medium'),
        sa.Column('statement_embedding', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(50), server_default='active', nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['ci_products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('product_id', 'job_id_key', name='unique_product_job_key'),
    )
    op.create_index('ix_product_jobs_id', 'product_jobs', ['id'])
    op.create_index('ix_product_jobs_product_id', 'product_jobs', ['product_id'])
    op.create_index('ix_product_jobs_status', 'product_jobs', ['status'])


def downgrade() -> None:
    # Drop product_jobs table
    op.drop_index('ix_product_jobs_status', table_name='product_jobs')
    op.drop_index('ix_product_jobs_product_id', table_name='product_jobs')
    op.drop_index('ix_product_jobs_id', table_name='product_jobs')
    op.drop_table('product_jobs')

    # Drop enums (PostgreSQL only, no-op on SQLite)
    sa.Enum(name='jobimportance').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='jobtype').drop(op.get_bind(), checkfirst=True)

    # Remove JTBD columns from ci_products
    op.drop_column('ci_products', 'job_map_last_updated')
    op.drop_column('ci_products', 'job_map_version')
    op.drop_column('ci_products', 'job_map')
    op.drop_column('ci_products', 'target_customer_profile')
