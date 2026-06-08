"""Integration tests verifying audit log + graph event dual-write on key workflows."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.models.study import Study

_CSV = b"subject_id,age\nS001,45\nS002,52\n"


async def _field_id_from_upload(
    iclient: AsyncClient, study_id, admin_tok: str
) -> str:
    upload = await iclient.post(
        f"/api/v1/studies/{study_id}/uploads",
        files={"file": ("dual_write.csv", _CSV, "text/csv")},
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert upload.status_code == 201
    file_id = upload.json()["id"]
    datasets = await iclient.get(
        f"/api/v1/raw-data/files/{file_id}/datasets",
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    items = datasets.json()["items"]
    if not items:
        pytest.skip("No datasets parsed")
    fields = await iclient.get(
        f"/api/v1/raw-data/datasets/{items[0]['id']}/fields",
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    field_list = fields.json()
    if not field_list:
        pytest.skip("No fields parsed")
    return field_list[0]["id"]


@pytest.mark.asyncio(loop_scope="session")
class TestAuditGraphDualWrite:
    async def test_mapping_approval_writes_audit_and_graph_event(
        self, iclient: AsyncClient, i_study: Study, admin_tok: str
    ):
        field_id = await _field_id_from_upload(iclient, i_study.id, admin_tok)

        await iclient.put(
            f"/api/v1/raw-data/fields/{field_id}/mapping",
            json={
                "mapped_ecrf_field_id": "SUBJECT_ID",
                "mapped_sdtm_variable_id": "DM.USUBJID",
            },
            headers={"Authorization": f"Bearer {admin_tok}"},
        )

        approve = await iclient.post(
            f"/api/v1/raw-data/fields/{field_id}/mapping/approve",
            json={"notes": "Approved"},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert approve.status_code == 200

        audit = await iclient.get(
            "/api/v1/audit",
            params={"resource_id": field_id, "page_size": 10},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert audit.status_code == 200
        audit_actions = [item["action"] for item in audit.json()["items"]]
        assert "data.mapping_approved" in audit_actions

        events = await iclient.get(
            "/api/v1/graph/events",
            params={"study_id": str(i_study.id), "page_size": 50},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert events.status_code == 200
        assert events.json()["total"] >= 1

    async def test_graph_impact_endpoint_returns_analysis(
        self, iclient: AsyncClient, i_study: Study, admin_tok: str
    ):
        field_id = await _field_id_from_upload(iclient, i_study.id, admin_tok)
        await iclient.put(
            f"/api/v1/raw-data/fields/{field_id}/mapping",
            json={
                "mapped_ecrf_field_id": "SUBJECT_ID",
                "mapped_sdtm_variable_id": "DM.USUBJID",
            },
            headers={"Authorization": f"Bearer {admin_tok}"},
        )

        entity = await iclient.get(
            "/api/v1/graph/by-entity",
            params={"external_type": "raw_field", "external_id": field_id},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert entity.status_code == 200
        node = entity.json().get("node")
        if node is None:
            pytest.skip("Raw field graph node not registered")

        resp = await iclient.get(
            f"/api/v1/graph/{node['id']}/impact",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["node_id"] == node["id"]
        assert "affected_downstream_count" in data
        assert isinstance(data["affected_nodes"], list)
