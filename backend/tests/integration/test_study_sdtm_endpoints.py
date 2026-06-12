"""Integration tests for study-level SDTM generation and define.xml export."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient

_CSV = b"subject_id,age,treatment\nS001,45,A\nS002,52,B\nS003,38,A\n"

_COLUMN_MAPS: dict[str, tuple[str, str]] = {
    "subject_id": ("SUBJECT_ID", "DM.USUBJID"),
    "age": ("AGE", "DM.AGE"),
    "treatment": ("TREATMENT", "CM.CMTRT"),
}


async def _create_study(iclient: AsyncClient, admin_tok: str, *, name: str) -> str:
    """Create a study isolated from i_study, which accumulates unmapped/unapproved
    uploads from other tests in this module and would fail readiness checks."""
    resp = await iclient.post(
        "/api/v1/studies",
        json={"name": name, "protocol_number": f"SDTM-{uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _approve_all_study_mappings(
    iclient: AsyncClient,
    study_id,
    admin_tok: str,
) -> None:
    """Upload CSV and approve SDTM mappings for every parsed field on the study."""
    upload = await iclient.post(
        f"/api/v1/studies/{study_id}/uploads",
        files={"file": ("sdtm_study.csv", _CSV, "text/csv")},
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert upload.status_code == 201

    uploads = await iclient.get(
        f"/api/v1/studies/{study_id}/uploads",
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert uploads.status_code == 200
    upload_items = uploads.json()["items"]
    if not upload_items:
        pytest.skip("No uploads on study")

    saw_dataset = False
    for upload_item in upload_items:
        file_id = upload_item["id"]
        datasets = await iclient.get(
            f"/api/v1/raw-data/files/{file_id}/datasets",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        items = datasets.json()["items"]
        if not items:
            continue
        saw_dataset = True

        for dataset in items:
            fields = await iclient.get(
                f"/api/v1/raw-data/datasets/{dataset['id']}/fields",
                headers={"Authorization": f"Bearer {admin_tok}"},
            )
            assert fields.status_code == 200
            for field in fields.json():
                col = field["column_name"].lower()
                ecrf, sdtm = _COLUMN_MAPS.get(col, (col.upper(), f"DM.{col.upper()}"))
                await iclient.put(
                    f"/api/v1/raw-data/fields/{field['id']}/mapping",
                    json={
                        "mapped_ecrf_field_id": ecrf,
                        "mapped_sdtm_variable_id": sdtm,
                    },
                    headers={"Authorization": f"Bearer {admin_tok}"},
                )
                approve = await iclient.post(
                    f"/api/v1/raw-data/fields/{field['id']}/mapping/approve",
                    json={"notes": "Approved for SDTM test"},
                    headers={"Authorization": f"Bearer {admin_tok}"},
                )
                assert approve.status_code == 200
                assert approve.json()["mapping_status"] == "APPROVED"

    if not saw_dataset:
        pytest.skip("No datasets parsed")


@pytest.mark.asyncio(loop_scope="session")
class TestStudySDTMReadiness:
    async def test_readiness_false_before_approval(
        self, iclient: AsyncClient, admin_tok: str
    ):
        study_id = await _create_study(
            iclient, admin_tok, name="SDTM Readiness Not Ready Study"
        )
        upload = await iclient.post(
            f"/api/v1/studies/{study_id}/uploads",
            files={"file": ("unmapped.csv", _CSV, "text/csv")},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert upload.status_code == 201

        resp = await iclient.get(
            f"/api/v1/raw-data/studies/{study_id}/sdtm-readiness",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ready"] is False
        assert data["dataset_count"] >= 1

    async def test_readiness_true_when_all_approved(
        self, iclient: AsyncClient, admin_tok: str
    ):
        study_id = await _create_study(
            iclient, admin_tok, name="SDTM Readiness Ready Study"
        )
        await _approve_all_study_mappings(iclient, study_id, admin_tok)

        resp = await iclient.get(
            f"/api/v1/raw-data/studies/{study_id}/sdtm-readiness",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ready"] is True
        assert data["approved_fields"] == data["total_fields"]
        assert data["total_fields"] >= 3


@pytest.mark.asyncio(loop_scope="session")
class TestStudySDTMGeneration:
    async def test_generate_study_sdtm_creates_artifact(
        self, iclient: AsyncClient, admin_tok: str
    ):
        study_id = await _create_study(iclient, admin_tok, name="SDTM Generation Study")
        await _approve_all_study_mappings(iclient, study_id, admin_tok)

        resp = await iclient.post(
            f"/api/v1/raw-data/studies/{study_id}/generate-sdtm",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "artifact_id" in data
        assert "validation_run_id" in data
        assert data["domain_count"] >= 1
        assert len(data["source_dataset_ids"]) >= 1

        artifact = await iclient.get(
            f"/api/v1/artifacts/{data['artifact_id']}",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert artifact.status_code == 200
        assert artifact.json()["artifact_type"] == "SDTM_DATASET"

    async def test_generate_when_not_ready_returns_422(
        self, iclient: AsyncClient, admin_tok: str
    ):
        study = await iclient.post(
            "/api/v1/studies",
            json={
                "name": "SDTM Not Ready Study",
                "protocol_number": f"NR-{uuid4().hex[:6]}",
            },
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert study.status_code == 201
        study_id = study.json()["id"]

        upload = await iclient.post(
            f"/api/v1/studies/{study_id}/uploads",
            files={"file": ("pending.csv", _CSV, "text/csv")},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert upload.status_code == 201

        resp = await iclient.post(
            f"/api/v1/raw-data/studies/{study_id}/generate-sdtm",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
class TestDefineXmlExport:
    async def test_export_define_xml_for_sdtm_artifact(
        self, iclient: AsyncClient, admin_tok: str
    ):
        study_id = await _create_study(
            iclient, admin_tok, name="SDTM Define XML Export Study"
        )
        await _approve_all_study_mappings(iclient, study_id, admin_tok)
        gen = await iclient.post(
            f"/api/v1/raw-data/studies/{study_id}/generate-sdtm",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert gen.status_code == 200
        artifact_id = gen.json()["artifact_id"]

        resp = await iclient.get(
            f"/api/v1/artifacts/{artifact_id}/define-xml",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        assert "application/xml" in resp.headers.get("content-type", "")
        body = resp.text
        assert "Define" in body
        assert "DM" in body
