"""Add login tracking and account lockout

Adds last_login_at, failed_login_attempts, locked_until to users table.
Creates login_events table for login audit trail.

Revision ID: x4y5z6a7b8c9
Revises: w3x4y5z6a7b8
Create Date: 2026-06-24

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = 'x4y5z6a7b8c9'
down_revision = 'w3x4y5z6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_columns = {c['name'] for c in inspector.get_columns('users')}

    if 'last_login_at' not in existing_columns:
        op.add_column('users', sa.Column(
            'last_login_at', sa.DateTime(timezone=True), nullable=True
        ))
    if 'failed_login_attempts' not in existing_columns:
        op.add_column('users', sa.Column(
            'failed_login_attempts', sa.Integer(), nullable=False, server_default='0'
        ))
    if 'locked_until' not in existing_columns:
        op.add_column('users', sa.Column(
            'locked_until', sa.DateTime(timezone=True), nullable=True
        ))

    if 'login_events' not in inspector.get_table_names():
        op.create_table(
            'login_events',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('logged_in_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('ip_address', sa.String(45), nullable=True),
            sa.Column('user_agent', sa.String(500), nullable=True),
        )


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if 'login_events' in inspector.get_table_names():
        op.drop_table('login_events')

    existing_columns = {c['name'] for c in inspector.get_columns('users')}
    for col in ('locked_until', 'failed_login_attempts', 'last_login_at'):
        if col in existing_columns:
            op.drop_column('users', col)
