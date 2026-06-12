"""CSR generation service — assemble ICH E3 Clinical Study Report from TLF + study artifacts.

Phase 7 pipeline: TLF artifact(s) + Protocol/SAP context → CSR artifact
→ context graph + section lineage → internal ICH E3 validation run.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from uuid import UUID

import anthropic
from anthropic.types import TextBlock
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.permissions import Permission, check_permission
from app.models.artifact import Artifact, ArtifactType
from app.models.audit import AuditAction
from app.models.graph import GraphEdgeType, GraphNodeType
from app.models.intelligence import DataLineageType
from app.models.user import User
from app.models.validation import ValidationRun
from app.repositories.artifact_repository import ArtifactRepository
from app.repositories.study_repository import StudyRepository
from app.schemas.validation import ValidationRunCreate
from app.services.artifact_service import ArtifactService
from app.services.audit_service import AuditService
from app.services.context_graph_service import ContextGraphService
from app.services.intelligence_service import AIDecisionService, DataLineageService
from app.services.data_cut_service import (
    CSRReadinessResult,
    CSRRequirement,
    DataCutContext,
    contains_shell_placeholder,
    extract_data_cut,
    prepare_pipeline_artifact,
)
from app.services.csr_prose_service import assemble_context
from app.services.generation_fallback import (
    NO_API_KEY_FALLBACK_REASON,
    apply_dummy_generation_labels,
    format_fallback_reasoning,
)
from app.services.generators.csr_generator import CSRGenerator
from app.services.validation_service import ValidationService

logger = logging.getLogger(__name__)

_CSR_BLOCKED_MESSAGE = (
    "CSR generation requires SDTM, ADaM, and TLF outputs for the selected data cut. "
    "Generate those artifacts first."
)

_AGENT_NAME = "csr-generation-agent"
_PROSE_AGENT_NAME = "csr-prose-generator"
_MODEL_ID = "claude-sonnet-4-20250514"

_SYSTEM_PROMPT = """You are a senior medical writer assembling an ICH E3 Clinical Study Report (CSR).

Given TLF table specifications and study artifact context, produce a CSR document JSON.

Rules:
- Follow ICH E3 section numbering (1 Title, 2 Synopsis, 9–15 body sections)
- Embed TLF table references in the appropriate efficacy/safety sections
- Mark sections DRAFT; use content_outline not full prose
- Return ONLY valid JSON matching the schema below

