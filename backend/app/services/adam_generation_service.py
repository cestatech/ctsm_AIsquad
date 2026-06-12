"""ADaM generation service — derive ADaM datasets from SDTM artifact content.

Phase 5 pipeline: SDTM_DATASET artifact → AI-assisted ADaM specification artifact
→ context graph + field lineage → internal CDISC validation run.
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
    assert_compatible_data_cuts,
    extract_data_cut,
    prepare_pipeline_artifact,
)
from app.services.dual_programmer_qc_service import DualProgrammerQCService
from app.services.generation_fallback import (
    DUMMY_GENERATION_NOTICE,
    NO_API_KEY_FALLBACK_REASON,
    apply_dummy_generation_labels,
    format_fallback_reasoning,
)
from app.services.validation_service import ValidationService
from app.models.statistical_qc import StatisticalQCWorkflow

logger = logging.getLogger(__name__)

_AGENT_NAME = "adam-derivation-agent"
_MODEL_ID = "claude-sonnet-4-20250514"

_SYSTEM_PROMPT = """You are a CDISC ADaM expert. Derive ADaM IG 1.3 analysis datasets from SDTM domain content.

Given SDTM domains with observations, produce an ADaM derivation specification.

Rules:
- Always include ADSL with required variables STUDYID, USUBJID, SUBJID
- Include population_flags with at least ITTFL in ADSL
- Document derivation for every variable
- Add ADAE if AE domain present; BDS datasets (ADLB, ADVS) only if source domains exist
- Return ONLY valid JSON matching the schema below

