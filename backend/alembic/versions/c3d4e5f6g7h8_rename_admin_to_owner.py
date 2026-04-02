"""rename_admin_permission_to_owner

Rename ProductPermissionLevel enum value from 'admin' to 'owner'
to avoid confusion with the app-level admin role.

On PostgreSQL, the enum may already have 'owner' (if create_all() ran
after the code change) or may still have 'admin' (if created earlier).
We check the actual enum labels before attempting any rename.

On SQLite, enums are plain text — just update rows.

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-03-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6g7h8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6g7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _get_pg_enum_labels(enum_name: str) -> list:
    """Query PostgreSQL for the current labels of an enum type."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT enumlabel FROM pg_enum WHERE enumtypid = "
                "(SELECT oid FROM pg_type WHERE typname = :name) "
                "ORDER BY enumsortorder"),
        {"name": enum_name},
    )
    return [row[0] for row in result]


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        labels = _get_pg_enum_labels("productpermissionlevel")
        if "admin" in labels and "owner" not in labels:
            op.execute("ALTER TYPE productpermissionlevel RENAME VALUE 'admin' TO 'owner'")
        # If 'owner' already exists, the enum is already correct — nothing to do.
    else:
        op.execute("UPDATE product_permissions SET permission_level = 'owner' WHERE permission_level = 'admin'")
        op.execute("UPDATE product_invite_codes SET permission_level = 'owner' WHERE permission_level = 'admin'")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        labels = _get_pg_enum_labels("productpermissionlevel")
        if "owner" in labels and "admin" not in labels:
            op.execute("ALTER TYPE productpermissionlevel RENAME VALUE 'owner' TO 'admin'")
    else:
        op.execute("UPDATE product_permissions SET permission_level = 'admin' WHERE permission_level = 'owner'")
        op.execute("UPDATE product_invite_codes SET permission_level = 'admin' WHERE permission_level = 'owner'")
