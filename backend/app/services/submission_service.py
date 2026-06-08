"""Submission packaging service — assemble eCTD Module 5 regulatory bundles."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.permissions import Permission, check_permission, require_admin
from app.models.artifact import Artifact, ArtifactStatus, ArtifactType
from app.models.audit import AuditAction
from app.models.graph import GraphEdgeType, GraphNodeType
from app.models.intelligence import AIDecision, AIDecisionStatus, ValidationEvidence
from app.models.intelligence import ValidationEvidenceStatus
from app.models.submission import SubmissionPackage, SubmissionPackageStatus
from app.models.user import User
from app.repositories.artifact_repository import ArtifactRepository
from app.repositories.submission_repository import SubmissionRepository
from app.repositories.study_repository import StudyRepository
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService
from app.services.context_graph_service import ContextGraphService
from app.services.sdtm_define_service import build_define_xml

_REQUIRED_TYPES = (
    ArtifactType.SDTM_DATASET,
    ArtifactType.ADAM_DATASET,
    ArtifactType.TLF,
    ArtifactType.CSR,
)


@dataclass
class SubmissionReadiness:
    study_id: UUID
    ready: bool
    issues: list[str]
    required_artifacts: dict[str, str | None]


class SubmissionService:
    """Assemble and export regulatory submission packages."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._settings = get_settings()
        self._study_repo = StudyRepository(db)
        self._artifact_repo = ArtifactRepository(db)
        self._submission_repo = SubmissionRepository(db)
        self._audit = AuditService(db)
        self._graph = ContextGraphService(db)

    async def get_readiness(
        self, study_id: UUID, organization_id: UUID
    ) -> SubmissionReadiness:
        """Check whether a study is ready for submission packaging."""
        await self._study_repo.get(study_id, organization_id)
        issues = await self._collect_readiness_issues(study_id, organization_id)
        artifacts = await self._find_required_artifacts(study_id, organization_id)
        required = {t.value: None for t in _REQUIRED_TYPES}
        for art in artifacts:
            required[art.artifact_type.value] = str(art.id)
        return SubmissionReadiness(
            study_id=study_id,
            ready=len(issues) == 0,
            issues=issues,
            required_artifacts=required,
        )

    async def create_submission_package(
        self,
        study_id: UUID,
        actor: User,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> SubmissionPackage:
        """Validate readiness, assemble eCTD folder structure, return package."""
        require_admin(actor)

        await self._study_repo.get(study_id, actor.organization_id)
        issues = await self._collect_readiness_issues(
            study_id, actor.organization_id
        )
        if issues:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "SUBMISSION_NOT_READY",
                    "message": "Study is not ready for submission packaging.",
                    "issues": issues,
                },
            )

        artifacts = await self._find_required_artifacts(
            study_id, actor.organization_id
        )
        artifact_ids = [str(a.id) for a in artifacts]

        package = await self._submission_repo.create(
            organization_id=actor.organization_id,
            study_id=study_id,
            created_by_id=actor.id,
            status=SubmissionPackageStatus.DRAFT,
            artifact_ids=artifact_ids,
        )

        await self._audit.log(
            action=AuditAction.SUBMISSION_PACKAGE_CREATED,
            resource_type="submission_package",
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            resource_id=package.id,
            after_state={
                "study_id": str(study_id),
                "artifact_ids": artifact_ids,
                "status": SubmissionPackageStatus.DRAFT.value,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return package

    async def assemble_submission_package(
        self,
        package_id: UUID,
        organization_id: UUID,
    ) -> SubmissionPackage:
        """Assemble package files on disk (background job). DRAFT -> READY."""
        package = await self._submission_repo.get_by_id(package_id, organization_id)
        if package.status not in (
            SubmissionPackageStatus.DRAFT,
            SubmissionPackageStatus.PACKAGING,
        ):
            return package

        from_status = package.status
        package.status = SubmissionPackageStatus.PACKAGING
        await self._submission_repo.update(package)
        await self._log_status_change(
            package=package,
            from_status=from_status,
            to_status=SubmissionPackageStatus.PACKAGING,
            actor_user_id=package.created_by_id,
        )

        artifacts = []
        for artifact_id_str in package.artifact_ids:
            art = await self._artifact_repo.get_by_id(
                UUID(artifact_id_str), organization_id
            )
            artifacts.append(art)

        actor = None
        if package.created_by_id:
            actor = await UserRepository(self._db).get_by_id(package.created_by_id)

        try:
            manifest, local_path, checksum = await self._assemble_package(
                package=package,
                artifacts=artifacts,
                organization_id=organization_id,
            )
            package.status = SubmissionPackageStatus.READY
            package.local_path = local_path
            package.manifest = manifest
            package.package_checksum = checksum
            package.error_message = None
            await self._submission_repo.update(package)
            await self._log_status_change(
                package=package,
                from_status=SubmissionPackageStatus.PACKAGING,
                to_status=SubmissionPackageStatus.READY,
                actor_user_id=package.created_by_id,
            )
            if actor is not None:
                await self._register_graph_links(
                    package=package,
                    artifacts=artifacts,
                    actor=actor,
                )
        except Exception as exc:
            package.status = SubmissionPackageStatus.DRAFT
            package.error_message = str(exc)
            await self._submission_repo.update(package)
            await self._log_status_change(
                package=package,
                from_status=SubmissionPackageStatus.PACKAGING,
                to_status=SubmissionPackageStatus.DRAFT,
                actor_user_id=package.created_by_id,
                error=str(exc),
            )
            raise

        return package

    async def _log_status_change(
        self,
        *,
        package: SubmissionPackage,
        from_status: SubmissionPackageStatus,
        to_status: SubmissionPackageStatus,
        actor_user_id: UUID | None,
        error: str | None = None,
    ) -> None:
        after_state: dict = {
            "from_status": from_status.value,
            "to_status": to_status.value,
            "package_checksum": package.package_checksum,
        }
        if error:
            after_state["error"] = error
        await self._audit.log(
            action=AuditAction.SUBMISSION_PACKAGE_STATUS_CHANGED,
            resource_type="submission_package",
            organization_id=package.organization_id,
            actor_user_id=actor_user_id,
            resource_id=package.id,
            before_state={"status": from_status.value},
            after_state=after_state,
        )

    async def list_for_study(
        self, study_id: UUID, organization_id: UUID
    ) -> tuple[list[SubmissionPackage], int]:
        """List submission packages for a study."""
        await self._study_repo.get(study_id, organization_id)
        return await self._submission_repo.list_for_study(
            study_id, organization_id, limit=100, offset=0
        )

    async def get_manifest(
        self, package_id: UUID, actor: User
    ) -> SubmissionPackage:
        """Return package with manifest. Reviewer or Admin."""
        check_permission(actor, Permission.AUDIT_READ)
        return await self._submission_repo.get_by_id(
            package_id, actor.organization_id
        )

    async def build_zip_bytes(self, package_id: UUID, actor: User) -> bytes:
        """Build zip archive of the submission folder. Admin only."""
        require_admin(actor)
        package = await self._submission_repo.get_by_id(
            package_id, actor.organization_id
        )
        if package.status != SubmissionPackageStatus.READY:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "PACKAGE_NOT_READY",
                    "message": f"Package status is {package.status.value}.",
                },
            )
        if not package.local_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "PACKAGE_FILES_MISSING",
                    "message": "Package files not found on disk.",
                },
            )

        root = Path(package.local_path)
        if not root.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "PACKAGE_FILES_MISSING",
                    "message": "Package directory does not exist.",
                },
            )

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in sorted(root.rglob("*")):
                if file_path.is_file():
                    arcname = file_path.relative_to(root).as_posix()
                    zf.write(file_path, arcname)
        return buffer.getvalue()

    async def _collect_readiness_issues(
        self, study_id: UUID, organization_id: UUID
    ) -> list[str]:
        issues: list[str] = []
        artifacts = await self._find_required_artifacts(study_id, organization_id)
        found_types = {a.artifact_type for a in artifacts}

        for req_type in _REQUIRED_TYPES:
            if req_type not in found_types:
                issues.append(f"Missing approved {req_type.value} artifact.")

        for art in artifacts:
            if art.status != ArtifactStatus.APPROVED:
                issues.append(
                    f"{art.artifact_type.value} '{art.name}' is {art.status.value}, "
                    "not APPROVED."
                )

        pending_ai = await self._db.execute(
            select(AIDecision).where(
                AIDecision.organization_id == organization_id,
                AIDecision.study_id == study_id,
                AIDecision.status == AIDecisionStatus.PENDING_REVIEW,
            )
        )
        pending_count = len(list(pending_ai.scalars().all()))
        if pending_count:
            issues.append(
                f"{pending_count} AI decision(s) still PENDING_REVIEW for this study."
            )

        open_failures = await self._db.execute(
            select(ValidationEvidence).where(
                and_(
                    ValidationEvidence.organization_id == organization_id,
                    ValidationEvidence.study_id == study_id,
                    ValidationEvidence.status == ValidationEvidenceStatus.FAIL,
                )
            )
        )
        fail_count = len(list(open_failures.scalars().all()))
        if fail_count:
            issues.append(
                f"{fail_count} open CDISC validation finding(s) with FAIL status."
            )

        return issues

    async def _find_required_artifacts(
        self, study_id: UUID, organization_id: UUID
    ) -> list[Artifact]:
        artifacts, _ = await self._artifact_repo.list_by_study(
            study_id, organization_id, limit=200, offset=0
        )
        result: list[Artifact] = []
        for req_type in _REQUIRED_TYPES:
            matches = [
                a
                for a in artifacts
                if a.artifact_type == req_type
                and a.status == ArtifactStatus.APPROVED
            ]
            if matches:
                result.append(
                    max(matches, key=lambda a: a.updated_at or a.created_at)
                )
        return result

    async def _assemble_package(
        self,
        *,
        package: SubmissionPackage,
        artifacts: list[Artifact],
        organization_id: UUID,
    ) -> tuple[dict, str, str]:
        study = await self._study_repo.get(package.study_id, organization_id)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        folder_name = f"submission_{package.study_id}_{timestamp}"
        root = (
            Path(self._settings.STORAGE_LOCAL_PATH)
            / "org"
            / str(organization_id)
            / "submissions"
            / str(package.id)
            / folder_name
        )
        root.mkdir(parents=True, exist_ok=True)

        m5_datasets = root / "m5" / "datasets"
        sdtm_dir = m5_datasets / "sdtm"
        adam_dir = m5_datasets / "adam"
        sdtm_dir.mkdir(parents=True, exist_ok=True)
        adam_dir.mkdir(parents=True, exist_ok=True)
        (root / "csr").mkdir(parents=True, exist_ok=True)
        (root / "tlf").mkdir(parents=True, exist_ok=True)

        files_manifest: list[dict] = []

        for art in artifacts:
            content = await self._load_artifact_content(art)
            if art.artifact_type == ArtifactType.SDTM_DATASET:
                define_xml = build_define_xml(content)
                define_path = root / "m5" / "define.xml"
                define_path.write_text(define_xml, encoding="utf-8")
                files_manifest.append(
                    self._file_entry(define_path, root, "m5/define.xml")
                )
                for domain in content.get("domains", []):
                    domain_code = domain.get("domain", "UNK")
                    csv_path = sdtm_dir / f"{domain_code}.csv"
                    self._write_domain_csv(csv_path, domain)
                    files_manifest.append(
                        self._file_entry(
                            csv_path, root, f"m5/datasets/sdtm/{domain_code}.csv"
                        )
                    )
            elif art.artifact_type == ArtifactType.ADAM_DATASET:
                for ds in content.get("datasets", []):
                    ds_name = ds.get("dataset", "UNK")
                    csv_path = adam_dir / f"{ds_name}.csv"
                    self._write_adam_csv(csv_path, ds)
                    files_manifest.append(
                        self._file_entry(
                            csv_path, root, f"m5/datasets/adam/{ds_name}.csv"
                        )
                    )
            elif art.artifact_type == ArtifactType.TLF:
                tlf_path = root / "tlf" / f"{art.id}.rtf"
                tlf_path.write_text(
                    self._build_tlf_placeholder(content, art.name),
                    encoding="utf-8",
                )
                files_manifest.append(
                    self._file_entry(tlf_path, root, f"tlf/{art.id}.rtf")
                )
            elif art.artifact_type == ArtifactType.CSR:
                csr_path = root / "csr" / f"{art.id}.pdf"
                csr_path.write_bytes(
                    self._build_csr_placeholder(content, art.name, study.name)
                )
                files_manifest.append(
                    self._file_entry(csr_path, root, f"csr/{art.id}.pdf")
                )

        reviewers_path = root / "m5" / "reviewers-guide.pdf"
        reviewers_path.write_bytes(
            b"%PDF-1.4\n% Reviewer's Guide placeholder - populate before submission.\n"
        )
        files_manifest.append(
            self._file_entry(
                reviewers_path, root, "m5/reviewers-guide.pdf"
            )
        )

        manifest = {
            "package_id": str(package.id),
            "study_id": str(package.study_id),
            "study_name": study.name,
            "protocol_number": study.protocol_number,
            "assembled_at": datetime.now(UTC).isoformat(),
            "artifact_ids": package.artifact_ids,
            "ectd_structure": "m5",
            "files": files_manifest,
        }
        manifest_path = root / "manifest.json"
        manifest_json = json.dumps(manifest, indent=2)
        manifest_path.write_text(manifest_json, encoding="utf-8")
        files_manifest.append(
            self._file_entry(manifest_path, root, "manifest.json")
        )
        manifest["files"] = files_manifest

        package_checksum = hashlib.sha256(manifest_json.encode()).hexdigest()
        return manifest, str(root), package_checksum

    async def _load_artifact_content(self, artifact: Artifact) -> dict:
        version = await self._artifact_repo.get_version(artifact.current_version_id)
        return version.content or {}

    @staticmethod
    def _file_entry(path: Path, root: Path, logical_path: str) -> dict:
        data = path.read_bytes()
        return {
            "path": logical_path,
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }

    @staticmethod
    def _write_domain_csv(path: Path, domain: dict) -> None:
        observations = domain.get("observations", [])
        variables = domain.get("variables", [])
        if not observations:
            path.write_text("", encoding="utf-8")
            return
        if observations and isinstance(observations[0], dict):
            fieldnames = variables or list(observations[0].keys())
        else:
            fieldnames = variables
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for row in observations:
                if isinstance(row, dict):
                    writer.writerow(row)

    @staticmethod
    def _write_adam_csv(path: Path, dataset: dict) -> None:
        observations = dataset.get("observations", [])
        variables = [v.get("variable") for v in dataset.get("variables", [])]
        if not observations:
            path.write_text(
                f"# ADaM dataset {dataset.get('dataset', 'UNK')} - specification only\n",
                encoding="utf-8",
            )
            return
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh, fieldnames=variables, extrasaction="ignore"
            )
            writer.writeheader()
            for row in observations:
                writer.writerow(row)

    @staticmethod
    def _build_tlf_placeholder(content: dict, name: str) -> str:
        tables = content.get("tables", content.get("tlfs", []))
        lines = [
            r"{\rtf1\ansi",
            rf"\b {name} \b0\par",
            r"\par",
            r"TLF package placeholder - RTF output pending full rendering.\par",
        ]
        for tbl in tables[:10]:
            tid = tbl.get("table_id", tbl.get("id", "?"))
            title = tbl.get("title", "")
            lines.append(rf"Table {tid}: {title}\par")
        lines.append("}")
        return "\n".join(lines)

    @staticmethod
    def _build_csr_placeholder(content: dict, name: str, study_name: str) -> bytes:
        title = content.get("title", name)
        text = (
            f"%PDF-1.4\n"
            f"% CSR placeholder for {study_name}\n"
            f"% Title: {title}\n"
            f"% ICH E3 sections: {len(content.get('sections', []))}\n"
        )
        return text.encode("utf-8")

    async def _register_graph_links(
        self,
        *,
        package: SubmissionPackage,
        artifacts: list[Artifact],
        actor: User,
    ) -> None:
        sub_node, _ = await self._graph.register_domain_record(
            organization_id=actor.organization_id,
            node_type=GraphNodeType.SUBMISSION_PACKAGE,
            external_id=package.id,
            external_type="submission_package",
            label=f"Submission Package {package.id}",
            study_id=package.study_id,
            properties={
                "package_id": str(package.id),
                "status": package.status.value,
                "checksum": package.package_checksum,
            },
            actor=actor,
        )
        for art in artifacts:
            art_node, _ = await self._graph.register_domain_record(
                organization_id=actor.organization_id,
                node_type=GraphNodeType.ARTIFACT,
                external_id=art.id,
                external_type="artifact",
                label=art.name,
                study_id=package.study_id,
                properties={
                    "artifact_id": str(art.id),
                    "artifact_type": art.artifact_type.value,
                },
                actor=actor,
            )
            await self._graph.create_relationship(
                organization_id=actor.organization_id,
                source_node_id=sub_node.id,
                target_node_id=art_node.id,
                edge_type=GraphEdgeType.INCLUDES,
                study_id=package.study_id,
                actor=actor,
            )
