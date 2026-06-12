"""Unit tests for submission packaging service."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.artifact import ArtifactStatus, ArtifactType
from app.models.submission import SubmissionPackageStatus
from app.services.storage.filesystem import FilesystemStorageBackend
from app.services.storage_service import StorageService
from app.services.submission_service import SubmissionService


def _artifact(
    artifact_type: ArtifactType, status: ArtifactStatus = ArtifactStatus.DRAFT
):
    art = MagicMock()
    art.id = uuid4()
    art.artifact_type = artifact_type
    art.status = status
    art.name = f"{artifact_type.value} artifact"
    art.current_version_id = uuid4()
    art.updated_at = None
    art.created_at = None
    art.study_id = uuid4()
    return art


@pytest.mark.asyncio
class TestSubmissionReadiness:
    async def test_readiness_fails_without_approved_artifacts(self):
        db = AsyncMock()
        svc = SubmissionService(db)
        study_id = uuid4()
        org_id = uuid4()

        svc._study_repo.get = AsyncMock()
        svc._artifact_repo.list_by_study = AsyncMock(return_value=([], 0))

        pending_result = MagicMock()
        pending_result.scalars.return_value.all.return_value = []
        fail_result = MagicMock()
        fail_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(side_effect=[pending_result, fail_result])

        readiness = await svc.get_readiness(study_id, org_id)
        assert readiness.ready is False
        assert any("Missing approved" in i for i in readiness.issues)

    async def test_readiness_passes_with_all_approved(self):
        db = AsyncMock()
        svc = SubmissionService(db)
        study_id = uuid4()
        org_id = uuid4()

        artifacts = [
            _artifact(ArtifactType.SDTM_DATASET, ArtifactStatus.APPROVED),
            _artifact(ArtifactType.ADAM_DATASET, ArtifactStatus.APPROVED),
            _artifact(ArtifactType.TLF, ArtifactStatus.APPROVED),
            _artifact(ArtifactType.CSR, ArtifactStatus.APPROVED),
        ]
        svc._study_repo.get = AsyncMock()
        svc._artifact_repo.list_by_study = AsyncMock(return_value=(artifacts, 4))

        pending_result = MagicMock()
        pending_result.scalars.return_value.all.return_value = []
        fail_result = MagicMock()
        fail_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(side_effect=[pending_result, fail_result])

        readiness = await svc.get_readiness(study_id, org_id)
        assert readiness.ready is True
        assert readiness.issues == []

    async def test_readiness_passes_with_locked_artifacts(self):
        db = AsyncMock()
        svc = SubmissionService(db)
        study_id = uuid4()
        org_id = uuid4()

        artifacts = [
            _artifact(ArtifactType.SDTM_DATASET, ArtifactStatus.LOCKED),
            _artifact(ArtifactType.ADAM_DATASET, ArtifactStatus.LOCKED),
            _artifact(ArtifactType.TLF, ArtifactStatus.LOCKED),
            _artifact(ArtifactType.CSR, ArtifactStatus.LOCKED),
        ]
        svc._study_repo.get = AsyncMock()
        svc._artifact_repo.list_by_study = AsyncMock(return_value=(artifacts, 4))

        pending_result = MagicMock()
        pending_result.scalars.return_value.all.return_value = []
        fail_result = MagicMock()
        fail_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(side_effect=[pending_result, fail_result])

        readiness = await svc.get_readiness(study_id, org_id)
        assert readiness.ready is True


@pytest.mark.asyncio
class TestManifestGeneration:
    async def test_assemble_writes_manifest_with_checksums(self, tmp_path):
        db = AsyncMock()
        storage = StorageService(FilesystemStorageBackend(tmp_path))
        svc = SubmissionService(db, storage=storage)
        org_id = uuid4()
        study_id = uuid4()
        package = MagicMock()
        package.id = uuid4()
        package.study_id = study_id
        package.artifact_ids = []

        sdtm = _artifact(ArtifactType.SDTM_DATASET, ArtifactStatus.APPROVED)
        adam = _artifact(ArtifactType.ADAM_DATASET, ArtifactStatus.APPROVED)
        tlf = _artifact(ArtifactType.TLF, ArtifactStatus.APPROVED)
        csr = _artifact(ArtifactType.CSR, ArtifactStatus.APPROVED)
        artifacts = [sdtm, adam, tlf, csr]

        study = MagicMock()
        study.name = "Test Study"
        study.protocol_number = "PROT-001"
        svc._study_repo.get = AsyncMock(return_value=study)

        sdtm_content = {
            "document_type": "SDTM_DATASET",
            "protocol_number": "PROT-001",
            "domains": [
                {
                    "domain": "DM",
                    "domain_label": "Demographics",
                    "class": "Special-Purpose",
                    "variables": ["STUDYID", "USUBJID"],
                    "observations": [{"STUDYID": "S1", "USUBJID": "S1-001"}],
                }
            ],
        }
        adam_content = {
            "datasets": [
                {
                    "dataset": "ADSL",
                    "variables": [{"variable": "USUBJID"}],
                    "observations": [],
                }
            ],
        }
        tlf_content = {"tables": [{"table_id": "T-01", "title": "Demographics"}]}
        csr_content = {"title": "CSR", "sections": [{"number": "1"}]}

        async def _load(art):
            return {
                sdtm.id: sdtm_content,
                adam.id: adam_content,
                tlf.id: tlf_content,
                csr.id: csr_content,
            }[art.id]

        svc._load_artifact_content = _load

        manifest, local_path, checksum = await svc._assemble_package(
            package=package,
            artifacts=artifacts,
            organization_id=org_id,
        )

        assert checksum
        assert manifest["study_name"] == "Test Study"
        assert manifest["data_classification"] == "SYNTHETIC_DEMO"
        assert any(f["path"] == "manifest.json" for f in manifest["files"])
        assert any(f["path"] == "m5/define.xml" for f in manifest["files"])
        define_entry = next(
            f for f in manifest["files"] if f["path"] == "m5/define.xml"
        )
        assert define_entry["grade"] == "generated"
        reviewers_entry = next(
            f for f in manifest["files"] if f["path"] == "m5/reviewers-guide.pdf"
        )
        assert reviewers_entry["grade"] == "placeholder"
        csr_entries = [f for f in manifest["files"] if f["path"].startswith("csr/")]
        assert csr_entries and csr_entries[0]["grade"] == "placeholder"
        tlf_entries = [f for f in manifest["files"] if f["path"].startswith("tlf/")]
        assert tlf_entries and tlf_entries[0]["grade"] == "generated"
        assert storage.exists(f"{local_path}/manifest.json")
        loaded = json.loads(storage.get(f"{local_path}/manifest.json").decode())
        assert loaded["package_id"] == str(package.id)


@pytest.mark.asyncio
class TestAssembleSubmissionPackage:
    async def test_assemble_transitions_to_ready(self, tmp_path):
        db = AsyncMock()
        storage = StorageService(FilesystemStorageBackend(tmp_path))
        svc = SubmissionService(db, storage=storage)
        org_id = uuid4()
        study_id = uuid4()
        user_id = uuid4()
        package = MagicMock()
        package.id = uuid4()
        package.study_id = study_id
        package.organization_id = org_id
        package.created_by_id = user_id
        package.artifact_ids = []
        package.status = SubmissionPackageStatus.DRAFT
        package.error_message = None
        package.local_path = None
        package.manifest = {}
        package.package_checksum = None

        sdtm = _artifact(ArtifactType.SDTM_DATASET, ArtifactStatus.APPROVED)
        package.artifact_ids = [str(sdtm.id)]

        svc._submission_repo.get_by_id = AsyncMock(return_value=package)
        svc._submission_repo.update = AsyncMock()
        svc._artifact_repo.get_by_id = AsyncMock(return_value=sdtm)
        svc._log_status_change = AsyncMock()
        svc._assemble_package = AsyncMock(
            return_value=({"files": []}, str(tmp_path / "pkg"), "abc123")
        )
        svc._register_graph_links = AsyncMock()

        actor = MagicMock()
        actor.id = user_id
        actor.organization_id = org_id
        svc._db = db
        user_repo = MagicMock()
        user_repo.get_by_id = AsyncMock(return_value=actor)
        with patch(
            "app.services.submission_service.UserRepository",
            return_value=user_repo,
        ):
            result = await svc.assemble_submission_package(package.id, org_id)

        assert result.status == SubmissionPackageStatus.READY
        assert svc._log_status_change.await_count >= 2


@pytest.mark.asyncio
class TestCreateSubmissionPackage:
    async def test_create_raises_when_not_ready(self):
        db = AsyncMock()
        svc = SubmissionService(db)
        actor = MagicMock()
        actor.id = uuid4()
        actor.organization_id = uuid4()

        svc._study_repo.get = AsyncMock()
        svc._collect_readiness_issues = AsyncMock(
            return_value=["Missing approved SDTM_DATASET artifact."]
        )

        with (
            patch(
                "app.services.submission_service.require_admin",
                return_value=None,
            ),
            pytest.raises(HTTPException) as exc,
        ):
            await svc.create_submission_package(uuid4(), actor)

        assert exc.value.status_code == 422
        assert exc.value.detail["code"] == "SUBMISSION_NOT_READY"
