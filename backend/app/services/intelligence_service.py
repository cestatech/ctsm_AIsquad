"""Intelligence service — AI decision logging, human overrides, and lineage.

COMPLIANCE CRITICAL: Every AI action in the platform MUST create an AIDecision
record via this service BEFORE executing any downstream effect. No AI action is
permitted to modify data without a logged decision record.

Human overrides MUST be recorded when a user changes a value that was AI-generated.
These records are immutable and are required for regulatory submission evidence.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.intelligence import (
    AIDecision,
    AIDecisionStatus,
    ArtifactLineage,
    DataLineage,
    DataLineageType,
    HumanOverride,
    ValidationEvidence,
    ValidationEvidenceStatus,
)
from app.models.user import User
from app.repositories.intelligence_repository import (
    AIDecisionRepository,
    DataLineageRepository,
    HumanOverrideRepository,
    ValidationEvidenceRepository,
)
from app.services.context_graph_service import ContextGraphService


class AIDecisionService:
    """
    Creates and manages AI decision records.

    Every call to begin_decision() and complete_decision() emits a GraphEvent
    so the Context Graph contains the full "why" for every AI action.

    Usage pattern in AI agents:
        decision = await ai_decision_svc.begin_decision(
            organization_id=org_id, study_id=study_id,
            agent_name="sdtm-agent", decision_type="FIELD_MAPPING",
            input_context={...}, model_id="claude-opus-4-7",
        )
        # ... run the AI logic ...
        await ai_decision_svc.complete_decision(
            decision, output={...}, reasoning="...", confidence=0.94
        )
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = AIDecisionRepository(db)
        self._graph = ContextGraphService(db)

    async def begin_decision(
        self,
        organization_id: UUID,
        agent_name: str,
        decision_type: str,
        input_context: dict,
        study_id: UUID | None = None,
        module: str | None = None,
        agent_version: str | None = None,
        model_id: str | None = None,
        model_provider: str | None = None,
        prompt_hash: str | None = None,
        prompt_tokens: int | None = None,
        input_artifact_ids: list[UUID] | None = None,
    ) -> AIDecision:
        """
        Create a PENDING_REVIEW decision record before the AI action executes.

        Call this at the start of every AI operation. The returned decision ID
        is threaded through all downstream writes so they can reference it.
        """
        decision = AIDecision(
            organization_id=organization_id,
            study_id=study_id,
            agent_name=agent_name,
            agent_version=agent_version,
            decision_type=decision_type,
            module=module,
            model_id=model_id,
            model_provider=model_provider,
            prompt_hash=prompt_hash,
            prompt_tokens=prompt_tokens,
            input_artifact_ids=input_artifact_ids,
            input_context=input_context,
            output={},
            status=AIDecisionStatus.PENDING_REVIEW,
        )
        decision = await self._repo.create(decision)

        await self._graph.emit_event(
            organization_id=organization_id,
            study_id=study_id,
            event_type="AI_DECISION_STARTED",
            actor_agent_id=agent_name,
            ai_decision_id=decision.id,
            payload={
                "agent_name": agent_name,
                "agent_version": agent_version,
                "decision_type": decision_type,
                "module": module,
                "model_id": model_id,
                "input_context": input_context,
            },
        )
        return decision

    async def complete_decision(
        self,
        decision: AIDecision,
        output: dict,
        reasoning: str | None = None,
        confidence: float | None = None,
        completion_tokens: int | None = None,
        output_artifact_ids: list[UUID] | None = None,
        graph_node_id: UUID | None = None,
    ) -> AIDecision:
        """
        Record the output of a completed AI decision.

        Must be called immediately after the AI operation completes, within
        the same transaction.
        """
        decision.output = output
        decision.reasoning = reasoning
        decision.confidence = confidence
        if completion_tokens is not None:
            decision.completion_tokens = completion_tokens
        if output_artifact_ids is not None:
            decision.output_artifact_ids = output_artifact_ids
        if graph_node_id is not None:
            decision.graph_node_id = graph_node_id
        await self._db.flush()

        # The reasoning payload is the "why" — this is the key event for AI
        # introspection. Anyone querying the graph can find this event by
        # ai_decision_id and read exactly why the AI produced this output.
        await self._graph.emit_event(
            organization_id=decision.organization_id,
            study_id=decision.study_id,
            event_type="AI_DECISION_COMPLETED",
            actor_agent_id=decision.agent_name,
            ai_decision_id=decision.id,
            node_id=graph_node_id,
            payload={
                "agent_name": decision.agent_name,
                "decision_type": decision.decision_type,
                "reasoning": reasoning,
                "confidence": confidence,
                "output": output,
            },
        )
        return decision

    async def accept_decision(
        self,
        decision_id: UUID,
        organization_id: UUID,
        reviewed_by: User,
        notes: str | None = None,
    ) -> AIDecision:
        """Human accepts an AI decision. Transitions to ACCEPTED."""
        decision = await self._repo.update_status(
            decision_id=decision_id,
            organization_id=organization_id,
            new_status=AIDecisionStatus.ACCEPTED,
            reviewed_by_id=reviewed_by.id,
            review_notes=notes,
        )
        await self._graph.emit_event(
            organization_id=organization_id,
            study_id=decision.study_id,
            event_type="AI_DECISION_ACCEPTED",
            actor_user_id=reviewed_by.id,
            ai_decision_id=decision.id,
            payload={
                "agent_name": decision.agent_name,
                "decision_type": decision.decision_type,
                "review_notes": notes,
                "reviewer_id": str(reviewed_by.id),
            },
        )
        return decision

    async def reject_decision(
        self,
        decision_id: UUID,
        organization_id: UUID,
        reviewed_by: User,
        notes: str | None = None,
    ) -> AIDecision:
        """Human rejects an AI decision. Transitions to REJECTED."""
        if not notes:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "REJECTION_REASON_REQUIRED",
                    "message": "A reason is required when rejecting an AI decision.",
                },
            )
        decision = await self._repo.update_status(
            decision_id=decision_id,
            organization_id=organization_id,
            new_status=AIDecisionStatus.REJECTED,
            reviewed_by_id=reviewed_by.id,
            review_notes=notes,
        )
        await self._graph.emit_event(
            organization_id=organization_id,
            study_id=decision.study_id,
            event_type="AI_DECISION_REJECTED",
            actor_user_id=reviewed_by.id,
            ai_decision_id=decision.id,
            payload={
                "agent_name": decision.agent_name,
                "decision_type": decision.decision_type,
                "rejection_reason": notes,
                "reviewer_id": str(reviewed_by.id),
            },
        )
        return decision

    async def get_decision(
        self, decision_id: UUID, organization_id: UUID
    ) -> AIDecision:
        return await self._repo.get(decision_id, organization_id)

    async def list_for_study(
        self,
        study_id: UUID,
        organization_id: UUID,
        agent_name: str | None = None,
        decision_type: str | None = None,
        decision_status: AIDecisionStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AIDecision], int]:
        return await self._repo.list_for_study(
            study_id=study_id,
            organization_id=organization_id,
            agent_name=agent_name,
            decision_type=decision_type,
            status=decision_status,
            limit=limit,
            offset=offset,
        )

    async def list_pending(
        self, organization_id: UUID, limit: int = 50
    ) -> list[AIDecision]:
        return await self._repo.pending_for_org(organization_id, limit)


