"""Drop users.default_product_access

The column held a per-user ProductAccessMode (SINGLE_USER or TEAM_WIDE). TEAM_WIDE
gave view access to every product, predating per-product sharing (ProductPermission).
No UI or API ever set it, and no production user was on TEAM_WIDE, so every row is
SINGLE_USER and the column carries no information.

The column was created by create_all(), never by a migration, so existence is checked
rather than assumed. On PostgreSQL the orphaned enum type is dropped as well.

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-10-25
"""
from alembic import op
import sqlalchemy as sa


revision = 'a3b4c5d6e7f8'
down_revision = 'f2a3b4c5d6e7'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = [c['name'] for c in sa.inspect(bind).get_columns('users')]
    if 'default_product_access' in columns:
        with op.batch_alter_table('users') as batch_op:
            batch_op.drop_column('default_product_access')

    if bind.dialect.name == 'postgresql':
        op.execute('DROP TYPE IF EXISTS productaccessmode')


def downgrade():
    # Schema symmetry only: every row comes back as SINGLE_USER, and nothing reads the
    # column. Restored as a plain string, so the PG enum type is not recreated.
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(
            sa.Column('default_product_access', sa.String(), nullable=False, server_default='SINGLE_USER')
        )
