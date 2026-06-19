"""Grant explicit OWNER permissions to existing admin users

Admin users previously bypassed all product permission checks.
Now that the bypass is removed, this migration ensures existing
admins retain access to all active products by granting them
explicit OWNER permission rows.

Revision ID: v2w3x4y5z6a7
Revises: u1v2w3x4y5z6
Create Date: 2026-06-18

"""
from alembic import op
import sqlalchemy as sa

revision = 'v2w3x4y5z6a7'
down_revision = 'u1v2w3x4y5z6'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == 'postgresql':
        active_filter = "u.is_active = true"
    else:
        active_filter = "u.is_active = 1"

    op.execute(sa.text(f"""
        INSERT INTO product_permissions (product_id, user_id, permission_level, granted_by_user_id)
        SELECT cp.id, u.id, 'owner', u.id
        FROM ci_products cp
        CROSS JOIN users u
        WHERE u.role = 'admin'
          AND {active_filter}
          AND cp.status = 'active'
          AND NOT EXISTS (
              SELECT 1 FROM product_permissions pp
              WHERE pp.product_id = cp.id AND pp.user_id = u.id
          )
    """))


def downgrade():
    pass
