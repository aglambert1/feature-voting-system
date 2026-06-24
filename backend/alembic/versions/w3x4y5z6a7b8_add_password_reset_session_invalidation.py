"""Add must_change_password and tokens_valid_after to users

Supports admin password reset (must_change_password forces user to
change on next login) and session invalidation (tokens_valid_after
rejects JWTs issued before a given timestamp).

Revision ID: w3x4y5z6a7b8
Revises: v2w3x4y5z6a7
Create Date: 2026-06-24

"""
from alembic import op
import sqlalchemy as sa

revision = 'w3x4y5z6a7b8'
down_revision = 'v2w3x4y5z6a7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column(
        'must_change_password', sa.Boolean(), nullable=False, server_default='0'
    ))
    op.add_column('users', sa.Column(
        'tokens_valid_after', sa.DateTime(timezone=True), nullable=True
    ))


def downgrade():
    op.drop_column('users', 'tokens_valid_after')
    op.drop_column('users', 'must_change_password')
