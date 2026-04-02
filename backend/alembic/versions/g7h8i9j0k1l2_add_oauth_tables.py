"""add oauth tables

Revision ID: g7h8i9j0k1l2
Revises: 7f515fa04654
Create Date: 2026-04-01 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g7h8i9j0k1l2'
down_revision: Union[str, Sequence[str], None] = '7f515fa04654'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add OAuth tables for MCP HTTP server authentication."""
    # OAuth clients (Dynamic Client Registration)
    op.create_table(
        "oauth_clients",
        sa.Column("client_id", sa.String(), primary_key=True),
        sa.Column("client_secret_hash", sa.String(), nullable=True),
        sa.Column("client_name", sa.String(200), nullable=True),
        sa.Column("redirect_uris", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("grant_types", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("response_types", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("token_endpoint_auth_method", sa.String(50), nullable=False, server_default="none"),
        sa.Column("scope", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # OAuth authorization codes (short-lived, PKCE)
    op.create_table(
        "oauth_authorization_codes",
        sa.Column("code", sa.String(), primary_key=True),
        sa.Column("client_id", sa.String(), sa.ForeignKey("oauth_clients.client_id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("redirect_uri", sa.Text(), nullable=False),
        sa.Column("redirect_uri_provided_explicitly", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("scopes", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("code_challenge", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_oauth_auth_codes_client_id", "oauth_authorization_codes", ["client_id"])

    # OAuth refresh tokens (long-lived, stored as SHA-256 hash)
    op.create_table(
        "oauth_refresh_tokens",
        sa.Column("token_hash", sa.String(), primary_key=True),
        sa.Column("client_id", sa.String(), sa.ForeignKey("oauth_clients.client_id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_oauth_refresh_tokens_client_id", "oauth_refresh_tokens", ["client_id"])
    op.create_index("ix_oauth_refresh_tokens_user_id", "oauth_refresh_tokens", ["user_id"])


def downgrade() -> None:
    """Remove OAuth tables."""
    op.drop_table("oauth_refresh_tokens")
    op.drop_table("oauth_authorization_codes")
    op.drop_table("oauth_clients")
