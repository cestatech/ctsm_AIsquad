"""Integration tests for CSR generation endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.models.study import Study


async def _tlf_artifact_id(
    iclient: AsyncClient,
    idb,
    i_study: Study,
    i_org,
    i_admin,
    admin_tok: str,
) -> str:
    from tests.integration.test_tlf_endpoints import _adam_artifact_id

    adam_id = await _adam_artifact_id(
        iclient, idb, i_study, i_org, i_admin, admin_tok
    )
    gen = await iclient.post(
        f"/api/v1/tlf/artifacts/{adam_id}/generate-tlf",
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert gen.status_code == 200
    return gen.json()["artifact_id"]


@pytest.mark.asyncio(loop_scope="session")
class TestCSREndpoints:
    async def test_csr_readiness(
        self,
        iclient: AsyncClient,
        idb,
        i_study: Study,
        i_org,
        i_admin,
        admin_tok: str,
    ):
        tlf_id = await _tlf_artifact_id(
            iclient, idb, i_study, i_org, i_admin, admin_tok
        )
        resp = await iclient.get(
            f"/api/v1/csr/studies/{i_study.id}/csr-readiness",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tlf_artifact_count"] >= 1
        assert data["ready"] is True
        assert any(a["artifact_id"] == tlf_id for a in data["tlf_artifacts"])

    async def test_generate_csr_from_tlf(
        self,
        iclient: AsyncClient,
        idb,
        i_study: Study,
        i_org,
        i_admin,
        admin_tok: str,
    ):
        tlf_id = await _tlf_artifact_id(
            iclient, idb, i_study, i_org, i_admin, admin_tok
        )
        resp = await iclient.post(
            f"/api/v1/csr/artifacts/{tlf_id}/generate-csr",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["section_count"] >= 9
        assert data["artifact_id"]

        artifact = await iclient.get(
            f"/api/v1/artifacts/{data['artifact_id']}",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert artifact.status_code == 200
        assert artifact.json()["artifact_type"] == "CSR"

    async def test_generate_study_csr(
        self,
        iclient: AsyncClient,
        idb,
        i_study: Study,
        i_org,
        i_admin,
        admin_tok: str,
    ):
        await _tlf_artifact_id(iclient, idb, i_study, i_org, i_admin, admin_tok)
        resp = await iclient.post(
            f"/api/v1/csr/studies/{i_study.id}/generate-csr",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        assert resp.json()["section_count"] >= 9

    async def test_rejects_non_tlf_source(
        self,
        iclient: AsyncClient,
        idb,
        i_study: Study,
        i_org,
        i_admin,
        admin_tok: str,
    ):
        from tests.integration.test_adam_endpoints import _create_sdtm_artifact

        sdtm_id = await _create_sdtm_artifact(
            iclient, idb, i_study, i_org, i_admin, admin_tok
        )
        resp = await iclient.post(
            f"/api/v1/csr/artifacts/{sdtm_id}/generate-csr",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 422
