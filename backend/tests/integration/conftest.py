"""Integration test fixtures.

Uses the same test engine as the parent conftest but with committed sessions
(not rolled-back) so API calls can see the data. The test DB is wiped at the
end of the test session by the session-scoped test_engine fixture.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import AsyncGenerator
from uuid import uuid4

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.artifact import Artifact, ArtifactStatus, ArtifactType, ArtifactVersion
from app.models.organization import Organization
from app.models.study import Study, StudyStatus
from app.models.user import User


# ---------------------------------------------------------------------------
# Session and client
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def idb(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Committed integration-test session. Data persists until session teardown."""
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def iclient(test_engine) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client whose DB sessions use the test engine."""
    factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def _override():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_db] = _override
    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Domain fixtures  (all committed to test DB)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def i_org(idb: AsyncSession) -> Organization:
    org = Organization(
        id=uuid4(),
        name="Integration Pharma",
        slug=f"int-pharma-{uuid4().hex[:6]}",
        is_active=True,
    )
    idb.add(org)
    await idb.commit()
    await idb.refresh(org)
    return org


@pytest_asyncio.fixture
async def i_admin(idb: AsyncSession, i_org: Organization) -> User:
    user = User(
        id=uuid4(),
        organization_id=i_org.id,
        email=f"admin-{uuid4().hex[:6]}@int.test",
        full_name="Int Admin",
        hashed_password=hash_password("TestPass123!"),
        is_active=True,
        is_system_admin=True,
    )
    idb.add(user)
    await idb.commit()
    await idb.refresh(user)
    return user


@pytest_asyncio.fixture
async def i_contributor(idb: AsyncSession, i_org: Organization) -> User:
    user = User(
        id=uuid4(),
        organization_id=i_org.id,
        email=f"contrib-{uuid4().hex[:6]}@int.test",
        full_name="Int Contributor",
        hashed_password=hash_password("TestPass123!"),
        is_active=True,
        is_system_admin=False,
    )
    idb.add(user)
    await idb.commit()
    await idb.refresh(user)
    return user


@pytest_asyncio.fixture
async def i_study(idb: AsyncSession, i_org: Organization, i_admin: User) -> Study:
    study = Study(
        id=uuid4(),
        organization_id=i_org.id,
        protocol_number=f"INT-{uuid4().hex[:6]}",
        name="Integration Study",
        status=StudyStatus.ACTIVE,
        created_by_id=i_admin.id,
    )
    idb.add(study)
    await idb.commit()
    await idb.refresh(study)
    return study


@pytest_asyncio.fixture
async def i_artifact(
    idb: AsyncSession, i_org: Organization, i_study: Study, i_admin: User
) -> Artifact:
    """A DRAFT artifact with version 1, ready for comment/validation tests."""
    artifact = Artifact(
        id=uuid4(),
        organization_id=i_org.id,
        study_id=i_study.id,
        artifact_type=ArtifactType.PROTOCOL,
        name="Integration Protocol",
        status=ArtifactStatus.DRAFT,
        created_by_id=i_admin.id,
    )
    idb.add(artifact)
    await idb.flush()

    content: dict = {"title": "Integration Protocol"}
    content_hash = hashlib.sha256(
        json.dumps(content, sort_keys=True).encode()
    ).hexdigest()
    version = ArtifactVersion(
        id=uuid4(),
        artifact_id=artifact.id,
        organization_id=i_org.id,
        version_number=1,
        is_current=True,
        content=content,
        content_hash=content_hash,
        status_at_creation=ArtifactStatus.DRAFT,
        created_by_id=i_admin.id,
        created_at=datetime.now(UTC),
    )
    idb.add(version)
    await idb.flush()

    artifact.current_version_id = version.id
    artifact.current_version_number = 1
    await idb.commit()
    await idb.refresh(artifact)
    return artifact


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------


def make_token(user: User) -> str:
    return create_access_token(
        user_id=user.id,
        organization_id=user.organization_id,
        email=user.email,
    )


@pytest_asyncio.fixture
async def admin_tok(i_admin: User) -> str:
    return make_token(i_admin)


@pytest_asyncio.fixture
async def contributor_tok(i_contributor: User) -> str:
    return make_token(i_contributor)
