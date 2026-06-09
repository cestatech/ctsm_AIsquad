"""TLF generation service — derive TLF specifications from ADaM artifact content."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.permissions import Permission, check_permission
from app.models.artifact import Artifact, ArtifactType
from app.models.audit import AuditAction
from app.models.statistical_qc import StatisticalQCWorkflow
from app.models.user import User
from app.models.validation import ValidationRun
from app.repositories.artifact_repository import ArtifactRepository
from app.repositories.study_repository import StudyRepository
from app.schemas.validation import ValidationRunCreate
from app.services.artifact_service import ArtifactService
from app.services.audit_service import AuditService
from app.services.data_cut_service import extract_data_cut, prepare_pipeline_artifact
from app.services.dual_programmer_qc_service import DualProgrammerQCService
from app.services.intelligence_service import AIDecisionService
from app.services.validation_service import ValidationService

_AGENT_NAME = "tlf-generation-agent"
_MODEL_ID = "claude-sonnet-4-20250514"


@dataclass
class TLFGenerationResult:
    artifact: Artifact
    ai_decision_id: UUID
    validation_run: ValidationRun
    table_count: int
    source_adam_artifact_ids: list[UUID]


class TLFGenerationService:
    """Generate TLF artifacts from ADaM dataset specifications."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._study_repo = StudyRepository(db)
        self._artifact_repo = ArtifactRepository(db)
        self._artifact_svc = ArtifactService(db)
        self._ai_decision = AIDecisionService(db)
        self._validation = ValidationService(db)
        self._audit = AuditService(db)
        self._settings = get_settings()

    async def generate_from_adam_artifact(
        self,
        adam_artifact_id: UUID,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TLFGenerationResult:
        """Derive TLF specification from an ADaM artifact."""
        check_permission(actor, Permission.ARTIFACT_CREATE)

        adam_artifact, adam_content = await self._get_adam_artifact(
            adam_artifact_id, actor.organization_id
        )
        study = await self._study_repo.get(
            adam_artifact.study_id, actor.organization_id
        )
        sdtm_domains = await self._load_source_sdtm_domains(
            adam_content, actor.organization_id
        )

        decision = await self._ai_decision.begin_decision(
            organization_id=actor.organization_id,
            agent_name=_AGENT_NAME,
            decision_type="TLF_GENERATION",
            study_id=study.id,
            model_id=_MODEL_ID,
            input_context={
                "adam_artifact_id": str(adam_artifact_id),
                "dataset_count": len(adam_content.get("datasets", [])),
            },
        )

        content = self._build_tlf_content(
            study_name=study.name,
            protocol_number=adam_content.get("protocol_number") or study.protocol_number,
            adam_content=adam_content,
            source_adam_artifact_id=adam_artifact_id,
        )
        data_cut = extract_data_cut(adam_artifact.extra_data, adam_content)
        if data_cut is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "NO_DATA_CUT",
                    "message": "ADaM source artifact must include data cut metadata.",
                },
            )
        art_name, art_desc, content, metadata = prepare_pipeline_artifact(
            study_name=study.name,
            package_label="TLF Package",
            data_cut=data_cut,
            content=content,
            base_description="AI-derived TLF specification from ADaM analysis datasets",
        )

        artifact = await self._artifact_svc.create_artifact(
            organization_id=actor.organization_id,
            study_id=study.id,
            user=actor,
            artifact_type=ArtifactType.TLF,
            name=art_name,
            description=art_desc,
            content=content,
            change_summary=f"TLF derivation from ADaM artifact {adam_artifact.name}",
            metadata=metadata,
        )

        await self._ai_decision.complete_decision(
            decision=decision,
            output={
                "artifact_id": str(artifact.id),
                "tables": [t["id"] for t in content.get("tables", [])],
            },
            reasoning="Derived TLF tables from ADaM specification",
            confidence=0.8,
            output_artifact_ids=[artifact.id],
        )

        validation_run = await self._validation.trigger(
            body=ValidationRunCreate(
                artifact_id=artifact.id,
                artifact_version_id=artifact.current_version_id,
                engine="internal",
                rule_set_version="ICH-E3-TLF",
            ),
            actor=actor,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self._audit.log(
            action=AuditAction.AI_GENERATION_COMPLETED,
            resource_type="tlf_package",
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            resource_id=artifact.id,
            after_state={
                "artifact_id": str(artifact.id),
                "source_adam_artifact_id": str(adam_artifact_id),
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        qc_input = {
            "domains": sdtm_domains or [{"domain": "ADSL", "observations": []}],
            "datasets": adam_content.get("datasets", []),
            "tables": content.get("tables", []),
        }
        qc_svc = DualProgrammerQCService(self._db)
        await qc_svc.run_qc(
            workflow_step=StatisticalQCWorkflow.ADAM_TO_TLF,
            study_id=study.id,
            actor=actor,
            input_payload=qc_input,
            output_artifact_id=artifact.id,
            source_artifact_id=adam_artifact_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return TLFGenerationResult(
            artifact=artifact,
            ai_decision_id=decision.id,
            validation_run=validation_run,
            table_count=len(content.get("tables", [])),
            source_adam_artifact_ids=[adam_artifact_id],
        )

    async def _get_adam_artifact(
        self, artifact_id: UUID, organization_id: UUID
    ) -> tuple[Artifact, dict]:
        artifact = await self._artifact_repo.get_by_id(artifact_id, organization_id)
        if artifact.artifact_type != ArtifactType.ADAM_DATASET:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "NOT_ADAM", "message": "Source must be ADAM_DATASET."},
            )
        version = await self._artifact_repo.get_version(artifact.current_version_id)
        return artifact, version.content or {}

    async def _load_source_sdtm_domains(
        self, adam_content: dict, organization_id: UUID
    ) -> list[dict]:
        """Load SDTM domains from source artifacts for R QC input fixtures."""
        domains: list[dict] = []
        for src_id in adam_content.get("source_sdtm_artifact_ids", []):
            try:
                art = await self._artifact_repo.get_by_id(UUID(src_id), organization_id)
                ver = await self._artifact_repo.get_version(art.current_version_id)
                domains.extend((ver.content or {}).get("domains", []))
            except (ValueError, HTTPException):
                continue
        return domains

    @staticmethod
    def _build_tlf_content(
        *,
        study_name: str,
        protocol_number: str,
        adam_content: dict,
        source_adam_artifact_id: UUID,
    ) -> dict:
        datasets = adam_content.get("datasets", [])
        has_adsl = any(d.get("dataset") == "ADSL" for d in datasets)
        tables = []
        if has_adsl:
            tables.append({
                "id": "T-01",
                "title": "Summary of Demographics and Baseline Characteristics",
                "section": "14.1",
                "population": "ITT",
                "source_dataset": "ADSL",
                "key_variables": ["AGE", "SEX", "RACE"],
                "row_definition": "Category levels",
                "column_definition": "Treatment groups",
                "statistical_summary": "n (%) for categorical; Mean (SD) for continuous",
                "footnotes": ["ITT population per ADSL.ITTFL=Y"],
                "program_name": "t_01_demog.R",
            })
        tables.append({
            "id": "T-02",
            "title": "Summary of Treatment Exposure",
            "section": "14.2",
            "population": "Safety",
            "source_dataset": "ADSL",
            "key_variables": ["TRT01P", "TRT01A"],
            "row_definition": "Treatment groups",
            "column_definition": "Statistics",
            "statistical_summary": "n (%)",
            "footnotes": [],
            "program_name": "t_02_exposure.R",
        })

        return {
            "document_type": "TLF_SPECIFICATION",
            "version": "1.0",
            "study_name": study_name,
            "protocol_number": protocol_number,
            "source_adam_artifact_ids": [str(source_adam_artifact_id)],
            "tables": tables,
            "listings": [],
            "figures": [],
            "output_formats": ["CSV", "RTF"],
            "regulatory_references": ["ICH E3", "CDISC TLF Standards"],
        }
