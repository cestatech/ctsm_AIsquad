"""CSR generation service — assemble ICH E3 Clinical Study Report from TLF + study artifacts.

Phase 7 pipeline: TLF artifact(s) + Protocol/SAP context → CSR artifact
→ context graph + section lineage → internal ICH E3 validation run.
"""

from __future__ import annotations

import json
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
from app.services.validation_service import ValidationService

_AGENT_NAME = "csr-generation-agent"
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
    study_id: UUID
    tlf_artifact_count: int
    protocol_artifact_count: int
    sap_artifact_count: int
    ready: bool
    issues: list[str]
    tlf_artifacts: list[dict]


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
        self, study_id: UUID, organization_id: UUID
    ) -> StudyCSRReadiness:
        """Return study-wide readiness for CSR assembly from TLF artifacts."""
        await self._study_repo.get(study_id, organization_id)
        artifacts, _ = await self._artifact_repo.list_by_study(
            study_id, organization_id, limit=100, offset=0
        )
        tlf_arts = [a for a in artifacts if a.artifact_type == ArtifactType.TLF]
        protocol_arts = [
            a for a in artifacts if a.artifact_type == ArtifactType.PROTOCOL
        ]
        sap_arts = [a for a in artifacts if a.artifact_type == ArtifactType.SAP]

        issues: list[str] = []
        summaries: list[dict] = []

        if not tlf_arts:
            issues.append("No TLF package artifacts found for this study.")

        for art in tlf_arts:
            content = await self._load_artifact_content(art)
            tables = content.get("tables", [])
            table_count = len(tables)
            art_ready = table_count > 0
            if not tables:
                issues.append(f"{art.name}: TLF package has no tables.")
            summaries.append({
                "artifact_id": str(art.id),
                "artifact_name": art.name,
                "table_count": table_count,
                "tables": [t.get("id", "?") for t in tables],
                "ready": art_ready,
            })

        ready = bool(summaries) and all(s["ready"] for s in summaries)
        return StudyCSRReadiness(
            study_id=study_id,
            tlf_artifact_count=len(tlf_arts),
            protocol_artifact_count=len(protocol_arts),
            sap_artifact_count=len(sap_arts),
            ready=ready and len(issues) == 0,
            issues=issues[:30],
            tlf_artifacts=summaries,
        )

    async def generate_from_tlf_artifact(
        self,
        tlf_artifact_id: UUID,
        actor: User,
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
        study_artifacts = await self._load_study_context_artifacts(
            study.id, actor.organization_id
        )

        return await self._run_generation(
            actor=actor,
            study=study,
            tlf_artifacts=[tlf_artifact],
            tlf_contents=[tlf_content],
            study_artifacts=study_artifacts,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def generate_from_study(
        self,
        study_id: UUID,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> CSRGenerationResult:
        """Merge all study TLF artifacts into one CSR package."""
        check_permission(actor, Permission.ARTIFACT_CREATE)

        readiness = await self.get_study_readiness(study_id, actor.organization_id)
        if not readiness.ready:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "STUDY_NOT_READY",
                    "message": "Study must have TLF artifacts with table specifications.",
                    "issues": readiness.issues,
                },
            )

        study = await self._study_repo.get(study_id, actor.organization_id)
        artifacts, _ = await self._artifact_repo.list_by_study(
            study_id, actor.organization_id, limit=100, offset=0
        )
        tlf_arts = [a for a in artifacts if a.artifact_type == ArtifactType.TLF]
        tlf_contents = [
            await self._load_artifact_content(a) for a in tlf_arts
        ]
        study_artifacts = await self._load_study_context_artifacts(
            study_id, actor.organization_id
        )

        return await self._run_generation(
            actor=actor,
            study=study,
            tlf_artifacts=tlf_arts,
            tlf_contents=tlf_contents,
            study_artifacts=study_artifacts,
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
        ip_address: str | None,
        user_agent: str | None,
    ) -> CSRGenerationResult:
        tlf_ids = [a.id for a in tlf_artifacts]
        context_ids = [
            a.id for a in study_artifacts.values() if a is not None
        ]
        merged_tables = self._merge_tlf_tables(tlf_contents)

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
            },
        )

        content = await self._build_csr_content(
            study=study,
            merged_tables=merged_tables,
            tlf_artifact_ids=tlf_ids,
            study_artifacts=study_artifacts,
        )

        artifact = await self._artifact_svc.create_artifact(
            organization_id=actor.organization_id,
            study_id=study.id,
            user=actor,
            artifact_type=ArtifactType.CSR,
            name=f"{study.name} — Clinical Study Report",
            description=(
                "AI-assembled ICH E3 CSR from TLF specifications and study artifacts"
            ),
            content=content,
            change_summary=(
                f"CSR assembly from {len(tlf_ids)} TLF artifact(s)"
            ),
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
        await self._link_study_traceability(
            study_id=study_id,
            artifact=artifact,
            actor=actor,
            ai_decision_id=decision.id,
        )

        await self._ai_decision.complete_decision(
            decision=decision,
            output={
                "artifact_id": str(artifact.id),
                "sections": [s["number"] for s in content.get("sections", [])],
                "source_tlf_artifact_ids": [str(a.id) for a in tlf_artifacts],
            },
            reasoning=(
                f"Assembled ICH E3 CSR with {len(content.get('sections', []))} sections "
                f"from {len(merged_tables)} TLF table(s)"
            ),
            confidence=0.82,
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
    ) -> dict:
        protocol = study_artifacts.get("PROTOCOL")
        sap = study_artifacts.get("SAP")
        protocol_content: dict = {}
        sap_content: dict = {}
        if protocol:
            protocol_content = await self._load_artifact_content(protocol)
        if sap:
            sap_content = await self._load_artifact_content(sap)

        if self._client:
            try:
                return await self._call_claude(
                    study=study,
                    merged_tables=merged_tables,
                    protocol_content=protocol_content,
                    sap_content=sap_content,
                    tlf_artifact_ids=tlf_artifact_ids,
                )
            except HTTPException:
                raise
            except Exception:
                pass

        return self._deterministic_csr(
            study=study,
            merged_tables=merged_tables,
            protocol_content=protocol_content,
            sap_content=sap_content,
            tlf_artifact_ids=tlf_artifact_ids,
        )

    async def _call_claude(
        self,
        *,
        study,
        merged_tables: list[dict],
        protocol_content: dict,
        sap_content: dict,
        tlf_artifact_ids: list[UUID],
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
    ) -> dict:
        """Build ICH E3 CSR shell without AI — maps TLF tables to sections."""
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
                section_entry["content_outline"] = (
                    f"{outline}. Incorporates TLF tables: "
                    + ", ".join(r["table_id"] for r in refs)
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

        return {
            "document_type": "CSR",
            "version": "1.0",
            "ich_e3_compliant": True,
            "title": f"{study.name} — Clinical Study Report",
            "study_identification": {
                "protocol_number": study.protocol_number,
                "sponsor": getattr(study, "sponsor", None) or "Sponsor",
                "phase": str(getattr(study, "phase", None) or "Not specified"),
                "indication": getattr(study, "indication", None) or "Not specified",
            },
            "synopsis": {
                "objectives": objectives or "See Section 10",
                "design": str(design),
                "population": sap_content.get("analysis_populations", ["ITT"])[0]
                if isinstance(sap_content.get("analysis_populations"), list)
                else "Intent-to-treat population per SAP",
                "treatments": protocol_content.get("treatments", []),
                "primary_results": f"Primary endpoint: {primary_endpoint} — see Section 13",
                "safety_summary": "See Section 14 and integrated TLF safety tables",
                "conclusions": "Draft — pending medical writer review",
            },
            "sections": sections,
            "appendices": [
                "Protocol and amendments",
                "Statistical Analysis Plan",
                "Patient data listings",
                "TLF outputs",
                "Investigators and study sites",
            ],
            "tlf_integration": tlf_integration,
            "source_tlf_artifact_ids": [str(i) for i in tlf_artifact_ids],
            "ectd_module_5": {
                "ready": False,
                "folder_structure": [
                    "m5/datasets/tabulation/sdtm",
                    "m5/datasets/analysis/adam",
                    "m5/clinical-study-reports",
                    "m5/clinical-study-reports/efficacy",
                    "m5/clinical-study-reports/safety",
                ],
                "notes": (
                    "CSR shell assembled — finalize after TLF lock and "
                    "regulatory review. Not submission-ready."
                ),
            },
            "estimated_total_word_count": 25000,
            "regulatory_references": [
                "ICH E3",
                "FDA Module 5 Guidance",
                "EMA Clinical Study Reports Guideline",
            ],
        }

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

    async def _link_study_traceability(
        self,
        *,
        study_id: UUID,
        artifact: Artifact,
        actor: User,
        ai_decision_id: UUID,
    ) -> None:
        study = await self._study_repo.get(study_id, actor.organization_id)
        study_node, _ = await self._graph.register_domain_record(
            organization_id=actor.organization_id,
            node_type=GraphNodeType.STUDY,
            external_id=study_id,
            external_type="study",
            label=study.name,
            study_id=study_id,
            actor=actor,
        )
        csr_node, _ = await self._graph.register_domain_record(
            organization_id=actor.organization_id,
            node_type=GraphNodeType.CSR_SECTION,
            external_id=artifact.id,
            external_type="csr_artifact",
            label=artifact.name,
            study_id=study_id,
            properties={"artifact_id": str(artifact.id)},
            actor=actor,
        )
        await self._graph.create_relationship(
            organization_id=actor.organization_id,
            source_node_id=csr_node.id,
            target_node_id=study_node.id,
            edge_type=GraphEdgeType.PART_OF,
            study_id=study_id,
            is_ai_generated=True,
            ai_decision_id=ai_decision_id,
            actor=actor,
        )