Schema:
{
  "document_type": "CSR",
  "version": "1.0",
  "ich_e3_compliant": true,
  "title": "<CSR title>",
  "study_identification": {
    "protocol_number": "",
    "sponsor": "",
    "phase": "",
    "indication": ""
  },
  "synopsis": {
    "objectives": "",
    "design": "",
    "population": "",
    "treatments": [],
    "primary_results": "",
    "safety_summary": "",
    "conclusions": ""
  },
  "sections": [
    {
      "number": "13",
      "title": "Efficacy Evaluation",
      "ich_e3_reference": "Section 13",
      "content_outline": "",
      "status": "DRAFT",
      "tlf_references": [{"table_id": "T-01", "title": ""}],
      "word_count_estimate": 0
    }
  ],
  "appendices": ["Protocol", "SAP", "TLF outputs"],
  "tlf_integration": [{"table_id": "", "csr_section": "13", "insertion_note": ""}],
  "ectd_module_5": {
    "ready": false,
    "folder_structure": ["m5/datasets/tabulation/sdtm", "m5/datasets/analysis/adam", "m5/clinical-study-reports"],
    "notes": "CSR shell — populate after final TLF lock"
  },
  "estimated_total_word_count": 25000,
  "regulatory_references": ["ICH E3", "FDA Module 5 Guidance"]
}"""

_ICH_E3_SECTIONS: list[tuple[str, str, str]] = [
    ("1", "Title Page", "Study title, sponsor, protocol number, report date"),
    ("2", "Synopsis", "Tabular summary of design, population, and key results"),
    ("9", "Introduction", "Disease background, rationale, prior studies"),
    ("10", "Study Objectives", "Primary and secondary objectives and endpoints"),
    ("11", "Investigational Plan", "Overall design, selection criteria, treatments"),
    ("12", "Study Patients", "Disposition, demographics, protocol deviations"),
    ("13", "Efficacy Evaluation", "Primary and secondary endpoint results"),
    ("14", "Safety Evaluation", "AEs, labs, vital signs, SAEs"),
    ("15", "Discussion and Overall Conclusions", "Integrated benefit-risk assessment"),
]


@dataclass
class StudyCSRReadiness:
    """CSR readiness for a study, optionally scoped to one data cut."""

    study_id: UUID
    tlf_artifact_count: int
    protocol_artifact_count: int
    sap_artifact_count: int
    ready: bool
    issues: list[str]
    tlf_artifacts: list[dict]
    data_cut_id: UUID | None = None
    data_source_type: str | None = None
    data_cut_label: str | None = None
    csr_kind: str | None = None
    requirements: list[dict] | None = None
    sdtm_artifact_id: UUID | None = None
    adam_artifact_id: UUID | None = None


@dataclass
class CSRGenerationResult:
    artifact: Artifact
    ai_decision_id: UUID
    validation_run: ValidationRun
    section_count: int
    source_tlf_artifact_ids: list[UUID]
    source_study_artifact_ids: list[UUID]


class CSRGenerationService:
    """Generate CSR artifacts from TLF packages and study context."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._study_repo = StudyRepository(db)
        self._artifact_repo = ArtifactRepository(db)
        self._artifact_svc = ArtifactService(db)
        self._ai_decision = AIDecisionService(db)
        self._graph = ContextGraphService(db)
        self._lineage = DataLineageService(db)
        self._validation = ValidationService(db)
        self._audit = AuditService(db)
        settings = get_settings()
        self._settings = settings
        self._client = (
            anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            if settings.ANTHROPIC_API_KEY
            else None
        )

    async def get_study_readiness(
        self,
        study_id: UUID,
        organization_id: UUID,
        data_cut_id: UUID | None = None,
    ) -> StudyCSRReadiness:
        """Return CSR readiness including upstream SDTM/ADaM/TLF for a data cut."""
        await self._study_repo.get(study_id, organization_id)
        result = await self._evaluate_csr_readiness(
            study_id, organization_id, data_cut_id=data_cut_id
        )
        return StudyCSRReadiness(
            study_id=result.study_id,
            tlf_artifact_count=1 if result.tlf_artifact_id else 0,
            protocol_artifact_count=1 if result.protocol_artifact_id else 0,
            sap_artifact_count=1 if result.sap_artifact_id else 0,
            ready=result.ready,
            issues=result.issues,
            tlf_artifacts=result.to_response_dict().get("tlf_artifacts", []),
            data_cut_id=result.data_cut_id,
            data_source_type=result.data_source_type,
            data_cut_label=result.data_cut_label,
            csr_kind=result.csr_kind,
            requirements=[r.to_dict() for r in result.requirements],
            sdtm_artifact_id=result.sdtm_artifact_id,
            adam_artifact_id=result.adam_artifact_id,
        )

    async def generate_from_tlf_artifact(
        self,
        tlf_artifact_id: UUID,
        actor: User,
        generate_shell: bool = False,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> CSRGenerationResult:
        """Assemble CSR from a single TLF artifact plus study context."""
        check_permission(actor, Permission.ARTIFACT_CREATE)

        tlf_artifact, tlf_content = await self._get_tlf_artifact(
            tlf_artifact_id, actor.organization_id
        )
        self._assert_tlf_ready(tlf_content, tlf_artifact.name)

        study = await self._study_repo.get(
            tlf_artifact.study_id, actor.organization_id
        )
        data_cut = extract_data_cut(tlf_artifact.extra_data, tlf_content)
        readiness = await self._evaluate_csr_readiness(
            study.id,
            actor.organization_id,
            data_cut_id=data_cut.data_cut_id if data_cut else None,
        )
        if not generate_shell and not readiness.ready:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "CSR_NOT_READY",
                    "message": _CSR_BLOCKED_MESSAGE,
                    "issues": readiness.issues,
                    "requirements": [r.to_dict() for r in readiness.requirements],
                },
            )

        upstream = await self._load_upstream_for_readiness(
            readiness, actor.organization_id
        )
        study_artifacts = await self._load_study_context_artifacts(
            study.id, actor.organization_id
        )

        return await self._run_generation(
            actor=actor,
            study=study,
            tlf_artifacts=[tlf_artifact],
            tlf_contents=[tlf_content],
            study_artifacts=study_artifacts,
            readiness=readiness,
            upstream=upstream,
            generate_shell=generate_shell,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def generate_from_study(
        self,
        study_id: UUID,
        actor: User,
        data_cut_id: UUID | None = None,
        generate_shell: bool = False,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> CSRGenerationResult:
        """Generate CSR for a study data cut with full upstream evidence."""
        check_permission(actor, Permission.ARTIFACT_CREATE)

        readiness = await self._evaluate_csr_readiness(
            study_id, actor.organization_id, data_cut_id=data_cut_id
        )
        if not generate_shell and not readiness.ready:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "CSR_NOT_READY",
                    "message": _CSR_BLOCKED_MESSAGE,
                    "issues": readiness.issues,
                    "requirements": [r.to_dict() for r in readiness.requirements],
                },
            )

        study = await self._study_repo.get(study_id, actor.organization_id)
        upstream = await self._load_upstream_for_readiness(
            readiness, actor.organization_id
        )
        tlf_artifact = upstream["tlf_artifact"]
        tlf_content = upstream["tlf_content"]
        study_artifacts = await self._load_study_context_artifacts(
            study_id, actor.organization_id
        )

        return await self._run_generation(
            actor=actor,
            study=study,
            tlf_artifacts=[tlf_artifact],
            tlf_contents=[tlf_content],
            study_artifacts=study_artifacts,
            readiness=readiness,
            upstream=upstream,
            generate_shell=generate_shell,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def _run_generation(
        self,
        *,
        actor: User,
        study,
        tlf_artifacts: list[Artifact],
        tlf_contents: list[dict],
        study_artifacts: dict[str, Artifact | None],
        readiness: CSRReadinessResult,
        upstream: dict,
        generate_shell: bool,
        ip_address: str | None,
        user_agent: str | None,
    ) -> CSRGenerationResult:
        tlf_ids = [a.id for a in tlf_artifacts]
        context_ids = [
            a.id for a in study_artifacts.values() if a is not None
        ]
        merged_tables = self._merge_tlf_tables(tlf_contents)
        data_cut = extract_data_cut(
            tlf_artifacts[0].extra_data if tlf_artifacts else None,
            tlf_contents[0] if tlf_contents else None,
        )

        decision = await self._ai_decision.begin_decision(
            organization_id=actor.organization_id,
            agent_name=_AGENT_NAME,
            decision_type="CSR_ASSEMBLY",
            study_id=study.id,
            model_id=_MODEL_ID,
            input_context={
                "study_id": str(study.id),
                "source_tlf_artifact_ids": [str(i) for i in tlf_ids],
                "table_count": len(merged_tables),
                "protocol_available": study_artifacts.get("PROTOCOL") is not None,
                "sap_available": study_artifacts.get("SAP") is not None,
                "data_cut_label": readiness.data_cut_label,
                "csr_kind": readiness.csr_kind,
                "generate_shell": generate_shell,
            },
        )

        content = await self._build_csr_content(
            study=study,
            merged_tables=merged_tables,
            tlf_artifact_ids=tlf_ids,
            study_artifacts=study_artifacts,
            upstream=upstream,
            data_cut=data_cut,
            generate_shell=generate_shell,
        )
        if not generate_shell:
            protocol_content: dict = {}
            sap_content: dict = {}
            protocol = study_artifacts.get("PROTOCOL")
            sap = study_artifacts.get("SAP")
            if protocol:
                protocol_content = await self._load_artifact_content(protocol)
            if sap:
                sap_content = await self._load_artifact_content(sap)
            content = await self._enrich_sections_with_prose(
                actor=actor,
                study=study,
                content=content,
                merged_tables=merged_tables,
                protocol_content=protocol_content,
                sap_content=sap_content,
                tlf_contents=tlf_contents,
            )

        if generate_shell:
            art_name = f"{study.name} — CSR Shell"
            art_desc = "CSR shell — generated only by explicit user request"
            metadata = {}
        elif data_cut:
            art_name = f"{study.name} — {data_cut.csr_title(study.name)}"
            _, art_desc, content, metadata = prepare_pipeline_artifact(
                study_name=study.name,
                package_label="CSR",
                data_cut=data_cut,
                content=content,
                base_description="ICH E3 Clinical Study Report assembled from TLF outputs",
            )
            art_name = f"{study.name} — {data_cut.csr_title(study.name)}"
        else:
            art_name = f"{study.name} — Clinical Study Report"
            art_desc = "ICH E3 Clinical Study Report assembled from TLF outputs"
            metadata = {}

        artifact = await self._artifact_svc.create_artifact(
            organization_id=actor.organization_id,
            study_id=study.id,
            user=actor,
            artifact_type=ArtifactType.CSR,
            name=art_name,
            description=art_desc,
            content=content,
            change_summary=(
                f"CSR assembly from {len(tlf_ids)} TLF artifact(s)"
            ),
            metadata=metadata,
        )

        return await self._finalize_generation(
            actor=actor,
            study_id=study.id,
            artifact=artifact,
            decision=decision,
            content=content,
            tlf_artifacts=tlf_artifacts,
            study_artifacts=study_artifacts,
            merged_tables=merged_tables,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def _finalize_generation(
        self,
        *,
        actor: User,
        study_id: UUID,
        artifact: Artifact,
        decision,
        content: dict,
        tlf_artifacts: list[Artifact],
        study_artifacts: dict[str, Artifact | None],
        merged_tables: list[dict],
        ip_address: str | None,
        user_agent: str | None,
    ) -> CSRGenerationResult:
        for tlf_art in tlf_artifacts:
            await self._register_cip_links(
                tlf_artifact=tlf_art,
                csr_artifact=artifact,
                csr_content=content,
                study_artifacts=study_artifacts,
                actor=actor,
                ai_decision_id=decision.id,
            )
            await self._record_section_prose_lineage(
                tlf_artifact=tlf_art,
                csr_artifact=artifact,
                csr_content=content,
                actor=actor,
                ai_decision_id=decision.id,
            )
        study = await self._study_repo.get(study_id, actor.organization_id)
        await self._graph.link_pipeline_artifact_to_study(
            organization_id=actor.organization_id,
            study_id=study_id,
            study_name=study.name,
            artifact_id=artifact.id,
            artifact_name=artifact.name,
            artifact_node_type=GraphNodeType.CSR_SECTION,
            artifact_external_type="csr_artifact",
            actor=actor,
            ai_decision_id=decision.id,
        )

        await self._ai_decision.complete_decision(
            decision=decision,
            output={
                "artifact_id": str(artifact.id),
                "sections": [s["number"] for s in content.get("sections", [])],
                "source_tlf_artifact_ids": [str(a.id) for a in tlf_artifacts],
                "generation_mode": content.get("generation_mode"),
            },
            reasoning=format_fallback_reasoning(
                (
                    f"Assembled ICH E3 CSR with {len(content.get('sections', []))} sections "
                    f"from {len(merged_tables)} TLF table(s)"
                ),
                content.get("fallback_reason"),
            ),
            confidence=0.82 if not content.get("fallback_reason") else 0.5,
            output_artifact_ids=[artifact.id],
        )

        validation_run = await self._validation.trigger(
            body=ValidationRunCreate(
                artifact_id=artifact.id,
                artifact_version_id=artifact.current_version_id,
                engine="internal",
                rule_set_version="ICH-E3-CSR",
            ),
            actor=actor,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self._audit.log(
            action=AuditAction.AI_GENERATION_COMPLETED,
            resource_type="csr_document",
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            resource_id=artifact.id,
            after_state={
                "artifact_id": str(artifact.id),
                "validation_run_id": str(validation_run.id),
                "ai_decision_id": str(decision.id),
                "source_tlf_artifact_ids": [str(a.id) for a in tlf_artifacts],
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        context_ids = [
            a.id for a in study_artifacts.values() if a is not None
        ]
        return CSRGenerationResult(
            artifact=artifact,
            ai_decision_id=decision.id,
            validation_run=validation_run,
            section_count=len(content.get("sections", [])),
            source_tlf_artifact_ids=[a.id for a in tlf_artifacts],
            source_study_artifact_ids=context_ids,
        )

    async def _get_tlf_artifact(
        self, artifact_id: UUID, organization_id: UUID
    ) -> tuple[Artifact, dict]:
        artifact = await self._artifact_repo.get_by_id(artifact_id, organization_id)
        if artifact.artifact_type != ArtifactType.TLF:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "NOT_TLF", "message": "Source must be TLF artifact."},
            )
        content = await self._load_artifact_content(artifact)
        return artifact, content

    async def _load_artifact_content(self, artifact: Artifact) -> dict:
        version = await self._artifact_repo.get_version(artifact.current_version_id)
        return version.content or {}

    async def _load_study_context_artifacts(
        self, study_id: UUID, organization_id: UUID
    ) -> dict[str, Artifact | None]:
        """Load latest Protocol and SAP artifacts for CSR context."""
        artifacts, _ = await self._artifact_repo.list_by_study(
            study_id, organization_id, limit=100, offset=0
        )
        result: dict[str, Artifact | None] = {
            "PROTOCOL": None,
            "SAP": None,
        }
        for art in artifacts:
            key = art.artifact_type.value
            if key in result and result[key] is None:
                result[key] = art
        return result

    @staticmethod
    def _assert_tlf_ready(content: dict, artifact_name: str) -> None:
        tables = content.get("tables", [])
        if not tables:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "TLF_NOT_READY",
                    "message": f"TLF artifact '{artifact_name}' has no tables.",
                },
            )

    @staticmethod
    def _merge_tlf_tables(tlf_contents: list[dict]) -> list[dict]:
        """Merge tables from multiple TLF packages, deduplicating by table id."""
        by_id: dict[str, dict] = {}
        for content in tlf_contents:
            for table in content.get("tables", []):
                tid = table.get("id", f"T-{len(by_id) + 1}")
                if tid not in by_id:
                    by_id[tid] = dict(table)
        return list(by_id.values())

    async def _build_csr_content(
        self,
        *,
        study,
        merged_tables: list[dict],
        tlf_artifact_ids: list[UUID],
        study_artifacts: dict[str, Artifact | None],
        upstream: dict,
        data_cut: DataCutContext | None,
        generate_shell: bool,
    ) -> dict:
        protocol = study_artifacts.get("PROTOCOL")
        sap = study_artifacts.get("SAP")
        protocol_content: dict = {}
        sap_content: dict = {}
        if protocol:
            protocol_content = await self._load_artifact_content(protocol)
        if sap:
            sap_content = await self._load_artifact_content(sap)

        if generate_shell:
            return self._csr_shell_content(
                study=study,
                protocol_content=protocol_content,
                sap_content=sap_content,
            )

        if not merged_tables:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "TLF_NOT_READY",
                    "message": _CSR_BLOCKED_MESSAGE,
                },
            )

        fallback_reason: str | None = None
        if self._client:
            try:
                return await self._call_claude(
                    study=study,
                    merged_tables=merged_tables,
                    protocol_content=protocol_content,
                    sap_content=sap_content,
                    tlf_artifact_ids=tlf_artifact_ids,
                    upstream=upstream,
                    data_cut=data_cut,
                )
            except HTTPException as exc:
                detail = exc.detail if isinstance(exc.detail, dict) else {}
                if exc.status_code != status.HTTP_502_BAD_GATEWAY or detail.get(
                    "code"
                ) != "AI_PARSE_ERROR":
                    raise
                fallback_reason = str(detail.get("message", exc))
                logger.warning(
                    "CSR agent parse failed, using deterministic fallback: %s",
                    fallback_reason,
                )
            except (anthropic.APIError, TimeoutError) as exc:
                fallback_reason = f"Anthropic API error: {exc}"
                logger.warning(
                    "CSR agent API call failed, using deterministic fallback: %s",
                    exc,
                )
            except Exception as exc:
                fallback_reason = f"AI generation failed: {exc}"
                logger.warning(
                    "CSR agent failed, using deterministic fallback: %s",
                    exc,
                )
        else:
            fallback_reason = NO_API_KEY_FALLBACK_REASON

        content = self._deterministic_csr(
            study=study,
            merged_tables=merged_tables,
            protocol_content=protocol_content,
            sap_content=sap_content,
            tlf_artifact_ids=tlf_artifact_ids,
            upstream=upstream,
            data_cut=data_cut,
        )
        return apply_dummy_generation_labels(content, fallback_reason=fallback_reason)

    async def _evaluate_csr_readiness(
        self,
        study_id: UUID,
        organization_id: UUID,
        data_cut_id: UUID | None = None,
    ) -> CSRReadinessResult:
        artifacts, _ = await self._artifact_repo.list_by_study(
            study_id, organization_id, limit=200, offset=0
        )
        protocol = next((a for a in artifacts if a.artifact_type == ArtifactType.PROTOCOL), None)
        sap = next((a for a in artifacts if a.artifact_type == ArtifactType.SAP), None)
        sdtm_candidates = [a for a in artifacts if a.artifact_type == ArtifactType.SDTM_DATASET]
        adam_candidates = [a for a in artifacts if a.artifact_type == ArtifactType.ADAM_DATASET]
        tlf_candidates = [a for a in artifacts if a.artifact_type == ArtifactType.TLF]

        requirements: list[CSRRequirement] = []
        issues: list[str] = []

        sdtm_art, sdtm_content = None, {}
        for art in sdtm_candidates:
            content = await self._load_artifact_content(art)
            cut = extract_data_cut(art.extra_data, content)
            if data_cut_id and cut and cut.data_cut_id != data_cut_id:
                continue
            if data_cut_id is None or (cut and cut.data_cut_id == data_cut_id):
                sdtm_art, sdtm_content = art, content
                break
        if sdtm_art is None and sdtm_candidates and data_cut_id is None:
            sdtm_art = sdtm_candidates[-1]
            sdtm_content = await self._load_artifact_content(sdtm_art)

        adam_art, adam_content = None, {}
        for art in adam_candidates:
            content = await self._load_artifact_content(art)
            cut = extract_data_cut(art.extra_data, content)
            if data_cut_id and cut and cut.data_cut_id != data_cut_id:
                continue
            if data_cut_id is None or (cut and cut.data_cut_id == data_cut_id):
                adam_art, adam_content = art, content
                break
        if adam_art is None and adam_candidates and data_cut_id is None:
            adam_art = adam_candidates[-1]
            adam_content = await self._load_artifact_content(adam_art)

        tlf_art, tlf_content = None, {}
        for art in tlf_candidates:
            content = await self._load_artifact_content(art)
            cut = extract_data_cut(art.extra_data, content)
            if data_cut_id and cut and cut.data_cut_id != data_cut_id:
                continue
            if data_cut_id is None or (cut and cut.data_cut_id == data_cut_id):
                tlf_art, tlf_content = art, content
                break
        if tlf_art is None and tlf_candidates and data_cut_id is None:
            tlf_art = tlf_candidates[-1]
            tlf_content = await self._load_artifact_content(tlf_art)

        data_cut = extract_data_cut(
            tlf_art.extra_data if tlf_art else None,
            tlf_content,
        ) or extract_data_cut(
            adam_art.extra_data if adam_art else None,
            adam_content,
        ) or extract_data_cut(
            sdtm_art.extra_data if sdtm_art else None,
            sdtm_content,
        )

        requirements.append(CSRRequirement("protocol", "Protocol artifact", protocol is not None))
        requirements.append(CSRRequirement("sap", "SAP artifact", sap is not None))
        requirements.append(
            CSRRequirement(
                "sdtm",
                "SDTM output for data cut",
                sdtm_art is not None and bool(sdtm_content.get("domains")),
                detail=sdtm_art.name if sdtm_art else "",
            )
        )
        requirements.append(
            CSRRequirement(
                "adam",
                "ADaM output for data cut",
                adam_art is not None and bool(adam_content.get("datasets")),
                detail=adam_art.name if adam_art else "",
            )
        )
        tlf_tables = tlf_content.get("tables", []) if tlf_content else []
        requirements.append(
            CSRRequirement(
                "tlf",
                "TLF output for data cut",
                tlf_art is not None and bool(tlf_tables),
                detail=tlf_art.name if tlf_art else "",
            )
        )

        if data_cut and data_cut.data_source_type.value == "LIVE_INTERIM":
            requirements.append(
                CSRRequirement(
                    "live_upload",
                    "Live interim raw upload",
                    data_cut.source_upload_id is not None,
                )
            )
        if data_cut and data_cut.is_synthetic:
            requirements.append(
                CSRRequirement(
                    "synthetic_run",
                    "Synthetic data run or upload",
                    data_cut.synthetic_data_run_id is not None
                    or data_cut.source_upload_id is not None,
                )
            )

        for req in requirements:
            if not req.met:
                issues.append(req.label if not req.detail else f"{req.label}: {req.detail}")

        ready = all(r.met for r in requirements)
        return CSRReadinessResult(
            study_id=study_id,
            data_cut_id=data_cut.data_cut_id if data_cut else data_cut_id,
            data_source_type=data_cut.data_source_type.value if data_cut else None,
            data_cut_label=data_cut.data_cut_label if data_cut else None,
            csr_kind=data_cut.csr_kind() if data_cut else None,
            ready=ready,
            requirements=requirements,
            issues=issues,
            protocol_artifact_id=protocol.id if protocol else None,
            sap_artifact_id=sap.id if sap else None,
            sdtm_artifact_id=sdtm_art.id if sdtm_art else None,
            adam_artifact_id=adam_art.id if adam_art else None,
            tlf_artifact_id=tlf_art.id if tlf_art else None,
            source_upload_id=data_cut.source_upload_id if data_cut else None,
            synthetic_data_run_id=data_cut.synthetic_data_run_id if data_cut else None,
        )

    async def _load_upstream_for_readiness(
        self, readiness: CSRReadinessResult, organization_id: UUID
    ) -> dict:
        result: dict = {}
        if readiness.sdtm_artifact_id:
            art = await self._artifact_repo.get_by_id(readiness.sdtm_artifact_id, organization_id)
            result["sdtm_artifact"] = art
            result["sdtm_content"] = await self._load_artifact_content(art)
        if readiness.adam_artifact_id:
            art = await self._artifact_repo.get_by_id(readiness.adam_artifact_id, organization_id)
            result["adam_artifact"] = art
            result["adam_content"] = await self._load_artifact_content(art)
        if readiness.tlf_artifact_id:
            art = await self._artifact_repo.get_by_id(readiness.tlf_artifact_id, organization_id)
            result["tlf_artifact"] = art
            result["tlf_content"] = await self._load_artifact_content(art)
        return result

    @staticmethod
    def _csr_shell_content(*, study, protocol_content: dict, sap_content: dict) -> dict:
        return {
            "document_type": "CSR_SHELL",
            "version": "1.0",
            "title": f"{study.name} — CSR Shell (Outline Only)",
            "shell_only": True,
            "warning": "This is an explicit CSR shell — not a full clinical study report.",
            "study_identification": {
                "protocol_number": study.protocol_number,
                "sponsor": getattr(study, "sponsor", None) or "Sponsor",
            },
            "synopsis": {"note": "Shell synopsis — populate after upstream artifacts exist."},
            "sections": [
                {"number": "1", "title": "Title Page", "content_outline": "Shell", "status": "SHELL"}
            ],
            "protocol_excerpt": {
                k: protocol_content.get(k)
                for k in ("title", "objectives", "design")
                if protocol_content.get(k)
            },
            "sap_excerpt": {
                k: sap_content.get(k)
                for k in ("title", "primary_endpoint")
                if sap_content.get(k)
            },
        }

    async def _call_claude(
        self,
        *,
        study,
        merged_tables: list[dict],
        protocol_content: dict,
        sap_content: dict,
        tlf_artifact_ids: list[UUID],
        upstream: dict,
        data_cut: DataCutContext | None,
    ) -> dict:
        user_prompt = f"""Study: {study.name}
Protocol: {study.protocol_number}
Indication: {getattr(study, 'indication', None) or 'Not specified'}
Phase: {getattr(study, 'phase', None) or 'Not specified'}
Sponsor: {getattr(study, 'sponsor', None) or 'Not specified'}

TLF tables:
{json.dumps(merged_tables[:20], indent=2, default=str)}

Protocol context (excerpt):
{json.dumps({k: protocol_content.get(k) for k in ('title', 'objectives', 'design') if protocol_content.get(k)}, indent=2, default=str)}

SAP context (excerpt):
{json.dumps({k: sap_content.get(k) for k in ('title', 'primary_endpoint', 'analysis_populations') if sap_content.get(k)}, indent=2, default=str)}

Assemble a complete ICH E3 CSR shell with TLF references embedded in sections 12–14."""

        response = await self._client.messages.create(
            model=_MODEL_ID,
            max_tokens=8000,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = ""
        for block in response.content:
            if isinstance(block, TextBlock):
                text += block.text
        parsed = self._parse_json(text)
        parsed.setdefault("document_type", "CSR")
        parsed["source_tlf_artifact_ids"] = [str(i) for i in tlf_artifact_ids]
        return parsed

    def _deterministic_csr(
        self,
        *,
        study,
        merged_tables: list[dict],
        protocol_content: dict,
        sap_content: dict,
        tlf_artifact_ids: list[UUID],
        upstream: dict,
        data_cut: DataCutContext | None,
    ) -> dict:
        """Build evidence-based ICH E3 CSR from TLF, ADaM, and SDTM inputs."""
        objectives = ""
        if protocol_content:
            objs = protocol_content.get("objectives", {})
            if isinstance(objs, dict):
                primary = objs.get("primary", [])
                if primary:
                    objectives = "; ".join(
                        o.get("description", str(o)) if isinstance(o, dict) else str(o)
                        for o in primary[:3]
                    )
            elif isinstance(objs, list) and objs:
                objectives = "; ".join(str(o) for o in objs[:3])

        design = (
            protocol_content.get("design", {}).get("summary")
            if isinstance(protocol_content.get("design"), dict)
            else protocol_content.get("design", "Randomized controlled trial")
        ) or "Randomized controlled trial"

        primary_endpoint = (
            sap_content.get("primary_endpoint")
            or protocol_content.get("primary_endpoint")
            or "See SAP"
        )

        sdtm_content = upstream.get("sdtm_content", {})
        adam_content = upstream.get("adam_content", {})
        sdtm_domains = sdtm_content.get("domains", [])
        adam_datasets = adam_content.get("datasets", [])
        subject_count = sum(len(d.get("observations", [])) for d in sdtm_domains if d.get("domain") == "DM")
        if not subject_count:
            subject_count = sum(
                1 for ds in adam_datasets if ds.get("dataset") == "ADSL"
            )

        interim_notice = ""
        if data_cut and data_cut.data_source_type.value == "LIVE_INTERIM":
            interim_notice = (
                f"Results in this interim CSR are based on {data_cut.data_cut_label} "
                f"({data_cut.data_cut_date or 'date not specified'}) and do not represent "
                "final study results. Database lock has not occurred."
            )
        synthetic_notice = ""
        if data_cut and data_cut.is_synthetic:
            synthetic_notice = (
                f"This CSR is derived from {data_cut.data_cut_label} — SYNTHETIC data only. "
                "Not derived from real patients. Do not submit to regulators as live data."
            )

        tlf_by_section: dict[str, list[dict]] = {"12": [], "13": [], "14": []}
        for table in merged_tables:
            section = str(table.get("section", "14.1")).split(".")[0]
            target = "13" if section in ("13", "14") else "12"
            if "safety" in table.get("title", "").lower() or "ae" in table.get("title", "").lower():
                target = "14"
            elif "demog" in table.get("title", "").lower() or "disposition" in table.get("title", "").lower():
                target = "12"
            elif "efficacy" in table.get("title", "").lower() or "endpoint" in table.get("title", "").lower():
                target = "13"
            tlf_by_section.setdefault(target, []).append({
                "table_id": table.get("id"),
                "title": table.get("title"),
                "population": table.get("population"),
                "key_result": table.get("statistical_summary", ""),
            })

        sections = []
        for num, title, outline in _ICH_E3_SECTIONS:
            section_entry = {
                "number": num,
                "title": title,
                "ich_e3_reference": f"Section {num}",
                "content_outline": outline,
                "status": "DRAFT",
                "word_count_estimate": 500 if num in ("1", "2") else 2000,
            }
            refs = tlf_by_section.get(num, [])
            if refs:
                section_entry["tlf_references"] = refs
                ref_summary = "; ".join(
                    f"{r['table_id']}: {r['title']} ({r.get('key_result', 'see TLF')})"
                    for r in refs
                )
                section_entry["content_outline"] = f"{outline}. Integrated TLF evidence: {ref_summary}"
                if num == "12" and subject_count:
                    section_entry["narrative_summary"] = (
                        f"Subject disposition and demographics based on SDTM DM domain "
                        f"({subject_count} subjects) and TLF tables {', '.join(r['table_id'] for r in refs)}."
                    )
                if num == "13":
                    section_entry["narrative_summary"] = (
                        f"Efficacy results per SAP primary endpoint ({primary_endpoint}) "
                        f"supported by TLF tables: {ref_summary}."
                    )
                if num == "14":
                    section_entry["narrative_summary"] = (
                        f"Safety evaluation integrated from ADaM datasets "
                        f"({', '.join(d.get('dataset', '?') for d in adam_datasets[:5])}) "
                        f"and TLF safety tables."
                    )
            sections.append(section_entry)

        tlf_integration = [
            {
                "table_id": t.get("id"),
                "csr_section": (
                    "14"
                    if "safety" in t.get("title", "").lower()
                    else "13"
                    if "efficacy" in t.get("title", "").lower()
                    else "12"
                ),
                "insertion_note": f"Insert {t.get('id')} per TLF specification",
            }
            for t in merged_tables
        ]

        csr_title = (
            data_cut.csr_title(study.name) if data_cut else f"{study.name} — Clinical Study Report"
        )
        content = {
            "document_type": "CSR",
            "version": "1.0",
            "ich_e3_compliant": True,
            "shell_only": False,
            "title": csr_title,
            "study_identification": {
                "protocol_number": study.protocol_number,
                "sponsor": getattr(study, "sponsor", None) or "Sponsor",
                "phase": str(getattr(study, "phase", None) or "Not specified"),
                "indication": getattr(study, "indication", None) or "Not specified",
            },
            "data_source_metadata": data_cut.to_dict() if data_cut else None,
            "synopsis": {
                "objectives": objectives or "See Section 10",
                "design": str(design),
                "population": sap_content.get("analysis_populations", ["ITT"])[0]
                if isinstance(sap_content.get("analysis_populations"), list)
                else "Intent-to-treat population per SAP",
                "treatments": protocol_content.get("treatments", []),
                "primary_results": (
                    f"Primary endpoint ({primary_endpoint}) results integrated from "
                    f"TLF tables {[t.get('id') for t in merged_tables if 'efficacy' in t.get('title', '').lower() or t.get('section', '').startswith('13')] or [t.get('id') for t in merged_tables[:2]]}."
                ),
                "safety_summary": (
                    f"Safety findings from SDTM domains "
                    f"({', '.join(d.get('domain', '?') for d in sdtm_domains[:6])}) "
                    "and TLF safety tables in Section 14."
                ),
                "conclusions": (
                    "Integrated benefit-risk assessment based on available TLF and ADaM outputs "
                    "for this data cut. Medical writer review required before submission."
                ),
                "interim_notice": interim_notice or None,
                "synthetic_notice": synthetic_notice or None,
            },
            "sections": sections,
            "appendices": [
                "Protocol and amendments",
                "Statistical Analysis Plan",
                "SDTM datasets",
                "ADaM analysis datasets",
                "TLF outputs",
            ],
            "tlf_integration": tlf_integration,
            "source_tlf_artifact_ids": [str(i) for i in tlf_artifact_ids],
            "source_sdtm_artifact_ids": [
                str(upstream["sdtm_artifact"].id) if upstream.get("sdtm_artifact") else None
            ],
            "source_adam_artifact_ids": [
                str(upstream["adam_artifact"].id) if upstream.get("adam_artifact") else None
            ],
            "upstream_evidence": {
                "sdtm_domain_count": len(sdtm_domains),
                "adam_dataset_count": len(adam_datasets),
                "tlf_table_count": len(merged_tables),
                "subject_count": subject_count,
            },
            "ectd_module_5": {
                "ready": bool(sdtm_domains and adam_datasets and merged_tables),
                "folder_structure": [
                    "m5/datasets/tabulation/sdtm",
                    "m5/datasets/analysis/adam",
                    "m5/clinical-study-reports",
                ],
                "notes": "CSR assembled from locked upstream artifacts for the selected data cut.",
            },
            "estimated_total_word_count": max(8000, len(merged_tables) * 1500),
            "regulatory_references": [
                "ICH E3",
                "FDA Module 5 Guidance",
                "EMA Clinical Study Reports Guideline",
            ],
        }
        if data_cut:
            content = data_cut.embed_in_content(content)
        for section in content.get("sections", []):
            text_blob = json.dumps(section, default=str)
            if contains_shell_placeholder(text_blob):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "CSR_SHELL_BLOCKED",
                        "message": _CSR_BLOCKED_MESSAGE,
                    },
                )
        return content

    async def regenerate_section_prose(
        self,
        csr_artifact_id: UUID,
        section_id: str,
        actor: User,
        instructions: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, UUID]:
        """Regenerate prose for a single CSR section without rebuilding the full CSR."""
        check_permission(actor, Permission.ARTIFACT_CREATE)

        artifact = await self._artifact_repo.get_by_id(
            csr_artifact_id, actor.organization_id
        )
        if artifact.artifact_type != ArtifactType.CSR:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "NOT_CSR", "message": "Artifact must be CSR."},
            )

        content = await self._load_artifact_content(artifact)
        section = self._find_section(content, section_id)
        if section is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "SECTION_NOT_FOUND",
                    "message": f"CSR section '{section_id}' not found.",
                },
            )

        study = await self._study_repo.get(artifact.study_id, actor.organization_id)
        study_artifacts = await self._load_study_context_artifacts(
            artifact.study_id, actor.organization_id
        )
        protocol_content: dict = {}
        sap_content: dict = {}
        if study_artifacts.get("PROTOCOL"):
            protocol_content = await self._load_artifact_content(
                study_artifacts["PROTOCOL"]
            )
        if study_artifacts.get("SAP"):
            sap_content = await self._load_artifact_content(study_artifacts["SAP"])

        tlf_contents: list[dict] = []
        tlf_artifacts: list[Artifact] = []
        for raw_id in content.get("source_tlf_artifact_ids", []):
            try:
                tlf_id = UUID(str(raw_id))
            except ValueError:
                continue
            try:
                tlf_art = await self._artifact_repo.get_by_id(
                    tlf_id, actor.organization_id
                )
            except HTTPException:
                continue
            if tlf_art.artifact_type != ArtifactType.TLF:
                continue
            tlf_artifacts.append(tlf_art)
            tlf_contents.append(await self._load_artifact_content(tlf_art))

        merged_tables = self._merge_tlf_tables(tlf_contents)
        prose, decision_id = await self._generate_section_prose(
            actor=actor,
            study=study,
            section=section,
            merged_tables=merged_tables,
            protocol_content=protocol_content,
            sap_content=sap_content,
            tlf_content=tlf_contents[0] if tlf_contents else {},
            instructions=instructions,
        )

        section["prose"] = prose
        section["ai_decision_id"] = str(decision_id)
        section["status"] = "DRAFT"
        content["sections"] = [
            section if str(s.get("number")) == str(section_id) else s
            for s in content.get("sections", [])
        ]

        await self._artifact_svc.update_artifact_content(
            csr_artifact_id,
            actor.organization_id,
            actor,
            content,
            change_summary=f"Regenerated CSR Section {section_id} prose",
        )

        if tlf_artifacts:
            tlf_node = await self._graph.find_node_for_domain_record(
                tlf_artifacts[0].id, "tlf_artifact", actor.organization_id
            ) or await self._graph.find_node_for_domain_record(
                tlf_artifacts[0].id, "artifact", actor.organization_id
            )
            csr_node = await self._graph.find_node_for_domain_record(
                artifact.id, "csr_artifact", actor.organization_id
            )
            await self._lineage.record_field_lineage(
                organization_id=actor.organization_id,
                lineage_type=DataLineageType.DERIVED,
                source_type="tlf_artifact",
                source_id=tlf_artifacts[0].id,
                source_field=section_id,
                target_type="csr_section",
                target_id=artifact.id,
                target_field=section_id,
                target_domain=section.get("title", f"Section {section_id}"),
                transformation_logic=(
                    f"Regenerated CSR Section {section_id} prose from TLF package"
                ),
                is_ai_generated=True,
                ai_decision_id=decision_id,
                study_id=artifact.study_id,
                created_by=actor,
                source_graph_node_id=tlf_node.id if tlf_node else None,
                target_graph_node_id=csr_node.id if csr_node else None,
            )

        await self._audit.log(
            action=AuditAction.AI_GENERATION_COMPLETED,
            resource_type="csr_section",
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            resource_id=artifact.id,
            after_state={
                "artifact_id": str(artifact.id),
                "section_id": section_id,
                "ai_decision_id": str(decision_id),
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return prose, decision_id

    @staticmethod
    def _study_context_dict(study) -> dict:
        return {
            "name": study.name,
            "protocol_number": study.protocol_number,
            "sponsor": getattr(study, "sponsor", None),
            "phase": str(getattr(study, "phase", None) or ""),
            "indication": getattr(study, "indication", None),
        }

    @staticmethod
    def _find_section(content: dict, section_id: str) -> dict | None:
        for section in content.get("sections", []):
            if str(section.get("number")) == str(section_id):
                return section
        return None

    async def _enrich_sections_with_prose(
        self,
        *,
        actor: User,
        study,
        content: dict,
        merged_tables: list[dict],
        protocol_content: dict,
        sap_content: dict,
        tlf_contents: list[dict],
    ) -> dict:
        enriched: list[dict] = []
        decision_ids: list[str] = []
        study_dict = self._study_context_dict(study)
        tlf_content = tlf_contents[0] if tlf_contents else {}

        for section in content.get("sections", []):
            section_id = str(section.get("number", ""))
            prose, decision_id = await self._generate_section_prose(
                actor=actor,
                study=study,
                section=section,
                merged_tables=merged_tables,
                protocol_content=protocol_content,
                sap_content=sap_content,
                tlf_content=tlf_content,
            )
            updated = dict(section)
            updated["prose"] = prose
            updated["ai_decision_id"] = str(decision_id)
            updated["status"] = "DRAFT"
            if updated.get("content_outline") and not updated.get("narrative_summary"):
                updated["narrative_summary"] = updated["content_outline"]
            enriched.append(updated)
            decision_ids.append(str(decision_id))

        content = dict(content)
        content["sections"] = enriched
        content["section_ai_decision_ids"] = decision_ids
        content["prose_generated"] = True
        return content

    async def _generate_section_prose(
        self,
        *,
        actor: User,
        study,
        section: dict,
        merged_tables: list[dict],
        protocol_content: dict,
        sap_content: dict,
        tlf_content: dict,
        instructions: str | None = None,
    ) -> tuple[str, UUID]:
        section_id = str(section.get("number", ""))
        context = assemble_context(
            section_id=section_id,
            study=self._study_context_dict(study),
            protocol_content=protocol_content,
            sap_content=sap_content,
            merged_tables=merged_tables,
            tlf_content=tlf_content,
            section_entry=section,
            instructions=instructions,
        )
        decision = await self._ai_decision.begin_decision(
            organization_id=actor.organization_id,
            agent_name=_PROSE_AGENT_NAME,
            decision_type="CSR_SECTION_PROSE",
            study_id=study.id,
            model_id=_MODEL_ID,
            input_context={"section_id": section_id, "context": context},
        )
        prose = await CSRGenerator.generate_section_prose(
            section_id,
            context,
            api_key=self._settings.ANTHROPIC_API_KEY,
            model_id=_MODEL_ID,
        )
        await self._ai_decision.complete_decision(
            decision=decision,
            output={
                "section_id": section_id,
                "prose_preview": prose[:500],
                "prose_length": len(prose),
            },
            reasoning=f"Generated ICH E3 prose for CSR Section {section_id}",
            confidence=0.8,
        )
        return prose, decision.id

    async def _record_section_prose_lineage(
        self,
        *,
        tlf_artifact: Artifact,
        csr_artifact: Artifact,
        csr_content: dict,
        actor: User,
        ai_decision_id: UUID,
    ) -> None:
        tlf_node = await self._graph.find_node_for_domain_record(
            tlf_artifact.id, "tlf_artifact", actor.organization_id
        )
        csr_node = await self._graph.find_node_for_domain_record(
            csr_artifact.id, "csr_artifact", actor.organization_id
        )
        for section in csr_content.get("sections", []):
            section_id = str(section.get("number", "?"))
            section_decision = section.get("ai_decision_id")
            decision_id = UUID(str(section_decision)) if section_decision else ai_decision_id
            await self._lineage.record_field_lineage(
                organization_id=actor.organization_id,
                lineage_type=DataLineageType.DERIVED,
                source_type="tlf_artifact",
                source_id=tlf_artifact.id,
                source_field=section_id,
                target_type="csr_section",
                target_id=csr_artifact.id,
                target_field=section_id,
                target_domain=section.get("title", f"Section {section_id}"),
                transformation_logic=(
                    f"CSR Section {section_id} prose derived from TLF package"
                ),
                is_ai_generated=True,
                ai_decision_id=decision_id,
                study_id=tlf_artifact.study_id,
                created_by=actor,
                source_graph_node_id=tlf_node.id if tlf_node else None,
                target_graph_node_id=csr_node.id if csr_node else None,
            )

    @staticmethod
    def _parse_json(text: str) -> dict:
        text = text.strip()
        fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if fence:
            text = fence.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "code": "AI_PARSE_ERROR",
                    "message": f"CSR agent returned invalid JSON: {exc}",
                },
            ) from exc

    async def _register_cip_links(
        self,
        *,
        tlf_artifact: Artifact,
        csr_artifact: Artifact,
        csr_content: dict,
        study_artifacts: dict[str, Artifact | None],
        actor: User,
        ai_decision_id: UUID,
    ) -> None:
        tlf_node, _ = await self._graph.register_domain_record(
            organization_id=actor.organization_id,
            node_type=GraphNodeType.TLF,
            external_id=tlf_artifact.id,
            external_type="tlf_artifact",
            label=tlf_artifact.name,
            study_id=tlf_artifact.study_id,
            properties={"artifact_id": str(tlf_artifact.id)},
            actor=actor,
        )
        csr_node, _ = await self._graph.register_domain_record(
            organization_id=actor.organization_id,
            node_type=GraphNodeType.CSR_SECTION,
            external_id=csr_artifact.id,
            external_type="csr_artifact",
            label=csr_artifact.name,
            study_id=tlf_artifact.study_id,
            properties={"artifact_id": str(csr_artifact.id)},
            actor=actor,
        )
        await self._graph.link_tlf_to_csr(
            org_id=actor.organization_id,
            study_id=tlf_artifact.study_id,
            tlf_node_id=tlf_node.id,
            csr_node_id=csr_node.id,
            is_ai_generated=True,
            ai_decision_id=ai_decision_id,
            actor=actor,
        )

        for section in csr_content.get("sections", []):
            sec_num = section.get("number", "?")
            sec_title = section.get("title", "Section")
            for ref in section.get("tlf_references", []):
                await self._lineage.record_field_lineage(
                    organization_id=actor.organization_id,
                    lineage_type=DataLineageType.DERIVED,
                    source_type="tlf_table",
                    source_id=tlf_artifact.id,
                    source_field=ref.get("table_id", ""),
                    target_type="csr_section",
                    target_id=csr_artifact.id,
                    target_field=sec_num,
                    target_domain=sec_title,
                    transformation_logic=(
                        f"TLF table {ref.get('table_id')} integrated into CSR §{sec_num}"
                    ),
                    is_ai_generated=True,
                    ai_decision_id=ai_decision_id,
                    study_id=tlf_artifact.study_id,
                    created_by=actor,
                    source_graph_node_id=tlf_node.id,
                    target_graph_node_id=csr_node.id,
                )

        protocol = study_artifacts.get("PROTOCOL")
        if protocol:
            proto_node, _ = await self._graph.register_domain_record(
                organization_id=actor.organization_id,
                node_type=GraphNodeType.PROTOCOL,
                external_id=protocol.id,
                external_type="artifact",
                label=protocol.name,
                study_id=tlf_artifact.study_id,
                actor=actor,
            )
            await self._graph.create_relationship(
                organization_id=actor.organization_id,
                source_node_id=csr_node.id,
                target_node_id=proto_node.id,
                edge_type=GraphEdgeType.DERIVED_FROM,
                study_id=tlf_artifact.study_id,
                is_ai_generated=True,
                ai_decision_id=ai_decision_id,
                actor=actor,
            )
