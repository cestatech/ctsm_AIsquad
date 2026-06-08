"""SDTM generation service — derive SDTM domains from approved raw field mappings.

Phase 4 pipeline: approved RawField mappings → AI-assisted SDTM dataset artifact
→ context graph + field lineage → internal CDISC validation run.

Pinnacle 21 is not required; validation uses engine=internal.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
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
from app.models.raw_data import RawDataset, RawField
from app.models.user import User
from app.models.validation import ValidationRun
from app.repositories.artifact_repository import ArtifactRepository
from app.repositories.raw_data_repository import RawDatasetRepository, RawFieldRepository
from app.repositories.study_repository import StudyRepository
from app.repositories.upload_repository import UploadRepository
from app.schemas.validation import ValidationRunCreate
from app.services.artifact_service import ArtifactService
from app.services.audit_service import AuditService
from app.services.context_graph_service import ContextGraphService
from app.services.intelligence_service import AIDecisionService, DataLineageService
from app.services.mapping_service import MappingService
from app.services.upload_service import UploadService
from app.services.dual_programmer_qc_service import DualProgrammerQCService
from app.services.validation_service import ValidationService
from app.models.statistical_qc import StatisticalQCWorkflow

_AGENT_NAME = "sdtm-derivation-agent"
_MODEL_ID = "claude-sonnet-4-20250514"
_MAX_ROWS = 5000

_SYSTEM_PROMPT = """You are a CDISC SDTM expert. Transform raw clinical data rows into SDTM IG 3.3 domain datasets.

Given approved column→SDTM variable mappings and sample raw rows, produce SDTM domain content.

Rules:
- Group variables by SDTM domain (prefix before the dot, e.g. DM.USUBJID → domain DM)
- Include standard required variables per domain where derivable (STUDYID, DOMAIN, USUBJID)
- Apply simple 1:1 mappings directly; document transforms in transformation_notes
- Return ONLY valid JSON matching the schema below

