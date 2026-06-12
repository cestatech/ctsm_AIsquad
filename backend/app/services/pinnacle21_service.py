"""Pinnacle 21 Community Edition API adapter for SDTM validation."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models.artifact import ArtifactType
from app.models.intelligence import ValidationEvidenceStatus
from app.models.user import User
from app.repositories.artifact_repository import ArtifactRepository
from app.services.intelligence_service import (
    AIDecisionService,
    ValidationIntelligenceService,
)

log = logging.getLogger(__name__)

_AGENT_NAME = "pinnacle21-validation-agent"
_MODEL_ID = "pinnacle21-community"


@dataclass
class P21Finding:
    """Normalised Pinnacle 21 validation finding."""

    rule_id: str
    rule_name: str
    severity: str
    message: str
    domain: str | None = None
    variable: str | None = None
    status: str = "FAIL"


class Pinnacle21Service:
    """HTTP adapter for Pinnacle 21 SDTM validation."""

    def __init__(
        self,
        db: AsyncSession,
        settings: Settings | None = None,
    ) -> None:
        self._db = db
        self._settings = settings or get_settings()
        self._artifact_repo = ArtifactRepository(db)
        self._ai_decision = AIDecisionService(db)
        self._validation_intel = ValidationIntelligenceService(db)

    @property
    def enabled(self) -> bool:
        return self._settings.pinnacle21_configured

    async def validate_sdtm_dataset(
        self,
        *,
        dataset_path: str,
        ig_version: str,
        rule_set: str,
        organization_id: UUID,
        study_id: UUID | None,
        validation_run_id: UUID | None,
        artifact_id: UUID | None,
        actor: User | None = None,
    ) -> list[P21Finding]:
        """Run P21 validation against a dataset path. Returns normalised findings."""
        if not self.enabled:
            return []

        decision = None
        if actor is not None:
            decision = await self._ai_decision.begin_decision(
                organization_id=organization_id,
                agent_name=_AGENT_NAME,
                decision_type="PINNACLE21_SDTM_VALIDATION",
                study_id=study_id,
                model_id=_MODEL_ID,
                input_context={
                    "dataset_path": dataset_path,
                    "ig_version": ig_version,
                    "rule_set": rule_set,
                },
            )

        try:
            findings = await self._call_p21_api(
                dataset_path=dataset_path,
                ig_version=ig_version,
                rule_set=rule_set,
            )
        except Exception as exc:
            log.warning("Pinnacle 21 validation failed (non-blocking): %s", exc)
            if decision is not None and actor is not None:
                await self._ai_decision.complete_decision(
                    decision=decision,
                    output={"error": str(exc), "findings": []},
                    reasoning="Pinnacle 21 API call failed; SDTM generation continues.",
                    confidence=0.0,
                )
            return []

        for finding in findings:
            ev_status = (
                ValidationEvidenceStatus.PASS
                if finding.status == "PASS"
                else (
                    ValidationEvidenceStatus.WARNING
                    if finding.severity == "WARNING"
                    else ValidationEvidenceStatus.FAIL
                )
            )
            await self._validation_intel.record_evidence(
                organization_id=organization_id,
                study_id=study_id,
                validation_run_id=validation_run_id,
                subject_type="artifact",
                subject_id=artifact_id,
                evidence_status=ev_status,
                rule_id=finding.rule_id,
                rule_name=finding.rule_name,
                rule_category="PINNACLE21",
                cdisc_standard=f"SDTM-IG-{ig_version}",
                subject_field=finding.variable,
                finding_severity=finding.severity,
                finding_message=finding.message,
                finding_details={
                    "domain": finding.domain,
                    "variable": finding.variable,
                    "source": "PINNACLE21",
                },
                is_ai_evaluated=True,
                ai_decision_id=decision.id if decision else None,
                source="PINNACLE21",
            )

        if decision is not None and actor is not None:
            await self._ai_decision.complete_decision(
                decision=decision,
                output={
                    "finding_count": len(findings),
                    "error_count": sum(1 for f in findings if f.status == "FAIL"),
                },
                reasoning=(
                    f"Pinnacle 21 validation completed with {len(findings)} finding(s)"
                ),
                confidence=1.0,
            )

        return findings

    async def validate_study(
        self,
        study_id: UUID,
        org_id: UUID,
        db: AsyncSession | None = None,
    ) -> list[P21Finding]:
        """Validate all SDTM artifacts for a study."""
        if not self.enabled:
            return []

        repo = ArtifactRepository(db or self._db)
        artifacts, _ = await repo.list_by_study(study_id, org_id, limit=100, offset=0)
        sdtm_arts = [
            a for a in artifacts if a.artifact_type == ArtifactType.SDTM_DATASET
        ]
        all_findings: list[P21Finding] = []
        for art in sdtm_arts:
            findings = await self.validate_sdtm_dataset(
                dataset_path=f"artifact:{art.id}",
                ig_version=self._settings.SDTM_IG_VERSION,
                rule_set=self._settings.PINNACLE21_RULE_SET_VERSION,
                organization_id=org_id,
                study_id=study_id,
                validation_run_id=None,
                artifact_id=art.id,
                actor=None,
            )
            all_findings.extend(findings)
        return all_findings

    async def _call_p21_api(
        self,
        *,
        dataset_path: str,
        ig_version: str,
        rule_set: str,
    ) -> list[P21Finding]:
        """POST to Pinnacle 21 validation endpoint."""
        url = f"{self._settings.PINNACLE21_API_BASE_URL.rstrip('/')}/v1/validate"
        headers = {
            "Authorization": f"Bearer {self._settings.PINNACLE21_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "dataset_path": dataset_path,
            "ig_version": ig_version,
            "rule_set": rule_set,
            "project_id": self._settings.PINNACLE21_PROJECT_ID or None,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        return self._parse_findings(data)

    @staticmethod
    def _parse_findings(data: dict | list) -> list[P21Finding]:
        """Map P21 API JSON to normalised findings."""
        raw_items: list[dict]
        if isinstance(data, list):
            raw_items = data
        else:
            raw_items = data.get("findings", data.get("issues", []))

        findings: list[P21Finding] = []
        for item in raw_items:
            severity = str(item.get("severity", item.get("level", "ERROR"))).upper()
            status_raw = item.get("status", "FAIL")
            if severity in ("NOTICE", "INFO"):
                status_raw = "PASS" if item.get("status") != "FAIL" else status_raw
            findings.append(
                P21Finding(
                    rule_id=str(item.get("rule_id", item.get("id", "P21-UNKNOWN"))),
                    rule_name=str(
                        item.get("rule_name", item.get("name", "Pinnacle 21 rule"))
                    ),
                    severity=severity,
                    message=str(item.get("message", item.get("description", ""))),
                    domain=item.get("domain"),
                    variable=item.get("variable"),
                    status=str(status_raw).upper(),
                )
            )
        return findings
