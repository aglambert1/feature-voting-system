"""
API key management endpoints for MCP HTTP server authentication.

Allows Product Owners and Admins to generate, list, and revoke API keys
for connecting external MCP clients (Claude Desktop, Cursor, etc.).
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.api_key import UserAPIKey
from app.utils.security import get_product_owner_or_admin, hash_password

router = APIRouter(prefix="/api-keys", tags=["api-keys"])

API_KEY_EXPIRY_DAYS = 90
API_KEY_PREFIX = "fiq_"


# --- Schemas ---

class APIKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class APIKeyResponse(BaseModel):
    id: int
    key_prefix: str
    name: str
    created_at: str
    expires_at: str
    last_used_at: Optional[str]
    is_revoked: bool


class APIKeyCreateResponse(APIKeyResponse):
    api_key: str  # Full key, shown only once


# --- Helpers ---

def _generate_api_key() -> Tuple[str, str]:
    """Generate a new API key and its display prefix."""
    raw = secrets.token_urlsafe(32)
    full_key = f"{API_KEY_PREFIX}{raw}"
    prefix = f"{API_KEY_PREFIX}{raw[:8]}"
    return full_key, prefix


# --- Endpoints ---

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_api_key(
    data: APIKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_product_owner_or_admin),
) -> APIKeyCreateResponse:
    """Generate a new API key. The full key is returned only once."""
    full_key, prefix = _generate_api_key()
    key_hash = hash_password(full_key)

    api_key = UserAPIKey(
        user_id=current_user.id,
        key_hash=key_hash,
        key_prefix=prefix,
        name=data.name,
        expires_at=datetime.now(timezone.utc) + timedelta(days=API_KEY_EXPIRY_DAYS),
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    return APIKeyCreateResponse(
        id=api_key.id,
        key_prefix=api_key.key_prefix,
        name=api_key.name,
        created_at=api_key.created_at.isoformat(),
        expires_at=api_key.expires_at.isoformat(),
        last_used_at=None,
        is_revoked=False,
        api_key=full_key,
    )


@router.get("")
async def list_api_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_product_owner_or_admin),
) -> List[APIKeyResponse]:
    """List all API keys for the current user (prefix only, never the full key)."""
    keys = (
        db.query(UserAPIKey)
        .filter(UserAPIKey.user_id == current_user.id)
        .order_by(UserAPIKey.created_at.desc())
        .all()
    )
    return [
        APIKeyResponse(
            id=k.id,
            key_prefix=k.key_prefix,
            name=k.name,
            created_at=k.created_at.isoformat(),
            expires_at=k.expires_at.isoformat(),
            last_used_at=k.last_used_at.isoformat() if k.last_used_at else None,
            is_revoked=k.is_revoked,
        )
        for k in keys
    ]


@router.delete("/{key_id}", status_code=status.HTTP_200_OK)
async def revoke_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_product_owner_or_admin),
):
    """Revoke an API key (soft delete)."""
    api_key = (
        db.query(UserAPIKey)
        .filter(
            UserAPIKey.id == key_id,
            UserAPIKey.user_id == current_user.id,
        )
        .first()
    )
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )
    if api_key.is_revoked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key is already revoked",
        )

    api_key.is_revoked = True
    db.commit()

    return {"message": "API key revoked", "id": key_id}
