"""Integration tests for artifact export endpoints."""

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


async def _create_artifact(
    idb: AsyncSession,
    org: Organization,
    study: Study,
    user: User,
    artifact_type: ArtifactType,
    content: dict,
) -> Artifact:
    artifact = Artifact(
        id=uuid4(),
        organization_id=org.id,
        study_id=study.id,
        artifact_type=artifact_type,
        name=f"Export {artifact_type.value}",
        status=ArtifactStatus.DRAFT,
        created_by_id=user.id,
    )
    idb.add(artifact)
    await idb.flush()

    content_hash = hashlib.sha256(
        json.dumps(content, sort_keys=True).encode()
    ).hexdigest()
    version = ArtifactVersion(
        id=uuid4(),
        artifact_id=artifact.id,
        organization_id=org.id,
        version_number=1,
        is_current=True,
        content=content,
        content_hash=content_hash,
        status_at_creation=ArtifactStatus.DRAFT,
        created_by_id=user.id,
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
class TestArtifactExportEndpoints:
    async def test_export_requires_auth(
        self, iclient: AsyncClient, i_artifact: Artifact
    ):
        resp = await iclient.get(
            f"/api/v1/artifacts/{i_artifact.id}/export?format=docx"
        )
        assert resp.status_code == 403

    async def test_protocol_exports_docx_and_audits(
        self,
        iclient: AsyncClient,
        idb: AsyncSession,
        i_org: Organization,
        i_study: Study,
        i_admin: User,
        admin_tok: str,
    ):
        artifact = await _create_artifact(
            idb,
            i_org,
            i_study,
            i_admin,
            ArtifactType.PROTOCOL,
            {"synopsis": {"title": "Integration Protocol", "phase": "II"}},
        )
        resp = await iclient.get(
            f"/api/v1/artifacts/{artifact.id}/export?format=docx",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        assert (
            resp.headers["content-type"]
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        assert resp.content[:2] == b"PK"
        assert "protocol_" in resp.headers.get("content-disposition", "")

        audit = await idb.execute(
            select(AuditLog).where(
                AuditLog.resource_id == artifact.id,
                AuditLog.action == AuditAction.ARTIFACT_EXPORTED,
            )
        )
        assert audit.scalar_one_or_none() is not None

    async def test_icf_exports_pdf(
        self,
        iclient: AsyncClient,
        idb: AsyncSession,
        i_org: Organization,
        i_study: Study,
        i_admin: User,
        admin_tok: str,
    ):
        artifact = await _create_artifact(
            idb,
            i_org,
            i_study,
            i_admin,
            ArtifactType.ICF,
            {"sections": {"introduction": "Consent text"}},
        )
        resp = await iclient.get(
            f"/api/v1/artifacts/{artifact.id}/export?format=pdf",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content.startswith(b"%PDF")

    async def test_sdtm_exports_zip(
        self,
        iclient: AsyncClient,
        idb: AsyncSession,
        i_org: Organization,
        i_study: Study,
        i_admin: User,
        admin_tok: str,
    ):
        artifact = await _create_artifact(
            idb,
            i_org,
            i_study,
            i_admin,
            ArtifactType.SDTM_DATASET,
            {
                "document_type": "SDTM_DATASET",
                "domains": [
                    {
                        "domain": "DM",
                        "observations": [{"USUBJID": "001", "SEX": "M"}],
                    }
                ],
            },
        )
        resp = await iclient.get(
            f"/api/v1/artifacts/{artifact.id}/export?format=zip",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"
        assert len(resp.content) > 100

    async def test_unsupported_format_returns_422(
        self, iclient: AsyncClient, i_artifact: Artifact, admin_tok: str
    ):
        resp = await iclient.get(
            f"/api/v1/artifacts/{i_artifact.id}/export?format=pdf",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["code"] == "EXPORT_NOT_AVAILABLE"
