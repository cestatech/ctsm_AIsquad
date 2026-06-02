"""
Test configuration and shared fixtures for the Celerius test suite.

Provides:
- Async test database session with rollback isolation
- Factory fixtures for organizations, users (all roles), studies, artifacts
- Authenticated test clients for each role
"""
from __future__ import annotations

import asyncio
from typing import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.base import Base
from app.models.organization import Organization
from app.models.study import Study, StudyMember, StudyStatus
from app.models.user import User

settings = get_settings()

TEST_DATABASE_URL = str(settings.DATABASE_URL).replace(
    "/celerius_dev", "/celerius_test"
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Each test gets a rolled-back session."""
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest_asyncio.fixture
async def organization(db: AsyncSession) -> Organization:
    org = Organization(
        id=uuid4(),
        name="Test Pharma Inc",
        slug=f"test-pharma-{uuid4().hex[:6]}",
        is_active=True,
    )
    db.add(org)
    await db.flush()
    return org


@pytest_asyncio.fixture
async def admin_user(db: AsyncSession, organization: Organization) -> User:
    user = User(
        id=uuid4(),
        organization_id=organization.id,
        email=f"admin-{uuid4().hex[:6]}@test.com",
        full_name="Test Admin",
        hashed_password=hash_password("TestPass123!"),
        is_active=True,
        is_system_admin=False,
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def contributor_user(db: AsyncSession, organization: Organization) -> User:
    user = User(
        id=uuid4(),
        organization_id=organization.id,
        email=f"contributor-{uuid4().hex[:6]}@test.com",
        full_name="Test Contributor",
        hashed_password=hash_password("TestPass123!"),
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def reviewer_user(db: AsyncSession, organization: Organization) -> User:
    user = User(
        id=uuid4(),
        organization_id=organization.id,
        email=f"reviewer-{uuid4().hex[:6]}@test.com",
        full_name="Test Reviewer",
        hashed_password=hash_password("TestPass123!"),
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


def make_token(user: User) -> str:
    return create_access_token(
        user_id=user.id,
        organization_id=user.organization_id,
        email=user.email,
    )


@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def admin_token(admin_user: User) -> str:
    return make_token(admin_user)


@pytest_asyncio.fixture
async def contributor_token(contributor_user: User) -> str:
    return make_token(contributor_user)


@pytest_asyncio.fixture
async def reviewer_token(reviewer_user: User) -> str:
    return make_token(reviewer_user)


@pytest_asyncio.fixture
async def study(db: AsyncSession, organization: Organization, admin_user: User) -> Study:
    s = Study(
        id=uuid4(),
        organization_id=organization.id,
        protocol_number=f"PROTO-{uuid4().hex[:6]}",
        name="Test Study Alpha",
        status=StudyStatus.ACTIVE,
        created_by_id=admin_user.id,
    )
    db.add(s)
    await db.flush()
    return s