Schema:
{
  "datasets": [
    {
      "dataset": "ADSL",
      "label": "Subject Level Analysis Dataset",
      "structure": "One record per subject",
      "source_domains": ["DM"],
      "key_variables": ["STUDYID", "USUBJID"],
      "variables": [
        {
          "variable": "USUBJID",
          "label": "Unique Subject Identifier",
          "type": "Char",
          "origin": "SDTM.DM",
          "derivation": "DM.USUBJID",
          "controlled_terminology": null,
          "notes": ""
        }
      ],
      "population_flags": [
        {"variable": "ITTFL", "label": "Intent-to-Treat Flag", "derivation": "Y if randomised"}
      ]
    }
  ],
  "traceability_notes": ["<note linking ADaM to SDTM>"]
}"""


@dataclass
class StudyADAMReadiness:
    study_id: UUID
    sdtm_artifact_count: int
    ready: bool
    issues: list[str]
    sdtm_artifacts: list[dict]


@dataclass
class ADAMGenerationResult:
    artifact: Artifact
    ai_decision_id: UUID
    validation_run: ValidationRun
    dataset_count: int
    source_sdtm_artifact_ids: list[UUID]


class ADAMGenerationService:
    """Generate ADaM dataset artifacts from SDTM artifact content."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._study_repo = StudyRepository(db)
        self._artifact_svc = ArtifactService(db)
        self._artifact_repo = ArtifactRepository(db)
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
    ) -> StudyADAMReadiness:
        """Return study-wide readiness for ADaM generation from SDTM artifacts."""
        await self._study_repo.get(study_id, organization_id)
        artifacts, _ = await self._artifact_repo.list_by_study(
            study_id, organization_id, limit=100, offset=0
        )
        sdtm_arts = [
            a for a in artifacts if a.artifact_type == ArtifactType.SDTM_DATASET
        ]
        issues: list[str] = []
        summaries: list[dict] = []

        if not sdtm_arts:
            issues.append("No SDTM dataset artifacts found for this study.")

        for art in sdtm_arts:
            content = await self._load_artifact_content(art)
            domains = content.get("domains", [])
            domain_codes = [d.get("domain", "?") for d in domains]
            obs_count = sum(len(d.get("observations", [])) for d in domains)
            art_ready = bool(domains) and obs_count > 0
            if not domains:
                issues.append(f"{art.name}: no SDTM domains in content.")
            elif obs_count == 0:
                issues.append(f"{art.name}: SDTM domains have no observations.")
            summaries.append(
                {
                    "artifact_id": str(art.id),
                    "artifact_name": art.name,
                    "domain_count": len(domains),
                    "domains": domain_codes,
                    "observation_count": obs_count,
                    "ready": art_ready,
                }
            )

        ready = bool(summaries) and all(s["ready"] for s in summaries)
        return StudyADAMReadiness(
            study_id=study_id,
            sdtm_artifact_count=len(sdtm_arts),
            ready=ready and len(issues) == 0,
            issues=issues[:30],
            sdtm_artifacts=summaries,
        )

    async def generate_from_sdtm_artifact(
        self,
        sdtm_artifact_id: UUID,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ADAMGenerationResult:
        """Derive ADaM specification from a single SDTM artifact."""
        check_permission(actor, Permission.ARTIFACT_CREATE)

        sdtm_artifact, sdtm_content = await self._get_sdtm_artifact(
            sdtm_artifact_id, actor.organization_id
        )
        self._assert_sdtm_ready(sdtm_content, sdtm_artifact.name)

        study = await self._study_repo.get(
            sdtm_artifact.study_id, actor.organization_id
        )
        merged_domains = sdtm_content.get("domains", [])

        return await self._run_generation(
            actor=actor,
            study=study,
            merged_domains=merged_domains,
            source_artifacts=[sdtm_artifact],
            source_contents=[sdtm_content],
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def generate_from_study(
        self,
        study_id: UUID,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ADAMGenerationResult:
        """Merge all study SDTM artifacts and derive a full ADaM package."""
        check_permission(actor, Permission.ARTIFACT_CREATE)

        readiness = await self.get_study_readiness(study_id, actor.organization_id)
        if not readiness.ready:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "STUDY_NOT_READY",
                    "message": "Study must have SDTM artifacts with domain observations.",
                    "issues": readiness.issues,
                },
            )

        study = await self._study_repo.get(study_id, actor.organization_id)
        artifacts, _ = await self._artifact_repo.list_by_study(
            study_id, actor.organization_id, limit=100, offset=0
        )
        sdtm_arts = [
            a for a in artifacts if a.artifact_type == ArtifactType.SDTM_DATASET
        ]
        source_artifacts: list[Artifact] = []
        source_contents: list[dict] = []
        merged_domains: list[dict] = []

        for art in sdtm_arts:
            content = await self._load_artifact_content(art)
            if not content.get("domains"):
                continue
            source_artifacts.append(art)
            source_contents.append(content)
            merged_domains = self._merge_sdtm_domains(
                merged_domains, content.get("domains", [])
            )

        if not merged_domains:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "NO_SDTM_CONTENT",
                    "message": "No usable SDTM domain content found.",
                },
            )

        return await self._run_generation(
            actor=actor,
            study=study,
            merged_domains=merged_domains,
            source_artifacts=source_artifacts,
            source_contents=source_contents,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def _run_generation(
        self,
        *,
        actor: User,
        study,
        merged_domains: list[dict],
        source_artifacts: list[Artifact],
        source_contents: list[dict],
        ip_address: str | None,
        user_agent: str | None,
    ) -> ADAMGenerationResult:
        source_ids = [a.id for a in source_artifacts]
        protocol_number = (
            source_contents[0].get("protocol_number") or study.protocol_number
        )

        decision = await self._ai_decision.begin_decision(
            organization_id=actor.organization_id,
            agent_name=_AGENT_NAME,
            decision_type="ADAM_DERIVATION",
            study_id=study.id,
            model_id=_MODEL_ID,
            input_context={
                "study_id": str(study.id),
                "source_sdtm_artifact_ids": [str(i) for i in source_ids],
                "sdtm_domain_count": len(merged_domains),
            },
        )

        content = await self._build_adam_content(
            study_name=study.name,
            protocol_number=protocol_number,
            sdtm_domains=merged_domains,
            source_sdtm_artifact_ids=source_ids,
        )

        shared_cut = None
        for art, src_content in zip(source_artifacts, source_contents, strict=True):
            cut = extract_data_cut(art.extra_data, src_content)
            if cut is None:
                continue
            if shared_cut is None:
                shared_cut = cut
            else:
                assert_compatible_data_cuts(
                    shared_cut, cut, operation="ADaM derivation"
                )
        if shared_cut is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "NO_DATA_CUT",
                    "message": "SDTM source artifacts must include data cut metadata.",
                },
            )
        art_name, art_desc, content, metadata = prepare_pipeline_artifact(
            study_name=study.name,
            package_label="ADaM Package",
            data_cut=shared_cut,
            content=content,
            base_description=(
                f"AI-derived ADaM IG {self._settings.ADAM_IG_VERSION} from "
                f"{len(source_ids)} SDTM artifact(s)"
            ),
        )

        artifact = await self._artifact_svc.create_artifact(
            organization_id=actor.organization_id,
            study_id=study.id,
            user=actor,
            artifact_type=ArtifactType.ADAM_DATASET,
            name=art_name,
            description=art_desc,
            content=content,
            change_summary=f"ADaM derivation from {len(source_ids)} SDTM artifact(s)",
            metadata=metadata,
        )

        return await self._finalize_generation(
            actor=actor,
            study_id=study.id,
            artifact=artifact,
            decision=decision,
            content=content,
            source_artifacts=source_artifacts,
            merged_domains=merged_domains,
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
        source_artifacts: list[Artifact],
        merged_domains: list[dict],
        ip_address: str | None,
        user_agent: str | None,
    ) -> ADAMGenerationResult:
        for sdtm_art in source_artifacts:
            await self._register_cip_links(
                sdtm_artifact=sdtm_art,
                adam_artifact=artifact,
                adam_content=content,
                sdtm_domains=merged_domains,
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
            artifact_node_type=GraphNodeType.ADAM_DATASET,
            artifact_external_type="adam_artifact",
            actor=actor,
            ai_decision_id=decision.id,
        )

        await self._ai_decision.complete_decision(
            decision=decision,
            output={
                "artifact_id": str(artifact.id),
                "datasets": [d["dataset"] for d in content.get("datasets", [])],
                "source_sdtm_artifact_ids": [str(a.id) for a in source_artifacts],
                "generation_mode": content.get("generation_mode"),
            },
            reasoning=format_fallback_reasoning(
                (
                    f"Derived ADaM from {len(merged_domains)} SDTM domain(s) "
                    f"across {len(source_artifacts)} artifact(s)"
                ),
                content.get("fallback_reason"),
            ),
            confidence=0.85 if not content.get("fallback_reason") else 0.5,
            output_artifact_ids=[artifact.id],
        )

        validation_run = await self._validation.trigger(
            body=ValidationRunCreate(
                artifact_id=artifact.id,
                artifact_version_id=artifact.current_version_id,
                engine="internal",
                rule_set_version=f"ADaM-IG-{self._settings.ADAM_IG_VERSION}",
            ),
            actor=actor,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self._audit.log(
            action=AuditAction.AI_GENERATION_COMPLETED,
            resource_type="adam_dataset",
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            resource_id=artifact.id,
            after_state={
                "artifact_id": str(artifact.id),
                "validation_run_id": str(validation_run.id),
                "ai_decision_id": str(decision.id),
                "source_sdtm_artifact_ids": [str(a.id) for a in source_artifacts],
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        qc_svc = DualProgrammerQCService(self._db)
        await qc_svc.run_qc(
            workflow_step=StatisticalQCWorkflow.SDTM_TO_ADAM,
            study_id=study_id,
            actor=actor,
            input_payload={
                "domains": merged_domains,
                "datasets": content.get("datasets", []),
                "protocol_number": content.get("protocol_number"),
            },
            output_artifact_id=artifact.id,
            source_artifact_id=source_artifacts[0].id if source_artifacts else None,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return ADAMGenerationResult(
            artifact=artifact,
            ai_decision_id=decision.id,
            validation_run=validation_run,
            dataset_count=len(content.get("datasets", [])),
            source_sdtm_artifact_ids=[a.id for a in source_artifacts],
        )

    async def _get_sdtm_artifact(
        self, artifact_id: UUID, organization_id: UUID
    ) -> tuple[Artifact, dict]:
        artifact = await self._artifact_repo.get_by_id(artifact_id, organization_id)
        if artifact.artifact_type != ArtifactType.SDTM_DATASET:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "NOT_SDTM",
                    "message": "Source artifact must be SDTM_DATASET type.",
                },
            )
        content = await self._load_artifact_content(artifact)
        return artifact, content

    async def _load_artifact_content(self, artifact: Artifact) -> dict:
        version = await self._artifact_repo.get_version(artifact.current_version_id)
        return version.content or {}

    @staticmethod
    def _assert_sdtm_ready(content: dict, artifact_name: str) -> None:
        domains = content.get("domains", [])
        if not domains:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "SDTM_NOT_READY",
                    "message": f"SDTM artifact '{artifact_name}' has no domains.",
                },
            )
        obs_count = sum(len(d.get("observations", [])) for d in domains)
        if obs_count == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "SDTM_NOT_READY",
                    "message": f"SDTM artifact '{artifact_name}' has no observations.",
                },
            )

    @staticmethod
    def _merge_sdtm_domains(existing: list[dict], incoming: list[dict]) -> list[dict]:
        by_code: dict[str, dict] = {d.get("domain", "UNK"): dict(d) for d in existing}
        for domain in incoming:
            code = domain.get("domain", "UNK")
            if code not in by_code:
                by_code[code] = dict(domain)
                continue
            current = by_code[code]
            vars_set = set(current.get("variables", []))
            vars_set.update(domain.get("variables", []))
            current["variables"] = sorted(vars_set)
            current["observations"] = current.get("observations", []) + domain.get(
                "observations", []
            )
        return list(by_code.values())

    async def _build_adam_content(
        self,
        *,
        study_name: str,
        protocol_number: str,
        sdtm_domains: list[dict],
        source_sdtm_artifact_ids: list[UUID],
    ) -> dict:
        fallback_reason: str | None = None
        if self._client:
            try:
                ai_spec = await self._call_claude(
                    study_name=study_name,
                    protocol_number=protocol_number,
                    sdtm_domains=sdtm_domains,
                )
                datasets = ai_spec.get("datasets", [])
                trace_notes = ai_spec.get("traceability_notes", [])
            except HTTPException as exc:
                detail = exc.detail if isinstance(exc.detail, dict) else {}
                if (
                    exc.status_code != status.HTTP_502_BAD_GATEWAY
                    or detail.get("code") != "AI_PARSE_ERROR"
                ):
                    raise
                fallback_reason = str(detail.get("message", exc))
                logger.warning(
                    "ADaM agent parse failed, using deterministic fallback: %s",
                    fallback_reason,
                )
                spec = self._deterministic_adam(
                    protocol_number=protocol_number,
                    sdtm_domains=sdtm_domains,
                )
                datasets = spec["datasets"]
                trace_notes = spec["traceability_notes"]
            except (anthropic.APIError, TimeoutError) as exc:
                fallback_reason = f"Anthropic API error: {exc}"
                logger.warning(
                    "ADaM agent API call failed, using deterministic fallback: %s",
                    exc,
                )
                spec = self._deterministic_adam(
                    protocol_number=protocol_number,
                    sdtm_domains=sdtm_domains,
                )
                datasets = spec["datasets"]
                trace_notes = spec["traceability_notes"]
        else:
            fallback_reason = NO_API_KEY_FALLBACK_REASON
            spec = self._deterministic_adam(
                protocol_number=protocol_number,
                sdtm_domains=sdtm_domains,
            )
            datasets = spec["datasets"]
            trace_notes = spec["traceability_notes"]

        datasets = self._enrich_bds_datasets(sdtm_domains, datasets)
        trace_notes = list(trace_notes)
        for ds in datasets:
            code = ds.get("dataset")
            if code in ("ADLB", "ADVS", "ADTTE") and not any(
                code in n for n in trace_notes
            ):
                trace_notes.append(f"{code} auto-derived from SDTM source domain(s)")

        content = {
            "document_type": "ADAM_SPECIFICATION",
            "version": "1.0",
            "adam_ig_version": self._settings.ADAM_IG_VERSION,
            "source_sdtm_artifact_ids": [str(i) for i in source_sdtm_artifact_ids],
            "study_name": study_name,
            "protocol_number": protocol_number,
            "validation_engine": "internal",
            "pinnacle21_ready": self._settings.pinnacle21_configured,
            "datasets": datasets,
            "traceability_notes": trace_notes,
            "regulatory_references": [
                f"CDISC ADaM IG v{self._settings.ADAM_IG_VERSION}",
                "FDA Study Data Technical Conformance Guide",
            ],
            "sdtm_domain_count": len(sdtm_domains),
        }
        if fallback_reason:
            apply_dummy_generation_labels(content, fallback_reason=fallback_reason)
            if DUMMY_GENERATION_NOTICE not in content["traceability_notes"]:
                content["traceability_notes"].insert(0, DUMMY_GENERATION_NOTICE)
        return content

    async def _call_claude(
        self,
        *,
        study_name: str,
        protocol_number: str,
        sdtm_domains: list[dict],
    ) -> dict:
        sample_domains = []
        for d in sdtm_domains[:10]:
            sample_domains.append(
                {
                    "domain": d.get("domain"),
                    "variables": d.get("variables", [])[:20],
                    "observations": (d.get("observations") or [])[:5],
                }
            )

        user_prompt = f"""Study: {study_name}
Protocol: {protocol_number}
ADaM IG: {self._settings.ADAM_IG_VERSION}

SDTM domains (sample observations):
{json.dumps(sample_domains, indent=2, default=str)}

Derive ADaM analysis datasets with full variable derivations and population flags."""

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
    def _deterministic_adam(
        *,
        protocol_number: str,
        sdtm_domains: list[dict],
    ) -> dict:
        """Fallback ADaM spec when no API key — ADSL from DM, ADAE from AE."""
        dm = next((d for d in sdtm_domains if d.get("domain") == "DM"), None)
        dm_obs = dm.get("observations", []) if dm else []
        dm_vars = set(dm.get("variables", [])) if dm else set()

        def _var(name: str, label: str, derivation: str) -> dict:
            return {
                "variable": name,
                "label": label,
                "type": "Char",
                "origin": "SDTM.DM",
                "derivation": derivation,
                "controlled_terminology": None,
                "notes": "Deterministic derivation (no AI)",
            }

        adsl_variables = [
            _var("STUDYID", "Study Identifier", "DM.STUDYID"),
            _var("USUBJID", "Unique Subject Identifier", "DM.USUBJID"),
            _var(
                "SUBJID",
                "Subject Identifier",
                "DM.SUBJID or derived from USUBJID",
            ),
        ]
        for extra in ("AGE", "SEX", "RACE", "ETHNIC"):
            if extra in dm_vars:
                adsl_variables.append(_var(extra, extra, f"DM.{extra}"))

        datasets: list[dict] = [
            {
                "dataset": "ADSL",
                "label": "Subject Level Analysis Dataset",
                "structure": "One record per subject",
                "source_domains": ["DM"] if dm else [],
                "key_variables": ["STUDYID", "USUBJID"],
                "variables": adsl_variables,
                "population_flags": [
                    {
                        "variable": "ITTFL",
                        "label": "Intent-to-Treat Population Flag",
                        "derivation": (
                            "Y if subject has DM record with USUBJID, N otherwise"
                        ),
                    },
                    {
                        "variable": "SAFFL",
                        "label": "Safety Population Flag",
                        "derivation": "Y if subject received any treatment",
                    },
                ],
                "observation_count": len(dm_obs),
            }
        ]

        ae = next((d for d in sdtm_domains if d.get("domain") == "AE"), None)
        if ae:
            datasets.append(
                {
                    "dataset": "ADAE",
                    "label": "Adverse Events Analysis Dataset",
                    "structure": "One record per subject per AE per visit",
                    "source_domains": ["AE"],
                    "key_variables": ["STUDYID", "USUBJID", "AESEQ"],
                    "variables": [
                        _var("USUBJID", "Unique Subject Identifier", "AE.USUBJID"),
                        {
                            "variable": "AEDECOD",
                            "label": "Dictionary-Derived Term",
                            "type": "Char",
                            "origin": "SDTM.AE",
                            "derivation": "AE.AEDECOD or AE.AETERM",
                            "controlled_terminology": None,
                            "notes": "",
                        },
                        {
                            "variable": "AESEV",
                            "label": "Severity",
                            "type": "Char",
                            "origin": "SDTM.AE",
                            "derivation": "AE.AESEV",
                            "controlled_terminology": None,
                            "notes": "",
                        },
                        {
                            "variable": "AESER",
                            "label": "Serious Event Flag",
                            "type": "Char",
                            "origin": "SDTM.AE",
                            "derivation": "AE.AESER",
                            "controlled_terminology": None,
                            "notes": "",
                        },
                    ],
                    "population_flags": [],
                }
            )

        trace = [
            f"ADSL derived from SDTM DM domain ({len(dm_obs)} subjects)",
            f"Protocol: {protocol_number}",
        ]
        if ae:
            trace.append("ADAE derived from SDTM AE domain")

        datasets = ADAMGenerationService._enrich_bds_datasets(sdtm_domains, datasets)
        return {"datasets": datasets, "traceability_notes": trace}

    @staticmethod
    def _enrich_bds_datasets(
        sdtm_domains: list[dict], datasets: list[dict]
    ) -> list[dict]:
        """Add ADLB, ADVS, ADTTE when source SDTM domains are present."""
        existing = {d.get("dataset") for d in datasets}
        domain_codes = {d.get("domain") for d in sdtm_domains}

        if "LB" in domain_codes and "ADLB" not in existing:
            lb = next(d for d in sdtm_domains if d.get("domain") == "LB")
            datasets.append(ADAMGenerationService._derive_adlb(lb))
        if "VS" in domain_codes and "ADVS" not in existing:
            vs = next(d for d in sdtm_domains if d.get("domain") == "VS")
            datasets.append(ADAMGenerationService._derive_advs(vs))
        if ("AE" in domain_codes or "DS" in domain_codes) and "ADTTE" not in existing:
            ae = next((d for d in sdtm_domains if d.get("domain") == "AE"), None)
            ds = next((d for d in sdtm_domains if d.get("domain") == "DS"), None)
            source = ae or ds
            src_dom = "AE" if ae else "DS"
            datasets.append(ADAMGenerationService._derive_adtte(source, src_dom))

        return datasets

    @staticmethod
    def _bds_var(
        name: str,
        label: str,
        derivation: str,
        origin: str,
        vtype: str = "Num",
    ) -> dict:
        return {
            "variable": name,
            "label": label,
            "type": vtype,
            "origin": origin,
            "derivation": derivation,
            "controlled_terminology": None,
            "notes": "BDS auto-derivation",
        }

    @staticmethod
    def _derive_adlb(lb_domain: dict) -> dict:
        """Derive ADLB (Laboratory Results BDS) from SDTM LB domain."""
        obs = lb_domain.get("observations", [])
        bds_vars = [
            ADAMGenerationService._bds_var(
                "PARAMCD", "Parameter Code", "LB.LBTESTCD", "SDTM.LB", "Char"
            ),
            ADAMGenerationService._bds_var(
                "PARAM", "Parameter", "LB.LBTEST", "SDTM.LB", "Char"
            ),
            ADAMGenerationService._bds_var(
                "AVAL", "Analysis Value", "numeric(LB.LBSTRESN)", "SDTM.LB"
            ),
            ADAMGenerationService._bds_var(
                "AVALC", "Analysis Value (C)", "LB.LBSTRESC", "SDTM.LB", "Char"
            ),
            ADAMGenerationService._bds_var(
                "BASE", "Baseline Value", "first(AVAL) per USUBJID/PARAMCD", "Derived"
            ),
            ADAMGenerationService._bds_var(
                "CHG", "Change from Baseline", "AVAL - BASE", "Derived"
            ),
            ADAMGenerationService._bds_var(
                "PCHG", "Percent Change", "100 * (CHG / BASE)", "Derived"
            ),
            ADAMGenerationService._bds_var(
                "ANRLO", "Analysis Normal Range Lower", "LB.LBSTNRLO", "SDTM.LB"
            ),
            ADAMGenerationService._bds_var(
                "ANRHI", "Analysis Normal Range Upper", "LB.LBSTNRHI", "SDTM.LB"
            ),
            ADAMGenerationService._bds_var(
                "ANL01FL", "Analysis Flag 01", "Y if post-baseline", "Derived", "Char"
            ),
        ]
        derived_obs = []
        for row in obs:
            if not isinstance(row, dict):
                continue
            derived_obs.append(
                {
                    "USUBJID": row.get("USUBJID"),
                    "PARAMCD": row.get("LBTESTCD") or row.get("LBTEST"),
                    "AVAL": row.get("LBSTRESN") or row.get("LBORRES"),
                    "AVALC": row.get("LBSTRESC") or row.get("LBORRES"),
                    "VISIT": row.get("VISIT"),
                }
            )
        return {
            "dataset": "ADLB",
            "label": "Laboratory Results Analysis Dataset",
            "structure": "One record per subject per visit per parameter",
            "source_domains": ["LB"],
            "key_variables": ["STUDYID", "USUBJID", "PARAMCD", "AVISIT"],
            "variables": bds_vars,
            "population_flags": [],
            "observations": derived_obs,
            "observation_count": len(derived_obs),
        }

    @staticmethod
    def _derive_advs(vs_domain: dict) -> dict:
        """Derive ADVS (Vital Signs BDS) from SDTM VS domain."""
        obs = vs_domain.get("observations", [])
        param_map = {
            "SYSBP": ("Systolic Blood Pressure", "VS.VSTESTCD='SYSBP'"),
            "DIABP": ("Diastolic Blood Pressure", "VS.VSTESTCD='DIABP'"),
            "PULSE": ("Pulse Rate", "VS.VSTESTCD='PULSE'"),
            "TEMP": ("Temperature", "VS.VSTESTCD='TEMP'"),
            "WEIGHT": ("Weight", "VS.VSTESTCD='WEIGHT'"),
            "HEIGHT": ("Height", "VS.VSTESTCD='HEIGHT'"),
            "BMI": ("Body Mass Index", "derived from WEIGHT/HEIGHT"),
        }
        bds_vars = [
            ADAMGenerationService._bds_var(
                "PARAMCD", "Parameter Code", "VS.VSTESTCD", "SDTM.VS", "Char"
            ),
            ADAMGenerationService._bds_var(
                "PARAM", "Parameter", "VS.VSTEST", "SDTM.VS", "Char"
            ),
            ADAMGenerationService._bds_var(
                "AVAL", "Analysis Value", "numeric(VS.VSSTRESN)", "SDTM.VS"
            ),
            ADAMGenerationService._bds_var(
                "BASE", "Baseline Value", "first(AVAL) per USUBJID/PARAMCD", "Derived"
            ),
            ADAMGenerationService._bds_var(
                "CHG", "Change from Baseline", "AVAL - BASE", "Derived"
            ),
            ADAMGenerationService._bds_var(
                "PCHG", "Percent Change", "100 * (CHG / BASE)", "Derived"
            ),
            ADAMGenerationService._bds_var(
                "ANRLO", "Analysis Normal Range Lower", "VS.VSSTNRLO", "SDTM.VS"
            ),
            ADAMGenerationService._bds_var(
                "ANRHI", "Analysis Normal Range Upper", "VS.VSSTNRHI", "SDTM.VS"
            ),
        ]
        derived_obs = []
        for row in obs:
            if not isinstance(row, dict):
                continue
            testcd = str(row.get("VSTESTCD") or row.get("VSTEST") or "").upper()
            paramcd = testcd if testcd in param_map else testcd[:6] or "VS"
            derived_obs.append(
                {
                    "USUBJID": row.get("USUBJID"),
                    "PARAMCD": paramcd,
                    "AVAL": row.get("VSSTRESN") or row.get("VSORRES"),
                    "VISIT": row.get("VISIT"),
                }
            )
        return {
            "dataset": "ADVS",
            "label": "Vital Signs Analysis Dataset",
            "structure": "One record per subject per visit per parameter",
            "source_domains": ["VS"],
            "key_variables": ["STUDYID", "USUBJID", "PARAMCD", "AVISIT"],
            "variables": bds_vars,
            "population_flags": [],
            "observations": derived_obs,
            "observation_count": len(derived_obs),
            "parameter_catalog": list(param_map.keys()),
        }

    @staticmethod
    def _derive_adtte(source_domain: dict, src_dom: str = "AE") -> dict:
        """Derive ADTTE (Time-to-Event BDS) from SDTM AE or DS domain."""
        obs = source_domain.get("observations", [])
        if src_dom == "AE":
            bds_vars = [
                ADAMGenerationService._bds_var(
                    "AVAL", "Analysis Value (days)", "AE.AESTDY or date diff", "SDTM.AE"
                ),
                ADAMGenerationService._bds_var(
                    "CNSR", "Censoring Flag", "0=event, 1=censored", "Derived", "Char"
                ),
                ADAMGenerationService._bds_var(
                    "EVNTDESC", "Event Description", "AE.AEDECOD", "SDTM.AE", "Char"
                ),
                ADAMGenerationService._bds_var(
                    "SRCDOM", "Source Domain", "'AE'", "Derived", "Char"
                ),
                ADAMGenerationService._bds_var(
                    "SRCVAR", "Source Variable", "'AESTDTC'", "Derived", "Char"
                ),
                ADAMGenerationService._bds_var(
                    "STARTDT", "Time-to-Event Origin Date", "ADSL.RANDDT", "ADSL"
                ),
            ]
            derived_obs = []
            for row in obs:
                if not isinstance(row, dict):
                    continue
                derived_obs.append(
                    {
                        "USUBJID": row.get("USUBJID"),
                        "AVAL": row.get("AESTDY") or row.get("AEDUR"),
                        "CNSR": "0" if row.get("AESER") == "Y" else "1",
                        "EVNTDESC": row.get("AEDECOD") or row.get("AETERM"),
                        "SRCDOM": "AE",
                        "SRCVAR": "AESTDTC",
                    }
                )
        else:
            bds_vars = [
                ADAMGenerationService._bds_var(
                    "AVAL", "Analysis Value (days)", "DS.DSDY or date diff", "SDTM.DS"
                ),
                ADAMGenerationService._bds_var(
                    "CNSR",
                    "Censoring Flag",
                    "0=discontinued, 1=censored",
                    "Derived",
                    "Char",
                ),
                ADAMGenerationService._bds_var(
                    "EVNTDESC", "Event Description", "DS.DSDECOD", "SDTM.DS", "Char"
                ),
                ADAMGenerationService._bds_var(
                    "SRCDOM", "Source Domain", "'DS'", "Derived", "Char"
                ),
                ADAMGenerationService._bds_var(
                    "SRCVAR", "Source Variable", "'DSSTDTC'", "Derived", "Char"
                ),
                ADAMGenerationService._bds_var(
                    "STARTDT", "Time-to-Event Origin Date", "ADSL.RANDDT", "ADSL"
                ),
            ]
            derived_obs = []
            for row in obs:
                if not isinstance(row, dict):
                    continue
                derived_obs.append(
                    {
                        "USUBJID": row.get("USUBJID"),
                        "AVAL": row.get("DSDY"),
                        "CNSR": "0",
                        "EVNTDESC": row.get("DSDECOD") or row.get("DSTERM"),
                        "SRCDOM": "DS",
                        "SRCVAR": "DSSTDTC",
                    }
                )

        return {
            "dataset": "ADTTE",
            "label": "Time-to-Event Analysis Dataset",
            "structure": "One record per subject per time-to-event parameter",
            "source_domains": [src_dom],
            "key_variables": ["STUDYID", "USUBJID", "PARAMCD"],
            "variables": bds_vars,
            "population_flags": [],
            "observations": derived_obs,
            "observation_count": len(derived_obs),
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
                    "message": f"ADaM agent returned invalid JSON: {exc}",
                },
            ) from exc

    async def _register_cip_links(
        self,
        *,
        sdtm_artifact: Artifact,
        adam_artifact: Artifact,
        adam_content: dict,
        sdtm_domains: list[dict],
        actor: User,
        ai_decision_id: UUID,
    ) -> None:
        sdtm_node, _ = await self._graph.register_domain_record(
            organization_id=actor.organization_id,
            node_type=GraphNodeType.SDTM_DOMAIN,
            external_id=sdtm_artifact.id,
            external_type="sdtm_artifact",
            label=sdtm_artifact.name,
            study_id=sdtm_artifact.study_id,
            properties={"artifact_id": str(sdtm_artifact.id)},
            actor=actor,
        )
        adam_node, _ = await self._graph.register_domain_record(
            organization_id=actor.organization_id,
            node_type=GraphNodeType.ADAM_DATASET,
            external_id=adam_artifact.id,
            external_type="adam_artifact",
            label=adam_artifact.name,
            study_id=sdtm_artifact.study_id,
            properties={"artifact_id": str(adam_artifact.id)},
            actor=actor,
        )
        await self._graph.link_sdtm_to_adam(
            org_id=actor.organization_id,
            study_id=sdtm_artifact.study_id,
            sdtm_node_id=sdtm_node.id,
            adam_node_id=adam_node.id,
            is_ai_generated=True,
            ai_decision_id=ai_decision_id,
            actor=actor,
        )

        sdtm_domain_codes = {d.get("domain") for d in sdtm_domains}
        for ds in adam_content.get("datasets", []):
            adam_ds = ds.get("dataset", "UNK")
            for var in ds.get("variables", []):
                vname = var.get("variable", "")
                origin = var.get("origin", "")
                derivation = var.get("derivation", "")
                adam_var_node, _ = await self._graph.register_domain_record(
                    organization_id=actor.organization_id,
                    node_type=GraphNodeType.ADAM_VARIABLE,
                    external_id=adam_artifact.id,
                    external_type="adam_variable",
                    label=f"{adam_ds}.{vname}",
                    study_id=sdtm_artifact.study_id,
                    properties={
                        "dataset": adam_ds,
                        "variable": vname,
                        "artifact_id": str(adam_artifact.id),
                    },
                    actor=actor,
                )
                await self._lineage.record_field_lineage(
                    organization_id=actor.organization_id,
                    lineage_type=DataLineageType.TRANSFORMED,
                    source_type="sdtm_domain",
                    target_type="adam_variable",
                    source_id=sdtm_artifact.id,
                    source_field=derivation,
                    target_id=adam_artifact.id,
                    target_field=vname,
                    target_domain=adam_ds,
                    transformation_logic=derivation or f"ADaM {adam_ds}.{vname}",
                    is_ai_generated=True,
                    ai_decision_id=ai_decision_id,
                    study_id=sdtm_artifact.study_id,
                    created_by=actor,
                )
                if origin.startswith("SDTM."):
                    src_domain = origin.split(".", 1)[1]
                    if src_domain in sdtm_domain_codes:
                        sdtm_var_node, _ = await self._graph.register_domain_record(
                            organization_id=actor.organization_id,
                            node_type=GraphNodeType.SDTM_VARIABLE,
                            external_id=sdtm_artifact.id,
                            external_type="sdtm_variable",
                            label=derivation or f"{src_domain}.{vname}",
                            study_id=sdtm_artifact.study_id,
                            properties={"domain": src_domain},
                            actor=actor,
                        )
                        await self._graph.create_relationship(
                            organization_id=actor.organization_id,
                            source_node_id=sdtm_var_node.id,
                            target_node_id=adam_var_node.id,
                            edge_type=GraphEdgeType.SDTM_TO_ADAM,
                            study_id=sdtm_artifact.study_id,
                            is_ai_generated=True,
                            ai_decision_id=ai_decision_id,
                            actor=actor,
                        )
