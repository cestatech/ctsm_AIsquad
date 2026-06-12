"""Integration test fixtures.

All fixtures are session-scoped to match test_engine's scope, ensuring
every fixture coroutine and test function runs on the same event loop that
asyncpg's connection pool was bound to.  Data committed during setup
persists for the full test session; tests are written to not require a
clean DB between runs (unique UUIDs, ordered test classes).
"""

from __future__ import annotations

import hashlib
import json
from contextlib import ExitStack
from datetime import UTC, datetime
from typing import AsyncGenerator
from unittest.mock import patch
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import get_db
from app.core.permissions import Role
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.artifact import Artifact, ArtifactStatus, ArtifactType, ArtifactVersion
from app.models.intake import SponsorIntake, IntakeStatus, StudyBrief
from app.models.organization import Organization
from app.models.study import Study, StudyStatus
from app.models.user import User


# ---------------------------------------------------------------------------
# Session and client  (scope="session" matches test_engine)
# ---------------------------------------------------------------------------

_BACKGROUND_EXECUTOR_MODULES = (
    "app.services.validation_executor",
    "app.services.generation_executor",
    "app.services.submission_executor",
)


@pytest.fixture(scope="session", autouse=True)
def _bind_background_executors_to_test_db(test_engine) -> AsyncGenerator[None, None]:
    """Background tasks must use the integration test DB, not the app default."""
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    with ExitStack() as stack:
        for module in _BACKGROUND_EXECUTOR_MODULES:
            stack.enter_context(patch(f"{module}.async_session_factory", factory))
        yield


@pytest_asyncio.fixture(scope="session")
async def idb(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Single committed session for the full test session."""
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture(scope="session")
async def iclient(test_engine) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client whose get_db override uses the test engine."""
    factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def _override():
        async with factory() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    app.dependency_overrides[get_db] = _override
    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Domain fixtures  (session-scoped, committed once)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session")
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


@pytest_asyncio.fixture(scope="session")
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


@pytest_asyncio.fixture(scope="session")
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


@pytest_asyncio.fixture(scope="session")
async def i_reviewer(idb: AsyncSession, i_org: Organization) -> User:
    user = User(
        id=uuid4(),
        organization_id=i_org.id,
        email=f"reviewer-{uuid4().hex[:6]}@int.test",
        full_name="Int Reviewer",
        hashed_password=hash_password("TestPass123!"),
        is_active=True,
        is_system_admin=False,
        org_role=Role.REVIEWER,
    )
    idb.add(user)
    await idb.commit()
    await idb.refresh(user)
    return user


@pytest_asyncio.fixture(scope="session")
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


@pytest_asyncio.fixture(scope="session")
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
# Token helpers  (sync — tokens are plain strings, no async needed)
# ---------------------------------------------------------------------------


def make_token(user: User) -> str:
    return create_access_token(
        user_id=user.id,
        organization_id=user.organization_id,
        email=user.email,
    )


@pytest.fixture(scope="session")
def admin_tok(i_admin: User) -> str:
    return make_token(i_admin)


@pytest.fixture(scope="session")
def contributor_tok(i_contributor: User) -> str:
    return make_token(i_contributor)


@pytest.fixture(scope="session")
def reviewer_tok(i_reviewer: User) -> str:
    return make_token(i_reviewer)


@pytest_asyncio.fixture(scope="session")
async def i_brief(
    idb: AsyncSession, i_org: Organization, i_study: Study, i_admin: User
) -> StudyBrief:
    """A compiled Study Brief for generation-from-brief tests."""
    intake = SponsorIntake(
        id=uuid4(),
        organization_id=i_org.id,
        study_id=i_study.id,
        created_by_id=i_admin.id,
        status=IntakeStatus.COMPILED,
        domains_completed=["STUDY_OVERVIEW"],
        ready_to_compile=True,
    )
    idb.add(intake)
    await idb.flush()

    brief = StudyBrief(
        id=uuid4(),
        intake_id=intake.id,
        organization_id=i_org.id,
        study_id=i_study.id,
        compiled_by_id=i_admin.id,
        content={"study_overview": {"title": "Integration Study", "phase": "Phase 2"}},
    )
    idb.add(brief)
    await idb.commit()
    await idb.refresh(brief)
    return brief
