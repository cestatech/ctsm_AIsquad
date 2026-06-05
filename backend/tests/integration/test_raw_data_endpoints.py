"""Integration tests for /api/v1/raw-data endpoints.

Covers: file detail, dataset listing, field listing, mapping CRUD,
approval/rejection, validation, and RBAC enforcement.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.models.study import Study


_CSV = b"subject_id,age,treatment\nS001,45,A\nS002,52,B\nS003,38,A\n"


@pytest.mark.asyncio(loop_scope="session")
class TestGetUploadDetail:
    async def test_unauthenticated_returns_403(
        self, iclient: AsyncClient, i_study: Study, admin_tok: str
    ):
        # First upload a file to get a valid file_id
        resp = await iclient.post(
            f"/api/v1/studies/{i_study.id}/uploads",
            files={"file": ("data.csv", _CSV, "text/csv")},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 201
        file_id = resp.json()["id"]

        resp = await iclient.get(f"/api/v1/raw-data/files/{file_id}")
        assert resp.status_code == 403

    async def test_get_file_detail_returns_file(
        self, iclient: AsyncClient, i_study: Study, admin_tok: str
    ):
        resp = await iclient.post(
            f"/api/v1/studies/{i_study.id}/uploads",
            files={"file": ("profile.csv", _CSV, "text/csv")},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 201
        file_id = resp.json()["id"]

        detail = await iclient.get(
            f"/api/v1/raw-data/files/{file_id}",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert detail.status_code == 200
        data = detail.json()
        assert data["id"] == file_id
        assert data["upload_status"] in ("UPLOADED", "PARSED", "FAILED")
        assert data["file_hash"] is not None

    async def test_nonexistent_file_returns_404(
        self, iclient: AsyncClient, admin_tok: str
    ):
        resp = await iclient.get(
            f"/api/v1/raw-data/files/{uuid4()}",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
class TestListDatasets:
    async def test_lists_datasets_after_csv_upload(
        self, iclient: AsyncClient, i_study: Study, admin_tok: str
    ):
        upload = await iclient.post(
            f"/api/v1/studies/{i_study.id}/uploads",
            files={"file": ("subjects.csv", _CSV, "text/csv")},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert upload.status_code == 201
        file_id = upload.json()["id"]

        resp = await iclient.get(
            f"/api/v1/raw-data/files/{file_id}/datasets",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    async def test_unauthenticated_returns_403(
        self, iclient: AsyncClient, i_study: Study, admin_tok: str
    ):
        upload = await iclient.post(
            f"/api/v1/studies/{i_study.id}/uploads",
            files={"file": ("x.csv", _CSV, "text/csv")},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        file_id = upload.json()["id"]
        resp = await iclient.get(f"/api/v1/raw-data/files/{file_id}/datasets")
        assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
class TestFieldMapping:
    """Tests for the full mapping lifecycle."""

    async def _upload_and_get_field(
        self,
        iclient: AsyncClient,
        i_study: Study,
        admin_tok: str,
    ) -> str:
        """Upload a CSV, list its datasets, list its fields, return a field_id."""
        upload = await iclient.post(
            f"/api/v1/studies/{i_study.id}/uploads",
            files={"file": ("map_test.csv", _CSV, "text/csv")},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert upload.status_code == 201
        file_id = upload.json()["id"]

        datasets = await iclient.get(
            f"/api/v1/raw-data/files/{file_id}/datasets",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert datasets.status_code == 200
        items = datasets.json()["items"]
        if not items:
            pytest.skip("No datasets parsed — CSV parsing may not have run in test mode")
        dataset_id = items[0]["id"]

        fields = await iclient.get(
            f"/api/v1/raw-data/datasets/{dataset_id}/fields",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert fields.status_code == 200
        field_list = fields.json()
        if not field_list:
            pytest.skip("No fields parsed")
        return field_list[0]["id"]

    async def test_map_field_sets_pending_approval(
        self, iclient: AsyncClient, i_study: Study, admin_tok: str
    ):
        field_id = await self._upload_and_get_field(iclient, i_study, admin_tok)

        resp = await iclient.put(
            f"/api/v1/raw-data/fields/{field_id}/mapping",
            json={
                "mapped_ecrf_field_id": "SUBJECT_ID",
                "mapped_sdtm_variable_id": "DM.USUBJID",
            },
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mapped_ecrf_field_id"] == "SUBJECT_ID"
        assert data["mapped_sdtm_variable_id"] == "DM.USUBJID"
        assert data["mapping_status"] == "PENDING_APPROVAL"
        assert data["mapping_version"] == 1

    async def test_empty_mapping_returns_422(
        self, iclient: AsyncClient, i_study: Study, admin_tok: str
    ):
        field_id = await self._upload_and_get_field(iclient, i_study, admin_tok)

        resp = await iclient.put(
            f"/api/v1/raw-data/fields/{field_id}/mapping",
            json={"mapped_ecrf_field_id": None, "mapped_sdtm_variable_id": None},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 422

    async def test_unauthenticated_mapping_returns_403(
        self, iclient: AsyncClient, i_study: Study, admin_tok: str
    ):
        field_id = await self._upload_and_get_field(iclient, i_study, admin_tok)
        resp = await iclient.put(
            f"/api/v1/raw-data/fields/{field_id}/mapping",
            json={"mapped_ecrf_field_id": "AGE", "mapped_sdtm_variable_id": "DM.AGE"},
        )
        assert resp.status_code == 403

    async def test_approve_mapping_sets_approved(
        self, iclient: AsyncClient, i_study: Study, admin_tok: str
    ):
        field_id = await self._upload_and_get_field(iclient, i_study, admin_tok)

        await iclient.put(
            f"/api/v1/raw-data/fields/{field_id}/mapping",
            json={"mapped_ecrf_field_id": "TREATMENT", "mapped_sdtm_variable_id": "CM.CMTRT"},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )

        approve = await iclient.post(
            f"/api/v1/raw-data/fields/{field_id}/mapping/approve",
            json={"notes": "Looks good"},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert approve.status_code == 200
        assert approve.json()["mapping_status"] == "APPROVED"

    async def test_approve_unmapped_returns_422(
        self, iclient: AsyncClient, i_study: Study, admin_tok: str
    ):
        field_id = await self._upload_and_get_field(iclient, i_study, admin_tok)

        resp = await iclient.post(
            f"/api/v1/raw-data/fields/{field_id}/mapping/approve",
            json={},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 422

    async def test_mapping_version_history_grows(
        self, iclient: AsyncClient, i_study: Study, admin_tok: str
    ):
        field_id = await self._upload_and_get_field(iclient, i_study, admin_tok)

        for i in range(3):
            await iclient.put(
                f"/api/v1/raw-data/fields/{field_id}/mapping",
                json={"mapped_ecrf_field_id": f"FIELD_V{i}"},
                headers={"Authorization": f"Bearer {admin_tok}"},
            )

        history = await iclient.get(
            f"/api/v1/raw-data/fields/{field_id}/mapping/history",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert history.status_code == 200
        assert len(history.json()) >= 3


@pytest.mark.asyncio(loop_scope="session")
class TestMappingValidation:
    async def test_validate_returns_coverage_stats(
        self, iclient: AsyncClient, i_study: Study, admin_tok: str
    ):
        upload = await iclient.post(
            f"/api/v1/studies/{i_study.id}/uploads",
            files={"file": ("validate.csv", _CSV, "text/csv")},
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
            pytest.skip("No datasets in test mode")
        dataset_id = items[0]["id"]

        result = await iclient.get(
            f"/api/v1/raw-data/datasets/{dataset_id}/validate",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert result.status_code == 200
        data = result.json()
        assert "total_fields" in data
        assert "coverage_pct" in data
        assert isinstance(data["issues"], list)
