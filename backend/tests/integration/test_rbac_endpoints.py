"""Integration tests: RBAC enforcement at the endpoint layer.

Verifies that calling endpoints as the wrong role yields 403,
and that missing auth yields 403 (HTTPBearer) or 401 (invalid token).

Fixtures reuse the session-scoped i_org, i_admin, i_contributor, i_artifact
from conftest.py, and add a Reviewer user created here.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Role
from app.core.security import hash_password
from app.models.user import User
from tests.integration.conftest import make_token


# ---------------------------------------------------------------------------
# Reviewer fixture (session-scoped)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session")
async def i_reviewer(idb: AsyncSession, i_org) -> User:
    """A Reviewer-role user at org level."""
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


@pytest.fixture(scope="session")
def reviewer_tok(i_reviewer: User) -> str:
    return make_token(i_reviewer)


# ---------------------------------------------------------------------------
# Unauthenticated → 403 (HTTPBearer raises 403 when no header)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
class TestUnauthenticated:
    async def test_list_artifacts_no_token_returns_403(self, iclient: AsyncClient):
        resp = await iclient.get("/api/v1/artifacts")
        assert resp.status_code == 403

    async def test_create_artifact_no_token_returns_403(self, iclient: AsyncClient):
        resp = await iclient.post("/api/v1/artifacts", json={})
        assert resp.status_code == 403

    async def test_list_approvals_no_token_returns_403(self, iclient: AsyncClient):
        resp = await iclient.get("/api/v1/approvals/queue")
        assert resp.status_code == 403

    async def test_invite_user_no_token_returns_403(self, iclient: AsyncClient):
        resp = await iclient.post("/api/v1/users/invite", json={})
        assert resp.status_code == 403

    async def test_list_notifications_no_token_returns_403(self, iclient: AsyncClient):
        resp = await iclient.get("/api/v1/notifications")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Invalid token → 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
class TestInvalidToken:
    async def test_invalid_bearer_returns_401(self, iclient: AsyncClient):
        resp = await iclient.get(
            "/api/v1/artifacts",
            headers={"Authorization": "Bearer not.a.real.token"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Contributor cannot approve / reject / lock / amend
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
class TestContributorRestrictions:
    async def test_contributor_cannot_lock_artifact(
        self, iclient: AsyncClient, contributor_tok: str, i_artifact
    ):
        resp = await iclient.post(
            f"/api/v1/artifacts/{i_artifact.id}/lock",
            headers={"Authorization": f"Bearer {contributor_tok}"},
        )
        assert resp.status_code == 403

    async def test_contributor_cannot_amend_artifact(
        self, iclient: AsyncClient, contributor_tok: str, i_artifact
    ):
        resp = await iclient.post(
            f"/api/v1/artifacts/{i_artifact.id}/amend",
            headers={"Authorization": f"Bearer {contributor_tok}"},
        )
        assert resp.status_code == 403

    async def test_contributor_cannot_invite_user(
        self, iclient: AsyncClient, contributor_tok: str
    ):
        resp = await iclient.post(
            "/api/v1/users/invite",
            json={
                "email": f"x-{uuid4().hex[:6]}@example.com",
                "full_name": "X",
                "role": "CONTRIBUTOR",
            },
            headers={"Authorization": f"Bearer {contributor_tok}"},
        )
        assert resp.status_code == 403

    async def test_contributor_cannot_approve_artifact(
        self, iclient: AsyncClient, contributor_tok: str, i_artifact
    ):
        resp = await iclient.post(
            "/api/v1/approvals",
            json={
                "artifact_id": str(i_artifact.id),
                "artifact_version_id": str(i_artifact.current_version_id),
                "decision": "APPROVED",
            },
            headers={"Authorization": f"Bearer {contributor_tok}"},
        )
        assert resp.status_code == 403

    async def test_contributor_cannot_deactivate_user(
        self, iclient: AsyncClient, contributor_tok: str, i_contributor
    ):
        resp = await iclient.post(
            f"/api/v1/users/{i_contributor.id}/deactivate",
            headers={"Authorization": f"Bearer {contributor_tok}"},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Reviewer cannot create / edit / submit artifacts or manage users
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
class TestReviewerRestrictions:
    async def test_reviewer_cannot_create_artifact(
        self, iclient: AsyncClient, reviewer_tok: str, i_study
    ):
        resp = await iclient.post(
            "/api/v1/artifacts",
            json={
                "study_id": str(i_study.id),
                "artifact_type": "PROTOCOL",
                "name": "Reviewer Draft",
            },
            headers={"Authorization": f"Bearer {reviewer_tok}"},
        )
        assert resp.status_code == 403

    async def test_reviewer_cannot_submit_artifact(
        self, iclient: AsyncClient, reviewer_tok: str, i_artifact
    ):
        resp = await iclient.post(
            f"/api/v1/artifacts/{i_artifact.id}/submit",
            headers={"Authorization": f"Bearer {reviewer_tok}"},
        )
        assert resp.status_code == 403

    async def test_reviewer_cannot_invite_user(
        self, iclient: AsyncClient, reviewer_tok: str
    ):
        resp = await iclient.post(
            "/api/v1/users/invite",
            json={
                "email": f"y-{uuid4().hex[:6]}@example.com",
                "full_name": "Y",
                "role": "CONTRIBUTOR",
            },
            headers={"Authorization": f"Bearer {reviewer_tok}"},
        )
        assert resp.status_code == 403

    async def test_reviewer_cannot_lock_artifact(
        self, iclient: AsyncClient, reviewer_tok: str, i_artifact
    ):
        resp = await iclient.post(
            f"/api/v1/artifacts/{i_artifact.id}/lock",
            headers={"Authorization": f"Bearer {reviewer_tok}"},
        )
        assert resp.status_code == 403

    async def test_reviewer_cannot_edit_artifact_content(
        self, iclient: AsyncClient, reviewer_tok: str, i_artifact
    ):
        resp = await iclient.patch(
            f"/api/v1/artifacts/{i_artifact.id}",
            json={"content": {"title": "Tampered"}},
            headers={"Authorization": f"Bearer {reviewer_tok}"},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Admin can do everything the others cannot
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
class TestAdminPermissions:
    async def test_admin_can_invite_user(self, iclient: AsyncClient, admin_tok: str):
        resp = await iclient.post(
            "/api/v1/users/invite",
            json={
                "email": f"rbac-invited-{uuid4().hex[:6]}@example.com",
                "full_name": "RBAC Test User",
                "role": "CONTRIBUTOR",
            },
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "user" in data
        assert "temporary_password" in data

    async def test_admin_can_list_users(self, iclient: AsyncClient, admin_tok: str):
        resp = await iclient.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1