class HumanOverrideService:
    """
    Records immutable human override events.

    Call this whenever a user edits a value that was AI-generated.
    The override is always recorded — even if the user is correcting
    their own previous override. The full chain of changes is preserved.

    Every override emits a HUMAN_OVERRIDE GraphEvent with the reason in the
    payload so the Context Graph contains the full correction history.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = HumanOverrideRepository(db)
        self._graph = ContextGraphService(db)

    async def record_override(
        self,
        organization_id: UUID,
        actor: User,
        context_type: str,
        original_value: dict | None,
        new_value: dict | None,
        reason: str,
        override_type: str,
        study_id: UUID | None = None,
        ai_decision_id: UUID | None = None,
        context_id: UUID | None = None,
        field_path: str | None = None,
        graph_node_id: UUID | None = None,
    ) -> HumanOverride:
        """
        Create a human override record. reason is mandatory.

        override_type examples: "VALUE_CORRECTION", "DECISION_REJECTION",
        "MAPPING_CORRECTION", "WAIVER", "MANUAL_ENTRY"
        """
        if not reason.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "OVERRIDE_REASON_REQUIRED",
                    "message": "A justification is required for human overrides.",
                },
            )

        override = HumanOverride(
            organization_id=organization_id,
            study_id=study_id,
            ai_decision_id=ai_decision_id,
            context_type=context_type,
            context_id=context_id,
            field_path=field_path,
            original_value=original_value,
            new_value=new_value,
            reason=reason,
            override_type=override_type,
            graph_node_id=graph_node_id,
            actor_user_id=actor.id,
        )
        override = await self._repo.create(override)

        await self._graph.emit_event(
            organization_id=organization_id,
            study_id=study_id,
            event_type="HUMAN_OVERRIDE",
            actor_user_id=actor.id,
            ai_decision_id=ai_decision_id,
            node_id=graph_node_id,
            payload={
                "override_type": override_type,
                "context_type": context_type,
                "field_path": field_path,
                "reason": reason,
                "original_value": original_value,
                "new_value": new_value,
                "override_id": str(override.id),
            },
        )
        return override

    async def list_for_study(
        self,
        study_id: UUID,
        organization_id: UUID,
        context_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[HumanOverride], int]:
        return await self._repo.list_for_study(
            study_id=study_id,
            organization_id=organization_id,
            context_type=context_type,
            limit=limit,
            offset=offset,
        )

    async def list_for_decision(
        self, ai_decision_id: UUID, organization_id: UUID
    ) -> list[HumanOverride]:
        return await self._repo.list_for_decision(ai_decision_id, organization_id)


class DataLineageService:
    """
    Records data and artifact lineage relationships.

    The full lineage chain — raw data → SDTM → ADaM → TLF → CSR — is
    captured here at both the field level (DataLineage) and the document
    level (ArtifactLineage).
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = DataLineageRepository(db)

    async def record_field_lineage(
        self,
        organization_id: UUID,
        lineage_type: DataLineageType,
        source_type: str,
        target_type: str,
        source_id: UUID | None = None,
        source_field: str | None = None,
        source_domain: str | None = None,
        target_id: UUID | None = None,
        target_field: str | None = None,
        target_domain: str | None = None,
        transformation_logic: str | None = None,
        transformation_code: str | None = None,
        assumptions: list | None = None,
        is_ai_generated: bool = False,
        ai_decision_id: UUID | None = None,
        study_id: UUID | None = None,
        created_by: User | None = None,
        source_graph_node_id: UUID | None = None,
        target_graph_node_id: UUID | None = None,
    ) -> DataLineage:
        lineage = DataLineage(
            organization_id=organization_id,
            study_id=study_id,
            lineage_type=lineage_type,
            source_type=source_type,
            source_id=source_id,
            source_field=source_field,
            source_domain=source_domain,
            target_type=target_type,
            target_id=target_id,
            target_field=target_field,
            target_domain=target_domain,
            transformation_logic=transformation_logic,
            transformation_code=transformation_code,
            assumptions=assumptions,
            is_ai_generated=is_ai_generated,
            ai_decision_id=ai_decision_id,
            created_by_id=created_by.id if created_by else None,
            source_graph_node_id=source_graph_node_id,
            target_graph_node_id=target_graph_node_id,
        )
        return await self._repo.create(lineage)

    async def record_artifact_lineage(
        self,
        organization_id: UUID,
        source_artifact_id: UUID,
        target_artifact_id: UUID,
        relationship_type: str,
        study_id: UUID | None = None,
        source_version_id: UUID | None = None,
        target_version_id: UUID | None = None,
        derivation_notes: str | None = None,
        is_ai_generated: bool = False,
        ai_decision_id: UUID | None = None,
        created_by: User | None = None,
    ) -> ArtifactLineage:
        link = ArtifactLineage(
            organization_id=organization_id,
            study_id=study_id,
            source_artifact_id=source_artifact_id,
            source_version_id=source_version_id,
            target_artifact_id=target_artifact_id,
            target_version_id=target_version_id,
            relationship_type=relationship_type,
            derivation_notes=derivation_notes,
            is_ai_generated=is_ai_generated,
            ai_decision_id=ai_decision_id,
            created_by_id=created_by.id if created_by else None,
        )
        return await self._repo.create_artifact_lineage(link)

    async def get_upstream_lineage(
        self,
        target_type: str,
        target_id: UUID,
        organization_id: UUID,
    ) -> list[DataLineage]:
        return await self._repo.lineage_chain_for_target(
            target_type, target_id, organization_id
        )

    async def get_downstream_lineage(
        self,
        source_type: str,
        source_id: UUID,
        organization_id: UUID,
    ) -> list[DataLineage]:
        return await self._repo.lineage_chain_for_source(
            source_type, source_id, organization_id
        )

    async def get_artifact_lineage_for_study(
        self, study_id: UUID, organization_id: UUID
    ) -> list[ArtifactLineage]:
        return await self._repo.artifact_lineage_for_study(study_id, organization_id)


