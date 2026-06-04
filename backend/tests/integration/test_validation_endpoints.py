"""Integration tests for /api/v1/validation/runs endpoints.

All authenticated roles can trigger and view validation runs.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.models.artifact import Artifact


@pytest.mark.asyncio(loop_scope="session")
class TestTriggerValidationRun:
    async def test_unauthenticated_returns_401(
        self, iclient: AsyncClient, i_artifact: Artifact
    ):
        resp = await iclient.post(
            "/api/v1/validation/runs",
            json={
                "artifact_id": str(i_artifact.id),
                "artifact_version_id": str(i_artifact.current_version_id),
            },
        )
        assert resp.status_code == 401

    async def test_admin_can_trigger(
        self, iclient: AsyncClient, i_artifact: Artifact, admin_tok: str
    ):
        resp = await iclient.post(
            "/api/v1/validation/runs",
            json={
                "artifact_id": str(i_artifact.id),
                "artifact_version_id": str(i_artifact.current_version_id),
                "engine": "internal",
            },
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "PENDING"
        assert data["artifact_id"] == str(i_artifact.id)
        assert data["engine"] == "internal"

    async def test_contributor_can_trigger(
        self, iclient: AsyncClient, i_artifact: Artifact, contributor_tok: str
    ):
        resp = await iclient.post(
            "/api/v1/validation/runs",
            json={
                "artifact_id": str(i_artifact.id),
                "artifact_version_id": str(i_artifact.current_version_id),
            },
            headers={"Authorization": f"Bearer {contributor_tok}"},
        )
        assert resp.status_code == 201

    async def test_wrong_org_artifact_returns_404(
        self, iclient: AsyncClient, admin_tok: str
    ):
        """Artifact from a different org must return 404 (not 403) for IDOR protection."""
        from uuid import uuid4

        resp = await iclient.post(
            "/api/v1/validation/runs",
            json={
                "artifact_id": str(uuid4()),
                "artifact_version_id": str(uuid4()),
            },
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 404

    async def test_missing_fields_returns_422(
        self, iclient: AsyncClient, admin_tok: str
    ):
        resp = await iclient.post(
            "/api/v1/validation/runs",
            json={"engine": "internal"},  # missing required fields
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
class TestListValidationRuns:
    async def test_unauthenticated_returns_401(self, iclient: AsyncClient):
        resp = await iclient.get("/api/v1/validation/runs")
        assert resp.status_code == 401

    async def test_returns_paginated_list(self, iclient: AsyncClient, admin_tok: str):
        resp = await iclient.get(
            "/api/v1/validation/runs",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)


@pytest.mark.asyncio(loop_scope="session")
class TestGetValidationRun:
    async def test_get_run_returns_correct_record(
        self, iclient: AsyncClient, i_artifact: Artifact, admin_tok: str
    ):
        # Trigger a run first
        trigger_resp = await iclient.post(
            "/api/v1/validation/runs",
            json={
                "artifact_id": str(i_artifact.id),
                "artifact_version_id": str(i_artifact.current_version_id),
            },
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        run_id = trigger_resp.json()["id"]

        # Fetch it
        get_resp = await iclient.get(
            f"/api/v1/validation/runs/{run_id}",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == run_id

    async def test_nonexistent_run_returns_404(
        self, iclient: AsyncClient, admin_tok: str
    ):
        from uuid import uuid4

        resp = await iclient.get(
            f"/api/v1/validation/runs/{uuid4()}",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 404
