"""Drop competitor_generated_ideas

Ideas are no longer created from competitive reports. Acting on a competitor gap in
isolation encodes "they have it, so we should build it" — parity chasing, which is what
the JTBD spine exists to prevent. A gap is already a durable job-keyed record that
synthesis consumes, so nothing is lost by letting judgement happen there instead.

The table backed that removed path and had no other reader. It was already marked
deprecated in the model, dating from the legacy session-based workflow.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-08-31
"""
from alembic import op
import sqlalchemy as sa


revision = 'f2a3b4c5d6e7'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('competitor_generated_ideas')


def downgrade():
    # Recreated for schema symmetry only. The rows are not recoverable, and nothing
    # reads this table any more.
    op.create_table(
        'competitor_generated_ideas',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('feature_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('idea_what', sa.Text(), nullable=False),
        sa.Column('idea_why', sa.Text(), nullable=False),
        sa.Column('idea_use_case', sa.Text(), nullable=False),
        sa.Column('is_differential', sa.Boolean(), server_default='0'),
        sa.Column('user_edited', sa.Boolean(), server_default='0'),
        sa.Column('user_approved', sa.Boolean(), server_default='0'),
        sa.Column('submitted_to_ideas', sa.Boolean(), server_default='0'),
        sa.Column('final_idea_id', sa.Integer(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.Column('edited_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['feature_id'], ['competitor_features.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['session_id'], ['competitor_analysis_sessions.id']),
        sa.ForeignKeyConstraint(['product_id'], ['ci_products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['final_idea_id'], ['ideas.id']),
        sa.PrimaryKeyConstraint('id'),
    )
