"""Add login tracking and account lockout

Adds last_login_at, failed_login_attempts, locked_until to users table.
Creates login_events table for login audit trail.

Revision ID: x4y5z6a7b8c9
Revises: w3x4y5z6a7b8
Create Date: 2026-06-24

"""
from alembic import op
import sqlalchemy as sa

revision = 'x4y5z6a7b8c9'
down_revision = 'w3x4y5z6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column(
        'last_login_at', sa.DateTime(timezone=True), nullable=True
    ))
    op.add_column('users', sa.Column(
        'failed_login_attempts', sa.Integer(), nullable=False, server_default='0'
    ))
    op.add_column('users', sa.Column(
        'locked_until', sa.DateTime(timezone=True), nullable=True
    ))

    op.create_table(
        'login_events',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('logged_in_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
    )


def downgrade():
    op.drop_table('login_events')
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'failed_login_attempts')
    op.drop_column('users', 'last_login_at')
