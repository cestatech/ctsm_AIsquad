"""Integration tests for dual-programmer statistical QC endpoints."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.models.study import Study


async def _seed_sdtm_and_generate(
    iclient: AsyncClient,
    idb,
    i_study: Study,
    i_org,
    i_admin,
    admin_tok: str,
) -> str:
    """Seed SDTM artifact via generate-sdtm or direct insert; return artifact id."""
    from tests.integration.test_adam_endpoints import _create_sdtm_artifact

    return await _create_sdtm_artifact(
        iclient, idb, i_study, i_org, i_admin, admin_tok
    )


@pytest.mark.asyncio(loop_scope="session")
class TestStatisticalQCEndpoints:
    async def test_list_runs_after_sdtm_generation(
        self,
        iclient: AsyncClient,
        idb,
        i_study: Study,
        i_org,
        i_admin,
        admin_tok: str,
    ):
        artifact_id = await _seed_sdtm_and_generate(
            iclient, idb, i_study, i_org, i_admin, admin_tok
        )

        resp = await iclient.get(
            "/api/v1/statistical-qc/runs",
            params={"output_artifact_id": artifact_id},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        run = data["items"][0]
        assert run["workflow_step"] == "RAW_TO_SDTM"
        assert run["primary_r_program"]
        assert run["qc_r_program"]
        assert run["status"] in {
            "R_UNAVAILABLE",
            "MATCH",
            "MISMATCH",
            "PROGRAMS_GENERATED",
            "EXECUTION_FAILED",
        }

    async def test_get_run_detail(
        self,
        iclient: AsyncClient,
        idb,
        i_study: Study,
        i_org,
        i_admin,
        admin_tok: str,
    ):
        artifact_id = await _seed_sdtm_and_generate(
            iclient, idb, i_study, i_org, i_admin, admin_tok
        )
        listing = await iclient.get(
            "/api/v1/statistical-qc/runs",
            params={"output_artifact_id": artifact_id},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        run_id = listing.json()["items"][0]["id"]

        detail = await iclient.get(
            f"/api/v1/statistical-qc/runs/{run_id}",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert detail.status_code == 200
        body = detail.json()
        assert body["id"] == run_id
        assert body["comparison_result"] is not None

    async def test_list_empty_for_unknown_artifact(
        self, iclient: AsyncClient, admin_tok: str
    ):
        resp = await iclient.get(
            "/api/v1/statistical-qc/runs",
            params={"output_artifact_id": str(uuid4())},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    async def test_download_r_programs(
        self,
        iclient: AsyncClient,
        idb,
        i_study: Study,
        i_org,
        i_admin,
        admin_tok: str,
    ):
        artifact_id = await _seed_sdtm_and_generate(
            iclient, idb, i_study, i_org, i_admin, admin_tok
        )
        listing = await iclient.get(
            "/api/v1/statistical-qc/runs",
            params={"output_artifact_id": artifact_id},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        run_id = listing.json()["items"][0]["id"]

        primary = await iclient.get(
            f"/api/v1/statistical-qc/runs/{run_id}/primary-program",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert primary.status_code == 200
        assert "library(" in primary.text or "R" in primary.text
        assert "attachment" in primary.headers.get("content-disposition", "")

        qc = await iclient.get(
            f"/api/v1/statistical-qc/runs/{run_id}/qc-program",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert qc.status_code == 200
        assert qc.text
        assert "attachment" in qc.headers.get("content-disposition", "")