class ValidationIntelligenceService:
    """
    Records and manages validation evidence.

    Each ValidationEvidence record ties a finding to the specific data element
    and CDISC rule that was checked. Findings can be waived with a mandatory
    justification recorded as a HumanOverride.

    Every finding and waiver emits a GraphEvent so the Context Graph contains
    the full validation history for each data element.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = ValidationEvidenceRepository(db)
        self._graph = ContextGraphService(db)

    async def record_evidence(
        self,
        organization_id: UUID,
        subject_type: str,
        evidence_status: ValidationEvidenceStatus,
        finding_details: dict,
        study_id: UUID | None = None,
        validation_run_id: UUID | None = None,
        rule_id: str | None = None,
        rule_name: str | None = None,
        rule_category: str | None = None,
        cdisc_standard: str | None = None,
        subject_id: UUID | None = None,
        subject_field: str | None = None,
        subject_value: dict | None = None,
        finding_severity: str | None = None,
        finding_message: str | None = None,
        is_ai_evaluated: bool = False,
        ai_decision_id: UUID | None = None,
        graph_node_id: UUID | None = None,
    ) -> ValidationEvidence:
        evidence = ValidationEvidence(
            organization_id=organization_id,
            study_id=study_id,
            validation_run_id=validation_run_id,
            rule_id=rule_id,
            rule_name=rule_name,
            rule_category=rule_category,
            cdisc_standard=cdisc_standard,
            subject_type=subject_type,
            subject_id=subject_id,
            subject_field=subject_field,
            subject_value=subject_value,
            status=evidence_status,
            finding_severity=finding_severity,
            finding_message=finding_message,
            finding_details=finding_details,
            is_ai_evaluated=is_ai_evaluated,
            ai_decision_id=ai_decision_id,
            graph_node_id=graph_node_id,
        )
        evidence = await self._repo.create(evidence)

        await self._graph.emit_event(
            organization_id=organization_id,
            study_id=study_id,
            event_type="VALIDATION_FINDING",
            ai_decision_id=ai_decision_id,
            node_id=graph_node_id,
            payload={
                "rule_id": rule_id,
                "rule_name": rule_name,
                "cdisc_standard": cdisc_standard,
                "subject_field": subject_field,
                "status": evidence_status.value,
                "finding_severity": finding_severity,
                "finding_message": finding_message,
                "is_ai_evaluated": is_ai_evaluated,
            },
        )
        return evidence

    async def waive_finding(
        self,
        evidence_id: UUID,
        organization_id: UUID,
        waived_by: User,
        reason: str,
    ) -> ValidationEvidence:
        if not reason.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "WAIVER_REASON_REQUIRED",
                    "message": "A justification is required to waive a validation finding.",
                },
            )
        evidence = await self._repo.waive(
            evidence_id=evidence_id,
            organization_id=organization_id,
            waived_by_id=waived_by.id,
            reason=reason,
        )
        await self._graph.emit_event(
            organization_id=organization_id,
            study_id=evidence.study_id,
            event_type="VALIDATION_WAIVED",
            actor_user_id=waived_by.id,
            payload={
                "evidence_id": str(evidence_id),
                "rule_id": evidence.rule_id,
                "rule_name": evidence.rule_name,
                "subject_field": evidence.subject_field,
                "waiver_reason": reason,
                "waived_by": str(waived_by.id),
            },
        )
        return evidence

    async def list_for_run(
        self,
        validation_run_id: UUID,
        organization_id: UUID,
        evidence_status: ValidationEvidenceStatus | None = None,
    ) -> list[ValidationEvidence]:
        return await self._repo.list_for_run(
            validation_run_id, organization_id, evidence_status
        )

    async def list_for_study(
        self,
        study_id: UUID,
        organization_id: UUID,
        evidence_status: ValidationEvidenceStatus | None = None,
        rule_category: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[ValidationEvidence], int]:
        return await self._repo.list_for_study(
            study_id=study_id,
            organization_id=organization_id,
            evidence_status=evidence_status,
            rule_category=rule_category,
            limit=limit,
            offset=offset,
        )