Schema:
{
  "domains": [
    {
      "domain": "DM",
      "domain_label": "Demographics",
      "class": "Special-Purpose",
      "variables": ["STUDYID", "DOMAIN", "USUBJID", "..."],
      "observations": [{"STUDYID": "...", "DOMAIN": "DM", "USUBJID": "...", ...}],
      "transformation_notes": ["<note>"]
    }
  ],
  "derived_variables": [
    {"variable": "DM.USUBJID", "logic": "<formula or description>"}
  ]
}"""


@dataclass
class StudySDTMReadiness:
    study_id: UUID
    dataset_count: int
    total_fields: int
    approved_fields: int
    ready: bool
    issues: list[str]
    datasets: list[dict]


@dataclass
class SDTMGenerationResult:
    artifact: Artifact
    ai_decision_id: UUID
    validation_run: ValidationRun
    domain_count: int
    source_dataset_ids: list[UUID]


class SDTMGenerationService:
    """Generate SDTM dataset artifacts from approved raw field mappings."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._ds_repo = RawDatasetRepository(db)
        self._field_repo = RawFieldRepository(db)
        self._upload_repo = UploadRepository(db)
        self._study_repo = StudyRepository(db)
        self._mapping = MappingService(db)
        self._artifact_svc = ArtifactService(db)
        self._ai_decision = AIDecisionService(db)
        self._graph = ContextGraphService(db)
        self._lineage = DataLineageService(db)
        self._validation = ValidationService(db)
        self._audit = AuditService(db)
        self._artifact_repo = ArtifactRepository(db)
        settings = get_settings()
        self._settings = settings
        self._client = (
            anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            if settings.ANTHROPIC_API_KEY
            else None
        )

    async def generate_from_dataset(
        self,
        dataset_id: UUID,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> SDTMGenerationResult:
        """Derive SDTM domains from a dataset with fully approved mappings."""
        check_permission(actor, Permission.ARTIFACT_CREATE)

        dataset = await self._get_dataset(dataset_id, actor.organization_id)
        fields = await self._field_repo.list_for_dataset(
            dataset_id, actor.organization_id
        )
        self._assert_ready_for_generation(fields)

        upload = await self._upload_repo.get_by_id(
            dataset.uploaded_file_id, actor.organization_id
        )
        if upload is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Source upload not found."},
            )

        study = await self._study_repo.get(dataset.study_id, actor.organization_id)
        raw_rows = self._load_dataset_rows(upload=upload, dataset=dataset, fields=fields)

        decision = await self._ai_decision.begin_decision(
            organization_id=actor.organization_id,
            agent_name=_AGENT_NAME,
            decision_type="SDTM_DERIVATION",
            study_id=dataset.study_id,
            model_id=_MODEL_ID,
            input_context={
                "dataset_id": str(dataset_id),
                "dataset_name": dataset.dataset_name,
                "field_count": len(fields),
                "row_count": len(raw_rows),
            },
        )

        content = await self._build_sdtm_content(
            dataset=dataset,
            fields=fields,
            raw_rows=raw_rows,
            study_name=study.name,
            protocol_number=study.protocol_number,
        )

        artifact = await self._artifact_svc.create_artifact(
            organization_id=actor.organization_id,
            study_id=dataset.study_id,
            user=actor,
            artifact_type=ArtifactType.SDTM_DATASET,
            name=f"{study.name} — SDTM ({dataset.dataset_name})",
            description=(
                f"AI-derived SDTM IG {self._settings.SDTM_IG_VERSION} dataset "
                f"from raw upload '{upload.original_filename}'"
            ),
            content=content,
            change_summary=f"SDTM derivation from dataset {dataset.dataset_name}",
        )

        return await self._finalize_generation(
            actor=actor,
            study_id=dataset.study_id,
            artifact=artifact,
            decision=decision,
            content=content,
            datasets_fields=[(dataset, fields)],
            source_dataset_ids=[dataset.id],
            audit_dataset_id=dataset_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def get_study_readiness(
        self, study_id: UUID, organization_id: UUID
    ) -> StudySDTMReadiness:
        """Return study-wide mapping readiness for SDTM generation."""
        datasets = await self._ds_repo.list_for_study(study_id, organization_id)
        issues: list[str] = []
        dataset_summaries: list[dict] = []
        total_fields = 0
        approved_fields = 0

        if not datasets:
            issues.append("No parsed datasets found for this study.")

        for ds in datasets:
            fields = await self._field_repo.list_for_dataset(ds.id, organization_id)
            ds_total = len(fields)
            ds_approved = sum(1 for f in fields if f.mapping_status == "APPROVED")
            total_fields += ds_total
            approved_fields += ds_approved
            ds_issues: list[str] = []
            for f in fields:
                if f.mapping_status != "APPROVED":
                    ds_issues.append(
                        f"{ds.dataset_name}/{f.column_name}: {f.mapping_status}"
                    )
                elif not f.mapped_sdtm_variable_id:
                    ds_issues.append(
                        f"{ds.dataset_name}/{f.column_name}: missing SDTM variable"
                    )
            issues.extend(ds_issues[:5])
            dataset_summaries.append({
                "dataset_id": str(ds.id),
                "dataset_name": ds.dataset_name,
                "total_fields": ds_total,
                "approved_fields": ds_approved,
                "ready": ds_total > 0 and ds_approved == ds_total
                and all(f.mapped_sdtm_variable_id for f in fields),
            })

        ready = bool(datasets) and bool(dataset_summaries) and all(
            d["ready"] for d in dataset_summaries
        )
        if total_fields > 0 and approved_fields < total_fields:
            issues.insert(0, f"{total_fields - approved_fields} field(s) not yet approved.")

        return StudySDTMReadiness(
            study_id=study_id,
            dataset_count=len(datasets),
            total_fields=total_fields,
            approved_fields=approved_fields,
            ready=ready and len(issues) == 0,
            issues=issues[:30],
            datasets=dataset_summaries,
        )

    async def generate_from_study(
        self,
        study_id: UUID,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> SDTMGenerationResult:
        """Merge all study datasets into one SDTM artifact (full-study scope)."""
        check_permission(actor, Permission.ARTIFACT_CREATE)

        readiness = await self.get_study_readiness(study_id, actor.organization_id)
        if not readiness.ready:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "STUDY_NOT_READY",
                    "message": "All datasets must have fully approved SDTM mappings.",
                    "issues": readiness.issues,
                },
            )

        study = await self._study_repo.get(study_id, actor.organization_id)
        datasets = await self._ds_repo.list_for_study(study_id, actor.organization_id)
        datasets_fields: list[tuple[RawDataset, list[RawField]]] = []
        merged_domains: list[dict] = []
        merged_derived: list[dict] = []
        total_rows = 0
        total_mappings = 0
        source_ids: list[UUID] = []

        for dataset in datasets:
            fields = await self._field_repo.list_for_dataset(
                dataset.id, actor.organization_id
            )
            self._assert_ready_for_generation(fields)
            upload = await self._upload_repo.get_by_id(
                dataset.uploaded_file_id, actor.organization_id
            )
            if upload is None:
                continue
            raw_rows = self._load_dataset_rows(
                upload=upload, dataset=dataset, fields=fields
            )
            partial = await self._build_sdtm_content(
                dataset=dataset,
                fields=fields,
                raw_rows=raw_rows,
                study_name=study.name,
                protocol_number=study.protocol_number,
            )
            merged_domains = self._merge_domains(
                merged_domains, partial.get("domains", [])
            )
            merged_derived.extend(partial.get("derived_variables", []))
            total_rows += partial.get("row_count", 0)
            total_mappings += partial.get("mapping_count", 0)
            source_ids.append(dataset.id)
            datasets_fields.append((dataset, fields))

        decision = await self._ai_decision.begin_decision(
            organization_id=actor.organization_id,
            agent_name=_AGENT_NAME,
            decision_type="SDTM_STUDY_DERIVATION",
            study_id=study_id,
            model_id=_MODEL_ID,
            input_context={
                "study_id": str(study_id),
                "dataset_count": len(datasets),
                "source_dataset_ids": [str(i) for i in source_ids],
            },
        )

        content = {
            "document_type": "SDTM_DATASET",
            "sdtm_ig_version": self._settings.SDTM_IG_VERSION,
            "source_dataset_ids": [str(i) for i in source_ids],
            "scope": "full_study",
            "study_name": study.name,
            "protocol_number": study.protocol_number,
            "validation_engine": "internal",
            "pinnacle21_ready": self._settings.pinnacle21_configured,
            "define_xml_version": "2.1",
            "domains": merged_domains,
            "derived_variables": merged_derived,
            "row_count": total_rows,
            "mapping_count": total_mappings,
        }

        artifact = await self._artifact_svc.create_artifact(
            organization_id=actor.organization_id,
            study_id=study_id,
            user=actor,
            artifact_type=ArtifactType.SDTM_DATASET,
            name=f"{study.name} — SDTM Full Study Package",
            description=(
                f"AI-derived SDTM IG {self._settings.SDTM_IG_VERSION} — "
                f"{len(source_ids)} dataset(s) merged"
            ),
            content=content,
            change_summary=f"Study-level SDTM merge from {len(source_ids)} datasets",
        )

        return await self._finalize_generation(
            actor=actor,
            study_id=study_id,
            artifact=artifact,
            decision=decision,
            content=content,
            datasets_fields=datasets_fields,
            source_dataset_ids=source_ids,
            audit_dataset_id=study_id,
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
        datasets_fields: list[tuple[RawDataset, list[RawField]]],
        source_dataset_ids: list[UUID],
        audit_dataset_id: UUID,
        ip_address: str | None,
        user_agent: str | None,
    ) -> SDTMGenerationResult:
        for dataset, fields in datasets_fields:
            await self._register_cip_links(
                dataset=dataset,
                fields=fields,
                artifact=artifact,
                actor=actor,
                ai_decision_id=decision.id,
            )
        await self._link_study_traceability(
            study_id=study_id,
            artifact=artifact,
            actor=actor,
            ai_decision_id=decision.id,
        )

        field_count = sum(len(f) for _, f in datasets_fields)
        await self._ai_decision.complete_decision(
            decision=decision,
            output={
                "artifact_id": str(artifact.id),
                "domains": [d["domain"] for d in content.get("domains", [])],
                "source_dataset_ids": [str(i) for i in source_dataset_ids],
            },
            reasoning=(
                f"Derived SDTM from {field_count} approved mappings "
                f"across {len(source_dataset_ids)} dataset(s)"
            ),
            confidence=0.85,
            output_artifact_ids=[artifact.id],
        )

        validation_run = await self._validation.trigger(
            body=ValidationRunCreate(
                artifact_id=artifact.id,
                artifact_version_id=artifact.current_version_id,
                engine="internal",
                rule_set_version=f"SDTM-IG-{self._settings.SDTM_IG_VERSION}",
            ),
            actor=actor,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self._audit.log(
            action=AuditAction.AI_GENERATION_COMPLETED,
            resource_type="sdtm_dataset",
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            resource_id=artifact.id,
            after_state={
                "dataset_id": str(audit_dataset_id),
                "artifact_id": str(artifact.id),
                "validation_run_id": str(validation_run.id),
                "ai_decision_id": str(decision.id),
                "source_dataset_ids": [str(i) for i in source_dataset_ids],
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        qc_svc = DualProgrammerQCService(self._db)
        await qc_svc.run_qc(
            workflow_step=StatisticalQCWorkflow.RAW_TO_SDTM,
            study_id=study_id,
            actor=actor,
            input_payload={
                "domains": content.get("domains", []),
                "protocol_number": content.get("protocol_number"),
            },
            output_artifact_id=artifact.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return SDTMGenerationResult(
            artifact=artifact,
            ai_decision_id=decision.id,
            validation_run=validation_run,
            domain_count=len(content.get("domains", [])),
            source_dataset_ids=source_dataset_ids,
        )

    @staticmethod
    def _merge_domains(existing: list[dict], incoming: list[dict]) -> list[dict]:
        """Merge SDTM domains by domain code, concatenating observations."""
        by_code: dict[str, dict] = {d["domain"]: dict(d) for d in existing}
        for domain in incoming:
            code = domain.get("domain", "UNK")
            if code not in by_code:
                by_code[code] = dict(domain)
                continue
            current = by_code[code]
            vars_set = set(current.get("variables", []))
            vars_set.update(domain.get("variables", []))
            current["variables"] = sorted(vars_set)
            current["observations"] = (
                current.get("observations", []) + domain.get("observations", [])
            )
            notes = current.get("transformation_notes", [])
            notes.extend(domain.get("transformation_notes", []))
            current["transformation_notes"] = list(dict.fromkeys(notes))
        return list(by_code.values())

    def _load_dataset_rows(
        self,
        *,
        upload,
        dataset: RawDataset,
        fields: list[RawField],
    ) -> list[dict]:
        """Load raw rows from storage, JSON export, or profiled field samples."""
        raw_rows = UploadService.read_tabular_rows(
            file_path=upload.file_path,
            mime_type=upload.mime_type,
            filename=upload.original_filename,
            dataset_name=dataset.dataset_name,
            max_rows=_MAX_ROWS,
            storage_root=self._settings.STORAGE_LOCAL_PATH,
        )
        if raw_rows:
            return raw_rows

        raw_rows = UploadService.reconstruct_rows_from_fields(
            fields,
            dataset.row_count,
            max_rows=_MAX_ROWS,
        )
        if raw_rows:
            return raw_rows

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "NO_RAW_ROWS",
                "message": (
                    f"No raw data rows could be loaded for dataset "
                    f"'{dataset.dataset_name}'. Re-upload the source CSV/XLSX "
                    "or ensure the stored file exists."
                ),
            },
        )

    async def _get_dataset(
        self, dataset_id: UUID, organization_id: UUID
    ) -> RawDataset:
        ds = await self._ds_repo.get(dataset_id, organization_id)
        if ds is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Dataset not found."},
            )
        return ds

    @staticmethod
    def _assert_ready_for_generation(fields: list[RawField]) -> None:
        if not fields:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "NO_FIELDS",
                    "message": "Dataset has no parsed fields.",
                },
            )

        issues: list[str] = []
        for f in fields:
            if f.mapping_status != "APPROVED":
                issues.append(
                    f"Column '{f.column_name}' mapping status is {f.mapping_status}."
                )
            elif not f.mapped_sdtm_variable_id:
                issues.append(
                    f"Column '{f.column_name}' has no approved SDTM variable."
                )

        if issues:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "MAPPINGS_NOT_READY",
                    "message": "All columns must have APPROVED SDTM mappings before generation.",
                    "issues": issues[:20],
                },
            )

    async def _build_sdtm_content(
        self,
        *,
        dataset: RawDataset,
        fields: list[RawField],
        raw_rows: list[dict],
        study_name: str,
        protocol_number: str,
    ) -> dict:
        mapping_spec = [
            {
                "column_name": f.column_name,
                "sdtm_variable": f.mapped_sdtm_variable_id,
                "ecrf_field": f.mapped_ecrf_field_id,
                "inferred_type": f.inferred_type,
            }
            for f in fields
            if f.mapped_sdtm_variable_id
        ]

        if self._client:
            ai_domains = await self._call_claude(
                study_name=study_name,
                protocol_number=protocol_number,
                mapping_spec=mapping_spec,
                raw_rows=raw_rows[:50],
            )
        else:
            ai_domains = self._deterministic_domains(
                mapping_spec=mapping_spec,
                raw_rows=raw_rows,
                protocol_number=protocol_number,
            )

        obs_count = sum(
            len(d.get("observations", [])) for d in ai_domains.get("domains", [])
        )
        if obs_count == 0 and raw_rows:
            ai_domains = self._deterministic_domains(
                mapping_spec=mapping_spec,
                raw_rows=raw_rows,
                protocol_number=protocol_number,
            )

        return {
            "document_type": "SDTM_DATASET",
            "sdtm_ig_version": self._settings.SDTM_IG_VERSION,
            "source_dataset_id": str(dataset.id),
            "source_dataset_name": dataset.dataset_name,
            "study_name": study_name,
            "protocol_number": protocol_number,
            "validation_engine": "internal",
            "pinnacle21_ready": self._settings.pinnacle21_configured,
            "define_xml_version": "2.1",
            "domains": ai_domains.get("domains", []),
            "derived_variables": ai_domains.get("derived_variables", []),
            "row_count": len(raw_rows),
            "mapping_count": len(mapping_spec),
        }

    async def _call_claude(
        self,
        *,
        study_name: str,
        protocol_number: str,
        mapping_spec: list[dict],
        raw_rows: list[dict],
    ) -> dict:
        user_prompt = f"""Study: {study_name}
Protocol: {protocol_number}
SDTM IG: {self._settings.SDTM_IG_VERSION}

Approved mappings:
{json.dumps(mapping_spec, indent=2)}

Sample raw rows (max 50):
{json.dumps(raw_rows, indent=2, default=str)}

Generate SDTM domain datasets with observations transformed from the raw rows."""

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
        return self._parse_json(text)

    @staticmethod
    def _deterministic_domains(
        *,
        mapping_spec: list[dict],
        raw_rows: list[dict],
        protocol_number: str,
    ) -> dict:
        """Fallback when no API key — direct column copy into SDTM domains."""
        domain_vars: dict[str, set[str]] = {}
        col_to_var: dict[str, str] = {}

        for m in mapping_spec:
            var = m["sdtm_variable"]
            if "." not in var:
                continue
            domain, variable = var.split(".", 1)
            domain_vars.setdefault(domain, set()).update(
                ["STUDYID", "DOMAIN", variable]
            )
            col_to_var[m["column_name"]] = variable
            if domain == "DM":
                domain_vars[domain].add("USUBJID")

        domains_out = []
        for domain, variables in sorted(domain_vars.items()):
            obs_list = []
            for i, row in enumerate(raw_rows):
                obs: dict[str, str] = {
                    "STUDYID": protocol_number,
                    "DOMAIN": domain,
                }
                if domain == "DM":
                    obs["USUBJID"] = f"{protocol_number}-{i + 1:04d}"
                for col, var in col_to_var.items():
                    if var in variables and col in row and row[col] is not None:
                        obs[var] = str(row[col])
                obs_list.append(obs)

            domains_out.append({
                "domain": domain,
                "domain_label": domain,
                "class": "General",
                "variables": sorted(variables),
                "observations": obs_list,
                "transformation_notes": ["Deterministic 1:1 column mapping (no AI)"],
            })

        return {"domains": domains_out, "derived_variables": []}

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
                    "message": f"SDTM agent returned invalid JSON: {exc}",
                },
            ) from exc

    async def _register_cip_links(
        self,
        *,
        dataset: RawDataset,
        fields: list[RawField],
        artifact: Artifact,
        actor: User,
        ai_decision_id: UUID,
    ) -> None:
        ds_node, _ = await self._graph.register_domain_record(
            organization_id=actor.organization_id,
            node_type=GraphNodeType.RAW_DATASET,
            external_id=dataset.id,
            external_type="raw_dataset",
            label=dataset.dataset_name,
            study_id=dataset.study_id,
            actor=actor,
        )
        art_node, _ = await self._graph.register_domain_record(
            organization_id=actor.organization_id,
            node_type=GraphNodeType.SDTM_DOMAIN,
            external_id=artifact.id,
            external_type="sdtm_artifact",
            label=artifact.name,
            study_id=dataset.study_id,
            properties={"artifact_id": str(artifact.id)},
            actor=actor,
        )
        await self._graph.create_relationship(
            organization_id=actor.organization_id,
            source_node_id=ds_node.id,
            target_node_id=art_node.id,
            edge_type=GraphEdgeType.DERIVED_FROM,
            study_id=dataset.study_id,
            is_ai_generated=True,
            ai_decision_id=ai_decision_id,
            actor=actor,
        )

        for field in fields:
            if not field.mapped_sdtm_variable_id:
                continue
            domain_code = field.mapped_sdtm_variable_id.split(".")[0]
            var_node, _ = await self._graph.register_domain_record(
                organization_id=actor.organization_id,
                node_type=GraphNodeType.SDTM_VARIABLE,
                external_id=field.id,
                external_type="sdtm_variable",
                label=field.mapped_sdtm_variable_id,
                study_id=dataset.study_id,
                properties={"domain": domain_code},
                actor=actor,
            )
            field_node, _ = await self._graph.register_domain_record(
                organization_id=actor.organization_id,
                node_type=GraphNodeType.RAW_DATA_FIELD,
                external_id=field.id,
                external_type="raw_field",
                label=field.column_name,
                study_id=dataset.study_id,
                actor=actor,
            )
            await self._graph.create_relationship(
                organization_id=actor.organization_id,
                source_node_id=field_node.id,
                target_node_id=var_node.id,
                edge_type=GraphEdgeType.MAPS_TO,
                study_id=dataset.study_id,
                is_ai_generated=True,
                ai_decision_id=ai_decision_id,
                actor=actor,
            )
            domain_part, var_part = (
                field.mapped_sdtm_variable_id.split(".", 1)
                if "." in field.mapped_sdtm_variable_id
                else ("", field.mapped_sdtm_variable_id)
            )
            await self._lineage.record_field_lineage(
                organization_id=actor.organization_id,
                lineage_type=DataLineageType.TRANSFORMED,
                source_type="raw_field",
                target_type="sdtm_variable",
                source_id=field.id,
                source_field=field.column_name,
                target_id=artifact.id,
                target_field=var_part,
                target_domain=domain_part,
                transformation_logic=(
                    f"Mapped raw column '{field.column_name}' → "
                    f"{field.mapped_sdtm_variable_id}"
                ),
                is_ai_generated=True,
                ai_decision_id=ai_decision_id,
                study_id=dataset.study_id,
                created_by=actor,
            )

            if field.mapped_ecrf_field_id:
                ecrf_node, _ = await self._graph.register_domain_record(
                    organization_id=actor.organization_id,
                    node_type=GraphNodeType.ECR_FIELD,
                    external_id=field.id,
                    external_type="ecr_field_name",
                    label=field.mapped_ecrf_field_id,
                    study_id=dataset.study_id,
                    properties={"ecr_field_name": field.mapped_ecrf_field_id},
                    actor=actor,
                )
                await self._graph.link_ecr_to_sdtm(
                    org_id=actor.organization_id,
                    ecr_node_id=ecrf_node.id,
                    sdtm_node_id=var_node.id,
                    study_id=dataset.study_id,
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
        """Link SDTM artifact to study and protocol for traceability chain."""
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
        sdtm_node, _ = await self._graph.register_domain_record(
            organization_id=actor.organization_id,
            node_type=GraphNodeType.SDTM_DOMAIN,
            external_id=artifact.id,
            external_type="sdtm_artifact",
            label=artifact.name,
            study_id=study_id,
            properties={"artifact_id": str(artifact.id)},
            actor=actor,
        )
        await self._graph.create_relationship(
            organization_id=actor.organization_id,
            source_node_id=sdtm_node.id,
            target_node_id=study_node.id,
            edge_type=GraphEdgeType.PART_OF,
            study_id=study_id,
            is_ai_generated=True,
            ai_decision_id=ai_decision_id,
            actor=actor,
        )

        artifacts, _ = await self._artifact_repo.list_by_study(
            study_id, actor.organization_id, limit=50, offset=0
        )
        from app.models.artifact import ArtifactType

        protocol = next(
            (a for a in artifacts if a.artifact_type == ArtifactType.PROTOCOL),
            None,
        )
        if protocol is not None:
            protocol_node, _ = await self._graph.register_domain_record(
                organization_id=actor.organization_id,
                node_type=GraphNodeType.PROTOCOL,
                external_id=protocol.id,
                external_type="artifact",
                label=protocol.name,
                study_id=study_id,
                actor=actor,
            )
            await self._graph.create_relationship(
                organization_id=actor.organization_id,
                source_node_id=sdtm_node.id,
                target_node_id=protocol_node.id,
                edge_type=GraphEdgeType.DERIVED_FROM,
                study_id=study_id,
                is_ai_generated=True,
                ai_decision_id=ai_decision_id,
                actor=actor,
            )
