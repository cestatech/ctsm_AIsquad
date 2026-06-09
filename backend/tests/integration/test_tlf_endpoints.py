"""Integration tests for TLF generation endpoints."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import Artifact, ArtifactStatus, ArtifactType, ArtifactVersion
from app.models.audit import AuditAction, AuditLog
from app.models.organization import Organization
from app.models.study import Study
from app.models.user import User


def _content_hash(content: dict) -> str:
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


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


async def _create_tlf_artifact(
    idb: AsyncSession,
    i_study: Study,
    i_org: Organization,
    i_admin: User,
) -> Artifact:
    content = {
        "document_type": "TLF_SPECIFICATION",
        "tables": [{
            "title": "Demographics",
            "columns": [{"key": "parameter", "label": "Parameter"}],
            "rows": [{"parameter": "Age"}],
        }],
    }
    artifact = Artifact(
        id=uuid4(),
        organization_id=i_org.id,
        study_id=i_study.id,
        artifact_type=ArtifactType.TLF,
        name="CSR TLF Package",
        status=ArtifactStatus.APPROVED,
        created_by_id=i_admin.id,
    )
    idb.add(artifact)
    await idb.flush()

    version = ArtifactVersion(
        id=uuid4(),
        artifact_id=artifact.id,
        organization_id=i_org.id,
        version_number=1,
        is_current=True,
        content=content,
        content_hash=_content_hash(content),
        status_at_creation=ArtifactStatus.APPROVED,
        created_by_id=i_admin.id,
        created_at=datetime.now(UTC),
    )
    idb.add(version)
    await idb.flush()
    artifact.current_version_id = version.id
    artifact.current_version_number = 1
    await idb.commit()
    await idb.refresh(artifact)
    return artifact


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

        edges = await iclient.get(
            "/api/v1/graph/edges",
            params={"study_id": str(i_study.id)},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert edges.status_code == 200
        edge_types = {item["edge_type"] for item in edges.json()["items"]}
        assert "ADAM_TO_TLF" in edge_types
        assert "SDTM_TO_ADAM" in edge_types

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

    async def test_render_tlf_artifact_downloads_rtf_and_audits(
        self,
        iclient: AsyncClient,
        idb: AsyncSession,
        i_study: Study,
        i_org: Organization,
        i_admin: User,
        admin_tok: str,
    ):
        artifact = await _create_tlf_artifact(idb, i_study, i_org, i_admin)

        resp = await iclient.post(
            f"/api/v1/tlf/artifacts/{artifact.id}/render",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/rtf"
        assert 'filename="CSR_TLF_Package.rtf"' in resp.headers["content-disposition"]
        assert resp.content.startswith(b"{\\rtf1")
        assert b"Demographics" in resp.content

        audit_result = await idb.execute(
            select(AuditLog).where(
                AuditLog.resource_id == artifact.id,
                AuditLog.action == AuditAction.ARTIFACT_EXPORTED,
            )
        )
        assert audit_result.scalar_one_or_none() is not None

    async def test_render_tlf_artifact_invalid_token_returns_401(
        self,
        iclient: AsyncClient,
    ):
        resp = await iclient.post(
            f"/api/v1/tlf/artifacts/{uuid4()}/render",
            headers={"Authorization": "Bearer not.a.real.token"},
        )
        assert resp.status_code == 401
