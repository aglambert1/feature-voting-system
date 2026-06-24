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
from sqlalchemy import inspect

revision = 'w3x4y5z6a7b8'
down_revision = 'v2w3x4y5z6a7'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_columns = {c['name'] for c in inspector.get_columns('users')}

    if 'must_change_password' not in existing_columns:
        op.add_column('users', sa.Column(
            'must_change_password', sa.Boolean(), nullable=False, server_default='0'
        ))
    if 'tokens_valid_after' not in existing_columns:
        op.add_column('users', sa.Column(
            'tokens_valid_after', sa.DateTime(timezone=True), nullable=True
        ))


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_columns = {c['name'] for c in inspector.get_columns('users')}

    if 'tokens_valid_after' in existing_columns:
        op.drop_column('users', 'tokens_valid_after')
    if 'must_change_password' in existing_columns:
        op.drop_column('users', 'must_change_password')
