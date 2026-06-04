"""Integration tests for /api/v1/comments endpoints.

Tests: list, create, update, resolve, delete.
RBAC: all authenticated users can comment; only author / Admin can edit / delete.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.models.artifact import Artifact


@pytest.mark.asyncio
class TestCommentList:
    async def test_unauthenticated_returns_401(
        self, iclient: AsyncClient, i_artifact: Artifact
    ):
        resp = await iclient.get(
            "/api/v1/comments", params={"artifact_id": str(i_artifact.id)}
        )
        assert resp.status_code == 401

    async def test_list_returns_empty_initially(
        self, iclient: AsyncClient, i_artifact: Artifact, admin_tok: str
    ):
        resp = await iclient.get(
            "/api/v1/comments",
            params={"artifact_id": str(i_artifact.id)},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0


@pytest.mark.asyncio
class TestCommentCreate:
    async def test_unauthenticated_returns_401(
        self, iclient: AsyncClient, i_artifact: Artifact
    ):
        resp = await iclient.post(
            "/api/v1/comments",
            json={"artifact_id": str(i_artifact.id), "body": "Hello"},
        )
        assert resp.status_code == 401

    async def test_contributor_can_create_comment(
        self, iclient: AsyncClient, i_artifact: Artifact, contributor_tok: str
    ):
        resp = await iclient.post(
            "/api/v1/comments",
            json={"artifact_id": str(i_artifact.id), "body": "Review note"},
            headers={"Authorization": f"Bearer {contributor_tok}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["body"] == "Review note"
        assert data["artifact_id"] == str(i_artifact.id)
        assert data["is_resolved"] is False

    async def test_admin_can_create_comment(
        self, iclient: AsyncClient, i_artifact: Artifact, admin_tok: str
    ):
        resp = await iclient.post(
            "/api/v1/comments",
            json={"artifact_id": str(i_artifact.id), "body": "Admin note"},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 201

    async def test_create_missing_body_returns_422(
        self, iclient: AsyncClient, i_artifact: Artifact, admin_tok: str
    ):
        resp = await iclient.post(
            "/api/v1/comments",
            json={"artifact_id": str(i_artifact.id)},  # missing body
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestCommentResolve:
    async def test_resolve_comment(
        self, iclient: AsyncClient, i_artifact: Artifact, admin_tok: str
    ):
        # Create a comment first
        create_resp = await iclient.post(
            "/api/v1/comments",
            json={"artifact_id": str(i_artifact.id), "body": "To be resolved"},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert create_resp.status_code == 201
        comment_id = create_resp.json()["id"]

        # Resolve it
        resolve_resp = await iclient.post(
            f"/api/v1/comments/{comment_id}/resolve",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resolve_resp.status_code == 200
        assert resolve_resp.json()["is_resolved"] is True


@pytest.mark.asyncio
class TestCommentDelete:
    async def test_author_can_delete_own_comment(
        self, iclient: AsyncClient, i_artifact: Artifact, contributor_tok: str
    ):
        create_resp = await iclient.post(
            "/api/v1/comments",
            json={"artifact_id": str(i_artifact.id), "body": "Delete me"},
            headers={"Authorization": f"Bearer {contributor_tok}"},
        )
        assert create_resp.status_code == 201
        comment_id = create_resp.json()["id"]

        delete_resp = await iclient.delete(
            f"/api/v1/comments/{comment_id}",
            headers={"Authorization": f"Bearer {contributor_tok}"},
        )
        assert delete_resp.status_code == 204

    async def test_non_author_cannot_delete_others_comment(
        self,
        iclient: AsyncClient,
        i_artifact: Artifact,
        admin_tok: str,
        contributor_tok: str,
    ):
        # Admin creates a comment
        create_resp = await iclient.post(
            "/api/v1/comments",
            json={"artifact_id": str(i_artifact.id), "body": "Admin comment"},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert create_resp.status_code == 201
        comment_id = create_resp.json()["id"]

        # Contributor tries to delete it — must fail
        delete_resp = await iclient.delete(
            f"/api/v1/comments/{comment_id}",
            headers={"Authorization": f"Bearer {contributor_tok}"},
        )
        assert delete_resp.status_code == 403
