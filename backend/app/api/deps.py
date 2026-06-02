"""
FastAPI dependency injection for authentication and database sessions.

SECURITY-CRITICAL: Changes require review by rbac-agent + architect-agent.
"""

from __future__ import annotations

from typing import AsyncGenerator
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import async_session_factory
from app.models.user import User

bearer_scheme = HTTPBearer()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session. Commits on success, rolls back on error."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Validate JWT and return the authenticated user.

    - Validates token signature and expiry
    - Validates organization_id claim against the database record
    - Raises 401 for any invalid token
    - Raises 403 if user is deactivated

    The returned User's organization_id is the authoritative tenant context
    for all downstream service calls. Never use request-supplied org IDs.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "INVALID_TOKEN", "message": "Could not validate credentials."},
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(credentials.credentials)
        user_id: str = payload.get("sub")
        org_id: str = payload.get("org")
        token_type: str = payload.get("type")

        if not user_id or not org_id or token_type != "access":
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    from sqlalchemy import select

    result = await db.execute(
        select(User).where(
            User.id == UUID(user_id),
            User.organization_id == UUID(org_id),
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "USER_DEACTIVATED",
                "message": "This account has been deactivated.",
            },
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Alias for get_current_user. Use where clarity helps."""
    return current_user
