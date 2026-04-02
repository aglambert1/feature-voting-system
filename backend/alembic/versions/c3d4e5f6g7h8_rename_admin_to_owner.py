"""rename_admin_permission_to_owner

Rename ProductPermissionLevel enum value from 'admin' to 'owner'
to avoid confusion with the app-level admin role.

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


def _is_pg() -> bool:
    from alembic import context
    return context.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if _is_pg():
        # PostgreSQL: rename the enum value at the type level.
        # The enum was created as ('view', 'edit', 'admin') by
        # Base.metadata.create_all(); the code now expects 'owner'.
        # ALTER TYPE ... RENAME VALUE was added in PostgreSQL 10.
        op.execute("ALTER TYPE productpermissionlevel RENAME VALUE 'admin' TO 'owner'")
    else:
        # SQLite: enums are plain text columns, just update the data.
        op.execute("UPDATE product_permissions SET permission_level = 'owner' WHERE permission_level = 'admin'")
        op.execute("UPDATE product_invite_codes SET permission_level = 'owner' WHERE permission_level = 'admin'")


def downgrade() -> None:
    if _is_pg():
        op.execute("ALTER TYPE productpermissionlevel RENAME VALUE 'owner' TO 'admin'")
    else:
        op.execute("UPDATE product_permissions SET permission_level = 'admin' WHERE permission_level = 'owner'")
        op.execute("UPDATE product_invite_codes SET permission_level = 'admin' WHERE permission_level = 'owner'")
