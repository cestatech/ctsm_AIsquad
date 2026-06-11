"""Integration tests for bulk mapping approve/reject and CSV export."""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.audit import AuditAction, AuditLog
from app.models.study import Study

_CSV = b"subject_id,age,treatment\nS001,45,A\nS002,52,B\n"


async def _upload_dataset_id(
    iclient: AsyncClient, study_id, admin_tok: str
) -> str:
    upload = await iclient.post(
        f"/api/v1/studies/{study_id}/uploads",
        files={"file": ("bulk_map.csv", _CSV, "text/csv")},
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
    return items[0]["id"]


@pytest.mark.asyncio(loop_scope="session")
class TestBulkApproveMappings:
    async def test_bulk_approve_pending_mappings(
        self, iclient: AsyncClient, i_study: Study, admin_tok: str
    ):
        dataset_id = await _upload_dataset_id(iclient, i_study.id, admin_tok)
        fields = await iclient.get(
            f"/api/v1/raw-data/datasets/{dataset_id}/fields",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert fields.status_code == 200
        for field in fields.json():
            await iclient.put(
                f"/api/v1/raw-data/fields/{field['id']}/mapping",
                json={
                    "mapped_ecrf_field_id": field["column_name"].upper(),
                    "mapped_sdtm_variable_id": f"DM.{field['column_name'].upper()}",
                },
                headers={"Authorization": f"Bearer {admin_tok}"},
            )

        resp = await iclient.post(
            f"/api/v1/raw-data/datasets/{dataset_id}/mapping/bulk-approve",
            json={"notes": "Bulk approved in test"},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["approved_count"] >= 1
        assert all(f["mapping_status"] == "APPROVED" for f in data["fields"])

    async def test_contributor_cannot_bulk_approve(
        self,
        iclient: AsyncClient,
        i_study: Study,
        admin_tok: str,
        contributor_tok: str,
    ):
        dataset_id = await _upload_dataset_id(iclient, i_study.id, admin_tok)
        resp = await iclient.post(
            f"/api/v1/raw-data/datasets/{dataset_id}/mapping/bulk-approve",
            json={},
            headers={"Authorization": f"Bearer {contributor_tok}"},
        )
        assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
class TestBulkRejectMappings:
    async def _pending_field_ids(
        self, iclient: AsyncClient, study_id, admin_tok: str, count: int = 3
    ) -> tuple[str, list[str]]:
        dataset_id = await _upload_dataset_id(iclient, study_id, admin_tok)
        fields = await iclient.get(
            f"/api/v1/raw-data/datasets/{dataset_id}/fields",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert fields.status_code == 200
        field_list = fields.json()[:count]
        for field in field_list:
            await iclient.put(
                f"/api/v1/raw-data/fields/{field['id']}/mapping",
                json={
                    "mapped_ecrf_field_id": field["column_name"].upper(),
                    "mapped_sdtm_variable_id": f"DM.{field['column_name'].upper()}",
                },
                headers={"Authorization": f"Bearer {admin_tok}"},
            )
        return dataset_id, [field["id"] for field in field_list]

    async def test_bulk_reject_pending_mappings(
        self, iclient: AsyncClient, i_study: Study, admin_tok: str, idb
    ):
        dataset_id, mapping_ids = await self._pending_field_ids(
            iclient, i_study.id, admin_tok
        )

        resp = await iclient.post(
            f"/api/v1/raw-data/datasets/{dataset_id}/mapping/bulk-reject",
            json={
                "mapping_ids": mapping_ids,
                "reason": "Incorrect AI suggestions for test dataset",
            },
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["rejected"] == 3
        assert data["failed"] == 0

        fields = await iclient.get(
            f"/api/v1/raw-data/datasets/{dataset_id}/fields",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        rejected_fields = [
            f for f in fields.json() if f["id"] in mapping_ids
        ]
        assert all(f["mapping_status"] == "REJECTED" for f in rejected_fields)

        mapping_uuids = [UUID(field_id) for field_id in mapping_ids]
        audit_rows = await idb.execute(
            select(AuditLog).where(
                AuditLog.action == AuditAction.DATA_MAPPING_REJECTED,
                AuditLog.resource_id.in_(mapping_uuids),
            )
        )
        assert len(audit_rows.scalars().all()) == 3

    async def test_empty_reason_returns_422(
        self, iclient: AsyncClient, i_study: Study, admin_tok: str
    ):
        dataset_id, mapping_ids = await self._pending_field_ids(
            iclient, i_study.id, admin_tok, count=1
        )
        resp = await iclient.post(
            f"/api/v1/raw-data/datasets/{dataset_id}/mapping/bulk-reject",
            json={"mapping_ids": mapping_ids, "reason": "short"},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 422

    async def test_reviewer_cannot_bulk_reject(
        self,
        iclient: AsyncClient,
        i_study: Study,
        admin_tok: str,
        reviewer_tok: str,
    ):
        dataset_id, mapping_ids = await self._pending_field_ids(
            iclient, i_study.id, admin_tok, count=1
        )
        resp = await iclient.post(
            f"/api/v1/raw-data/datasets/{dataset_id}/mapping/bulk-reject",
            json={
                "mapping_ids": mapping_ids,
                "reason": "Reviewer should not be allowed to bulk reject",
            },
            headers={"Authorization": f"Bearer {reviewer_tok}"},
        )
        assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
class TestMappingExport:
    async def test_export_mappings_csv(
        self, iclient: AsyncClient, i_study: Study, admin_tok: str
    ):
        dataset_id = await _upload_dataset_id(iclient, i_study.id, admin_tok)
        resp = await iclient.get(
            f"/api/v1/raw-data/datasets/{dataset_id}/mapping/export",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")
        body = resp.text
        assert "column_name" in body
        assert "mapping_status" in body
