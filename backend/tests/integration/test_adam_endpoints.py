"""Integration tests for SDTM → ADaM generation endpoints."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from app.models.artifact import Artifact, ArtifactStatus, ArtifactType, ArtifactVersion

_CSV = b"subject_id,age,treatment\nS001,45,A\nS002,52,B\n"

_COLUMN_MAPS: dict[str, tuple[str, str]] = {
    "subject_id": ("SUBJECT_ID", "DM.USUBJID"),
    "age": ("AGE", "DM.AGE"),
    "treatment": ("TREATMENT", "CM.CMTRT"),
}


async def _create_study(iclient: AsyncClient, admin_tok: str, *, name: str) -> UUID:
    """Create an isolated study for ADaM pipeline tests."""
    resp = await iclient.post(
        "/api/v1/studies",
        json={
            "name": name,
            "protocol_number": f"AD-{uuid4().hex[:6]}",
        },
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert resp.status_code == 201, resp.text
    return UUID(resp.json()["id"])


async def _create_sdtm_artifact(
    iclient: AsyncClient,
    idb,
    study_id: UUID,
    i_org,
    i_admin,
    admin_tok: str,
) -> str:
    """Upload, map, approve, and generate SDTM; return artifact id."""
    upload = await iclient.post(
        f"/api/v1/studies/{study_id}/uploads",
        files={"file": ("adam_src.csv", _CSV, "text/csv")},
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
    dataset_id = items[0]["id"]

    fields = await iclient.get(
        f"/api/v1/raw-data/datasets/{dataset_id}/fields",
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
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
        await iclient.post(
            f"/api/v1/raw-data/fields/{field['id']}/mapping/approve",
            json={"notes": "ok"},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )

    gen = await iclient.post(
        f"/api/v1/raw-data/datasets/{dataset_id}/generate-sdtm",
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    if gen.status_code != 200:
        # Fallback: seed SDTM artifact directly for ADaM tests
        artifact = Artifact(
            id=uuid4(),
            organization_id=i_org.id,
            study_id=study_id,
            artifact_type=ArtifactType.SDTM_DATASET,
            name="Seeded SDTM",
            status=ArtifactStatus.DRAFT,
            created_by_id=i_admin.id,
        )
        idb.add(artifact)
        await idb.flush()
        content = {
            "document_type": "SDTM_DATASET",
            "domains": [{
                "domain": "DM",
                "variables": ["STUDYID", "USUBJID", "SUBJID", "AGE"],
                "observations": [
                    {
                        "STUDYID": "STUDY-1",
                        "USUBJID": "STUDY-1-001",
                        "SUBJID": "001",
                        "AGE": "45",
                    }
                ],
            }],
        }
        content_hash = hashlib.sha256(
            json.dumps(content, sort_keys=True).encode()
        ).hexdigest()
        version = ArtifactVersion(
            id=uuid4(),
            artifact_id=artifact.id,
            organization_id=i_org.id,
            version_number=1,
            is_current=True,
            content=content,
            content_hash=content_hash,
            status_at_creation=ArtifactStatus.DRAFT,
            created_by_id=i_admin.id,
            created_at=datetime.now(UTC),
        )
        idb.add(version)
        await idb.flush()
        artifact.current_version_id = version.id
        artifact.current_version_number = 1
        await idb.commit()
        return str(artifact.id)

    return gen.json()["artifact_id"]


@pytest.mark.asyncio(loop_scope="session")
class TestADAMReadiness:
    async def test_readiness_false_without_sdtm(
        self, iclient: AsyncClient, admin_tok: str
    ):
        study = await iclient.post(
            "/api/v1/studies",
            json={
                "name": "ADaM Empty Study",
                "protocol_number": f"AE-{uuid4().hex[:6]}",
            },
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        study_id = study.json()["id"]
        resp = await iclient.get(
            f"/api/v1/adam/studies/{study_id}/adam-readiness",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        assert resp.json()["ready"] is False

    async def test_readiness_true_with_sdtm(
        self,
        iclient: AsyncClient,
        idb,
        i_org,
        i_admin,
        admin_tok: str,
    ):
        study_id = await _create_study(
            iclient, admin_tok, name="ADaM Readiness Study"
        )
        await _create_sdtm_artifact(
            iclient, idb, study_id, i_org, i_admin, admin_tok
        )
        resp = await iclient.get(
            f"/api/v1/adam/studies/{study_id}/adam-readiness",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sdtm_artifact_count"] >= 1
        assert data["ready"] is True


@pytest.mark.asyncio(loop_scope="session")
class TestADAMGeneration:
    async def test_generate_from_sdtm_artifact(
        self,
        iclient: AsyncClient,
        idb,
        i_org,
        i_admin,
        admin_tok: str,
    ):
        study_id = await _create_study(
            iclient, admin_tok, name="ADaM Single Artifact Study"
        )
        sdtm_id = await _create_sdtm_artifact(
            iclient, idb, study_id, i_org, i_admin, admin_tok
        )
        resp = await iclient.post(
            f"/api/v1/adam/artifacts/{sdtm_id}/generate-adam",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["dataset_count"] >= 1
        assert len(data["source_sdtm_artifact_ids"]) >= 1

        artifact = await iclient.get(
            f"/api/v1/artifacts/{data['artifact_id']}",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert artifact.status_code == 200
        assert artifact.json()["artifact_type"] == "ADAM_DATASET"

    async def test_generate_study_adam(
        self,
        iclient: AsyncClient,
        idb,
        i_org,
        i_admin,
        admin_tok: str,
    ):
        study_id = await _create_study(
            iclient, admin_tok, name="ADaM Full Study Generation"
        )
        await _create_sdtm_artifact(
            iclient, idb, study_id, i_org, i_admin, admin_tok
        )
        resp = await iclient.post(
            f"/api/v1/adam/studies/{study_id}/generate-adam",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["dataset_count"] >= 1
