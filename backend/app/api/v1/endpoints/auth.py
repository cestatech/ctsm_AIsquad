from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import Response as PlainResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import get_settings
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, RegisterRequest, TokenResponse
from app.schemas.user import AuthResponse, UserResponse
from app.services.auth_service import AuthService
from app.services.context_graph_service import ContextGraphService

router = APIRouter()
settings = get_settings()

_COOKIE = "refresh_token"
_COOKIE_MAX_AGE = settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_COOKIE,
        value=token,
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
        max_age=_COOKIE_MAX_AGE,
        path="/api/v1/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=_COOKIE, path="/api/v1/auth")


@router.post(
    "/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Register a new organization and its first admin user."""
    service = AuthService(db)
    user, access_token, refresh_token = await service.register(
        body,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await ContextGraphService(db).emit_event(
        organization_id=user.organization_id,
        event_type="USER_REGISTERED",
        actor_user_id=user.id,
        payload={
            "user_id": str(user.id),
            "email": user.email,
            "ip_address": request.client.host if request.client else None,
        },
    )
    _set_refresh_cookie(response, refresh_token)
    return AuthResponse(
        access_token=access_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Authenticate user credentials and return access token."""
    service = AuthService(db)
    user, access_token, refresh_token = await service.login(
        body.email,
        body.password,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await ContextGraphService(db).emit_event(
        organization_id=user.organization_id,
        event_type="USER_LOGIN",
        actor_user_id=user.id,
        payload={
            "user_id": str(user.id),
            "email": user.email,
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        },
    )
    _set_refresh_cookie(response, refresh_token)
    return AuthResponse(
        access_token=access_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Exchange a valid refresh token cookie for a new access token."""
    token_value = request.cookies.get(_COOKIE)
    if not token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "NO_REFRESH_TOKEN",
                "message": "No refresh token provided.",
            },
        )
    service = AuthService(db)
    new_access, new_refresh = await service.refresh(
        token_value,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    _set_refresh_cookie(response, new_refresh)
    return TokenResponse(
        access_token=new_access,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout")
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlainResponse:
    """Revoke the refresh token and clear the cookie."""
    token_value = request.cookies.get(_COOKIE)
    if token_value:
        service = AuthService(db)
        await service.logout(token_value)
    await ContextGraphService(db).emit_event(
        organization_id=current_user.organization_id,
        event_type="USER_LOGOUT",
        actor_user_id=current_user.id,
        payload={
            "user_id": str(current_user.id),
            "ip_address": request.client.host if request.client else None,
        },
    )
    resp = PlainResponse(status_code=status.HTTP_204_NO_CONTENT)
    resp.delete_cookie(key=_COOKIE, path="/api/v1/auth")
    return resp


@router.post(
    "/change-password",
    response_class=PlainResponse,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlainResponse:
    """Change the current user's password. Requires the correct current password."""
    service = AuthService(db)
    await service.change_password(
        actor=current_user,
        current_password=body.current_password,
        new_password=body.new_password,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return PlainResponse(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return the currently authenticated user."""
    return UserResponse.model_validate(current_user)
