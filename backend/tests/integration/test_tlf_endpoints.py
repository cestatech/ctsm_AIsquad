"""Integration tests for TLF generation endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.models.study import Study


async def _adam_artifact_id(
    iclient: AsyncClient,
    idb,
    i_study: Study,
    i_org,
    i_admin,
    admin_tok: str,
) -> str:
    from tests.integration.test_adam_endpoints import _create_sdtm_artifact

    sdtm_id = await _create_sdtm_artifact(
        iclient, idb, i_study, i_org, i_admin, admin_tok
    )
    gen = await iclient.post(
        f"/api/v1/adam/artifacts/{sdtm_id}/generate-adam",
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert gen.status_code == 200
    return gen.json()["artifact_id"]


@pytest.mark.asyncio(loop_scope="session")
class TestTLFEndpoints:
    async def test_generate_tlf_from_adam(
        self,
        iclient: AsyncClient,
        idb,
        i_study: Study,
        i_org,
        i_admin,
        admin_tok: str,
    ):
        adam_id = await _adam_artifact_id(
            iclient, idb, i_study, i_org, i_admin, admin_tok
        )
        resp = await iclient.post(
            f"/api/v1/tlf/artifacts/{adam_id}/generate-tlf",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["table_count"] >= 1
        assert data["artifact_id"]
        assert str(adam_id) in [str(x) for x in data["source_adam_artifact_ids"]]

        artifact = await iclient.get(
            f"/api/v1/artifacts/{data['artifact_id']}",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert artifact.status_code == 200
        assert artifact.json()["artifact_type"] == "TLF"

        qc = await iclient.get(
            "/api/v1/statistical-qc/runs",
            params={"output_artifact_id": data["artifact_id"]},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert qc.status_code == 200
        assert qc.json()["total"] >= 1
        assert qc.json()["items"][0]["workflow_step"] == "ADAM_TO_TLF"

    async def test_rejects_non_adam_source(
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
            f"/api/v1/tlf/artifacts/{sdtm_id}/generate-tlf",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 422
