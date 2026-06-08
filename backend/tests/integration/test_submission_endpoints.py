"""Integration tests for submission packaging endpoints."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import Artifact, ArtifactStatus, ArtifactType, ArtifactVersion
from app.services.submission_executor import execute_submission_assembly
from app.models.organization import Organization
from app.models.study import Study
from app.models.user import User


def _content_hash(content: dict) -> str:
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


async def _seed_approved_pipeline_artifacts(
    idb: AsyncSession,
    i_org: Organization,
    i_study: Study,
    i_admin: User,
) -> list[Artifact]:
    """Create APPROVED SDTM, ADaM, TLF, CSR artifacts for submission tests."""
    specs: list[tuple[ArtifactType, str, dict]] = [
        (
            ArtifactType.SDTM_DATASET,
            "SDTM Package",
            {
                "document_type": "SDTM_DATASET",
                "protocol_number": i_study.protocol_number,
                "domains": [{
                    "domain": "DM",
                    "domain_label": "Demographics",
                    "class": "Special-Purpose",
                    "variables": ["STUDYID", "USUBJID"],
                    "observations": [{"STUDYID": "S1", "USUBJID": "S1-001"}],
                }],
            },
        ),
        (
            ArtifactType.ADAM_DATASET,
            "ADaM Package",
            {
                "datasets": [{
                    "dataset": "ADSL",
                    "variables": [{"variable": "USUBJID"}],
                    "observations": [],
                }],
            },
        ),
        (
            ArtifactType.TLF,
            "TLF Package",
            {"tables": [{"table_id": "T-01", "title": "Demographics"}]},
        ),
        (
            ArtifactType.CSR,
            "CSR Document",
            {"title": "CSR", "sections": [{"number": "1", "title": "Title Page"}]},
        ),
    ]

    created: list[Artifact] = []
    for art_type, name, content in specs:
        artifact = Artifact(
            id=uuid4(),
            organization_id=i_org.id,
            study_id=i_study.id,
            artifact_type=art_type,
            name=name,
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
            status_at_creation=ArtifactStatus.APPROVED,
            content=content,
            content_hash=_content_hash(content),
            created_by_id=i_admin.id,
            created_at=datetime.now(UTC),
            change_summary="Submission test seed",
        )
        idb.add(version)
        await idb.flush()
        artifact.current_version_id = version.id
        artifact.current_version_number = 1
        created.append(artifact)

    await idb.flush()
    return created


async def _await_package_assembly(package_id: str, org_id: UUID) -> None:
    """Run assembly synchronously in tests (background tasks are async-unreliable)."""
    await execute_submission_assembly(UUID(package_id), org_id)


@pytest.mark.asyncio(loop_scope="session")
class TestSubmissionEndpoints:
    async def test_readiness_not_ready_without_approved(
        self,
        iclient: AsyncClient,
        i_study: Study,
        admin_tok: str,
    ):
        resp = await iclient.get(
            f"/api/v1/submissions/studies/{i_study.id}/readiness",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        assert resp.json()["ready"] is False
        assert resp.json()["issues"]

    async def test_create_rejects_when_not_ready(
        self,
        iclient: AsyncClient,
        i_study: Study,
        admin_tok: str,
    ):
        resp = await iclient.post(
            f"/api/v1/submissions/studies/{i_study.id}/create",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["code"] == "SUBMISSION_NOT_READY"

    async def test_full_submission_flow(
        self,
        iclient: AsyncClient,
        idb: AsyncSession,
        i_study: Study,
        i_org: Organization,
        i_admin: User,
        admin_tok: str,
    ):
        await _seed_approved_pipeline_artifacts(idb, i_org, i_study, i_admin)
        await idb.commit()

        readiness = await iclient.get(
            f"/api/v1/submissions/studies/{i_study.id}/readiness",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert readiness.status_code == 200
        assert readiness.json()["ready"] is True

        create = await iclient.post(
            f"/api/v1/submissions/studies/{i_study.id}/create",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert create.status_code == 200
        package_id = create.json()["package_id"]
        assert create.json()["status"] == "DRAFT"
        await _await_package_assembly(package_id, i_org.id)

        manifest = await iclient.get(
            f"/api/v1/submissions/{package_id}/manifest",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert manifest.status_code == 200
        data = manifest.json()
        assert data["status"] == "READY"
        assert data["manifest"]["files"]
        assert data["package_checksum"]
        assert any(f["sha256"] for f in data["manifest"]["files"])

        download = await iclient.get(
            f"/api/v1/submissions/{package_id}/download",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert download.status_code == 200
        assert download.headers["content-type"] == "application/zip"
        assert len(download.content) > 100

        listing = await iclient.get(
            f"/api/v1/submissions/studies/{i_study.id}",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert listing.status_code == 200
        assert listing.json()["total"] >= 1

    async def test_contributor_cannot_create_or_download(
        self,
        iclient: AsyncClient,
        idb: AsyncSession,
        i_study: Study,
        i_org: Organization,
        i_admin: User,
        contributor_tok: str,
        admin_tok: str,
    ):
        await _seed_approved_pipeline_artifacts(idb, i_org, i_study, i_admin)
        await idb.commit()

        create = await iclient.post(
            f"/api/v1/submissions/studies/{i_study.id}/create",
            headers={"Authorization": f"Bearer {contributor_tok}"},
        )
        assert create.status_code == 403

        admin_create = await iclient.post(
            f"/api/v1/submissions/studies/{i_study.id}/create",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert admin_create.status_code == 200
        package_id = admin_create.json()["package_id"]
        await _await_package_assembly(package_id, i_org.id)

        download = await iclient.get(
            f"/api/v1/submissions/{package_id}/download",
            headers={"Authorization": f"Bearer {contributor_tok}"},
        )
        assert download.status_code == 403

    async def test_reviewer_can_view_manifest_not_download(
        self,
        iclient: AsyncClient,
        idb: AsyncSession,
        i_study: Study,
        i_org: Organization,
        i_admin: User,
        reviewer_tok: str,
        admin_tok: str,
    ):
        await _seed_approved_pipeline_artifacts(idb, i_org, i_study, i_admin)
        await idb.commit()

        create = await iclient.post(
            f"/api/v1/submissions/studies/{i_study.id}/create",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert create.status_code == 200
        package_id = create.json()["package_id"]
        await _await_package_assembly(package_id, i_org.id)

        manifest = await iclient.get(
            f"/api/v1/submissions/{package_id}/manifest",
            headers={"Authorization": f"Bearer {reviewer_tok}"},
        )
        assert manifest.status_code == 200

        download = await iclient.get(
            f"/api/v1/submissions/{package_id}/download",
            headers={"Authorization": f"Bearer {reviewer_tok}"},
        )
        assert download.status_code == 403
