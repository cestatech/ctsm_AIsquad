"""Integration tests for /api/v1/generation/jobs endpoints.

RBAC: Admin and Contributor can trigger generation.
The background executor is NOT invoked in integration tests
(BackgroundTasks fires after response, and we only check the job record).
"""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.models.intake import StudyBrief
from app.models.study import Study


@pytest.mark.asyncio(loop_scope="session")
class TestCreateGenerationJob:
    async def test_unauthenticated_returns_403(
        self, iclient: AsyncClient, i_study: Study
    ):
        resp = await iclient.post(
            "/api/v1/generation/jobs",
            json={
                "study_id": str(i_study.id),
                "artifact_type": "PROTOCOL",
                "model_id": "claude-sonnet-4-6",
            },
        )
        assert resp.status_code == 403

    async def test_admin_can_create_job(
        self, iclient: AsyncClient, i_study: Study, admin_tok: str
    ):
        # Patch the background executor so it doesn't actually call Claude
        with patch("app.api.v1.endpoints.generation.execute_generation_job"):
            resp = await iclient.post(
                "/api/v1/generation/jobs",
                json={
                    "study_id": str(i_study.id),
                    "artifact_type": "PROTOCOL",
                    "model_id": "claude-sonnet-4-6",
                },
                headers={"Authorization": f"Bearer {admin_tok}"},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "PENDING"
        assert data["artifact_type"] == "PROTOCOL"
        assert data["study_id"] == str(i_study.id)

    async def test_contributor_can_create_job(
        self, iclient: AsyncClient, i_study: Study, contributor_tok: str
    ):
        with patch("app.api.v1.endpoints.generation.execute_generation_job"):
            resp = await iclient.post(
                "/api/v1/generation/jobs",
                json={
                    "study_id": str(i_study.id),
                    "artifact_type": "ICF",
                    "model_id": "claude-sonnet-4-6",
                },
                headers={"Authorization": f"Bearer {contributor_tok}"},
            )

        assert resp.status_code == 201

    async def test_missing_study_id_returns_422(
        self, iclient: AsyncClient, admin_tok: str
    ):
        resp = await iclient.post(
            "/api/v1/generation/jobs",
            json={"artifact_type": "PROTOCOL", "model_id": "claude-sonnet-4-6"},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 422

    async def test_invalid_artifact_type_returns_422(
        self, iclient: AsyncClient, i_study: Study, admin_tok: str
    ):
        resp = await iclient.post(
            "/api/v1/generation/jobs",
            json={
                "study_id": str(i_study.id),
                "artifact_type": "INVALID_TYPE",
                "model_id": "claude-sonnet-4-6",
            },
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
class TestListGenerationJobs:
    async def test_unauthenticated_returns_403(self, iclient: AsyncClient):
        resp = await iclient.get("/api/v1/generation/jobs")
        assert resp.status_code == 403

    async def test_returns_paginated_list(self, iclient: AsyncClient, admin_tok: str):
        resp = await iclient.get(
            "/api/v1/generation/jobs",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data


@pytest.mark.asyncio(loop_scope="session")
class TestGetGenerationJob:
    async def test_get_job_returns_correct_record(
        self, iclient: AsyncClient, i_study: Study, admin_tok: str
    ):
        with patch("app.api.v1.endpoints.generation.execute_generation_job"):
            create_resp = await iclient.post(
                "/api/v1/generation/jobs",
                json={
                    "study_id": str(i_study.id),
                    "artifact_type": "SAP",
                    "model_id": "claude-sonnet-4-6",
                },
                headers={"Authorization": f"Bearer {admin_tok}"},
            )
        job_id = create_resp.json()["id"]

        get_resp = await iclient.get(
            f"/api/v1/generation/jobs/{job_id}",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == job_id

    async def test_nonexistent_job_returns_404(
        self, iclient: AsyncClient, admin_tok: str
    ):
        resp = await iclient.get(
            f"/api/v1/generation/jobs/{uuid4()}",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
class TestGenerationFromBrief:
    async def test_unauthenticated_returns_403(
        self, iclient: AsyncClient, i_brief: StudyBrief
    ):
        resp = await iclient.post(
            "/api/v1/generation/jobs/from-brief",
            json={"brief_id": str(i_brief.id), "artifact_type": "PROTOCOL"},
        )
        assert resp.status_code == 403

    async def test_admin_can_generate_from_brief(
        self, iclient: AsyncClient, i_brief: StudyBrief, admin_tok: str
    ):
        with patch("app.api.v1.endpoints.generation.execute_generation_job"):
            resp = await iclient.post(
                "/api/v1/generation/jobs/from-brief",
                json={"brief_id": str(i_brief.id), "artifact_type": "PROTOCOL"},
                headers={"Authorization": f"Bearer {admin_tok}"},
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["artifact_type"] == "PROTOCOL"
        assert data["status"] == "PENDING"
        assert data["study_id"] == str(i_brief.study_id)

    async def test_admin_can_generate_sap_from_brief(
        self, iclient: AsyncClient, i_brief: StudyBrief, admin_tok: str
    ):
        with patch("app.api.v1.endpoints.generation.execute_generation_job"):
            resp = await iclient.post(
                "/api/v1/generation/jobs/from-brief",
                json={"brief_id": str(i_brief.id), "artifact_type": "SAP"},
                headers={"Authorization": f"Bearer {admin_tok}"},
            )
        assert resp.status_code == 201
        assert resp.json()["artifact_type"] == "SAP"

    async def test_admin_can_create_edc_generation_job(
        self, iclient: AsyncClient, i_study, admin_tok: str
    ):
        with patch("app.api.v1.endpoints.generation.execute_generation_job"):
            resp = await iclient.post(
                "/api/v1/generation/jobs",
                json={
                    "study_id": str(i_study.id),
                    "artifact_type": "EDC_CRF",
                    "model_id": "deterministic",
                },
                headers={"Authorization": f"Bearer {admin_tok}"},
            )
        assert resp.status_code == 201
        assert resp.json()["artifact_type"] == "EDC_CRF"

    async def test_invalid_brief_id_returns_404(
        self, iclient: AsyncClient, admin_tok: str
    ):
        with patch("app.api.v1.endpoints.generation.execute_generation_job"):
            resp = await iclient.post(
                "/api/v1/generation/jobs/from-brief",
                json={"brief_id": str(uuid4()), "artifact_type": "ICF"},
                headers={"Authorization": f"Bearer {admin_tok}"},
            )
        assert resp.status_code == 404

    async def test_missing_brief_id_returns_422(
        self, iclient: AsyncClient, admin_tok: str
    ):
        resp = await iclient.post(
            "/api/v1/generation/jobs/from-brief",
            json={"artifact_type": "PROTOCOL"},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 422
