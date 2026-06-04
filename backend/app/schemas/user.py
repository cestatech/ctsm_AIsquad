from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str
    title: str | None
    organization_id: UUID
    is_active: bool
    is_system_admin: bool
    last_login_at: datetime | None
    created_at: datetime


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool


class UserInviteRequest(BaseModel):
    """Request body for inviting a new organization member."""

    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    role: str = Field(default="CONTRIBUTOR", pattern="^(ADMIN|CONTRIBUTOR|REVIEWER)$")


class UserInviteResponse(BaseModel):
    """Response after inviting a user; includes temp password until email service is ready."""

    user: UserResponse
    temporary_password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
