"""
JWT token creation, validation, and password hashing.

SECURITY-CRITICAL: Changes to this file require review by rbac-agent + architect-agent.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import bcrypt
from jose import jwt

from app.core.config import get_settings

settings = get_settings()


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt (cost factor 12)."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ---------------------------------------------------------------------------
# JWT tokens
# ---------------------------------------------------------------------------


def create_access_token(
    user_id: UUID,
    organization_id: UUID,
    email: str,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """
    Create a short-lived JWT access token.

    Claims: sub (user_id), org (organization_id), email, type, iat, exp.
    """
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "org": str(organization_id),
        "email": email,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


def create_refresh_token_value() -> str:
    """
    Generate a cryptographically random refresh token value (not a JWT).
    The value is stored hashed in the database.
    """
    import secrets

    return secrets.token_urlsafe(64)


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT access token.

    Raises JWTError on invalid or expired tokens.
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        options={"verify_exp": True},
    )


def hash_token(token: str) -> str:
    """Hash a refresh token value for storage. Uses SHA-256."""
    import hashlib

    return hashlib.sha256(token.encode()).hexdigest()
