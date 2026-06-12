"""AI mapping suggestion service — propose raw column → eCRF/SDTM mappings.

CIP compliance:
  - begin_decision() before any AI inference
  - complete_decision() with output, reasoning, confidence
  - Suggestions are returned for human review; applying them uses map_field()
    with ai_decision_id so lineage and graph edges are AI-tagged.
"""

from __future__ import annotations

import json
import re
from uuid import UUID

import anthropic
from anthropic.types import TextBlock
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.permissions import Permission, check_permission
from app.models.audit import AuditAction
from app.models.raw_data import RawField
from app.models.user import User
from app.repositories.raw_data_repository import (
    RawDatasetRepository,
    RawFieldRepository,
)
from app.schemas.raw_data import (
    ApplyMappingSuggestionsRequest,
    FieldMappingSuggestion,
    SuggestMappingsResponse,
)
from app.services.audit_service import AuditService
from app.services.intelligence_service import AIDecisionService
from app.services.mapping_service import MappingService

_AGENT_NAME = "mapping-suggestion-agent"
_MODEL_ID = "claude-haiku-4-5-20251001"
_BATCH_SIZE = 18

_SYSTEM_PROMPT = """You are a clinical data standards expert specializing in CDASH eCRF fields and CDISC SDTM variable mapping.

Given a list of raw dataset columns with profiling metadata, propose the best eCRF field name and SDTM variable for each column.

Rules:
- Use standard SDTM notation: DOMAIN.VARIABLE (e.g. DM.USUBJID, AE.AETERM, LB.LBTEST)
- Use CDASH-style eCRF field names (e.g. SUBJID, AGE, SEX, AETERM)
- Return ONLY valid JSON — no prose outside the JSON
- One entry per input column

Output schema:
{
  "suggestions": [
    {
      "column_name": "<exact column name from input>",
      "mapped_ecrf_field_id": "<eCRF field or null>",
      "mapped_sdtm_variable_id": "<SDTM variable or null>",
      "confidence": <0.0-1.0>,
      "reasoning": "<one sentence>"
    }
  ]
}"""

# Deterministic fallback when no API key (local dev / tests).
_RULE_MAP: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"^usubjid$", re.I), "SUBJID", "DM.USUBJID"),
    (re.compile(r"^subjid$", re.I), "SUBJID", "DM.SUBJID"),
    (re.compile(r"^studyid$", re.I), "STUDYID", "DM.STUDYID"),
    (re.compile(r"subj|subject", re.I), "SUBJID", "DM.USUBJID"),
    (re.compile(r"^age$", re.I), "AGE", "DM.AGE"),
    (re.compile(r"sex|gender", re.I), "SEX", "DM.SEX"),
    (re.compile(r"race", re.I), "RACE", "DM.RACE"),
    (re.compile(r"ethnic", re.I), "ETHNIC", "DM.ETHNIC"),
    (re.compile(r"^arm$", re.I), "ARM", "DM.ARM"),
    (re.compile(r"treat|trt", re.I), "TRT01P", "EX.EXTRT"),
    (re.compile(r"randdt|rand", re.I), "RANDDTC", "DM.RANDDTC"),
    (re.compile(r"trtsdt|trtstdt", re.I), "RFSTDTC", "DM.RFSTDTC"),
    (re.compile(r"trtedt", re.I), "RFENDTC", "DM.RFENDTC"),
    (re.compile(r"disposition|dscat", re.I), "DSDECOD", "DS.DSDECOD"),
    (re.compile(r"height", re.I), "HEIGHT", "VS.HEIGHT"),
    (re.compile(r"weight", re.I), "WEIGHT", "VS.WEIGHT"),
    (re.compile(r"^bmi", re.I), "BMI", "VS.BMI"),
    (re.compile(r"^sbp|sysbp", re.I), "SYSBP", "VS.SYSBP"),
    (re.compile(r"^dbp|diabp", re.I), "DIABP", "VS.DIABP"),
    (re.compile(r"^hr$|heart.?rate", re.I), "HR", "VS.HR"),
    (
        re.compile(r"hba1c|glucose|ldl|hdl|triglycer|creatinine|alt|ast", re.I),
        "LBORRES",
        "LB.LBORRES",
    ),
    (re.compile(r"ae|adverse", re.I), "AETERM", "AE.AETERM"),
    (re.compile(r"visit|sv", re.I), "VISIT", "SV.VISIT"),
    (re.compile(r"siteid|site", re.I), "SITEID", "DM.SITEID"),
    (re.compile(r"date", re.I), "RFSTDTC", "DM.RFSTDTC"),
]


