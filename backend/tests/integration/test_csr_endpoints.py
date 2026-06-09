"""Integration tests for CSR generation endpoints."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.models.artifact import Artifact, ArtifactStatus, ArtifactType, ArtifactVersion
from app.models.study import Study


async def _ensure_protocol_and_sap(idb, i_study, i_org, i_admin) -> None:
    """Seed Protocol and SAP artifacts required for CSR gating."""
    for art_type, name, content in (
        (
            ArtifactType.PROTOCOL,
            "Test Protocol",
            {
                "title": "Test Protocol",
                "objectives": {"primary": [{"description": "Primary objective"}]},
                "design": {"summary": "Randomized controlled trial"},
            },
        ),
        (
            ArtifactType.SAP,
            "Test SAP",
            {
                "title": "Test SAP",
                "primary_endpoint": "Change from baseline",
                "analysis_populations": ["ITT"],
            },
        ),
    ):
        artifact = Artifact(
            id=uuid4(),
            organization_id=i_org.id,
            study_id=i_study.id,
            artifact_type=art_type,
            name=name,
            status=ArtifactStatus.DRAFT,
            created_by_id=i_admin.id,
        )
        idb.add(artifact)
        await idb.flush()
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


async def _tlf_artifact_id(
    iclient: AsyncClient,
    idb,
    i_study: Study,
    i_org,
    i_admin,
    admin_tok: str,
) -> str:
    from tests.integration.test_tlf_endpoints import _adam_artifact_id

    await _ensure_protocol_and_sap(idb, i_study, i_org, i_admin)
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
        assert data["protocol_artifact_count"] >= 1
        assert data["sap_artifact_count"] >= 1
        assert data["ready"] is True
        assert any(a["artifact_id"] == tlf_id for a in data["tlf_artifacts"])
        assert any(r["key"] == "sdtm" and r["met"] for r in data.get("requirements", []))

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
