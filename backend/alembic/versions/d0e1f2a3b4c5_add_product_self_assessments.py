"""Add product_self_assessments

Our score against each job, assessed once rather than re-derived inside every competitor
audit — where the same job could otherwise carry a different "our" score in each report.

Shaped like competitor_functional_reports on purpose: a self-assessment is an audit whose
subject is us. Same job-keyed structure and versioning, so a comparison view can put our
column beside the competitors with no special-casing.

evidence_based records whether anything other than the product's own description informed
the assessment. It is not a quality score — the job map is generated from that description,
so an assessment with no independent evidence is circular and should be read that way.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-08-31
"""
from alembic import op
import sqlalchemy as sa


revision = 'd0e1f2a3b4c5'
down_revision = 'c9d0e1f2a3b4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'product_self_assessments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('assessment_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('job_map_version', sa.Integer(), nullable=True),
        sa.Column('job_assessments', sa.JSON(), nullable=True),
        # server_default '0' rather than sa.text('false') — SQLite has no boolean literal
        sa.Column('evidence_based', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('assessment_summary', sa.Text(), nullable=True),
        sa.Column(
            'generated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.Column('queue_job_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['product_id'], ['ci_products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['queue_job_id'], ['queue_jobs.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_product_self_assessments_product_id'),
        'product_self_assessments',
        ['product_id'],
    )
    op.create_index(
        op.f('ix_product_self_assessments_id'),
        'product_self_assessments',
        ['id'],
    )


def downgrade():
    op.drop_index(op.f('ix_product_self_assessments_id'), table_name='product_self_assessments')
    op.drop_index(
        op.f('ix_product_self_assessments_product_id'),
        table_name='product_self_assessments',
    )
    op.drop_table('product_self_assessments')