class MappingSuggestionService:
    """Generate and apply AI-proposed raw field mappings."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._ds_repo = RawDatasetRepository(db)
        self._field_repo = RawFieldRepository(db)
        self._mapping = MappingService(db)
        self._ai_decision = AIDecisionService(db)
        self._audit = AuditService(db)
        settings = get_settings()
        self._client = (
            anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            if settings.ANTHROPIC_API_KEY
            else None
        )

    async def suggest_mappings(
        self,
        dataset_id: UUID,
        organization_id: UUID,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> SuggestMappingsResponse:
        """Run AI inference to propose eCRF/SDTM mappings for all dataset columns."""
        check_permission(actor, Permission.AI_GENERATION_TRIGGER)

        dataset = await self._ds_repo.get(dataset_id, organization_id)
        if dataset is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Dataset not found."},
            )

        fields = await self._field_repo.list_for_dataset(dataset_id, organization_id)
        if not fields:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "NO_FIELDS",
                    "message": "Dataset has no parsed columns to map.",
                },
            )

        field_input = [
            {
                "field_id": str(f.id),
                "column_name": f.column_name,
                "inferred_type": f.inferred_type,
                "missing_count": f.missing_count,
                "distinct_count": f.distinct_count,
                "current_ecrf": f.mapped_ecrf_field_id,
                "current_sdtm": f.mapped_sdtm_variable_id,
            }
            for f in fields
        ]

        decision = await self._ai_decision.begin_decision(
            organization_id=organization_id,
            study_id=dataset.study_id,
            agent_name=_AGENT_NAME,
            decision_type="FIELD_MAPPING_SUGGESTION",
            model_id=_MODEL_ID,
            model_provider="anthropic",
            input_context={
                "dataset_id": str(dataset_id),
                "dataset_name": dataset.dataset_name,
                "field_count": len(fields),
                "fields": field_input,
            },
        )

        try:
            raw_suggestions, reasoning, confidence = await self._infer_mappings(
                dataset_name=dataset.dataset_name,
                fields=fields,
            )
        except Exception as exc:
            await self._ai_decision.complete_decision(
                decision=decision,
                output={"error": str(exc)},
                reasoning=f"Mapping suggestion failed: {exc}",
                confidence=0.0,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "code": "AI_SUGGESTION_FAILED",
                    "message": f"AI mapping suggestion failed: {exc}",
                },
            ) from exc

        suggestions = self._build_suggestions(fields, raw_suggestions)

        await self._ai_decision.complete_decision(
            decision=decision,
            output={
                "dataset_id": str(dataset_id),
                "suggestion_count": len(suggestions),
                "suggestions": [s.model_dump(mode="json") for s in suggestions],
            },
            reasoning=reasoning,
            confidence=confidence,
        )

        await self._audit.log(
            action=AuditAction.AI_MAPPING_SUGGESTED,
            resource_type="raw_dataset",
            organization_id=organization_id,
            actor_user_id=actor.id,
            resource_id=dataset_id,
            after_state={
                "ai_decision_id": str(decision.id),
                "suggestion_count": len(suggestions),
                "dataset_name": dataset.dataset_name,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self._db.flush()
        return SuggestMappingsResponse(
            ai_decision_id=decision.id,
            dataset_id=dataset_id,
            suggestions=suggestions,
            model_id=_MODEL_ID,
        )

    async def apply_suggestions(
        self,
        dataset_id: UUID,
        body: ApplyMappingSuggestionsRequest,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> list[RawField]:
        """Apply AI suggestions as PENDING_APPROVAL mappings (human review still required)."""
        check_permission(actor, Permission.ARTIFACT_EDIT)

        dataset = await self._ds_repo.get(dataset_id, actor.organization_id)
        if dataset is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Dataset not found."},
            )

        applied: list[RawField] = []
        for item in body.suggestions:
            field = await self._mapping.map_field(
                field_id=item.field_id,
                mapped_ecrf_field_id=item.mapped_ecrf_field_id,
                mapped_sdtm_variable_id=item.mapped_sdtm_variable_id,
                notes=item.notes
                or f"Applied from AI suggestion (decision {body.ai_decision_id})",
                actor=actor,
                ip_address=ip_address,
                user_agent=user_agent,
                ai_decision_id=body.ai_decision_id,
                is_ai_generated=True,
            )
            applied.append(field)

        return applied

    async def _infer_mappings(
        self,
        dataset_name: str,
        fields: list[RawField],
    ) -> tuple[list[dict], str, float]:
        """Call Claude in batches or use rule-based fallback."""
        if self._client is None:
            return self._rule_based_suggestions(fields)

        all_suggestions: list[dict] = []
        fallback_batches = 0
        for start in range(0, len(fields), _BATCH_SIZE):
            batch = fields[start : start + _BATCH_SIZE]
            try:
                batch_suggestions = await self._infer_mappings_batch(
                    dataset_name=dataset_name,
                    fields=batch,
                )
                all_suggestions.extend(batch_suggestions)
            except Exception:
                fallback, _, _ = self._rule_based_suggestions(batch)
                all_suggestions.extend(fallback)
                fallback_batches += 1

        avg_conf = (
            sum(s.get("confidence", 0.8) for s in all_suggestions)
            / len(all_suggestions)
            if all_suggestions
            else 0.0
        )
        if fallback_batches:
            reasoning = (
                "AI-proposed mappings for most columns; rule-based fallback used "
                f"for {fallback_batches} batch(es) where model output was invalid."
            )
        else:
            reasoning = (
                "AI-proposed CDASH/SDTM mappings from column profiling metadata "
                f"({len(fields)} columns in batches of {_BATCH_SIZE})"
            )
        return all_suggestions, reasoning, avg_conf

    async def _infer_mappings_batch(
        self,
        *,
        dataset_name: str,
        fields: list[RawField],
    ) -> list[dict]:
        """Run AI inference for one column batch."""
        user_prompt = (
            f"Dataset: {dataset_name}\n\nColumns:\n"
            f"{json.dumps([{'column_name': f.column_name, 'inferred_type': f.inferred_type, 'missing_count': f.missing_count, 'distinct_count': f.distinct_count} for f in fields], indent=2)}"
        )

        response = await self._client.messages.create(
            model=_MODEL_ID,
            max_tokens=4096,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = ""
        for block in response.content:
            if isinstance(block, TextBlock):
                text += block.text
        parsed = self._parse_json_response(text)
        return parsed.get("suggestions", [])

    @staticmethod
    def _rule_based_suggestions(
        fields: list[RawField],
    ) -> tuple[list[dict], str, float]:
        """Deterministic fallback when Anthropic API key is not configured."""
        results: list[dict] = []
        for field in fields:
            ecrf, sdtm = None, None
            for pattern, e, s in _RULE_MAP:
                if pattern.search(field.column_name):
                    ecrf, sdtm = e, s
                    break
            if not ecrf:
                ecrf = field.column_name.upper().replace(" ", "_")[:20]
                sdtm = f"SUPP.{ecrf}"
            results.append(
                {
                    "column_name": field.column_name,
                    "mapped_ecrf_field_id": ecrf,
                    "mapped_sdtm_variable_id": sdtm,
                    "confidence": 0.6,
                    "reasoning": "Rule-based fallback mapping (no API key configured).",
                }
            )
        return results, "Rule-based fallback mappings applied", 0.6

    def _build_suggestions(
        self,
        fields: list[RawField],
        raw: list[dict],
    ) -> list[FieldMappingSuggestion]:
        """Match AI output to field IDs by column name."""
        by_name = {f.column_name.lower(): f for f in fields}
        suggestions: list[FieldMappingSuggestion] = []

        for item in raw:
            col = str(item.get("column_name", "")).strip()
            field = by_name.get(col.lower())
            if field is None:
                continue
            ecrf = item.get("mapped_ecrf_field_id")
            sdtm = item.get("mapped_sdtm_variable_id")
            if not ecrf and not sdtm:
                continue
            suggestions.append(
                FieldMappingSuggestion(
                    field_id=field.id,
                    column_name=field.column_name,
                    mapped_ecrf_field_id=str(ecrf) if ecrf else None,
                    mapped_sdtm_variable_id=str(sdtm) if sdtm else None,
                    confidence=float(item.get("confidence", 0.8)),
                    reasoning=str(item.get("reasoning", "AI-proposed mapping")),
                )
            )

        # Include any fields the model missed via rule-based fill-in
        suggested_ids = {s.field_id for s in suggestions}
        for field in fields:
            if field.id in suggested_ids:
                continue
            fallback, _, _ = self._rule_based_suggestions([field])
            if fallback:
                item = fallback[0]
                suggestions.append(
                    FieldMappingSuggestion(
                        field_id=field.id,
                        column_name=field.column_name,
                        mapped_ecrf_field_id=item.get("mapped_ecrf_field_id"),
                        mapped_sdtm_variable_id=item.get("mapped_sdtm_variable_id"),
                        confidence=0.5,
                        reasoning="Gap-fill fallback for column not returned by model.",
                    )
                )

        return suggestions

    @staticmethod
    def _parse_json_response(text: str) -> dict:
        cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE)
        try:
            return json.loads(cleaned.strip())
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            array_match = re.search(r"\[.*\]", cleaned, re.DOTALL)
            if array_match:
                try:
                    items = json.loads(array_match.group())
                    if isinstance(items, list):
                        return {"suggestions": items}
                except json.JSONDecodeError:
                    pass
            raise ValueError("Could not parse JSON from AI response")
